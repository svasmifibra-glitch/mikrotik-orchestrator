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

@router.post("/{router_id}/reboot")
async def reboot_router(router_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    r = db.query(Router).filter(Router.id == router_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Router not found")
    
    # Direct SSH reboot if reachable
    if r.host and r.api_user and r.api_password:
        MikroTikClient.execute_ssh_command(r.host, r.api_user or "admin", r.api_password or "", "/system reboot")
        return {"status": "rebooting", "mode": "direct", "message": f"Comando de reinicio enviado directamente a {r.name}"}

    # Queue for next agent poll
    r.pending_command = "reboot"
    db.commit()
    return {"status": "queued", "mode": "agent", "message": f"Reinicio encolado para {r.name}. Se ejecutará en el próximo ciclo (máx 60s)."}

@router.post("/{router_id}/command")
async def execute_router_command(router_id: int, payload: dict, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    r = db.query(Router).filter(Router.id == router_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Router not found")
    
    command = payload.get("command", "").strip()
    if not command:
        raise HTTPException(status_code=400, detail="Command cannot be empty")

    # If direct host available, execute immediately
    if r.host and r.api_user and r.api_password:
        res = MikroTikClient.execute_ssh_command(r.host, r.api_user or "admin", r.api_password or "", command)
        output = res.get("output", "") or res.get("error", "")
        r.last_command_output = output
        db.commit()
        return {"status": "executed", "output": output}

    # Queue for agent
    r.pending_command = f"script:{command}"
    db.commit()
    return {"status": "queued", "output": f"Comando encolado para el router. Se ejecutará en su próximo reporte (máx 60s)."}

from app.services.provisioning import generate_onboarding_command, generate_uninstall_command
from app.services.onedrive_service import OneDriveService

@router.put("/{router_id}/settings")
def update_router_settings(router_id: int, payload: dict, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Updates auto-backup interval, retention limit, and polling interval"""
    r = db.query(Router).filter(Router.id == router_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Router not found")

    if "auto_backup_interval" in payload:
        r.auto_backup_interval = payload["auto_backup_interval"]
    if "backup_retention_count" in payload:
        try:
            r.backup_retention_count = int(payload["backup_retention_count"])
        except Exception:
            pass
    if "poll_interval_seconds" in payload:
        try:
            r.poll_interval_seconds = max(30, int(payload["poll_interval_seconds"]))
        except Exception:
            pass

    db.commit()
    db.refresh(r)
    return {
        "status": "updated",
        "router_id": r.id,
        "auto_backup_interval": r.auto_backup_interval,
        "backup_retention_count": r.backup_retention_count,
        "poll_interval_seconds": r.poll_interval_seconds
    }

@router.get("/{router_id}/uninstall-command")
def get_router_uninstall_command(router_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Returns the RouterOS terminal script to cleanly uninstall and remove the orchestrator agent"""
    r = db.query(Router).filter(Router.id == router_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Router not found")
    
    cmd = generate_uninstall_command()
    return {
        "router_id": r.id,
        "router_name": r.name,
        "command": cmd
    }

@router.delete("/{router_id}")
def delete_router(router_id: int, queue_uninstall: bool = Query(True), db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    r = db.query(Router).filter(Router.id == router_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Router not found")

    uninstall_cmd = generate_uninstall_command()

    # If the router has direct host SSH credentials, attempt to execute uninstall immediately
    if r.host and r.api_user and r.api_password:
        try:
            MikroTikClient.execute_ssh_command(r.host, r.api_user or "admin", r.api_password or "", uninstall_cmd)
        except Exception:
            pass

    # If router is online via agent, queue the uninstall script so it cleans itself on its final poll
    if r.status == "online" and queue_uninstall:
        # Enqueue uninstall command as pending script
        r.pending_command = f"script:{uninstall_cmd}"
        db.commit()

    db.delete(r)
    db.commit()
    return {
        "status": "deleted",
        "uninstall_command": uninstall_cmd,
        "message": f"Router '{r.name}' desvinculado de la plataforma."
    }
