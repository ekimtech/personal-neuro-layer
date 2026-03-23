# === Email Web UI Routes — email_server/email_routes.py ===
# Flask Blueprint registered at /email prefix
# Wired 03-18-26

import os
import ssl
import imaplib
import smtplib
import logging
from email import message_from_bytes
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, send_file
)

from .email_config import get_email_config
from .inbox_manager import fetch_recent_emails
from .email_utils import count_saved_emails

logger = logging.getLogger("email_server")

email_bp = Blueprint("email_bp", __name__, url_prefix="/email")


# ---------------------------------------------------------
# Helper — decode email headers safely
# ---------------------------------------------------------
def _decode_header(val) -> str:
    if val is None:
        return ""
    parts = decode_header(val)
    out = []
    for p, enc in parts:
        if isinstance(p, bytes):
            out.append(p.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(str(p))
    return "".join(out)


# ---------------------------------------------------------
# Inbox
# ---------------------------------------------------------
@email_bp.route("/")
@email_bp.route("/email")          # /email/email matches controlpanel link
def render_email():
    emails      = fetch_recent_emails(limit=10)
    saved_count = count_saved_emails()
    return render_template("email.html", emails=emails, saved_count=saved_count)


# ---------------------------------------------------------
# Compose
# ---------------------------------------------------------
@email_bp.route("/compose", methods=["GET"])
def show_compose_form():
    return render_template("compose.html")


@email_bp.route("/compose", methods=["POST"])
def compose_email():
    recipient = request.form.get("recipient", "").strip()
    subject   = request.form.get("subject", "").strip()
    body      = request.form.get("body", "").strip()
    files     = request.files.getlist("attachments")

    if not recipient or not subject or not body:
        flash("All fields are required.", "danger")
        return redirect(url_for("email_bp.show_compose_form"))

    cfg = get_email_config()
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"]    = cfg["username"]
    msg["To"]      = recipient
    msg.attach(MIMEText(body, "plain"))

    for file in files:
        if file and file.filename:
            part = MIMEApplication(file.read(), Name=file.filename)
            part["Content-Disposition"] = f'attachment; filename="{file.filename}"'
            msg.attach(part)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(cfg["smtp_server"], cfg["smtp_port"], context=context) as server:
            server.login(cfg["username"], cfg["password"])
            server.sendmail(cfg["username"], [recipient], msg.as_string())
        flash("Email sent successfully.", "success")
        logger.info(f"[Email] Sent via UI to {recipient}")
    except Exception as e:
        logger.error(f"[Email] Compose send error: {e}")
        flash(f"Failed to send: {e}", "danger")

    return redirect(url_for("email_bp.show_compose_form"))


# ---------------------------------------------------------
# View single email
# ---------------------------------------------------------
@email_bp.route("/view/<email_id>")
def view_email(email_id):
    cfg = get_email_config()
    try:
        mail = imaplib.IMAP4_SSL(cfg["imap_server"], cfg["imap_port"])
        mail.login(cfg["username"], cfg["password"])
        mail.select("INBOX")
        _, data = mail.fetch(email_id, "(RFC822)")
        message = message_from_bytes(data[0][1])

        subject = _decode_header(message.get("subject"))
        sender  = _decode_header(message.get("from"))

        body        = ""
        attachments = []

        if message.is_multipart():
            for part in message.walk():
                ct = part.get_content_type()
                cd = str(part.get("Content-Disposition", ""))
                if ct == "text/plain" and "attachment" not in cd and not body:
                    body = part.get_payload(decode=True).decode(
                        part.get_content_charset() or "utf-8", errors="replace")
                if "attachment" in cd:
                    fname = part.get_filename()
                    if fname:
                        fname = _decode_header(fname)
                        os.makedirs("static/attachments", exist_ok=True)
                        path = os.path.join("static/attachments", fname)
                        with open(path, "wb") as f:
                            f.write(part.get_payload(decode=True))
                        attachments.append(fname)
        else:
            body = message.get_payload(decode=True).decode(
                message.get_content_charset() or "utf-8", errors="replace")

        mail.logout()
        email_data = {
            "id":          email_id,
            "subject":     subject,
            "sender":      sender,
            "body":        body.strip(),
            "attachments": attachments
        }
        return render_template("view_email.html", email=email_data)

    except Exception as e:
        logger.error(f"[Email] View error: {e}")
        return f"<h2>Error loading email: {e}</h2>", 500


# ---------------------------------------------------------
# Saved emails
# ---------------------------------------------------------
@email_bp.route("/saved")
def show_emails():
    cfg         = get_email_config()
    saved_emails = []
    try:
        mail = imaplib.IMAP4_SSL(cfg["imap_server"], cfg["imap_port"])
        mail.login(cfg["username"], cfg["password"])
        mail.select("INBOX.Saved")
        _, data = mail.search(None, "ALL")
        ids = data[0].split()
        for e_id in ids[-20:]:
            _, email_data = mail.fetch(e_id, "(RFC822)")
            msg = message_from_bytes(email_data[0][1])
            saved_emails.append({
                "id":      e_id.decode(),
                "sender":  _decode_header(msg.get("from")),
                "subject": _decode_header(msg.get("subject")),
                "body":    ""
            })
        mail.logout()
    except Exception as e:
        logger.error(f"[Email] Saved fetch error: {e}")

    return render_template("saved_emails.html", saved_emails=saved_emails)


# ---------------------------------------------------------
# Move to saved
# ---------------------------------------------------------
@email_bp.route("/move_to_saved", methods=["POST"])
def move_email_to_saved_route():
    email_id = request.form.get("email_id")
    cfg      = get_email_config()
    try:
        mail = imaplib.IMAP4_SSL(cfg["imap_server"], cfg["imap_port"])
        mail.login(cfg["username"], cfg["password"])
        mail.select("INBOX")
        result = mail.copy(email_id, "INBOX.Saved")
        if result[0] != "OK":
            raise Exception("Copy to INBOX.Saved failed")
        mail.store(email_id, "+FLAGS", "\\Deleted")
        mail.expunge()
        mail.logout()
        flash("Email moved to Saved.", "success")
    except Exception as e:
        logger.error(f"[Email] Move error: {e}")
        flash("Failed to move email.", "danger")
    return redirect(url_for("email_bp.render_email"))


# ---------------------------------------------------------
# Delete
# ---------------------------------------------------------
@email_bp.route("/delete_email", methods=["POST"])
def delete_email_route():
    email_id = request.form.get("email_id")
    cfg      = get_email_config()
    try:
        mail = imaplib.IMAP4_SSL(cfg["imap_server"], cfg["imap_port"])
        mail.login(cfg["username"], cfg["password"])
        mail.select("INBOX")
        mail.store(email_id, "+FLAGS", "\\Deleted")
        mail.expunge()
        mail.logout()
        flash("Email deleted.", "success")
    except Exception as e:
        logger.error(f"[Email] Delete error: {e}")
        flash("Failed to delete email.", "danger")
    return redirect(url_for("email_bp.render_email"))


# ---------------------------------------------------------
# Download attachment
# ---------------------------------------------------------
@email_bp.route("/attachment/<email_id>/<filename>")
def download_attachment(email_id, filename):
    path = os.path.join("static", "attachments", filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return "Attachment not found.", 404
