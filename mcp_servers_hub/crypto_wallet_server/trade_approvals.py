# === Jarvis 4.0 — Trade Approval System (Phase 2) ===
# All real trades require explicit approval before execution.
# Auto-expires after 15 minutes if no response.

import os
import json
import uuid
import logging
from datetime import datetime, UTC, timedelta

logger = logging.getLogger("trade_approvals")

# ---------------------------------------------------------
# Config
# ---------------------------------------------------------
APPROVALS_FILE     = "mcp_servers_hub/crypto_wallet_server/pending_approvals.json"
EXPIRY_MINUTES     = 15
REAL_TRADE_LOG     = "mcp_servers_hub/crypto_wallet_server/real_trades.json"

# Phase 2 live trading toggle — starts OFF, user enables from dashboard
_phase2_enabled = False


# ---------------------------------------------------------
# Phase 2 Toggle
# ---------------------------------------------------------

def is_phase2_enabled() -> bool:
    return _phase2_enabled


def set_phase2_enabled(enabled: bool):
    global _phase2_enabled
    _phase2_enabled = enabled
    status = "ENABLED" if enabled else "DISABLED"
    logger.warning(f"[Approvals] Phase 2 live trading {status}.")


# ---------------------------------------------------------
# Approval File Helpers
# ---------------------------------------------------------

