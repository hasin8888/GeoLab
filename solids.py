"""
solids.py

General 3D solid geometry engine (companion to shapes.py, which covers
2D shapes).

Responsibilities:
  - Compute volume and surface area for common 3D solids: sphere,
    hemisphere, spherical cap, ellipsoid, torus, cube, cuboid, cylinder,
    cone, truncated cone, pyramids, prisms and the five Platonic solids.
  - Validate input (reject negative/zero dimensions).
  - Return structured, JSON-serializable results or descriptive error
    payloads -- SolidError mirrors ShapeError's shape (status/error_code/
    message/details) so callers can handle both the same way, without
    this module depending on shapes.py.
"""

import math
from typing import Any, Dict


class SolidError(Exception):
    """Raised for any recoverable domain error (bad dimensions)."""

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
        raise SolidError("MISSING_VALUE", f"Missing required value: '{name}'.")
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise SolidError("INVALID_VALUE", f"'{name}' must be a number, got: {value!r}")
    if value <= 0:
        raise SolidError(
            "INVALID_DIMENSION",
            f"'{name}' must be a positive number, got: {value}.",
            details={name: value},
        )


# ---------------------------------------------------------------------------
# Sphere
# ---------------------------------------------------------------------------

def sphere(radius: float) -> Dict[str, Any]:
    _require_positive("radius", radius)
    r = float(radius)
    volume = (4 / 3) * math.pi * r ** 3
    surface_area = 4 * math.pi * r ** 2
    return {
        "status": "ok",
        "solid": "sphere",
        "inputs": {"radius": r},
        "volume": volume,
        "surface_area": surface_area,
    }


# ---------------------------------------------------------------------------
# Cube / Cuboid (rectangular box)
# ---------------------------------------------------------------------------

def cube(side: float) -> Dict[str, Any]:
    _require_positive("side", side)
    side = float(side)
    return {
        "status": "ok",
        "solid": "cube",
        "inputs": {"side": side},
        "volume": side ** 3,
        "surface_area": 6 * side ** 2,
        "space_diagonal": side * math.sqrt(3),
    }


def cuboid(length: float, width: float, height: float) -> Dict[str, Any]:
    _require_positive("length", length)
    _require_positive("width", width)
    _require_positive("height", height)
    length, width, height = float(length), float(width), float(height)
    volume = length * width * height
    surface_area = 2 * (length * width + width * height + height * length)
    space_diagonal = math.sqrt(length ** 2 + width ** 2 + height ** 2)
    return {
        "status": "ok",
        "solid": "cuboid",
        "inputs": {"length": length, "width": width, "height": height},
        "volume": volume,
        "surface_area": surface_area,
        "space_diagonal": space_diagonal,
    }


# ---------------------------------------------------------------------------
# Cylinder
# ---------------------------------------------------------------------------

def cylinder(radius: float, height: float) -> Dict[str, Any]:
    _require_positive("radius", radius)
    _require_positive("height", height)
    r, h = float(radius), float(height)
    volume = math.pi * r ** 2 * h
    lateral_surface_area = 2 * math.pi * r * h
    base_area = math.pi * r ** 2
    total_surface_area = lateral_surface_area + 2 * base_area
    return {
        "status": "ok",
        "solid": "cylinder",
        "inputs": {"radius": r, "height": h},
        "volume": volume,
        "surface_area": total_surface_area,
        "lateral_surface_area": lateral_surface_area,
        "base_area": base_area,
    }


# ---------------------------------------------------------------------------
# Cone (right circular)
# ---------------------------------------------------------------------------

def cone(radius: float, height: float) -> Dict[str, Any]:
    _require_positive("radius", radius)
    _require_positive("height", height)
    r, h = float(radius), float(height)
    slant_height = math.hypot(r, h)
    volume = (1 / 3) * math.pi * r ** 2 * h
    lateral_surface_area = math.pi * r * slant_height
    base_area = math.pi * r ** 2
    total_surface_area = lateral_surface_area + base_area
    return {
        "status": "ok",
        "solid": "cone",
        "inputs": {"radius": r, "height": h},
        "volume": volume,
        "surface_area": total_surface_area,
        "lateral_surface_area": lateral_surface_area,
        "base_area": base_area,
        "slant_height": slant_height,
    }


