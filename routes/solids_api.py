"""
routes/solids_api.py

3D solid endpoints. The solid table lives in dispatch.py (shared with the
command line); this file is only the HTTP layer.
"""

from flask import Blueprint, jsonify, request

from dispatch import SOLID_HANDLERS, run_solid  # noqa: F401  (re-exported)
from solids import SUPPORTED_SOLIDS

bp = Blueprint("solids", __name__)


@bp.route("/solids")
def list_solids():
    return jsonify({"status": "ok", "supported_solids": SUPPORTED_SOLIDS})


@bp.route("/solid/<solid_type>")
def get_solid(solid_type):
    payload, status = run_solid(solid_type, request.args)
    return jsonify(payload), status
