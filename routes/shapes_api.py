"""
routes/shapes_api.py

2D shape endpoints. The shape table and the error handling live in
dispatch.py (shared with the command line); this file is only the HTTP layer.
To add a new shape, add one entry to SHAPE_HANDLERS in dispatch.py.
"""

from flask import Blueprint, jsonify, request

from dispatch import SHAPE_HANDLERS, run_shape  # noqa: F401  (re-exported)
from shapes import SUPPORTED_SHAPES

bp = Blueprint("shapes", __name__)


@bp.route("/shapes")
def list_shapes():
    return jsonify({"status": "ok", "supported_shapes": SUPPORTED_SHAPES})


@bp.route("/shape/<shape_type>")
def get_shape(shape_type):
    payload, status = run_shape(shape_type, request.args)
    return jsonify(payload), status
