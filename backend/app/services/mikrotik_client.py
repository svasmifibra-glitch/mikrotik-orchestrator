import httpx
import paramiko
import io
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("mikrotik_client")

class MikroTikClient:
    """
    Multi-protocol interface for RouterOS 6.x and 7.x
    Supports HTTPS REST API (RouterOS 7+) and SSH command execution fallback.
    """

    @staticmethod
    async def get_system_resource_rest(host: str, user: str, password: str, port: int = 443, use_ssl: bool = True) -> Dict[str, Any]:
        """Fetch /system/resource metrics via RouterOS REST API"""
        protocol = "https" if use_ssl else "http"
        url = f"{protocol}://{host}:{port}/rest/system/resource"
        
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            try:
                response = await client.get(url, auth=(user, password or ""))
                if response.status_code == 200:
                    data = response.json()
                    # RouterOS returns list of object or single dict
                    res = data[0] if isinstance(data, list) else data
                    
                    total_mem = float(res.get("total-memory", 0)) / (1024 * 1024)
                    free_mem = float(res.get("free-memory", 0)) / (1024 * 1024)
                    total_hdd = float(res.get("total-hdd-space", 0)) / (1024 * 1024)
                    free_hdd = float(res.get("free-hdd-space", 0)) / (1024 * 1024)
                    
                    return {
                        "status": "online",
                        "cpu_load": float(res.get("cpu-load", 0)),
                        "memory_total_mb": round(total_mem, 1),
                        "memory_used_mb": round(total_mem - free_mem, 1),
                        "disk_total_mb": round(total_hdd, 1),
                        "disk_used_mb": round(total_hdd - free_hdd, 1),
                        "routeros_version": res.get("version", ""),
                        "architecture": res.get("architecture-name", ""),
                        "board_name": res.get("board-name", ""),
                        "uptime": res.get("uptime", "")
                    }
                else:
                    return {"status": "error", "message": f"HTTP {response.status_code}"}
            except Exception as e:
                logger.error(f"REST API connection error for {host}: {e}")
                return {"status": "offline", "message": str(e)}

    @staticmethod
    async def get_routerboard_rest(host: str, user: str, password: str, port: int = 443, use_ssl: bool = True) -> Dict[str, Any]:
        """Fetch /system/routerboard serial and model"""
        protocol = "https" if use_ssl else "http"
        url = f"{protocol}://{host}:{port}/rest/system/routerboard"
        
        async with httpx.AsyncClient(verify=False, timeout=8.0) as client:
            try:
                response = await client.get(url, auth=(user, password or ""))
                if response.status_code == 200:
                    data = response.json()
                    res = data[0] if isinstance(data, list) else data
                    return {
                        "serial_number": res.get("serial-number", ""),
                        "model_name": res.get("model", ""),
                        "current_firmware": res.get("current-firmware", ""),
                        "upgrade_firmware": res.get("upgrade-firmware", "")
                    }
            except Exception as e:
                logger.warning(f"Failed to fetch routerboard info for {host}: {e}")
        return {}

    @staticmethod
    def execute_ssh_command(host: str, user: str, password: str, command: str, port: int = 22, timeout: int = 15) -> Dict[str, Any]:
        """Execute a command on RouterOS via SSH"""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(host, port=port, username=user, password=password or "", timeout=timeout)
            stdin, stdout, stderr = ssh.exec_command(command)
            out = stdout.read().decode("utf-8", errors="ignore")
            err = stderr.read().decode("utf-8", errors="ignore")
            ssh.close()
            return {
                "success": True,
                "output": out,
                "error": err
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e)
            }

    @staticmethod
    async def run_script_rest(host: str, user: str, password: str, script: str, port: int = 443, use_ssl: bool = True) -> Dict[str, Any]:
        """Run custom script via REST API endpoint /rest/system/script/add & run or direct script execution"""
        protocol = "https" if use_ssl else "http"
        url = f"{protocol}://{host}:{port}/rest/execute"
        
        async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
            try:
                # RouterOS 7.12+ supports /rest/execute or script run
                response = await client.post(url, auth=(user, password or ""), json={"script": script})
                if response.status_code in (200, 201, 204):
                    return {"success": True, "output": response.text}
                else:
                    return {"success": False, "error": f"REST HTTP {response.status_code}: {response.text}"}
            except Exception as e:
                # Fallback to SSH if REST fails
                return MikroTikClient.execute_ssh_command(host, user, password, script)
