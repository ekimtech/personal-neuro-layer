# === Jarvis 4.0 QNAP MCP Organ ===
# Full QNAP tool list discovered and mapped correctly

import json
import os
import re
import shutil
import threading
import time
import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from mcp_servers_hub.qnap_server.qnap_config import (
        QNAP_TOKEN, QNAP_URL,
        JARVIS_SOURCE, JARVIS_BACKUP_PATH, NAS_DRIVE
    )
except ImportError:
    QNAP_TOKEN = ""
    QNAP_URL = "http://192.168.X.X:8442/sse"
    JARVIS_SOURCE = r"C:\path\to\your\Jarvis4.0"
    JARVIS_BACKUP_PATH = r"X:\backups"
    NAS_DRIVE = r"X:\\"
    logger.error("[QNAP] Could not load qnap_config.py — check qnap_config.py!")


# ---------------------------------------------------------
# Core QNAP MCP call — keeps SSE open while sending POST
# ---------------------------------------------------------

def _call_qnap(method: str, params: dict = None) -> dict:
    if not QNAP_TOKEN or QNAP_TOKEN == "paste_your_token_here":
        return {"error": "QNAP token not configured. Please update qnap_config.py"}

    sse_url = QNAP_URL if QNAP_URL.endswith("/sse") else QNAP_URL + "/sse"
    base_url = QNAP_URL.replace("/sse", "")

    sse_headers = {
        "Authorization": f"Bearer {QNAP_TOKEN}",
        "Accept": "text/event-stream"
    }

    post_headers = {
        "Authorization": f"Bearer {QNAP_TOKEN}",
        "Content-Type": "application/json"
    }

    result_container = {"result": None, "error": None}
    session_id_holder = {"id": None}
    session_ready = threading.Event()
    response_received = threading.Event()

    def listen_sse():
        try:
            response = requests.get(
                sse_url,
                headers=sse_headers,
                stream=True,
                timeout=60
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    decoded = line.decode("utf-8")
                    print(f"[QNAP] SSE: {decoded}")

                    if decoded.startswith("data:"):
                        data_str = decoded[5:].strip()

                        # Extract session ID
                        if not session_id_holder["id"]:
                            match = re.search(r"sessionId=([a-zA-Z0-9_\-]+)", data_str)
                            if match:
                                session_id_holder["id"] = match.group(1)
                                session_ready.set()
                                continue

                        # Parse result messages
                        try:
                            data = json.loads(data_str)
                            if "result" in data:
                                result_container["result"] = data["result"]
                                response_received.set()
                            elif "error" in data:
                                result_container["error"] = data["error"].get("message", str(data["error"]))
                                response_received.set()
                        except Exception:
                            pass

                # Stop once we have the response
                if response_received.is_set():
                    break

        except Exception as e:
            result_container["error"] = str(e)
            session_ready.set()
            response_received.set()

    # Start SSE listener
    sse_thread = threading.Thread(target=listen_sse, daemon=True)
    sse_thread.start()

    # Wait for session ID
    if not session_ready.wait(timeout=20):
        return {"error": "Timed out waiting for QNAP session"}

    if not session_id_holder["id"]:
        return {"error": result_container.get("error", "Could not get QNAP session ID")}

    # Send command while SSE is still open
    messages_url = f"{base_url}/message?sessionId={session_id_holder['id']}"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params if params is not None else {}
    }

    try:
        print(f"[QNAP] Sending: {method}")
        post_resp = requests.post(
            messages_url,
            headers=post_headers,
            json=payload,
            timeout=30
        )
        print(f"[QNAP] POST status: {post_resp.status_code}")

    except Exception as e:
        return {"error": f"POST failed: {str(e)}"}

    # Wait for SSE response
    if not response_received.wait(timeout=30):
        return {"error": "Timed out waiting for QNAP response"}

    if result_container["error"]:
        return {"error": result_container["error"]}

    return result_container["result"] or {}


# ---------------------------------------------------------
# Tool functions — correct QNAP tool names
# ---------------------------------------------------------

def get_system_info() -> dict:
    """Get CPU, memory, storage, network and hardware status."""
    result = _call_qnap("tools/call", {"name": "get_system_info", "arguments": {}})
    if "error" in result:
        return result

    try:
        # Parse the nested JSON text from QNAP response
        raw_text = result.get("content", [{}])[0].get("text", "{}")
        data = json.loads(raw_text)

        # Build a clean human readable summary
        cpu = data.get("cpu", {})
        mem = data.get("memory", {})
        storage = data.get("storage", {})
        system = data.get("system", {})
        network = data.get("network", {})
        firmware = data.get("firmware", {})
        model = data.get("model", {})

        mem_total = mem.get("total_mb", 0)
        mem_used = mem.get("used_mb", 0)
        mem_pct = round((mem_used / mem_total) * 100) if mem_total else 0

        disks = storage.get("disks", [])
        disk_temps = [f"Disk {d['id']}: {d['temperature_celsius']}C" for d in disks if d.get("installed")]

        fans = system.get("fans", [])
        fan_info = ", ".join([f"Fan {f['fan_id']}: {f['speed_rpm']} RPM" for f in fans])

        eth0 = next((i for i in network.get("interfaces", []) if i["name"] == "eth0"), {})

        summary = (
            f"EKIMTECHNAS ({model.get('display_model_name', 'QNAP')}) running QTS {firmware.get('version', 'unknown')}. "
            f"CPU: {cpu.get('usage', 'N/A')} at {cpu.get('temperature', {}).get('celsius', 'N/A')}C. "
            f"Memory: {mem_used}MB used of {mem_total}MB ({mem_pct}%). "
            f"Storage: {storage.get('total_disks', 0)} disks — {', '.join(disk_temps)}. "
            f"System temp: {system.get('system_temp', {}).get('celsius', 'N/A')}C. "
            f"Fan: {fan_info}. "
            f"Network eth0: {eth0.get('ip_address', 'N/A')} — {'online' if eth0.get('status') else 'offline'}."
        )

        return {"status": "success", "data": summary}

    except Exception as e:
        return {"status": "success", "data": f"QNAP system info received but could not parse: {str(e)}"}


