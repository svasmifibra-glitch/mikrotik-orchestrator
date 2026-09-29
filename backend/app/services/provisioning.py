from app.core.config import settings

def generate_onboarding_command(token: str, server_url: str = None) -> str:
    """Returns 1-line RouterOS terminal command to copy/paste"""
    base_url = (server_url or settings.SERVER_HOST).rstrip('/')
    script_url = f"{base_url}/api/v1/agent/script/{token}"
    mode = "https" if base_url.startswith("https") else "http"
    return f'/tool fetch url="{script_url}" mode={mode} keep-result=yes dst-path="orchestrator_install.rsc"; /import orchestrator_install.rsc; /file remove orchestrator_install.rsc;'

def generate_routeros_agent_script(token: str, server_url: str = None) -> str:
    """
    Generates the complete .rsc script that configures the MikroTik router
    to periodically report metrics, run queued scripts, and perform backups.
    """
    base_url = (server_url or settings.SERVER_HOST).rstrip('/')
    hb_url = f"{base_url}/api/v1/agent/heartbeat"
    poll_seconds = settings.AGENT_POLL_INTERVAL
    mode = "https" if base_url.startswith("https") else "http"
    
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
    
    # Collect System Metrics safely
    :local cpu 0
    :do {{ :set cpu [/system resource get cpu-load] }} on-error={{}}
    
    :local freeMem 0
    :local totalMem 0
    :do {{ 
        :set freeMem ([/system resource get free-memory] / 1048576)
        :set totalMem ([/system resource get total-memory] / 1048576)
    }} on-error={{}}
    
    :local usedMem ($totalMem - $freeMem)
    :if ($usedMem < 0) do={{ :set usedMem 0 }}

    :local freeHdd 0
    :local totalHdd 0
    :do {{
        :set freeHdd ([/system resource get free-hdd-space] / 1048576)
        :set totalHdd ([/system resource get total-hdd-space] / 1048576)
    }} on-error={{}}
    
    :local usedHdd ($totalHdd - $freeHdd)
    :if ($usedHdd < 0) do={{ :set usedHdd 0 }}

    :local rosVer ""
    :do {{ :set rosVer [/system resource get version] }} on-error={{}}
    :local board ""
    :do {{ :set board [/system resource get board-name] }} on-error={{}}
    :local arch ""
    :do {{ :set arch [/system resource get architecture-name] }} on-error={{}}
    :local uptime ""
    :do {{ :set uptime [/system resource get uptime] }} on-error={{}}
    
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
        /tool fetch url=($serverUrl . "?token=" . $token) mode={mode} http-method=post http-header-field="Content-Type: application/json" http-data=$jsonPayload keep-result=no
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
