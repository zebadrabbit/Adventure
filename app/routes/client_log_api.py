"""Client error logging endpoint.

Lightweight endpoint to accept client-side JS error reports. Stores only in
server logs for now (no persistence) to aid debugging of front-end runtime
issues.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

bp_client_log = Blueprint("client_log", __name__)


@bp_client_log.route("/api/client/log", methods=["POST"])
def client_log():  # pragma: no cover - side-effect logging
    try:
        data = request.get_json(force=True, silent=True) or {}
    except Exception:
        data = {"_parse_error": True}
    # Basic size guard
    msg = str(data)[:1000]
    current_app.logger.info("client_log: %s", msg)
    return jsonify({"ok": True})
