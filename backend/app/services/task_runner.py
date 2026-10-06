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
            script_str = (task.script_content or "").strip()
            is_backup = "/export" in script_str or "backup" in (task.title or "").lower() or "respaldo" in (task.title or "").lower()

            # Case 1: Backup task - route directly to agent backup command
            if is_backup:
                router.pending_command = "backup"
                results[f"router_{router.id}"] = {
                    "name": router.name,
                    "status": "queued_agent",
                    "output": "Tarea de respaldo encolada para el agente MikroTik. Se ejecutará y subirá el archivo .rsc en el próximo ciclo (máx 60 segundos)."
                }
                continue

            # Case 2: Direct REST execution if credentials exist
            direct_done = False
            if router.host and router.api_password:
                try:
                    res = await MikroTikClient.run_script_rest(
                        host=router.host,
                        user=router.api_user or "admin",
                        password=router.api_password or "",
                        script=task.script_content,
                        port=router.rest_port or 443
                    )
                    if res.get("success"):
                        direct_done = True
                        results[f"router_{router.id}"] = {
                            "name": router.name,
                            "status": "success",
                            "output": res.get("output", "Ejecutado exitosamente vía conexión directa.")
                        }
                except Exception as ex:
                    logger.warning(f"Direct connection to {router.name} failed: {ex}")

            # Case 3: If direct failed or router is agent-managed behind NAT/Firewall
            if not direct_done:
                if router.provision_token:
                    router.pending_command = f"script:{task.script_content}"
                    results[f"router_{router.id}"] = {
                        "name": router.name,
                        "status": "queued_agent",
                        "output": "Router en NAT/Firewall: Comando encolado para el agente RouterOS (ejecución automática en máx 60 segundos)."
                    }
                else:
                    results[f"router_{router.id}"] = {
                        "name": router.name,
                        "status": "failed",
                        "output": "No se pudo conectar directamente y el router no cuenta con el agente RouterOS aprovisionado."
                    }
                    all_success = False

        task.status = "completed" if all_success else "failed"
        task.execution_results = results
        db.commit()
        return task
