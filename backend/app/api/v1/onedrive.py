import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.models.models import Backup, Router
from app.services.onedrive_service import OneDriveService
from app.api.v1.auth import get_current_user, require_roles

router = APIRouter(prefix="/onedrive", tags=["OneDrive Sync"])

class OneDriveConfig(BaseModel):
    access_token: Optional[str] = None
    webhook_url: Optional[str] = None
    folder_name: str = "MikroTik_Backups"

# In-memory config cache (or environment)
onedrive_config = {
    "access_token": os.getenv("ONEDRIVE_ACCESS_TOKEN", ""),
    "webhook_url": os.getenv("ONEDRIVE_WEBHOOK_URL", ""),
    "folder_name": os.getenv("ONEDRIVE_FOLDER", "MikroTik_Backups")
}

@router.get("/status")
def get_onedrive_status(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    backup_dir = OneDriveService.get_backup_dir()
    file_count = 0
    if os.path.exists(backup_dir):
        for root, dirs, files in os.walk(backup_dir):
            file_count += len([f for f in files if f.endswith('.rsc')])
    
    total_db_backups = db.query(Backup).count()

    host_backup_dir = os.getenv("HOST_BACKUPS_DIR", "/opt/mikrotik-orchestrator/data/backups")
    return {
        "status": "ready",
        "backup_storage_path": host_backup_dir,
        "physical_files_count": file_count,
        "total_backups_db": total_db_backups,
        "has_access_token": bool(onedrive_config["access_token"]),
        "has_webhook": bool(onedrive_config["webhook_url"]),
        "folder_name": onedrive_config["folder_name"],
        "rclone_command": f"rclone sync {host_backup_dir} onedrive:{onedrive_config['folder_name']}"
    }

@router.post("/settings")
def save_onedrive_settings(config: OneDriveConfig, current_user = Depends(get_current_user)):
    if config.access_token is not None:
        onedrive_config["access_token"] = config.access_token.strip()
    if config.webhook_url is not None:
        onedrive_config["webhook_url"] = config.webhook_url.strip()
    if config.folder_name:
        onedrive_config["folder_name"] = config.folder_name.strip()
    
    return {"status": "saved", "config": {
        "has_access_token": bool(onedrive_config["access_token"]),
        "has_webhook": bool(onedrive_config["webhook_url"]),
        "folder_name": onedrive_config["folder_name"]
    }}

@router.post("/sync/{backup_id}")
async def sync_single_backup(backup_id: int, db: Session = Depends(get_db), current_user = Depends(require_roles("admin", "operator"))):
    b = db.query(Backup).filter(Backup.id == backup_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Backup not found")
    
    r = db.query(Router).filter(Router.id == b.router_id).first()
    router_name = r.name if r else f"Router_{b.router_id}"

    # 1. Always save physical file on disk
    file_path = OneDriveService.save_physical_backup(router_name, b.filename, b.content_rsc or "")

    results = {"physical_path": file_path, "cloud_sync": "saved_to_disk"}

    # 2. Upload to Microsoft Graph API if token is provided
    if onedrive_config["access_token"]:
        graph_res = await OneDriveService.upload_to_graph_api(
            filename=b.filename,
            content=b.content_rsc or "",
            access_token=onedrive_config["access_token"],
            folder=onedrive_config["folder_name"]
        )
        results["graph_api"] = graph_res

    # 3. Trigger webhook if webhook URL is provided
    if onedrive_config["webhook_url"]:
        webhook_res = await OneDriveService.trigger_webhook_sync(
            webhook_url=onedrive_config["webhook_url"],
            router_name=router_name,
            filename=b.filename,
            content=b.content_rsc or ""
        )
        results["webhook"] = webhook_res

    # 4. Trigger rclone sync directly
    rclone_res = OneDriveService.run_rclone_sync(folder=onedrive_config["folder_name"])
    results["rclone"] = rclone_res

    return {"status": "synced", "details": results}

@router.post("/sync-all")
async def sync_all_backups(db: Session = Depends(get_db), current_user = Depends(require_roles("admin", "operator"))):
    """Exports all existing database backups to physical disk and triggers rclone sync to OneDrive"""
    backups = db.query(Backup).all()
    routers = {r.id: r.name for r in db.query(Router).all()}
    
    synced_count = 0
    saved_files = []
    for b in backups:
        r_name = routers.get(b.router_id, f"Router_{b.router_id}")
        fp = OneDriveService.save_physical_backup(r_name, b.filename, b.content_rsc or "")
        saved_files.append(b.filename)
        synced_count += 1
        
        if onedrive_config["access_token"]:
            await OneDriveService.upload_to_graph_api(
                filename=b.filename,
                content=b.content_rsc or "",
                access_token=onedrive_config["access_token"],
                folder=onedrive_config["folder_name"]
            )
        if onedrive_config["webhook_url"]:
            await OneDriveService.trigger_webhook_sync(
                webhook_url=onedrive_config["webhook_url"],
                router_name=r_name,
                filename=b.filename,
                content=b.content_rsc or ""
            )

    # Trigger rclone sync to upload all files to OneDrive
    rclone_res = OneDriveService.run_rclone_sync(folder=onedrive_config["folder_name"])
    host_backup_dir = os.getenv("HOST_BACKUPS_DIR", "/opt/mikrotik-orchestrator/data/backups")

    return {
        "status": "completed",
        "synced_count": synced_count,
        "backup_storage_path": host_backup_dir,
        "rclone": rclone_res,
        "files": saved_files
    }

