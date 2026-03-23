# === Jarvis 4.0 — Trading Brain (Phase 2) ===
# 15-minute candles, EMA crossover signals.
# Paper trading always runs. Real trades require user approval.

import os
import json
import logging
import requests
from datetime import datetime, UTC
from collections import deque

logger = logging.getLogger("trading_brain")

# --- Config ---
PRICE_HISTORY_FILE  = "mcp_servers_hub/crypto_wallet_server/price_history.json"
TRADE_LOG_FILE      = "mcp_servers_hub/crypto_wallet_server/trade_signals.json"
SIGNAL_STATE_FILE   = "mcp_servers_hub/crypto_wallet_server/signal_state.json"

# EMA periods (15-min candles)
EMA_SHORT = 5    # 5 × 15min = 75 min fast EMA
EMA_LONG  = 20   # 20 × 15min = 5 hour slow EMA

# Minimum EMA separation to confirm a real crossover (filters noise/whipsaw)
# 0.1% means EMAs must be at least 0.1% apart — e.g. $0.00025 apart at $0.25 ADA
EMA_MIN_SEPARATION_PCT = 0.001

# Risk settings (Phase 2)
TRADE_SIZE_ADA  = 20.0   # 20 ADA per trade
STOP_LOSS_PCT   = 0.03   # 3% stop loss
TAKE_PROFIT_PCT = 0.05   # 5% take profit

# 15-minute candle interval
CANDLE_INTERVAL_SECONDS = 900  # 15 minutes

# In-memory price history (100 points = ~25 hours of 15-min candles)
_price_history: deque = deque(maxlen=100)

# Previous signal — track crossover changes
_last_signal_type: str = None


# ---------------------------------------------------------
# Price Feed
# ---------------------------------------------------------

def fetch_ada_price() -> float | None:
    """Fetch current ADA/USD price from CoinGecko free API."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids=cardano&vs_currencies=usd&include_24hr_change=true",
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            price = data["cardano"]["usd"]
            change_24h = data["cardano"].get("usd_24h_change", 0)
            return price, round(change_24h, 2)
    except Exception as e:
        logger.error(f"[Brain] Price fetch error: {e}")
    return None, None


# ---------------------------------------------------------
# Price History
# ---------------------------------------------------------

def load_price_history():
    """Load price history from disk into memory."""
    global _price_history
    if os.path.exists(PRICE_HISTORY_FILE):
        try:
            with open(PRICE_HISTORY_FILE) as f:
                data = json.load(f)
                _price_history = deque(data[-100:], maxlen=100)
        except Exception:
            _price_history = deque(maxlen=50)


def save_price_history():
    """Save price history to disk."""
    try:
        with open(PRICE_HISTORY_FILE, "w") as f:
            json.dump(list(_price_history), f, indent=2)
    except Exception as e:
        logger.error(f"[Brain] Save history error: {e}")


def should_record_price() -> bool:
    """Only record a new price every 15 minutes (candle interval)."""
    if not _price_history:
        return True
    last_ts = datetime.fromisoformat(_price_history[-1]["timestamp"])
    elapsed = (datetime.now(UTC) - last_ts).total_seconds()
    return elapsed >= CANDLE_INTERVAL_SECONDS


def record_price(price: float) -> bool:
    """Add a price point to history — respects 15-min candle interval."""
    if not should_record_price():
        return False
    _price_history.append({
        "price":     price,
        "timestamp": datetime.now(UTC).isoformat()
    })
    save_price_history()
    return True


# ---------------------------------------------------------
# EMA Calculation
# ---------------------------------------------------------

def calculate_ema(prices: list, period: int) -> float | None:
    """Calculate Exponential Moving Average."""
    if len(prices) < period:
        return None
    k = 2 / (period + 1)
    ema = prices[0]
    for price in prices[1:]:
        ema = price * k + ema * (1 - k)
    return round(ema, 6)


# ---------------------------------------------------------
# EMA State Persistence — survives Flask restarts
# ---------------------------------------------------------

def _load_signal_state() -> str | None:
    """Load last confirmed EMA state from disk (BUY / SELL / NEUTRAL)."""
    try:
        if os.path.exists(SIGNAL_STATE_FILE):
            with open(SIGNAL_STATE_FILE) as f:
                return json.load(f).get("last_ema_state")
    except Exception:
        pass
    return None


def _save_signal_state(state: str):
    """Persist current EMA state to disk so restarts don't cause false signals."""
    try:
        with open(SIGNAL_STATE_FILE, "w") as f:
            json.dump({
                "last_ema_state": state,
                "updated": datetime.now(UTC).isoformat()
            }, f)
    except Exception as e:
        logger.error(f"[Brain] Save state error: {e}")


