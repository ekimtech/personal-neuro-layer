# === Documents Server Routes — documents_server/routes.py ===
# Flask Blueprint — registered at /documents
# Handles invoice, estimate, and letter generation with PDF save
# Wired 03-19-26

import os
import base64
import logging
from datetime import datetime, timedelta
from flask import (
    Blueprint, render_template, request,
    send_file, jsonify, Response
)

try:
    from weasyprint import HTML as WeasyprintHTML
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError, Exception):
    WEASYPRINT_AVAILABLE = False
    logger.warning("[Docs] WeasyPrint not available — PDF auto-save disabled. Browser print-to-PDF still works.")

logger = logging.getLogger("documents_server")

documents_bp = Blueprint("documents_bp", __name__, url_prefix="/documents")

# --- Paths ---
_HERE     = os.path.dirname(os.path.abspath(__file__))
BASE_DIR  = os.path.dirname(os.path.dirname(_HERE))   # Jarvis4.0/

LOGO_PATH = os.path.join(BASE_DIR, "static", "images", "handybeaverlogo.jpg")

DOC_FOLDERS = {
    "invoice":  os.path.join(BASE_DIR, "documents", "invoices"),
    "estimate": os.path.join(BASE_DIR, "documents", "estimates"),
    "letter":   os.path.join(BASE_DIR, "documents", "letters"),
}

