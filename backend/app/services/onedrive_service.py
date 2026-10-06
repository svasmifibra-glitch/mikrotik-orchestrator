import os
import httpx
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("onedrive_service")

BACKUPS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "backups"))

class OneDriveService:
    """
    Manages backup synchronization with Microsoft OneDrive:
    1. Local physical persistence for rclone / OneDrive client auto-sync.
    2. Direct Microsoft Graph API upload if access token is configured.
    3. Webhook / Power Automate sync if webhook URL is configured.
    """

    @staticmethod
    def get_backup_dir() -> str:
        os.makedirs(BACKUPS_DIR, exist_ok=True)
        return BACKUPS_DIR

    @staticmethod
    def save_physical_backup(router_name: str, filename: str, content: str) -> str:
        """Saves physical .rsc file to server disk for rclone/OneDrive synchronization"""
        safe_name = "".join(c for c in router_name if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
        router_dir = os.path.join(OneDriveService.get_backup_dir(), safe_name)
        os.makedirs(router_dir, exist_ok=True)
        file_path = os.path.join(router_dir, filename)
        with open(file_path, "w", encoding="utf-8", errors="ignore") as f:
            f.write(content)
        logger.info(f"Physical backup saved for OneDrive sync: {file_path}")
        return file_path

    @staticmethod
    async def upload_to_graph_api(filename: str, content: str, access_token: str, folder: str = "MikroTik_Backups") -> Dict[str, Any]:
        """Uploads backup file directly to Microsoft OneDrive via Microsoft Graph API"""
        url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{folder}/{filename}:/content"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "text/plain"
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.put(url, headers=headers, content=content.encode("utf-8"))
                if response.status_code in (200, 201):
                    return {"success": True, "message": "Uploaded to OneDrive successfully", "data": response.json()}
                else:
                    return {"success": False, "message": f"Graph API error HTTP {response.status_code}: {response.text}"}
            except Exception as e:
                return {"success": False, "message": str(e)}

    @staticmethod
    async def trigger_webhook_sync(webhook_url: str, router_name: str, filename: str, content: str) -> Dict[str, Any]:
        """Sends backup payload to Power Automate / OneDrive webhook"""
        payload = {
            "router_name": router_name,
            "filename": filename,
            "timestamp": datetime.utcnow().isoformat(),
            "content": content
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(webhook_url, json=payload)
                return {"success": response.status_code in (200, 201, 202), "status_code": response.status_code}
            except Exception as e:
                return {"success": False, "message": str(e)}
