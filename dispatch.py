"""
dispatch.py

Shared "which function do I call for this shape / solid / theorem?" logic.

Both front ends use this module, so the rules live in exactly one place:

    - the Flask routes   (routes/shapes_api.py, solids_api.py, theorems_api.py)
    - the command line   (main.py)

Each handler receives a mapping with a `.get(key)` method and `in` support --
Flask's `request.args` or a plain dict of CLI `--param` values both work --
and returns a result dict, or raises ShapeError / SolidError / TheoremError.

To add a new shape / solid / theorem: write the engine function in
shapes.py / solids.py / triangle_theorems.py, then add ONE entry to the
matching *_HANDLERS table below. The API and the CLI both pick it up.

The run_shape / run_solid / run_theorem helpers wrap the lookup and the error
handling and return (payload, http_status). The CLI ignores the status.
"""

import ast
import math
from typing import Any, Callable, Dict, Tuple

from centers import TriangleCenterError
from shapes import (
    ShapeError,
    SUPPORTED_SHAPES,
    circle_from_radius,
    circle_from_diameter,
    circle_from_circumference,
    ellipse,
    circle_sector,
    circle_segment,
    triangle_from_sides,
    isosceles_triangle,
    equilateral_triangle,
    rectangle,
    square,
    parallelogram,
    rhombus_from_diagonals,
    trapezoid,
    regular_polygon,
    polygon_from_vertices,
    polygon_from_sides_and_angles,
    cyclic_polygon_from_sides,
)
from solids import (
    SolidError,
    SUPPORTED_SOLIDS,
    sphere,
    hemisphere,
    spherical_cap,
    ellipsoid,
    torus,
    cube,
    cuboid,
    cylinder,
    cone,
    truncated_cone,
    square_pyramid,
    regular_pyramid,
    regular_prism,
    triangular_prism,
    tetrahedron,
    octahedron,
    dodecahedron,
    icosahedron,
)
from triangle_theorems import (
    TheoremError,
    SUPPORTED_THEOREMS,
    solve_sine_rule,
    solve_cosine_rule,
    tangent_rule_check,
    ceva_check,
    menelaus_check,
)

Result = Tuple[Dict[str, Any], int]


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

MAX_RAW_LEN = 2000  # longest point/triangle string we are willing to parse


def _literal_list(raw: str):
    """ast.literal_eval(f"[{raw}]") with a length cap. Deeply nested input
    can raise RecursionError / MemoryError, which callers turn into a clean
    error (they are caught alongside ValueError / SyntaxError)."""
    if not isinstance(raw, str) or len(raw) > MAX_RAW_LEN:
        raise ValueError(f"input is too long (max {MAX_RAW_LEN} characters)")
    return ast.literal_eval(f"[{raw}]")


def _finite_float(v) -> float:
    f = float(v)
    if not math.isfinite(f):
        raise ValueError(f"coordinate {v!r} is not a finite number")
    return f


def parse_triangle(raw: str):
    """Parse a string like '(0,0),(4,0),(0,3)' into three (x, y) float tuples."""
    try:
        parsed = _literal_list(raw)
        if len(parsed) != 3:
            raise ValueError("Expected exactly 3 vertices.")
        points = []
        for p in parsed:
            if len(p) != 2:
                raise ValueError("Each vertex must have exactly 2 coordinates.")
            points.append((_finite_float(p[0]), _finite_float(p[1])))
        return points
    except (ValueError, SyntaxError, TypeError, IndexError, RecursionError, MemoryError) as exc:
        raise TriangleCenterError(
            "INVALID_TRIANGLE_INPUT",
            f"Could not parse triangle vertices: {exc}",
        )


def _parse_points(raw: str):
    """Parse '(x1,y1),(x2,y2),...' into a list of (x, y) float tuples."""
    try:
        parsed = _literal_list(raw)
        return [(_finite_float(p[0]), _finite_float(p[1])) for p in parsed]
    except (ValueError, SyntaxError, TypeError, IndexError, RecursionError, MemoryError) as exc:
        raise ShapeError(
            "INVALID_VALUE", f"Could not parse points: {exc}"
        )


