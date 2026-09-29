import secrets
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.models.models import Router
from app.schemas.schemas import RouterCreate, RouterUpdate, RouterOut
from app.services.provisioning import generate_onboarding_command
from app.services.mikrotik_client import MikroTikClient
from app.api.v1.auth import get_current_user

router = APIRouter(prefix="/routers", tags=["Routers"])

@router.get("/", response_model=List[RouterOut])
def get_routers(
    group: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    query = db.query(Router)
    if group:
        query = query.filter(Router.group_name == group)
    if status:
        query = query.filter(Router.status == status)
    if search:
        query = query.filter(
            (Router.name.ilike(f"%{search}%")) | 
            (Router.model_name.ilike(f"%{search}%")) |
            (Router.serial_number.ilike(f"%{search}%")) |
            (Router.host.ilike(f"%{search}%"))
        )
    return query.order_by(Router.updated_at.desc()).all()

@router.post("/", response_model=RouterOut)
def create_router(router_in: RouterCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    provision_token = f"mt_{secrets.token_urlsafe(16)}"
    db_router = Router(
        name=router_in.name,
        host=router_in.host,
        port=router_in.port,
        rest_port=router_in.rest_port,
        api_user=router_in.api_user,
        api_password=router_in.api_password,
        group_name=router_in.group_name,
        tags=router_in.tags,
        location=router_in.location,
        provision_token=provision_token,
        status="unprovisioned"
    )
    db.add(db_router)
    db.commit()
    db.refresh(db_router)
    return db_router

@router.get("/{router_id}", response_model=RouterOut)
def get_router(router_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    r = db.query(Router).filter(Router.id == router_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Router not found")
    return r

@router.get("/{router_id}/onboarding-command")
def get_onboarding_command(router_id: int, server_url: Optional[str] = None, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    r = db.query(Router).filter(Router.id == router_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Router not found")
    
    cmd = generate_onboarding_command(r.provision_token, server_url)
    return {
        "router_id": r.id,
        "token": r.provision_token,
        "command": cmd
    }

@router.post("/{router_id}/sync")
async def sync_router_direct(router_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Triggers direct REST API sync if router has accessible IP"""
    r = db.query(Router).filter(Router.id == router_id).first()
    if not r or not r.host:
        raise HTTPException(status_code=400, detail="Router does not have a direct host IP set")
    
    res = await MikroTikClient.get_system_resource_rest(
        host=r.host,
        user=r.api_user or "admin",
        password=r.api_password or "",
        port=r.rest_port or 443
    )
    
    if res.get("status") == "online":
        r.status = "online"
        r.cpu_load = res.get("cpu_load", 0.0)
        r.memory_total_mb = res.get("memory_total_mb", 0.0)
        r.memory_used_mb = res.get("memory_used_mb", 0.0)
        r.disk_total_mb = res.get("disk_total_mb", 0.0)
        r.disk_used_mb = res.get("disk_used_mb", 0.0)
        r.routeros_version = res.get("routeros_version", "")
        r.architecture = res.get("architecture", "")
        r.board_name = res.get("board_name", "")
        r.uptime = res.get("uptime", "")
        r.last_seen = datetime.utcnow()
        
        rb = await MikroTikClient.get_routerboard_rest(r.host, r.api_user or "admin", r.api_password or "", r.rest_port or 443)
        if rb.get("serial_number"):
            r.serial_number = rb.get("serial_number")
        if rb.get("model_name"):
            r.model_name = rb.get("model_name")
            
        db.commit()
        db.refresh(r)
        return {"success": True, "router": r}
    else:
        r.status = "offline"
        db.commit()
        raise HTTPException(status_code=504, detail=f"Could not connect via REST API: {res.get('message')}")

@router.delete("/{router_id}")
def delete_router(router_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    r = db.query(Router).filter(Router.id == router_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Router not found")
    db.delete(r)
    db.commit()
    return {"status": "deleted"}
