"""Debug / diagnostics API endpoints.

Currently exposes:
  GET /api/debug/sockets  (admin only) -> runtime websocket instrumentation snapshot
"""

from __future__ import annotations

from flask import Blueprint, jsonify
from flask_login import current_user

from app.instrumentation.socket_stats import socket_stats

bp_debug = Blueprint("debug_api", __name__, url_prefix="/api/debug")


@bp_debug.get("/sockets")
def debug_sockets():  # pragma: no cover - lightweight admin utility
    if not getattr(current_user, "is_authenticated", False) or getattr(current_user, "role", "user") != "admin":
        return jsonify({"error": "forbidden"}), 403
    return jsonify(socket_stats.snapshot())
