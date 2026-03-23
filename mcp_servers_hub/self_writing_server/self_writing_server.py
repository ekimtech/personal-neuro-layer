# === Self-Writing Tools Organ — self_writing_server.py ===
# Allows Jarvis to review his own code, propose improvements,
# and write changes after user approval.
# Built: 03-19-26

import os
import uuid
import json
import logging
import threading
import requests
from datetime import datetime

logger = logging.getLogger("self_writing_server")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _ch = logging.StreamHandler()
    _ch.setFormatter(logging.Formatter("[SelfWrite] %(message)s"))
    logger.addHandler(_ch)

# ---------------------------------------------------------
# LM Studio config (matches app.py / cognition.py)
# ---------------------------------------------------------
LMSTUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
LMSTUDIO_MODEL = "qwen2.5-14b-instruct-1m"

# ---------------------------------------------------------
# Base path for the Jarvis project
# ---------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(_HERE))   # Jarvis4.0/

# ---------------------------------------------------------
# File Registry — friendly name → relative path from BASE_DIR
# ---------------------------------------------------------
FILE_REGISTRY = {
    "home assistant server": "mcp_servers_hub/home_assistant_server/home_assistant_server.py",
    "home assistant":        "mcp_servers_hub/home_assistant_server/home_assistant_server.py",
    "ha config":             "mcp_servers_hub/home_assistant_server/ha_config.py",
    "mcp router":            "mcp_servers_hub/mcp_router_hub.py",
    "router hub":            "mcp_servers_hub/mcp_router_hub.py",
    "router":                "mcp_servers_hub/mcp_router_hub.py",
    "cognition":             "model_injection/cognition.py",
    "cognition server":      "model_injection/cognition.py",
    "email server":          "mcp_servers_hub/email_server/server.py",
    "documents server":      "mcp_servers_hub/documents_server/server.py",
    "documents routes":      "mcp_servers_hub/documents_server/routes.py",
    "weather server":        "mcp_servers_hub/weather_server/server.py",
    "internet server":       "mcp_servers_hub/internet_server/server.py",
    "memory server":         "mcp_servers_hub/memory_servers/jsonl_server/jsonl_memory_server.py",
    "jsonl memory":          "mcp_servers_hub/memory_servers/jsonl_server/jsonl_memory_server.py",
    "qnap server":           "mcp_servers_hub/qnap_server/qnap_server.py",
    "qnap":                  "mcp_servers_hub/qnap_server/qnap_server.py",
    "mikrotik server":       "mcp_servers_hub/mikrotik_server/mikrotik_server.py",
    "mikrotik":              "mcp_servers_hub/mikrotik_server/mikrotik_server.py",
    "jarvis routes":         "jarvis_routes.py",
    "routes":                "jarvis_routes.py",
    "app":                   "app.py",
    "tts server":            "mcp_servers_hub/tts_server/server.py",
    "stt server":            "mcp_servers_hub/stt_server/stt_server.py",
    "wake word":             "mcp_servers_hub/stt_server/wake_word_listener.py",
    "games server":          "mcp_servers_hub/games_server/games_server.py",
    "games":                 "mcp_servers_hub/games_server/games_server.py",
    "script runner":         "mcp_servers_hub/script_runner_server/script_runner_server.py",
    "script runner server":  "mcp_servers_hub/script_runner_server/script_runner_server.py",
    "self writing server":   "mcp_servers_hub/self_writing_server/self_writing_server.py",
    "self writing":          "mcp_servers_hub/self_writing_server/self_writing_server.py",
    "security server":       "mcp_servers_hub/login_security/security.py",
    "security":              "mcp_servers_hub/login_security/security.py",
    "crypto wallet server":  "mcp_servers_hub/crypto_wallet_server/crypto_wallet_server.py",
    "crypto wallet":         "mcp_servers_hub/crypto_wallet_server/crypto_wallet_server.py",
    "trading brain":         "mcp_servers_hub/crypto_wallet_server/trading_brain.py",
    "trade approvals":       "mcp_servers_hub/crypto_wallet_server/trade_approvals.py",
    "trade executor":        "mcp_servers_hub/crypto_wallet_server/trade_executor.py",
}