# ---------------------------------------------------------------------------
# Square pyramid (regular: square base, apex centered above it)
# ---------------------------------------------------------------------------

def square_pyramid(base_side: float, height: float) -> Dict[str, Any]:
    _require_positive("base_side", base_side)
    _require_positive("height", height)
    s, h = float(base_side), float(height)
    base_area = s ** 2
    volume = (1 / 3) * base_area * h
    # Slant height: distance from apex to the midpoint of a base edge.
    slant_height = math.sqrt(h ** 2 + (s / 2) ** 2)
    lateral_surface_area = 2 * s * slant_height  # 4 triangular faces
    total_surface_area = base_area + lateral_surface_area
    # Edge length of the four slanted (lateral) edges, apex to corner.
    lateral_edge_length = math.sqrt(h ** 2 + 2 * (s / 2) ** 2)
    return {
        "status": "ok",
        "solid": "square_pyramid",
        "inputs": {"base_side": s, "height": h},
        "volume": volume,
        "surface_area": total_surface_area,
        "lateral_surface_area": lateral_surface_area,
        "base_area": base_area,
        "slant_height": slant_height,
        "lateral_edge_length": lateral_edge_length,
    }


# ---------------------------------------------------------------------------
# Extra helpers for the solids below
# ---------------------------------------------------------------------------

