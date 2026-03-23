# === Jarvis 4.0 — Trade Executor (Phase 2) ===
# Executes real ADA swaps via Minswap Aggregator API + PyCardano signing
# Minswap never holds funds — all settlement is on-chain

import logging
import requests
from mcp_servers_hub.crypto_wallet_server.crypto_wallet_server import load_wallet, get_wallet_address

logger = logging.getLogger("trade_executor")

# ---------------------------------------------------------
# Minswap Aggregator API
# ---------------------------------------------------------
MINSWAP_BASE = "https://agg-api.minswap.org/aggregator"

# Token IDs — ADA ↔ DJED (Cardano native stablecoin)
ADA_TOKEN  = "lovelace"
DJED_TOKEN = "8db269c3ec630e06ae29f74bc39edd1f87c819f1056206e879a1cd644a65644d6963726f555344"

# Slippage tolerance (0.5%)
SLIPPAGE = 0.5


# ---------------------------------------------------------
# Step 1 — Estimate
# ---------------------------------------------------------

def estimate_swap(ada_amount: float, action: str) -> dict:
    """
    Get swap estimate from Minswap.
    action = "SELL" → ADA to DJED (protect from downside)
    action = "BUY"  → DJED to ADA (re-enter position)
    """
    lovelace = int(ada_amount * 1_000_000)

    if action == "SELL":
        payload = {
            "amount":         str(lovelace),
            "token_in":       ADA_TOKEN,
            "token_out":      DJED_TOKEN,
            "slippage":       SLIPPAGE,
            "allow_multi_hops": True
        }
    else:  # BUY
        payload = {
            "amount":         str(lovelace),
            "token_in":       DJED_TOKEN,
            "token_out":      ADA_TOKEN,
            "slippage":       SLIPPAGE,
            "allow_multi_hops": True
        }

    try:
        r = requests.post(f"{MINSWAP_BASE}/estimate", json=payload, timeout=15)
        if r.status_code == 200:
            data = r.json()
            logger.info(f"[Executor] Estimate OK — {action} {ada_amount} ADA: {data}")
            return {"ok": True, "estimate": data}
        else:
            logger.error(f"[Executor] Estimate failed {r.status_code}: {r.text}")
            return {"ok": False, "error": f"Estimate failed: {r.status_code}"}
    except Exception as e:
        logger.error(f"[Executor] Estimate error: {e}")
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------
# Step 2 — Build Transaction
# ---------------------------------------------------------

def build_swap_tx(action: str, estimate: dict) -> dict:
    """Build unsigned swap CBOR via Minswap."""
    address = get_wallet_address()
    if not address:
        return {"ok": False, "error": "No wallet address found."}

    payload = {
        "sender":         address,
        "min_amount_out": estimate.get("min_amount_out", "0"),
        "estimate":       estimate
    }

    try:
        r = requests.post(f"{MINSWAP_BASE}/build-tx", json=payload, timeout=15)
        if r.status_code == 200:
            data = r.json()
            cbor_hex = data.get("cbor", "")
            logger.info(f"[Executor] TX built — CBOR length: {len(cbor_hex)}")
            return {"ok": True, "cbor": cbor_hex, "build_data": data}
        else:
            logger.error(f"[Executor] Build TX failed {r.status_code}: {r.text}")
            return {"ok": False, "error": f"Build TX failed: {r.status_code}"}
    except Exception as e:
        logger.error(f"[Executor] Build TX error: {e}")
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------
# Step 3 — Sign Transaction with PyCardano
# ---------------------------------------------------------

def sign_tx(cbor_hex: str) -> dict:
    """Sign the unsigned CBOR transaction with Jarvis's wallet key."""
    try:
        from pycardano import (
            PaymentSigningKey, PaymentVerificationKey,
            Transaction, TransactionWitnessSet, VerificationKeyWitness
        )

        # Load wallet seed
        wallet = load_wallet()
        if not wallet:
            return {"ok": False, "error": "Wallet seed not found."}

        seed_hex  = wallet["mnemonic"]  # stored as hex string
        seed_bytes = bytes.fromhex(seed_hex)

        # Reconstruct signing key
        signing_key   = PaymentSigningKey.from_primitive(seed_bytes)
        verification_key = PaymentVerificationKey.from_signing_key(signing_key)

        # Parse the unsigned transaction
        tx = Transaction.from_cbor(cbor_hex)

        # Sign the transaction body hash
        signature = signing_key.sign(tx.transaction_body.hash())

        # Build witness set
        witness     = VerificationKeyWitness(verification_key, signature)
        witness_set = TransactionWitnessSet(vkey_witnesses=[witness])
        witness_hex = witness_set.to_cbor_hex()

        logger.info(f"[Executor] TX signed successfully.")
        return {"ok": True, "witness_hex": witness_hex}

    except ImportError:
        return {"ok": False, "error": "PyCardano not installed."}
    except Exception as e:
        logger.error(f"[Executor] Signing error: {e}")
        return {"ok": False, "error": f"Signing failed: {e}"}


# ---------------------------------------------------------
# Step 4 — Submit Transaction
# ---------------------------------------------------------

def submit_tx(cbor_hex: str, witness_hex: str) -> dict:
    """Submit the signed transaction to Minswap for on-chain execution."""
    payload = {
        "txCbor":     cbor_hex,
        "signatures": witness_hex
    }

    try:
        r = requests.post(f"{MINSWAP_BASE}/finalize-and-submit-tx", json=payload, timeout=30)
        if r.status_code == 200:
            data   = r.json()
            tx_id  = data.get("txId") or data.get("tx_id") or data.get("hash", "unknown")
            logger.info(f"[Executor] TX submitted! TX ID: {tx_id}")
            return {"ok": True, "tx_id": tx_id, "data": data}
        else:
            logger.error(f"[Executor] Submit failed {r.status_code}: {r.text}")
            return {"ok": False, "error": f"Submit failed: {r.status_code} — {r.text}"}
    except Exception as e:
        logger.error(f"[Executor] Submit error: {e}")
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------
# Full Trade Flow
# ---------------------------------------------------------

def execute_trade(action: str, ada_amount: float) -> dict:
    """
    Full trade execution flow:
    1. Estimate → 2. Build TX → 3. Sign → 4. Submit
    Returns result with tx_id on success.
    """
    logger.info(f"[Executor] Starting {action} trade — {ada_amount} ADA")

    # Step 1 — Estimate
    est_result = estimate_swap(ada_amount, action)
    if not est_result["ok"]:
        return {"ok": False, "step": "estimate", "error": est_result["error"]}

    # Step 2 — Build TX
    build_result = build_swap_tx(action, est_result["estimate"])
    if not build_result["ok"]:
        return {"ok": False, "step": "build", "error": build_result["error"]}

    # Step 3 — Sign
    sign_result = sign_tx(build_result["cbor"])
    if not sign_result["ok"]:
        return {"ok": False, "step": "sign", "error": sign_result["error"]}

    # Step 4 — Submit
    submit_result = submit_tx(build_result["cbor"], sign_result["witness_hex"])
    if not submit_result["ok"]:
        return {"ok": False, "step": "submit", "error": submit_result["error"]}

    logger.info(f"[Executor] Trade complete! TX: {submit_result['tx_id']}")
    return {
        "ok":     True,
        "action": action,
        "amount": ada_amount,
        "tx_id":  submit_result["tx_id"]
    }
