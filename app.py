# === Jarvis 4.0 Boot Layer — with STT Wake Word Listener ===

import os
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from mcp_servers_hub.memory_servers.contacts_server.server import contacts_bp
from mcp_servers_hub.email_server.email_routes import email_bp
from mcp_servers_hub.documents_server.routes import documents_bp
from mcp_servers_hub.self_writing_server.routes import self_writing_bp
from mcp_servers_hub.crypto_wallet_server.routes import crypto_bp
from mcp_servers_hub.login_security.security import login_bp, handle_404, start_background_scanner
from mcp_servers_hub.crypto_wallet_server.trading_brain import start_candle_collector

# Import the new web routes
from jarvis_routes import jarvis_bp, upload_bp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

app = Flask(__name__, static_folder=STATIC_DIR, template_folder=TEMPLATE_DIR)
app.secret_key = os.environ.get("JARVIS_SECRET_KEY", "change-me-in-production")

# Optional: trust reverse proxy headers
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1)

# Register blueprints
app.register_blueprint(login_bp)
app.register_blueprint(jarvis_bp, url_prefix="/")
app.register_blueprint(contacts_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(email_bp)
app.register_blueprint(documents_bp)
app.register_blueprint(self_writing_bp)
app.register_blueprint(crypto_bp)

# Security — 404 probe logger
app.register_error_handler(404, handle_404)

app.config["LMSTUDIO_API_URL"] = "http://127.0.0.1:1234/v1/chat/completions"

@app.route("/health")
def health():
    return "ok", 200

@app.route("/favicon.ico")
def favicon():
    from flask import send_from_directory
    return send_from_directory(STATIC_DIR, "favicon.ico", mimetype="image/x-icon")

@app.route("/manifest.json")
def manifest():
    from flask import send_from_directory
    return send_from_directory(STATIC_DIR, "manifest.json", mimetype="application/manifest+json")

# ============================================================
# STT — Button triggered transcribe endpoint
# ============================================================

from mcp_servers_hub.stt_server.stt_server import record_and_transcribe

@app.route("/stt/record", methods=["POST"])
def stt_record():
    """
    Called by the WebUI microphone button.
    Records for 6 seconds and returns transcription.
    """
    from flask import request, jsonify
    try:
        data = request.get_json(silent=True) or {}
        duration = float(data.get("duration", 6))

        text = record_and_transcribe(duration)

        if not text:
            return jsonify({"error": "Could not transcribe audio"}), 400

        return jsonify({"transcription": text})

    except ValueError as ve:
        app.logger.error(f"[STT] Invalid duration value: {ve}")
        return jsonify({"error": "Invalid request data"}), 400
    except Exception as e:
        app.logger.error(f"[STT] Transcription failed: {e}")
        return jsonify({"error": "Failed to transcribe audio"}), 500


# ============================================================
# Start Wake Word Listener on Boot
# ============================================================

if __name__ == "__main__":

    # Clear stale session turns so old wrong answers don't poison new conversations
    try:
        import sqlite3 as _sqlite3, os as _os
        _session_db = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
            "mcp_servers_hub", "memory_servers", "sqlite_server", "session.db")
        if _os.path.exists(_session_db):
            _conn = _sqlite3.connect(_session_db)
            _conn.execute("DELETE FROM turns")
            _conn.commit()
            _conn.close()
            print("[Jarvis] Session history cleared on startup.")
    except Exception as e:
        print(f"[Jarvis] Session clear failed: {e}")

    # Warm JSONL memory cache into RAM before first request
    try:
        from mcp_servers_hub.memory_servers.jsonl_server.jsonl_memory_server import warm_cache
        warm_cache()
        print("[Jarvis] Memory cache warmed.")
    except Exception as e:
        print(f"[Jarvis] Memory cache warm failed: {e}")

    # Start wake word listener in background
    try:
        from mcp_servers_hub.stt_server.wake_word_listener import start as start_wake_word
        start_wake_word()
        print("[Jarvis] Wake word listener started.")
    except Exception as e:
        print(f"[Jarvis] Wake word listener failed to start: {e}")

    # Start 15-minute background security scanner
    try:
        start_background_scanner()
    except Exception as e:
        print(f"[Jarvis] Security scanner failed to start: {e}")

    # Start 15-minute background candle collector for crypto trading
    try:
        start_candle_collector()
    except Exception as e:
        print(f"[Jarvis] Candle collector failed to start: {e}")

    print("[Jarvis] Flask is running on port 5000.")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,   # Must be False when using background threads
        threaded=True
    )