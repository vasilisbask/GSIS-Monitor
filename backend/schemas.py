from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

# Service Schemas
class ServiceBase(BaseModel):
    name: str = Field(..., max_length=100)
    url: str = Field(..., max_length=255)
    verification_keyword: Optional[str] = Field(None, max_length=100)
    exclusion_keyword: Optional[str] = Field(None, max_length=100)
    skip_tls_verify: Optional[bool] = False
    is_active: Optional[bool] = True
    order_index: Optional[int] = 0

class ServiceCreate(ServiceBase):
    pass

class ServiceUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    url: Optional[str] = Field(None, max_length=255)
    verification_keyword: Optional[str] = None
    exclusion_keyword: Optional[str] = None
    skip_tls_verify: Optional[bool] = None
    is_active: Optional[bool] = None
    order_index: Optional[int] = None

class ServiceResponse(ServiceBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# PingLog Schemas
class PingLogBase(BaseModel):
    time: datetime
    service_id: int
    is_healthy: bool
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    dns_lookup_ms: Optional[float] = None
    tcp_connect_ms: Optional[float] = None
    tls_handshake_ms: Optional[float] = None
    ttfb_ms: Optional[float] = None
    total_response_ms: Optional[float] = None
    ssl_expiry_days: Optional[int] = None
    content_verified: bool = False

class PingLogResponse(PingLogBase):
    model_config = ConfigDict(from_attributes=True)

# AlertRule Schemas
class AlertRuleBase(BaseModel):
    service_id: int
    metric: str
    operator: str
    value: float
    is_active: Optional[bool] = True

class AlertRuleCreate(AlertRuleBase):
    pass

class AlertRuleResponse(AlertRuleBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# AlertLog Schemas
class AlertLogBase(BaseModel):
    service_id: int
    alert_rule_id: Optional[int] = None
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    status: str
    message: str

class AlertLogResponse(AlertLogBase):
    id: int
    service_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# Dashboard Summary Schemas
class ServiceSummary(BaseModel):
    id: int
    name: str
    url: str
    is_active: bool
    is_healthy: bool
    last_status_code: Optional[int] = None
    last_response_time_ms: Optional[float] = None
    last_ping_time: Optional[datetime] = None
    ssl_expiry_days: Optional[int] = None
    active_alerts_count: int

class DashboardSummary(BaseModel):
    total_services: int
    active_services: int
    healthy_services: int
    unhealthy_services: int
    active_alerts: int
    average_response_time_ms: float
    services: List[ServiceSummary]
