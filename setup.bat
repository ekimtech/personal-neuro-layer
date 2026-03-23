@echo off
echo ============================================================
echo   Jarvis Personal Neuro Layer — Setup
echo ============================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

echo [1/5] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)

echo [2/5] Activating virtual environment...
call venv\Scripts\activate.bat

echo [3/5] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo [4/5] Setting up config files...

REM Copy example configs if real ones don't exist
if not exist "mcp_servers_hub\home_assistant_server\ha_config.py" (
    echo      Created ha_config.py — fill in your Home Assistant URL and token
)
if not exist "mcp_servers_hub\email_server\.env" (
    echo      Created .env — fill in your email credentials
)
if not exist "mcp_servers_hub\login_security\auth_config.py" (
    echo      Created auth_config.py — set your Jarvis login username and password
)
if not exist "mcp_servers_hub\mikrotik_server\mikrotik_config.py" (
    echo      Created mikrotik_config.py — fill in your router credentials
)
if not exist "mcp_servers_hub\qnap_server\qnap_config.py" (
    echo      Created qnap_config.py — fill in your QNAP token and IP
)
if not exist "mcp_servers_hub\crypto_wallet_server\wallet_config.py" (
    echo      Created wallet_config.py — fill in your Blockfrost project ID
)

echo [5/5] Creating required folders...
if not exist "uploads" mkdir uploads
if not exist "documents" mkdir documents
if not exist "certs" mkdir certs
if not exist "mcp_servers_hub\memory_servers\jsonl_server\storage" (
    mkdir "mcp_servers_hub\memory_servers\jsonl_server\storage"
)

echo.
echo ============================================================
echo   Setup complete!
echo.
echo   BEFORE starting Jarvis, fill in your config files:
echo.
echo   1. mcp_servers_hub\home_assistant_server\ha_config.py
echo      - Your Home Assistant IP and long-lived token
echo.
echo   2. mcp_servers_hub\login_security\auth_config.py
echo      - Username and password for the Jarvis web UI
echo.
echo   3. mcp_servers_hub\email_server\.env
echo      - Your email address and password
echo.
echo   4. mcp_servers_hub\mikrotik_server\mikrotik_config.py
echo      - Your MikroTik router IP and credentials
echo      (Skip if you don't have a MikroTik router)
echo.
echo   5. mcp_servers_hub\qnap_server\qnap_config.py
echo      - Your QNAP NAS IP and MCP token
echo      (Skip if you don't have a QNAP NAS)
echo.
echo   6. mcp_servers_hub\crypto_wallet_server\wallet_config.py
echo      - Your Blockfrost Project ID from blockfrost.io
echo      (Skip if you don't want crypto trading)
echo.
echo   7. model_injection\internet_server\server.py
echo      - Change DEFAULT_LOCATION to your city
echo.
echo   Then start Jarvis:
echo      python app.py
echo.
echo   Open your browser at: http://localhost:5000
echo ============================================================
pause