# ---------------------------------------------------------
# Signal Engine
# ---------------------------------------------------------

def generate_signal() -> dict:
    """
    Analyze price history and generate a trade signal.
    Returns: BUY / SELL / HOLD with reasoning.
    BUY/SELL only fires on an actual EMA crossover (state change).
    HOLD is returned when EMAs stay in the same relationship as last candle.
    State is persisted to disk so Flask restarts don't cause false signals.
    """
    global _last_signal_type
    load_price_history()
    price, change_24h = fetch_ada_price()

    if price is None:
        return {"signal": "ERROR", "reason": "Could not fetch ADA price."}

    recorded = record_price(price)
    prices = [p["price"] for p in _price_history]

    ema_short = calculate_ema(prices, EMA_SHORT)
    ema_long  = calculate_ema(prices, EMA_LONG)

    # Not enough data yet — log only when a new candle was recorded
    if ema_short is None or ema_long is None:
        signal = {
            "signal":      "ACCUMULATING",
            "price":       price,
            "change_24h":  change_24h,
            "ema_short":   ema_short,
            "ema_long":    ema_long,
            "reason":      f"Building price history. Have {len(prices)}/{EMA_LONG} data points needed.",
            "would_trade": None,
            "timestamp":   datetime.now(UTC).isoformat()
        }
        if recorded:
            log_signal(signal)
        return signal

    # --- Determine current EMA state ---
    if ema_short > ema_long:
        current_ema_state = "BUY"
    elif ema_short < ema_long:
        current_ema_state = "SELL"
    else:
        current_ema_state = "NEUTRAL"

    # --- Load last known state from disk ---
    last_ema_state = _load_signal_state()

    # --- EMA separation check — filters noise/whipsaw crossovers ---
    # If EMAs are within 0.1% of each other the crossover is likely noise
    ema_separation_pct = abs(ema_short - ema_long) / ema_long if ema_long else 0
    has_separation = ema_separation_pct >= EMA_MIN_SEPARATION_PCT

    # --- Crossover detection ---
    # A crossover only fires when:
    #   1. State actually changed (not same direction as last candle)
    #   2. New state is BUY or SELL (not NEUTRAL)
    #   3. EMAs have meaningful separation (not just noise touching)
    is_crossover = (
        last_ema_state is not None and
        current_ema_state != last_ema_state and
        current_ema_state in ("BUY", "SELL") and
        has_separation
    )

    # Persist new state whenever it changes (or on first run)
    if current_ema_state != last_ema_state:
        _save_signal_state(current_ema_state)

    if is_crossover:
        signal_type = current_ema_state  # BUY or SELL
        _last_signal_type = signal_type
        if signal_type == "BUY":
            reason      = f"Fast EMA ({ema_short:.4f}) crossed above Slow EMA ({ema_long:.4f}) — bullish momentum."
            stop_loss   = round(price * (1 - STOP_LOSS_PCT), 4)
            take_profit = round(price * (1 + TAKE_PROFIT_PCT), 4)
        else:
            reason      = f"Fast EMA ({ema_short:.4f}) crossed below Slow EMA ({ema_long:.4f}) — bearish momentum."
            stop_loss   = round(price * (1 + STOP_LOSS_PCT), 4)
            take_profit = round(price * (1 - TAKE_PROFIT_PCT), 4)
        would_trade = {
            "action":      signal_type,
            "ada_amount":  TRADE_SIZE_ADA,
            "at_price":    price,
            "stop_loss":   stop_loss,
            "take_profit": take_profit,
        }
    else:
        signal_type = "HOLD"
        if current_ema_state == "BUY":
            direction = "above"
        elif current_ema_state == "SELL":
            direction = "below"
        else:
            direction = "equal to"
        reason      = f"No crossover — Fast EMA ({ema_short:.4f}) {direction} Slow EMA ({ema_long:.4f})."
        would_trade = None

    signal = {
        "signal":      signal_type,
        "price":       price,
        "change_24h":  change_24h,
        "ema_short":   ema_short,
        "ema_long":    ema_long,
        "reason":      reason,
        "would_trade": would_trade,
        "timestamp":   datetime.now(UTC).isoformat()
    }

    # Only log to file when a new candle was recorded — prevents manual
    # query spam from polluting the signal log
    if recorded:
        log_signal(signal)
        # Check open paper trades against new candle price
        try:
            from mcp_servers_hub.crypto_wallet_server.trade_tracker import update_paper_trades
            update_paper_trades(price)
        except Exception as e:
            logger.error(f"[Brain] Paper trade update error: {e}")

    # --- Phase 2: Request approval on actual crossover only ---
    if is_crossover and signal_type in ("BUY", "SELL"):
        try:
            from mcp_servers_hub.crypto_wallet_server.trade_approvals import (
                is_phase2_enabled, request_approval
            )
            if is_phase2_enabled() and would_trade:
                logger.warning(
                    f"[Brain] Crossover detected: {signal_type} "
                    f"— requesting trade approval."
                )
                request_approval(signal)
        except Exception as e:
            logger.error(f"[Brain] Approval request error: {e}")

        # Always open a paper trade on every crossover regardless of Phase 2 status
        try:
            from mcp_servers_hub.crypto_wallet_server.trade_tracker import open_paper_trade
            open_paper_trade(signal)
        except Exception as e:
            logger.error(f"[Brain] Paper trade open error: {e}")

    return signal