# Create folders on import
for _folder in DOC_FOLDERS.values():
    os.makedirs(_folder, exist_ok=True)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _logo_b64() -> str:
    """Return company logo as base64 data URI."""
    try:
        with open(LOGO_PATH, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        ext = os.path.splitext(LOGO_PATH)[1].lower().lstrip(".")
        mime = "jpeg" if ext in ("jpg", "jpeg") else ext
        return f"data:image/{mime};base64,{data}"
    except Exception as e:
        logger.warning(f"[Docs] Logo error: {e}")
        return ""


def _next_number(doc_type: str) -> str:
    """Generate next sequential document number."""
    prefix  = {"invoice": "INV", "estimate": "EST", "letter": "LTR"}[doc_type]
    folder  = DOC_FOLDERS[doc_type]
    count   = len([f for f in os.listdir(folder) if f.endswith(".pdf")]) + 1
    return f"{prefix}-{datetime.now().strftime('%Y%m')}-{count:04d}"


def _parse_items(form) -> tuple:
    """Parse dynamic line-item arrays from form POST data."""
    descs   = form.getlist("description[]")
    qtys    = form.getlist("quantity[]")
    prices  = form.getlist("unit_price[]")
    items   = []
    for desc, qty, price in zip(descs, qtys, prices):
        try:
            q = float(qty)
            p = float(price)
            items.append({
                "description": desc.strip(),
                "quantity":    q,
                "unit_price":  p,
                "line_total":  round(q * p, 2),
            })
        except ValueError:
            continue
    total = round(sum(i["line_total"] for i in items), 2)
    return items, total


def _safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


def _save_pdf(html_string: str, path: str) -> bool:
    """Render HTML → PDF via weasyprint and save to disk."""
    if not WEASYPRINT_AVAILABLE:
        logger.warning("[Docs] weasyprint not available — PDF not saved")
        return False
    try:
        WeasyprintHTML(string=html_string, base_url=BASE_DIR).write_pdf(path)
        logger.info(f"[Docs] Saved: {path}")
        return True
    except Exception as e:
        logger.error(f"[Docs] PDF save error: {e}")
        return False


# ---------------------------------------------------------
# Document Browser
# ---------------------------------------------------------

@documents_bp.route("/")
@documents_bp.route("")
def documents_index():
    return render_template("lists_pdf.html")


# ---------------------------------------------------------
# API — list saved PDFs
# ---------------------------------------------------------

@documents_bp.route("/api/list")
def api_list():
    doc_type = request.args.get("type", "invoice").lower()
    folder   = DOC_FOLDERS.get(doc_type)
    if not folder or not os.path.exists(folder):
        return jsonify([])
    files = sorted([f for f in os.listdir(folder) if f.endswith(".pdf")], reverse=True)
    return jsonify(files)


# ---------------------------------------------------------
# Serve stored PDF
# ---------------------------------------------------------

@documents_bp.route("/<doc_type>/<filename>.pdf")
def serve_document(doc_type, filename):
    folder = DOC_FOLDERS.get(doc_type)
    if not folder:
        return "Document type not found.", 404
    path = os.path.join(folder, filename + ".pdf")
    if not os.path.exists(path):
        return "File not found.", 404
    return send_file(path, mimetype="application/pdf")


# ---------------------------------------------------------
# INVOICE
# ---------------------------------------------------------

@documents_bp.route("/invoice/create", methods=["GET"])
def invoice_form():
    return render_template(
        "invoice_form.html",
        today=datetime.now().strftime("%Y-%m-%d")
    )


@documents_bp.route("/invoice/generate", methods=["POST"])
def invoice_generate():
    items, total  = _parse_items(request.form)
    doc_number    = _next_number("invoice")
    context = {
        "logo_base64":       _logo_b64(),
        "recipient_name":    request.form.get("recipient_name", "").strip(),
        "recipient_address": request.form.get("recipient_address", "").strip(),
        "invoice_date":      request.form.get("invoice_date", datetime.now().strftime("%Y-%m-%d")),
        "invoice_number":    doc_number,
        "items":             items,
        "total_amount":      total,
        "notes":             request.form.get("notes", "").strip(),
        "signature":         request.form.get("signature", "Your Name").strip(),
    }
    html = render_template("invoice_template.html", **context)
    fname = f"{doc_number}_{_safe_filename(context['recipient_name'])}.pdf"
    _save_pdf(html, os.path.join(DOC_FOLDERS["invoice"], fname))
    return Response(html, mimetype="text/html")


# ---------------------------------------------------------
# ESTIMATE
# ---------------------------------------------------------

@documents_bp.route("/estimate/create", methods=["GET"])
def estimate_form():
    return render_template(
        "estimate_form.html",
        today=datetime.now().strftime("%Y-%m-%d"),
        expiry=(datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    )


@documents_bp.route("/estimate/generate", methods=["POST"])
def estimate_generate():
    items, total = _parse_items(request.form)
    doc_number   = _next_number("estimate")
    context = {
        "logo_base64":       _logo_b64(),
        "recipient_name":    request.form.get("recipient_name", "").strip(),
        "recipient_address": request.form.get("recipient_address", "").strip(),
        "estimate_date":     request.form.get("estimate_date", datetime.now().strftime("%Y-%m-%d")),
        "estimate_number":   doc_number,
        "items":             items,
        "estimated_total":   total,
        "notes":             request.form.get("notes", "").strip(),
        "signature":         request.form.get("signature", "Your Name").strip(),
        "expiry_date":       request.form.get("expiry_date", "").strip(),
    }
    html = render_template("estimate_template.html", **context)
    fname = f"{doc_number}_{_safe_filename(context['recipient_name'])}.pdf"
    _save_pdf(html, os.path.join(DOC_FOLDERS["estimate"], fname))
    return Response(html, mimetype="text/html")


# ---------------------------------------------------------
# LETTER
# ---------------------------------------------------------

@documents_bp.route("/letter/create", methods=["GET"])
def letter_form():
    return render_template(
        "letter_form.html",
        today=datetime.now().strftime("%Y-%m-%d")
    )


@documents_bp.route("/letter/generate", methods=["POST"])
def letter_generate():
    doc_number  = _next_number("letter")
    body_raw    = request.form.get("body", "").strip()
    paragraphs  = [p.strip() for p in body_raw.split("\n\n") if p.strip()] or [body_raw]
    context = {
        "logo_base64":       _logo_b64(),
        "recipient_name":    request.form.get("recipient_name", "").strip(),
        "recipient_address": request.form.get("recipient_address", "").strip(),
        "subject":           request.form.get("subject", "").strip(),
        "salutation":        request.form.get("salutation", "Sir/Madam").strip(),
        "body_paragraphs":   paragraphs,
        "closing":           request.form.get("closing", "Sincerely").strip(),
        "signature":         request.form.get("signature", "Your Name").strip(),
    }
    html = render_template("letter_template.html", **context)
    fname = f"{doc_number}_{_safe_filename(context['recipient_name'])}.pdf"
    _save_pdf(html, os.path.join(DOC_FOLDERS["letter"], fname))
    return Response(html, mimetype="text/html")
