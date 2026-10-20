"""
construction.py

Pure-geometry helper for the /draw page: given a triangle, return the
classic centers (G, O, I, H, N), the Euler line, the circumcircle,
incircle and nine-point circle, plus midpoints and altitude feet.
Everything is JSON-serializable; no database needed.
"""

import math
from typing import Any, Dict, Tuple

from centers import Triangle

Point = Tuple[float, float]


def _pt(p: Point) -> Dict[str, float]:
    return {"x": p[0], "y": p[1]}


def _mid(p: Point, q: Point) -> Point:
    return ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)


def _foot(p: Point, q: Point, r: Point) -> Point:
    """Foot of the perpendicular from p onto line qr."""
    dx, dy = r[0] - q[0], r[1] - q[1]
    t = ((p[0] - q[0]) * dx + (p[1] - q[1]) * dy) / (dx * dx + dy * dy)
    return (q[0] + t * dx, q[1] + t * dy)


def build_construction(tri: Triangle) -> Dict[str, Any]:
    """Validate `tri` (raises TriangleCenterError if degenerate) and return
    its construction data."""
    tri.validate()
    A, B, C = tri.A, tri.B, tri.C
    a, b, c = tri.side_lengths()
    area = abs(tri.area2()) / 2
    s = (a + b + c) / 2

    # Centroid, incenter, circumcenter, orthocenter, nine-point center.
    G = ((A[0] + B[0] + C[0]) / 3, (A[1] + B[1] + C[1]) / 3)
    perimeter = a + b + c
    I = ((a * A[0] + b * B[0] + c * C[0]) / perimeter,
         (a * A[1] + b * B[1] + c * C[1]) / perimeter)
    d = 2 * (A[0] * (B[1] - C[1]) + B[0] * (C[1] - A[1]) + C[0] * (A[1] - B[1]))
    sa, sb, sc = A[0] ** 2 + A[1] ** 2, B[0] ** 2 + B[1] ** 2, C[0] ** 2 + C[1] ** 2
    O = ((sa * (B[1] - C[1]) + sb * (C[1] - A[1]) + sc * (A[1] - B[1])) / d,
         (sa * (C[0] - B[0]) + sb * (A[0] - C[0]) + sc * (B[0] - A[0])) / d)
    H = (3 * G[0] - 2 * O[0], 3 * G[1] - 2 * O[1])  # Euler: H = 3G - 2O
    N = _mid(O, H)

    R = math.hypot(O[0] - A[0], O[1] - A[1])
    r = area / s

    def angle(x, y, z):  # angle opposite side x, between sides y and z
        return math.degrees(math.acos(max(-1.0, min(1.0, (y * y + z * z - x * x) / (2 * y * z)))))

    angles = {"A": angle(a, b, c), "B": angle(b, c, a), "C": angle(c, a, b)}
    biggest = max(angles.values())
    if abs(biggest - 90) < 1e-6:
        kind = "right"
    else:
        kind = "obtuse" if biggest > 90 else "acute"

    # Euler line passes through O, G, H -- undefined when they coincide
    # (equilateral triangle).
    oh = math.hypot(H[0] - O[0], H[1] - O[1])
    euler = None
    if oh > 1e-9 * max(1.0, R):
        euler = {"point": _pt(O), "direction": {"x": (H[0] - O[0]) / oh, "y": (H[1] - O[1]) / oh}}

    return {
        "status": "ok",
        "triangle": {"A": _pt(A), "B": _pt(B), "C": _pt(C)},
        "side_lengths": {"a": a, "b": b, "c": c},
        "angles_degrees": angles,
        "triangle_type": kind,
        "area": area,
        "centers": {"G": _pt(G), "O": _pt(O), "I": _pt(I), "H": _pt(H), "N": _pt(N)},
        "circles": {
            "circumcircle": {"center": _pt(O), "radius": R},
            "incircle": {"center": _pt(I), "radius": r},
            "nine_point_circle": {"center": _pt(N), "radius": R / 2},
        },
        "euler_line": euler,
        "midpoints": {"A": _pt(_mid(B, C)), "B": _pt(_mid(C, A)), "C": _pt(_mid(A, B))},
        "altitude_feet": {"A": _pt(_foot(A, B, C)), "B": _pt(_foot(B, C, A)), "C": _pt(_foot(C, A, B))},
    }
