"""
shapes.py

General 2D shape geometry engine.

Responsibilities:
  - Compute area, perimeter, and (where applicable) angles for common
    2D shapes: circle, triangle, rectangle, square, parallelogram,
    rhombus, trapezoid, and regular/general polygons.
  - Validate shape input (reject negative/zero lengths, invalid polygons,
    triangles that don't satisfy the triangle inequality, etc.).
  - Return structured, JSON-serializable results or descriptive error
    payloads -- same conventions as centers.py (ShapeError mirrors
    TriangleCenterError).

This module is intentionally independent of centers.py: centers.py deals
with *triangle centers* (a single specialised problem), while this module
answers general "given this shape's measurements, what is its area /
perimeter / angles?" questions.
"""

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


class ShapeError(Exception):
    """Raised for any recoverable domain error (bad dimensions, invalid shape)."""

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


def _require_positive(name: str, value: float) -> None:
    if value is None:
        raise ShapeError("MISSING_VALUE", f"Missing required value: '{name}'.")
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ShapeError("INVALID_VALUE", f"'{name}' must be a number, got: {value!r}")
    if value <= 0:
        raise ShapeError(
            "INVALID_DIMENSION",
            f"'{name}' must be a positive number, got: {value}.",
            details={name: value},
        )


# ---------------------------------------------------------------------------
# Circle
# ---------------------------------------------------------------------------

def circle_from_radius(radius: float) -> Dict[str, Any]:
    _require_positive("radius", radius)
    r = float(radius)
    area = math.pi * r ** 2
    circumference = 2 * math.pi * r
    diameter = 2 * r
    return {
        "status": "ok",
        "shape": "circle",
        "inputs": {"radius": r},
        "area": area,
        "perimeter": circumference,
        "circumference": circumference,
        "diameter": diameter,
    }


def circle_from_diameter(diameter: float) -> Dict[str, Any]:
    _require_positive("diameter", diameter)
    return circle_from_radius(float(diameter) / 2)


def circle_from_circumference(circumference: float) -> Dict[str, Any]:
    _require_positive("circumference", circumference)
    r = float(circumference) / (2 * math.pi)
    return circle_from_radius(r)


# ---------------------------------------------------------------------------
# Ellipse
# ---------------------------------------------------------------------------

def ellipse(semi_major: float, semi_minor: float) -> Dict[str, Any]:
    """
    semi_major (a) and semi_minor (b) are the two semi-axis lengths.
    Perimeter has no elementary closed form, so Ramanujan's second
    approximation is used -- accurate to a relative error well under
    1e-5 for any ellipse, which is more than sufficient here.
    """
    _require_positive("semi_major", semi_major)
    _require_positive("semi_minor", semi_minor)
    a, b = float(semi_major), float(semi_minor)
    if b > a:
        raise ShapeError(
            "INVALID_DIMENSION",
            "'semi_minor' cannot be greater than 'semi_major' (swap them "
            "if you meant the axes the other way around).",
            details={"semi_major": a, "semi_minor": b},
        )
    area = math.pi * a * b
    h = ((a - b) ** 2) / ((a + b) ** 2)
    perimeter = math.pi * (a + b) * (1 + (3 * h) / (10 + math.sqrt(4 - 3 * h)))
    eccentricity = math.sqrt(1 - (b ** 2) / (a ** 2)) if a > 0 else 0.0
    return {
        "status": "ok",
        "shape": "ellipse",
        "inputs": {"semi_major": a, "semi_minor": b},
        "area": area,
        "perimeter": perimeter,
        "eccentricity": eccentricity,
        "note": "Perimeter uses Ramanujan's second approximation "
                "(no elementary closed form exists for an ellipse).",
    }


# ---------------------------------------------------------------------------
# Circle sector / segment (pie-slice and the region cut off by a chord)
# ---------------------------------------------------------------------------

