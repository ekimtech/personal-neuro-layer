# === Self-Writing Tools Routes — self_writing_server/routes.py ===
# Flask Blueprint — registered at /code_review
# Provides the web UI for approving/rejecting Jarvis's self-improvement suggestions
# Built: 03-19-26

import logging
from flask import Blueprint, render_template, request, jsonify

from mcp_servers_hub.self_writing_server.self_writing_server import (
    get_pending_reviews,
    get_review,
    approve_review,
    remove_review,
    clear_all_reviews,
    review_file,
    start_review_async,
    get_job_status,
)

logger = logging.getLogger("self_writing_server")

self_writing_bp = Blueprint("self_writing_bp", __name__, url_prefix="/code_review")


# ---------------------------------------------------------
# Main UI — pending reviews dashboard
# ---------------------------------------------------------

@self_writing_bp.route("/", methods=["GET"])
@self_writing_bp.route("", methods=["GET"])
def code_review_index():
    reviews = get_pending_reviews()
    return render_template("code_review.html", reviews=reviews)


# ---------------------------------------------------------
# API — trigger a review from the web UI
# ---------------------------------------------------------

@self_writing_bp.route("/api/review", methods=["POST"])
def api_trigger_review():
    """Start an async review job — returns job_id immediately."""
    data = request.get_json(silent=True) or {}
    file_name = data.get("file_name", "").strip()
    if not file_name:
        return jsonify({"error": "file_name is required"}), 400

    job_id = start_review_async(file_name)
    return jsonify({"job_id": job_id, "status": "running"})


@self_writing_bp.route("/api/review/status/<job_id>", methods=["GET"])
def api_review_status(job_id):
    """Poll for async review job status."""
    return jsonify(get_job_status(job_id))


# ---------------------------------------------------------
# API — get a single review's full content
# ---------------------------------------------------------

@self_writing_bp.route("/api/review/<review_id>", methods=["GET"])
def api_get_review(review_id):
    review = get_review(review_id)
    if not review:
        return jsonify({"error": "Review not found"}), 404
    return jsonify(review)


# ---------------------------------------------------------
# API — approve (write to disk)
# ---------------------------------------------------------

@self_writing_bp.route("/api/approve/<review_id>", methods=["POST"])
def api_approve(review_id):
    data = request.get_json(silent=True) or {}
    custom_code = data.get("custom_code") or None
    result = approve_review(review_id, custom_code=custom_code)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


# ---------------------------------------------------------
# API — reject (discard)
# ---------------------------------------------------------

@self_writing_bp.route("/api/reject/<review_id>", methods=["POST"])
def api_reject(review_id):
    success = remove_review(review_id)
    if not success:
        return jsonify({"error": "Review not found"}), 404
    return jsonify({"success": True})


# ---------------------------------------------------------
# API — clear all
# ---------------------------------------------------------

@self_writing_bp.route("/api/clear", methods=["POST"])
def api_clear():
    clear_all_reviews()
    return jsonify({"success": True})


# ---------------------------------------------------------
# API — list all pending (JSON, for polling)
# ---------------------------------------------------------

@self_writing_bp.route("/api/list", methods=["GET"])
def api_list():
    reviews = get_pending_reviews()
    # Return lightweight summary only (no full code)
    summaries = [
        {
            "id":          r["id"],
            "file_name":   r["file_name"],
            "rel_path":    r["rel_path"],
            "explanation": r["explanation"],
            "issue_count": len(r["issues"]),
            "timestamp":   r["timestamp"],
        }
        for r in reviews
    ]
    return jsonify(summaries)
