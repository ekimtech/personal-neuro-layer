# email_server/email_utils.py
import imaplib
import logging
from .email_config import get_email_config

logger = logging.getLogger("email_server")


def count_saved_emails() -> int:
    """Return the count of emails in INBOX.Saved."""
    cfg = get_email_config()
    try:
        mail = imaplib.IMAP4_SSL(cfg["imap_server"], cfg["imap_port"])
        mail.login(cfg["username"], cfg["password"])
        mail.select("INBOX.Saved")
        _, data = mail.search(None, "ALL")
        mail.logout()
        return len(data[0].split())
    except Exception as e:
        logger.error(f"[Email] Saved count error: {e}")
        return 0
