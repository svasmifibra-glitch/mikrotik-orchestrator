from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.models import Task
from app.schemas.schemas import TaskCreate, TaskOut
from app.services.task_runner import TaskRunnerService
from app.api.v1.auth import get_current_user

router = APIRouter(prefix="/tasks", tags=["Batch Tasks"])

@router.get("/", response_model=List[TaskOut])
def list_tasks(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    return db.query(Task).order_by(Task.created_at.desc()).all()

@router.post("/", response_model=TaskOut)
def create_task(task_in: TaskCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    t = Task(
        title=task_in.title,
        description=task_in.description,
        target_routers=task_in.target_routers,
        script_content=task_in.script_content,
        status="pending"
    )
    db.add(t)
    db.commit()
    db.refresh(t)

    # Launch background execution
    background_tasks.add_task(TaskRunnerService.execute_task_now, db, t.id)
    return t

@router.post("/{task_id}/run")
async def run_task_now(task_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    t = await TaskRunnerService.execute_task_now(db, task_id)
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    return t
