"""
tests/test_etc_position.py

Tests for etc_position.py: the reader of ETC's human-written formulas and the
"how much can we trust this position?" flag (`confidence`).

No network and no database are needed: the ETC page text and the verified
database are replaced with small fakes (monkeypatch), so these tests are fast
and always give the same result.
"""

import math

import pytest

import etc_position
from centers import Triangle

TRI = Triangle(A=(0.0, 0.0), B=(7.0, 0.0), C=(2.0, 5.0))


def _incenter(tri):
    a, b, c = tri.side_lengths()
    s = a + b + c
    return (
        (a * tri.A[0] + b * tri.B[0] + c * tri.C[0]) / s,
        (a * tri.A[1] + b * tri.B[1] + c * tri.C[1]) / s,
    )


def _weights(kind, text):
    return etc_position._weights_from_text(kind, text, etc_position._triangle_env(TRI))


# ---------------------------------------------------------------------------
# Reading ETC notation
# ---------------------------------------------------------------------------

def test_reads_plain_barycentrics():
    a, b, c = TRI.side_lengths()
    assert _weights("bary", "a : b : c") == pytest.approx((a, b, c))


def test_trilinears_are_converted_to_barycentrics():
    a, b, c = TRI.side_lengths()
    assert _weights("tri", "1 : 1 : 1") == pytest.approx((a, b, c))   # incenter


def test_short_form_means_cyclic_permutations():
    a, b, c = TRI.side_lengths()
    got = _weights("bary", "a(b + c - a) : :")
    want = (a * (b + c - a), b * (c + a - b), c * (a + b - c))
    assert got == pytest.approx(want)


def test_implicit_multiplication_and_trig_without_brackets():
    # "a cos A" = a*cos(A); ETC writes products with no * sign.
    env = etc_position._triangle_env(TRI)
    got = _weights("bary", "a cos A : b cos B : c cos C")
    want = (env["a"] * math.cos(env["A"]), env["b"] * math.cos(env["B"]),
            env["c"] * math.cos(env["C"]))
    assert got == pytest.approx(want)


def test_where_clause_definition():
    a, b, c = TRI.side_lengths()
    got = _weights("bary", "f(a,b,c) : f(b,c,a) : f(c,a,b), where f(a,b,c) = a")
    assert got == pytest.approx((a, b, c))


def test_unknown_notation_is_rejected_not_guessed():
    with pytest.raises(etc_position._Unsupported):
        _weights("bary", "foo : bar : baz")


def test_division_by_zero_is_undefined_not_a_crash():
    with pytest.raises(etc_position._Undefined):
        _weights("bary", "1/(a - a) : 1 : 1")


def test_listed_lines_both_notations():
    bare = "<p>X(5) lies on these lines: 2,3   4,8</p>"
    braced = "<p>X(5) lies on these lines: {2, 3}, {4, 8}</p>"
    assert etc_position._listed_lines(bare) == [(2, 3), (4, 8)]
    assert etc_position._listed_lines(braced) == [(2, 3), (4, 8)]


# ---------------------------------------------------------------------------
# The confidence flag
# ---------------------------------------------------------------------------

def test_confidence_rules():
    c = etc_position._confidence
    assert c("etc_formula", (2, 2)) == "cross_checked"
    assert c("etc_formula", (5, 5)) == "cross_checked"
    assert c("etc_formula", (1, 1)) == "unverified"       # one line is not enough
    assert c("etc_formula", (0, 0)) == "unverified"
    assert c("etc_formula", None) == "unverified"
    assert c("etc_formula", (2, 1)) == "unverified"       # a listed line disagrees
    assert c("construction", (0, 0)) == "unverified"
    assert c("verified", (0, 0)) == "hand_verified"
    assert c("verified", (1, 1)) == "hand_verified"
    assert c("verified", (1, 0)) == "unverified"          # database contradicted


