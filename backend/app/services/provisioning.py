from app.core.config import settings

def generate_onboarding_command(token: str, server_url: str = None) -> str:
    """Returns 1-line RouterOS terminal command to copy/paste"""
    base_url = (server_url or settings.SERVER_HOST).rstrip('/')
    script_url = f"{base_url}/api/v1/agent/script/{token}"
    mode = "https" if base_url.startswith("https") else "http"
    return f'/tool fetch url="{script_url}" mode={mode} keep-result=yes dst-path="orchestrator_install.rsc"; /import orchestrator_install.rsc; /file remove orchestrator_install.rsc;'

def generate_instant_backup_command(token: str, server_url: str = None) -> str:
    """Returns 1-line RouterOS terminal command to immediately generate & upload backup"""
    base_url = (server_url or settings.SERVER_HOST).rstrip('/')
    upload_url = f"{base_url}/api/v1/agent/upload-backup?token={token}"
    mode = "https" if base_url.startswith("https") else "http"
    return f'/export file="orch_export" hide-sensitive; :delay 2s; /tool fetch url="{upload_url}" mode={mode} http-method=post upload=yes src-path="orch_export.rsc"; :delay 1s; /file remove [find name="orch_export.rsc"];'

def generate_routeros_agent_script(token: str, server_url: str = None) -> str:
    """
    Generates the complete .rsc script that configures the MikroTik router
    to periodically report metrics, poll for tasks/commands, and execute backups.
    """
    base_url = (server_url or settings.SERVER_HOST).rstrip('/')
    poll_url = f"{base_url}/api/v1/agent/poll"
    poll_seconds = 60 # Polling every 60 seconds for fast response to cloud commands
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
    :local pollUrl "{poll_url}"
    
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

    # Clean RouterOS version string (remove spaces like ' (stable)')
    :local rosVer ""
    :do {{ :set rosVer [/system resource get version] }} on-error={{}}
    :local cleanRos $rosVer
    :local spacePos [:find $rosVer " "]
    :if ($spacePos > 0) do={{ :set cleanRos [:pick $rosVer 0 $spacePos] }}

    :local serial ""
    :do {{ :set serial [/system routerboard get serial-number] }} on-error={{}}
    :if ($serial = "") do={{ :set serial "CHR" }}

    :local model ""
    :do {{ :set model [/system routerboard get model] }} on-error={{}}
    :if ($model = "") do={{ :set model "RouterOS" }}

    # Poll server: sends metrics AND downloads any queued command (.rsc)
    :do {{
        /tool fetch url=($pollUrl . "?token=" . $token . "&cpu=" . $cpu . "&mem_used=" . $usedMem . "&mem_total=" . $totalMem . "&ros=" . $cleanRos . "&serial=" . $serial . "&model=" . $model) mode={mode} keep-result=yes dst-path="orch_task.rsc"
        
        :if ([/file find name="orch_task.rsc"] != "") do={{
            :local sz [/file get orch_task.rsc size]
            # If server sent actual script commands (more than # idle comment)
            :if ($sz > 15) do={{
                :log info "Orchestrator: Executing cloud task from platform..."
                /import orch_task.rsc
            }}
            /file remove [find name="orch_task.rsc"]
        }}
    }} on-error={{
        :log error "Orchestrator Agent: Polling connection failed."
    }}
}}

# Create Scheduler (runs every {poll_seconds} seconds)
/system scheduler add name="orchestrator_poll" interval={poll_seconds}s on-event="/system script run orchestrator_agent" comment="MikroTik Cloud Orchestrator Poller"

# Run once immediately
/system script run orchestrator_agent

:log info "MikroTik Cloud Orchestrator Agent successfully installed!"
"""
    return script
