"""
tests/test_scenes.py

Scene save / load tests that use the object types the geometry workspace
really produces -- including the derivedCircle / derivedPoint objects behind
every triangle circle and triangle center (see static/geometry/model.js).

Regression: scene_store.py once rejected those two types, so any scene with
a circumcircle, incenter, etc. could not be saved.
"""

import json

import scene_store

NAME = "test_derived_objects_scene"


def _triangle_points():
    return [
        {"id": 1, "type": "point", "x": 0, "y": 0, "label": "A"},
        {"id": 2, "type": "point", "x": 4, "y": 0, "label": "B"},
        {"id": 3, "type": "point", "x": 0, "y": 3, "label": "C"},
    ]


def _put(client, name, scene):
    return client.put(
        f"/api/scenes/{name}",
        data=json.dumps(scene),
        content_type="application/json",
    )


def test_scene_with_derived_circle_and_point_roundtrips(client):
    scene = {
        "version": 1,
        "objects": _triangle_points() + [
            {"id": 4, "type": "derivedCircle", "A": 1, "B": 2, "C": 3,
             "formulaName": "circumcircle", "label": "", "visible": True},
            {"id": 5, "type": "derivedPoint", "A": 1, "B": 2, "C": 3,
             "formulaName": "incenter", "label": "I", "visible": True},
            # excircles-style entry: one slot of an array formula
            {"id": 6, "type": "derivedCircle", "A": 1, "B": 2, "C": 3,
             "formulaName": "excircles", "index": 1},
            # any verified Kimberling center
            {"id": 7, "type": "derivedPoint", "A": 1, "B": 2, "C": 3,
             "formulaName": "etc", "index": 13},
        ],
    }
    try:
        assert _put(client, NAME, scene).status_code == 200

        resp = client.get(f"/api/scenes/{NAME}")
        assert resp.status_code == 200
        types = [o["type"] for o in resp.get_json()["scene"]["objects"]]
        assert types.count("derivedCircle") == 2
        assert types.count("derivedPoint") == 2
    finally:
        client.delete(f"/api/scenes/{NAME}")


def test_derived_object_with_missing_vertex_is_rejected(client):
    scene = {
        "objects": _triangle_points() + [
            {"id": 4, "type": "derivedCircle", "A": 1, "B": 2, "C": 99,
             "formulaName": "circumcircle"},
        ],
    }
    resp = _put(client, "test_dangling_derived_scene", scene)
    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "DANGLING_REFERENCE"


def test_scene_with_ellipse_roundtrips(client):
    name = "test_ellipse_scene"
    scene = {
        "version": 1,
        "objects": [
            {"id": 1, "type": "point", "x": -3, "y": 0, "label": "A"},
            {"id": 2, "type": "point", "x": 3, "y": 0, "label": "B"},
            {"id": 3, "type": "point", "x": 0, "y": 4, "label": "C"},
            {"id": 4, "type": "ellipse", "f1": 1, "f2": 2, "through": 3,
             "label": "", "visible": True},
            {"id": 5, "type": "constructedPoint", "kind": "midpoint",
             "refs": [1, 2], "x": 0, "y": 0, "label": "O"},
        ],
    }
    try:
        assert _put(client, name, scene).status_code == 200
        resp = client.get(f"/api/scenes/{name}")
        assert resp.status_code == 200
        types = [o["type"] for o in resp.get_json()["scene"]["objects"]]
        assert types.count("ellipse") == 1
    finally:
        client.delete(f"/api/scenes/{name}")


def test_ellipse_with_missing_focus_is_rejected(client):
    scene = {
        "objects": _triangle_points() + [
            {"id": 4, "type": "ellipse", "f1": 1, "f2": 99, "through": 3},
        ],
    }
    resp = _put(client, "test_dangling_ellipse_scene", scene)
    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "DANGLING_REFERENCE"


def test_unknown_object_type_still_rejected(client):
    scene = {"objects": [{"id": 1, "type": "banana"}]}
    resp = _put(client, "test_unknown_type_scene", scene)
    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "UNKNOWN_OBJECT_TYPE"


def test_scene_name_cannot_escape_scenes_folder(client):
    for bad in ("..%2Fevil", "a%2F..%2Fb", "x" * 61):
        resp = _put(client, bad, {"objects": []})
        assert resp.status_code in (400, 404)
    assert scene_store.list_scenes().count("evil") == 0
