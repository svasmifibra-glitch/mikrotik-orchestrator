from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from app.core.database import get_db
from app.models.models import Router, Task
from app.services.task_runner import TaskRunnerService
from app.api.v1.auth import get_current_user

router = APIRouter(prefix="/firmware", tags=["Firmware Management"])

@router.get("/summary")
def get_firmware_summary(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    routers = db.query(Router).all()
    versions: Dict[str, int] = {}
    outdated = 0
    total = len(routers)

    # Standard recommended stable version baseline
    RECOMMENDED_STABLE = "7.14.3"

    for r in routers:
        v = r.routeros_version or "Unknown"
        versions[v] = versions.get(v, 0) + 1
        if v != "Unknown" and v < RECOMMENDED_STABLE:
            outdated += 1

    return {
        "total_devices": total,
        "recommended_version": RECOMMENDED_STABLE,
        "outdated_count": outdated,
        "version_distribution": versions
    }

@router.post("/batch-upgrade")
def trigger_batch_upgrade(channel: str = "stable", db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Creates a batch task to trigger RouterOS auto-upgrade on targeted routers"""
    upgrade_script = f"""
/system package update set channel={channel}
/system package update check-for-updates
/system package update install
"""
    t = Task(
        title=f"Batch RouterOS Upgrade ({channel})",
        description=f"Automated fleet update to latest {channel} release",
        target_routers="ALL",
        script_content=upgrade_script.strip(),
        status="pending"
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"message": "Batch upgrade task created", "task_id": t.id}