def _float_list(raw: str, what: str):
    try:
        return [float(s.strip()) for s in raw.split(",")]
    except ValueError as exc:
        raise ShapeError("INVALID_VALUE", f"Could not parse {what}: {exc}")


def _float_or_none(args, key):
    """Parse a float parameter, or raise a clear error instead of letting a
    bad value (e.g. a=abc) surface as an unrelated 500 error."""
    val = args.get(key)
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        raise TheoremError("INVALID_VALUE", f"'{key}' must be a number, got: {val!r}")


# ---------------------------------------------------------------------------
# 2D shapes
# ---------------------------------------------------------------------------

def _shape_circle(args):
    if "radius" in args:
        return circle_from_radius(args.get("radius"))
    if "diameter" in args:
        return circle_from_diameter(args.get("diameter"))
    if "circumference" in args:
        return circle_from_circumference(args.get("circumference"))
    raise ShapeError(
        "MISSING_VALUE",
        "Provide one of: 'radius', 'diameter', 'circumference'.",
    )


def _shape_polygon(args):
    points_raw = args.get("points")
    if not points_raw:
        raise ShapeError(
            "MISSING_VALUE",
            "Provide 'points', e.g. points=(0,0),(4,0),(4,3),(0,3)",
        )
    return polygon_from_vertices(_parse_points(points_raw))


def _shape_polygon_from_sides_angles(args):
    sides_raw = args.get("sides")
    angles_raw = args.get("angles_degrees")
    if not sides_raw or not angles_raw:
        raise ShapeError(
            "MISSING_VALUE",
            "Provide 'sides' and 'angles_degrees' as comma-separated "
            "lists, e.g. sides=5,5,5,5,5 angles_degrees=108,108,108,108,108",
        )
    return polygon_from_sides_and_angles(
        _float_list(sides_raw, "sides"), _float_list(angles_raw, "angles")
    )


def _shape_cyclic_polygon(args):
    sides_raw = args.get("sides")
    if not sides_raw:
        raise ShapeError(
            "MISSING_VALUE",
            "Provide 'sides' as a comma-separated list, e.g. sides=4,5,6,7",
        )
    return cyclic_polygon_from_sides(_float_list(sides_raw, "sides"))


SHAPE_HANDLERS: Dict[str, Callable] = {
    "circle": _shape_circle,
    "ellipse": lambda a: ellipse(a.get("semi_major"), a.get("semi_minor")),
    "circle_sector": lambda a: circle_sector(a.get("radius"), a.get("angle_degrees")),
    "circle_segment": lambda a: circle_segment(a.get("radius"), a.get("angle_degrees")),
    "triangle": lambda a: triangle_from_sides(a.get("a"), a.get("b"), a.get("c")),
    "isosceles_triangle": lambda a: isosceles_triangle(a.get("leg"), a.get("base")),
    "equilateral_triangle": lambda a: equilateral_triangle(a.get("side")),
    "rectangle": lambda a: rectangle(a.get("length"), a.get("width")),
    "square": lambda a: square(a.get("side")),
    "parallelogram": lambda a: parallelogram(a.get("base"), a.get("side"), a.get("height")),
    "rhombus": lambda a: rhombus_from_diagonals(a.get("d1"), a.get("d2")),
    "trapezoid": lambda a: trapezoid(
        a.get("base1"), a.get("base2"), a.get("height"),
        a.get("side1"), a.get("side2"),
    ),
    "regular_polygon": lambda a: regular_polygon(a.get("num_sides"), a.get("side_length")),
    "polygon": _shape_polygon,
    "polygon_from_sides_angles": _shape_polygon_from_sides_angles,
    "cyclic_polygon": _shape_cyclic_polygon,
}


# ---------------------------------------------------------------------------
# 3D solids
# ---------------------------------------------------------------------------

