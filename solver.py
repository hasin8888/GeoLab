"""
solver.py

Coordinate-free triangle problem solver.

You give it whatever you KNOW about a triangle (any mix of sides, angles,
area, radii, ...) and it derives everything else it can, one justified step
at a time, using only classical, well-known results:

    Angle sum, Law of Sines, Law of Cosines, Heron's formula,
    Area = 1/2 ab sin(gamma), R = abc / (4*Area), r = Area / s,
    and the standard height / median / bisector formulas.

No (x, y) coordinates and no barycentric coordinates are used anywhere --
the ONLY quantities are lengths and angles:

    a, b, c        side lengths (a = BC, b = CA, c = AB)
    alpha,beta,gamma   interior angles at A, B, C (stored in DEGREES)
    s              semi-perimeter
    Delta          area
    R, r           circumradius, inradius

How it works
------------
It is a small forward-chaining engine. Each RULE says "if you know these
quantities, then this other quantity follows, by this named theorem". The
engine keeps applying rules to the set of known values until nothing new
can be derived (a fixed point). Every application is recorded, so the
result reads as a step-by-step solution.

Output is always the same four-part layout:
    1. given        -- what was supplied
    2. notation     -- what each symbol means
    3. steps        -- each deduction, with the theorem used
    4. conclusion   -- everything that is now known, plus a consistency check

Response conventions mirror the rest of the project: a SolverError carries a
code/message/details and to_payload() gives the usual status/error_code JSON.
"""

import math
from typing import Any, Callable, Dict, List, Optional, Tuple


class SolverError(Exception):
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
# Quantities
# ---------------------------------------------------------------------------

# name -> (description, kind). kind: "length" | "angle" | "area"
QUANTITIES: Dict[str, Tuple[str, str]] = {
    "a": ("side BC (opposite A)", "length"),
    "b": ("side CA (opposite B)", "length"),
    "c": ("side AB (opposite C)", "length"),
    "alpha": ("interior angle at A, in degrees", "angle"),
    "beta": ("interior angle at B, in degrees", "angle"),
    "gamma": ("interior angle at C, in degrees", "angle"),
    "s": ("semi-perimeter (a+b+c)/2", "length"),
    "Delta": ("area of the triangle", "area"),
    "R": ("circumradius", "length"),
    "r": ("inradius", "length"),
    "h_a": ("altitude from A onto BC", "length"),
    "h_b": ("altitude from B onto CA", "length"),
    "h_c": ("altitude from C onto AB", "length"),
    "m_a": ("median from A to the midpoint of BC", "length"),
    "m_b": ("median from B to the midpoint of CA", "length"),
    "m_c": ("median from C to the midpoint of AB", "length"),
}

# Display symbols (math-italic Greek), used only for pretty output.
SYMBOL = {
    "alpha": "\u03b1", "beta": "\u03b2", "gamma": "\u03b3",
    "Delta": "\u0394",
}


def sym(name: str) -> str:
    return SYMBOL.get(name, name)


def _sin(deg: float) -> float:
    return math.sin(math.radians(deg))


def _cos(deg: float) -> float:
    return math.cos(math.radians(deg))


def _acos_deg(x: float) -> float:
    return math.degrees(math.acos(max(-1.0, min(1.0, x))))


def _asin_deg(x: float) -> float:
    return math.degrees(math.asin(max(-1.0, min(1.0, x))))


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------
# A Rule computes ONE target quantity from a tuple of required quantities.
#   needs   -- names that must already be known
#   target  -- the name this rule produces
#   theorem -- human-readable justification
#   formula -- the formula as text (shown to the user)
#   fn      -- takes a dict of known values, returns the target value

class Rule:
    def __init__(self, needs: Tuple[str, ...], target: str, theorem: str,
                 formula: str, fn: Callable[[Dict[str, float]], float]):
        self.needs = needs
        self.target = target
        self.theorem = theorem
        self.formula = formula
        self.fn = fn


