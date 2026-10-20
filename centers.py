"""
centers.py

Core computational geometry engine for triangle centers.

Responsibilities:
  - Load center definitions from triangle_centers.db
  - Validate triangle vertices (reject degenerate / collinear input)
  - Safely evaluate barycentric formulas (no plain eval on arbitrary code)
  - Convert barycentric weights -> Cartesian (x, y) for a concrete triangle
  - Return structured, JSON-serializable results or descriptive error payloads
"""

import ast
import math
import sqlite3
import os
from dataclasses import dataclass
from typing import Tuple, Dict, Any

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "triangle_centers.db")

# Names allowed inside formula strings. Anything else is rejected.
# Note: a, b, c, A, B, C are plain identifiers supplied at eval time,
# not entries here; this dict only holds constants and whitelisted functions.
_ALLOWED_NAMES = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "sec": lambda x: 1.0 / math.cos(x),
    "csc": lambda x: 1.0 / math.sin(x),
    "cot": lambda x: 1.0 / math.tan(x),
    "pi": math.pi,
}
_ALLOWED_FUNC_NAMES = {k for k, v in _ALLOWED_NAMES.items() if callable(v)}
_ALLOWED_VAR_NAMES = {"a", "b", "c", "A", "B", "C"} | {k for k, v in _ALLOWED_NAMES.items() if not callable(v)}


