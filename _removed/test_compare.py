"""
tests/test_compare.py

Tests for routes/compare_api.py: the /compare page, /api/compare (every
verified center for one triangle + collinear groups) and /api/compare.csv.
"""

from routes.compare_api import find_collinear_groups

RIGHT = "(0,0),(4,0),(0,3)"
SCALENE = "(1,1),(10,1),(4,7)"
EQUILATERAL = "(0,0),(2,0),(1,1.7320508075688772)"


def _groups(data):
    return {tuple(g["ids"]): g["label"] for g in data["collinear_groups"]}


def test_compare_page_loads(client):
    assert client.get("/compare").status_code == 200


def test_compare_right_triangle(client):
    resp = client.get(f"/api/compare?triangle={RIGHT}")
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["status"] == "ok"
    # X(19) (Clawson point) is undefined for a right triangle.
    assert [s["id"] for s in data["skipped"]] == [19]
    assert data["count"] == len(data["centers"])

    groups = _groups(data)
    assert groups[(2, 3, 4, 5, 20, 21)] == "Euler line"
    assert groups[(1, 2, 8, 10)] == "Nagel line"


def test_compare_positions_match_known_values(client):
    data = client.get(f"/api/compare?triangle={RIGHT}").get_json()
    by_id = {c["id"]: c for c in data["centers"]}
    # 3-4-5 right triangle: G=(4/3,1), O=(2,1.5), I=(1,1), H=(0,0), N=(1,0.75)
    for cid, (x, y) in {2: (4 / 3, 1), 3: (2, 1.5), 1: (1, 1), 4: (0, 0), 5: (1, 0.75)}.items():
        assert abs(by_id[cid]["x"] - x) < 1e-9
        assert abs(by_id[cid]["y"] - y) < 1e-9


def test_compare_scalene_has_euler_line_with_clawson_point(client):
    data = client.get(f"/api/compare?triangle={SCALENE}").get_json()
    assert data["skipped"] == []
    assert _groups(data)[(2, 3, 4, 5, 19, 20, 21)] == "Euler line"


def test_compare_equilateral_everything_coincides(client):
    data = client.get(f"/api/compare?triangle={EQUILATERAL}").get_json()
    assert data["status"] == "ok"
    assert data["collinear_groups"] == []
    assert len(data["coincident"]) == 1
    assert len(data["coincident"][0]) == data["count"]


def test_compare_degenerate_triangle_is_400(client):
    resp = client.get("/api/compare?triangle=(0,0),(1,0),(2,0)")
    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "DEGENERATE_TRIANGLE"


def test_compare_missing_param_is_400(client):
    resp = client.get("/api/compare")
    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "MISSING_TRIANGLE"


def test_compare_malformed_is_400(client):
    resp = client.get("/api/compare?triangle=not,a,triangle")
    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "INVALID_TRIANGLE_INPUT"


def test_compare_csv(client):
    resp = client.get(f"/api/compare.csv?triangle={RIGHT}")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert "attachment" in resp.headers["Content-Disposition"]
    lines = resp.get_data(as_text=True).splitlines()
    assert lines[0] == "id,name,x,y,collinear_with"
    assert any(line.startswith("X(2),Centroid") and "Euler line" in line for line in lines)


def test_compare_csv_error_is_json_400(client):
    resp = client.get("/api/compare.csv")
    assert resp.status_code == 400


# ---------------------------------------------------------------- unit tests
def _c(i, x, y):
    return {"id": i, "name": f"P{i}", "x": x, "y": y}


def test_find_collinear_groups_basic():
    pts = [_c(1, 0, 0), _c(2, 1, 1), _c(3, 2, 2), _c(4, 0, 5)]
    clusters, groups = find_collinear_groups(pts, scale=5)
    assert groups == [[1, 2, 3]]
    assert len(clusters) == 4


def test_find_collinear_groups_merges_coincident_points():
    pts = [_c(1, 0, 0), _c(2, 0, 0), _c(3, 1, 1), _c(4, 2, 2)]
    clusters, groups = find_collinear_groups(pts, scale=2)
    assert len(clusters) == 3
    # Coincident centers stay together inside the same line.
    assert groups == [[1, 2, 3, 4]]


def test_find_collinear_groups_none_when_not_collinear():
    pts = [_c(1, 0, 0), _c(2, 1, 0), _c(3, 0, 1)]
    _, groups = find_collinear_groups(pts, scale=1)
    assert groups == []
