# email_server/inbox_manager.py
import os
import imaplib
import email
import logging
from email.header import decode_header
from .email_config import get_email_config

logger = logging.getLogger("email_server")


def _decode(value) -> str:
    """Safely decode an email header value."""
    if value is None:
        return ""
    parts = decode_header(value)
    decoded = []
    for part, enc in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            decoded.append(str(part))
    return "".join(decoded)


def fetch_recent_emails(limit: int = 5) -> list:
    """Fetch the most recent emails from INBOX. Returns a list of dicts."""
    cfg = get_email_config()
    emails = []

    try:
        mail = imaplib.IMAP4_SSL(cfg["imap_server"], cfg["imap_port"])
        mail.login(cfg["username"], cfg["password"])
        mail.select("INBOX")

        status, search_data = mail.search(None, "ALL")
        email_ids = search_data[0].split()
        logger.info(f"[Email] Inbox has {len(email_ids)} messages, fetching last {limit}")

        for e_id in email_ids[-limit:]:
            _, email_data = mail.fetch(e_id, "(RFC822)")
            raw_email = email_data[0][1]
            message = email.message_from_bytes(raw_email)

            subject = _decode(message.get("subject", "No Subject"))
            sender  = _decode(message.get("from", "Unknown"))
            date    = message.get("date", "")

            # Extract plain text body
            body = ""
            if message.is_multipart():
                for part in message.walk():
                    ct = part.get_content_type()
                    cd = str(part.get("Content-Disposition", ""))
                    if ct == "text/plain" and "attachment" not in cd:
                        body = part.get_payload(decode=True).decode(
                            part.get_content_charset() or "utf-8", errors="replace"
                        )
                        break
            else:
                body = message.get_payload(decode=True).decode(
                    message.get_content_charset() or "utf-8", errors="replace"
                )

            # Extract attachments
            attachments = []
            for part in message.walk():
                if part.get_content_disposition() == "attachment":
                    filename = part.get_filename()
                    if filename:
                        filename = _decode(filename)
                        os.makedirs("static/attachments", exist_ok=True)
                        path = os.path.join("static/attachments", filename)
                        with open(path, "wb") as f:
                            f.write(part.get_payload(decode=True))
                        attachments.append(filename)

            emails.append({
                "id":          e_id.decode(),
                "sender":      sender,
                "subject":     subject,
                "date":        date,
                "body":        body.strip(),
                "attachments": attachments
            })

        mail.logout()

    except Exception as e:
        logger.error(f"[Email] IMAP error: {e}")

    return emails


def count_inbox() -> int:
    """Return the total number of emails in INBOX."""
    cfg = get_email_config()
    try:
        mail = imaplib.IMAP4_SSL(cfg["imap_server"], cfg["imap_port"])
        mail.login(cfg["username"], cfg["password"])
        mail.select("INBOX")
        _, data = mail.search(None, "ALL")
        mail.logout()
        return len(data[0].split())
    except Exception as e:
        logger.error(f"[Email] Count error: {e}")
        return 0