def _build_rules() -> List[Rule]:
    R: List[Rule] = []

    # --- Angle sum ---------------------------------------------------------
    R.append(Rule(("alpha", "beta"), "gamma", "Angle sum of a triangle",
                  "\u03b3 = 180\u00b0 \u2212 \u03b1 \u2212 \u03b2",
                  lambda k: 180.0 - k["alpha"] - k["beta"]))
    R.append(Rule(("alpha", "gamma"), "beta", "Angle sum of a triangle",
                  "\u03b2 = 180\u00b0 \u2212 \u03b1 \u2212 \u03b3",
                  lambda k: 180.0 - k["alpha"] - k["gamma"]))
    R.append(Rule(("beta", "gamma"), "alpha", "Angle sum of a triangle",
                  "\u03b1 = 180\u00b0 \u2212 \u03b2 \u2212 \u03b3",
                  lambda k: 180.0 - k["beta"] - k["gamma"]))

    # --- Semi-perimeter ----------------------------------------------------
    R.append(Rule(("a", "b", "c"), "s", "Definition of semi-perimeter",
                  "s = (a + b + c) / 2",
                  lambda k: (k["a"] + k["b"] + k["c"]) / 2))
    R.append(Rule(("s", "a", "b"), "c", "Definition of semi-perimeter",
                  "c = 2s \u2212 a \u2212 b",
                  lambda k: 2 * k["s"] - k["a"] - k["b"]))
    R.append(Rule(("s", "a", "c"), "b", "Definition of semi-perimeter",
                  "b = 2s \u2212 a \u2212 c",
                  lambda k: 2 * k["s"] - k["a"] - k["c"]))
    R.append(Rule(("s", "b", "c"), "a", "Definition of semi-perimeter",
                  "a = 2s \u2212 b \u2212 c",
                  lambda k: 2 * k["s"] - k["b"] - k["c"]))

    # --- Law of Cosines: sides -> angles (SSS) -----------------------------
    R.append(Rule(("a", "b", "c"), "alpha", "Law of Cosines",
                  "cos \u03b1 = (b\u00b2 + c\u00b2 \u2212 a\u00b2) / (2bc)",
                  lambda k: _acos_deg((k["b"]**2 + k["c"]**2 - k["a"]**2) / (2 * k["b"] * k["c"]))))
    R.append(Rule(("a", "b", "c"), "beta", "Law of Cosines",
                  "cos \u03b2 = (a\u00b2 + c\u00b2 \u2212 b\u00b2) / (2ac)",
                  lambda k: _acos_deg((k["a"]**2 + k["c"]**2 - k["b"]**2) / (2 * k["a"] * k["c"]))))
    R.append(Rule(("a", "b", "c"), "gamma", "Law of Cosines",
                  "cos \u03b3 = (a\u00b2 + b\u00b2 \u2212 c\u00b2) / (2ab)",
                  lambda k: _acos_deg((k["a"]**2 + k["b"]**2 - k["c"]**2) / (2 * k["a"] * k["b"]))))

    # --- Law of Cosines: SAS -> third side ---------------------------------
    R.append(Rule(("b", "c", "alpha"), "a", "Law of Cosines (SAS)",
                  "a\u00b2 = b\u00b2 + c\u00b2 \u2212 2bc cos \u03b1",
                  lambda k: math.sqrt(max(0.0, k["b"]**2 + k["c"]**2 - 2 * k["b"] * k["c"] * _cos(k["alpha"])))))
    R.append(Rule(("a", "c", "beta"), "b", "Law of Cosines (SAS)",
                  "b\u00b2 = a\u00b2 + c\u00b2 \u2212 2ac cos \u03b2",
                  lambda k: math.sqrt(max(0.0, k["a"]**2 + k["c"]**2 - 2 * k["a"] * k["c"] * _cos(k["beta"])))))
    R.append(Rule(("a", "b", "gamma"), "c", "Law of Cosines (SAS)",
                  "c\u00b2 = a\u00b2 + b\u00b2 \u2212 2ab cos \u03b3",
                  lambda k: math.sqrt(max(0.0, k["a"]**2 + k["b"]**2 - 2 * k["a"] * k["b"] * _cos(k["gamma"])))))

    # --- Law of Sines: one side + its opposite angle + another angle -------
    pairs = [("a", "alpha"), ("b", "beta"), ("c", "gamma")]
    for side, ang in pairs:
        for other_side, other_ang in pairs:
            if other_side == side:
                continue
            R.append(Rule(
                (side, ang, other_ang), other_side, "Law of Sines",
                f"{other_side} = {side} \u00b7 sin {sym(other_ang)} / sin {sym(ang)}",
                (lambda s_, a_, oa_: lambda k: k[s_] * _sin(k[oa_]) / _sin(k[a_]))(side, ang, other_ang),
            ))

    # --- Law of Sines: two sides + the angle opposite one of them (SSA) ----
    # Gives the OTHER angle. Ambiguous in general: we take the acute solution
    # only when it is the sole possibility, otherwise we flag it (see solve()).
    # (The engine treats SSA specially, so it is handled there, not as a Rule.)

    # --- Area --------------------------------------------------------------
    R.append(Rule(("s", "a", "b", "c"), "Delta", "Heron's formula",
                  "\u0394 = \u221a[ s(s\u2212a)(s\u2212b)(s\u2212c) ]",
                  lambda k: math.sqrt(max(0.0, k["s"] * (k["s"] - k["a"]) * (k["s"] - k["b"]) * (k["s"] - k["c"])))))
    R.append(Rule(("a", "b", "gamma"), "Delta", "Area from two sides and the included angle",
                  "\u0394 = \u00bd ab sin \u03b3",
                  lambda k: 0.5 * k["a"] * k["b"] * _sin(k["gamma"])))
    R.append(Rule(("b", "c", "alpha"), "Delta", "Area from two sides and the included angle",
                  "\u0394 = \u00bd bc sin \u03b1",
                  lambda k: 0.5 * k["b"] * k["c"] * _sin(k["alpha"])))
    R.append(Rule(("a", "c", "beta"), "Delta", "Area from two sides and the included angle",
                  "\u0394 = \u00bd ac sin \u03b2",
                  lambda k: 0.5 * k["a"] * k["c"] * _sin(k["beta"])))
    R.append(Rule(("r", "s"), "Delta", "Inradius-area relation",
                  "\u0394 = r \u00b7 s",
                  lambda k: k["r"] * k["s"]))
    R.append(Rule(("a", "b", "c", "R"), "Delta", "Circumradius-area relation",
                  "\u0394 = abc / (4R)",
                  lambda k: k["a"] * k["b"] * k["c"] / (4 * k["R"])))

    # --- Radii -------------------------------------------------------------
    R.append(Rule(("Delta", "s"), "r", "Inradius-area relation",
                  "r = \u0394 / s",
                  lambda k: k["Delta"] / k["s"]))
    R.append(Rule(("a", "b", "c", "Delta"), "R", "Circumradius formula",
                  "R = abc / (4\u0394)",
                  lambda k: k["a"] * k["b"] * k["c"] / (4 * k["Delta"])))
    for side, ang in pairs:
        R.append(Rule(
            (side, ang), "R", "Extended Law of Sines",
            f"R = {side} / (2 sin {sym(ang)})",
            (lambda s_, a_: lambda k: k[s_] / (2 * _sin(k[a_])))(side, ang),
        ))
        R.append(Rule(
            ("R", ang), side, "Extended Law of Sines",
            f"{side} = 2R sin {sym(ang)}",
            (lambda s_, a_: lambda k: 2 * k["R"] * _sin(k[a_]))(side, ang),
        ))

    # --- Altitudes ---------------------------------------------------------
    for side, h in (("a", "h_a"), ("b", "h_b"), ("c", "h_c")):
        R.append(Rule(
            ("Delta", side), h, "Area = \u00bd \u00b7 base \u00b7 height",
            f"{h} = 2\u0394 / {side}",
            (lambda s_: lambda k: 2 * k["Delta"] / k[s_])(side),
        ))
        R.append(Rule(
            ("Delta", h), side, "Area = \u00bd \u00b7 base \u00b7 height",
            f"{side} = 2\u0394 / {h}",
            (lambda h_: lambda k: 2 * k["Delta"] / k[h_])(h),
        ))

    # --- Medians (Apollonius) ---------------------------------------------
    R.append(Rule(("a", "b", "c"), "m_a", "Apollonius' theorem (median formula)",
                  "m_a = \u00bd \u221a(2b\u00b2 + 2c\u00b2 \u2212 a\u00b2)",
                  lambda k: 0.5 * math.sqrt(max(0.0, 2 * k["b"]**2 + 2 * k["c"]**2 - k["a"]**2))))
    R.append(Rule(("a", "b", "c"), "m_b", "Apollonius' theorem (median formula)",
                  "m_b = \u00bd \u221a(2a\u00b2 + 2c\u00b2 \u2212 b\u00b2)",
                  lambda k: 0.5 * math.sqrt(max(0.0, 2 * k["a"]**2 + 2 * k["c"]**2 - k["b"]**2))))
    R.append(Rule(("a", "b", "c"), "m_c", "Apollonius' theorem (median formula)",
                  "m_c = \u00bd \u221a(2a\u00b2 + 2b\u00b2 \u2212 c\u00b2)",
                  lambda k: 0.5 * math.sqrt(max(0.0, 2 * k["a"]**2 + 2 * k["b"]**2 - k["c"]**2))))

    return R


