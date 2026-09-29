import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.models import Task, Router
from app.services.mikrotik_client import MikroTikClient

logger = logging.getLogger("task_runner")

class TaskRunnerService:
    @staticmethod
    async def execute_task_now(db: Session, task_id: int):
        """Executes a batch script task across targeted routers"""
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return
        
        task.status = "running"
        task.executed_at = datetime.utcnow()
        db.commit()

        # Target selection
        if task.target_routers == "ALL":
            routers = db.query(Router).all()
        elif task.target_routers.startswith("group:"):
            group_name = task.target_routers.replace("group:", "").strip()
            routers = db.query(Router).filter(Router.group_name == group_name).all()
        else:
            try:
                router_ids = [int(rid.strip()) for rid in task.target_routers.split(",") if rid.strip().isdigit()]
                routers = db.query(Router).filter(Router.id.in_(router_ids)).all()
            except Exception:
                routers = []

        results = {}
        all_success = True

        for router in routers:
            if not router.host:
                results[f"router_{router.id}"] = {
                    "name": router.name,
                    "status": "pending_agent",
                    "output": "No direct IP. Task queued for next agent heartbeat."
                }
                continue

            res = await MikroTikClient.run_script_rest(
                host=router.host,
                user=router.api_user or "admin",
                password=router.api_password or "",
                script=task.script_content,
                port=router.rest_port or 443
            )
            
            results[f"router_{router.id}"] = {
                "name": router.name,
                "status": "success" if res.get("success") else "failed",
                "output": res.get("output", "") or res.get("error", "")
            }
            if not res.get("success"):
                all_success = False

        task.status = "completed" if all_success else "failed"
        task.execution_results = results
        db.commit()
        return task