def circle_sector(radius: float, angle_degrees: float) -> Dict[str, Any]:
    """A 'pie slice' of a circle, defined by radius and central angle."""
    _require_positive("radius", radius)
    if angle_degrees is None:
        raise ShapeError("MISSING_VALUE", "Missing required value: 'angle_degrees'.")
    try:
        angle_degrees = float(angle_degrees)
    except (TypeError, ValueError):
        raise ShapeError(
            "INVALID_VALUE",
            f"'angle_degrees' must be a number, got: {angle_degrees!r}",
        )
    if not (0 < angle_degrees <= 360):
        raise ShapeError(
            "INVALID_DIMENSION",
            "'angle_degrees' must be greater than 0 and at most 360.",
            details={"angle_degrees": angle_degrees},
        )
    r = float(radius)
    angle_rad = math.radians(angle_degrees)
    area = 0.5 * r ** 2 * angle_rad
    arc_length = r * angle_rad
    # Perimeter of the sector = the two straight radii + the curved arc.
    perimeter = 2 * r + arc_length
    return {
        "status": "ok",
        "shape": "circle_sector",
        "inputs": {"radius": r, "angle_degrees": angle_degrees},
        "area": area,
        "perimeter": perimeter,
        "arc_length": arc_length,
    }


def circle_segment(radius: float, angle_degrees: float) -> Dict[str, Any]:
    """
    The region between a chord and the arc it cuts off (a sector minus
    the triangle formed by the two radii and the chord).
    """
    _require_positive("radius", radius)
    if angle_degrees is None:
        raise ShapeError("MISSING_VALUE", "Missing required value: 'angle_degrees'.")
    try:
        angle_degrees = float(angle_degrees)
    except (TypeError, ValueError):
        raise ShapeError(
            "INVALID_VALUE",
            f"'angle_degrees' must be a number, got: {angle_degrees!r}",
        )
    if not (0 < angle_degrees < 360):
        raise ShapeError(
            "INVALID_DIMENSION",
            "'angle_degrees' must be greater than 0 and less than 360 "
            "(360 would be the full circle, with no chord).",
            details={"angle_degrees": angle_degrees},
        )
    r = float(radius)
    angle_rad = math.radians(angle_degrees)
    sector_area = 0.5 * r ** 2 * angle_rad
    triangle_area = 0.5 * r ** 2 * math.sin(angle_rad)
    area = sector_area - triangle_area
    chord_length = 2 * r * math.sin(angle_rad / 2)
    arc_length = r * angle_rad
    return {
        "status": "ok",
        "shape": "circle_segment",
        "inputs": {"radius": r, "angle_degrees": angle_degrees},
        "area": area,
        "perimeter": chord_length + arc_length,
        "chord_length": chord_length,
        "arc_length": arc_length,
    }


# ---------------------------------------------------------------------------
# Triangle (side-based: area, perimeter, and all three angles)
# ---------------------------------------------------------------------------

@dataclass
class TriangleShape:
    a: float
    b: float
    c: float

    def validate(self) -> None:
        for name, val in (("a", self.a), ("b", self.b), ("c", self.c)):
            _require_positive(name, val)
        # Coerce to float now that we know each value is a valid positive
        # number -- callers (CLI/Flask) may have passed strings.
        self.a, self.b, self.c = float(self.a), float(self.b), float(self.c)
        a, b, c = self.a, self.b, self.c
        if not (a + b > c and b + c > a and c + a > b):
            raise ShapeError(
                "INVALID_TRIANGLE",
                "Side lengths do not satisfy the triangle inequality "
                "(the sum of any two sides must exceed the third).",
                details={"a": a, "b": b, "c": c},
            )

    def solve(self) -> Dict[str, Any]:
        self.validate()
        a, b, c = self.a, self.b, self.c
        s = (a + b + c) / 2  # semi-perimeter
        area = math.sqrt(s * (s - a) * (s - b) * (s - c))  # Heron's formula
        perimeter = a + b + c

        # Law of cosines for each angle (in degrees), opposite each side.
        def angle_opposite(x, y, z):
            # angle opposite side x, between sides y and z
            cos_val = (y ** 2 + z ** 2 - x ** 2) / (2 * y * z)
            cos_val = max(-1.0, min(1.0, cos_val))  # clamp for float safety
            return math.degrees(math.acos(cos_val))

        angle_A = angle_opposite(a, b, c)  # angle opposite side a
        angle_B = angle_opposite(b, c, a)  # angle opposite side b
        angle_C = angle_opposite(c, a, b)  # angle opposite side c

        return {
            "status": "ok",
            "shape": "triangle",
            "inputs": {"a": a, "b": b, "c": c},
            "area": area,
            "perimeter": perimeter,
            "angles_degrees": {"A": angle_A, "B": angle_B, "C": angle_C},
            "is_right_triangle": any(
                abs(ang - 90) < 1e-6 for ang in (angle_A, angle_B, angle_C)
            ),
            "is_equilateral": abs(a - b) < 1e-9 and abs(b - c) < 1e-9,
            "is_isosceles": (
                abs(a - b) < 1e-9 or abs(b - c) < 1e-9 or abs(c - a) < 1e-9
            ),
        }


