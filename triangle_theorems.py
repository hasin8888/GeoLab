"""
triangle_theorems.py

Classic triangle theorems as standalone, callable tools -- separate from
shapes.py (which solves a full triangle from its three sides) because
these theorems each have their own distinct input shape (partial
information, cevian ratios, transversal ratios, etc.) and are commonly
used one at a time rather than as a "give me everything" solver.

Covered:
  - Law of Sines   (solve_sine_rule)    -- SSA / AAS input
  - Law of Cosines (solve_cosine_rule)  -- SSS or SAS input
  - Law of Tangents (tangent_rule_check) -- verify the tangent-rule identity
  - Ceva's Theorem   (ceva_check)       -- test 3 cevians for concurrency
  - Menelaus' Theorem (menelaus_check)  -- test 3 points for collinearity

Error/response conventions mirror shapes.py: a TheoremError carries a
code/message/details and to_payload() produces the same JSON-serializable
shape used throughout this project (status/error_code/message/details).
"""

import math
from typing import Any, Dict, List


class TheoremError(Exception):
    """Raised for any recoverable domain error (bad input, no valid triangle)."""

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


def _require_positive(name: str, value) -> float:
    if value is None:
        raise TheoremError("MISSING_VALUE", f"Missing required value: '{name}'.")
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise TheoremError("INVALID_VALUE", f"'{name}' must be a number, got: {value!r}")
    if value <= 0:
        raise TheoremError(
            "INVALID_DIMENSION", f"'{name}' must be a positive number, got: {value}.",
            details={name: value},
        )
    return value


def _require_valid_angle(name: str, value) -> float:
    if value is None:
        raise TheoremError("MISSING_VALUE", f"Missing required value: '{name}'.")
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise TheoremError("INVALID_VALUE", f"'{name}' must be a number, got: {value!r}")
    if not (0 < value < 180):
        raise TheoremError(
            "INVALID_DIMENSION",
            f"'{name}' must be a triangle angle strictly between 0 and 180 "
            f"degrees, got: {value}.",
            details={name: value},
        )
    return value