_RULES = _build_rules()


# ---------------------------------------------------------------------------
# Validation of the supplied data
# ---------------------------------------------------------------------------

def _to_float(name: str, value: Any) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise SolverError("INVALID_VALUE", f"'{name}' must be a number, got: {value!r}")
    if not math.isfinite(v):
        raise SolverError("INVALID_VALUE", f"'{name}' must be finite, got: {value!r}")
    return v


def _validate_given(given: Dict[str, Any]) -> Dict[str, float]:
    if not isinstance(given, dict) or not given:
        raise SolverError("MISSING_VALUE", "Provide at least one known quantity.")
    out: Dict[str, float] = {}
    for name, raw in given.items():
        if raw is None or raw == "":
            continue  # blank field in a form = "unknown"
        if name not in QUANTITIES:
            raise SolverError(
                "UNKNOWN_QUANTITY",
                f"Unknown quantity '{name}'.",
                details={"supported": sorted(QUANTITIES)},
            )
        v = _to_float(name, raw)
        kind = QUANTITIES[name][1]
        if kind == "angle" and not (0 < v < 180):
            raise SolverError(
                "INVALID_DIMENSION",
                f"'{name}' must be strictly between 0 and 180 degrees, got {v}.",
                details={name: v},
            )
        if kind != "angle" and v <= 0:
            raise SolverError(
                "INVALID_DIMENSION",
                f"'{name}' must be positive, got {v}.",
                details={name: v},
            )
        out[name] = v
    if not out:
        raise SolverError("MISSING_VALUE", "Provide at least one known quantity.")
    return out


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------