def list_shared_folders(detailed: bool = False, limit: int = 20) -> dict:
    """List all shared folders on the NAS."""
    result = _call_qnap("tools/call", {
        "name": "list_shared_folder",
        "arguments": {"detailed": detailed, "limit": limit, "offset": 0}
    })
    if "error" in result:
        return result
    return {"status": "success", "data": result}

def list_files(path: str = "/", limit: int = 50) -> dict:
    """List files and folders at a given path."""
    result = _call_qnap("tools/call", {
        "name": "list_files",
        "arguments": {"path": path, "limit": limit, "offset": 0}
    })
    if "error" in result:
        return result
    return {"status": "success", "data": result}


def search_files(path: str, name: str) -> dict:
    """Search for files by name in a given path."""
    result = _call_qnap("tools/call", {
        "name": "search_files",
        "arguments": {"path": path, "name": name}
    })
    if "error" in result:
        return result
    return {"status": "success", "data": result}


def advanced_search(query: str, categories: list = None, limit: int = 20) -> dict:
    """Advanced search using Qsirch across the entire NAS."""
    args = {"any_words": [query], "limit": limit}
    if categories:
        args["categories"] = categories
    result = _call_qnap("tools/call", {
        "name": "advanced_search",
        "arguments": args
    })
    if "error" in result:
        return result
    return {"status": "success", "data": result}


def create_folder(path: str) -> dict:
    """Create a new folder directly on the mapped NAS drive."""
    try:
        os.makedirs(path, exist_ok=True)
        return {"status": "success", "data": f"Folder created at {path}"}
    except Exception as e:
        return {"error": str(e)}