def _numeric_or_same(value):
    """Convert numeric strings (e.g. from a URL query) to float so the
    zero-ratio check in ceva_check/menelaus_check works for '0' as well as
    0. Non-numeric values are returned unchanged so the normal
    INVALID_VALUE error is still raised for them."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


# ---------------------------------------------------------------------------
# Law of Sines (Sine Rule): a/sin(A) = b/sin(B) = c/sin(C)
# ---------------------------------------------------------------------------

def solve_sine_rule(a: float = None, b: float = None,
                     angle_A_degrees: float = None, angle_B_degrees: float = None
                     ) -> Dict[str, Any]:
    """
    Solve a triangle from the Law of Sines given exactly one of two cases:

      SSA (two sides + the angle opposite one of them):
        a, b, angle_A_degrees  -- solve for angle_B (and hence C, c).
        This is the classic "ambiguous case": depending on the numbers,
        there can be ZERO, ONE, or TWO valid triangles. All valid
        solutions are returned.

      AAS/ASA (one side + both angles it determines the rest from):
        a, angle_A_degrees, angle_B_degrees  -- unique solution for b, C, c.

    Returns one or more solutions; each solution is a complete triangle
    (all 3 sides, all 3 angles).
    """
    have_two_sides = a is not None and b is not None
    have_two_angles = angle_A_degrees is not None and angle_B_degrees is not None

    if have_two_angles:
        # AAS/ASA case: unique solution.
        a_val = _require_positive("a", a) if a is not None else None
        A = _require_valid_angle("angle_A_degrees", angle_A_degrees)
        B = _require_valid_angle("angle_B_degrees", angle_B_degrees)
        if A + B >= 180:
            raise TheoremError(
                "INVALID_TRIANGLE",
                f"angle_A ({A}\u00b0) + angle_B ({B}\u00b0) must be less than "
                "180\u00b0 (the third angle would be zero or negative).",
                details={"angle_A_degrees": A, "angle_B_degrees": B},
            )
        C = 180.0 - A - B
        if a_val is None:
            raise TheoremError(
                "MISSING_VALUE",
                "Provide side 'a' along with both angles to fix the "
                "triangle's scale (angles alone only fix its shape).",
            )
        ratio = a_val / math.sin(math.radians(A))
        b_val = ratio * math.sin(math.radians(B))
        c_val = ratio * math.sin(math.radians(C))
        return {
            "status": "ok",
            "theorem": "law_of_sines",
            "case": "AAS_ASA",
            "solutions": [{
                "a": a_val, "b": b_val, "c": c_val,
                "angle_A_degrees": A, "angle_B_degrees": B, "angle_C_degrees": C,
                "common_ratio": ratio,
            }],
            "note": "a/sin(A) = b/sin(B) = c/sin(C) = "
                    f"{ratio:.6g} (the common ratio, equal to the circumdiameter 2R).",
        }

    if have_two_sides and angle_A_degrees is not None:
        # SSA case: possibly ambiguous.
        a_val = _require_positive("a", a)
        b_val = _require_positive("b", b)
        A = _require_valid_angle("angle_A_degrees", angle_A_degrees)

        sin_B = b_val * math.sin(math.radians(A)) / a_val
        if sin_B > 1 + 1e-9:
            raise TheoremError(
                "NO_TRIANGLE",
                "No triangle satisfies these values: side 'a' is too short "
                "to reach side 'b' at the given angle A (sin(B) would "
                "exceed 1).",
                details={"a": a_val, "b": b_val, "angle_A_degrees": A},
            )
        sin_B = min(1.0, sin_B)
        # Snap to exactly 1 when within float noise, so the right-angle
        # case (B = 90 degrees) is reported as ONE solution, not two.
        if abs(sin_B - 1.0) < 1e-9:
            sin_B = 1.0
        B_acute = math.degrees(math.asin(sin_B))
        candidates = {B_acute, 180.0 - B_acute}

        solutions = []
        for B in candidates:
            if B <= 1e-9:
                continue
            C = 180.0 - A - B
            if C <= 1e-9:
                continue
            c_val = a_val * math.sin(math.radians(C)) / math.sin(math.radians(A))
            solutions.append({
                "a": a_val, "b": b_val, "c": c_val,
                "angle_A_degrees": A, "angle_B_degrees": B, "angle_C_degrees": C,
            })
        # De-duplicate the right-angle case where both candidates coincide.
        unique_solutions = []
        for s in solutions:
            if not any(abs(s["angle_B_degrees"] - u["angle_B_degrees"]) < 1e-6
                       for u in unique_solutions):
                unique_solutions.append(s)

        if not unique_solutions:
            raise TheoremError(
                "NO_TRIANGLE",
                "No valid triangle satisfies these values.",
                details={"a": a_val, "b": b_val, "angle_A_degrees": A},
            )

        return {
            "status": "ok",
            "theorem": "law_of_sines",
            "case": "SSA",
            "ambiguous": len(unique_solutions) > 1,
            "num_solutions": len(unique_solutions),
            "solutions": unique_solutions,
            "note": (
                "This is the SSA 'ambiguous case' -- two distinct "
                "triangles satisfy the given side/side/angle values."
                if len(unique_solutions) > 1 else
                "Exactly one triangle satisfies the given side/side/angle "
                "values."
            ),
        }

    raise TheoremError(
        "MISSING_VALUE",
        "Provide either (a, b, angle_A_degrees) for the SSA case, or "
        "(a, angle_A_degrees, angle_B_degrees) for the AAS/ASA case.",
    )


# ---------------------------------------------------------------------------
# Law of Cosines: c^2 = a^2 + b^2 - 2ab*cos(C)
# ---------------------------------------------------------------------------

def solve_cosine_rule(a: float = None, b: float = None, c: float = None,
                       angle_C_degrees: float = None) -> Dict[str, Any]:
    """
    Solve a triangle via the Law of Cosines given exactly one of two cases:

      SSS (all three sides): a, b, c -- solve for all three angles.

      SAS (two sides + their included angle): a, b, angle_C_degrees
        (the angle between sides a and b) -- solve for side c and the
        remaining two angles.
    """
    have_three_sides = a is not None and b is not None and c is not None
    have_sas = (a is not None and b is not None and angle_C_degrees is not None
                and c is None)

    if have_three_sides:
        a_val = _require_positive("a", a)
        b_val = _require_positive("b", b)
        c_val = _require_positive("c", c)
        if not (a_val + b_val > c_val and b_val + c_val > a_val and c_val + a_val > b_val):
            raise TheoremError(
                "INVALID_TRIANGLE",
                "Side lengths do not satisfy the triangle inequality "
                "(the sum of any two sides must exceed the third).",
                details={"a": a_val, "b": b_val, "c": c_val},
            )

        def angle_opposite(x, y, z):
            cos_val = (y ** 2 + z ** 2 - x ** 2) / (2 * y * z)
            cos_val = max(-1.0, min(1.0, cos_val))
            return math.degrees(math.acos(cos_val))

        A = angle_opposite(a_val, b_val, c_val)
        B = angle_opposite(b_val, c_val, a_val)
        C = angle_opposite(c_val, a_val, b_val)
        return {
            "status": "ok",
            "theorem": "law_of_cosines",
            "case": "SSS",
            "a": a_val, "b": b_val, "c": c_val,
            "angle_A_degrees": A, "angle_B_degrees": B, "angle_C_degrees": C,
        }

    if have_sas:
        a_val = _require_positive("a", a)
        b_val = _require_positive("b", b)
        C = _require_valid_angle("angle_C_degrees", angle_C_degrees)

        c_val = math.sqrt(
            a_val ** 2 + b_val ** 2 - 2 * a_val * b_val * math.cos(math.radians(C))
        )
        if c_val < 1e-9:
            raise TheoremError(
                "DEGENERATE_TRIANGLE",
                "These values produce a (near) zero-length third side.",
                details={"a": a_val, "b": b_val, "angle_C_degrees": C},
            )

        # Get the remaining two angles via Law of Cosines (not Law of
        # Sines): asin() alone can't tell an acute angle from its obtuse
        # supplement, so re-deriving A and B this way -- the same method
        # already proven correct in the SSS case above -- avoids having
        # to guess which root is right.
        def angle_opposite(x, y, z):
            cos_val = (y ** 2 + z ** 2 - x ** 2) / (2 * y * z)
            cos_val = max(-1.0, min(1.0, cos_val))
            return math.degrees(math.acos(cos_val))

        A = angle_opposite(a_val, b_val, c_val)
        B = angle_opposite(b_val, c_val, a_val)

        return {
            "status": "ok",
            "theorem": "law_of_cosines",
            "case": "SAS",
            "a": a_val, "b": b_val, "c": c_val,
            "angle_A_degrees": A, "angle_B_degrees": B, "angle_C_degrees": C,
        }

    raise TheoremError(
        "MISSING_VALUE",
        "Provide either (a, b, c) for the SSS case, or (a, b, "
        "angle_C_degrees) for the SAS case (angle_C is the angle between "
        "sides a and b).",
    )


# ---------------------------------------------------------------------------
# Law of Tangents: (a-b)/(a+b) = tan((A-B)/2) / tan((A+B)/2)
# ---------------------------------------------------------------------------

def tangent_rule_check(a: float, b: float,
                        angle_A_degrees: float, angle_B_degrees: float,
                        tol: float = 1e-6) -> Dict[str, Any]:
    """
    Verify the Law of Tangents identity for a triangle:
        (a - b) / (a + b) = tan((A - B) / 2) / tan((A + B) / 2)
    where a, b are two sides and A, B are their opposite angles. Useful
    for checking a triangle's consistency (e.g. after solving it another
    way) rather than as a primary solver, since Law of Sines/Cosines
    already determine a triangle uniquely -- this reports both sides of
    the identity and whether they match.
    """
    a_val = _require_positive("a", a)
    b_val = _require_positive("b", b)
    A = _require_valid_angle("angle_A_degrees", angle_A_degrees)
    B = _require_valid_angle("angle_B_degrees", angle_B_degrees)

    if A + B >= 180:
        raise TheoremError(
            "INVALID_TRIANGLE",
            f"angle_A ({A}\u00b0) + angle_B ({B}\u00b0) must be less than 180\u00b0.",
            details={"angle_A_degrees": A, "angle_B_degrees": B},
        )

    half_sum = (A + B) / 2
    if abs(half_sum - 90.0) < 1e-9:
        raise TheoremError(
            "UNDEFINED_TANGENT",
            "tan((A+B)/2) is undefined here because (A+B)/2 = 90\u00b0 "
            "(this happens when C = 0\u00b0, i.e. not a valid triangle).",
            details={"angle_A_degrees": A, "angle_B_degrees": B},
        )

    lhs = (a_val - b_val) / (a_val + b_val)
    rhs = math.tan(math.radians((A - B) / 2)) / math.tan(math.radians(half_sum))
    matches = abs(lhs - rhs) < tol

    return {
        "status": "ok",
        "theorem": "law_of_tangents",
        "inputs": {"a": a_val, "b": b_val, "angle_A_degrees": A, "angle_B_degrees": B},
        "lhs_value": lhs,
        "rhs_value": rhs,
        "identity_holds": matches,
        "note": (
            "(a-b)/(a+b) = tan((A-B)/2) / tan((A+B)/2) -- both sides "
            f"{'match, confirming this is a consistent triangle.' if matches else 'do NOT match, so a/A and b/B are not from the same triangle.'}"
        ),
    }


# ---------------------------------------------------------------------------
# Ceva's Theorem: concurrency of three cevians
# ---------------------------------------------------------------------------

def ceva_check(bd_dc: float, ce_ea: float, af_fb: float,
                tol: float = 1e-6) -> Dict[str, Any]:
    """
    Ceva's Theorem: for cevians AD, BE, CF of triangle ABC (D on line BC,
    E on line CA, F on line AB), the three cevians are concurrent
    (meet at a single point) if and only if:

        (BD/DC) * (CE/EA) * (AF/FB) = 1

    using signed ratios (negative when the dividing point falls outside
    the segment). Provide the three ratios; this reports their product
    and whether it equals 1 (concurrent) within tolerance.

    Example: the three medians always give ratios (1, 1, 1) -> product 1
    -> concurrent at the centroid, since a median hits the midpoint of
    the opposite side.
    """
    bd_dc, ce_ea, af_fb = (_numeric_or_same(v) for v in (bd_dc, ce_ea, af_fb))
    for name, val in (("bd_dc", bd_dc), ("ce_ea", ce_ea), ("af_fb", af_fb)):
        if val is None:
            raise TheoremError("MISSING_VALUE", f"Missing required ratio: '{name}'.")
        try:
            float(val)
        except (TypeError, ValueError):
            raise TheoremError("INVALID_VALUE", f"'{name}' must be a number, got: {val!r}")
        if val == 0:
            raise TheoremError(
                "INVALID_VALUE",
                f"'{name}' cannot be zero (a ratio of two lengths can't be 0 "
                "unless a vertex coincides with a division point).",
                details={name: val},
            )

    bd_dc, ce_ea, af_fb = float(bd_dc), float(ce_ea), float(af_fb)
    product = bd_dc * ce_ea * af_fb
    concurrent = abs(product - 1.0) < tol

    return {
        "status": "ok",
        "theorem": "ceva",
        "inputs": {"BD/DC": bd_dc, "CE/EA": ce_ea, "AF/FB": af_fb},
        "product": product,
        "concurrent": concurrent,
        "note": (
            "(BD/DC)\u00b7(CE/EA)\u00b7(AF/FB) = "
            f"{product:.6g} {'= 1, so the three cevians ARE concurrent.' if concurrent else '!= 1, so the three cevians are NOT concurrent.'}"
        ),
    }


# ---------------------------------------------------------------------------
# Menelaus' Theorem: collinearity of three points on a transversal
# ---------------------------------------------------------------------------

def menelaus_check(bd_dc: float, ce_ea: float, af_fb: float,
                    tol: float = 1e-6) -> Dict[str, Any]:
    """
    Menelaus' Theorem: for a line (transversal) crossing the sides (or
    extensions) of triangle ABC at points D (on line BC), E (on line CA),
    and F (on line AB), those three points are collinear if and only if:

        (BD/DC) * (CE/EA) * (AF/FB) = -1

    using SIGNED ratios (negative when a point divides the segment
    externally). This is the same ratio layout as Ceva's Theorem, but
    the collinearity condition equals -1 instead of +1 -- a transversal
    must cross an odd number (one or three) of the sides externally,
    which is exactly what forces the sign to flip relative to Ceva's
    concurrency case.
    """
    bd_dc, ce_ea, af_fb = (_numeric_or_same(v) for v in (bd_dc, ce_ea, af_fb))
    for name, val in (("bd_dc", bd_dc), ("ce_ea", ce_ea), ("af_fb", af_fb)):
        if val is None:
            raise TheoremError("MISSING_VALUE", f"Missing required ratio: '{name}'.")
        try:
            float(val)
        except (TypeError, ValueError):
            raise TheoremError("INVALID_VALUE", f"'{name}' must be a number, got: {val!r}")
        if val == 0:
            raise TheoremError(
                "INVALID_VALUE",
                f"'{name}' cannot be zero (a ratio of two lengths can't be 0 "
                "unless a vertex coincides with a division point).",
                details={name: val},
            )

    bd_dc, ce_ea, af_fb = float(bd_dc), float(ce_ea), float(af_fb)
    product = bd_dc * ce_ea * af_fb
    collinear = abs(product - (-1.0)) < tol

    return {
        "status": "ok",
        "theorem": "menelaus",
        "inputs": {"BD/DC": bd_dc, "CE/EA": ce_ea, "AF/FB": af_fb},
        "product": product,
        "collinear": collinear,
        "note": (
            "(BD/DC)\u00b7(CE/EA)\u00b7(AF/FB) = "
            f"{product:.6g} {'= -1, so D, E, F ARE collinear.' if collinear else '!= -1, so D, E, F are NOT collinear.'}"
        ),
    }


# ---------------------------------------------------------------------------
# Dispatch table -- used by app.py / main.py
# ---------------------------------------------------------------------------

SUPPORTED_THEOREMS = {
    "sine_rule": "EITHER (a, b, angle_A_degrees) for SSA, OR (a, angle_A_degrees, angle_B_degrees) for AAS/ASA",
    "cosine_rule": "EITHER (a, b, c) for SSS, OR (a, b, angle_C_degrees) for SAS",
    "tangent_rule": "a, b, angle_A_degrees, angle_B_degrees -- verifies the tangent-rule identity",
    "ceva": "bd_dc, ce_ea, af_fb (signed cevian ratios) -- checks concurrency",
    "menelaus": "bd_dc, ce_ea, af_fb (signed transversal ratios) -- checks collinearity",
}
