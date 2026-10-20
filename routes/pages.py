"""
routes/pages.py

HTML pages plus the JSON index of every API endpoint.
"""

from flask import Blueprint, jsonify, render_template

from etc_lookup import MAX_KNOWN_ID

bp = Blueprint("pages", __name__)


@bp.route("/")
def home_page():
    """The single entry point: links to every page in the project."""
    return render_template("home.html")


@bp.route("/api")
def home():
    return jsonify({
        "status": "ok",
        "message": "Triangle Centers API is running.",
        "endpoints": {
            "GET /centers": "List locally verified Kimberling centers (support calculation). "
                            "Optional ?q=<text> filters by name, e.g. /centers?q=centroid.",
            "GET /info/<id>":
                f"Look up ANY center's name and full definition by Kimberling "
                f"number (1 to {MAX_KNOWN_ID}) -- no triangle required. Merges "
                f"the local verified database (when available) with a live "
                f"fetch from the official Encyclopedia of Triangle Centers "
                f"website, so you get name + description + formulas in one call.",
            "GET /center/<id>?triangle=(x1,y1),(x2,y2),(x3,y3)":
                "Compute a specific center's (x, y) position for a given "
                "triangle. Only available for centers in the local verified "
                "database (see /centers for the list).",
            "GET /shapes":
                "List all supported general 2D shapes and the parameters "
                "each one needs.",
            "GET /shape/<type>?<params>":
                "Compute area, perimeter, and (where applicable) angles for "
                "a general 2D shape: circle, ellipse, circle_sector, "
                "circle_segment, triangle, rectangle, square, "
                "parallelogram, rhombus, trapezoid, regular_polygon, or "
                "polygon. See /shapes for required parameters per shape.",
            "GET /solids":
                "List all supported 3D solids and the parameters each one needs.",
            "GET /solid/<type>?<params>":
                "Compute volume and surface area for a 3D solid: sphere, "
                "cube, cuboid, cylinder, cone, or square_pyramid. See "
                "/solids for required parameters per solid.",
            "GET /theorems":
                "List all supported triangle theorems and the parameters "
                "each one needs.",
            "GET /theorem/<type>?<params>":
                "Apply a classic triangle theorem: sine_rule, cosine_rule, "
                "tangent_rule, ceva, or menelaus. See /theorems for "
                "required parameters per theorem.",
            "GET /solver":
                "Coordinate-free triangle problem solver (web page).",
            "POST /api/solve":
                "Solve a triangle from any known lengths/angles/radii. Body: "
                "{\"given\": {\"a\": 13, \"b\": 14, \"c\": 15}, \"want\": [\"R\"]}. "
                "Angles in degrees; returns given / notation / steps / conclusion.",
        },
        "example_info": "/info/12345",
        "example_center": "/center/1?triangle=(0,0),(4,0),(0,3)",
        "example_shape": "/shape/circle?radius=5",
        "example_solid": "/solid/sphere?radius=3",
    })


@bp.route("/geometry")
def geometry_page():
    """Interactive geometry workspace: Move, Point, Segment, Line, Polygon,
    Circle, Select, Show/Hide Label, Show/Hide Object, Delete tools."""
    return render_template("geometry.html")


@bp.route("/solver")
def solver_page():
    """Coordinate-free triangle problem solver (sides / angles / radii only)."""
    return render_template("solver.html")


@bp.route("/app")
def full_app():
    """Full single-page frontend: Center Library, Encyclopedia,
    Shapes, Solids, and Theorems -- all wired to this Flask API."""
    return render_template("app.html")