def backup_jarvis() -> dict:
    """Back up the Jarvis project folder to the NAS backup path, skipping venv."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    dest = os.path.join(JARVIS_BACKUP_PATH, f"Jarvis4.0_{timestamp}")

    def ignore_venv(dir, contents):
        return [c for c in contents if c == "venv"]

    try:
        os.makedirs(JARVIS_BACKUP_PATH, exist_ok=True)
        shutil.copytree(JARVIS_SOURCE, dest, ignore=ignore_venv)
        return {"status": "success", "data": f"Backup complete — saved to {dest}"}
    except Exception as e:
        return {"error": str(e)}


def list_logs(limit: int = 20, query_text: str = "") -> dict:
    """List NAS system logs."""
    args = {"limit": limit, "offset": 0, "severities": ["info", "warning", "error"]}
    if query_text:
        args["query_text"] = query_text
    result = _call_qnap("tools/call", {
        "name": "list_logs",
        "arguments": args
    })
    if "error" in result:
        return result
    return {"status": "success", "data": result}


def list_storages() -> dict:
    """List all storage pools, RAID and disk info."""
    result = _call_qnap("tools/call", {"name": "list_storages", "arguments": {}})
    if "error" in result:
        return result
    return {"status": "success", "data": result}


def list_qpkgs() -> dict:
    """List installed apps on the NAS."""
    result = _call_qnap("tools/call", {"name": "list_qpkgs", "arguments": {}})
    if "error" in result:
        return result
    return {"status": "success", "data": result}


def query_load_avg(duration_minutes: int = 60) -> dict:
    """Get load average data for the NAS."""
    result = _call_qnap("tools/call", {
        "name": "query_load_avg",
        "arguments": {"duration_minutes": duration_minutes, "interval": 15}
    })
    if "error" in result:
        return result
    return {"status": "success", "data": result}


def list_tools_available() -> dict:
    """List all available QNAP MCP tools."""
    result = _call_qnap("tools/list")
    return result


# ---------------------------------------------------------
# MCP Router handle function
# ---------------------------------------------------------

def handle(user_input: str) -> dict:
    text = user_input.lower().strip()

    # System info / status
    if any(k in text for k in ["status", "cpu", "memory", "ram", "system info", "hardware"]):
        result = get_system_info()
        if "error" in result:
            return {"data": f"QNAP error: {result['error']}"}
        return {"data": f"QNAP system info: {json.dumps(result['data'], indent=2)}"}

    # Storage / disks
    if any(k in text for k in ["storage", "disk", "raid", "pool", "drive"]):
        result = list_storages()
        if "error" in result:
            return {"data": f"QNAP error: {result['error']}"}
        return {"data": f"QNAP storage: {json.dumps(result['data'], indent=2)}"}

    # Logs
    if any(k in text for k in ["log", "logs", "errors", "warnings"]):
        result = list_logs(limit=20)
        if "error" in result:
            return {"data": f"QNAP error: {result['error']}"}
        return {"data": f"QNAP logs: {json.dumps(result['data'], indent=2)}"}

    # Apps
    if any(k in text for k in ["app", "apps", "installed", "package", "qpkg"]):
        result = list_qpkgs()
        if "error" in result:
            return {"data": f"QNAP error: {result['error']}"}
        return {"data": f"QNAP installed apps: {json.dumps(result['data'], indent=2)}"}

    # Advanced search
    if any(k in text for k in ["search", "find", "look for", "locate"]):
        for keyword in ["search for", "find", "search", "look for", "locate"]:
            if keyword in text:
                query = text.split(keyword, 1)[-1].strip()
                if query:
                    result = advanced_search(query)
                    if "error" in result:
                        return {"data": f"QNAP search error: {result['error']}"}
                    return {"data": f"QNAP search results for '{query}': {json.dumps(result['data'], indent=2)}"}

    # Backup Jarvis
    if any(k in text for k in ["backup jarvis", "back up jarvis", "backup the project", "backup jarvis4"]):
        result = backup_jarvis()
        if "error" in result:
            return {"data": f"Backup failed: {result['error']}"}
        return {"data": result["data"]}

    # Create folder
    if any(k in text for k in ["create folder", "create a folder", "make folder", "new folder", "mkdir", "folder named"]):
        # Extract folder name — use original input to preserve underscores and casing
        folder_name = user_input
        for kw in ["create a folder named", "create folder named", "create a folder", "create folder",
                   "make folder named", "make folder", "new folder named", "new folder",
                   "folder named", "mkdir"]:
            if kw.lower() in folder_name.lower():
                idx = folder_name.lower().index(kw.lower())
                folder_name = folder_name[idx + len(kw):].strip()
                break
        # Strip common location phrases
        for phrase in ["in the jarvis shared drive", "in the jarvis share", "on the jarvis drive",
                       "on the nas", "on qnap", "in jarvis", "on jarvis", "in the nas"]:
            folder_name = folder_name.replace(phrase, "").replace(phrase.title(), "").strip()
        # Keep only valid folder name characters (letters, digits, underscores, hyphens)
        folder_name = re.sub(r"[^\w\-]", "", folder_name).strip("_")
        if folder_name:
            full_path = os.path.join(NAS_DRIVE, folder_name)
            result = create_folder(full_path)
            if "error" in result:
                return {"data": f"Could not create folder: {result['error']}"}
            return {"data": f"Folder '{folder_name}' created on the NAS drive at {full_path}"}
        return {"data": "Please specify a folder name to create."}

    # List files
    if any(k in text for k in ["list files", "list folder", "show files", "browse", "contents"]):
        path = "/"
        for keyword in ["list files", "list folder", "show files", "browse", "contents of"]:
            if keyword in text:
                after = text.split(keyword, 1)[-1].strip()
                if after:
                    path = after if after.startswith("/") else f"/{after}"
                break
        result = list_files(path)
        if "error" in result:
            return {"data": f"QNAP list error: {result['error']}"}
        return {"data": f"Contents of {path}: {json.dumps(result['data'], indent=2)}"}

    # Default — list shared folders
    result = list_shared_folders()
    if "error" in result:
        return {"data": f"QNAP error: {result['error']}"}

    # Parse and format shared folders cleanly
    try:
        raw = result.get("data", {})
        # The data may be nested inside content/text as a JSON string
        if isinstance(raw, dict) and "content" in raw:
            import json as _json
            text_content = raw["content"][0].get("text", "{}")
            parsed = _json.loads(text_content)
        elif isinstance(raw, str):
            import json as _json
            parsed = _json.loads(raw)
        else:
            parsed = raw

        folders = parsed.get("sharedfolders", [])
        if not folders:
            return {"data": "No shared folders found on the QNAP."}

        visible = [f for f in folders if not f.get("hidden", False)]
        hidden = [f for f in folders if f.get("hidden", False)]

        lines = ["Here are your QNAP shared folders:\n"]
        for f in visible:
            dirs = f.get("dir_count", 0)
            files = f.get("file_count", 0)
            comment = f.get("comment", "")
            note = f" — {comment}" if comment and comment != "System default share" else ""
            dir_word = "folder" if dirs == 1 else "folders"
            file_word = "file" if files == 1 else "files"
            lines.append(f"  • {f['name']}: {dirs:,} {dir_word}, {files:,} {file_word}{note}")

        if hidden:
            lines.append(f"\nHidden volumes: {', '.join(f['name'] for f in hidden)}")

        return {"data": "\n".join(lines)}

    except Exception:
        return {"data": f"QNAP shared folders: {json.dumps(result['data'], indent=2)}"}