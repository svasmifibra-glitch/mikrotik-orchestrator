import difflib
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.models.models import Backup, Router
from app.schemas.schemas import BackupOut
from app.services.mikrotik_client import MikroTikClient
from app.api.v1.auth import get_current_user

router = APIRouter(prefix="/backups", tags=["Backups"])

@router.get("/", response_model=List[BackupOut])
def list_backups(router_id: Optional[int] = None, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    query = db.query(Backup)
    if router_id:
        query = query.filter(Backup.router_id == router_id)
    return query.order_by(Backup.created_at.desc()).all()

@router.post("/trigger/{router_id}", response_model=BackupOut)
async def trigger_manual_backup(router_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    r = db.query(Router).filter(Router.id == router_id).first()
    if not r or not r.host:
        raise HTTPException(status_code=400, detail="Router must have direct host IP configured to pull backup on demand")

    # SSH command to run export
    cmd_res = MikroTikClient.execute_ssh_command(r.host, r.api_user or "admin", r.api_password or "", "/export hide-sensitive")
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=f"Backup export failed: {cmd_res.get('error')}")

    content = cmd_res.get("output", "")
    b = Backup(
        router_id=r.id,
        backup_type="rsc",
        filename=f"manual_{r.name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.rsc",
        file_size=len(content.encode('utf-8')),
        content_rsc=content
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return b

@router.get("/{backup_id}/download")
def download_backup(backup_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    b = db.query(Backup).filter(Backup.id == backup_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Backup not found")
    
    return Response(
        content=b.content_rsc or "",
        media_type="application/text",
        headers={"Content-Disposition": f'attachment; filename="{b.filename}"'}
    )

@router.get("/diff")
def diff_backups(backup_a_id: int, backup_b_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    b1 = db.query(Backup).filter(Backup.id == backup_a_id).first()
    b2 = db.query(Backup).filter(Backup.id == backup_b_id).first()
    if not b1 or not b2:
        raise HTTPException(status_code=404, detail="One or both backups not found")

    lines1 = (b1.content_rsc or "").splitlines(keepends=True)
    lines2 = (b2.content_rsc or "").splitlines(keepends=True)
    diff = list(difflib.unified_diff(lines1, lines2, fromfile=b1.filename, tofile=b2.filename))
    
    return {
        "backup_a": {"id": b1.id, "filename": b1.filename, "date": b1.created_at},
        "backup_b": {"id": b2.id, "filename": b2.filename, "date": b2.created_at},
        "diff": "".join(diff)
    }
