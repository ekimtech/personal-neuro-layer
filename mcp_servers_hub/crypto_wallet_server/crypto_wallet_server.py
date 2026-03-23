# === Jarvis 4.0 — Crypto Wallet MCP Organ ===
# Cardano wallet generation, balance checking, transaction history
# Uses Blockfrost API + PyCardano

import os
import json
import logging
import requests
from mcp_servers_hub.crypto_wallet_server.wallet_config import (
    BLOCKFROST_PROJECT_ID, BLOCKFROST_BASE_URL,
    JARVIS_WALLET_ADDRESS, WALLET_SEED_FILE
)

logger = logging.getLogger("crypto_wallet")

HEADERS = {"project_id": BLOCKFROST_PROJECT_ID}


# ---------------------------------------------------------
# Blockfrost API Helpers
# ---------------------------------------------------------

def _get(endpoint: str) -> dict | list | None:
    """GET request to Blockfrost API."""
    try:
        url = f"{BLOCKFROST_BASE_URL}{endpoint}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 404:
            return None
        else:
            logger.error(f"[Wallet] Blockfrost error {r.status_code}: {r.text}")
            return None
    except Exception as e:
        logger.error(f"[Wallet] Request error: {e}")
        return None


# ---------------------------------------------------------
# Wallet Generation
# ---------------------------------------------------------

def generate_wallet() -> dict:
    """Generate a new Cardano wallet using PyCardano and save seed."""
    try:
        import os
        from pycardano import PaymentSigningKey, PaymentVerificationKey, Address, Network

        # Generate a random 32-byte seed and derive keys
        seed = os.urandom(32)
        signing_key      = PaymentSigningKey.from_primitive(seed)
        verification_key = PaymentVerificationKey.from_signing_key(signing_key)
        address          = Address(payment_part=verification_key.hash(), network=Network.MAINNET)
        mnemonic         = seed.hex()  # Store seed as hex for recovery

        wallet_data = {
            "mnemonic": mnemonic,
            "address":  str(address),
            "network":  "mainnet"
        }

        # Save seed file
        os.makedirs(os.path.dirname(WALLET_SEED_FILE), exist_ok=True)
        with open(WALLET_SEED_FILE, "w") as f:
            json.dump(wallet_data, f, indent=2)

        logger.info(f"[Wallet] New wallet generated: {address}")
        return {"address": str(address), "mnemonic": mnemonic}

    except ImportError:
        return {"error": "PyCardano not installed. Run: pip install pycardano"}
    except Exception as e:
        logger.error(f"[Wallet] Generation error: {e}")
        return {"error": str(e)}


def load_wallet() -> dict | None:
    """Load wallet from seed file."""
    if os.path.exists(WALLET_SEED_FILE):
        with open(WALLET_SEED_FILE) as f:
            return json.load(f)
    return None


def get_wallet_address() -> str | None:
    """Return Jarvis's wallet address from config or seed file."""
    if JARVIS_WALLET_ADDRESS:
        return JARVIS_WALLET_ADDRESS
    wallet = load_wallet()
    return wallet["address"] if wallet else None


# ---------------------------------------------------------
# Balance & Info
# ---------------------------------------------------------

def get_balance(address: str = None) -> dict:
    """Get ADA balance for Jarvis's wallet."""
    addr = address or get_wallet_address()
    if not addr:
        return {"error": "No wallet address configured. Generate a wallet first."}

    data = _get(f"/addresses/{addr}")
    if not data:
        return {"error": "Address not found or no transactions yet."}

    lovelace = next(
        (int(a["quantity"]) for a in data.get("amount", []) if a["unit"] == "lovelace"),
        0
    )
    ada = lovelace / 1_000_000

    # Get any native tokens
    tokens = [
        {"unit": a["unit"], "quantity": a["quantity"]}
        for a in data.get("amount", [])
        if a["unit"] != "lovelace"
    ]

    return {
        "address": addr,
        "ada":     round(ada, 6),
        "lovelace": lovelace,
        "tokens":  tokens
    }