def triangle_from_sides(a: float, b: float, c: float) -> Dict[str, Any]:
    return TriangleShape(a=a, b=b, c=c).solve()


def isosceles_triangle(leg: float, base: float) -> Dict[str, Any]:
    """
    Isosceles triangle construction: two equal legs and a base.

        leg  -- length of each of the two equal sides
        base -- length of the third (unequal) side

    Returns the same area/perimeter/angles payload as triangle_from_sides,
    plus reconstructed (x, y) vertices so the triangle can be drawn: the
    base sits on the x-axis and the apex (the vertex between the two
    equal legs) sits above its midpoint, as in the classic compass-and-
    straightedge construction (draw the base, swing two equal-radius
    arcs from its endpoints, the arcs meet at the apex).
    """
    _require_positive("leg", leg)
    _require_positive("base", base)
    leg, base = float(leg), float(base)

    # a = BC = base, b = CA = leg, c = AB = leg -- so A is the apex.
    result = TriangleShape(a=base, b=leg, c=leg).solve()
    result["shape"] = "isosceles_triangle"
    result["inputs"] = {"leg": leg, "base": base}

    half_base = base / 2
    height_sq = leg ** 2 - half_base ** 2
    if height_sq <= 0:
        raise ShapeError(
            "INVALID_TRIANGLE",
            "These legs are too short for this base -- two sides of "
            "length 'leg' cannot reach across a base this wide (the "
            "triangle inequality requires 2*leg > base).",
            details={"leg": leg, "base": base},
        )
    height = math.sqrt(height_sq)

    apex = (half_base, height)
    result["vertices"] = {
        "apex": apex,
        "base_left": (0.0, 0.0),
        "base_right": (base, 0.0),
    }
    result["height"] = height
    result["apex_angle_degrees"] = result["angles_degrees"]["A"]
    result["base_angle_degrees"] = result["angles_degrees"]["B"]
    result["is_isosceles"] = True
    return result


def equilateral_triangle(side: float) -> Dict[str, Any]:
    """
    Equilateral triangle construction: all three sides equal.

        side -- the common length of all three sides

    Returns the same area/perimeter/angles payload as triangle_from_sides
    (all angles are always 60 degrees), plus reconstructed (x, y)
    vertices for drawing: base on the x-axis, apex centered above it --
    the classic construction (draw the base, swing two arcs of the same
    radius from its endpoints, connect the base to where they meet).
    """
    _require_positive("side", side)
    side = float(side)

    result = TriangleShape(a=side, b=side, c=side).solve()
    result["shape"] = "equilateral_triangle"
    result["inputs"] = {"side": side}

    height = side * math.sqrt(3) / 2
    apex = (side / 2, height)
    result["vertices"] = {
        "apex": apex,
        "base_left": (0.0, 0.0),
        "base_right": (side, 0.0),
    }
    result["height"] = height
    result["inradius"] = side / (2 * math.sqrt(3))
    result["circumradius"] = side / math.sqrt(3)
    result["is_equilateral"] = True
    return result


# ---------------------------------------------------------------------------
# Rectangle / Square
# ---------------------------------------------------------------------------

def rectangle(length: float, width: float) -> Dict[str, Any]:
    _require_positive("length", length)
    _require_positive("width", width)
    length, width = float(length), float(width)
    diagonal = math.hypot(length, width)
    return {
        "status": "ok",
        "shape": "rectangle",
        "inputs": {"length": length, "width": width},
        "area": length * width,
        "perimeter": 2 * (length + width),
        "diagonal": diagonal,
        "is_square": abs(length - width) < 1e-9,
    }