# ---------------------------------------------------------
# Pending Reviews — in-memory store
# id → { id, file_name, rel_path, abs_path, original,
#          suggested, explanation, issues, timestamp }
# ---------------------------------------------------------
_pending_reviews: dict = {}

# ---------------------------------------------------------
# Async Review Jobs — { job_id: { status, error, review_id } }
# status: "pending" | "running" | "done" | "error"
# ---------------------------------------------------------
_review_jobs: dict = {}


def get_pending_reviews() -> list:
    """Return all pending reviews as a list (newest first)."""
    return sorted(_pending_reviews.values(), key=lambda r: r["timestamp"], reverse=True)


def get_review(review_id: str) -> dict | None:
    return _pending_reviews.get(review_id)


def remove_review(review_id: str) -> bool:
    if review_id in _pending_reviews:
        del _pending_reviews[review_id]
        return True
    return False


def clear_all_reviews():
    _pending_reviews.clear()


# ---------------------------------------------------------
# LLM Code Review — two system prompts based on file size
# ---------------------------------------------------------

# For small files (≤ 300 lines): full file rewrite
_REVIEW_SYSTEM_FULL = """You are an expert Python code reviewer embedded inside Jarvis 4.0,
a personal AI assistant built with Flask, modular MCP organ architecture, and LM Studio.

Your job is to review a Python file and suggest concrete, safe improvements.
Focus on: bugs, error handling, clarity, efficiency, and adherence to the project's organ pattern.

Respond in this EXACT format (use these exact delimiter lines):

EXPLANATION:
<2-4 sentence summary of what you found and changed>

ISSUES:
- <issue 1>
- <issue 2>
- <issue 3>

SUGGESTED_CODE:
<full improved python file — complete, runnable, nothing omitted>

Rules:
- Always output the complete file in SUGGESTED_CODE, never truncated
- Keep the same function signatures and imports unless there is a clear bug
- Do not add unnecessary complexity
- If the file is already clean, say so in EXPLANATION and repeat the original code in SUGGESTED_CODE
"""

# For large files (> 300 lines): issues + changed functions only
_REVIEW_SYSTEM_LARGE = """You are an expert Python code reviewer embedded inside Jarvis 4.0,
a personal AI assistant built with Flask, modular MCP organ architecture, and LM Studio.

This is a LARGE file. Your job is to identify issues and show ONLY the specific functions
or sections that need changing — do NOT output the entire file.

Respond in this EXACT format (use these exact delimiter lines):

EXPLANATION:
<2-4 sentence summary of what you found>

ISSUES:
- <issue 1>
- <issue 2>
- <issue 3>

SUGGESTED_CODE:
# === PATCH MODE — only changed functions shown ===
# Replace each function below in the original file.

def function_name_that_needs_changing(...):
    <improved function body>

# Add more changed functions below if needed

Rules:
- Only include functions/sections that actually need changing
- Keep unchanged code as-is — do not repeat it
- Keep the same function signatures unless there is a clear bug
- If the file is already clean, say so in EXPLANATION and write: # No changes needed
"""

LARGE_FILE_THRESHOLD = 300  # lines


def _call_lmstudio(system_prompt: str, user_prompt: str) -> tuple[str, str]:
    """
    Direct LM Studio call, bypassing Flask context.
    Returns (response_text, error_message) — one will be empty.
    """
    payload = {
        "model": LMSTUDIO_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 16384,
    }
    try:
        resp = requests.post(LMSTUDIO_URL, json=payload, timeout=300)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"], ""
    except requests.exceptions.ConnectionError:
        err = "Cannot connect to LM Studio at 127.0.0.1:1234 — is it running?"
        logger.error(f"[SelfWrite] {err}")
        return "", err
    except requests.exceptions.Timeout:
        err = "LM Studio timed out (300s) — file may be too large or model is busy."
        logger.error(f"[SelfWrite] {err}")
        return "", err
    except Exception as e:
        err = f"LM Studio error: {e}"
        logger.error(f"[SelfWrite] {err}")
        return "", err


