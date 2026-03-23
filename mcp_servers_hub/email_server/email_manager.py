# email_server/email_manager.py
import os
import ssl
import uuid
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .email_config import get_email_config

logger = logging.getLogger("email_server")


def send_email(recipient: str, subject: str, body: str) -> dict:
    """Send an email via SMTP SSL. Returns {"status": "success"} or {"status": "error", "message": ...}"""
    try:
        cfg = get_email_config()

        message = MIMEMultipart("alternative")
        message["Subject"]    = subject
        message["From"]       = cfg["username"]
        message["To"]         = recipient
        message["Message-ID"] = f"<{uuid.uuid4()}@jarvis.local>"
        message["User-Agent"] = "Jarvis Mailer/1.0"

        # Plain text fallback + HTML body
        message.attach(MIMEText(body, "plain"))
        message.attach(MIMEText(f"<p>{body}</p>", "html"))

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(cfg["smtp_server"], cfg["smtp_port"], context=context) as server:
            server.login(cfg["username"], cfg["password"])
            server.sendmail(cfg["username"], recipient, message.as_string())

        logger.info(f"[Email] Sent to {recipient} — subject: {subject}")
        return {"status": "success", "message": "Email sent successfully."}

    except Exception as e:
        logger.error(f"[Email] Send error: {e}")
        return {"status": "error", "message": str(e)}
