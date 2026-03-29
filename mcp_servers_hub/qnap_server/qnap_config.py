# === Jarvis 4.0 — QNAP NAS Config ===
# 1. Install the QNAP MCP Server app on your NAS
# 2. Generate an MCP token in the app settings
# 3. Set QNAP_URL to your NAS LAN IP and MCP port (default 8442)

QNAP_TOKEN = "YOUR_QNAP_MCP_TOKEN_HERE"
QNAP_URL   = "http://192.168.X.X:8442/sse"

# === Backup & File System Config ===
# Set JARVIS_SOURCE to the full path of your Jarvis4.0 project folder
# Set JARVIS_BACKUP_PATH to where backups should be stored (e.g. a mapped NAS drive)
# Set NAS_DRIVE to the mapped drive letter Jarvis uses for file operations

JARVIS_SOURCE      = r"C:\path\to\your\Jarvis4.0"
JARVIS_BACKUP_PATH = r"X:\backups"
NAS_DRIVE          = r"X:\\"
