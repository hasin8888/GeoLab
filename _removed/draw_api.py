"""
routes/draw_api.py

The /draw page and its data endpoint:

    GET /api/construction?triangle=(x1,y1),(x2,y2),(x3,y3)

returns G, O, I, H, N, the Euler line, the three circles, and the position
of every verified Kimberling center from the local database (best effort --
a center that is undefined for this triangle is simply skipped).
"""

import os

from flask import Blueprint, jsonify, render_template, request

from centers import Triangle, TriangleCenterError, safe_eval_formula, DB_PATH
from construction import build_construction
from .centers_api import get_db, parse_triangle

bp = Blueprint("draw", __name__)


def _verified_centers(tri: Triangle):
    """Positions of all centers in the local verified database."""
    if not os.path.exists(DB_PATH):
        return []
    a, b, c = tri.side_lengths()
    found = []
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT kimberling_id, name, barycentric FROM triangle_centers "
                "ORDER BY kimberling_id"
            ).fetchall()
    except Exception:  # table missing etc. -- the page still works without these
        return []
    for row in rows:
        try:
            weights = safe_eval_formula(row["barycentric"], a, b, c)
            x, y = tri.barycentric_to_cartesian(weights)
        except TriangleCenterError:
            continue  # undefined / at infinity for this triangle
        found.append({"id": row["kimberling_id"], "name": row["name"], "x": x, "y": y})
    return found


@bp.route("/draw")
def draw_page():
    return render_template("draw.html")


@bp.route("/api/construction")
def api_construction():
    raw = request.args.get("triangle")
    if not raw:
        return jsonify({
            "status": "error",
            "error_code": "MISSING_TRIANGLE",
            "message": "Provide a 'triangle' query parameter, e.g. "
                       "?triangle=(0,0),(4,0),(0,3).",
        }), 400
    try:
        pts = parse_triangle(raw)
        tri = Triangle(A=pts[0], B=pts[1], C=pts[2])
        data = build_construction(tri)
    except TriangleCenterError as exc:
        return jsonify(exc.to_payload()), 400
    data["verified_centers"] = _verified_centers(tri)
    return jsonify(data), 200
