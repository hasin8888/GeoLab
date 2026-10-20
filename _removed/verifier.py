"""
verifier.py

Numeric statement/conjecture verifier for the geometry project.

The idea: you give it (a) a diagram -- a named set of points with concrete
(x, y) coordinates -- and (b) a statement (an equation) to check, optionally
built out of named intermediate "measures" (r, r2, r3, m, n, u, ... -- exactly
the style used in problem_statement.py). It evaluates both sides of the
statement numerically and reports whether they match.

This does NOT prove anything symbolically -- it is a *falsifier* /
*sanity-checker*: if the two sides disagree for a concrete diagram, the
statement is definitely not a general theorem. If they agree across several
independently-built diagrams, that's good evidence (not proof) that it's
worth pursuing a real proof for.

Supported geometry functions, callable only on point *labels* (not
arbitrary sub-expressions):
    dist(P, Q)            distance between two points
    area(P, Q, R)          area of triangle PQR
    perimeter(P, Q, R)      perimeter of triangle PQR
    inradius(P, Q, R)       inradius of triangle PQR
    circumradius(P, Q, R)   circumradius of triangle PQR
    angle(P, Q, R)          angle at vertex Q (i.e. angle PQR), in degrees

A "measures" dict maps a short name (r, r2, m, ...) to an expression built
from the functions above and arithmetic (+ - * / ** and parentheses), e.g.:

    measures = {
        "r":  "inradius(A, B, C)",
        "r2": "inradius(A, B, P)",
        "r3": "inradius(A, P, C)",
        "m":  "dist(B, P)",
        "n":  "dist(P, C)",
        "u":  "dist(A, P)",
    }
    statement = "1/r2 + 1/r3 = 2/r + u*(m+n)/(m*n*r)"

Everything is evaluated with a restricted AST walker -- no eval()/exec(),
mirroring the safe-evaluation approach already used in centers.py.
"""

from __future__ import annotations

import ast
import math
from typing import Any, Dict, List, Tuple

Point = Tuple[float, float]


class VerifierError(Exception):
    """Same status/error_code/message/details shape used elsewhere in this project."""

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
# Geometry primitives (operate on plain (x, y) tuples)
# ---------------------------------------------------------------------------

def _dist(P: Point, Q: Point) -> float:
    return math.hypot(P[0] - Q[0], P[1] - Q[1])


def _side_lengths(P: Point, Q: Point, R: Point) -> Tuple[float, float, float]:
    """Sides opposite P, Q, R respectively: p = QR, q = PR, r = PQ."""
    return _dist(Q, R), _dist(P, R), _dist(P, Q)


def _area(P: Point, Q: Point, R: Point) -> float:
    return abs((Q[0] - P[0]) * (R[1] - P[1]) - (R[0] - P[0]) * (Q[1] - P[1])) / 2.0


def _perimeter(P: Point, Q: Point, R: Point) -> float:
    return sum(_side_lengths(P, Q, R))


def _inradius(P: Point, Q: Point, R: Point) -> float:
    area = _area(P, Q, R)
    s = _perimeter(P, Q, R) / 2.0
    if s == 0:
        raise VerifierError("DEGENERATE_TRIANGLE", "Triangle has zero perimeter.")
    return area / s


def _circumradius(P: Point, Q: Point, R: Point) -> float:
    p, q, r = _side_lengths(P, Q, R)
    area = _area(P, Q, R)
    if area == 0:
        raise VerifierError(
            "DEGENERATE_TRIANGLE", "Points are collinear; circumradius is undefined."
        )
    return (p * q * r) / (4.0 * area)


def _angle_deg(P: Point, Q: Point, R: Point) -> float:
    """Angle at vertex Q, i.e. the angle PQR, in degrees."""
    v1 = (P[0] - Q[0], P[1] - Q[1])
    v2 = (R[0] - Q[0], R[1] - Q[1])
    n1 = math.hypot(*v1)
    n2 = math.hypot(*v2)
    if n1 == 0 or n2 == 0:
        raise VerifierError(
            "DEGENERATE_TRIANGLE", "Cannot measure an angle at a repeated point."
        )
    cos_theta = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    cos_theta = max(-1.0, min(1.0, cos_theta))  # guard tiny float overshoot
    return math.degrees(math.acos(cos_theta))


