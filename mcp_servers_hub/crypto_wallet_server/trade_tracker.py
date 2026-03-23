# === Jarvis 4.0 — Paper Trade Tracker ===
# Opens a simulated paper trade on every BUY/SELL crossover signal.
# Evaluates open trades on each candle — closes them when TP or SL is hit.
# Tracks win rate, P&L, and trade history for strategy evaluation.

import os
import json
import logging
from datetime import datetime, UTC

logger = logging.getLogger("trade_tracker")

PAPER_TRADES_FILE = "mcp_servers_hub/crypto_wallet_server/paper_trades.json"


def _load_trades() -> dict:
    """Load paper trades from disk. Returns {open: [...], closed: [...]}"""
    if os.path.exists(PAPER_TRADES_FILE):
        try:
            with open(PAPER_TRADES_FILE) as f:
                data = json.load(f)
                data.setdefault("open", [])
                data.setdefault("closed", [])
                return data
        except Exception:
            pass
    return {"open": [], "closed": []}


def _save_trades(data: dict):
    """Save paper trades to disk."""
    try:
        with open(PAPER_TRADES_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"[Tracker] Save error: {e}")


def open_paper_trade(signal: dict):
    """
    Open a new paper trade when a BUY or SELL crossover fires.
    If an opposing trade is already open, close it at current price first
    before opening the new trade — prevents stacking conflicting positions.
    signal must have: signal, price, would_trade (stop_loss, take_profit, ada_amount, at_price)
    """
    wt = signal.get("would_trade")
    if not wt:
        return

    data        = _load_trades()
    new_dir     = signal["signal"]       # BUY or SELL
    curr_price  = wt["at_price"]

    # --- Close any opposing open trades before opening new position ---
    still_open = []
    for trade in data["open"]:
        if trade["direction"] != new_dir:
            # Signal reversed — close this trade at current price
            entry      = trade["entry_price"]
            ada_amount = trade["ada_amount"]

            if trade["direction"] == "BUY":
                pnl     = round((curr_price - entry) * ada_amount, 4)
                outcome = "WIN" if curr_price > entry else "LOSS"
            else:  # SELL
                pnl     = round((entry - curr_price) * ada_amount, 4)
                outcome = "WIN" if curr_price < entry else "LOSS"

            trade["status"]       = "CLOSED"
            trade["outcome"]      = outcome
            trade["exit_price"]   = curr_price
            trade["closed_at"]    = datetime.now(UTC).isoformat()
            trade["pnl_usd"]      = pnl
            trade["close_reason"] = "SIGNAL_REVERSED"

            data["closed"].append(trade)
            logger.info(
                f"[Tracker] Trade reversed: {trade['direction']} "
                f"entry=${entry} exit=${curr_price} → {outcome} ${pnl:+.4f}"
            )
        else:
            still_open.append(trade)

    data["open"] = still_open

    # --- Open the new trade ---
    trade = {
        "id":          f"pt_{int(datetime.now(UTC).timestamp())}",
        "direction":   new_dir,
        "entry_price": curr_price,
        "stop_loss":   wt["stop_loss"],
        "take_profit": wt["take_profit"],
        "ada_amount":  wt["ada_amount"],
        "opened_at":   datetime.now(UTC).isoformat(),
        "status":      "OPEN"
    }

    data["open"].append(trade)
    _save_trades(data)
    logger.info(f"[Tracker] Paper trade opened: {trade['direction']} @ ${trade['entry_price']}")


def update_paper_trades(current_price: float):
    """
    Check all open paper trades against current price.
    Closes any trade that has hit take profit or stop loss.
    """
    data = _load_trades()
    if not data["open"]:
        return

    still_open = []
    for trade in data["open"]:
        direction   = trade["direction"]
        entry       = trade["entry_price"]
        stop_loss   = trade["stop_loss"]
        take_profit = trade["take_profit"]
        ada_amount  = trade["ada_amount"]

        outcome    = None
        exit_price = None

        if direction == "BUY":
            # Profit if price rises to TP, loss if price falls to SL
            if current_price >= take_profit:
                outcome    = "WIN"
                exit_price = take_profit
            elif current_price <= stop_loss:
                outcome    = "LOSS"
                exit_price = stop_loss
        else:  # SELL
            # Profit if price drops to TP, loss if price rises to SL
            if current_price <= take_profit:
                outcome    = "WIN"
                exit_price = take_profit
            elif current_price >= stop_loss:
                outcome    = "LOSS"
                exit_price = stop_loss

        if outcome:
            if direction == "BUY":
                pnl = round((exit_price - entry) * ada_amount, 4)
            else:
                pnl = round((entry - exit_price) * ada_amount, 4)

            trade["status"]     = "CLOSED"
            trade["outcome"]    = outcome
            trade["exit_price"] = exit_price
            trade["closed_at"]  = datetime.now(UTC).isoformat()
            trade["pnl_usd"]    = pnl

            data["closed"].append(trade)
            logger.info(
                f"[Tracker] Paper trade CLOSED: {direction} "
                f"entry=${entry} exit=${exit_price} → {outcome} ${pnl:+.4f}"
            )
        else:
            still_open.append(trade)

    data["open"] = still_open
    # Keep last 100 closed trades
    data["closed"] = data["closed"][-100:]
    _save_trades(data)


def get_paper_performance() -> dict:
    """Return paper trading performance summary with open and closed trade lists."""
    data = _load_trades()
    closed      = data["closed"]
    open_trades = data["open"]

    if not closed and not open_trades:
        return {"message": "No paper trades yet — waiting for first crossover signal."}

    wins         = [t for t in closed if t.get("outcome") == "WIN"]
    losses       = [t for t in closed if t.get("outcome") == "LOSS"]
    total_closed = len(closed)
    win_rate     = round((len(wins) / total_closed * 100), 1) if total_closed else 0
    total_pnl    = round(sum(t.get("pnl_usd", 0) for t in closed), 4)

    return {
        "open_trades":   len(open_trades),
        "closed_trades": total_closed,
        "wins":          len(wins),
        "losses":        len(losses),
        "win_rate_pct":  win_rate,
        "total_pnl_usd": total_pnl,
        "open":          open_trades,
        "closed":        list(reversed(closed[-20:]))  # most recent first
    }


def get_open_paper_trades() -> list:
    """Return currently open paper trades."""
    return _load_trades()["open"]


def get_closed_paper_trades(count: int = 20) -> list:
    """Return last N closed paper trades, most recent first."""
    closed = _load_trades()["closed"]
    return list(reversed(closed[-count:]))
