# === Jarvis 4.0 jarvis_routes.py (with full session system rebuilt) ===
# Updated: 03/16/26

import uuid
import os
import time
import sqlite3
import json
from flask import Blueprint, request, jsonify, render_template
from werkzeug.utils import secure_filename
from mcp_servers_hub.vector_metadata_server.server import insert_chunk
from mcp_servers_hub.vector_metadata_server.vector_store import index_chunk
from collections import deque
_wake_queue = deque(maxlen=10)
from collections import deque
_wake_queue = deque(maxlen=10)
_stt_status = {"status": "listening", "enabled": True}

# === Wake Word Message Queue ===
from collections import deque
_wake_queue = deque(maxlen=10)

def push_wake_message(message: str):
    _wake_queue.append({"message": message, "timestamp": int(time.time())})

def push_wake_message(message: str):
    """Called by wake word listener to push response to WebUI."""
    _wake_queue.append({"message": message, "timestamp": int(time.time())})
 
def set_stt_status(status: str):
    """Called by wake word listener to update status."""
    _stt_status["status"] = status

# MCP router
from mcp_servers_hub.mcp_router_hub import handle_request
from mcp_servers_hub.memory_servers.jsonl_server.jsonl_memory_server import reload_cache as _reload_memory_cache

# Vector Metadata Server (new organ)
from mcp_servers_hub.vector_metadata_server.server import (
    list_chunks,
    delete_chunk,
    clear_all
)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ============================================================
# BLUEPRINTS
# ============================================================

jarvis_bp = Blueprint("jarvis_bp", __name__)
upload_bp = Blueprint("upload_bp", __name__)

# ============================================================
# SESSION DATABASE LOCATION
# ============================================================

SESSION_DB_PATH = os.path.join(
    "mcp_servers_hub",
    "memory_servers",
    "sqlite_server",
    "session.db"
)

# Ensure folder exists
os.makedirs(os.path.dirname(SESSION_DB_PATH), exist_ok=True)

# ============================================================
# SESSION DB INITIALIZER
# ============================================================

