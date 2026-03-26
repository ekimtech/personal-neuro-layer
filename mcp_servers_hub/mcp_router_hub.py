# === Jarvis 4.0 Rebuild — MCP Router Hub 03-15-26 ===
# This is the central dispatcher for all organs.

import re
import os
import json
from datetime import datetime

# ---------------------------------------------------------
# Miss Tracker — logs requests that fall through to LLM
# ---------------------------------------------------------
_MISS_LOG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "mcp_servers_hub", "miss_log.json"
)

def _log_miss(user_input: str, intent: str):
    """Log requests that fell through to cognition — helps identify missing organs."""
    try:
        entries = []
        if os.path.exists(_MISS_LOG):
            with open(_MISS_LOG) as f:
                entries = json.load(f)
        entries.append({
            "timestamp":  datetime.now().isoformat(),
            "user_input": user_input,
            "intent":     intent
        })
        entries = entries[-500:]  # Keep last 500 misses
        with open(_MISS_LOG, "w") as f:
            json.dump(entries, f, indent=2)
    except Exception:
        pass


def get_miss_log(limit: int = 20) -> list:
    """Return recent miss log entries."""
    try:
        if not os.path.exists(_MISS_LOG):
            return []
        with open(_MISS_LOG) as f:
            entries = json.load(f)
        return entries[-limit:]
    except Exception:
        return []


def get_miss_summary() -> dict:
    """Summarize miss patterns — most common unhandled topics."""
    try:
        if not os.path.exists(_MISS_LOG):
            return {"total": 0, "entries": []}
        with open(_MISS_LOG) as f:
            entries = json.load(f)
        # Count word frequency across all missed inputs (filter stop words)
        from collections import Counter
        STOP_WORDS = {
            "the", "and", "for", "that", "this", "with", "from", "your", "just",
            "like", "what", "have", "will", "can", "you", "are", "was", "were",
            "they", "their", "there", "then", "than", "when", "which", "would",
            "could", "should", "about", "some", "been", "into", "more", "also",
            "how", "does", "did", "its", "not", "but", "had", "has", "her",
            "him", "his", "she", "our", "out", "who", "all", "any", "one",
            "want", "need", "tell", "give", "show", "make", "here", "know"
        }
        words = []
        for e in entries:
            words += [
                w.lower().strip("?.,!") for w in e["user_input"].split()
                if len(w) > 3 and w.lower().strip("?.,!") not in STOP_WORDS
            ]
        top = Counter(words).most_common(10)
        return {
            "total":    len(entries),
            "top_words": top,
            "recent":   entries[-5:]
        }
    except Exception as e:
        return {"total": 0, "error": str(e)}

# --- Import MCP organs (add more as you build them) ---
from mcp_servers_hub.weather_server.server import handle as weather_handle
from mcp_servers_hub.cognition_server.cognition_server import handle as cognition_handle
from mcp_servers_hub.internet_server.server import handle as internet_handle
from mcp_servers_hub.memory_servers.jsonl_server.jsonl_memory_server import handle as jsonl_memory_handle
from mcp_servers_hub.tts_server.server import handle as tts_handle
from mcp_servers_hub.qnap_server.qnap_server import handle as qnap_handle
from mcp_servers_hub.mikrotik_server.mikrotik_server import handle as mikrotik_handle
from mcp_servers_hub.home_assistant_server.home_assistant_server import handle as ha_handle
from mcp_servers_hub.email_server.server import handle as email_handle
from mcp_servers_hub.documents_server.server import handle as documents_handle
from mcp_servers_hub.self_writing_server.self_writing_server import handle as self_writing_handle
from mcp_servers_hub.crypto_wallet_server.crypto_wallet_server import handle as crypto_handle
from mcp_servers_hub.login_security.security import handle as security_handle
from mcp_servers_hub.games_server.games_server import handle as games_handle, is_game_active
from mcp_servers_hub.script_runner_server.script_runner_server import handle as script_runner_handle, is_code_paste

# NEW: semantic search
from mcp_servers_hub.vector_metadata_server.vector_store import search_similar


# ---------------------------------------------------------
# Emoji remover (fixes Piper crash)
# ---------------------------------------------------------
def remove_emojis(text):
    # Remove high-codepoint emojis (supplementary plane)
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    # Remove BMP emoji ranges — variation selectors, misc symbols, dingbats
    text = re.sub(r'[\u2600-\u27BF]', '', text)   # misc symbols & dingbats
    text = re.sub(r'[\uFE00-\uFE0F]', '', text)   # variation selectors (\ufe0f)
    text = re.sub(r'[\u200D]', '', text)           # zero-width joiner
    text = re.sub(r'[\u20E3]', '', text)           # combining enclosing keycap
    text = re.sub(r'[\u2300-\u23FF]', '', text)   # misc technical symbols
    return text


