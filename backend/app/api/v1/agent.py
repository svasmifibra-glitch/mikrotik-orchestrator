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

@router.api_route("/heartbeat", methods=["GET", "POST"])
async def handle_agent_heartbeat(request: Request, db: Session = Depends(get_db)):
    """Universal endpoint accepting GET query params or POST JSON for 100% RouterOS compatibility"""
    data = {}
    if request.method == "POST":
        try:
            data = await request.json()
        except Exception:
            data = dict(request.query_params)
    else:
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

    # Extract metrics safely (supports GET keys 'cpu', 'ros', 'serial', etc.)
    cpu_val = data.get("cpu") or data.get("cpu_load")
    if cpu_val:
        try: r.cpu_load = float(cpu_val)
        except Exception: pass

    mem_used = data.get("mem_used") or data.get("memory_used_mb")
    if mem_used:
        try: r.memory_used_mb = float(mem_used)
        except Exception: pass

    mem_total = data.get("mem_total") or data.get("memory_total_mb")
    if mem_total:
        try: r.memory_total_mb = float(mem_total)
        except Exception: pass

    ros_ver = data.get("ros") or data.get("routeros_version")
    if ros_ver: r.routeros_version = str(ros_ver)

    arch_val = data.get("arch") or data.get("architecture")
    if arch_val: r.architecture = str(arch_val)

    board_val = data.get("board") or data.get("board_name")
    if board_val: r.board_name = str(board_val)

    serial_val = data.get("serial") or data.get("serial_number")
    if serial_val: r.serial_number = str(serial_val)

    model_val = data.get("model") or data.get("model_name")
    if model_val: r.model_name = str(model_val)

    uptime_val = data.get("uptime")
    if uptime_val: r.uptime = str(uptime_val)

    # Auto-detect Public IP of remote router
    client_ip = request.client.host if request.client else None
    if client_ip and client_ip != "127.0.0.1":
        r.host = client_ip

    db.commit()
    logger.info(f"Received heartbeat from router '{r.name}' (Serial: {r.serial_number or 'N/A'}, IP: {r.host})")

    return {"status": "ok", "ack": True}
