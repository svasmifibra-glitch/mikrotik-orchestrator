from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.core.database import get_db
from app.models.models import Router, Alert, Backup
from app.services.provisioning import generate_routeros_agent_script

logger = logging.getLogger("agent")

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
@router.get("/heartbeat")
async def handle_agent_heartbeat(request: Request, db: Session = Depends(get_db)):
    """Flexible endpoint accepting JSON POST or Query params for maximum RouterOS compatibility"""
    data = {}
    try:
        data = await request.json()
    except Exception:
        data = dict(request.query_params)

    token = data.get("token") or request.query_params.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="Missing token")

    r = db.query(Router).filter(Router.provision_token == token).first()
    if not r:
        raise HTTPException(status_code=404, detail="Unknown router token")

    # Update state & last_seen
    r.status = "online"
    r.last_seen = datetime.utcnow()

    # Safely extract metrics
    try: r.cpu_load = float(data.get("cpu_load", 0.0))
    except Exception: pass

    try: r.memory_used_mb = float(data.get("memory_used_mb", 0.0))
    except Exception: pass

    try: r.memory_total_mb = float(data.get("memory_total_mb", 0.0))
    except Exception: pass

    try: r.disk_used_mb = float(data.get("disk_used_mb", 0.0))
    except Exception: pass

    try: r.disk_total_mb = float(data.get("disk_total_mb", 0.0))
    except Exception: pass

    if data.get("routeros_version"): r.routeros_version = str(data.get("routeros_version"))
    if data.get("architecture"): r.architecture = str(data.get("architecture"))
    if data.get("board_name"): r.board_name = str(data.get("board_name"))
    if data.get("serial_number"): r.serial_number = str(data.get("serial_number"))
    if data.get("model_name"): r.model_name = str(data.get("model_name"))
    if data.get("uptime"): r.uptime = str(data.get("uptime"))
    
    # Save IP if client IP header is available
    client_ip = request.client.host if request.client else None
    if client_ip and client_ip != "127.0.0.1":
        r.host = client_ip

    # Generate CPU high alert if cpu > 90%
    if r.cpu_load > 90.0:
        alert = Alert(
            router_id=r.id,
            alert_type="cpu_high",
            message=f"High CPU load on {r.name}: {r.cpu_load}%",
            severity="warning"
        )
        db.add(alert)

    db.commit()
    logger.info(f"Received heartbeat from router '{r.name}' (ID: {r.id})")

    return {"status": "ok", "ack": True}