# name -> (function, expected number of point arguments)
_GEOM_FUNCS = {
    "dist": (_dist, 2),
    "area": (_area, 3),
    "perimeter": (_perimeter, 3),
    "inradius": (_inradius, 3),
    "circumradius": (_circumradius, 3),
    "angle": (_angle_deg, 3),
}

_ALLOWED_BINOPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.Pow: lambda a, b: a ** b,
}
_ALLOWED_UNARYOPS = {
    ast.UAdd: lambda a: +a,
    ast.USub: lambda a: -a,
}


# ---------------------------------------------------------------------------
# Safe expression evaluator
# ---------------------------------------------------------------------------

def _eval_node(node: ast.AST, points: Dict[str, Point], measures: Dict[str, float]) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, points, measures)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return float(node.value)
        raise VerifierError("UNSUPPORTED_SYNTAX", f"Unsupported constant: {node.value!r}")

    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        left = _eval_node(node.left, points, measures)
        right = _eval_node(node.right, points, measures)
        try:
            return _ALLOWED_BINOPS[type(node.op)](left, right)
        except ZeroDivisionError:
            raise VerifierError("DIVISION_BY_ZERO", "Expression divides by zero.")

    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return _ALLOWED_UNARYOPS[type(node.op)](_eval_node(node.operand, points, measures))

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _GEOM_FUNCS:
            name = getattr(node.func, "id", "<expr>")
            raise VerifierError(
                "UNKNOWN_FUNCTION",
                f"'{name}' is not a supported function. Supported: "
                f"{', '.join(sorted(_GEOM_FUNCS))}.",
            )
        func, arity = _GEOM_FUNCS[node.func.id]
        if node.keywords:
            raise VerifierError("UNSUPPORTED_SYNTAX", "Keyword arguments are not supported.")
        if len(node.args) != arity:
            raise VerifierError(
                "WRONG_ARITY",
                f"{node.func.id}(...) expects {arity} point argument(s), "
                f"got {len(node.args)}.",
            )
        point_args = []
        for arg in node.args:
            if not isinstance(arg, ast.Name):
                raise VerifierError(
                    "INVALID_ARGUMENT",
                    f"Arguments to {node.func.id}(...) must be point labels "
                    f"(e.g. {node.func.id}(A, B{', C' if arity == 3 else ''})).",
                )
            if arg.id not in points:
                raise VerifierError(
                    "UNKNOWN_POINT",
                    f"Point '{arg.id}' is not defined in the diagram.",
                    details={"point": arg.id, "known_points": sorted(points)},
                )
            point_args.append(points[arg.id])
        return func(*point_args)

    if isinstance(node, ast.Name):
        if node.id in measures:
            return measures[node.id]
        if node.id in points:
            raise VerifierError(
                "POINT_USED_AS_NUMBER",
                f"'{node.id}' is a point, not a number -- wrap it in a function, "
                f"e.g. dist({node.id}, OtherPoint).",
            )
        raise VerifierError(
            "UNKNOWN_NAME",
            f"'{node.id}' is not a known measure or constant.",
            details={"name": node.id, "known_measures": sorted(measures)},
        )

    raise VerifierError("UNSUPPORTED_SYNTAX", f"Unsupported expression: {ast.dump(node)}")


def _parse(expr: str) -> ast.AST:
    try:
        return ast.parse(expr.strip(), mode="eval")
    except SyntaxError as exc:
        raise VerifierError(
            "INVALID_EXPRESSION",
            f"Could not parse '{expr}' as a formula: {exc}. If this was meant "
            "as plain English rather than a math expression, it can't be "
            "auto-verified here -- formalize it as an equation over the "
            "available measures/points, or discuss it directly in chat instead.",
        )


def _eval_expr(expr: str, points: Dict[str, Point], measures: Dict[str, float]) -> float:
    return _eval_node(_parse(expr).body, points, measures)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _normalize_points(raw_points: Dict[str, Any]) -> Dict[str, Point]:
    if not isinstance(raw_points, dict) or not raw_points:
        raise VerifierError(
            "MISSING_POINTS", "Provide a non-empty 'points' object, e.g. "
            '{"A": [0, 4], "B": [0, 0], "C": [6, 0]}.'
        )
    points: Dict[str, Point] = {}
    for label, coords in raw_points.items():
        try:
            x, y = coords
            points[label] = (float(x), float(y))
        except (TypeError, ValueError, IndexError):
            raise VerifierError(
                "INVALID_POINT",
                f"Point '{label}' must be a [x, y] pair of numbers, got {coords!r}.",
                details={"point": label},
            )
    return points


