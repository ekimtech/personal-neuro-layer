# === Jarvis 4.0 — Clean, Optimized Prompt Injection Layer ===
# This version removes chain-of-thought leakage, removes prompt bloat,
# and ensures JSONL memory + session recall are injected cleanly.

import datetime

# ------------------------------------------------------------
# SYSTEM PROMPT — Jarvis Identity, Rules, Behavior
# ------------------------------------------------------------

SYSTEM_PROMPT = """
You are Jarvis, a Personal Neuro Layer AI assistant.

Your personality:
- Friendly, professional, concise
- Occasionally humorous, but only when appropriate
- Clear, direct, and helpful

Your behavior rules:
- Never reveal chain-of-thought or hidden reasoning
- Never output <think> tags or internal steps
- Never invent facts, dates, or technical specifications
- If unsure, say: "I don't have that specific information."
- Only mention your origin if the user explicitly asks
- Never use bullet points, numbered lists, or markdown formatting in responses
- Always respond in plain flowing sentences and paragraphs only
- Never use bold text, headers, or any markdown symbols

Your capabilities:
- Network diagnostics
- Weather updates
- Email/letter drafting
- Invoice/estimate creation
- File summarization (.txt, .pdf, .docx)
- Code execution (when tools are available)
- Long-term memory recall (JSONL memory)
- Session recall (last 8 turns)

Your goal:
Respond naturally, intelligently, and efficiently.
"""


# ------------------------------------------------------------
# SYSTEM CONTEXT — Static background info
# ------------------------------------------------------------

def get_system_context():
    return """
System Context:
- Jarvis Personal Neuro Layer is active and running.
- Local network monitoring and smart home control are enabled.
"""


# ------------------------------------------------------------
# BUILD PROMPT — Clean, minimal, no instructions injected
# ------------------------------------------------------------

def build_prompt(user_input: str, context: str, soft_instruction: str = "", cue: str = "Jarvis:"):
    """
    This function now ONLY assembles:
    - system context
    - long-term memory (injected by cognition.py)
    - session recall (injected by cognition.py)
    - user message

    It does NOT inject:
    - instructions
    - rules
    - meta text
    - chain-of-thought cues
    - "Thinking Process"
    - "Jarvis:" prefixes

    This keeps the prompt clean and prevents Qwen from leaking reasoning.
    """

    timestamp = datetime.datetime.utcnow().isoformat()

    return f"""
Timestamp: {timestamp}

{context}

User: {user_input}

{cue}
"""