def init_session_db():
    conn = sqlite3.connect(SESSION_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            timestamp INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            speaker TEXT,
            message TEXT,
            timestamp INTEGER,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        )
    """)

    conn.commit()
    conn.close()

# Initialize DB on import
init_session_db()

# ============================================================
# SESSION HELPERS
# ============================================================

def create_new_session():
    conn = sqlite3.connect(SESSION_DB_PATH)
    cursor = conn.cursor()
    ts = int(time.time())
    cursor.execute("INSERT INTO sessions (title, timestamp) VALUES (?, ?)", ("", ts))
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id

def list_sessions():
    conn = sqlite3.connect(SESSION_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, timestamp FROM sessions ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "title": r[1], "timestamp": r[2]} for r in rows]

def get_turns(session_id):
    conn = sqlite3.connect(SESSION_DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT speaker, message, timestamp FROM turns WHERE session_id = ? ORDER BY timestamp ASC",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"speaker": r[0], "message": r[1], "timestamp": r[2]} for r in rows]

def add_turn(session_id, speaker, message):
    conn = sqlite3.connect(SESSION_DB_PATH)
    cursor = conn.cursor()
    ts = int(time.time())
    cursor.execute(
        "INSERT INTO turns (session_id, speaker, message, timestamp) VALUES (?, ?, ?, ?)",
        (session_id, speaker, message, ts)
    )
    conn.commit()
    conn.close()

def delete_session(session_id):
    conn = sqlite3.connect(SESSION_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM turns WHERE session_id = ?", (session_id,))
    cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()

# ============================================================
# JSONL MEMORY MANAGER CONFIG
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_DIR = os.path.join(
    BASE_DIR,
    "mcp_servers_hub",
    "memory_servers",
    "jsonl_server",
    "storage" 
)

MEMORY_FILES = {
    # display_name: full_path
    "memory_core.jsonl": os.path.join(MEMORY_DIR, "memory_core.jsonl"),
    # add more here if you want later
    # "cortex_memory.jsonl": os.path.join(MEMORY_DIR, "cortex_memory.jsonl"),
}


def load_jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def save_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

# ============================================================
# UI HOME
# ============================================================

@jarvis_bp.route("/", methods=["GET"])
def index():
    sessions = list_sessions()
    # Don't auto-select a session — user must explicitly click one or start new
    return render_template("index.html", selected_session_id=None)

@jarvis_bp.route("/face", methods=["GET"])
def face():
    return render_template("face.html")

@jarvis_bp.route("/lists_pdf", methods=["GET"])
def lists_pdf():
    return render_template("lists_pdf.html")

# @jarvis_bp.route("/api/wake_poll", methods=["GET"])
# def wake_poll():
#    if _wake_queue:
#        msg = _wake_queue.popleft()
#        return jsonify(msg)
#    return "", 204

@jarvis_bp.route("/api/wake_poll", methods=["GET"])
def wake_poll():
    """WebUI polls this every 2 seconds to check for wake word responses."""
    if _wake_queue:
        msg = _wake_queue.popleft()
        return jsonify(msg)
    return "", 204
 
 
@jarvis_bp.route("/api/stt/status", methods=["GET"])
def stt_status():
    """Returns current STT status for the WebUI indicator."""
    return jsonify(_stt_status)
 
 
@jarvis_bp.route("/api/stt/toggle", methods=["POST"])
def stt_toggle():
    """Toggles the wake word listener on or off."""
    from mcp_servers_hub.stt_server.wake_word_listener import start, stop, _running
    if _stt_status["enabled"]:
        stop()
        _stt_status["enabled"] = False
        _stt_status["status"] = "disabled"
    else:
        start()
        _stt_status["enabled"] = True
        _stt_status["status"] = "listening"
    return jsonify({"enabled": _stt_status["enabled"]})

# ============================================================
# UPLOAD PAGE
# ============================================================

@upload_bp.route("/upload", methods=["GET"])
def upload_page():
    return render_template("upload.html")

# ============================================================
# VECTOR DB MANAGER PAGE (NEW)
# ============================================================

@upload_bp.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    # Extract text depending on file type
    ext = filename.split(".")[-1].lower()

    if ext in ("txt", "md"):
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

    elif ext == "jsonl":
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            text = "\n".join([line.strip() for line in f.readlines()])

    else:
        return jsonify({"error": f"Unsupported file type: .{ext}"}), 400

    # --- Smart chunking ---
    # Markdown files: chunk by ## section headings (one chunk per section)
    # All other files: fall back to 1000-char chunks
    if ext == "md":
        import re as _re
        raw_sections = _re.split(r'(?=^## )', text, flags=_re.MULTILINE)
        # Filter empty sections, strip whitespace
        chunks = [s.strip() for s in raw_sections if s.strip()]
        # Safety: if a section is huge, sub-chunk it at 2000 chars
        final_chunks = []
        for section in chunks:
            if len(section) <= 2000:
                final_chunks.append(section)
            else:
                for i in range(0, len(section), 2000):
                    final_chunks.append(section[i:i+2000])
        chunks = final_chunks
    else:
        chunk_size = 1000
        chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

    # Insert chunks into vector metadata DB
    for index, chunk in enumerate(chunks):
        chunk_id = str(uuid.uuid4())
        preview = chunk[:200].replace("\n", " ")

        insert_chunk(
            id=chunk_id,
            filename=filename,
            file_type=ext,
            chunk_index=index,
            content_preview=preview,
            full_content=chunk
        )

        # Create embedding for this chunk
        index_chunk(chunk_id, chunk)

    return jsonify({
        "message": f"Uploaded {filename} with {len(chunks)} chunks",
        "chunks": len(chunks)
    })

# ============================================================
# JSONL MEMORY MANAGER PAGE
# ============================================================

@jarvis_bp.route("/jan/memory_manager", methods=["GET"])
def memory_manager():
    file_param = request.args.get("file")
    search = request.args.get("search", "").strip()
    page = int(request.args.get("page", 1))
    per_page = 25

    # resolve selected file
    if file_param and "|" in file_param:
        selected_file, selected_path = file_param.split("|", 1)

        # 🔥 FIX WINDOWS PATHS
        selected_path = selected_path.replace("\\\\", "\\").replace("\\", "/")
    else:
        selected_file = list(MEMORY_FILES.keys())[0]
        selected_path = MEMORY_FILES[selected_file]

    available_files = [(name, path) for name, path in MEMORY_FILES.items()]

    records = load_jsonl(selected_path)

    def normalize(rec):
        return {
            "id": rec.get("id"),
            "timestamp": rec.get("timestamp"),
            "intent": rec.get("intent", ""),
            "priority": rec.get("priority", 5),
            "tags": rec.get("tags", []),
            "content": rec.get("content", ""),
            "mood": rec.get("mood", ""),
            "topic": rec.get("topic", ""),
            "related_to": rec.get("related_to"),
            "response": rec.get("response"),
            "perspective": rec.get("perspective"),
            "refer_as": rec.get("refer_as"),
        }

    normalized = [normalize(r) for r in records]

    # simple search
    if search:
        s = search.lower()
        filtered = []
        for m in normalized:
            haystack = " ".join([
                m.get("content", ""),
                m.get("intent", ""),
                " ".join(m.get("tags", [])),
            ]).lower()
            if s in haystack:
                filtered.append(m)
    else:
        filtered = normalized

    total = len(filtered)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = filtered[start:end]

    return render_template(
        "memory_manager.html",
        memories=page_items,
        page=page,
        per_page=per_page,
        total=total,
        available_files=available_files,
        selected_file=selected_file,
        selected_path=selected_path,
    )

@jarvis_bp.route("/documents/vector_db_manager", methods=["GET"])
def vector_db_manager():
    page = int(request.args.get("page", 1))
    search = request.args.get("search", "")
    file_type = request.args.get("file_type", "")

    result = list_chunks(page=page, search=search, file_type=file_type)

    return render_template(
        "vector_db_manager.html",
        documents=result["documents"],
        total_documents=result["total_documents"],
        file_types=result["file_types"],
        page=result["page"],
        total_pages=result["total_pages"],
        search_query=search,
        filter_file_type=file_type
    )

# ============================================================
# VECTOR DB DELETE ENTRY (NEW)
# ============================================================

@jarvis_bp.route("/documents/delete_vector_db_entry/<chunk_id>", methods=["POST"])
def delete_vector_db_entry(chunk_id):
    success = delete_chunk(chunk_id)
    if success:
        return jsonify({"message": "Chunk deleted successfully"})
    return jsonify({"error": "Failed to delete chunk"})

@jarvis_bp.route("/jan/update_memory", methods=["POST"])
def update_memory():
    data = request.get_json(force=True)

    filename = data.get("filename")
    timestamp = data.get("timestamp")
    if not filename or not timestamp:
        return jsonify({"message": "Missing filename or timestamp"}), 400

    path = MEMORY_FILES.get(filename)
    if not path:
        return jsonify({"message": f"Unknown memory file: {filename}"}), 400

    records = load_jsonl(path)
    updated = False

    for rec in records:
        if rec.get("timestamp") == timestamp:
            rec["content"] = data.get("content", rec.get("content"))
            rec["tags"] = data.get("tags", rec.get("tags", []))
            rec["intent"] = data.get("intent", rec.get("intent"))
            rec["mood"] = data.get("mood", rec.get("mood"))
            rec["topic"] = data.get("topic", rec.get("topic"))
            rec["priority"] = data.get("priority", rec.get("priority", 5))
            rec["related_to"] = data.get("related_to")
            rec["response"] = data.get("response")
            rec["perspective"] = data.get("perspective")
            rec["refer_as"] = data.get("refer_as")
            updated = True
            break

    if not updated:
        return jsonify({"message": "Memory not found"}), 404

    save_jsonl(path, records)
    _reload_memory_cache()
    return jsonify({"message": "Memory updated successfully"})

@jarvis_bp.route("/jan/delete_memory", methods=["POST"])
def delete_memory():
    timestamp = request.form.get("timestamp")

    # default to first configured file
    if not MEMORY_FILES:
        return jsonify({"message": "No memory files configured"}), 500
    selected_file = list(MEMORY_FILES.keys())[0]
    path = MEMORY_FILES.get(selected_file)

    records = load_jsonl(path)
    new_records = [r for r in records if r.get("timestamp") != timestamp]
    save_jsonl(path, new_records)
    _reload_memory_cache()

    return jsonify({"message": "Memory deleted"})

# ============================================================
# VECTOR DB CLEAR ALL (NEW)
# ============================================================

@jarvis_bp.route("/documents/clear_vector_db", methods=["POST"])
def clear_vector_db():
    success = clear_all()
    if success:
        return jsonify({"message": "Vector metadata cleared"})
    return jsonify({"error": "Failed to clear metadata"})

# ============================================================
# SESSION API ENDPOINTS
# ============================================================

@jarvis_bp.route("/api/sessions", methods=["GET"])
def api_get_sessions():
    return jsonify({"sessions": list_sessions()})

@jarvis_bp.route("/api/session", methods=["POST"])
def api_create_session():
    new_id = create_new_session()
    return jsonify({"id": new_id})

@jarvis_bp.route("/api/turns/<int:session_id>", methods=["GET"])
def api_get_turns(session_id):
    return jsonify(get_turns(session_id))

@jarvis_bp.route("/api/session/<int:session_id>", methods=["DELETE"])
def api_delete_session(session_id):
    delete_session(session_id)
    return "", 204

@jarvis_bp.route("/api/session/<int:session_id>/rename", methods=["POST"])
def api_rename_session(session_id):
    data = request.get_json()
    new_title = (data.get("title") or "").strip()
    if not new_title:
        return jsonify({"error": "Title cannot be empty"}), 400
    conn = sqlite3.connect(SESSION_DB_PATH)
    conn.execute("UPDATE sessions SET title = ? WHERE id = ?", (new_title, session_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# ============================================================
# MOBILE STT UPLOAD — receives audio blob from phone browser
# ============================================================

@jarvis_bp.route("/stt/upload", methods=["POST"])
def stt_upload():
    """Receive audio blob from mobile browser, transcribe with Whisper, return text."""
    import tempfile as _tempfile
    import os as _os

    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided", "text": ""}), 400

    audio_file = request.files["audio"]

    # Pick suffix from filename if available, default to .webm
    suffix = ".webm"
    if audio_file.filename:
        ext = _os.path.splitext(audio_file.filename)[1]
        if ext:
            suffix = ext

    tmp_path = None
    try:
        with _tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            audio_file.save(tmp.name)
            tmp_path = tmp.name

        from mcp_servers_hub.stt_server.stt_server import transcribe_file
        text = transcribe_file(tmp_path)
        return jsonify({"text": text.strip() if text else ""})

    except Exception as e:
        return jsonify({"error": str(e), "text": ""}), 500

    finally:
        if tmp_path:
            try:
                _os.unlink(tmp_path)
            except Exception:
                pass

# ============================================================
# MAIN CHAT ENDPOINT
# ============================================================

@jarvis_bp.route("/controlpanel", methods=["GET"])
def controlpanel():
    return render_template("controlpanel.html")

# ============================================================
# CYBER SECURITY DASHBOARD ROUTES
# ============================================================
from mcp_servers_hub.cyber_security_servers.cyber_security_server import (
    generate_security_digest,
    get_personal_info, save_personal_info, build_broker_urls, log_broker_submission, get_identity_summary,
    REFUSED_BROKERS,
    fetch_cve_feed, scan_dependencies, get_all_cves, get_threat_summary, get_dependency_results,
    dismiss_cve, clear_all_cves, clear_dep_results,
    build_integrity_baseline, run_integrity_check, get_integrity_log, get_system_summary
)

@jarvis_bp.route("/cyber/dashboard", methods=["GET"])
def cyber_dashboard():
    return render_template("cyber_security.html")

@jarvis_bp.route("/cyber/digest", methods=["GET"])
def cyber_digest():
    return jsonify(generate_security_digest())

@jarvis_bp.route("/cyber/identity", methods=["GET"])
def cyber_identity_get():
    return jsonify(get_personal_info())

@jarvis_bp.route("/cyber/identity", methods=["POST"])
def cyber_identity_save():
    d = request.get_json(silent=True) or {}
    return jsonify(save_personal_info(
        d.get("first_name",""), d.get("last_name",""),
        d.get("city",""),       d.get("state",""),
        d.get("email",""),      d.get("phone","")
    ))

@jarvis_bp.route("/cyber/brokers", methods=["GET"])
def cyber_brokers():
    return jsonify(build_broker_urls())

@jarvis_bp.route("/cyber/brokers/log", methods=["POST"])
def cyber_broker_log():
    d      = request.get_json(silent=True) or {}
    broker = d.get("broker_name","")
    action = d.get("action","submitted")
    notes  = d.get("notes","")
    if not broker:
        return jsonify({"error": "broker_name required"}), 400
    return jsonify(log_broker_submission(broker, action, notes))

@jarvis_bp.route("/cyber/identity/summary", methods=["GET"])
def cyber_identity_summary():
    return jsonify(get_identity_summary())

@jarvis_bp.route("/cyber/brokers/refused", methods=["GET"])
def cyber_brokers_refused():
    return jsonify(REFUSED_BROKERS)

@jarvis_bp.route("/cyber/cve/fetch", methods=["POST"])
def cyber_cve_fetch():
    data    = request.get_json(silent=True) or {}
    keyword = data.get("keyword", "python")
    return jsonify(fetch_cve_feed(keyword))

@jarvis_bp.route("/cyber/deps/scan", methods=["POST"])
def cyber_deps_scan():
    return jsonify(scan_dependencies())

@jarvis_bp.route("/cyber/cves", methods=["GET"])
def cyber_cves():
    return jsonify(get_all_cves())

@jarvis_bp.route("/cyber/deps/results", methods=["GET"])
def cyber_deps_results():
    return jsonify(get_dependency_results())

@jarvis_bp.route("/cyber/cve/<int:cve_id>/dismiss", methods=["POST"])
def cyber_cve_dismiss(cve_id):
    return jsonify(dismiss_cve(cve_id))

@jarvis_bp.route("/cyber/cve/clear", methods=["POST"])
def cyber_cve_clear():
    return jsonify(clear_all_cves())

@jarvis_bp.route("/cyber/deps/clear", methods=["POST"])
def cyber_deps_clear():
    return jsonify(clear_dep_results())

@jarvis_bp.route("/cyber/integrity/baseline", methods=["POST"])
def cyber_baseline():
    return jsonify(build_integrity_baseline())

@jarvis_bp.route("/cyber/integrity/check", methods=["POST"])
def cyber_integrity_check():
    return jsonify(run_integrity_check())

@jarvis_bp.route("/cyber/integrity/log", methods=["GET"])
def cyber_integrity_log():
    return jsonify(get_integrity_log())

@jarvis_bp.route("/talk", methods=["POST"])
def talk():
    data = request.get_json(silent=True) or {}
    user_input = data.get("message", "").strip()
    session_id = data.get("session_id")

    if not user_input:
        return jsonify({"error": "No input received"}), 400

    # Normalize session_id — treat "None", "null", empty as no session
    if session_id in (None, "None", "null", "", 0, "0"):
        session_id = None

    # Only store turns if a real session is active
    if session_id:
        add_turn(session_id, "user", user_input)

    result = handle_request(user_input, session_id=session_id)

    if isinstance(result, dict):
        response_text = result.get("response") or result.get("message") or ""
    else:
        response_text = str(result)

    if session_id:
        add_turn(session_id, "jarvis", response_text)

    return jsonify({
        "message": response_text,
        "response": response_text,
        "items": []
    })
