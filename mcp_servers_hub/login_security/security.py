# === Jarvis 4.0 — Login Security MCP Organ ===
# Handles: login, logout, @login_required, failed attempt tracking, IP blacklisting
# Adapted from Jarvis 3.0 ip_blocker.py

import os
import re
import json
import time
import threading
import logging
import ipaddress
from datetime import datetime, UTC, timedelta
from functools import wraps
from logging.handlers import RotatingFileHandler
from flask import (
    Blueprint, request, session, redirect, url_for,
    render_template, flash, abort
)

from mcp_servers_hub.login_security.auth_config import (
    AUTH_USERNAME, AUTH_PASSWORD,
    MAX_ATTEMPTS, ATTEMPT_WINDOW_MINUTES
)

# --- Base directory ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Security logger with rotating file handler ---
LOG_DIR = os.path.join(BASE_DIR, "mcp_servers_hub", "login_security", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
SECURITY_LOG_FILE = os.path.join(LOG_DIR, "security.log")

logger = logging.getLogger("login_security")
logger.setLevel(logging.INFO)

if not logger.handlers:
    # Rotating file: 5 files × 500KB each
    file_handler = RotatingFileHandler(
        SECURITY_LOG_FILE, maxBytes=500_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(file_handler)

    # Also keep console output
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(levelname)s | %(message)s"))
    logger.addHandler(console_handler)

# --- Startup log ---
logger.info("[Security] Jarvis 4.0 Login Security initialized. Watching for threats.")

# --- Blueprint ---
login_bp = Blueprint("login_bp", __name__)

# --- Probe log path ---
PROBE_LOG_FILE = os.path.join(BASE_DIR, "mcp_servers_hub", "login_security", "logs", "probe_logs.txt")

# --- Persistent banned IPs file ---
BANNED_IPS_FILE = os.path.join(BASE_DIR, "mcp_servers_hub", "login_security", "logs", "banned_ips.json")

# --- In-memory failed attempt tracker ---
# { ip: {"count": int, "first_attempt": datetime} }
_failed_attempts: dict = {}

# --- In-memory blocked IPs (Flask layer) — loaded from file at startup ---
_blocked_ips: set = set()


def _load_banned_ips():
    """Load persistent banned IPs from JSON file into memory at startup."""
    try:
        if os.path.exists(BANNED_IPS_FILE):
            with open(BANNED_IPS_FILE, "r") as f:
                entries = json.load(f)
            for entry in entries:
                ip = entry.get("ip", "").strip()
                if ip:
                    _blocked_ips.add(ip)
            logger.info(f"[Security] Loaded {len(_blocked_ips)} banned IPs from persistent store.")
    except Exception as e:
        logger.error(f"[Security] Failed to load banned IPs: {e}")


def _save_banned_ip(ip: str, reason: str):
    """Append a newly banned IP to the persistent JSON file."""
    try:
        entries = []
        if os.path.exists(BANNED_IPS_FILE):
            with open(BANNED_IPS_FILE, "r") as f:
                entries = json.load(f)
        # Avoid duplicates
        if not any(e.get("ip") == ip for e in entries):
            entries.append({
                "ip": ip,
                "reason": reason,
                "source": "jarvis_4.0",
                "timestamp": datetime.now(UTC).isoformat()
            })
            with open(BANNED_IPS_FILE, "w") as f:
                json.dump(entries, f, indent=2)
    except Exception as e:
        logger.error(f"[Security] Failed to save banned IP {ip}: {e}")


# --- Load persisted bans into memory at startup ---
_load_banned_ips()

# ---------------------------------------------------------
# Background Scanner — Configuration
# ---------------------------------------------------------
SCAN_INTERVAL_SECONDS = 900        # 15 minutes
TIME_WINDOW_HOURS     = 24         # Look back 24 hours in logs
SUSPICIOUS_THRESHOLD  = 5          # Hits before ban
BURST_COUNT           = 10         # Hits within BURST_WINDOW = instant ban
BURST_WINDOW_SECONDS  = 10

SUSPICIOUS_PATTERNS = [
    r"\.env$", r"phpinfo\.php$", r"info\.php$", r"credentials",
    r"sparkpost", r"sendgrid", r"backup", r"SMTP\.php$",
    r"conf\.php", r"pinfo\.php", r"phpversion\.php",
    r"wp-admin", r"wp-login", r"\.php$", r"passwd", r"shell", r"setup\.cgi"
]

MIKROTIK_SUSPICIOUS_KEYWORDS = [
    "ScanAttempt", "brute-force attempt", "failed login",
    "authentication failure", "connection attempt",
]

IP_REGEX = re.compile(r'(?:from|src-address|src-mac)=([0-9a-fA-F.:-]+)')


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _get_client_ip() -> str:
    """Get real client IP, respecting Cloudflare/proxy headers."""
    return (
        request.headers.get("CF-Connecting-IP") or
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or
        request.remote_addr or
        "unknown"
    )


def _is_private(ip: str) -> bool:
    """Returns True for private/loopback IPs — never block these."""
    try:
        return ipaddress.ip_address(ip).is_private or ipaddress.ip_address(ip).is_loopback
    except ValueError:
        return False


def _log_probe(ip: str, path: str, reason: str = "404"):
    """Append a probe entry to probe_logs.txt."""
    try:
        user_agent = request.headers.get("User-Agent", "Unknown")
        entry = f"{ip} | {datetime.now(UTC).isoformat()} | {path} | {user_agent} | {reason}\n"
        with open(PROBE_LOG_FILE, "a") as f:
            f.write(entry)
    except Exception as e:
        logger.error(f"[Security] Probe log error: {e}")


def _block_ip_mikrotik(ip: str, reason: str = "Blocked by Jarvis"):
    """Push IP to MikroTik Jarvis-Blacklist address list via SSH."""
    try:
        from mcp_servers_hub.mikrotik_server.mikrotik_server import block_ip
        result = block_ip(ip, comment=reason)
        if isinstance(result, dict) and result.get("status") == "success":
            logger.warning(f"[Security] Blacklisted on MikroTik: {ip} — {reason}")
        else:
            logger.error(f"[Security] MikroTik block failed for {ip}: {result}")
        return result
    except Exception as e:
        logger.error(f"[Security] MikroTik block failed for {ip}: {e}")
        return False


def _record_failed_attempt(ip: str):
    """Track failed login attempts and block after MAX_ATTEMPTS."""
    if _is_private(ip):
        return

    now = datetime.now(UTC)
    entry = _failed_attempts.get(ip)

    if entry:
        # Reset window if expired
        if now - entry["first_attempt"] > timedelta(minutes=ATTEMPT_WINDOW_MINUTES):
            _failed_attempts[ip] = {"count": 1, "first_attempt": now}
            return
        entry["count"] += 1
    else:
        _failed_attempts[ip] = {"count": 1, "first_attempt": now}

    count = _failed_attempts[ip]["count"]
    logger.warning(f"[Security] Failed login attempt {count}/{MAX_ATTEMPTS} from {ip}")

    if count >= MAX_ATTEMPTS:
        reason = f"Jarvis: {count} failed login attempts"
        _blocked_ips.add(ip)
        _save_banned_ip(ip, reason)
        _block_ip_mikrotik(ip, reason=reason)
        logger.warning(f"[Security] IP {ip} blocked after {count} failed attempts.")


def get_blocked_count() -> int:
    return len(_blocked_ips)


def get_probe_count() -> int:
    """Count entries in probe_logs.txt."""
    try:
        if not os.path.exists(PROBE_LOG_FILE):
            return 0
        with open(PROBE_LOG_FILE) as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


# ---------------------------------------------------------
# Background Scanner — 15-minute probe log + MikroTik analyzer
# ---------------------------------------------------------

def _fetch_mikrotik_system_logs() -> list:
    """Pull MikroTik system logs via SSH and return suspicious (timestamp, ip, line) tuples."""
    entries = []
    try:
        from mcp_servers_hub.mikrotik_server.mikrotik_server import run_command
        output = run_command("/log print")
        if not output:
            return entries
        now = datetime.now(UTC)
        for line in output.splitlines():
            stripped = line.strip()
            if len(stripped) < 19:
                continue
            # Check for suspicious keywords
            if not any(kw.lower() in stripped.lower() for kw in MIKROTIK_SUSPICIOUS_KEYWORDS):
                continue
            # Try to parse timestamp
            try:
                ts_str = stripped[:19]
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
                if now - ts > timedelta(hours=TIME_WINDOW_HOURS):
                    continue
            except ValueError:
                ts = now
            # Extract IP
            match = IP_REGEX.search(stripped)
            if match:
                try:
                    ip = str(ipaddress.ip_address(match.group(1)))
                    entries.append((ts, ip, stripped))
                except ValueError:
                    pass
    except Exception as e:
        logger.error(f"[Scanner] MikroTik log fetch error: {e}")
    return entries


def _analyze_and_ban():
    """
    Read probe_logs.txt + MikroTik system logs.
    Count suspicious hits per IP — ban anything that exceeds threshold.
    Runs every 15 minutes via background thread.
    """
    logger.info("[Scanner] Starting 15-minute security scan...")
    now = datetime.now(UTC)
    ip_activity: dict = {}  # { ip: [(timestamp, source, content), ...] }

    # --- Read probe_logs.txt ---
    if os.path.exists(PROBE_LOG_FILE):
        try:
            with open(PROBE_LOG_FILE, "r") as f:
                for line in f:
                    parts = line.strip().split(" | ")
                    if len(parts) >= 3:
                        ip   = parts[0].strip()
                        path = parts[2].strip()
                        try:
                            ts = datetime.fromisoformat(parts[1].strip()).replace(tzinfo=UTC)
                        except ValueError:
                            ts = now
                        if now - ts <= timedelta(hours=TIME_WINDOW_HOURS):
                            ip_activity.setdefault(ip, []).append((ts, "probe", path))
        except Exception as e:
            logger.error(f"[Scanner] Error reading probe log: {e}")
    else:
        logger.debug("[Scanner] No probe_logs.txt yet — skipping probe analysis.")

    # --- Read MikroTik system logs ---
    for ts, ip, msg in _fetch_mikrotik_system_logs():
        ip_activity.setdefault(ip, []).append((ts, "mikrotik", msg))

    # --- Evaluate each IP ---
    newly_banned = 0
    for ip, activities in ip_activity.items():
        if _is_private(ip) or ip in _blocked_ips:
            continue

        # Count suspicious probe hits
        suspicious_hits = sum(
            1 for ts, src, content in activities
            if src == "probe" and any(re.search(p, content, re.IGNORECASE) for p in SUSPICIOUS_PATTERNS)
        )
        # Add MikroTik hits
        suspicious_hits += sum(1 for ts, src, _ in activities if src == "mikrotik")

        # Burst detection — 10+ hits within 10 seconds
        timestamps = sorted(ts for ts, _, _ in activities)
        burst = (
            len(timestamps) >= BURST_COUNT and
            (timestamps[-1] - timestamps[0]).total_seconds() < BURST_WINDOW_SECONDS
        )

        if burst:
            reason = f"Jarvis Scanner: Burst probe detected ({len(timestamps)} hits)"
            logger.warning(f"[Scanner] BURST detected from {ip} — banning immediately.")
        elif suspicious_hits >= SUSPICIOUS_THRESHOLD:
            reason = f"Jarvis Scanner: {suspicious_hits} suspicious probes in 24h"
        else:
            continue

        # Ban it
        _blocked_ips.add(ip)
        _save_banned_ip(ip, reason)
        _block_ip_mikrotik(ip, reason=reason)
        logger.warning(f"[Scanner] Banned {ip} — {reason}")
        newly_banned += 1

    if newly_banned:
        logger.warning(f"[Scanner] Scan complete — {newly_banned} new IP(s) banned.")
    else:
        logger.info(f"[Scanner] Scan complete — no new threats found. ({len(ip_activity)} IPs reviewed)")


def _scanner_loop():
    """Background thread: run analysis every 15 minutes."""
    # Small startup delay so Flask is fully up first
    time.sleep(30)
    while True:
        try:
            _analyze_and_ban()
        except Exception as e:
            logger.error(f"[Scanner] Unexpected error in scanner loop: {e}")
        time.sleep(SCAN_INTERVAL_SECONDS)


def start_background_scanner():
    """Start the 15-minute background security scanner. Call once from app.py."""
    t = threading.Thread(target=_scanner_loop, name="JarvisSecurityScanner", daemon=True)
    t.start()
    logger.info("[Scanner] Background security scanner started — runs every 15 minutes.")


# ---------------------------------------------------------
# Before-request guard — runs on every request
# ---------------------------------------------------------

@login_bp.before_app_request
def security_guard():
    """Block blacklisted IPs and enforce login on protected routes."""
    ip = _get_client_ip()

    # Always allow static files and the login/logout routes
    open_endpoints = {"login_bp.login", "login_bp.logout", "static"}
    if request.endpoint in open_endpoints:
        return

    # Always allow localhost — internal server calls (wake word listener, etc.)
    if ip in ("127.0.0.1", "::1"):
        return

    # Block blacklisted IPs
    if ip in _blocked_ips:
        logger.warning(f"[Security] Blocked IP attempted access: {ip} → {request.path}")
        abort(403)

    # Enforce login
    if not session.get("logged_in"):
        return redirect(url_for("login_bp.login"))


# ---------------------------------------------------------
# 404 Probe Logger — attached to app error handler
# ---------------------------------------------------------

def handle_404(e):
    """Log 404 probes and block IPs that hit suspicious paths."""
    ip = _get_client_ip()
    path = request.path

    if not _is_private(ip):
        _log_probe(ip, path, reason="404")

        # Suspicious path patterns — instant flag
        SUSPICIOUS = [
            ".env", "phpinfo", "wp-admin", "wp-login", "credentials",
            "backup", ".php", "config", "passwd", "shell", "setup.cgi"
        ]
        if any(s in path.lower() for s in SUSPICIOUS):
            _record_failed_attempt(ip)
            logger.warning(f"[Security] Suspicious probe from {ip}: {path}")

    return render_template("404.html"), 404


# ---------------------------------------------------------
# Security Report — readable by Jarvis chat
# ---------------------------------------------------------

def _read_log_tail(filepath: str, lines: int = 50) -> list:
    """Read last N lines from a log file."""
    try:
        if not os.path.exists(filepath):
            return []
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.readlines()[-lines:]
    except Exception:
        return []


def handle(user_input: str) -> dict:
    """Security organ handler — called by MCP router."""
    text = user_input.lower().strip()

    # --- Blocked IPs ---
    if any(k in text for k in ["blocked ip", "banned ip", "who is blocked", "who is banned", "blacklist"]):
        if not _blocked_ips:
            return {"data": "✅ No IPs are currently blocked in this session."}
        lines = "\n".join(f"• {ip}" for ip in sorted(_blocked_ips))
        return {"data": f"🚫 **Currently Blocked IPs ({len(_blocked_ips)}):**\n{lines}"}

    # --- Probe log summary ---
    if any(k in text for k in ["probe log", "probe report", "who probed", "scan attempts", "port scan"]):
        entries = _read_log_tail(PROBE_LOG_FILE, 20)
        if not entries:
            return {"data": "✅ No probes logged yet."}
        count = sum(1 for _ in open(PROBE_LOG_FILE)) if os.path.exists(PROBE_LOG_FILE) else 0
        recent = "".join(entries[-10:])
        return {"data": f"🔍 **Probe Log — {count} total entries. Last 10:**\n```\n{recent}```"}

    # --- Recent bans from security log ---
    if any(k in text for k in ["recent bans", "who was banned", "who got banned", "new bans"]):
        log_lines = _read_log_tail(SECURITY_LOG_FILE, 100)
        bans = [l.strip() for l in log_lines if "banned" in l.lower() or "blacklisted" in l.lower()]
        if not bans:
            return {"data": "✅ No bans recorded in the recent log."}
        return {"data": f"🚫 **Recent Bans ({len(bans)}):**\n" + "\n".join(f"• {b}" for b in bans[-10:])}

    # --- Failed login attempts ---
    if any(k in text for k in ["failed login", "login attempt", "brute force", "failed attempt"]):
        log_lines = _read_log_tail(SECURITY_LOG_FILE, 100)
        fails = [l.strip() for l in log_lines if "failed login" in l.lower()]
        if not fails:
            return {"data": "✅ No failed login attempts in recent log."}
        return {"data": f"⚠️ **Failed Login Attempts ({len(fails)}):**\n" + "\n".join(f"• {f}" for f in fails[-10:])}

    # --- Full security report (default) ---
    probe_count   = get_probe_count()
    blocked_count = get_blocked_count()
    log_lines     = _read_log_tail(SECURITY_LOG_FILE, 30)
    recent_events = [l.strip() for l in log_lines if l.strip()][-10:]

    # Count scanner runs
    scanner_runs = sum(1 for l in log_lines if "scan complete" in l.lower())
    threats_found = sum(1 for l in log_lines if "banned" in l.lower() or "blacklisted" in l.lower())

    report = (
        f"🛡️ **Jarvis Security Report**\n\n"
        f"• **Blocked IPs (this session):** {blocked_count}\n"
        f"• **Probe attempts logged:** {probe_count}\n"
        f"• **Scanner runs (last 30 log lines):** {scanner_runs}\n"
        f"• **Threats actioned:** {threats_found}\n\n"
        f"**Recent Security Events:**\n"
    )
    for event in recent_events:
        report += f"• {event}\n"

    return {"data": report}


# ---------------------------------------------------------
# Login / Logout Routes
# ---------------------------------------------------------

@login_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("jarvis_bp.index"))

    if request.method == "POST":
        ip = _get_client_ip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username == AUTH_USERNAME and password == AUTH_PASSWORD:
            session["logged_in"] = True
            session.permanent = True
            logger.info(f"[Security] Successful login from {ip}")
            # Clear failed attempts on success
            _failed_attempts.pop(ip, None)
            return redirect(url_for("jarvis_bp.index"))
        else:
            _record_failed_attempt(ip)
            flash("Invalid username or password.", "danger")

    return render_template("login.html")


@login_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login_bp.login"))
