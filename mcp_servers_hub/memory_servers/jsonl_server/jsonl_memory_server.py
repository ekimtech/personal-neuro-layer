import os
import json
import datetime
import tempfile
import threading

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
LOG_DIR = os.path.join(BASE_DIR, "logs")

MEMORY_FILE = os.path.join(STORAGE_DIR, "memory_core.jsonl")
LOG_FILE = os.path.join(LOG_DIR, "jsonl_memory_server.log")

os.makedirs(STORAGE_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# ── RAM Cache ──────────────────────────────────────────────
# Loaded once from disk; all reads served from here.
# Writes update both the cache and disk atomically.
_cache: list = []
_cache_loaded: bool = False
_cache_lock = threading.Lock()
# ──────────────────────────────────────────────────────────


def log(message: str):
    timestamp = datetime.datetime.utcnow().isoformat()
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def _ensure_memory_file():
    if not os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            pass
        log(f"Created new memory file at {MEMORY_FILE}")


def _load_from_disk() -> list:
    """Read all entries from disk. Internal use only."""
    _ensure_memory_file()
    entries = []
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception as e:
                log(f"ERROR parsing JSONL line: {e} | line={line!r}")
    return entries


def warm_cache():
    """
    Load all JSONL entries into RAM.
    Call this once at app startup for zero-latency memory reads.
    """
    global _cache, _cache_loaded
    with _cache_lock:
        _cache = _load_from_disk()
        _cache_loaded = True
    log(f"RAM cache warmed: {len(_cache)} entries loaded.")


def _get_cache() -> list:
    """Return cached entries, warming from disk on first access."""
    global _cache_loaded
    if not _cache_loaded:
        warm_cache()
    return _cache


def reload_cache():
    """Force reload from disk (use if file was edited outside Jarvis)."""
    global _cache, _cache_loaded
    with _cache_lock:
        _cache = _load_from_disk()
        _cache_loaded = True
    log(f"RAM cache reloaded: {len(_cache)} entries.")


def _atomic_write(entries: list):
    """Write entries to disk atomically and sync the RAM cache."""
    global _cache
    fd, temp_path = tempfile.mkstemp()
    with os.fdopen(fd, "w", encoding="utf-8") as tmp:
        for entry in entries:
            tmp.write(json.dumps(entry, ensure_ascii=False) + "\n")
    os.replace(temp_path, MEMORY_FILE)
    # Keep RAM cache in sync
    with _cache_lock:
        _cache = entries
    log(f"Atomic write + cache sync: {len(entries)} entries.")


def _next_id(entries: list) -> str:
    if not entries:
        return "M0001"
    last = entries[-1].get("id", "M0000")
    try:
        num = int(last[1:])
    except Exception:
        num = 0
    return f"M{num + 1:04d}"


# ── Public API (all reads from RAM) ───────────────────────

def add_memory(content: str):
    with _cache_lock:
        entries = list(_get_cache())   # shallow copy to avoid mutation
    new_entry = {
        "id": _next_id(entries),
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "source": "user",
        "content": content,
        "tags": [],
        "intent": None,
        "related_to": None,
        "response": None,
        "priority": 1,
        "mood": None,
        "topic": None,
        "perspective": None,
        "refer_as": None,
        "source_file": "ui",
    }
    entries.append(new_entry)
    _atomic_write(entries)
    log(f"ADD success: {new_entry['id']}")
    return new_entry


def search_memory(keyword: str):
    entries = _get_cache()
    keyword_lower = keyword.lower()
    results = [
        e for e in entries
        if keyword_lower in json.dumps(e, ensure_ascii=False).lower()
    ]
    log(f"SEARCH '{keyword}' → {len(results)} results (from RAM).")
    return results


def delete_memory(entry_id: str):
    with _cache_lock:
        entries = list(_get_cache())
    new_entries = [e for e in entries if e.get("id") != entry_id]
    if len(new_entries) == len(entries):
        log(f"DELETE failed: ID {entry_id} not found")
        return None
    _atomic_write(new_entries)
    log(f"DELETE success: removed {entry_id}")
    return entry_id


def list_memory():
    entries = _get_cache()
    log(f"LIST → {len(entries)} entries (from RAM).")
    return entries


def handle(user_input: str):
    """
    log(f"DEBUG HANDLE RECEIVED: {user_input!r}")

    Natural-language interface.

    Supported patterns:
      - "remember <text>"
      - "search memory for <keyword>"
      - "delete memory <id>"
      - "list memory"
    """
    text = user_input.strip()
    lower = text.lower().strip()

    # remember ...
    if lower.startswith("remember "):
        content = text[len("remember "):].strip()
        if not content:
            log("ADD failed: empty content")
            return {"data": "Nothing to remember."}
        entry = add_memory(content)
        return {"data": f"Remembered as {entry['id']}: {entry['content']}"}

    # search memory for ...
    if lower.startswith("search memory for"):
        keyword = text[len("search memory for "):].strip()
        if not keyword:
            log("SEARCH failed: empty keyword")
            return {"data": "Nothing to search for."}
        results = search_memory(keyword)
        return {
            "data": {
                "count": len(results),
                "results": results,
            }
        }

    # delete memory <id>
    if lower.startswith("delete memory "):
        entry_id = text[len("delete memory "):].strip()
        if not entry_id:
            log("DELETE failed: empty ID")
            return {"data": "No memory ID provided."}
        deleted = delete_memory(entry_id)
        if deleted is None:
            return {"data": f"No memory found with ID {entry_id}."}
        return {"data": f"Deleted memory {entry_id}."}

    # list memory
    if lower == "list memory":
        entries = list_memory()
        return {
            "data": {
                "count": len(entries),
                "results": entries,
            }
        }

    log(f"UNHANDLED memory input: {user_input!r}")
    return {"data": "Memory command not recognized."}
