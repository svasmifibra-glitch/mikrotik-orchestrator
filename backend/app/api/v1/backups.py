import difflib
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.models.models import Backup, Router, Task
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
    if not r:
        raise HTTPException(status_code=404, detail="Router not found")

    # Try SSH direct export if credentials are provided
    if r.host and r.api_user and r.api_password:
        cmd_res = MikroTikClient.execute_ssh_command(r.host, r.api_user or "admin", r.api_password or "", "/export hide-sensitive")
        if cmd_res.get("success") and cmd_res.get("output"):
            content = cmd_res.get("output", "")
            b = Backup(
                router_id=r.id,
                backup_type="rsc",
                filename=f"export_{r.name.replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.rsc",
                file_size=len(content.encode('utf-8')),
                content_rsc=content
            )
            db.add(b)
            db.commit()
            db.refresh(b)
            return b

    # If agent-connected, queue backup task & create backup log entry
    clean_name = r.name.replace(' ', '_')
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    
    # Queue task for agent
    t = Task(
        title=f"Backup Export for {r.name}",
        description="Automated config export task",
        target_routers=str(r.id),
        script_content="/export hide-sensitive",
        status="pending"
    )
    db.add(t)

    b = Backup(
        router_id=r.id,
        backup_type="rsc",
        filename=f"export_{clean_name}_{timestamp}.rsc",
        file_size=1024,
        content_rsc=f"# Respaldo de Configuración generado para {r.name} (Serial: {r.serial_number or 'N/A'})\n# Fecha: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n/system identity set name=\"{r.name}\"\n/system resource print\n# Exportación en ejecución..."
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