def _parse_review_response(raw: str) -> tuple[str, list, str]:
    """Parse LLM response into (explanation, issues_list, suggested_code)."""
    explanation = ""
    issues = []
    suggested_code = ""

    try:
        if "EXPLANATION:" in raw:
            after_exp = raw.split("EXPLANATION:", 1)[1]
            explanation = after_exp.split("ISSUES:")[0].strip() if "ISSUES:" in after_exp else after_exp.strip()

        if "ISSUES:" in raw:
            after_issues = raw.split("ISSUES:", 1)[1]
            issues_block = after_issues.split("SUGGESTED_CODE:")[0] if "SUGGESTED_CODE:" in after_issues else after_issues
            for line in issues_block.splitlines():
                line = line.strip().lstrip("- ").strip()
                if line:
                    issues.append(line)

        if "SUGGESTED_CODE:" in raw:
            code_block = raw.split("SUGGESTED_CODE:", 1)[1].strip()
            # Strip markdown code fences if present
            if code_block.startswith("```"):
                code_block = code_block.split("\n", 1)[1] if "\n" in code_block else code_block
                if code_block.endswith("```"):
                    code_block = code_block[:-3]
            suggested_code = code_block.strip()

    except Exception as e:
        logger.error(f"[SelfWrite] Parse error: {e}")

    return explanation, issues, suggested_code


