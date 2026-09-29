from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(String, default="admin") # admin, operator, viewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Router(Base):
    __tablename__ = "routers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    serial_number = Column(String, index=True, nullable=True)
    mac_address = Column(String, nullable=True)
    
    # Connection info
    host = Column(String, nullable=True) # IP address or hostname
    port = Column(Integer, default=8728) # Default RouterOS API port
    rest_port = Column(Integer, default=443) # HTTPS REST API port
    api_user = Column(String, default="admin")
    api_password = Column(String, nullable=True)
    
    # Cloud provisioning token (used by agent script fetch)
    provision_token = Column(String, unique=True, index=True, nullable=False)
    
    # Device State
    status = Column(String, default="unprovisioned") # online, offline, unprovisioned
    model_name = Column(String, nullable=True) # e.g. RB750Gr3, hAP ac3, CHR
    board_name = Column(String, nullable=True)
    routeros_version = Column(String, nullable=True) # e.g. 7.14.2
    architecture = Column(String, nullable=True) # e.g. arm64, mmips, x86
    
    # Real-time Metrics
    cpu_load = Column(Float, default=0.0) # Percentage 0-100%
    memory_used_mb = Column(Float, default=0.0)
    memory_total_mb = Column(Float, default=0.0)
    disk_used_mb = Column(Float, default=0.0)
    disk_total_mb = Column(Float, default=0.0)
    uptime = Column(String, nullable=True)
    last_seen = Column(DateTime, nullable=True)
    
    # Organization
    group_name = Column(String, default="Default")
    tags = Column(String, nullable=True) # Comma-separated tags
    location = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    backups = relationship("Backup", back_populates="router", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="router", cascade="all, delete-orphan")

class Backup(Base):
    __tablename__ = "backups"

    id = Column(Integer, primary_key=True, index=True)
    router_id = Column(Integer, ForeignKey("routers.id"), nullable=False)
    backup_type = Column(String, default="rsc") # rsc (export text) or backup (binary)
    filename = Column(String, nullable=False)
    file_size = Column(Integer, default=0) # Bytes
    content_rsc = Column(Text, nullable=True) # Text export for diffs & viewing
    created_at = Column(DateTime, default=datetime.utcnow)

    router = relationship("Router", back_populates="backups")

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    target_routers = Column(Text, nullable=False) # JSON list or "ALL" or "group:Default"
    script_content = Column(Text, nullable=False)
    status = Column(String, default="pending") # pending, running, completed, failed
    execution_results = Column(JSON, nullable=True) # {"router_1": {"status": "ok", "output": "..."}, ...}
    scheduled_at = Column(DateTime, default=datetime.utcnow)
    executed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    router_id = Column(Integer, ForeignKey("routers.id"), nullable=False)
    alert_type = Column(String, nullable=False) # cpu_high, memory_high, offline, firmware_outdated
    message = Column(String, nullable=False)
    severity = Column(String, default="warning") # info, warning, critical
    acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    router = relationship("Router", back_populates="alerts")
