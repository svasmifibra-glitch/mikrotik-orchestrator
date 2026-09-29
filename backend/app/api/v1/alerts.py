from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.models import Alert
from app.schemas.schemas import AlertOut
from app.api.v1.auth import get_current_user

router = APIRouter(prefix="/alerts", tags=["Alerts"])

@router.get("/", response_model=List[AlertOut])
def list_alerts(acknowledged: bool = False, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    return db.query(Alert).filter(Alert.acknowledged == acknowledged).order_by(Alert.created_at.desc()).all()

@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    a = db.query(Alert).filter(Alert.id == alert_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Alert not found")
    a.acknowledged = True
    db.commit()
    return {"status": "acknowledged"}