# ---------------------------------------------------------
# Signal Logger
# ---------------------------------------------------------

def log_signal(signal: dict):
    """Append signal to trade log file."""
    try:
        logs = []
        if os.path.exists(TRADE_LOG_FILE):
            with open(TRADE_LOG_FILE) as f:
                logs = json.load(f)
        logs.append(signal)
        # Keep last 200 signals
        logs = logs[-200:]
        with open(TRADE_LOG_FILE, "w") as f:
            json.dump(logs, f, indent=2)
    except Exception as e:
        logger.error(f"[Brain] Log error: {e}")


def get_recent_signals(count: int = 5) -> list:
    """Return the most recent N signals."""
    if not os.path.exists(TRADE_LOG_FILE):
        return []
    try:
        with open(TRADE_LOG_FILE) as f:
            logs = json.load(f)
        return logs[-count:]
    except Exception:
        return []


# ---------------------------------------------------------
# Background Candle Collector
# ---------------------------------------------------------

def _candle_loop():
    """Background thread — records a new candle every 15 minutes."""
    import time
    logger.info("[Brain] Candle collector started. Recording every 15 minutes.")
    while True:
        try:
            generate_signal()
        except Exception as e:
            logger.error(f"[Brain] Candle collector error: {e}")
        time.sleep(CANDLE_INTERVAL_SECONDS)


def start_candle_collector():
    """Start the background 15-minute candle collector thread."""
    import threading
    t = threading.Thread(target=_candle_loop, daemon=True)
    t.start()
    logger.info("[Brain] Background candle collector thread started.")


def get_performance_summary() -> dict:
    """Summarize would-have-been trade performance."""
    if not os.path.exists(TRADE_LOG_FILE):
        return {"error": "No signal data yet."}
    try:
        with open(TRADE_LOG_FILE) as f:
            logs = json.load(f)
        buys  = sum(1 for l in logs if l.get("signal") == "BUY")
        sells = sum(1 for l in logs if l.get("signal") == "SELL")
        holds = sum(1 for l in logs if l.get("signal") == "HOLD")
        total = len(logs)
        first = logs[0]["timestamp"][:10]  if logs else "N/A"
        last  = logs[-1]["timestamp"][:10] if logs else "N/A"
        return {
            "total_signals": total,
            "buy_signals":   buys,
            "sell_signals":  sells,
            "hold_signals":  holds,
            "tracking_since": first,
            "last_signal":    last
        }
    except Exception as e:
        return {"error": str(e)}
