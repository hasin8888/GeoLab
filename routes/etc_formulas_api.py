"""
routes/etc_formulas_api.py

Serves every locally verified center's barycentric formula to the browser,
translated into a tiny JavaScript expression, so the geometry workspace
(static/geometry/) can place ANY verified center X(n) on a triangle and
keep it LIVE while the triangle's vertices are dragged.

    GET /api/center-formulas

JSON response:
    status   "ok"
    count    number of centers served
    centers  [{"id": 2, "name": "Centroid", "js": "[1.0,1.0,1.0]"}, ...]

`js` evaluates (with a, b, c = side lengths and A, B, C = angles in radians
in scope) to the 3 barycentric weights. It is generated here from the
formula's parsed Python AST -- after the same whitelist check used by
centers.safe_eval_formula -- never by pasting the stored string, so the
browser only ever receives numbers, + - * /, parentheses, and calls to a
fixed list of math functions.
"""

import ast
import os

from flask import Blueprint, jsonify

from centers import DB_PATH, TriangleCenterError, _validate_ast
from .centers_api import get_db

bp = Blueprint("etc_formulas", __name__)

_BINOPS = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}


def formula_to_js(formula: str) -> str:
    """Translate a "(expr, expr, expr)" formula string to a JavaScript
    array expression. Raises TriangleCenterError / ValueError if the
    formula is not a plain 3-tuple of whitelisted arithmetic."""
    tree = ast.parse(formula, mode="eval")
    _validate_ast(tree)
    if not isinstance(tree.body, ast.Tuple) or len(tree.body.elts) != 3:
        raise ValueError("formula is not a 3-tuple")
    return _js(tree.body)


def _js(node) -> str:
    if isinstance(node, ast.Tuple):
        return "[" + ",".join(_js(e) for e in node.elts) + "]"
    if isinstance(node, ast.Constant):
        v = node.value
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError("non-numeric constant")
        return repr(float(v))
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            return "(-" + _js(node.operand) + ")"
        if isinstance(node.op, ast.UAdd):
            return "(+" + _js(node.operand) + ")"
        raise ValueError("unsupported unary operator")
    if isinstance(node, ast.BinOp):
        left, right = _js(node.left), _js(node.right)
        if type(node.op) in _BINOPS:
            return f"({left}{_BINOPS[type(node.op)]}{right})"
        # `**` and `%` need helper functions: JS `**` rejects a bare unary
        # minus on the left (-a**2) and `%` rounds differently for negatives.
        if isinstance(node.op, ast.Pow):
            return f"pow({left},{right})"
        if isinstance(node.op, ast.Mod):
            return f"mod({left},{right})"
        raise ValueError("unsupported binary operator")
    if isinstance(node, ast.Call):
        if node.keywords or not isinstance(node.func, ast.Name):
            raise ValueError("unsupported call")
        return node.func.id + "(" + ",".join(_js(a) for a in node.args) + ")"
    raise ValueError(f"unsupported node {type(node).__name__}")


@bp.route("/api/center-formulas")
def api_center_formulas():
    if not os.path.exists(DB_PATH):
        return jsonify({
            "status": "error",
            "error_code": "DATABASE_NOT_FOUND",
            "message": f"Database not found at '{DB_PATH}'. Run setup_db.py first.",
        }), 500

    with get_db() as conn:
        rows = conn.execute(
            "SELECT kimberling_id, name, barycentric FROM triangle_centers "
            "ORDER BY kimberling_id"
        ).fetchall()

    centers = []
    for row in rows:
        try:
            js = formula_to_js(row["barycentric"])
        except (TriangleCenterError, ValueError, SyntaxError):
            continue  # a formula we can't translate safely is simply not offered
        centers.append({"id": row["kimberling_id"], "name": row["name"], "js": js})
    return jsonify({"status": "ok", "count": len(centers), "centers": centers})