def square(side: float) -> Dict[str, Any]:
    _require_positive("side", side)
    side = float(side)
    return {
        "status": "ok",
        "shape": "square",
        "inputs": {"side": side},
        "area": side ** 2,
        "perimeter": 4 * side,
        "diagonal": side * math.sqrt(2),
    }


# ---------------------------------------------------------------------------
# Parallelogram / Rhombus
# ---------------------------------------------------------------------------

def parallelogram(base: float, side: float, height: float) -> Dict[str, Any]:
    _require_positive("base", base)
    _require_positive("side", side)
    _require_positive("height", height)
    base, side, height = float(base), float(side), float(height)
    if height > side:
        raise ShapeError(
            "INVALID_DIMENSION",
            "Height cannot be greater than the slanted side length.",
            details={"height": height, "side": side},
        )
    return {
        "status": "ok",
        "shape": "parallelogram",
        "inputs": {"base": base, "side": side, "height": height},
        "area": base * height,
        "perimeter": 2 * (base + side),
    }


def rhombus_from_diagonals(d1: float, d2: float) -> Dict[str, Any]:
    _require_positive("d1", d1)
    _require_positive("d2", d2)
    d1, d2 = float(d1), float(d2)
    side = math.hypot(d1 / 2, d2 / 2)
    return {
        "status": "ok",
        "shape": "rhombus",
        "inputs": {"d1": d1, "d2": d2},
        "area": (d1 * d2) / 2,
        "perimeter": 4 * side,
        "side": side,
    }


# ---------------------------------------------------------------------------
# Trapezoid
# ---------------------------------------------------------------------------

def trapezoid(base1: float, base2: float, height: float,
              side1: float = None, side2: float = None) -> Dict[str, Any]:
    _require_positive("base1", base1)
    _require_positive("base2", base2)
    _require_positive("height", height)
    base1, base2, height = float(base1), float(base2), float(height)
    area = ((base1 + base2) / 2) * height
    result = {
        "status": "ok",
        "shape": "trapezoid",
        "inputs": {"base1": base1, "base2": base2, "height": height},
        "area": area,
    }
    if side1 is not None and side2 is not None:
        _require_positive("side1", side1)
        _require_positive("side2", side2)
        side1, side2 = float(side1), float(side2)
        result["inputs"]["side1"] = side1
        result["inputs"]["side2"] = side2
        result["perimeter"] = base1 + base2 + side1 + side2
    else:
        result["perimeter"] = None
        result["note"] = (
            "Perimeter omitted: provide 'side1' and 'side2' (the two "
            "non-parallel legs) to include it."
        )
    return result


# ---------------------------------------------------------------------------
# Regular polygon (n equal sides)
# ---------------------------------------------------------------------------

def regular_polygon(num_sides: int, side_length: float) -> Dict[str, Any]:
    if num_sides is None:
        raise ShapeError("MISSING_VALUE", "Missing required value: 'num_sides'.")
    try:
        num_sides = int(num_sides)
    except (TypeError, ValueError):
        raise ShapeError("INVALID_VALUE", f"'num_sides' must be an integer, got: {num_sides!r}")
    if num_sides < 3:
        raise ShapeError(
            "INVALID_POLYGON",
            "A polygon must have at least 3 sides.",
            details={"num_sides": num_sides},
        )
    _require_positive("side_length", side_length)
    side_length = float(side_length)

    n = num_sides
    perimeter = n * side_length
    area = (n * side_length ** 2) / (4 * math.tan(math.pi / n))
    interior_angle = (n - 2) * 180 / n
    exterior_angle = 360 / n
    apothem = side_length / (2 * math.tan(math.pi / n))
    circumradius = side_length / (2 * math.sin(math.pi / n))

    return {
        "status": "ok",
        "shape": "regular_polygon",
        "inputs": {"num_sides": n, "side_length": side_length},
        "area": area,
        "perimeter": perimeter,
        "interior_angle_degrees": interior_angle,
        "exterior_angle_degrees": exterior_angle,
        "sum_of_interior_angles_degrees": (n - 2) * 180,
        "apothem": apothem,
        "circumradius": circumradius,
    }