def _fmt(name: str, v: float) -> str:
    unit = "\u00b0" if QUANTITIES[name][1] == "angle" else ""
    return f"{v:.6g}{unit}"


def _try_ssa(known: Dict[str, float], steps: List[Dict[str, Any]],
             warnings: List[str]) -> bool:
    """
    SSA: two sides and the angle opposite ONE of them determine the angle
    opposite the other side via the Law of Sines -- but only up to the
    acute/obtuse ambiguity. We use the acute value when the triangle is
    otherwise forced to be that one, and otherwise report the ambiguity.
    Returns True if it added something.
    """
    pairs = [("a", "alpha"), ("b", "beta"), ("c", "gamma")]
    for s1, a1 in pairs:
        for s2, a2 in pairs:
            if s1 == s2 or a2 in known:
                continue
            if s1 in known and a1 in known and s2 in known:
                ratio = known[s2] * _sin(known[a1]) / known[s1]
                if ratio > 1 + 1e-9:
                    raise SolverError(
                        "NO_TRIANGLE",
                        f"No triangle exists: sin {sym(a2)} would be "
                        f"{ratio:.6g} > 1 (side {s1} is too short).",
                        details={"sin_" + a2: ratio},
                    )
                ratio = min(1.0, ratio)
                acute = _asin_deg(ratio)
                obtuse = 180.0 - acute
                candidates = []
                for cand in {round(acute, 12), round(obtuse, 12)}:
                    if cand + known[a1] < 180.0 - 1e-9:
                        candidates.append(cand)
                if not candidates:
                    raise SolverError(
                        "NO_TRIANGLE",
                        "No triangle exists for these values (angles would sum to 180\u00b0 or more).",
                    )
                if len(candidates) == 1:
                    known[a2] = candidates[0]
                    steps.append({
                        "derived": a2,
                        "value": candidates[0],
                        "theorem": "Law of Sines (SSA, one valid solution)",
                        "formula": f"sin {sym(a2)} = {s2} \u00b7 sin {sym(a1)} / {s1}",
                        "uses": {s1: known[s1], a1: known[a1], s2: known[s2]},
                    })
                    return True
                # Two valid triangles: take the acute one, but say so loudly.
                chosen = min(candidates)
                known[a2] = chosen
                other = max(candidates)
                warnings.append(
                    f"SSA ambiguous case: {sym(a2)} could be {chosen:.6g}\u00b0 or "
                    f"{other:.6g}\u00b0 (two different triangles fit the data). "
                    f"The acute solution ({chosen:.6g}\u00b0) was used. Supply one more "
                    f"quantity (e.g. another angle or side) to pick the other."
                )
                steps.append({
                    "derived": a2,
                    "value": chosen,
                    "theorem": "Law of Sines (SSA, ambiguous case \u2014 acute root taken)",
                    "formula": f"sin {sym(a2)} = {s2} \u00b7 sin {sym(a1)} / {s1}",
                    "uses": {s1: known[s1], a1: known[a1], s2: known[s2]},
                })
                return True
    return False


