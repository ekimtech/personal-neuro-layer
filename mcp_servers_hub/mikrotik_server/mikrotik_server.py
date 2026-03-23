# === Jarvis 4.0 MikroTik MCP Organ ===
# Connects to MikroTik router via SSH
# Tools: router status, connected devices, firewall rules, block/unblock IP

import json
import logging
import re

logger = logging.getLogger(__name__)

# Load config
try:
    from mcp_servers_hub.mikrotik_server.mikrotik_config import (
        MIKROTIK_HOST, MIKROTIK_PORT, MIKROTIK_USER, MIKROTIK_PASS
    )
except ImportError:
    MIKROTIK_HOST = "192.168.X.X"
    MIKROTIK_PORT = 22
    MIKROTIK_USER = ""
    MIKROTIK_PASS = ""
    logger.error("[MikroTik] Could not load mikrotik_config.py — check mikrotik_config.py!")

# Try importing paramiko
try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False
    logger.error("[MikroTik] paramiko not installed. Run: pip install paramiko")


# ---------------------------------------------------------
# Core SSH command runner
# ---------------------------------------------------------

def run_command(command: str) -> str:
    """Public wrapper — allows other modules (e.g. security scanner) to run MikroTik commands."""
    return _run_command(command)


def _run_command(command: str) -> str:
    if not PARAMIKO_AVAILABLE:
        return "ERROR: paramiko not installed. Run: pip install paramiko"

    if not MIKROTIK_USER or MIKROTIK_USER == "paste_your_username_here":
        return "ERROR: MikroTik credentials not configured. Please update mikrotik_config.py"

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=MIKROTIK_HOST,
            port=MIKROTIK_PORT,
            username=MIKROTIK_USER,
            password=MIKROTIK_PASS,
            timeout=15,
            look_for_keys=False,
            allow_agent=False
        )

        stdin, stdout, stderr = client.exec_command(command)
        output = stdout.read().decode("utf-8", errors="replace").strip()
        error = stderr.read().decode("utf-8", errors="replace").strip()
        client.close()

        if error and not output:
            return f"ERROR: {error}"

        return output

    except Exception as e:
        return f"ERROR: {str(e)}"


# ---------------------------------------------------------
# Tool: Router status
# ---------------------------------------------------------

def get_router_status() -> dict:
    try:
        identity = _run_command("/system identity print")
        resources = _run_command("/system resource print")
        routerboard = _run_command("/system routerboard print")

        if "ERROR" in resources:
            return {"error": resources}

        def extract(text, key):
            match = re.search(rf"{key}:\s*(.+)", text, re.IGNORECASE)
            return match.group(1).strip() if match else "N/A"

        name = extract(identity, "name")
        uptime = extract(resources, "uptime")
        cpu_load = extract(resources, "cpu-load")
        free_mem = extract(resources, "free-memory")
        total_mem = extract(resources, "total-memory")
        version = extract(resources, "version")
        board = extract(routerboard, "model")

        summary = (
            f"MikroTik {board} ({name}) running RouterOS {version}. "
            f"Uptime: {uptime}. "
            f"CPU load: {cpu_load}. "
            f"Memory: {free_mem} free of {total_mem}."
        )

        return {"status": "success", "data": summary}

    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------
# Tool: Connected devices
# ---------------------------------------------------------

def get_connected_devices() -> dict:
    try:
        arp = _run_command("/ip arp print")
        dhcp = _run_command("/ip dhcp-server lease print")

        if "ERROR" in arp:
            return {"error": arp}

        leases = {}
        for line in dhcp.splitlines():
            ip_match = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
            host_match = re.search(r"host-name=(\S+)", line)
            mac_match = re.search(r"([0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2})", line)
            if ip_match:
                ip = ip_match.group(1)
                leases[ip] = {
                    "hostname": host_match.group(1) if host_match else "unknown",
                    "mac": mac_match.group(1) if mac_match else "unknown"
                }

        devices = []
        for line in arp.splitlines():
            ip_match = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
            mac_match = re.search(r"([0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2})", line)
            if ip_match and mac_match:
                ip = ip_match.group(1)
                mac = mac_match.group(1)
                hostname = leases.get(ip, {}).get("hostname", "unknown")
                devices.append(f"{ip} ({hostname}) - {mac}")

        if not devices:
            return {"status": "success", "data": "No devices found in ARP table."}

        summary = f"Connected devices ({len(devices)} total):\n" + "\n".join(devices)
        return {"status": "success", "data": summary}

    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------
# Tool: View firewall rules
# ---------------------------------------------------------

def get_firewall_rules() -> dict:
    try:
        output = _run_command("/ip firewall filter print")

        if "ERROR" in output:
            return {"error": output}

        if not output.strip():
            return {"status": "success", "data": "No firewall filter rules found."}

        lines = [l for l in output.splitlines() if l.strip()]
        rule_count = sum(1 for l in lines if re.match(r"\s*\d+", l))

        summary = f"MikroTik firewall has {rule_count} filter rules:\n{output[:2000]}"
        if len(output) > 2000:
            summary += "\n... (truncated)"

        return {"status": "success", "data": summary}

    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------