def _install_fakes(monkeypatch, blocks, verified_points):
    """blocks: {id: ETC html}; verified_points: {id: (x, y)} for the fake DB."""

    def fake_block(kid):
        return blocks.get(kid)

    def fake_compute(kid, tri, db_path=None):
        if kid in verified_points:
            x, y = verified_points[kid]
            return {"status": "ok", "kimberling_id": kid, "name": f"fake {kid}",
                    "cartesian_position": {"x": x, "y": y},
                    "barycentric_weights_normalized": (1 / 3, 1 / 3, 1 / 3)}
        return {"status": "error", "error_code": "CENTER_NOT_FOUND", "message": "not in fake DB"}

    monkeypatch.setattr(etc_position, "_etc_block", fake_block)
    monkeypatch.setattr(etc_position, "compute_center", fake_compute)


def _block(n, body):
    return f'<h3 id="X{n}">X({n}) = TEST CENTER</h3>\n<p>{body}</p>'


def test_flagged_unverified_when_etc_lists_no_lines(monkeypatch):
    _install_fakes(monkeypatch, {9999: _block(9999, "Barycentrics a : b : c<br>")}, {})
    res = etc_position.locate_center(9999, TRI)
    assert res["status"] == "ok"
    assert res["method"] == "etc_formula"
    assert res["confidence"] == "unverified"
    assert "double-checked" in res["confidence_note"]
    # the point itself is still the right one
    ix, iy = _incenter(TRI)
    assert res["position"]["x"] == pytest.approx(ix)
    assert res["position"]["y"] == pytest.approx(iy)


def test_flagged_unverified_with_only_one_listed_line(monkeypatch):
    ix, iy = _incenter(TRI)
    body = "Barycentrics a : b : c<br>\nX(9999) lies on these lines: {1, 2}"
    _install_fakes(monkeypatch, {9999: _block(9999, body)},
                   {1: (ix + 1, iy), 2: (ix - 3, iy)})
    res = etc_position.locate_center(9999, TRI)
    assert res["confidence"] == "unverified"
    assert res["consistency"] == {"lines_checked": 1, "lines_passed": 1}


def test_cross_checked_when_two_listed_lines_pass(monkeypatch):
    ix, iy = _incenter(TRI)
    body = "Barycentrics a : b : c<br>\nX(9999) lies on these lines: {1, 2}, {3, 4}"
    _install_fakes(monkeypatch, {9999: _block(9999, body)},
                   {1: (ix + 1, iy), 2: (ix - 3, iy),        # horizontal line through I
                    3: (ix, iy + 1), 4: (ix, iy - 5)})       # vertical line through I
    res = etc_position.locate_center(9999, TRI)
    assert res["method"] == "etc_formula"
    assert res["confidence"] == "cross_checked"
    assert "confidence_note" not in res
    assert res["consistency"] == {"lines_checked": 2, "lines_passed": 2}


def test_partial_disagreement_is_flagged(monkeypatch):
    ix, iy = _incenter(TRI)
    body = "Barycentrics a : b : c<br>\nX(9999) lies on these lines: {1, 2}, {3, 4}"
    _install_fakes(monkeypatch, {9999: _block(9999, body)},
                   {1: (ix + 1, iy), 2: (ix - 3, iy),        # passes through I
                    3: (ix + 1, iy + 2), 4: (ix + 4, iy + 2)})  # a line that misses I
    res = etc_position.locate_center(9999, TRI)
    assert res["status"] == "ok"
    assert res["confidence"] == "unverified"
    assert "1 of the 2" in res["confidence_note"]


def test_verified_database_center_is_hand_verified(monkeypatch):
    _install_fakes(monkeypatch, {9998: _block(9998, "nothing useful here")},
                   {9998: (1.5, 2.5)})
    res = etc_position.locate_center(9998, TRI)
    assert res["method"] == "verified"
    assert res["confidence"] == "hand_verified"


def test_construction_is_flagged_unverified(monkeypatch):
    blocks = {9997: f'<h3 id="X9997">X(9997) = midpoint of X(1) and X(2)</h3>\n<p>no formula</p>'}
    _install_fakes(monkeypatch, blocks, {1: (0.0, 0.0), 2: (4.0, 2.0)})
    res = etc_position.locate_center(9997, TRI)
    assert res["method"] == "construction"
    assert res["position"] == {"x": 2.0, "y": 1.0}
    assert res["confidence"] == "unverified"
    assert "other centers" in res["confidence_note"]