def evaluate_measures(
    points: Dict[str, Point], measures: Dict[str, str]
) -> Dict[str, float]:
    """Evaluate each named measure in order, so later measures may reference
    earlier ones (e.g. m, n, u are point-derived; a later measure could combine them)."""
    computed: Dict[str, float] = {}
    for name, expr in (measures or {}).items():
        if not isinstance(expr, str) or not expr.strip():
            raise VerifierError(
                "INVALID_MEASURE", f"Measure '{name}' must be a non-empty formula string."
            )
        computed[name] = _eval_expr(expr, points, computed)
    return computed


def verify_statement(
    raw_points: Dict[str, Any],
    measures: Dict[str, str],
    statement: str,
    tolerance: float = 1e-6,
) -> Dict[str, Any]:
    """Verify one statement against one concrete diagram. Returns a
    structured result; raises VerifierError on malformed input."""
    if not isinstance(statement, str) or "=" not in statement:
        raise VerifierError(
            "INVALID_STATEMENT",
            "Statement must be an equation containing exactly one '=', e.g. "
            "'1/r2 + 1/r3 = 2/r + u*(m+n)/(m*n*r)'. Plain-English statements "
            "aren't auto-verifiable -- formalize them as an equation first, "
            "or ask about them directly in chat.",
        )
    if statement.count("=") != 1:
        raise VerifierError(
            "INVALID_STATEMENT", "Statement must contain exactly one '=' sign."
        )

    points = _normalize_points(raw_points)
    computed_measures = evaluate_measures(points, measures)

    lhs_str, rhs_str = statement.split("=")
    lhs_val = _eval_expr(lhs_str, points, computed_measures)
    rhs_val = _eval_expr(rhs_str, points, computed_measures)

    diff = lhs_val - rhs_val
    scale = max(1.0, abs(lhs_val), abs(rhs_val))
    holds = abs(diff) <= tolerance * scale

    return {
        "status": "ok",
        "statement": statement,
        "points": {k: list(v) for k, v in points.items()},
        "measures": computed_measures,
        "lhs_value": lhs_val,
        "rhs_value": rhs_val,
        "difference": diff,
        "holds": holds,
        "tolerance": tolerance,
    }


def verify_statement_over_diagrams(
    diagrams: List[Dict[str, Any]],
    measures: Dict[str, str],
    statement: str,
    tolerance: float = 1e-6,
) -> Dict[str, Any]:
    """Run verify_statement across several independent diagrams (e.g. several
    differently-shaped triangles built the same way). A statement that only
    holds for one specific diagram but fails on others is NOT a general
    theorem -- this is exactly the check that catches that."""
    if not isinstance(diagrams, list) or not diagrams:
        raise VerifierError(
            "MISSING_DIAGRAMS", "Provide a non-empty 'diagrams' list of point-sets."
        )

    results = []
    for i, raw_points in enumerate(diagrams):
        try:
            result = verify_statement(raw_points, measures, statement, tolerance)
            results.append({"diagram_index": i, **result})
        except VerifierError as exc:
            results.append({"diagram_index": i, **exc.to_payload()})

    ok_results = [r for r in results if r.get("status") == "ok"]
    holds_for_all = bool(ok_results) and all(r["holds"] for r in ok_results)
    any_errors = len(ok_results) < len(results)

    return {
        "status": "ok",
        "statement": statement,
        "diagram_count": len(diagrams),
        "holds_for_all": holds_for_all,
        "any_errors": any_errors,
        "results": results,
        "verdict": (
            "Holds across every diagram tried -- consistent with (but not proof "
            "of) a general theorem." if holds_for_all and not any_errors else
            "FAILS for at least one diagram -- this is NOT a general theorem "
            "as stated." if ok_results and not holds_for_all else
            "Could not be fully evaluated -- see per-diagram errors."
        ),
    }
