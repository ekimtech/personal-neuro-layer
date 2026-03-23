# === Email Organ — email_server/server.py ===
# Wired 03-18-26
# Provider: configured via email_server/.env
# SMTP SSL port 465 | IMAP SSL port 993

import re
import logging
from .email_manager import send_email
from .inbox_manager import fetch_recent_emails, count_inbox

logger = logging.getLogger("email_server")


# ---------------------------------------------------------
# Formatters
# ---------------------------------------------------------

def _format_inbox(emails: list) -> str:
    if not emails:
        return "Your inbox is empty."

    total = count_inbox()
    lines = [f"You have {total} email(s) in your inbox. Here are the last {len(emails)}:"]
    for i, e in enumerate(emails, 1):
        sender  = e.get("sender", "Unknown")
        subject = e.get("subject", "No Subject")
        date    = e.get("date", "")
        lines.append(f"{i}. From: {sender} | {subject} | {date}")
    return "\n".join(lines)


def _format_email_detail(e: dict) -> str:
    lines = [
        f"From:    {e.get('sender', 'Unknown')}",
        f"Subject: {e.get('subject', 'No Subject')}",
        f"Date:    {e.get('date', '')}",
        "",
        e.get("body", "No body content.")[:500]
    ]
    if e.get("attachments"):
        lines.append(f"Attachments: {', '.join(e['attachments'])}")
    return "\n".join(lines)


# ---------------------------------------------------------
# Parser — extract send parameters from natural language
# ---------------------------------------------------------

def _parse_send(text: str) -> dict | None:
    """
    Supported voice patterns:
      "send email to mike@example.com subject hello saying how are you"
      "send email to mike@example.com saying how are you"
      "email mike@example.com saying how are you"
      "email mike@example.com subject test message body goes here"
    """
    patterns = [
        r"(?:send (?:an? )?email|email) to (.+?) subject (.+?) (?:message|body|saying) (.+)",
        r"(?:send (?:an? )?email|email) to (.+?) saying (.+)",
        r"email (.+?) subject (.+?) saying (.+)",
        r"email (.+?) saying (.+)",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            g = m.groups()
            return {
                "to":      g[0].strip(),
                "subject": g[1].strip() if len(g) == 3 else "Message from Jarvis",
                "body":    g[-1].strip()
            }
    return None


# ---------------------------------------------------------
# Main handle()
# ---------------------------------------------------------

def handle(user_input: str) -> dict:
    text = user_input.lower().strip()

    # --- Send email ---
    if any(k in text for k in [
        "send email", "send an email", "send a email",
        "compose email", "write email", "email to"
    ]):
        params = _parse_send(user_input)
        if params:
            logger.info(f"[Email] Sending to: {params['to']} | Subject: {params['subject']}")
            result = send_email(params["to"], params["subject"], params["body"])
            if result.get("status") == "success":
                return {"data": f"Done. Email sent to {params['to']}."}
            else:
                return {"data": f"Failed to send email. {result.get('message', '')}"}
        else:
            return {"data": (
                "I couldn't parse that. Try: "
                "'send email to address@example.com saying your message here'"
            )}

    # --- Read / check inbox ---
    if any(k in text for k in [
        "check email", "check my email", "read email", "read my email",
        "check inbox", "my inbox", "any new email", "any emails",
        "do i have email", "what emails", "new emails",
        "show emails", "list emails", "show inbox"
    ]):
        try:
            logger.info("[Email] Fetching inbox")
            emails = fetch_recent_emails(limit=5)
            return {"data": _format_inbox(emails)}
        except Exception as e:
            logger.error(f"[Email] Inbox error: {e}")
            return {"data": f"Could not fetch inbox. {e}"}

    # --- Count emails ---
    if any(k in text for k in ["how many emails", "email count", "count emails", "count my emails"]):
        total = count_inbox()
        return {"data": f"You have {total} email(s) in your inbox."}

    return {"data": (
        "Email command not understood. "
        "Try 'check email', 'how many emails', or "
        "'send email to address@example.com saying your message'."
    )}
