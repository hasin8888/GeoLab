"""
routes/centers_api.py

Triangle-center endpoints: /centers, /info/<id>, /center/<id>, /position/<id>.

The lookup logic for /centers and /info/<id> lives in center_info.py (shared
with the command line); this file is only the HTTP layer for those two.
"""

from flask import Blueprint, jsonify, request

from center_info import get_db, list_verified_centers, lookup_info  # noqa: F401  (get_db re-exported)
from centers import Triangle, compute_center, TriangleCenterError
from dispatch import parse_triangle
from etc_lookup import MAX_KNOWN_ID
from etc_position import locate_center

bp = Blueprint("centers", __name__)


@bp.route("/centers")
def list_centers():
    """List locally verified centers. Optional ?q=<text> filters by a
    case-insensitive substring match on the center's name, e.g.
    /centers?q=centroid."""
    payload, status = list_verified_centers(request.args.get("q", ""))
    return jsonify(payload), status


@bp.route("/info/<int:kimberling_id>")
def get_info(kimberling_id):
    """
    Encyclopedia-style lookup: given ONLY a Kimberling number, return its
    name and full definition/formulas (X(1) to X(84000)). No triangle input
    needed -- this does not compute any (x, y) position. Sources, fastest
    first: verified database, local encyclopedia cache, live ETC fetch (see
    center_info.lookup_info).
    """
    payload, status = lookup_info(kimberling_id)
    return jsonify(payload), status


@bp.route("/center/<int:kimberling_id>")
def get_center(kimberling_id):
    triangle_param = request.args.get("triangle")
    if not triangle_param:
        return jsonify({
            "status": "error",
            "error_code": "MISSING_TRIANGLE",
            "message": "Provide a 'triangle' query parameter, e.g. "
                       "?triangle=(0,0),(4,0),(0,3). If you only want this "
                       "center's definition and formulas (no calculation), "
                       "use /info/<id> instead -- that works for any center "
                       f"from 1 to {MAX_KNOWN_ID}.",
        }), 400

    try:
        points = parse_triangle(triangle_param)
        triangle = Triangle(A=points[0], B=points[1], C=points[2])
        result = compute_center(kimberling_id, triangle)
    except TriangleCenterError as exc:
        result = exc.to_payload()

    if result.get("status") != "ok" and result.get("error_code") == "CENTER_NOT_FOUND":
        result["message"] += (
            " This center may still exist in the full Encyclopedia of "
            f"Triangle Centers -- try /info/{kimberling_id} to look up its "
            "definition (calculation just isn't available for it yet)."
        )

    status_code = 200 if result.get("status") == "ok" else 400
    return jsonify(result), status_code


@bp.route("/position/<int:kimberling_id>")
def get_position(kimberling_id):
    """Where is X(n) on a triangle? Unlike /center/<id> (verified database
    only), this works for any center whose position can be worked out from
    its ETC entry (published formula or a named construction). Used by the
    Encyclopedia page to draw a diagram for every center it looks up."""
    triangle_param = request.args.get("triangle")
    if not triangle_param:
        return jsonify({
            "status": "error",
            "error_code": "MISSING_TRIANGLE",
            "message": "Provide a 'triangle' query parameter, e.g. ?triangle=(0,0),(4,0),(0,3).",
        }), 400
    try:
        points = parse_triangle(triangle_param)
        triangle = Triangle(A=points[0], B=points[1], C=points[2])
    except TriangleCenterError as exc:
        return jsonify(exc.to_payload()), 400

    result = locate_center(kimberling_id, triangle)
    return jsonify(result), (200 if result.get("status") == "ok" else 400)
