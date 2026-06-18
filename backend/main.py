from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timezone, timedelta

from .database import get_db, engine
from . import models, schemas

import os

# Create tables only if not in testing mode
if os.getenv("TESTING") != "1":
    try:
        models.Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Warning: Database table creation failed (Postgres may be offline): {e}")

app = FastAPI(title="GSIS Monitor API", version="1.0.0")

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service Endpoints

@app.get("/api/services", response_model=List[schemas.ServiceResponse])
def get_services(db: Session = Depends(get_db)):
    return db.query(models.Service).order_by(models.Service.id).all()

@app.post("/api/services", response_model=schemas.ServiceResponse, status_code=status.HTTP_201_CREATED)
def create_service(service: schemas.ServiceCreate, db: Session = Depends(get_db)):
    db_service = models.Service(**service.model_dump())
    try:
        db.add(db_service)
        db.commit()
        db.refresh(db_service)
        return db_service
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Service creation failed: {str(e)}")

@app.put("/api/services/{service_id}", response_model=schemas.ServiceResponse)
def update_service(service_id: int, service_update: schemas.ServiceUpdate, db: Session = Depends(get_db)):
    db_service = db.query(models.Service).filter(models.Service.id == service_id).first()
    if not db_service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    update_data = service_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_service, key, value)
        
    db.commit()
    db.refresh(db_service)
    return db_service

@app.delete("/api/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(service_id: int, db: Session = Depends(get_db)):
    db_service = db.query(models.Service).filter(models.Service.id == service_id).first()
    if not db_service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    db.delete(db_service)
    db.commit()
    return None


# Alert Rules Endpoints

@app.get("/api/rules", response_model=List[schemas.AlertRuleResponse])
def get_rules(db: Session = Depends(get_db)):
    return db.query(models.AlertRule).all()

@app.post("/api/rules", response_model=schemas.AlertRuleResponse, status_code=status.HTTP_201_CREATED)
def create_rule(rule: schemas.AlertRuleCreate, db: Session = Depends(get_db)):
    db_rule = models.AlertRule(**rule.model_dump())
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    return db_rule

@app.delete("/api/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    db_rule = db.query(models.AlertRule).filter(models.AlertRule.id == rule_id).first()
    if not db_rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    db.delete(db_rule)
    db.commit()
    return None


# Alert Logs Endpoints

@app.get("/api/alerts", response_model=List[schemas.AlertLogResponse])
def get_alerts(status_filter: Optional[str] = Query(None, alias="status"), db: Session = Depends(get_db)):
    query = db.query(models.AlertLog, models.Service.name.label("service_name"))\
              .join(models.Service, models.AlertLog.service_id == models.Service.id)
    
    if status_filter:
        query = query.filter(models.AlertLog.status == status_filter)
        
    results = query.order_by(models.AlertLog.triggered_at.desc()).all()
    
    # Map results into response schema structure
    alerts = []
    for log, s_name in results:
        alert_dict = {c.name: getattr(log, c.name) for c in log.__table__.columns}
        alert_dict["service_name"] = s_name
        alerts.append(alert_dict)
    return alerts

@app.put("/api/alerts/{alert_id}/resolve", response_model=schemas.AlertLogResponse)
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    db_alert = db.query(models.AlertLog).filter(models.AlertLog.id == alert_id).first()
    if not db_alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    if db_alert.status == "resolved":
         raise HTTPException(status_code=400, detail="Alert already resolved")
         
    db_alert.status = "resolved"
    db_alert.resolved_at = datetime.now(timezone.utc)
    db_alert.message = f"{db_alert.message} (Manually resolved)"
    db.commit()
    db.refresh(db_alert)
    
    # Get service name for response
    service_name = db.query(models.Service.name).filter(models.Service.id == db_alert.service_id).scalar()
    
    alert_dict = {c.name: getattr(db_alert, c.name) for c in db_alert.__table__.columns}
    alert_dict["service_name"] = service_name
    return alert_dict


# Telemetry Logs Endpoint

@app.get("/api/services/{service_id}/logs", response_model=List[schemas.PingLogResponse])
def get_service_logs(
    service_id: int, 
    range_param: str = Query("24h", alias="range"), 
    db: Session = Depends(get_db)
):
    # Validate service exists
    service_exists = db.query(models.Service.id).filter(models.Service.id == service_id).scalar()
    if not service_exists:
        raise HTTPException(status_code=404, detail="Service not found")
        
    now = datetime.now(timezone.utc)
    if range_param == "1h":
        start_time = now - timedelta(hours=1)
    elif range_param == "6h":
        start_time = now - timedelta(hours=6)
    elif range_param == "24h":
        start_time = now - timedelta(hours=24)
    elif range_param == "7d":
        start_time = now - timedelta(days=7)
    else:
        start_time = now - timedelta(hours=24)
        
    logs = db.query(models.PingLog)\
             .filter(models.PingLog.service_id == service_id, models.PingLog.time >= start_time)\
             .order_by(models.PingLog.time.asc())\
             .all()
    return logs


# Dashboard Summary Endpoint

@app.get("/api/dashboard/summary", response_model=schemas.DashboardSummary)
def get_dashboard_summary(db: Session = Depends(get_db)):
    services = db.query(models.Service).all()
    
    total_services = len(services)
    active_services = 0
    healthy_services = 0
    unhealthy_services = 0
    total_response_time = 0.0
    response_time_count = 0
    
    service_summaries = []
    
    for service in services:
        if service.is_active:
            active_services += 1
            
        # Get latest ping log entry
        latest_log = db.query(models.PingLog)\
                       .filter(models.PingLog.service_id == service.id)\
                       .order_by(models.PingLog.time.desc())\
                       .first()
                       
        # Get active alerts count
        active_alerts_count = db.query(models.AlertLog)\
                                .filter(models.AlertLog.service_id == service.id, models.AlertLog.status == "active")\
                                .count()
                                
        is_healthy = True
        last_status_code = None
        last_response_time_ms = None
        last_ping_time = None
        ssl_expiry_days = None
        
        if latest_log:
            is_healthy = latest_log.is_healthy
            last_status_code = latest_log.status_code
            last_response_time_ms = latest_log.total_response_ms
            last_ping_time = latest_log.time
            ssl_expiry_days = latest_log.ssl_expiry_days
            
            if service.is_active:
                if is_healthy:
                    healthy_services += 1
                else:
                    unhealthy_services += 1
                
                if last_response_time_ms is not None:
                    total_response_time += last_response_time_ms
                    response_time_count += 1
        else:
            # If no pings yet, default to healthy (or unhealthy if not active)
            if service.is_active:
                healthy_services += 1
                
        service_summaries.append(
            schemas.ServiceSummary(
                id=service.id,
                name=service.name,
                url=service.url,
                is_active=service.is_active,
                is_healthy=is_healthy,
                last_status_code=last_status_code,
                last_response_time_ms=last_response_time_ms,
                last_ping_time=last_ping_time,
                ssl_expiry_days=ssl_expiry_days,
                active_alerts_count=active_alerts_count
            )
        )
        
    active_alerts = db.query(models.AlertLog).filter(models.AlertLog.status == "active").count()
    avg_response_time = total_response_time / response_time_count if response_time_count > 0 else 0.0
    
    return schemas.DashboardSummary(
        total_services=total_services,
        active_services=active_services,
        healthy_services=healthy_services,
        unhealthy_services=unhealthy_services,
        active_alerts=active_alerts,
        average_response_time_ms=round(avg_response_time, 2),
        services=service_summaries
    )
