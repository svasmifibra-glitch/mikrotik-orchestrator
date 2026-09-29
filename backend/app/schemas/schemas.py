from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any, Dict
from datetime import datetime

# Auth Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role: str = "admin"

class UserOut(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    class Config:
        from_attributes = True

# Router Schemas
class RouterCreate(BaseModel):
    name: str
    host: Optional[str] = None
    port: int = 8728
    rest_port: int = 443
    api_user: str = "admin"
    api_password: Optional[str] = None
    group_name: str = "Default"
    tags: Optional[str] = None
    location: Optional[str] = None

class RouterUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    rest_port: Optional[int] = None
    api_user: Optional[str] = None
    api_password: Optional[str] = None
    group_name: Optional[str] = None
    tags: Optional[str] = None
    location: Optional[str] = None

class RouterOut(BaseModel):
    id: int
    name: str
    serial_number: Optional[str] = None
    mac_address: Optional[str] = None
    host: Optional[str] = None
    port: int
    rest_port: int
    api_user: str
    provision_token: str
    status: str
    model_name: Optional[str] = None
    board_name: Optional[str] = None
    routeros_version: Optional[str] = None
    architecture: Optional[str] = None
    cpu_load: float
    memory_used_mb: float
    memory_total_mb: float
    disk_used_mb: float
    disk_total_mb: float
    uptime: Optional[str] = None
    last_seen: Optional[datetime] = None
    group_name: str
    tags: Optional[str] = None
    location: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Backup Schemas
class BackupOut(BaseModel):
    id: int
    router_id: int
    backup_type: str
    filename: str
    file_size: int
    content_rsc: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True

# Task Schemas
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    target_routers: str  # "ALL", "1,2,3", "group:Default"
    script_content: str

class TaskOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    target_routers: str
    script_content: str
    status: str
    execution_results: Optional[Dict[str, Any]] = None
    scheduled_at: datetime
    executed_at: Optional[datetime] = None
    created_at: datetime
    class Config:
        from_attributes = True

# Heartbeat & Telemetry schema sent by MikroTik fetch script
class HeartbeatPayload(BaseModel):
    token: str
    serial_number: Optional[str] = None
    mac_address: Optional[str] = None
    model_name: Optional[str] = None
    board_name: Optional[str] = None
    routeros_version: Optional[str] = None
    architecture: Optional[str] = None
    cpu_load: Optional[float] = 0.0
    memory_used_mb: Optional[float] = 0.0
    memory_total_mb: Optional[float] = 0.0
    disk_used_mb: Optional[float] = 0.0
    disk_total_mb: Optional[float] = 0.0
    uptime: Optional[str] = None
    public_ip: Optional[str] = None
    export_rsc: Optional[str] = None # Optional automatic config update push

class AlertOut(BaseModel):
    id: int
    router_id: int
    alert_type: str
    message: str
    severity: str
    acknowledged: bool
    created_at: datetime
    class Config:
        from_attributes = True
