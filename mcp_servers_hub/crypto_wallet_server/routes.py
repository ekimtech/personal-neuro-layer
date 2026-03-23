# === Crypto Wallet Routes — Phase 2 ===
# Flask Blueprint — registered at /crypto

import logging
from flask import Blueprint, render_template, jsonify, request

from mcp_servers_hub.crypto_wallet_server.crypto_wallet_server import (
    get_balance, get_ada_price, get_transactions
)
from mcp_servers_hub.crypto_wallet_server.trading_brain import (
    generate_signal, get_recent_signals, get_performance_summary
)
from mcp_servers_hub.crypto_wallet_server.trade_approvals import (
    get_pending_approvals, get_all_approvals, get_real_trades,
    approve_trade, reject_trade,
    is_phase2_enabled, set_phase2_enabled
)

logger = logging.getLogger("crypto_wallet")

crypto_bp = Blueprint("crypto_bp", __name__, url_prefix="/crypto")


# ---------------------------------------------------------
# Pages
# ---------------------------------------------------------

@crypto_bp.route("/")
@crypto_bp.route("")
def crypto_index():
    return render_template("crypto.html")


# ---------------------------------------------------------
# Data APIs (read-only)
# ---------------------------------------------------------

@crypto_bp.route("/api/balance")
def api_balance():
    return jsonify(get_balance())


@crypto_bp.route("/api/price")
def api_price():
    price, change_24h = get_ada_price()
    return jsonify({"usd": price or "unavailable", "change_24h": change_24h or 0})


@crypto_bp.route("/api/signal")
def api_signal():
    return jsonify(generate_signal())


@crypto_bp.route("/api/signals")
def api_signals():
    count = int(request.args.get("count", 20))
    return jsonify(get_recent_signals(count))


@crypto_bp.route("/api/performance")
def api_performance():
    return jsonify(get_performance_summary())


@crypto_bp.route("/api/paper-performance")
def api_paper_performance():
    """Return paper trading win rate, P&L, open/closed trade lists."""
    from mcp_servers_hub.crypto_wallet_server.trade_tracker import get_paper_performance
    return jsonify(get_paper_performance())


@crypto_bp.route("/api/paper-trades")
def api_paper_trades():
    """Return open and recent closed paper trades."""
    from mcp_servers_hub.crypto_wallet_server.trade_tracker import get_open_paper_trades, get_closed_paper_trades
    return jsonify({
        "open":   get_open_paper_trades(),
        "closed": get_closed_paper_trades(20)
    })


# ---------------------------------------------------------
# Phase 2 — Approval System APIs
# ---------------------------------------------------------

@crypto_bp.route("/api/pending-trades")
def api_pending_trades():
    """Return pending trade approvals."""
    return jsonify(get_pending_approvals())


@crypto_bp.route("/api/approve-trade/<approval_id>", methods=["POST"])
def api_approve_trade(approval_id):
    """Approve a pending trade — executes real transaction."""
    result = approve_trade(approval_id)
    return jsonify(result)


@crypto_bp.route("/api/reject-trade/<approval_id>", methods=["POST"])
def api_reject_trade(approval_id):
    """Reject a pending trade."""
    result = reject_trade(approval_id)
    return jsonify(result)


@crypto_bp.route("/api/trade-history")
def api_trade_history():
    """Return all approval history (pending, approved, rejected, expired)."""
    return jsonify(get_all_approvals())


@crypto_bp.route("/api/real-trades")
def api_real_trades():
    """Return real executed trades only."""
    return jsonify(get_real_trades())


# ---------------------------------------------------------
# Phase 2 — Kill Switch
# ---------------------------------------------------------

@crypto_bp.route("/api/phase2/status")
def api_phase2_status():
    """Return Phase 2 live trading status."""
    return jsonify({"enabled": is_phase2_enabled()})


@crypto_bp.route("/api/phase2/enable", methods=["POST"])
def api_phase2_enable():
    """Enable Phase 2 live trading."""
    set_phase2_enabled(True)
    logger.warning("[Routes] ⚡ Phase 2 live trading ENABLED by user.")
    return jsonify({"ok": True, "enabled": True, "message": "Live trading enabled."})


@crypto_bp.route("/api/phase2/disable", methods=["POST"])
def api_phase2_disable():
    """Disable Phase 2 live trading (kill switch)."""
    set_phase2_enabled(False)
    logger.warning("[Routes] 🛑 Phase 2 live trading DISABLED by user.")
    return jsonify({"ok": True, "enabled": False, "message": "Live trading disabled."})
