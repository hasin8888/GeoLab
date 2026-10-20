"""
routes/compare_api.py

Compare every locally verified center for one triangle, and find which of
them lie on a common line (e.g. X(2), X(3), X(4), X(5) on the Euler line).

    GET /api/compare?triangle=(x1,y1),(x2,y2),(x3,y3)
    GET /api/compare.csv?triangle=...        (same data as a CSV download)

JSON response:
    centers          every verified center with its (x, y) position
    collinear_groups every maximal set of 3+ distinct points on one line
    coincident       centers that land on exactly the same point
    skipped          centers undefined / at infinity for this triangle
"""

import csv
import io
import math
import os

from flask import Blueprint, Response, jsonify, request

from centers import Triangle, TriangleCenterError, safe_eval_formula, DB_PATH
from .centers_api import get_db, parse_triangle

bp = Blueprint("compare", __name__)

# Relative tolerance: a point counts as "on the line" if it is within this
# fraction of the triangle's longest side from it.
_REL_TOL = 1e-7

# Well-known lines, recognised when a group contains these center numbers.
_KNOWN_LINES = (
    ({2, 3, 4}, "Euler line"),
    ({1, 2, 8}, "Nagel line"),
)


def compute_all_centers(tri: Triangle):
    """Return (found, skipped): every verified center that has a finite
    position for this triangle, and the ones that don't."""
    tri.validate()
    a, b, c = tri.side_lengths()
    found, skipped = [], []

    if not os.path.exists(DB_PATH):
        raise TriangleCenterError(
            "DATABASE_NOT_FOUND",
            f"Database not found at '{DB_PATH}'. Run setup_db.py first.",
        )

    with get_db() as conn:
        rows = conn.execute(
            "SELECT kimberling_id, name, barycentric FROM triangle_centers "
            "ORDER BY kimberling_id"
        ).fetchall()

    for row in rows:
        try:
            weights = safe_eval_formula(row["barycentric"], a, b, c)
            x, y = tri.barycentric_to_cartesian(weights)
        except (TriangleCenterError, ZeroDivisionError, OverflowError, ValueError):
            skipped.append({"id": row["kimberling_id"], "name": row["name"]})
            continue
        if not (math.isfinite(x) and math.isfinite(y)):
            skipped.append({"id": row["kimberling_id"], "name": row["name"]})
            continue
        found.append({"id": row["kimberling_id"], "name": row["name"], "x": x, "y": y})
    return found, skipped


def _dist_to_line(p, q, r):
    """Distance from point r to the line through p and q (p != q)."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    return abs(dx * (r[1] - p[1]) - dy * (r[0] - p[0])) / math.hypot(dx, dy)


def find_collinear_groups(centers, scale):
    """Group coincident centers, then return (clusters, groups).

    clusters: list of lists of center dicts that share one position.
    groups:   maximal sets of 3+ DISTINCT positions lying on one line, each
              as a sorted list of center ids (coincident centers included).
    """
    tol = _REL_TOL * scale

    # 1. Merge centers that sit on the same point.
    clusters = []
    for ctr in centers:
        for cl in clusters:
            if math.hypot(cl[0]["x"] - ctr["x"], cl[0]["y"] - ctr["y"]) <= tol:
                cl.append(ctr)
                break
        else:
            clusters.append([ctr])

    pts = [(cl[0]["x"], cl[0]["y"]) for cl in clusters]
    n = len(pts)

    # 2. For every pair of distinct points, collect everything on that line.
    found = set()
    for i in range(n):
        for j in range(i + 1, n):
            members = frozenset(
                k for k in range(n)
                if k in (i, j) or _dist_to_line(pts[i], pts[j], pts[k]) <= tol
            )
            if len(members) >= 3:
                found.add(members)

    # 3. Keep only maximal sets.
    maximal = [g for g in found if not any(g < other for other in found)]

    groups = []
    for g in maximal:
        ids = sorted(ctr["id"] for k in g for ctr in clusters[k])
        groups.append(ids)
    groups.sort(key=lambda ids: (-len(ids), ids))
    return clusters, groups


def _label_for(ids):
    s = set(ids)
    for needed, label in _KNOWN_LINES:
        if needed <= s:
            return label
    return None


def build_comparison(tri: Triangle):
    found, skipped = compute_all_centers(tri)
    a, b, c = tri.side_lengths()
    scale = max(a, b, c)
    clusters, groups = find_collinear_groups(found, scale)

    names = {ctr["id"]: ctr["name"] for ctr in found}
    return {
        "status": "ok",
        "triangle": {"A": tri.A, "B": tri.B, "C": tri.C},
        "side_lengths": {"a": a, "b": b, "c": c},
        "count": len(found),
        "centers": found,
        "coincident": [
            [{"id": ctr["id"], "name": ctr["name"]} for ctr in cl]
            for cl in clusters if len(cl) > 1
        ],
        "collinear_groups": [
            {
                "ids": ids,
                "names": [names[i] for i in ids],
                "label": _label_for(ids),
            }
            for ids in groups
        ],
        "skipped": skipped,
    }


def _parse_request():
    raw = request.args.get("triangle")
    if not raw:
        raise TriangleCenterError(
            "MISSING_TRIANGLE",
            "Provide a 'triangle' query parameter, e.g. "
            "?triangle=(0,0),(4,0),(0,3).",
        )
    pts = parse_triangle(raw)
    return Triangle(A=pts[0], B=pts[1], C=pts[2])


@bp.route("/api/compare")
def api_compare():
    try:
        data = build_comparison(_parse_request())
    except TriangleCenterError as exc:
        status = 500 if exc.code == "DATABASE_NOT_FOUND" else 400
        return jsonify(exc.to_payload()), status
    return jsonify(data), 200


@bp.route("/api/compare.csv")
def api_compare_csv():
    try:
        data = build_comparison(_parse_request())
    except TriangleCenterError as exc:
        status = 500 if exc.code == "DATABASE_NOT_FOUND" else 400
        return jsonify(exc.to_payload()), status

    on_line = {}
    for grp in data["collinear_groups"]:
        tag = grp["label"] or "line"
        for i in grp["ids"]:
            on_line.setdefault(i, []).append(f"{tag} [{'-'.join('X' + str(k) for k in grp['ids'])}]")

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "name", "x", "y", "collinear_with"])
    for ctr in data["centers"]:
        writer.writerow([
            f"X({ctr['id']})", ctr["name"],
            f"{ctr['x']:.10g}", f"{ctr['y']:.10g}",
            "; ".join(on_line.get(ctr["id"], [])),
        ])
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=triangle_centers.csv"},
    )
