from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import logging

from app.core.config import settings
from app.core.database import get_db
from app.models.models import Router, Alert, Backup, Task
from app.services.provisioning import generate_routeros_agent_script
from app.services.onedrive_service import OneDriveService

logger = logging.getLogger("agent")

router = APIRouter(prefix="/agent", tags=["Agent RouterOS"])

def get_server_url(request: Request) -> str:
    """Accurately computes server URL taking into account reverse proxy Host & Port"""
    if settings.SERVER_HOST and not settings.SERVER_HOST.startswith("http://localhost") and not settings.SERVER_HOST.startswith("http://127.0.0.1"):
        return settings.SERVER_HOST.rstrip('/')
    
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    proto = request.headers.get("x-forwarded-proto") or ("https" if request.url.is_secure else "http")
    if host:
        return f"{proto}://{host}".rstrip('/')
    return str(request.base_url).rstrip('/')

@router.get("/script/{token}")
def get_agent_provision_script(token: str, request: Request, db: Session = Depends(get_db)):
    """Returns the .rsc setup script for MikroTik fetch command"""
    r = db.query(Router).filter(Router.provision_token == token).first()
    if not r:
        raise HTTPException(status_code=404, detail="Invalid provision token")
    
    server_url = get_server_url(request)
    rsc_content = generate_routeros_agent_script(token, server_url)
    return Response(content=rsc_content, media_type="text/plain")

@router.api_route("/poll", methods=["GET", "POST"])
async def agent_poll(request: Request, db: Session = Depends(get_db)):
    """
    Bidirectional polling endpoint called every 60s by MikroTik agent.
    1. Collects live telemetry (CPU, RAM, Uptime, Version, Serial).
    2. Returns pending commands or backup tasks as RouterOS executable script.
    """
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

    # Update telemetry
    r.status = "online"
    r.last_seen = datetime.utcnow()

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
    if serial_val and serial_val != "CHR" and serial_val != "NO_SERIAL":
        r.serial_number = str(serial_val)

    model_val = data.get("model") or data.get("model_name")
    if model_val: r.model_name = str(model_val)

    uptime_val = data.get("uptime")
    if uptime_val: r.uptime = str(uptime_val)

    # Detect IP
    client_ip = request.client.host if request.client else None
    if client_ip and client_ip != "127.0.0.1":
        r.host = client_ip

    server_url = get_server_url(request)
    mode = "https" if server_url.startswith("https") else "http"

    # Default idle response (small, won't trigger import)
    task_script = "# idle\n"

    # Check for pending tasks or commands
    if r.pending_command:
        cmd = r.pending_command.strip()
        logger.info(f"Dispatching pending command to router '{r.name}': {cmd[:30]}...")

        if cmd == "backup":
            task_script = f"""# Automated backup task
:log info "Orchestrator: Executing configuration backup export..."
:do {{
    /file remove [find name="orch_export.rsc"]
    :delay 1s
    /export file="orch_export" hide-sensitive
    :delay 4s
    /tool fetch url="{server_url}/api/v1/agent/upload-backup?token={token}" mode={mode} http-method=post upload=yes src-path="orch_export.rsc"
    :delay 2s
    /file remove [find name="orch_export.rsc"]
    :log info "Orchestrator: Backup export successfully sent to cloud."
}} on-error={{
    :log error "Orchestrator: Backup export failed."
}}
"""
            r.pending_command = None

        elif cmd.startswith("script:"):
            actual_script = cmd[7:]
            task_script = f"""# Custom batch script task
:log info "Orchestrator: Executing custom remote task..."
:do {{
    {actual_script}
    :log info "Orchestrator: Remote task completed."
}} on-error={{
    :log error "Orchestrator: Remote task failed."
}}
"""
            r.pending_command = None

        elif cmd == "reboot":
            task_script = """# Reboot command
:log warning "Orchestrator: System reboot ordered from cloud platform..."
:delay 2s
/system reboot
"""
            r.pending_command = None

        else:
            task_script = f"""# Command execution
:do {{
    {cmd}
}} on-error={{
    :log error "Orchestrator: Command failed."
}}
"""
            r.pending_command = None

    db.commit()
    return Response(content=task_script, media_type="text/plain")

@router.post("/upload-backup")
async def upload_backup(request: Request, token: Optional[str] = None, db: Session = Depends(get_db)):
    """Receives uploaded .rsc export from MikroTik router via /tool fetch upload=yes"""
    token_val = token or request.query_params.get("token") or request.headers.get("x-router-token")
    if not token_val:
        raise HTTPException(status_code=400, detail="Missing router token")

    r = db.query(Router).filter(Router.provision_token == token_val).first()
    if not r:
        raise HTTPException(status_code=404, detail="Unknown router token")

    body_bytes = await request.body()
    if not body_bytes or len(body_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty backup payload received")

    content_str = body_bytes.decode('utf-8', errors='ignore')
    clean_name = r.name.replace(' ', '_')
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    filename = f"backup_{clean_name}_{timestamp}.rsc"

    # Save real backup into database
    b = Backup(
        router_id=r.id,
        backup_type="rsc",
        filename=filename,
        file_size=len(body_bytes),
        content_rsc=content_str,
        created_at=datetime.utcnow()
    )
    db.add(b)

    r.status = "online"
    r.last_seen = datetime.utcnow()
    r.last_backup_at = datetime.utcnow()

    # Clean any pending backup command
    if r.pending_command == "backup":
        r.pending_command = None

    db.commit()
    logger.info(f"✅ Real backup saved for '{r.name}': {filename} ({len(body_bytes)} bytes)")

    try:
        OneDriveService.save_physical_backup(r.name, filename, content_str)
        # Automatic cloud sync to OneDrive
        OneDriveService.run_rclone_sync()
    except Exception as e:
        logger.error(f"Error saving physical backup or syncing for OneDrive: {e}")

    return {"status": "ok", "filename": filename, "size": len(body_bytes)}

@router.api_route("/heartbeat", methods=["GET", "POST"])
async def handle_agent_heartbeat(request: Request, db: Session = Depends(get_db)):
    """Fallback legacy heartbeat endpoint (redirects to poll logic)"""
    return await agent_poll(request, db)
