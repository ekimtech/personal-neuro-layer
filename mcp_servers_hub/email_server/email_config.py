# email_server/email_config.py
import os
from dotenv import load_dotenv

def get_email_config():
    # Always load .env from the email_server directory itself
    _dir = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(dotenv_path=os.path.join(_dir, ".env"))
    return {
        "username":    os.getenv("JARVIS_EMAIL_USERNAME"),
        "password":    os.getenv("JARVIS_EMAIL_PASSWORD"),
        "smtp_server": os.getenv("JARVIS_EMAIL_SMTP_SERVER", "mail.yourdomain.com"),
        "smtp_port":   int(os.getenv("JARVIS_EMAIL_SMTP_PORT", 465)),
        "imap_server": os.getenv("JARVIS_EMAIL_IMAP_SERVER", "mail.yourdomain.com"),
        "imap_port":   993,
        "use_tls":     os.getenv("JARVIS_EMAIL_USE_TLS", "False").lower() == "true"
    }