def review_file(friendly_name: str) -> dict:
    """
    Read a file, send to LLM for review, store pending review.
    Returns a summary dict with review_id.
    """
    # Resolve file path
    key = friendly_name.lower().strip()
    rel_path = None
    for registry_key, registry_path in FILE_REGISTRY.items():
        if key == registry_key or key in registry_key or registry_key in key:
            rel_path = registry_path
            break

    if not rel_path:
        return {"error": f"No file found matching '{friendly_name}'. Try a name like 'home assistant server' or 'router'."}

    abs_path = os.path.join(BASE_DIR, rel_path.replace("/", os.sep))
    file_name = os.path.basename(abs_path)

    if not os.path.exists(abs_path):
        return {"error": f"File not found on disk: {rel_path}"}

    # Read the file
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            original_code = f.read()
    except Exception as e:
        return {"error": f"Could not read file: {e}"}

    # Pick system prompt based on file size
    line_count = original_code.count("\n")
    if line_count > LARGE_FILE_THRESHOLD:
        system_prompt = _REVIEW_SYSTEM_LARGE
        logger.info(f"[SelfWrite] Large file ({line_count} lines) — using patch mode")
    else:
        system_prompt = _REVIEW_SYSTEM_FULL
        logger.info(f"[SelfWrite] Small file ({line_count} lines) — using full rewrite mode")

    # Call LLM
    logger.info(f"[SelfWrite] Reviewing: {rel_path} ({len(original_code)} chars)")
    user_prompt = f"Please review this file ({file_name}):\n\n{original_code}"
    raw_response, err = _call_lmstudio(system_prompt, user_prompt)

    if not raw_response:
        return {"error": err or "LM Studio did not respond. Is it running?"}

    explanation, issues, suggested_code = _parse_review_response(raw_response)

    if not suggested_code:
        suggested_code = original_code   # fallback: no change

    # Store pending review
    review_id = str(uuid.uuid4())[:8]
    _pending_reviews[review_id] = {
        "id":           review_id,
        "file_name":    file_name,
        "rel_path":     rel_path,
        "abs_path":     abs_path,
        "original":     original_code,
        "suggested":    suggested_code,
        "explanation":  explanation or "No explanation provided.",
        "issues":       issues,
        "timestamp":    datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    logger.info(f"[SelfWrite] Review stored: ID={review_id}, file={file_name}")

    return {
        "review_id":   review_id,
        "file_name":   file_name,
        "issue_count": len(issues),
        "explanation": explanation,
    }


def start_review_async(friendly_name: str) -> str:
    """
    Start a review in a background thread.
    Returns a job_id immediately — caller polls get_job_status(job_id).
    """
    job_id = str(uuid.uuid4())[:8]
    _review_jobs[job_id] = {"status": "running", "error": None, "review_id": None}

    def _run():
        result = review_file(friendly_name)
        if "error" in result:
            _review_jobs[job_id]["status"] = "error"
            _review_jobs[job_id]["error"]  = result["error"]
        else:
            _review_jobs[job_id]["status"]    = "done"
            _review_jobs[job_id]["review_id"] = result.get("review_id")
            _review_jobs[job_id]["result"]    = result

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return job_id


def get_job_status(job_id: str) -> dict:
    """Return current status of an async review job."""
    job = _review_jobs.get(job_id)
    if not job:
        return {"status": "not_found"}
    return job


def approve_review(review_id: str, custom_code: str = None) -> dict:
    """Write the suggested (or user-edited) code to disk, replacing the original file."""
    review = _pending_reviews.get(review_id)
    if not review:
        return {"error": f"No pending review with ID: {review_id}"}

    # Use user-edited code if provided, otherwise fall back to suggested
    code_to_write = (custom_code.strip() if custom_code and custom_code.strip()
                     else review["suggested"])

    try:
        with open(review["abs_path"], "w", encoding="utf-8") as f:
            f.write(code_to_write)
        logger.info(f"[SelfWrite] Applied review {review_id} → {review['abs_path']}")
        del _pending_reviews[review_id]
        return {"success": True, "file": review["file_name"]}
    except Exception as e:
        logger.error(f"[SelfWrite] Write failed: {e}")
        return {"error": f"Could not write file: {e}"}


# ---------------------------------------------------------
# Voice handle() — MCP organ interface
# ---------------------------------------------------------

def handle(user_input: str) -> dict:
    text = user_input.lower().strip()

    # List pending reviews
    if any(k in text for k in ["list reviews", "show reviews", "pending reviews", "my reviews"]):
        reviews = get_pending_reviews()
        if not reviews:
            return {"data": "No pending code reviews right now."}
        names = ", ".join(r["file_name"] for r in reviews)
        return {"data": f"You have {len(reviews)} pending review(s): {names}. Check the Code Review panel to approve or reject."}

    # Clear all reviews
    if any(k in text for k in ["clear reviews", "dismiss reviews", "delete reviews"]):
        clear_all_reviews()
        return {"data": "All pending reviews have been cleared."}

    # Trigger a review — "review the home assistant server"
    trigger_words = ["review ", "analyze ", "analyse ", "inspect ", "improve ", "check "]
    file_query = None
    for trigger in trigger_words:
        if trigger in text:
            file_query = text.split(trigger, 1)[1].strip()
            # Strip leading "the ", "my "
            for filler in ["the ", "my ", "your "]:
                if file_query.startswith(filler):
                    file_query = file_query[len(filler):]
            break

    if file_query:
        result = review_file(file_query)
        if "error" in result:
            return {"data": result["error"]}
        n = result["issue_count"]
        fname = result["file_name"]
        return {
            "data": (
                f"Review complete for {fname}. "
                f"I found {n} suggestion{'s' if n != 1 else ''}. "
                f"Review ID is {result['review_id']}. "
                f"Open the Code Review panel to approve or reject my changes."
            )
        }

    # List available files
    if any(k in text for k in ["what can you review", "list files", "available files"]):
        names = sorted(set(FILE_REGISTRY.keys()))
        return {"data": "I can review: " + ", ".join(names) + "."}

    return {
        "data": (
            "Self-writing commands: "
            "'review [server name]' to analyze a file, "
            "'list reviews' to see pending changes, "
            "or open the Code Review panel to approve or reject."
        )
    }
