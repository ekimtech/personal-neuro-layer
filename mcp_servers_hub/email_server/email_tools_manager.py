# email_tools/email_tools_manager.py
import email
import imaplib
import os
import smtplib
from email_tools.email_utils import count_saved_emails
from flask import Blueprint, render_template, request, redirect, url_for, flash
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email_tools.inbox_manager import fetch_recent_emails
print("✅ inbox_manager imported")
from email_tools.email_config import get_email_config
from email.header import decode_header
from email import message_from_bytes

email_bp = Blueprint('email_bp', __name__)

@email_bp.route('/ping', methods=['GET'])
def ping():
    return {"status": "Jarvis is alive"}

@email_bp.route('/email')
def render_email():
    emails = fetch_recent_emails(limit=5)
    saved_count = count_saved_emails()
    return render_template('email.html', emails=emails, saved_count=saved_count)

@email_bp.route('/compose', methods=['GET'])
def show_compose_form():
    return render_template('compose.html')

@email_bp.route('/compose', methods=['POST'])
def compose_email():
    recipient = request.form['recipient']
    subject = request.form['subject']
    body = request.form['body']
    files = request.files.getlist('attachments')

    cfg = get_email_config()
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = cfg["username"]
    msg['To'] = recipient
    msg.attach(MIMEText(body, 'plain'))

    for file in files:
        if file and file.filename:
            part = MIMEApplication(file.read(), Name=file.filename)
            part['Content-Disposition'] = f'attachment; filename="{file.filename}"'
            msg.attach(part)

    try:
        with smtplib.SMTP_SSL(cfg["smtp_server"], cfg["smtp_port"]) as server:
            server.login(cfg["username"], cfg["password"])
            server.sendmail(cfg["username"], [recipient], msg.as_string())
        flash("✅ Email sent successfully", "success")
    except Exception as e:
        print(f"⚠️ Email failed: {e}")
        flash("❌ Failed to send email", "danger")

    return redirect(url_for('email_bp.show_compose_form'))

@email_bp.route('/view/<email_id>')
def view_email(email_id):
    cfg = get_email_config()
    try:
        mail = imaplib.IMAP4_SSL(cfg["imap_server"], cfg["imap_port"])
        mail.login(cfg["username"], cfg["password"])
        mail.select("INBOX")
        _, data = mail.fetch(email_id, "(RFC822)")
        raw_email = data[0][1]
        message = message_from_bytes(raw_email)

        subject = decode_header(message["subject"])[0][0]
        subject = subject.decode() if isinstance(subject, bytes) else subject
        sender = message["from"]

        body = ""
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                    body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
                    break
        else:
            body = message.get_payload(decode=True).decode(message.get_content_charset() or "utf-8")

        email_data = {
            "id": email_id,
            "subject": subject,
            "sender": sender,
            "body": body,
            "attachments": []  # You can populate this later
        }

        return render_template("view_email.html", email=email_data)

    except Exception as e:
        print(f"⚠️ View error: {e}")
        return f"<h2>Error loading email: {e}</h2>"

@email_bp.route('/move_to_saved', methods=['POST'])
def move_email_to_saved_route():
    email_id = request.form.get("email_id")
    cfg = get_email_config()
    try:
        mail = imaplib.IMAP4_SSL(cfg["imap_server"], cfg["imap_port"])
        mail.login(cfg["username"], cfg["password"])
        mail.select("INBOX")

        # ✅ Validate copy before deleting
        result = mail.copy(email_id, "INBOX.Saved")
        if result[0] != 'OK':
            raise Exception("Copy to INBOX.Saved failed")

        mail.store(email_id, '+FLAGS', '\\Deleted')
        mail.expunge()
        mail.logout()

        print(f"✅ Email {email_id} moved to INBOX.Saved")
        flash(f"Email {email_id} moved to Saved", "success")

    except Exception as e:
        print(f"⚠️ Save error: {e}")
        flash("Failed to move email to Saved", "danger")

    return redirect(url_for("email_bp.render_email"))

@email_bp.route('/delete_email', methods=['POST'])
def delete_email_route():
    email_id = request.form.get("email_id")
    cfg = get_email_config()
    try:
        mail = imaplib.IMAP4_SSL(cfg["imap_server"], cfg["imap_port"])
        mail.login(cfg["username"], cfg["password"])
        mail.select("INBOX")
        mail.store(email_id, '+FLAGS', '\\Deleted')
        mail.expunge()
        mail.logout()
        print(f"✅ Email {email_id} deleted")
    except Exception as e:
        print(f"⚠️ Delete error: {e}")
    return redirect(url_for("email_bp.render_email"))

@email_bp.route('/inbox_preview')
def inbox_preview():
    emails = fetch_recent_emails(limit=5)
    return {
        "status": "ok",
        "count": len(emails),
        "emails": emails
    }

    return redirect(url_for('email_bp.render_email_ui'))