# ---------------------------------------------------------------------------
# General polygon (arbitrary vertices, via shoelace formula)
# ---------------------------------------------------------------------------

def polygon_from_vertices(points: List[Tuple[float, float]]) -> Dict[str, Any]:
    if points is None or len(points) < 3:
        raise ShapeError(
            "INVALID_POLYGON",
            "A polygon needs at least 3 vertices.",
            details={"num_points": 0 if points is None else len(points)},
        )
    try:
        pts = [(float(x), float(y)) for x, y in points]
    except (TypeError, ValueError):
        raise ShapeError(
            "INVALID_VALUE",
            f"Could not parse vertices as (x, y) number pairs: {points!r}",
        )

    n = len(pts)
    shoelace_sum = 0.0
    perimeter = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        shoelace_sum += (x1 * y2) - (x2 * y1)
        perimeter += math.hypot(x2 - x1, y2 - y1)

    area = abs(shoelace_sum) / 2
    if area < 1e-9:
        raise ShapeError(
            "DEGENERATE_POLYGON",
            "The provided vertices are collinear (or nearly so) and do "
            "not enclose any area.",
            details={"points": pts},
        )

    return {
        "status": "ok",
        "shape": "polygon",
        "inputs": {"points": pts},
        "area": area,
        "perimeter": perimeter,
        "num_vertices": n,
        "orientation": "counter-clockwise" if shoelace_sum > 0 else "clockwise",
    }


# ---------------------------------------------------------------------------
# N-gon from side lengths + interior angles
# ---------------------------------------------------------------------------

def polygon_from_sides_and_angles(
    sides: List[float], angles_degrees: List[float]
) -> Dict[str, Any]:
    """
    Compute area/perimeter for a simple polygon fully specified by its N
    side lengths and N interior angles (in the order you'd walk around the
    polygon: side[0], angle at the vertex after side[0], side[1], ...).

    Unlike a triangle, a polygon's side lengths alone do NOT determine a
    unique shape (think of a rectangle vs. a slanted parallelogram with
    the same four side lengths) -- so interior angles are required here to
    fully pin down the polygon. This walks the boundary vertex by vertex
    (turning by the exterior angle = 180 - interior angle after each side)
    to reconstruct (x, y) coordinates, then reuses the shoelace formula
    via polygon_from_vertices for area/perimeter.
    """
    if sides is None or angles_degrees is None:
        raise ShapeError(
            "MISSING_VALUE", "Provide both 'sides' and 'angles_degrees'."
        )
    n = len(sides)
    if n < 3:
        raise ShapeError(
            "INVALID_POLYGON", "A polygon needs at least 3 sides.",
            details={"num_sides": n},
        )
    if len(angles_degrees) != n:
        raise ShapeError(
            "MISMATCHED_INPUT",
            f"Got {n} side lengths but {len(angles_degrees)} angles -- "
            "provide exactly one interior angle per side.",
            details={"num_sides": n, "num_angles": len(angles_degrees)},
        )

    try:
        sides = [float(s) for s in sides]
        angles_degrees = [float(a) for a in angles_degrees]
    except (TypeError, ValueError):
        raise ShapeError(
            "INVALID_VALUE", "All sides and angles must be numbers."
        )

    for i, s in enumerate(sides):
        if s <= 0:
            raise ShapeError(
                "INVALID_DIMENSION", f"Side {i + 1} must be positive, got {s}.",
                details={"index": i, "value": s},
            )
    for i, ang in enumerate(angles_degrees):
        if not (0 < ang < 360):
            raise ShapeError(
                "INVALID_DIMENSION",
                f"Angle {i + 1} must be between 0 and 360 degrees, got {ang}.",
                details={"index": i, "value": ang},
            )

    # A simple polygon's interior angles must sum to (n-2)*180 degrees.
    expected_sum = (n - 2) * 180.0
    actual_sum = sum(angles_degrees)
    if abs(actual_sum - expected_sum) > 1e-6:
        raise ShapeError(
            "INVALID_ANGLE_SUM",
            f"The {n} interior angles sum to {actual_sum:.6f}\u00b0, but a "
            f"simple {n}-sided polygon's interior angles must sum to "
            f"exactly {expected_sum:.6f}\u00b0. Check your angle values.",
            details={"expected_sum": expected_sum, "actual_sum": actual_sum},
        )

    # Walk the boundary: start at the origin heading along side[0]. After
    # placing each side, turn left by the exterior angle before the next
    # side (exterior = 180 - interior, the standard convention for a
    # counter-clockwise walk around a convex/simple polygon).
    x, y = 0.0, 0.0
    heading = 0.0  # radians
    pts = [(x, y)]
    for i in range(n):
        x += sides[i] * math.cos(heading)
        y += sides[i] * math.sin(heading)
        if i < n - 1:
            pts.append((x, y))
        exterior = 180.0 - angles_degrees[i]
        heading += math.radians(exterior)

    # Closure check: after walking all N sides/angles we should land back
    # near the starting point. A relative tolerance handles both tiny and
    # huge polygons; a strict absolute one would misfire on either.
    closure_error = math.hypot(x - 0.0, y - 0.0)
    scale = sum(sides) / n  # average side length, for a relative tolerance
    if closure_error > 1e-6 * max(scale, 1.0) * 10:
        raise ShapeError(
            "POLYGON_DOES_NOT_CLOSE",
            "The given sides and angles do not form a closed polygon "
            f"(gap of {closure_error:.6f} after walking the boundary). "
            "Double-check the order of sides/angles and that they "
            "describe a simple (non-self-intersecting) polygon.",
            details={"closure_error": closure_error},
        )

    result = polygon_from_vertices(pts)
    result["inputs"] = {"sides": sides, "angles_degrees": angles_degrees}
    result["num_vertices"] = n
    result["reconstructed_vertices"] = pts
    return result


