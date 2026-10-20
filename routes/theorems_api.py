"""
routes/theorems_api.py

Triangle-theorem endpoints. The theorem table lives in dispatch.py (shared
with the command line); this file is only the HTTP layer.
"""

from flask import Blueprint, jsonify, request

from dispatch import THEOREM_HANDLERS, run_theorem  # noqa: F401  (re-exported)
from triangle_theorems import SUPPORTED_THEOREMS

bp = Blueprint("theorems", __name__)


@bp.route("/theorems")
def list_theorems():
    return jsonify({"status": "ok", "supported_theorems": SUPPORTED_THEOREMS})


@bp.route("/theorem/<theorem_type>")
def get_theorem(theorem_type):
    payload, status = run_theorem(theorem_type, request.args)
    return jsonify(payload), status