def get_transactions(address: str = None, count: int = 5) -> list:
    """Get recent transactions for Jarvis's wallet."""
    addr = address or get_wallet_address()
    if not addr:
        return []

    data = _get(f"/addresses/{addr}/transactions?count={count}&order=desc")
    return data if data else []


def get_ada_price() -> tuple:
    """Get current ADA/USD price from CoinGecko. Returns (price, change_24h)."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids=cardano&vs_currencies=usd&include_24hr_change=true",
            timeout=10
        )
        if r.status_code == 200:
            data = r.json().get("cardano", {})
            return data.get("usd", None), round(data.get("usd_24h_change", 0), 2)
    except Exception as e:
        logger.error(f"[Wallet] Price fetch error: {e}")
    return None, None


# ---------------------------------------------------------
# MCP handle()
# ---------------------------------------------------------

def handle(user_input: str) -> dict:
    text = user_input.lower().strip()

    # Generate wallet
    if any(k in text for k in ["generate wallet", "create wallet", "new wallet", "setup wallet"]):
        existing = load_wallet()
        if existing:
            return {"data": f"Jarvis already has a wallet at address: {existing['address']}"}
        result = generate_wallet()
        if "error" in result:
            return {"data": f"Wallet generation failed: {result['error']}"}
        return {"data": (
            f"Jarvis's new Cardano wallet has been created.\n"
            f"Address: {result['address']}\n"
            f"IMPORTANT: Your seed phrase has been saved securely. "
            f"Fund the wallet by sending ADA to the address above."
        )}

    # Show wallet address
    if any(k in text for k in ["wallet address", "my address", "jarvis address", "show address"]):
        addr = get_wallet_address()
        if not addr:
            return {"data": "No wallet found. Say 'generate wallet' to create one."}
        return {"data": f"Jarvis's wallet address: {addr}"}

    # Check balance
    if any(k in text for k in ["balance", "how much ada", "check wallet", "wallet balance", "how much do i have"]):
        result = get_balance()
        if "error" in result:
            return {"data": result["error"]}
        msg = f"Jarvis Wallet Balance: {result['ada']} ADA"
        if result["tokens"]:
            msg += f" plus {len(result['tokens'])} native token(s)."
        return {"data": msg}

    # Transaction history
    if any(k in text for k in ["transactions", "transaction history", "recent transactions", "wallet history"]):
        txs = get_transactions()
        if not txs:
            return {"data": "No transactions found yet or wallet not funded."}
        lines = [f"Last {len(txs)} transactions:"]
        for tx in txs:
            lines.append(f"- TX: {tx.get('tx_hash', '')[:20]}... Block: {tx.get('block_height', 'unknown')}")
        return {"data": "\n".join(lines)}

    # ADA price
    if any(k in text for k in ["ada price", "cardano price", "price of ada", "price of cardano", "what is ada"]):
        price, change_24h = get_ada_price()
        if price:
            return {"data": f"Current ADA price: ${price} USD ({change_24h:+.2f}% 24h)"}
        return {"data": "Could not fetch ADA price right now."}

    # Trading signals
    if any(k in text for k in [
        "what would you trade", "trade signal", "check signal", "should i buy",
        "should i sell", "trading signal", "jarvis trade", "what would jarvis trade"
    ]):
        from mcp_servers_hub.crypto_wallet_server.trading_brain import generate_signal
        signal = generate_signal()
        if signal.get("signal") == "ERROR":
            return {"data": signal["reason"]}
        msg = (
            f"Trading Signal: {signal['signal']}\n"
            f"ADA Price: ${signal['price']} USD ({signal.get('change_24h', 0):+.2f}% 24h)\n"
            f"Reason: {signal['reason']}"
        )
        if signal.get("would_trade"):
            t = signal["would_trade"]
            msg += (
                f"\nWould {t['action']} {t['ada_amount']} ADA at ${t['at_price']}"
                f" | Stop Loss: ${t['stop_loss']} | Take Profit: ${t['take_profit']}"
            )
        return {"data": msg}

    # Performance summary
    if any(k in text for k in [
        "jarvis performance", "trading performance", "how is jarvis trading",
        "signal history", "trade history"
    ]):
        from mcp_servers_hub.crypto_wallet_server.trading_brain import get_performance_summary, get_recent_signals
        perf = get_performance_summary()
        if "error" in perf:
            return {"data": perf["error"]}
        recent = get_recent_signals(3)
        msg = (
            f"Trading Performance since {perf['tracking_since']}:\n"
            f"Total Signals: {perf['total_signals']} "
            f"| Buy: {perf['buy_signals']} | Sell: {perf['sell_signals']} | Hold: {perf['hold_signals']}\n"
        )
        if recent:
            msg += "Recent signals:\n"
            for s in reversed(recent):
                msg += f"- {s['signal']} @ ${s['price']} — {s['timestamp'][:10]}\n"
        return {"data": msg}

    # Paper trading performance
    if any(k in text for k in [
        "paper trading", "paper trade", "paper performance",
        "how are my trades doing", "how are trades doing",
        "paper trade performance", "simulated trading", "paper results"
    ]):
        from mcp_servers_hub.crypto_wallet_server.trade_tracker import get_paper_performance
        perf = get_paper_performance()
        if "message" in perf:
            return {"data": perf["message"]}
        pnl_sign = "+" if perf["total_pnl_usd"] >= 0 else ""
        msg = (
            f"Paper Trading Performance:\n"
            f"Open Trades: {perf['open_trades']} | Closed: {perf['closed_trades']}\n"
            f"Wins: {perf['wins']} | Losses: {perf['losses']} | Win Rate: {perf['win_rate_pct']}%\n"
            f"Total P&L: {pnl_sign}${perf['total_pnl_usd']} USD"
        )
        if perf.get("open"):
            msg += "\n\nOpen Trades:"
            for t in perf["open"]:
                msg += f"\n  {t['direction']} @ ${t['entry_price']} | TP: ${t['take_profit']} | SL: ${t['stop_loss']}"
        if perf.get("closed"):
            msg += "\n\nLast 5 Closed:"
            for t in perf["closed"][:5]:
                icon = "✅" if t["outcome"] == "WIN" else "❌"
                msg += f"\n  {icon} {t['direction']} ${t['entry_price']} → ${t['exit_price']} (${t['pnl_usd']:+.4f})"
        return {"data": msg}

    # Phase 2 — approve trade via chat
    if any(k in text for k in ["approve trade", "yes trade", "execute trade", "confirm trade"]):
        from mcp_servers_hub.crypto_wallet_server.trade_approvals import get_pending_approvals, approve_trade
        pending = get_pending_approvals()
        if not pending:
            return {"data": "No pending trade approvals right now."}
        a = pending[0]
        result = approve_trade(a["id"])
        if result["ok"]:
            return {"data": f"Trade approved and executed! TX ID: {result['tx_id']}"}
        return {"data": f"Trade execution failed: {result.get('error', 'Unknown error')}"}

    # Phase 2 — reject trade via chat
    if any(k in text for k in ["reject trade", "cancel trade", "no trade", "skip trade"]):
        from mcp_servers_hub.crypto_wallet_server.trade_approvals import get_pending_approvals, reject_trade
        pending = get_pending_approvals()
        if not pending:
            return {"data": "No pending trade approvals to reject."}
        a = pending[0]
        reject_trade(a["id"])
        return {"data": f"Trade rejected. No real transaction executed."}

    # Phase 2 — status
    if any(k in text for k in ["phase 2", "live trading status", "trading mode", "is jarvis trading"]):
        from mcp_servers_hub.crypto_wallet_server.trade_approvals import is_phase2_enabled, get_pending_approvals
        enabled = is_phase2_enabled()
        pending = get_pending_approvals()
        status  = "ENABLED — live trades require your approval." if enabled else "DISABLED — paper trading only."
        msg = f"Phase 2 live trading: {status}"
        if pending:
            p = pending[0]
            msg += f"\n⏳ Pending approval: {p['action']} {p['ada_amount']} ADA @ ${p['price']}"
        return {"data": msg}

    # Manual sell/buy — "sell 20 ada", "buy 15 ada", "manual sell", "force sell 30"
    import re as _re
    manual_sell = any(k in text for k in ["manual sell", "sell ada", "sell now", "force sell", "jarvis sell"])
    manual_buy  = any(k in text for k in ["manual buy", "buy ada", "buy now", "force buy", "jarvis buy"])

    if manual_sell or manual_buy:
        from datetime import datetime, UTC
        from mcp_servers_hub.crypto_wallet_server.trade_approvals import is_phase2_enabled, request_approval
        from mcp_servers_hub.crypto_wallet_server.trading_brain import TRADE_SIZE_ADA

        action = "SELL" if manual_sell else "BUY"

        # Phase 2 must be enabled for real trades
        if not is_phase2_enabled():
            return {"data": "Phase 2 is disabled. Enable it from the crypto dashboard before placing manual trades."}

        # Parse amount — e.g. "sell 30 ada" → 30.0
        amount_match = _re.search(r'(\d+\.?\d*)', text)
        ada_amount   = float(amount_match.group(1)) if amount_match else TRADE_SIZE_ADA

        # Balance check with clear user feedback
        balance = get_balance()
        if "error" in balance:
            return {"data": f"Could not check wallet balance: {balance['error']}"}

        DJED_TOKEN = "8db269c3ec630e06ae29f74bc39edd1f87c819f1056206e879a1cd644a65644d6963726f555344"

        if action == "SELL":
            if balance.get("ada", 0) < ada_amount:
                return {"data": (
                    f"Not enough ADA for that trade. "
                    f"You have {balance['ada']:.2f} ADA, trade requires {ada_amount} ADA."
                )}
        else:  # BUY
            djed_qty = next(
                (int(t["quantity"]) for t in balance.get("tokens", []) if t["unit"] == DJED_TOKEN), 0
            )
            if djed_qty <= 0:
                return {"data": "No DJED in wallet for a BUY trade. Complete a SELL first to get DJED."}

        # Get current price
        price, change_24h = get_ada_price()
        if not price:
            return {"data": "Could not fetch ADA price right now. Try again in a moment."}

        # Build manual signal dict
        signal = {
            "signal":      action,
            "price":       price,
            "change_24h":  change_24h,
            "ema_short":   None,
            "ema_long":    None,
            "reason":      f"Manual {action} requested by user — {ada_amount} ADA @ ${price}",
            "would_trade": {
                "action":      action,
                "ada_amount":  ada_amount,
                "at_price":    price,
                "stop_loss":   round(price * (0.97 if action == "SELL" else 1.03), 4),
                "take_profit": round(price * (1.05 if action == "SELL" else 0.95), 4),
            },
            "timestamp": datetime.now(UTC).isoformat()
        }

        result = request_approval(signal)
        if result["ok"]:
            return {"data": (
                f"Manual {action} queued — {ada_amount} ADA at ${price}.\n"
                f"Check the crypto dashboard to approve or reject.\n"
                f"Trade expires in 15 minutes."
            )}
        return {"data": f"Could not queue trade: {result.get('reason', 'Unknown error')}"}

    return {"data": "Crypto wallet commands: 'generate wallet', 'wallet balance', 'wallet address', 'ada price', 'transaction history', 'what would you trade', 'jarvis performance', 'approve trade', 'reject trade', 'phase 2 status', 'sell 20 ada', 'buy 15 ada'."}