# ---------------------------------------------------------------------------
# Cyclic polygon from side lengths only (inscribed in a circle)
# ---------------------------------------------------------------------------

def cyclic_polygon_from_sides(sides: List[float]) -> Dict[str, Any]:
    """
    Compute the area of a polygon given ONLY its side lengths, under the
    assumption that it is cyclic (inscribable in a single circle).

    Side lengths alone don't fix a general polygon's shape (see
    polygon_from_sides_and_angles's docstring), but the CYCLIC case is a
    special exception: among all simple polygons sharing a given set of
    side lengths (in a given order), the cyclic one is the UNIQUE
    maximum-area configuration, and its area is fully determined by the
    side lengths alone. This generalizes Brahmagupta's formula (cyclic
    quadrilaterals) to any N >= 3; for N = 3 it's just Heron's formula
    (every triangle is trivially cyclic).

    Method: each side s_i subtends a central angle theta_i = 2*asin(s_i /
    (2R)) at the circumradius R, and a valid cyclic polygon requires
    these central angles to sum to exactly 360 degrees. That equation has
    no closed form for R in general, but sum(theta_i) is a strictly
    decreasing function of R (a bigger circle means smaller angles for
    the same chord lengths), so R is found by bisection, then area is the
    sum of the N triangular slices (1/2)*R^2*sin(theta_i).
    """
    if sides is None:
        raise ShapeError("MISSING_VALUE", "Provide 'sides' (a list of side lengths).")
    n = len(sides)
    if n < 3:
        raise ShapeError(
            "INVALID_POLYGON", "A polygon needs at least 3 sides.",
            details={"num_sides": n},
        )
    try:
        sides = [float(s) for s in sides]
    except (TypeError, ValueError):
        raise ShapeError("INVALID_VALUE", "All sides must be numbers.")
    for i, s in enumerate(sides):
        if s <= 0:
            raise ShapeError(
                "INVALID_DIMENSION", f"Side {i + 1} must be positive, got {s}.",
                details={"index": i, "value": s},
            )
    if n == 3:
        a, b, c = sides
        if not (a + b > c and b + c > a and c + a > b):
            raise ShapeError(
                "INVALID_TRIANGLE",
                "Side lengths do not satisfy the triangle inequality.",
                details={"sides": sides},
            )

    max_side = max(sides)
    max_index = sides.index(max_side)
    R_min = max_side / 2  # smallest circle any chord of this length fits on

    def angle_deg(s: float, R: float) -> float:
        """Central angle (degrees, 0-180) subtended by a chord of length s."""
        return math.degrees(2 * math.asin(max(-1.0, min(1.0, s / (2 * R)))))

    def total_angle(R: float) -> float:
        return sum(angle_deg(s, R) for s in sides)

    def others_minus_longest(R: float) -> float:
        # Used when the circumcentre lies OUTSIDE the polygon: then the
        # longest side's arc is the one that equals the sum of all others.
        return total_angle(R) - 2 * angle_deg(max_side, R)

    def grow_upper_bound(still_too_small) -> float:
        hi = R_min * 2
        guard = 0
        while still_too_small(hi):
            hi *= 2
            guard += 1
            if guard > 200:
                raise ShapeError(
                    "NO_CYCLIC_SOLUTION",
                    "Could not find a circumradius admitting a cyclic polygon "
                    "with these side lengths (no valid R found).",
                    details={"sides": sides},
                )
        return hi

    # Where is the circumcentre? Test the smallest possible circle:
    #   total > 360  -> centre is INSIDE the polygon (normal case)
    #   total == 360 -> centre sits exactly ON the longest side (e.g. a
    #                   3-4-5 right triangle) -- R is exactly max_side/2
    #   total < 360  -> centre is OUTSIDE (e.g. an obtuse triangle)
    # The exact-boundary case is handled directly because bisecting there
    # is badly conditioned (asin has an infinite slope at 1).
    total_at_min = total_angle(R_min)
    if abs(total_at_min - 360.0) <= 1e-9:
        center = "on_longest_side"
        R = R_min
    elif total_at_min > 360.0:
        center = "inside"
        lo = R_min
        hi = grow_upper_bound(lambda r: total_angle(r) >= 360.0)
        for _ in range(200):  # total_angle(R) is strictly decreasing in R
            mid = (lo + hi) / 2
            if total_angle(mid) > 360.0:
                lo = mid
            else:
                hi = mid
        R = (lo + hi) / 2
    else:
        center = "outside"
        lo = R_min
        hi = grow_upper_bound(lambda r: others_minus_longest(r) <= 0.0)
        for _ in range(200):
            mid = (lo + hi) / 2
            if others_minus_longest(mid) < 0.0:
                lo = mid
            else:
                hi = mid
        R = (lo + hi) / 2

    central_angles = [angle_deg(s, R) for s in sides]
    if center == "outside":
        # The longest side's arc is the reflex one (360 - theta). Its slice
        # then has a negative sine and is subtracted automatically below.
        central_angles[max_index] = 360.0 - central_angles[max_index]
    area = 0.5 * R * R * sum(math.sin(math.radians(a)) for a in central_angles)

    perimeter = sum(sides)

    return {
        "status": "ok",
        "shape": "cyclic_polygon",
        "inputs": {"sides": sides},
        "num_vertices": n,
        "area": area,
        "perimeter": perimeter,
        "circumradius": R,
        "circumcenter": center,
        "central_angles_degrees": central_angles,
        "note": (
            "Assumes the polygon is cyclic (inscribed in a circle) -- the "
            "unique maximum-area shape for these side lengths in this "
            "order. A non-cyclic polygon with the same sides would have "
            "strictly less area."
        ),
    }


# ---------------------------------------------------------------------------
# Dispatch table -- used by app.py / main.py
# ---------------------------------------------------------------------------

SUPPORTED_SHAPES = {
    "circle": "radius (or diameter, or circumference)",
    "ellipse": "semi_major, semi_minor",
    "circle_sector": "radius, angle_degrees",
    "circle_segment": "radius, angle_degrees",
    "triangle": "a, b, c (side lengths)",
    "isosceles_triangle": "leg, base (two equal sides + base)",
    "equilateral_triangle": "side (all three sides equal)",
    "rectangle": "length, width",
    "square": "side",
    "parallelogram": "base, side, height",
    "rhombus": "d1, d2 (diagonals)",
    "trapezoid": "base1, base2, height (side1, side2 optional for perimeter)",
    "regular_polygon": "num_sides, side_length",
    "polygon": "points (list of (x, y) vertices)",
    "polygon_from_sides_angles": "sides (list), angles_degrees (list) -- same length, N \u2265 3",
    "cyclic_polygon": "sides (list), N \u2265 3 -- assumes inscribed in a circle",
}