SOLID_HANDLERS: Dict[str, Callable] = {
    "sphere": lambda a: sphere(a.get("radius")),
    "hemisphere": lambda a: hemisphere(a.get("radius")),
    "spherical_cap": lambda a: spherical_cap(a.get("radius"), a.get("height")),
    "ellipsoid": lambda a: ellipsoid(a.get("a"), a.get("b"), a.get("c")),
    "torus": lambda a: torus(a.get("major_radius"), a.get("minor_radius")),
    "cube": lambda a: cube(a.get("side")),
    "cuboid": lambda a: cuboid(a.get("length"), a.get("width"), a.get("height")),
    "cylinder": lambda a: cylinder(a.get("radius"), a.get("height")),
    "cone": lambda a: cone(a.get("radius"), a.get("height")),
    "truncated_cone": lambda a: truncated_cone(
        a.get("bottom_radius"), a.get("top_radius"), a.get("height")
    ),
    "square_pyramid": lambda a: square_pyramid(a.get("base_side"), a.get("height")),
    "regular_pyramid": lambda a: regular_pyramid(
        a.get("num_sides"), a.get("base_side"), a.get("height")
    ),
    "regular_prism": lambda a: regular_prism(
        a.get("num_sides"), a.get("base_side"), a.get("height")
    ),
    "triangular_prism": lambda a: triangular_prism(
        a.get("a"), a.get("b"), a.get("c"), a.get("height")
    ),
    "tetrahedron": lambda a: tetrahedron(a.get("edge")),
    "octahedron": lambda a: octahedron(a.get("edge")),
    "dodecahedron": lambda a: dodecahedron(a.get("edge")),
    "icosahedron": lambda a: icosahedron(a.get("edge")),
}


# ---------------------------------------------------------------------------
# Triangle theorems
# ---------------------------------------------------------------------------

THEOREM_HANDLERS: Dict[str, Callable] = {
    "sine_rule": lambda a: solve_sine_rule(
        a=_float_or_none(a, "a"),
        b=_float_or_none(a, "b"),
        angle_A_degrees=_float_or_none(a, "angle_A_degrees"),
        angle_B_degrees=_float_or_none(a, "angle_B_degrees"),
    ),
    "cosine_rule": lambda a: solve_cosine_rule(
        a=_float_or_none(a, "a"),
        b=_float_or_none(a, "b"),
        c=_float_or_none(a, "c"),
        angle_C_degrees=_float_or_none(a, "angle_C_degrees"),
    ),
    "tangent_rule": lambda a: tangent_rule_check(
        a=a.get("a"), b=a.get("b"),
        angle_A_degrees=a.get("angle_A_degrees"),
        angle_B_degrees=a.get("angle_B_degrees"),
    ),
    "ceva": lambda a: ceva_check(
        bd_dc=a.get("bd_dc"), ce_ea=a.get("ce_ea"), af_fb=a.get("af_fb"),
    ),
    "menelaus": lambda a: menelaus_check(
        bd_dc=a.get("bd_dc"), ce_ea=a.get("ce_ea"), af_fb=a.get("af_fb"),
    ),
}


# ---------------------------------------------------------------------------
# Lookup + error handling, shared by the API and the CLI
# ---------------------------------------------------------------------------

def _run(kind, table, error_type, unknown_code, supported, list_path, name, params) -> Result:
    handler = table.get(name)
    if handler is None:
        return {
            "status": "error",
            "error_code": unknown_code,
            "message": f"Unknown {kind} '{name}'. See {list_path} for supported types.",
            f"supported_{kind}s": supported,
        }, 400
    try:
        return handler(params), 200
    except error_type as exc:
        return exc.to_payload(), 400
    except (ValueError, SyntaxError, TypeError, IndexError, RecursionError, MemoryError) as exc:
        # Safety net: malformed input is a clean error, never a traceback / 500.
        return {
            "status": "error",
            "error_code": "INVALID_VALUE",
            "message": f"Could not parse the given parameters: {exc}",
            "details": {},
        }, 400


def run_shape(name: str, params) -> Result:
    return _run("shape", SHAPE_HANDLERS, ShapeError, "UNKNOWN_SHAPE",
                SUPPORTED_SHAPES, "/shapes", name, params)


def run_solid(name: str, params) -> Result:
    return _run("solid", SOLID_HANDLERS, SolidError, "UNKNOWN_SOLID",
                SUPPORTED_SOLIDS, "/solids", name, params)


def run_theorem(name: str, params) -> Result:
    return _run("theorem", THEOREM_HANDLERS, TheoremError, "UNKNOWN_THEOREM",
                SUPPORTED_THEOREMS, "/theorems", name, params)
