# Jarvis4.0/email_tools/email_mcp.py

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email_tools.email_config import get_email_config

def send_email(to_address, subject, body):
    cfg = get_email_config()

    msg = MIMEMultipart()
    msg['From'] = cfg["username"]
    msg['To'] = to_address
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(cfg["smtp_server"], cfg["smtp_port"])
        if cfg.get("use_tls", False):  # Optional: add USE_TLS to .env if needed
            server.starttls()
        server.login(cfg["username"], cfg["password"])
        server.sendmail(cfg["username"], to_address, msg.as_string())
        server.quit()
        return {"status": "success", "message": "Email sent successfully."}
    except Exception as e:
        return {"status": "error", "message": str(e)}