def _require_sides(name: str, value) -> int:
    """A whole number of sides, at least 3 (accepts '6' and '6.0')."""
    if value is None:
        raise SolidError("MISSING_VALUE", f"Missing required value: '{name}'.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise SolidError("INVALID_VALUE", f"'{name}' must be a number, got: {value!r}")
    if not math.isfinite(number) or not number.is_integer() or number < 3:
        raise SolidError(
            "INVALID_POLYGON",
            f"'{name}' must be a whole number that is at least 3, got: {value!r}.",
            details={name: value},
        )
    return int(number)


def _regular_polygon_base_area(n: int, side: float) -> float:
    return n * side ** 2 / (4 * math.tan(math.pi / n))


# ---------------------------------------------------------------------------
# Hemisphere and spherical cap
# ---------------------------------------------------------------------------

def hemisphere(radius: float) -> Dict[str, Any]:
    _require_positive("radius", radius)
    r = float(radius)
    curved = 2 * math.pi * r ** 2
    base_area = math.pi * r ** 2
    return {
        "status": "ok",
        "solid": "hemisphere",
        "inputs": {"radius": r},
        "volume": (2 / 3) * math.pi * r ** 3,
        "surface_area": curved + base_area,  # curved surface + flat disc
        "curved_surface_area": curved,
        "base_area": base_area,
    }


def spherical_cap(radius: float, height: float) -> Dict[str, Any]:
    """Cap cut from a sphere of the given radius; height runs from the flat
    face to the top of the cap (0 < height <= 2 * radius)."""
    _require_positive("radius", radius)
    _require_positive("height", height)
    r, h = float(radius), float(height)
    if h > 2 * r:
        raise SolidError(
            "INVALID_DIMENSION",
            "'height' of a spherical cap cannot exceed the sphere's diameter "
            f"(2 * radius = {2 * r}).",
            details={"radius": r, "height": h},
        )
    base_radius = math.sqrt(h * (2 * r - h))
    base_area = math.pi * base_radius ** 2
    curved = 2 * math.pi * r * h
    return {
        "status": "ok",
        "solid": "spherical_cap",
        "inputs": {"radius": r, "height": h},
        "volume": math.pi * h ** 2 * (3 * r - h) / 3,
        "surface_area": curved + base_area,
        "curved_surface_area": curved,
        "base_radius": base_radius,
        "base_area": base_area,
    }


# ---------------------------------------------------------------------------
# Ellipsoid and torus
# ---------------------------------------------------------------------------

def ellipsoid(a: float, b: float, c: float) -> Dict[str, Any]:
    """Ellipsoid with semi-axes a, b, c. The volume is exact; the surface area
    has no closed form, so Knud Thomsen's approximation is used (relative
    error below about 1.1%)."""
    _require_positive("a", a)
    _require_positive("b", b)
    _require_positive("c", c)
    a, b, c = float(a), float(b), float(c)
    p = 1.6075
    surface_area = 4 * math.pi * (
        ((a * b) ** p + (a * c) ** p + (b * c) ** p) / 3
    ) ** (1 / p)
    return {
        "status": "ok",
        "solid": "ellipsoid",
        "inputs": {"a": a, "b": b, "c": c},
        "volume": (4 / 3) * math.pi * a * b * c,
        "surface_area": surface_area,
        "surface_area_is_approximate": True,
    }


def torus(major_radius: float, minor_radius: float) -> Dict[str, Any]:
    """Ring torus: major_radius is the distance from the centre of the hole to
    the middle of the tube, minor_radius is the tube's own radius."""
    _require_positive("major_radius", major_radius)
    _require_positive("minor_radius", minor_radius)
    R, r = float(major_radius), float(minor_radius)
    if r > R:
        raise SolidError(
            "INVALID_DIMENSION",
            "'minor_radius' cannot be larger than 'major_radius' (the tube "
            "would overlap itself).",
            details={"major_radius": R, "minor_radius": r},
        )
    return {
        "status": "ok",
        "solid": "torus",
        "inputs": {"major_radius": R, "minor_radius": r},
        "volume": 2 * math.pi ** 2 * R * r ** 2,
        "surface_area": 4 * math.pi ** 2 * R * r,
    }


# ---------------------------------------------------------------------------
# Truncated cone (frustum of a right circular cone)
# ---------------------------------------------------------------------------

def truncated_cone(bottom_radius: float, top_radius: float, height: float) -> Dict[str, Any]:
    _require_positive("bottom_radius", bottom_radius)
    _require_positive("top_radius", top_radius)
    _require_positive("height", height)
    r1, r2, h = float(bottom_radius), float(top_radius), float(height)
    slant_height = math.hypot(h, r1 - r2)
    lateral = math.pi * (r1 + r2) * slant_height
    bottom_area = math.pi * r1 ** 2
    top_area = math.pi * r2 ** 2
    return {
        "status": "ok",
        "solid": "truncated_cone",
        "inputs": {"bottom_radius": r1, "top_radius": r2, "height": h},
        "volume": math.pi * h * (r1 ** 2 + r1 * r2 + r2 ** 2) / 3,
        "surface_area": lateral + bottom_area + top_area,
        "lateral_surface_area": lateral,
        "slant_height": slant_height,
    }


# ---------------------------------------------------------------------------
# Prisms and pyramids
# ---------------------------------------------------------------------------

def regular_prism(num_sides: int, base_side: float, height: float) -> Dict[str, Any]:
    """Right prism whose base is a regular polygon."""
    n = _require_sides("num_sides", num_sides)
    _require_positive("base_side", base_side)
    _require_positive("height", height)
    s, h = float(base_side), float(height)
    base_area = _regular_polygon_base_area(n, s)
    lateral = n * s * h
    return {
        "status": "ok",
        "solid": "regular_prism",
        "inputs": {"num_sides": n, "base_side": s, "height": h},
        "volume": base_area * h,
        "surface_area": lateral + 2 * base_area,
        "lateral_surface_area": lateral,
        "base_area": base_area,
    }


def triangular_prism(a: float, b: float, c: float, height: float) -> Dict[str, Any]:
    """Right prism whose base is the triangle with sides a, b, c."""
    _require_positive("a", a)
    _require_positive("b", b)
    _require_positive("c", c)
    _require_positive("height", height)
    a, b, c, h = float(a), float(b), float(c), float(height)
    if a + b <= c or a + c <= b or b + c <= a:
        raise SolidError(
            "INVALID_TRIANGLE",
            "The base sides do not satisfy the triangle inequality.",
            details={"a": a, "b": b, "c": c},
        )
    s = (a + b + c) / 2
    base_area = math.sqrt(s * (s - a) * (s - b) * (s - c))  # Heron's formula
    perimeter = a + b + c
    lateral = perimeter * h
    return {
        "status": "ok",
        "solid": "triangular_prism",
        "inputs": {"a": a, "b": b, "c": c, "height": h},
        "volume": base_area * h,
        "surface_area": lateral + 2 * base_area,
        "lateral_surface_area": lateral,
        "base_area": base_area,
    }


def regular_pyramid(num_sides: int, base_side: float, height: float) -> Dict[str, Any]:
    """Pyramid whose base is a regular polygon, apex directly above its
    centre (square_pyramid is the num_sides = 4 case)."""
    n = _require_sides("num_sides", num_sides)
    _require_positive("base_side", base_side)
    _require_positive("height", height)
    s, h = float(base_side), float(height)
    base_area = _regular_polygon_base_area(n, s)
    apothem = s / (2 * math.tan(math.pi / n))
    circumradius = s / (2 * math.sin(math.pi / n))
    slant_height = math.hypot(h, apothem)
    lateral = 0.5 * n * s * slant_height
    return {
        "status": "ok",
        "solid": "regular_pyramid",
        "inputs": {"num_sides": n, "base_side": s, "height": h},
        "volume": base_area * h / 3,
        "surface_area": base_area + lateral,
        "lateral_surface_area": lateral,
        "base_area": base_area,
        "slant_height": slant_height,
        "lateral_edge_length": math.hypot(h, circumradius),
    }


# ---------------------------------------------------------------------------
# Platonic solids (all edges equal)
# ---------------------------------------------------------------------------

def tetrahedron(edge: float) -> Dict[str, Any]:
    _require_positive("edge", edge)
    a = float(edge)
    return {
        "status": "ok",
        "solid": "tetrahedron",
        "inputs": {"edge": a},
        "volume": a ** 3 / (6 * math.sqrt(2)),
        "surface_area": math.sqrt(3) * a ** 2,
        "height": a * math.sqrt(2 / 3),
        "circumradius": a * math.sqrt(6) / 4,
        "inradius": a * math.sqrt(6) / 12,
    }


def octahedron(edge: float) -> Dict[str, Any]:
    _require_positive("edge", edge)
    a = float(edge)
    return {
        "status": "ok",
        "solid": "octahedron",
        "inputs": {"edge": a},
        "volume": math.sqrt(2) / 3 * a ** 3,
        "surface_area": 2 * math.sqrt(3) * a ** 2,
        "circumradius": a / math.sqrt(2),
        "inradius": a / math.sqrt(6),
    }


def dodecahedron(edge: float) -> Dict[str, Any]:
    _require_positive("edge", edge)
    a = float(edge)
    sqrt5 = math.sqrt(5)
    return {
        "status": "ok",
        "solid": "dodecahedron",
        "inputs": {"edge": a},
        "volume": (15 + 7 * sqrt5) / 4 * a ** 3,
        "surface_area": 3 * math.sqrt(25 + 10 * sqrt5) * a ** 2,
        "circumradius": a * math.sqrt(3) * (1 + sqrt5) / 4,
        "inradius": a / 2 * math.sqrt((25 + 11 * sqrt5) / 10),
    }


def icosahedron(edge: float) -> Dict[str, Any]:
    _require_positive("edge", edge)
    a = float(edge)
    sqrt5 = math.sqrt(5)
    return {
        "status": "ok",
        "solid": "icosahedron",
        "inputs": {"edge": a},
        "volume": 5 * (3 + sqrt5) / 12 * a ** 3,
        "surface_area": 5 * math.sqrt(3) * a ** 2,
        "circumradius": a / 4 * math.sqrt(10 + 2 * sqrt5),
        "inradius": math.sqrt(3) * (3 + sqrt5) / 12 * a,
    }


# ---------------------------------------------------------------------------
# Dispatch table -- used by dispatch.py (API + CLI)
# ---------------------------------------------------------------------------

SUPPORTED_SOLIDS = {
    "sphere": "radius",
    "hemisphere": "radius",
    "spherical_cap": "radius, height",
    "ellipsoid": "a, b, c",
    "torus": "major_radius, minor_radius",
    "cube": "side",
    "cuboid": "length, width, height",
    "cylinder": "radius, height",
    "cone": "radius, height",
    "truncated_cone": "bottom_radius, top_radius, height",
    "square_pyramid": "base_side, height",
    "regular_pyramid": "num_sides, base_side, height",
    "regular_prism": "num_sides, base_side, height",
    "triangular_prism": "a, b, c, height",
    "tetrahedron": "edge",
    "octahedron": "edge",
    "dodecahedron": "edge",
    "icosahedron": "edge",
}