# ---------------------------------------------------------
# Intent Matching
# ---------------------------------------------------------

def detect_intent(user_input: str) -> str:
    text = user_input.lower().strip()

    # Script Runner — explicit trigger or detected code paste
    if any(k in text for k in [
        "run this", "execute this", "run script", "run this script",
        "execute script", "execute this script", "run this code",
        "execute this code", "run the script"
    ]):
        return "script_runner"
    if is_code_paste(user_input):
        return "script_runner"

    # Games — active game intercepts input first
    if is_game_active():
        return "games"
    if any(k in text for k in [
        "start number game", "number guessing game", "guessing game",
        "play a game", "lets play a game", "let's play a game",
        "start game", "number game", "play number", "play guessing",
        "quit game", "stop game", "end game", "exit game", "give up"
    ]):
        return "games"

    # Date / Time
    if any(k in text for k in [
        "what time", "what's the time", "whats the time", "current time",
        "what date", "what's the date", "whats the date", "today's date",
        "todays date", "what day is it", "what day is today",
        "what is today", "what is the date", "what is the time",
        "tell me the time", "tell me the date", "date and time",
        "current date", "day of the week"
    ]):
        return "datetime"

    # Miss Log — what fell through to LLM
    if any(k in text for k in [
        "miss log", "what did you miss", "what can't you do",
        "what are you missing", "unhandled requests",
        "what topics did you miss", "miss report", "miss summary"
    ]):
        return "miss_log"

    # Self-Knowledge — "triggers for X", "commands for X" — MUST be highest priority
    # Regex catches "what are the [anything] commands/triggers" generically
    if re.search(r"(what are|list|show|give me).*(commands|triggers|phrases)", text) or \
       re.search(r"(commands|triggers|phrases).*(for|on|about)\s+\w+", text) or \
       any(k in text for k in [
           "triggers for", "what are the triggers", "commands for",
           "how do i use", "what can you do with", "capabilities for",
           "what triggers", "show triggers", "what commands for",
           "how do i ask", "how do i tell", "what do i say to",
           "list triggers", "list commands", "show commands",
           "what commands", "which commands", "what phrases",
           "how do i ask jarvis", "what can jarvis do", "what can you do"
       ]):
        return "self_knowledge"

    # Security Report
    if any(k in text for k in [
        "security report", "who tried to hack", "any threats", "threats today",
        "blocked ips", "banned ips", "who is blocked", "who is banned",
        "blacklist", "probe log", "probe report", "who probed", "scan attempts",
        "failed login", "login attempts", "brute force", "recent bans",
        "security log", "show security", "jarvis security", "security status"
    ]):
        return "security"

    # Memory FIRST (regex catches all memory commands + personal info lookups)
    if re.match(r"^(remember|search memory|delete memory|list memory)\b", text):
        return "memory"
    if re.search(r"(when was|what is|what's|whats).*(born|birthday|birth date|anniversary|married|age)", text):
        return "memory"
    if re.search(r"(how old is|what year was|where was).*(born|live|married)", text):
        return "memory"

    # Crypto Wallet
    if any(k in text for k in [
        "wallet", "ada price", "cardano price", "generate wallet", "crypto",
        "wallet balance", "transaction history", "wallet address",
        "how much ada", "price of ada", "price of cardano",
        "trade signal", "what would you trade", "jarvis trade",
        "jarvis performance", "trading performance", "trading signal"
    ]):
        return "crypto"

    # Self-Writing Tools
    if any(k in text for k in [
        "review ", "analyze ", "analyse ", "inspect my code", "improve my code",
        "list reviews", "show reviews", "pending reviews", "clear reviews",
        "code review", "what can you review", "review your own",
    ]):
        return "self_writing"

    # Documents
    if any(k in text for k in [
        "invoice", "estimate", "generate letter", "create letter",
        "write letter", "compose letter", "write a letter", "create a letter",
        "make a letter", "new letter", "write me a letter",
        "create form", "open form", "fill out", "new document", "create document",
        "list documents", "show documents", "my documents", "saved documents"
    ]):
        return "documents"

    # Email
    if any(k in text for k in [
        "email", "inbox", "send email", "check email", "read email",
        "compose email", "check my email", "new emails", "any emails",
        "how many emails", "show inbox", "list emails"
    ]):
        return "email"

    # Internet search / news / fetch
    # Require action phrases so "search results" or "AI search" don't false-trigger
    if any(k in text for k in [
        "search for", "google", "look up", "lookup",
        "web search", "search the web", "search online",
        "find me", "find information",
        "news", "headlines", "what's happening", "whats happening",
        "latest news", "top stories", "breaking news",
        "http://", "https://"
    ]) or re.search(r"\bweb\b.*(find|get|show|look)", text):
        return "internet"

    # Weather / Air Quality / Hurricane
    if any(k in text for k in [
        "weather", "forecast", "temperature", "rain", "raining",
        "sunny", "cloudy", "humid", "humidity", "snow", "snowing",
        "cold outside", "hot outside",
        "air quality", "aqi", "uv index", "uv level", "pm2.5", "pm10",
        "air pollution", "air today", "how's the air", "how is the air",
        "hurricane", "tropical storm", "tropical depression",
        "storm surge", "active storms", "any storms", "nhc",
        "hurricane warning", "hurricane watch", "tropical warning", "cyclone"
    ]):
        return "weather"

    # TTS
    if text.startswith("speak ") or text.startswith("say "):
        return "tts"

    # STT
    if "transcribe" in text or "speech to text" in text:
        return "stt"

    # QNAP
    if any(k in text for k in ["qnap", "nas", "storage", "network drive", "shared folder"]):
        return "qnap"

    # MikroTik
    if any(k in text for k in ["mikrotik", "router", "firewall", "block ip", "unblock ip", "connected devices", "who is on"]):
        return "mikrotik"

    # Home Assistant
    if any(k in text for k in [
        "home assistant", "turn on the", "turn off the", "lights", "thermostat",
        "scene", "automation", "garage", "lock", "unlock", "blind", "shutter",
        "switch the", "dim the", "brighten", "hvac", "climate", "smart home",
        "is the light", "is the door", "is my", "home sensor", "turn on my", "turn off my",
        "play music", "play some music", "play a song", "play something", "play on the", "play on my",
        "pause the", "pause music", "resume music", "stop the music", "stop music",
        "next track", "next song", "previous track", "skip song", "skip track",
        "volume up", "volume down", "louder", "quieter", "shuffle",
        "now playing", "what's playing", "whats playing", "what is playing", "what song",
        "bedroom speaker", "bedroom tv", "cast devices",
        "set volume", "volume to", "turn it up", "turn it down",
        "turn up the volume", "turn down the volume",
        "list media", "media player", "media players", "what speakers",
        "show media", "cast device"
    ]):
        return "home_assistant"

    # Default → cognition
    return "cognition"


