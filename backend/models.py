from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from .database import Base
import datetime

class Service(Base):
    __tablename__ = "service"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    url = Column(String(255), nullable=False)
    verification_keyword = Column(String(100), nullable=True)
    exclusion_keyword = Column(String(100), nullable=True)
    skip_tls_verify = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    order_index = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    logs = relationship("PingLog", back_populates="service", cascade="all, delete-orphan")
    rules = relationship("AlertRule", back_populates="service", cascade="all, delete-orphan")
    alerts = relationship("AlertLog", back_populates="service", cascade="all, delete-orphan")

class PingLog(Base):
    __tablename__ = "ping_log"

    time = Column(DateTime(timezone=True), primary_key=True, default=datetime.datetime.utcnow)
    service_id = Column(Integer, ForeignKey("service.id", ondelete="CASCADE"), primary_key=True)
    is_healthy = Column(Boolean, nullable=False)
    status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    dns_lookup_ms = Column(Float, nullable=True)
    tcp_connect_ms = Column(Float, nullable=True)
    tls_handshake_ms = Column(Float, nullable=True)
    ttfb_ms = Column(Float, nullable=True)
    total_response_ms = Column(Float, nullable=True)
    ssl_expiry_days = Column(Integer, nullable=True)
    content_verified = Column(Boolean, default=False)

    service = relationship("Service", back_populates="logs")

class AlertRule(Base):
    __tablename__ = "alert_rule"

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("service.id", ondelete="CASCADE"), nullable=False)
    metric = Column(String(50), nullable=False) # latency, status_code, ssl_expiry, content_verified
    operator = Column(String(10), nullable=False) # >, <, =, !=
    value = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

    service = relationship("Service", back_populates="rules")
    alerts = relationship("AlertLog", back_populates="rule", cascade="all, delete-orphan")

class AlertLog(Base):
    __tablename__ = "alert_log"

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("service.id", ondelete="CASCADE"), nullable=False)
    alert_rule_id = Column(Integer, ForeignKey("alert_rule.id", ondelete="SET NULL"), nullable=True)
    triggered_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), default="active") # active, resolved
    message = Column(Text, nullable=False)

    service = relationship("Service", back_populates="alerts")
    rule = relationship("AlertRule", back_populates="alerts")
