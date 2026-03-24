import json
import re
from datetime import datetime
import logging
import requests
from flask import current_app

# === Session Recall — reads last 8 turns from SQLite ===
import sqlite3 as _sqlite3
import os as _os

_SESSION_DB = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
    "mcp_servers_hub", "memory_servers", "sqlite_server", "session.db"
)

def get_turns(session_id):
    """Fetch last 8 turns from SQLite session DB."""
    if not session_id:
        return []
    try:
        conn = _sqlite3.connect(_SESSION_DB)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT speaker, message FROM turns WHERE session_id = ? ORDER BY timestamp DESC LIMIT 8",
            (session_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        rows.reverse()  # chronological order
        return [{"speaker": r[0], "message": r[1]} for r in rows]
    except Exception as e:
        logger.error(f"[Cognition] Failed to get turns from SQLite: {e}")
        return []


# === Logging ===
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logger.addHandler(console)


# === LM Studio Query ===
def query_model(payload):
    api_url = current_app.config["LMSTUDIO_API_URL"]
    headers = {"Content-Type": "application/json"}

    try:
        logger.info(f"Sending request to LM Studio at {api_url}")
        response = requests.post(api_url, headers=headers, json=payload, timeout=600)
        response.raise_for_status()
        json_response = response.json()
        reply = json_response["choices"][0]["message"]["content"]
        logger.info(f"LM Studio response: {reply}")
        return reply
    except Exception as e:
        logger.error(f"❌ LM Studio query failed: {e}", exc_info=True)
        return ""


# === IMPORT JSONL MEMORY ORGAN ===
from mcp_servers_hub.memory_servers.jsonl_server.jsonl_memory_server import list_memory


# === Main Cognition Engine ===
def generate_response(user_input, session=None):
    user_input = user_input.strip()
    if not user_input:
        return {"message": "No message provided."}

    # === Session Recall ===
    session_context = ""
    if session:
        try:
            turns = get_turns(session)
            if turns:
                session_context = "\n\nRecent Conversation:\n" + "\n".join(
                    f"{t['speaker']}: {t['message']}" for t in turns
                )
        except Exception as e:
            logger.error(f"⚠️ Failed to load session turns: {e}", exc_info=True)

    # === Load JSONL Memory (Top 20 Relevant) ===
    try:
        all_entries = list_memory()

        # Score memory relevance based on keyword matches (strip punctuation)
        keywords = set(re.split(r'\W+', user_input.lower()))
        keywords.discard('')  # remove empty strings from split
        scored = []

        for entry in all_entries:
            content = entry["content"].lower()
            score = sum(1 for k in keywords if k in content)
            scored.append((score, entry))

        # Sort by score (desc), then take top 20 with minimum relevance threshold
        scored.sort(key=lambda x: x[0], reverse=True)
        top_entries = [e for score, e in scored[:20] if score >= 3]

        # Fallback: if nothing meets threshold, try score > 0
        if not top_entries:
            top_entries = [e for score, e in scored[:20] if score > 0]

        # Final fallback: take 20 most recent if still nothing
        if not top_entries:
            top_entries = all_entries[-20:]

        memory_text = "\n\nLong-Term Memory:\n" + "\n".join(
            f"- {e['id']}: {e['content']}" for e in top_entries
        )

    except Exception as e:
        memory_text = ""
        logger.error(f"⚠️ Failed to load JSONL memory: {e}", exc_info=True)

    # === Prompt Construction ===
    from model_injection.prompts import SYSTEM_PROMPT, get_system_context, build_prompt

    context = get_system_context()
    full_context = f"{context}{memory_text}{session_context}"

    full_prompt = build_prompt(
        user_input=user_input,
        context=full_context,
        soft_instruction="",
        cue="Jarvis:"
    )

    logger.info(f"\n🧠 FULL PROMPT SENT TO QWEN:\n{full_prompt}\n")

    # === LM Studio Call (Final, Stable, Compatible) ===
    reply = query_model(payload={
        "model": "qwen2.5-14b-instruct-1m",
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT + "\n\n" + full_context
            },
            {
                "role": "user",
                "content": f"/no_think {user_input}"
            }
        ],
        "chat_template_kwargs": {"enable_thinking": False}
    })

    # === Strip Chain-of-Thought, Markdown, Emojis, Memory Leaks ===
    raw = reply

    # 1. If </think> exists, strip everything before and including it
    if "</think>" in raw:
        raw = raw.split("</think>")[-1].strip()
    elif "<think>" in raw:
        # Unclosed <think> — entire response is thinking, no final answer
        # Try to extract the last clean draft embedded in the reasoning
        think_content = raw.split("<think>", 1)[-1]
        DRAFT_MARKERS = [
            "Final Polish:", "Final check on constraints:", "Final Draft:",
            "Let's write it.", "Revised Draft:", "Final:", "Output:",
            "Refined:", "Revised:"
        ]
        extracted = None
        for marker in DRAFT_MARKERS:
            if marker in think_content:
                after = think_content.split(marker)[-1].strip()
                paras = [p.strip() for p in after.split("\n\n") if p.strip()]
                for para in paras:
                    if not re.match(r'^[\d\*\-]|^Wait,|^Check|^Let\'s|^Ensure|^Note:|^Actually|^\*', para) \
                            and len(para) > 30:
                        extracted = para
                        break
            if extracted:
                break
        raw = extracted if extracted else ""

    # 1b. Safety net — if </think> still exists, strip everything before it
    if "</think>" in raw:
        raw = raw.split("</think>")[-1].strip()

    # 1c. Strip plain text thinking bleed (no tags)
    if "Thinking Process:" in raw:
        if "Jarvis final reply:" in raw:
            raw = raw.split("Jarvis final reply:", 1)[-1].strip()
        else:
            # Try to extract the final clean draft embedded in the reasoning
            DRAFT_MARKERS = [
                "Final Polish:", "Final check on constraints:", "Final Draft:",
                "Let's write it.", "Revised Draft:", "Final:", "Output:"
            ]
            extracted = None
            for marker in DRAFT_MARKERS:
                if marker in raw:
                    after = raw.split(marker)[-1].strip()
                    paras = [p.strip() for p in after.split("\n\n") if p.strip()]
                    for para in paras:
                        # Skip lines that are clearly still reasoning
                        if not re.match(r'^[\d\*\-]|^Wait,|^Check|^Let\'s|^Ensure|^Note:|^Actually', para) \
                                and len(para) > 30 \
                                and "Thinking Process:" not in para:
                            extracted = para
                            break
                if extracted:
                    break
            if extracted:
                raw = extracted
            else:
                # Nothing clean found — whole response is thinking, return safe fallback
                raw = "I'm here and ready."

    # 1d. Strip system prompt echo — model repeating its own instructions
    ECHO_MARKERS = [
        "I am Jarvis, Version", "You are Jarvis", "Memory Check:",
        "Personality:", "Constraints:", "Behavior rules:",
        "Memory Limitations:", "Given the context of the conversation",
        "I need to be careful", "The recent conversation shows",
        "I should explain"
    ]
    if any(marker in raw for marker in ECHO_MARKERS):
        # Try to find a clean final answer after all the reasoning
        paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip()]
        clean_paragraphs = [
            p for p in paragraphs
            if not any(marker in p for marker in ECHO_MARKERS)
            and not p.startswith("Memory chunk")
            and len(p) > 20
        ]
        if clean_paragraphs:
            raw = clean_paragraphs[-1]  # Take the last clean paragraph
        else:
            raw = "I'm here and ready."

    # 2. Remove "Content blocked…" artifacts
    raw = re.sub(r"\[Content blocked.*?\]", "", raw, flags=re.DOTALL)

    # 3. Remove markdown formatting
    raw = re.sub(r"\*\*|__", "", raw)
    raw = re.sub(r"\*|_", "", raw)
    raw = re.sub(r"`{1,3}.*?`{1,3}", "", raw)
    raw = re.sub(r"^#+\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"^- .*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"^\d+\.\s+.*", "", raw, flags=re.MULTILINE)

    # 4. Remove emojis
    raw = re.sub(r"[\U0001F600-\U0001F64F]", "", raw)
    raw = re.sub(r"[\U0001F300-\U0001F5FF]", "", raw)
    raw = re.sub(r"[\U0001F680-\U0001F6FF]", "", raw)
    raw = re.sub(r"[\U0001F1E0-\U0001F1FF]", "", raw)

    # 5. Remove memory leaks
    raw = re.sub(r"M\d{4}:\s.*", "", raw)

    # 6. Extract after "Jarvis final reply:" if present, otherwise use full raw
    if "Jarvis final reply:" in raw:
        clean = raw.split("Jarvis final reply:")[-1].strip()
    else:
        clean = raw.strip()

    # 7. Take only the first clean paragraph (stops at double newline)
    clean = clean.split("\n\n")[0].strip()

    # 8. Collapse whitespace
    clean = re.sub(r"\s+", " ", clean).strip()

    if not clean:
        clean = "I'm here and ready."

    logger.info(f"Jarvis final reply: {clean}")

    return {"message": clean}