# ---------------------------------------------------------
# Router Core
# ---------------------------------------------------------

def handle_request(user_input: str, session_id=None) -> dict:
    intent = detect_intent(user_input)

    # --- Crypto Wallet Organ ---
    if intent == "crypto":
        result = crypto_handle(user_input)
        response_text = result.get("data", "")
        cleaned = remove_emojis(response_text)
        tts_handle("say " + cleaned)
        return {"message": response_text}

    # --- Miss Log Organ ---
    if intent == "miss_log":
        summary = get_miss_summary()
        if summary["total"] == 0:
            return {"message": "No missed requests logged yet. Everything has been handled by an organ."}
        top = "\n".join(f"  '{w}' ({c} times)" for w, c in summary.get("top_words", [])[:5])
        recent = "\n".join(f"  - {e['user_input'][:60]} [{e['timestamp'][:10]}]" for e in summary.get("recent", []))
        response = (
            f"**Miss Log Summary — {summary['total']} unhandled requests**\n\n"
            f"**Top unrecognized topics:**\n{top}\n\n"
            f"**Recent misses:**\n{recent}"
        )
        tts_handle(f"say I have logged {summary['total']} requests that went to the language model. The most common topics were {', '.join(w for w, c in summary.get('top_words', [])[:3])}.")
        return {"message": response}

    # --- Self-Knowledge Organ (triggers/commands help) ---
    if intent == "self_knowledge":
        import os as _os
        text_lower = user_input.lower()

        # Map keywords in the query to section headings in the trigger guide
        SECTION_MAP = {
            "memory":        "## Memory",
            "document":      "## Documents",
            "email":         "## Email",
            "home assistant":"## Home Assistant",
            "media":         "## Home Assistant",
            "weather":       "## Weather",
            "internet":      "## Internet",
            "search":        "## Internet",
            "news":          "## Internet",
            "qnap":          "## QNAP",
            "nas":           "## QNAP",
            "storage":       "## QNAP",
            "mikrotik":      "## MikroTik",
            "router":        "## MikroTik",
            "firewall":      "## MikroTik",
            "security":      "## Security",
            "threat":        "## Security",
            "blocked":       "## Security",
            "crypto":        "## Crypto",
            "ada":           "## Crypto",
            "wallet":        "## Crypto",
            "trading":       "## Crypto",
            "self":          "## Self-Writing",
            "code review":   "## Self-Writing",
            "review":        "## Self-Writing",
            "datetime":      "## Date",
            "date":          "## Date",
            "time":          "## Date",
        }

        # Find the best matching section
        target_section = None
        for keyword, section in SECTION_MAP.items():
            if keyword in text_lower:
                target_section = section
                break

        # Read the trigger guide directly
        guide_path = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            "JARVIS_TRIGGER_GUIDE.md"
        )

        if _os.path.exists(guide_path):
            with open(guide_path, "r", encoding="utf-8") as f:
                content = f.read()

            if target_section:
                # Extract the matching section
                sections = re.split(r'(?=^## )', content, flags=re.MULTILINE)
                for section in sections:
                    if section.startswith(target_section):
                        tts_handle("say Here are the trigger phrases for that tool.")
                        return {"message": section.strip()}
            else:
                # No specific tool found — return full guide
                tts_handle("say Here is the full Jarvis trigger guide.")
                return {"message": content.strip()}

        # Fallback to vector search
        results = search_similar(user_input, top_k=2)
        if results:
            tts_handle("say Here are the trigger phrases for that tool.")
            return {"message": results[0]["full_content"]}

        return {"message": "I don't have trigger information for that tool yet. Try uploading the Jarvis Trigger Guide to my vector memory."}

    # --- Security Organ ---
    if intent == "security":
        result = security_handle(user_input)
        response_text = result.get("data", "No security data available.")
        cleaned = remove_emojis(response_text)
        tts_handle("say " + cleaned)
        return {"message": response_text}

    # --- Date / Time ---
    if intent == "datetime":
        now = datetime.now()
        day_name  = now.strftime("%A")
        date_str  = now.strftime("%B %d, %Y")
        time_str  = now.strftime("%I:%M %p").lstrip("0")
        response_text = f"Today is {day_name}, {date_str}. The current time is {time_str}."
        tts_handle("say " + response_text)
        return {"message": response_text}

    # --- Self-Writing Organ ---
    if intent == "self_writing":
        result = self_writing_handle(user_input)
        response_text = result.get("data", "")
        cleaned = remove_emojis(response_text)
        tts_handle("say " + cleaned)
        return {"message": response_text}

    # --- Documents Organ ---
    if intent == "documents":
        result = documents_handle(user_input)
        response_text = result.get("data", "")
        cleaned = remove_emojis(response_text)
        tts_handle("say " + cleaned)
        return {"message": response_text}

    # --- Email Organ ---
    if intent == "email":
        result = email_handle(user_input)
        response_text = result.get("data", "No email result.")
        cleaned = remove_emojis(response_text)
        tts_handle("say " + cleaned)
        return {"message": response_text}

    # --- Internet Organ ---
    if intent == "internet":
        result = internet_handle(user_input)
        response_text = result.get("data", "No result found.")
        cleaned = remove_emojis(response_text)
        tts_handle("say " + cleaned)
        return {"message": response_text}

    # --- Weather Organ ---
    if intent == "weather":
        # Air quality and hurricane route through internet_handle
        _wtext = user_input.lower()
        if any(k in _wtext for k in [
            "air quality", "aqi", "uv index", "uv level", "pm2.5", "pm10",
            "air pollution", "air today", "how's the air", "how is the air",
            "hurricane", "tropical storm", "tropical depression",
            "storm surge", "active storms", "any storms", "nhc",
            "hurricane warning", "hurricane watch", "tropical warning", "cyclone"
        ]):
            result = internet_handle(user_input)
        else:
            result = weather_handle(user_input)
        response_text = result.get("data", "Could not get weather.")
        cleaned = remove_emojis(response_text)
        tts_handle("say " + cleaned)
        return {"message": response_text}

    # --- TTS Organ ---
    if intent == "tts":
        result = tts_handle(user_input)
        return {"response": result.get("data", "No TTS result")}

    # --- STT Organ ---
    if intent == "stt":
        return {"response": "STT organ not implemented yet."}

    # --- Script Runner Organ ---
    if intent == "script_runner":
        result = script_runner_handle(user_input)
        return {"response": result.get("data", "Script runner error."), "no_tts": True}

    # --- Games Organ ---
    if intent == "games":
        result = games_handle(user_input)
        return {"response": result.get("data", "Game error.")}

    # --- Memory Organ ---
    if intent == "memory":
        print(f"[Router] intent=memory | input={user_input[:60]}")
        lower_input = user_input.lower().strip()

        # If it's an explicit memory command, pass straight through
        if any(lower_input.startswith(cmd) for cmd in [
            "remember ", "search memory", "delete memory", "list memory"
        ]):
            result = jsonl_memory_handle(user_input)
            response_text = result.get("data", "No memory result.")
            print(f"[Memory] Response: {str(response_text)[:80]}")
            cleaned = remove_emojis(str(response_text))
            tts_handle("say " + cleaned)
            return {"message": str(response_text)}

        # Natural language lookup — extract subject and search memory
        # Strip common question words to isolate the key name/topic
        subject = re.sub(
            r"^(when was|when did|what is|what's|whats|how old is|"
            r"where was|where is|who is|what was|tell me about|"
            r"do you know|do you remember|what do you know about)\s+",
            "", lower_input, flags=re.IGNORECASE
        ).strip()
        # Strip trailing question/filler words
        subject = re.sub(
            r"\s+(born|birthday|birth date|age|anniversary|married|"
            r"live|living|from|die|died|get married|get born)\??$",
            "", subject, flags=re.IGNORECASE
        ).strip(" ?.,")

        print(f"[Memory] Searching for subject: '{subject}'")

        from mcp_servers_hub.memory_servers.jsonl_server.jsonl_memory_server import search_memory
        results = search_memory(subject) if subject else []

        if results:
            # Format the top matches into a readable response
            snippets = []
            for r in results[:3]:
                content = r.get("content", "")
                if content:
                    snippets.append(content)
            response_text = " | ".join(snippets) if snippets else "I found some entries but couldn't read them."
            print(f"[Memory] Found {len(results)} result(s): {response_text[:80]}")
        else:
            response_text = f"I don't have any memory stored about {subject}." if subject else "I couldn't determine what you were asking about."
            print(f"[Memory] No results for '{subject}'")

        cleaned = remove_emojis(response_text)
        tts_handle("say " + cleaned)
        return {"message": response_text}

    # --- QNAP Organ ---
    if intent == "qnap":
        result = qnap_handle(user_input)
        response_text = result.get("data", "No QNAP result")
        # Speak the response
        cleaned = remove_emojis(response_text)
        tts_handle("say " + cleaned)
        return {"message": response_text}
    
    # --- MikroTik Organ ---
    if intent == "mikrotik":
        result = mikrotik_handle(user_input)
        cleaned = remove_emojis(result.get("data", "No router result"))
        tts_handle("say " + cleaned)
        return {"message": result.get("data", "No router result")}

    # --- Home Assistant Organ ---
    if intent == "home_assistant":
        result = ha_handle(user_input)
        response_text = result.get("data", "No Home Assistant result")
        cleaned = remove_emojis(response_text)
        tts_handle("say " + cleaned)
        return {"message": response_text}

    # ---------------------------------------------------------
    # Cognition (default fallback) WITH SEMANTIC MEMORY
    # ---------------------------------------------------------

    # Log this as a miss — no organ handled it
    _log_miss(user_input, intent)

    # 1. Retrieve relevant memory chunks — only for document/command queries
    _doc_keywords = {
        "how", "command", "trigger", "turn", "device", "light", "thermostat",
        "lock", "document", "invoice", "estimate", "letter", "guide",
        "what command", "how do", "how to", "what does my", "uploaded"
    }
    _input_lower = user_input.lower()
    _use_vector = any(k in _input_lower for k in _doc_keywords)

    memory_results = search_similar(user_input, top_k=3) if _use_vector else []

    # 2. Build memory context string
    memory_context = ""
    for r in memory_results:
        memory_context += (
            f"\n[Memory chunk {r['chunk_index']} from {r['filename']}]\n"
            f"{r['full_content']}\n"
        )

    # 3. Build augmented prompt
    augmented_input = f"""
Relevant memory:
{memory_context}

User: {user_input}
"""

    # 4. Send augmented prompt to cognition organ
    result = cognition_handle(augmented_input, session=session_id)

    # ---------------------------------------------------------
    # Auto-speak the cognition response (cleaned)
    # ---------------------------------------------------------

    raw = result.get("message", "")

    # Extract final reply safely
    if "Jarvis final reply:" in raw:
        cleaned = raw.split("Jarvis final reply:")[-1].strip()
    else:
        lines = [line.strip() for line in raw.split("\n") if line.strip()]
        cleaned = lines[-1] if lines else ""

    # Remove emojis before sending to Piper
    cleaned = remove_emojis(cleaned)

    # Speak the cleaned text
    tts_handle("say " + cleaned)

    # Return cleaned text to UI (fixes the "None" issue)
    return {"message": cleaned}
