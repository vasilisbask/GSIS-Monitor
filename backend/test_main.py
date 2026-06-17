import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.main import app
from backend import models

# 1. Setup in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create the database schema in the test database
Base.metadata.create_all(bind=engine)

# 2. Dependency override
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    # Clean database before each test
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

# 3. Test Endpoints

def test_create_and_read_service():
    # Create service
    response = client.post(
        "/api/services",
        json={
            "name": "e-Paravolo Test",
            "url": "https://example.gov.gr/eparavolo",
            "verification_keyword": "e-Παράβολο",
            "exclusion_keyword": "maintenance",
            "skip_tls_verify": False,
            "is_active": True,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "e-Paravolo Test"
    assert data["url"] == "https://example.gov.gr/eparavolo"
    assert "id" in data

    # Read services
    response = client.get("/api/services")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "e-Paravolo Test"

def test_update_service():
    # Create service
    response = client.post(
        "/api/services",
        json={
            "name": "Diavgeia Test",
            "url": "https://example.gov.gr/diavgeia",
            "verification_keyword": "Διαύγεια",
            "skip_tls_verify": False,
        },
    )
    service_id = response.json()["id"]

    # Update service
    response = client.put(
        f"/api/services/{service_id}",
        json={
            "url": "https://example.gov.gr/new-diavgeia",
            "verification_keyword": "Δι@ύγεια",
            "skip_tls_verify": True,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["url"] == "https://example.gov.gr/new-diavgeia"
    assert data["verification_keyword"] == "Δι@ύγεια"
    assert data["skip_tls_verify"] is True

def test_delete_service():
    # Create service
    response = client.post(
        "/api/services",
        json={"name": "Temp Service", "url": "https://temp.gov.gr"},
    )
    service_id = response.json()["id"]

    # Delete service
    response = client.delete(f"/api/services/{service_id}")
    assert response.status_code == 204

    # Verify deleted
    response = client.get("/api/services")
    assert len(response.json()) == 0

def test_create_and_delete_rule():
    # Create service
    response = client.post(
        "/api/services",
        json={"name": "Service for Rule", "url": "https://rule.gov.gr"},
    )
    service_id = response.json()["id"]

    # Create rule
    response = client.post(
        "/api/rules",
        json={
            "service_id": service_id,
            "metric": "latency",
            "operator": ">",
            "value": 2000.0,
        },
    )
    assert response.status_code == 201
    rule_data = response.json()
    assert rule_data["metric"] == "latency"
    assert rule_data["value"] == 2000.0

    # Get rules
    response = client.get("/api/rules")
    assert response.status_code == 200
    assert len(response.json()) == 1

    # Delete rule
    rule_id = rule_data["id"]
    response = client.delete(f"/api/rules/{rule_id}")
    assert response.status_code == 204

def test_resolve_alert():
    # Create service
    response = client.post(
        "/api/services",
        json={"name": "Service for Alert", "url": "https://alert.gov.gr"},
    )
    service_id = response.json()["id"]

    # Insert alert into DB manually via session
    db = TestingSessionLocal()
    db_alert = models.AlertLog(
        service_id=service_id,
        status="active",
        message="Service is offline",
    )
    db.add(db_alert)
    db.commit()
    db.refresh(db_alert)
    alert_id = db_alert.id
    db.close()

    # Get active alerts
    response = client.get("/api/alerts?status=active")
    assert response.status_code == 200
    assert len(response.json()) == 1

    # Resolve alert
    response = client.put(f"/api/alerts/{alert_id}/resolve")
    assert response.status_code == 200
    assert response.json()["status"] == "resolved"
    assert "Manually resolved" in response.json()["message"]

def test_get_service_logs_and_dashboard_summary():
    # Create service
    response = client.post(
        "/api/services",
        json={"name": "Service for Logs", "url": "https://logs.gov.gr"},
    )
    service_id = response.json()["id"]

    # Get service logs (should be empty initially)
    response = client.get(f"/api/services/{service_id}/logs?range=1h")
    assert response.status_code == 200
    assert len(response.json()) == 0

    # Get dashboard summary (should have 1 service with default healthy=True since no pings logged yet)
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    summary = response.json()
    assert summary["total_services"] == 1
    assert summary["healthy_services"] == 1
    assert summary["average_response_time_ms"] == 0.0