def solve(given: Dict[str, Any], want: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Derive everything derivable from `given`.

    given -- dict of known quantities (see QUANTITIES). Angles in degrees.
    want  -- optional list of quantity names the user cares about. The full
             derivation is still done; `want` only controls the headline
             answer and reports which wanted values could NOT be derived.
    """
    known = _validate_given(given)
    initial = dict(known)
    steps: List[Dict[str, Any]] = []
    warnings: List[str] = []

    if want:
        for w in want:
            if w not in QUANTITIES:
                raise SolverError(
                    "UNKNOWN_QUANTITY", f"Unknown target quantity '{w}'.",
                    details={"supported": sorted(QUANTITIES)},
                )

    # Forward-chain to a fixed point.
    progress = True
    guard = 0
    while progress and guard < 200:
        guard += 1
        progress = False
        for rule in _RULES:
            if rule.target in known:
                continue
            if all(n in known for n in rule.needs):
                try:
                    value = rule.fn(known)
                except (ZeroDivisionError, ValueError):
                    continue
                if not math.isfinite(value):
                    continue
                if QUANTITIES[rule.target][1] == "angle":
                    if not (0 < value < 180):
                        raise SolverError(
                            "INVALID_TRIANGLE",
                            f"The data is inconsistent: {rule.target} would be "
                            f"{value:.6g}\u00b0, which is not a valid triangle angle.",
                            details={rule.target: value, "rule": rule.theorem},
                        )
                elif value <= 0:
                    raise SolverError(
                        "INVALID_TRIANGLE",
                        f"The data is inconsistent: {rule.target} would be {value:.6g} "
                        "(must be positive).",
                        details={rule.target: value, "rule": rule.theorem},
                    )
                known[rule.target] = value
                steps.append({
                    "derived": rule.target,
                    "value": value,
                    "theorem": rule.theorem,
                    "formula": rule.formula,
                    "uses": {n: known[n] for n in rule.needs},
                })
                progress = True
        if not progress and _try_ssa(known, steps, warnings):
            progress = True

    check = _consistency_check(known)

    if not any(k in known for k in ("a", "b", "c")):
        warnings.append(
            "Only angles (and/or radii/area) were given, so the triangle's SIZE is "
            "not fixed \u2014 only its shape. Add at least one side length or the area "
            "to get lengths."
        )

    wanted_out = None
    if want:
        wanted_out = {}
        for w in want:
            wanted_out[w] = known.get(w)
        missing = [w for w in want if w not in known]
        if missing:
            warnings.append(
                "Could not derive: " + ", ".join(sym(m) for m in missing) +
                ". The given data does not determine "
                f"{'it' if len(missing) == 1 else 'them'}. Try supplying more "
                "known values (a triangle needs three independent measurements, "
                "at least one of them a length)."
            )

    return {
        "status": "ok",
        "method": "coordinate-free (lengths and angles only)",
        "given": {k: {"value": v, "meaning": QUANTITIES[k][0]} for k, v in initial.items()},
        "notation": {k: QUANTITIES[k][0] for k in sorted(set(initial) | {s["derived"] for s in steps})},
        "steps": steps,
        "conclusion": {
            "known": {k: known[k] for k in known},
            "wanted": wanted_out,
        },
        "consistency_check": check,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Consistency check (independent of how the values were derived)
# ---------------------------------------------------------------------------

def _consistency_check(k: Dict[str, float]) -> Dict[str, Any]:
    """Re-test well-known identities on the final values. All must hold."""
    results: List[Dict[str, Any]] = []

    def add(name: str, lhs: float, rhs: float, tol: float = 1e-6) -> None:
        scale = max(1.0, abs(lhs), abs(rhs))
        results.append({"identity": name, "lhs": lhs, "rhs": rhs,
                        "holds": abs(lhs - rhs) <= tol * scale})

    if all(x in k for x in ("alpha", "beta", "gamma")):
        add("\u03b1 + \u03b2 + \u03b3 = 180\u00b0", k["alpha"] + k["beta"] + k["gamma"], 180.0)
    if all(x in k for x in ("a", "b", "c")):
        a, b, c = k["a"], k["b"], k["c"]
        results.append({"identity": "Triangle inequality",
                        "lhs": None, "rhs": None,
                        "holds": a + b > c and b + c > a and c + a > b})
    if all(x in k for x in ("a", "b", "c", "alpha", "beta", "gamma")):
        ra = k["a"] / _sin(k["alpha"])
        rb = k["b"] / _sin(k["beta"])
        rc = k["c"] / _sin(k["gamma"])
        add("a/sin\u03b1 = b/sin\u03b2", ra, rb)
        add("b/sin\u03b2 = c/sin\u03b3", rb, rc)
    if all(x in k for x in ("a", "b", "c", "gamma")):
        add("c\u00b2 = a\u00b2 + b\u00b2 \u2212 2ab cos\u03b3",
            k["c"]**2, k["a"]**2 + k["b"]**2 - 2 * k["a"] * k["b"] * _cos(k["gamma"]))
    if all(x in k for x in ("a", "b", "c", "R", "Delta")):
        add("\u0394 = abc/(4R)", k["Delta"], k["a"] * k["b"] * k["c"] / (4 * k["R"]))
    if all(x in k for x in ("r", "s", "Delta")):
        add("\u0394 = rs", k["Delta"], k["r"] * k["s"])
    if all(x in k for x in ("R", "r", "alpha", "beta", "gamma")):
        rhs = 4 * k["R"] * _sin(k["alpha"] / 2) * _sin(k["beta"] / 2) * _sin(k["gamma"] / 2)
        add("r = 4R sin(\u03b1/2) sin(\u03b2/2) sin(\u03b3/2)", k["r"], rhs)

    return {"all_hold": all(r["holds"] for r in results) if results else None,
            "checks": results}


# ---------------------------------------------------------------------------
# Metadata for the UI
# ---------------------------------------------------------------------------

SUPPORTED_QUANTITIES = {k: v[0] for k, v in QUANTITIES.items()}