def _load_approvals() -> list:
    if not os.path.exists(APPROVALS_FILE):
        return []
    try:
        with open(APPROVALS_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def _save_approvals(approvals: list):
    try:
        with open(APPROVALS_FILE, "w") as f:
            json.dump(approvals, f, indent=2)
    except Exception as e:
        logger.error(f"[Approvals] Save error: {e}")


# ---------------------------------------------------------
# Request Approval
# ---------------------------------------------------------

DJED_TOKEN = "8db269c3ec630e06ae29f74bc39edd1f87c819f1056206e879a1cd644a65644d6963726f555344"


def request_approval(signal: dict) -> dict:
    """
    Create a pending trade approval from a trading signal.
    Returns the approval record.
    """
    approvals = _load_approvals()

    # Only one pending approval at a time
    pending = [a for a in approvals if a["status"] == "pending"]
    if pending:
        logger.info("[Approvals] Already have a pending approval — skipping.")
        return {"ok": False, "reason": "Approval already pending."}

    # --- Wallet balance check before creating approval ---
    action     = signal.get("signal")
    ada_amount = signal.get("would_trade", {}).get("ada_amount", 20.0)
    try:
        from mcp_servers_hub.crypto_wallet_server.crypto_wallet_server import get_balance
        balance = get_balance()
        if "error" not in balance:
            if action == "SELL":
                # Need enough ADA to sell
                if balance.get("ada", 0) < ada_amount:
                    logger.warning(
                        f"[Approvals] Skipping SELL — insufficient ADA. "
                        f"Have {balance.get('ada', 0):.2f}, need {ada_amount}"
                    )
                    return {"ok": False, "reason": f"Insufficient ADA. Have {balance.get('ada', 0):.2f}, need {ada_amount}"}
            elif action == "BUY":
                # Need DJED balance to buy with
                djed_balance = next(
                    (int(t["quantity"]) for t in balance.get("tokens", []) if t["unit"] == DJED_TOKEN),
                    0
                )
                if djed_balance <= 0:
                    logger.warning("[Approvals] Skipping BUY — no DJED balance in wallet.")
                    return {"ok": False, "reason": "No DJED balance available for BUY trade."}
    except Exception as e:
        logger.warning(f"[Approvals] Balance check failed — proceeding anyway: {e}")

    now     = datetime.now(UTC)
    expires = now + timedelta(minutes=EXPIRY_MINUTES)

    approval = {
        "id":         str(uuid.uuid4())[:8],
        "action":     signal.get("signal"),          # BUY or SELL
        "ada_amount": signal.get("would_trade", {}).get("ada_amount", 20.0),
        "price":      signal.get("price"),
        "reason":     signal.get("reason"),
        "ema_short":  signal.get("ema_short"),
        "ema_long":   signal.get("ema_long"),
        "created_at": now.isoformat(),
        "expires_at": expires.isoformat(),
        "status":     "pending",
        "tx_id":      None,
        "paper_signal": signal
    }

    approvals.append(approval)
    _save_approvals(approvals)

    logger.warning(
        f"[Approvals] ⏳ Trade approval requested — "
        f"{approval['action']} {approval['ada_amount']} ADA @ ${approval['price']} "
        f"| Expires in {EXPIRY_MINUTES} min | ID: {approval['id']}"
    )
    return {"ok": True, "approval": approval}


# ---------------------------------------------------------
# Approve Trade
# ---------------------------------------------------------

def approve_trade(approval_id: str) -> dict:
    """Approve a pending trade — executes real transaction."""
    approvals = _load_approvals()
    approval  = next((a for a in approvals if a["id"] == approval_id), None)

    if not approval:
        return {"ok": False, "error": f"Approval ID {approval_id} not found."}

    if approval["status"] != "pending":
        return {"ok": False, "error": f"Approval is already {approval['status']}."}

    # Check not expired
    expires = datetime.fromisoformat(approval["expires_at"])
    if datetime.now(UTC) > expires:
        approval["status"] = "expired"
        _save_approvals(approvals)
        return {"ok": False, "error": "Approval has expired."}

    # Execute the real trade
    from mcp_servers_hub.crypto_wallet_server.trade_executor import execute_trade
    logger.warning(f"[Approvals] ✅ Executing APPROVED trade: {approval['action']} {approval['ada_amount']} ADA")

    result = execute_trade(approval["action"], approval["ada_amount"])

    if result["ok"]:
        approval["status"] = "approved"
        approval["tx_id"]  = result["tx_id"]
        _save_approvals(approvals)
        _log_real_trade(approval, result)
        logger.warning(f"[Approvals] ✅ Trade executed! TX: {result['tx_id']}")
        return {"ok": True, "tx_id": result["tx_id"], "approval": approval}
    else:
        approval["status"] = "failed"
        approval["error"]  = result.get("error", "Unknown error")
        _save_approvals(approvals)
        logger.error(f"[Approvals] ❌ Trade execution failed: {result.get('error')}")
        return {"ok": False, "error": result.get("error"), "step": result.get("step")}


# ---------------------------------------------------------
# Reject Trade
# ---------------------------------------------------------

def reject_trade(approval_id: str) -> dict:
    """Reject a pending trade — no transaction executed."""
    approvals = _load_approvals()
    approval  = next((a for a in approvals if a["id"] == approval_id), None)

    if not approval:
        return {"ok": False, "error": f"Approval ID {approval_id} not found."}

    if approval["status"] != "pending":
        return {"ok": False, "error": f"Approval is already {approval['status']}."}

    approval["status"] = "rejected"
    _save_approvals(approvals)
    logger.info(f"[Approvals] ❌ Trade rejected — ID: {approval_id}")
    return {"ok": True, "message": "Trade rejected."}


# ---------------------------------------------------------
# Get Pending Approvals
# ---------------------------------------------------------

def get_pending_approvals() -> list:
    """Return all currently pending (non-expired) approvals."""
    expire_old_approvals()
    approvals = _load_approvals()
    return [a for a in approvals if a["status"] == "pending"]


def get_all_approvals(limit: int = 20) -> list:
    """Return recent approvals for history display."""
    approvals = _load_approvals()
    return approvals[-limit:]


# ---------------------------------------------------------
# Auto-Expire
# ---------------------------------------------------------

def expire_old_approvals():
    """Mark expired approvals — called before checking pending."""
    approvals = _load_approvals()
    now       = datetime.now(UTC)
    changed   = False

    for a in approvals:
        if a["status"] == "pending":
            expires = datetime.fromisoformat(a["expires_at"])
            if now > expires:
                a["status"] = "expired"
                changed = True
                logger.info(f"[Approvals] Approval {a['id']} expired.")

    if changed:
        _save_approvals(approvals)


# ---------------------------------------------------------
# Real Trade Logger
# ---------------------------------------------------------

def _log_real_trade(approval: dict, result: dict):
    """Log executed real trades separately from paper trades."""
    try:
        trades = []
        if os.path.exists(REAL_TRADE_LOG):
            with open(REAL_TRADE_LOG) as f:
                trades = json.load(f)

        trades.append({
            "id":         approval["id"],
            "action":     approval["action"],
            "ada_amount": approval["ada_amount"],
            "price":      approval["price"],
            "tx_id":      result.get("tx_id"),
            "executed_at": datetime.now(UTC).isoformat(),
            "paper_signal": approval.get("paper_signal")
        })

        trades = trades[-100:]  # Keep last 100 real trades
        with open(REAL_TRADE_LOG, "w") as f:
            json.dump(trades, f, indent=2)
    except Exception as e:
        logger.error(f"[Approvals] Real trade log error: {e}")


def get_real_trades(limit: int = 20) -> list:
    """Return recent real executed trades."""
    if not os.path.exists(REAL_TRADE_LOG):
        return []
    try:
        with open(REAL_TRADE_LOG) as f:
            trades = json.load(f)
        return trades[-limit:]
    except Exception:
        return []