# ---------------------------------------------------------
# Jarvis Blacklist — address-list name used for all bans
# ---------------------------------------------------------
BLACKLIST_NAME = "Jarvis-Blacklist"


def _ensure_blacklist_rules():
    """
    Create the one-time firewall filter rules that drop all traffic
    from the Jarvis-Blacklist address list (input + forward chains).
    Safe to call multiple times — checks before adding.
    """
    try:
        existing = _run_command(
            f"/ip firewall filter print where src-address-list={BLACKLIST_NAME}"
        )
        if BLACKLIST_NAME in existing:
            return  # Rules already exist
        # Add drop rule for input chain (traffic to the router itself)
        _run_command(
            f'/ip firewall filter add chain=input '
            f'src-address-list={BLACKLIST_NAME} action=drop '
            f'comment="Jarvis-Blacklist Drop (input)"'
        )
        # Add drop rule for forward chain (traffic through the router)
        _run_command(
            f'/ip firewall filter add chain=forward '
            f'src-address-list={BLACKLIST_NAME} action=drop '
            f'comment="Jarvis-Blacklist Drop (forward)"'
        )
        logger.info("[MikroTik] Jarvis-Blacklist firewall rules created.")
    except Exception as e:
        logger.error(f"[MikroTik] Failed to ensure blacklist rules: {e}")


# ---------------------------------------------------------
# Tool: Block IP
# ---------------------------------------------------------

def block_ip(ip: str, comment: str = "Blocked by Jarvis") -> dict:
    try:
        if not re.match(r"^\d+\.\d+\.\d+\.\d+$", ip):
            return {"error": f"Invalid IP address: {ip}"}

        # Make sure the drop rules exist for this address list
        _ensure_blacklist_rules()

        # Add IP to the Jarvis-Blacklist address list
        command = (
            f'/ip firewall address-list add list={BLACKLIST_NAME} '
            f'address={ip} comment="{comment}"'
        )
        output = _run_command(command)

        if "ERROR" in output:
            return {"error": output}

        return {"status": "success", "data": f"IP {ip} added to {BLACKLIST_NAME}."}

    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------
# Tool: Unblock IP
# ---------------------------------------------------------

def unblock_ip(ip: str) -> dict:
    try:
        if not re.match(r"^\d+\.\d+\.\d+\.\d+$", ip):
            return {"error": f"Invalid IP address: {ip}"}

        # Check if IP is in the address list
        check = _run_command(
            f"/ip firewall address-list print where list={BLACKLIST_NAME} address={ip}"
        )
        if not check.strip():
            return {"status": "success", "data": f"IP {ip} not found in {BLACKLIST_NAME}."}

        # Remove from address list
        _run_command(
            f"/ip firewall address-list remove "
            f"[find list={BLACKLIST_NAME} address={ip}]"
        )
        return {"status": "success", "data": f"IP {ip} removed from {BLACKLIST_NAME}."}

    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------
# MCP Router handle function
# ---------------------------------------------------------

def handle(user_input: str) -> dict:
    text = user_input.lower().strip()

    # Block IP
    if any(k in text for k in ["block", "ban", "blacklist"]):
        ip_match = re.search(r"(\d+\.\d+\.\d+\.\d+)", text)
        if ip_match:
            ip = ip_match.group(1)
            result = block_ip(ip)
            if "error" in result:
                return {"data": f"MikroTik error: {result['error']}"}
            return {"data": result["data"]}
        return {"data": "Please specify an IP address to block."}

    # Unblock IP
    if any(k in text for k in ["unblock", "unban", "whitelist"]):
        ip_match = re.search(r"(\d+\.\d+\.\d+\.\d+)", text)
        if ip_match:
            ip = ip_match.group(1)
            result = unblock_ip(ip)
            if "error" in result:
                return {"data": f"MikroTik error: {result['error']}"}
            return {"data": result["data"]}
        return {"data": "Please specify an IP address to unblock."}

    # Firewall rules
    if any(k in text for k in ["firewall", "rules", "filter"]):
        result = get_firewall_rules()
        if "error" in result:
            return {"data": f"MikroTik error: {result['error']}"}
        return {"data": result["data"]}

    # Connected devices
    if any(k in text for k in ["connected", "devices", "who is on", "network devices", "arp", "dhcp"]):
        result = get_connected_devices()
        if "error" in result:
            return {"data": f"MikroTik error: {result['error']}"}
        return {"data": result["data"]}

    # Router status - default
    result = get_router_status()
    if "error" in result:
        return {"data": f"MikroTik error: {result['error']}"}
    return {"data": result["data"]}