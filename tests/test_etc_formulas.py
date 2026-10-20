"""
tests/test_etc_formulas.py

Tests for routes/etc_formulas_api.py: /api/center-formulas hands the browser
a JavaScript expression per verified center. The expressions are plain
arithmetic, so Python can evaluate them too -- which lets us check that every
translated formula gives the same barycentric weights as centers.py does.
"""

import math

from centers import safe_eval_formula
from routes.etc_formulas_api import formula_to_js

TRIANGLES = [
    ((0, 0), (4, 0), (0, 3)),
    ((1, 1), (10, 1), (4, 7)),
    ((-2.5, 3), (6, -1), (3, 5.5)),
]


def _sec(x): return 1 / math.cos(x)
def _csc(x): return 1 / math.sin(x)
def _cot(x): return 1 / math.tan(x)
def _mod(x, y): return ((x % y) + y) % y


def _js_env(a, b, c):
    A = math.acos((b * b + c * c - a * a) / (2 * b * c))
    B = math.acos((a * a + c * c - b * b) / (2 * a * c))
    return dict(a=a, b=b, c=c, A=A, B=B, C=math.pi - A - B,
                sqrt=math.sqrt, sin=math.sin, cos=math.cos, tan=math.tan,
                sec=_sec, csc=_csc, cot=_cot, pi=math.pi, pow=math.pow, mod=_mod)


def test_endpoint_lists_centers(client):
    resp = client.get("/api/center-formulas")
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["status"] == "ok"
    assert data["count"] == len(data["centers"]) > 0
    by_id = {c["id"]: c for c in data["centers"]}
    assert by_id[2]["js"] == "[1.0,1.0,1.0]"            # centroid
    assert all(set(c) == {"id", "name", "js"} for c in data["centers"])


def test_every_translated_formula_matches_python(client):
    centers = client.get("/api/center-formulas").get_json()["centers"]
    # Need the original strings to compare against: read them from the DB.
    from routes.centers_api import get_db
    with get_db() as conn:
        original = {r["kimberling_id"]: r["barycentric"] for r in conn.execute(
            "SELECT kimberling_id, barycentric FROM triangle_centers")}

    for ctr in centers:
        for P in TRIANGLES:
            a = math.dist(P[1], P[2]); b = math.dist(P[2], P[0]); c = math.dist(P[0], P[1])
            try:
                want = safe_eval_formula(original[ctr["id"]], a, b, c)
            except Exception:
                continue  # undefined for this triangle in Python too
            got = eval(ctr["js"], {"__builtins__": {}}, _js_env(a, b, c))
            assert all(math.isclose(x, y, rel_tol=1e-9, abs_tol=1e-9)
                       for x, y in zip(want, got)), ctr["id"]


def test_formula_to_js_unary_minus_and_power():
    # JS rejects -a**2 outright; the translation must be explicit.
    assert formula_to_js("(-a**2, 1, 1)") == "[(-pow(a,2.0)),1.0,1.0]"


def test_formula_to_js_rejects_unsafe_input():
    for bad in ("(__import__('os'), 1, 1)", "(a, b)", "(a.real, 1, 1)", "(open('x'), 1, 1)"):
        try:
            formula_to_js(bad)
        except Exception:
            continue
        raise AssertionError(f"accepted unsafe formula: {bad}")
