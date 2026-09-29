from app.core.config import settings

def generate_onboarding_command(token: str, server_url: str = None) -> str:
    """Returns 1-line RouterOS terminal command to copy/paste"""
    base_url = (server_url or settings.SERVER_HOST).rstrip('/')
    script_url = f"{base_url}/api/v1/agent/script/{token}"
    return f'/tool fetch url="{script_url}" mode=https keep-result=yes dst-path="orchestrator_install.rsc"; /import orchestrator_install.rsc; /file remove orchestrator_install.rsc;'

def generate_routeros_agent_script(token: str, server_url: str = None) -> str:
    """
    Generates the complete .rsc script that configures the MikroTik router
    to periodically report metrics, run queued scripts, and perform backups.
    """
    base_url = (server_url or settings.SERVER_HOST).rstrip('/')
    hb_url = f"{base_url}/api/v1/agent/heartbeat"
    poll_seconds = settings.AGENT_POLL_INTERVAL
    
    script = f"""# =========================================================
# MikroTik Cloud Orchestrator - Auto Provisioning Script
# Token: {token}
# Server: {base_url}
# =========================================================

:log info "Setting up MikroTik Cloud Orchestrator Agent..."

# Remove old script and scheduler if exists
/system scheduler remove [find name="orchestrator_poll"]
/system script remove [find name="orchestrator_agent"]

# Create Main Agent Script
/system script add name="orchestrator_agent" owner="admin" policy=read,write,policy,test,password,sniff,sensitive source={{
    :local token "{token}"
    :local serverUrl "{hb_url}"
    
    # Collect System Metrics
    :local cpu [/system resource get cpu-load]
    :local freeMem ([/system resource get free-memory] / 1048576)
    :local totalMem ([/system resource get total-memory] / 1048576)
    :local freeHdd ([/system resource get free-hdd-space] / 1048576)
    :local totalHdd ([/system resource get total-hdd-space] / 1048576)
    :local usedMem ($totalMem - $freeMem)
    :local usedHdd ($totalHdd - $freeHdd)
    :local rosVer [/system resource get version]
    :local board [/system resource get board-name]
    :local arch [/system resource get architecture-name]
    :local uptime [/system resource get uptime]
    
    :local serial ""
    :local model ""
    :do {{
        :set serial [/system routerboard get serial-number]
        :set model [/system routerboard get model]
    }} on-error={{}}

    # Build JSON Payload
    :local jsonPayload "{{\\"token\\":\\"$token\\",\\"cpu_load\\":$cpu,\\"memory_used_mb\\":$usedMem,\\"memory_total_mb\\":$totalMem,\\"disk_used_mb\\":$usedHdd,\\"disk_total_mb\\":$totalHdd,\\"routeros_version\\":\\"$rosVer\\",\\"board_name\\":\\"$board\\",\\"architecture\\":\\"$arch\\",\\"uptime\\":\\"$uptime\\",\\"serial_number\\":\\"$serial\\",\\"model_name\\":\\"$model\\"}}"
    
    :log info ("Orchestrator Agent: Sending heartbeat for serial " . $serial)
    
    # Send Heartbeat via HTTP/HTTPS POST
    :do {{
        /tool fetch url=($serverUrl . "?token=" . $token) http-method=post http-header-field="Content-Type: application/json" http-data=$jsonPayload keep-result=yes dst-path="orchestrator_response.txt"
        
        # Check if response contains queued command to execute
        :if ([/file find name="orchestrator_response.txt"] != "") do={{
            :local resp [/file get orchestrator_response.txt contents]
            /file remove orchestrator_response.txt
            
            # Execute queued command if returned
            :if ($resp != "" && $resp != "{{}}" && [:find $resp "cmd:"] = 0) do={{
                :local cmd [:pick $resp 4 [:len $resp]]
                :log warning ("Orchestrator Agent: Executing remote task script...")
                :execute script=$cmd
            }}
        }}
    }} on-error={{
        :log error "Orchestrator Agent: Failed to connect to orchestrator server."
    }}
}}

# Create Scheduler (runs every {poll_seconds} seconds)
/system scheduler add name="orchestrator_poll" interval={poll_seconds}s on-event="/system script run orchestrator_agent" comment="MikroTik Cloud Orchestrator Poller"

# Run once immediately
/system script run orchestrator_agent

:log info "MikroTik Cloud Orchestrator Agent successfully installed!"
"""
    return script
