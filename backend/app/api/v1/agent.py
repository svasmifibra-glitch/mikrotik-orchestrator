from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.models.models import Router, Alert, Backup
from app.schemas.schemas import HeartbeatPayload
from app.services.provisioning import generate_routeros_agent_script

router = APIRouter(prefix="/agent", tags=["Agent RouterOS"])

@router.get("/script/{token}")
def get_agent_provision_script(token: str, request: Request, db: Session = Depends(get_db)):
    """Returns the .rsc setup script for MikroTik fetch command"""
    r = db.query(Router).filter(Router.provision_token == token).first()
    if not r:
        raise HTTPException(status_code=404, detail="Invalid provision token")
    
    server_url = str(request.base_url).rstrip('/')
    rsc_content = generate_routeros_agent_script(token, server_url)
    return Response(content=rsc_content, media_type="text/plain")

@router.post("/heartbeat")
def handle_agent_heartbeat(payload: HeartbeatPayload, db: Session = Depends(get_db)):
    """Receives periodic metrics and heartbeat from MikroTik router script"""
    r = db.query(Router).filter(Router.provision_token == payload.token).first()
    if not r:
        raise HTTPException(status_code=404, detail="Unknown router token")

    # Update telemetry
    r.status = "online"
    r.last_seen = datetime.utcnow()
    if payload.cpu_load is not None: r.cpu_load = payload.cpu_load
    if payload.memory_used_mb is not None: r.memory_used_mb = payload.memory_used_mb
    if payload.memory_total_mb is not None: r.memory_total_mb = payload.memory_total_mb
    if payload.disk_used_mb is not None: r.disk_used_mb = payload.disk_used_mb
    if payload.disk_total_mb is not None: r.disk_total_mb = payload.disk_total_mb
    if payload.routeros_version: r.routeros_version = payload.routeros_version
    if payload.architecture: r.architecture = payload.architecture
    if payload.board_name: r.board_name = payload.board_name
    if payload.serial_number: r.serial_number = payload.serial_number
    if payload.model_name: r.model_name = payload.model_name
    if payload.uptime: r.uptime = payload.uptime
    if payload.public_ip: r.host = payload.public_ip

    # Generate CPU high alert if cpu > 90%
    if r.cpu_load > 90.0:
        alert = Alert(
            router_id=r.id,
            alert_type="cpu_high",
            message=f"High CPU load on {r.name}: {r.cpu_load}%",
            severity="warning"
        )
        db.add(alert)

    # Save RSC config backup if provided
    if payload.export_rsc:
        b = Backup(
            router_id=r.id,
            backup_type="rsc",
            filename=f"auto_backup_{r.name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.rsc",
            file_size=len(payload.export_rsc),
            content_rsc=payload.export_rsc
        )
        db.add(b)

    db.commit()

    # Response to router - can return commands if queued
    return {"status": "ok", "ack": True}