class TriangleCenterError(Exception):
    """Raised for any recoverable domain error (bad center id, bad triangle, bad formula)."""

    def __init__(self, code: str, message: str, details: Dict[str, Any] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_payload(self) -> Dict[str, Any]:
        return {
            "status": "error",
            "error_code": self.code,
            "message": self.message,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# Safe expression evaluation
# ---------------------------------------------------------------------------

_ALLOWED_AST_NODES = (
    ast.Expression, ast.Tuple, ast.BinOp, ast.UnaryOp, ast.Call, ast.Name,
    ast.Load, ast.Constant,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd, ast.Mod,
)


def _validate_ast(node: ast.AST) -> None:
    """Walk the parsed expression tree and reject anything not explicitly allowed."""
    for child in ast.walk(node):
        if not isinstance(child, _ALLOWED_AST_NODES):
            raise TriangleCenterError(
                "UNSAFE_FORMULA",
                f"Formula contains disallowed syntax: {type(child).__name__}",
            )
        if isinstance(child, ast.Name) and child.id not in _ALLOWED_VAR_NAMES and child.id not in _ALLOWED_FUNC_NAMES:
            raise TriangleCenterError(
                "UNSAFE_FORMULA",
                f"Formula references disallowed identifier: '{child.id}'",
            )
        if isinstance(child, ast.Call):
            if not isinstance(child.func, ast.Name) or child.func.id not in _ALLOWED_FUNC_NAMES:
                raise TriangleCenterError(
                    "UNSAFE_FORMULA",
                    "Formula calls a disallowed function.",
                )


def safe_eval_formula(formula: str, a: float, b: float, c: float) -> Tuple[float, float, float]:
    """
    Safely evaluate a barycentric/trilinear formula string of the form
    "(expr1, expr2, expr3)" using only a, b, c and a whitelist of math
    functions. Raises TriangleCenterError on any parse/evaluation problem.
    """
    try:
        parsed = ast.parse(formula, mode="eval")
    except SyntaxError as exc:
        raise TriangleCenterError(
            "FORMULA_PARSE_ERROR", f"Could not parse formula '{formula}': {exc}"
        )

    _validate_ast(parsed)

    env = {k: v for k, v in _ALLOWED_NAMES.items() if callable(v) or k in ("pi",)}
    env.update({"a": a, "b": b, "c": c})

    try:
        result = eval(compile(parsed, "<formula>", "eval"), {"__builtins__": {}}, env)
    except ZeroDivisionError:
        raise TriangleCenterError(
            "DIVISION_BY_ZERO",
            "Formula evaluation hit a division by zero for this triangle "
            "(often caused by a degenerate or special-case triangle).",
        )
    except Exception as exc:  # noqa: BLE001 - convert any eval failure to a domain error
        raise TriangleCenterError(
            "FORMULA_EVAL_ERROR", f"Error evaluating formula '{formula}': {exc}"
        )

    if not isinstance(result, tuple) or len(result) != 3:
        raise TriangleCenterError(
            "FORMULA_SHAPE_ERROR",
            f"Formula '{formula}' did not evaluate to a 3-tuple.",
        )
    try:
        return tuple(float(v) for v in result)
    except (TypeError, ValueError):
        raise TriangleCenterError(
            "FORMULA_SHAPE_ERROR",
            f"Formula '{formula}' produced non-numeric weights.",
        )


# ---------------------------------------------------------------------------
# Triangle geometry
# ---------------------------------------------------------------------------

@dataclass
class Triangle:
    A: Tuple[float, float]
    B: Tuple[float, float]
    C: Tuple[float, float]

    def side_lengths(self) -> Tuple[float, float, float]:
        """Return (a, b, c) = (|BC|, |CA|, |AB|), the standard convention."""
        def dist(p, q):
            return math.hypot(p[0] - q[0], p[1] - q[1])

        a = dist(self.B, self.C)
        b = dist(self.C, self.A)
        c = dist(self.A, self.B)
        return a, b, c

    def area2(self) -> float:
        """Twice the signed area, via the shoelace formula."""
        (x1, y1), (x2, y2), (x3, y3) = self.A, self.B, self.C
        return (x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)

    def validate(self) -> None:
        for p in (self.A, self.B, self.C):
            if not all(math.isfinite(v) for v in p):
                raise TriangleCenterError(
                    "INVALID_TRIANGLE_INPUT",
                    "Triangle coordinates must be finite numbers (no inf / nan).",
                    details={"A": self.A, "B": self.B, "C": self.C},
                )
        area2 = self.area2()
        if abs(area2) < 1e-9:
            raise TriangleCenterError(
                "DEGENERATE_TRIANGLE",
                "The provided vertices are collinear (or nearly so) and do "
                "not form a valid triangle.",
                details={"A": self.A, "B": self.B, "C": self.C, "signed_area2": area2},
            )
        a, b, c = self.side_lengths()
        for name, length in (("a", a), ("b", b), ("c", c)):
            if length < 1e-9:
                raise TriangleCenterError(
                    "DEGENERATE_TRIANGLE",
                    f"Side '{name}' has (near) zero length; two vertices coincide.",
                    details={"A": self.A, "B": self.B, "C": self.C},
                )

    def barycentric_to_cartesian(self, weights: Tuple[float, float, float]) -> Tuple[float, float]:
        alpha, beta, gamma = weights
        total = alpha + beta + gamma
        if abs(total) < 1e-12:
            raise TriangleCenterError(
                "NORMALIZATION_ERROR",
                "Barycentric weights sum to zero and cannot be normalized "
                "(this triangle center is undefined / at infinity for this triangle).",
                details={"weights": weights},
            )
        alpha, beta, gamma = alpha / total, beta / total, gamma / total
        x = alpha * self.A[0] + beta * self.B[0] + gamma * self.C[0]
        y = alpha * self.A[1] + beta * self.B[1] + gamma * self.C[1]
        return x, y


# ---------------------------------------------------------------------------
# Database access
# ---------------------------------------------------------------------------

def fetch_center(kimberling_id: int, db_path: str = DB_PATH) -> Dict[str, Any]:
    if not os.path.exists(db_path):
        raise TriangleCenterError(
            "DATABASE_NOT_FOUND",
            f"Database file not found at '{db_path}'. Run setup_db.py first.",
        )

    # timeout=5: if another request briefly holds a write lock on the same
    # SQLite file, wait up to 5s instead of failing immediately.
    conn = sqlite3.connect(db_path, timeout=5)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT kimberling_id, name, barycentric, trilinear, etc_notes "
            "FROM triangle_centers WHERE kimberling_id = ?",
            (kimberling_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise TriangleCenterError(
                "CENTER_NOT_FOUND",
                f"Kimberling center X({kimberling_id}) was not found in the database.",
                details={"requested_id": kimberling_id},
            )
        return dict(row)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------

def compute_center(kimberling_id: int, triangle: Triangle, db_path: str = DB_PATH) -> Dict[str, Any]:
    """
    Full pipeline: validate triangle -> fetch center definition -> evaluate
    formula -> convert to Cartesian. Returns a structured success or error
    payload; never raises.
    """
    try:
        triangle.validate()
        record = fetch_center(kimberling_id, db_path=db_path)
        a, b, c = triangle.side_lengths()
        weights = safe_eval_formula(record["barycentric"], a, b, c)
        x, y = triangle.barycentric_to_cartesian(weights)

        return {
            "status": "ok",
            "kimberling_id": kimberling_id,
            "name": record["name"],
            "barycentric_formula": record["barycentric"],
            "trilinear_formula": record["trilinear"],
            "etc_notes": record["etc_notes"],
            "input_triangle": {"A": triangle.A, "B": triangle.B, "C": triangle.C},
            "side_lengths": {"a": a, "b": b, "c": c},
            "barycentric_weights_normalized": weights,
            "cartesian_position": {"x": x, "y": y},
        }
    except TriangleCenterError as exc:
        return exc.to_payload()
