"""
scene_store.py

Persistence + validation for interactive geometry scenes (the JSON produced
by static/geometry/model.js -> Scene.toJSON()).

Responsibilities:
  - Validate an incoming scene BEFORE it is written to disk: known object
    types only, required fields present, numbers finite, and every reference
    (segment endpoints, polygon vertices, ...) pointing at a Point that
    actually exists in the same scene.
  - Store each scene as scenes/<name>.json, with the name sanitised so a
    request can never escape the scenes folder (no "../" tricks).
  - Return the same structured payloads used elsewhere in this project
    (status / error_code / message / details).
"""

import json
import math
import os
import re
from typing import Any, Dict, List

SCENES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenes")

MAX_OBJECTS = 5000
MAX_SCENE_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_LABEL_LEN = 2000   # LaTeX notes can be long-ish
MAX_COLOR_LEN = 64

_NAME_RE = re.compile(r"^[A-Za-z0-9 _\-]{1,60}$")

# type -> names of fields that hold references to Point ids
_REF_FIELDS = {
    "point": [],
    "text": [],
    "segment": ["p1", "p2"],
    "line": ["p1", "p2"],
    "circle": ["center", "through"],
    "semicircle": ["p1", "p2"],
    # Ellipse from its two foci and one point on it (see model.js).
    "ellipse": ["f1", "f2", "through"],
    "angle": ["p1", "vertex", "p3"],
    "polygon": [],  # 'vertices' is a list, handled separately
    # Triangle circles / centers built on 3 source vertices (see model.js).
    "derivedCircle": ["A", "B", "C"],
    "derivedPoint": ["A", "B", "C"],
    # Live point on the crossing of two shapes: 'o1' / 'o2' reference any
    # shape (not a Point), so they are checked separately below.
    "intersectionPoint": [],
    # Live points created by the geometry tools (see model.js): a point sliding
    # on a shape ('glider': host + t) and a point defined by a rule on other
    # points ('constructedPoint': kind + refs). Their references are checked
    # separately below.
    "glider": [],
    "constructedPoint": [],
}

# Every type that can be used as a point (an endpoint of a segment, a polygon
# vertex, a vertex of a triangle circle, ...).
_POINT_LIKE = {"point", "intersectionPoint", "derivedPoint", "glider", "constructedPoint"}
_CONSTRUCTED_KINDS = {"midpoint", "perp", "parallel", "bisector", "apex", "offset", "parallelogram"}


class SceneError(Exception):
    """Same shape as ShapeError / SolidError / TheoremError."""

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
# Names / paths
# ---------------------------------------------------------------------------

def _validate_name(name: str) -> str:
    if not isinstance(name, str) or not _NAME_RE.match(name.strip()):
        raise SceneError(
            "INVALID_SCENE_NAME",
            "Scene names may only contain letters, digits, spaces, '_' and "
            "'-' (max 60 characters).",
            details={"name": name},
        )
    return name.strip()


def _path_for(name: str) -> str:
    return os.path.join(SCENES_DIR, name + ".json")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _is_finite_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def validate_scene(data: Any) -> Dict[str, Any]:
    """Return a normalised scene dict, or raise SceneError.

    Wrong-typed fields anywhere in the JSON (e.g. a list where an id is
    expected) surface as a clean INVALID_SCENE error, never a 500."""
    try:
        return _validate_scene(data)
    except (TypeError, ValueError, AttributeError, KeyError) as exc:
        raise SceneError("INVALID_SCENE", f"Malformed scene data: {exc}")


def _validate_scene(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict) or not isinstance(data.get("objects"), list):
        raise SceneError(
            "INVALID_SCENE", "Scene must be an object with an 'objects' list."
        )
    objects: List[Dict[str, Any]] = data["objects"]
    if len(objects) > MAX_OBJECTS:
        raise SceneError(
            "SCENE_TOO_LARGE",
            f"A scene may contain at most {MAX_OBJECTS} objects.",
            details={"count": len(objects)},
        )

    ids = set()
    point_ids = set()
    for i, obj in enumerate(objects):
        if not isinstance(obj, dict):
            raise SceneError("INVALID_OBJECT", f"Object #{i} is not an object.")
        oid = obj.get("id")
        otype = obj.get("type")
        if not isinstance(oid, int) or isinstance(oid, bool):
            raise SceneError("INVALID_OBJECT", f"Object #{i} has no integer 'id'.")
        if oid in ids:
            raise SceneError(
                "DUPLICATE_ID", f"Two objects share id {oid}.", details={"id": oid}
            )
        if otype not in _REF_FIELDS:
            raise SceneError(
                "UNKNOWN_OBJECT_TYPE",
                f"Object {oid} has unknown type {otype!r}.",
                details={"id": oid, "type": otype},
            )
        ids.add(oid)

        # Free-text fields: must be plain strings of sane length (the client
        # also renders them with textContent, this is defence in depth).
        for field, limit in ("label", MAX_LABEL_LEN), ("color", MAX_COLOR_LEN):
            val = obj.get(field)
            if val is not None and (not isinstance(val, str) or len(val) > limit):
                raise SceneError(
                    "INVALID_FIELD",
                    f"Object {oid}: '{field}' must be text of at most {limit} characters.",
                    details={"id": oid, "field": field},
                )

        if otype in _POINT_LIKE:
            point_ids.add(oid)
        if otype in ("point", "intersectionPoint"):
            for axis in ("x", "y"):
                if not _is_finite_number(obj.get(axis)):
                    raise SceneError(
                        "INVALID_COORDINATE",
                        f"Point {oid} needs a finite numeric '{axis}'.",
                        details={"id": oid, axis: obj.get(axis)},
                    )

    # Second pass: every reference must resolve to a Point.
    for obj in objects:
        oid, otype = obj["id"], obj["type"]
        for field in _REF_FIELDS[otype]:
            if obj.get(field) not in point_ids:
                raise SceneError(
                    "DANGLING_REFERENCE",
                    f"{otype} {oid}: '{field}' does not refer to an existing point.",
                    details={"id": oid, "field": field, "value": obj.get(field)},
                )
        if otype == "intersectionPoint":
            for field in ("o1", "o2"):
                if obj.get(field) not in ids or obj.get(field) == oid:
                    raise SceneError(
                        "DANGLING_REFERENCE",
                        f"intersectionPoint {oid}: '{field}' does not refer to an existing object.",
                        details={"id": oid, "field": field, "value": obj.get(field)},
                    )
        if otype == "glider":
            host = obj.get("host")
            if host not in ids or host == oid:
                raise SceneError(
                    "DANGLING_REFERENCE",
                    f"glider {oid}: 'host' does not refer to an existing object.",
                    details={"id": oid, "field": "host", "value": host},
                )
            if not _is_finite_number(obj.get("t")):
                raise SceneError(
                    "INVALID_FIELD",
                    f"glider {oid} needs a finite numeric 't'.",
                    details={"id": oid, "field": "t"},
                )
        if otype == "constructedPoint":
            refs = obj.get("refs")
            if obj.get("kind") not in _CONSTRUCTED_KINDS:
                raise SceneError(
                    "INVALID_FIELD",
                    f"constructedPoint {oid}: unknown kind {obj.get('kind')!r}.",
                    details={"id": oid, "field": "kind"},
                )
            if not isinstance(refs, list) or not 1 <= len(refs) <= 3:
                raise SceneError(
                    "INVALID_FIELD",
                    f"constructedPoint {oid} needs 1 to 3 'refs'.",
                    details={"id": oid, "field": "refs"},
                )
            for r in refs:
                if r not in ids or r == oid:
                    raise SceneError(
                        "DANGLING_REFERENCE",
                        f"constructedPoint {oid}: ref {r!r} does not refer to an existing object.",
                        details={"id": oid, "field": "refs", "value": r},
                    )
            if obj.get("k") is not None and not _is_finite_number(obj.get("k")):
                raise SceneError(
                    "INVALID_FIELD",
                    f"constructedPoint {oid}: 'k' must be a finite number.",
                    details={"id": oid, "field": "k"},
                )
        if otype == "polygon":
            verts = obj.get("vertices")
            if not isinstance(verts, list) or len(verts) < 3:
                raise SceneError(
                    "INVALID_POLYGON",
                    f"Polygon {oid} needs at least 3 vertices.",
                    details={"id": oid},
                )
            for v in verts:
                if v not in point_ids:
                    raise SceneError(
                        "DANGLING_REFERENCE",
                        f"Polygon {oid} references missing point {v}.",
                        details={"id": oid, "value": v},
                    )

    return {"version": int(data.get("version", 1)), "objects": objects}


# ---------------------------------------------------------------------------
# Store operations
# ---------------------------------------------------------------------------

def list_scenes() -> List[str]:
    if not os.path.isdir(SCENES_DIR):
        return []
    return sorted(
        f[:-5] for f in os.listdir(SCENES_DIR) if f.endswith(".json")
    )


def save_scene(name: str, data: Any) -> Dict[str, Any]:
    name = _validate_name(name)
    scene = validate_scene(data)

    # ensure_ascii=False keeps Greek labels (alpha, beta, ...) readable in the
    # saved file instead of turning them into \uXXXX escapes.
    payload = json.dumps(scene, indent=2, ensure_ascii=False)
    if len(payload.encode("utf-8")) > MAX_SCENE_BYTES:
        raise SceneError("SCENE_TOO_LARGE", "Scene exceeds the 2 MB size limit.")

    os.makedirs(SCENES_DIR, exist_ok=True)
    # Write to a temp file then replace, so a crash mid-write can never leave
    # a half-written (corrupt) scene behind.
    tmp = _path_for(name) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(payload)
    os.replace(tmp, _path_for(name))
    return {"status": "ok", "name": name, "object_count": len(scene["objects"])}


def load_scene(name: str) -> Dict[str, Any]:
    name = _validate_name(name)
    path = _path_for(name)
    if not os.path.exists(path):
        raise SceneError(
            "SCENE_NOT_FOUND", f"No saved scene named '{name}'.", details={"name": name}
        )
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise SceneError(
            "SCENE_UNREADABLE", f"Could not read scene '{name}': {exc}"
        )
    return {"status": "ok", "name": name, "scene": validate_scene(data)}


def delete_scene(name: str) -> Dict[str, Any]:
    name = _validate_name(name)
    path = _path_for(name)
    if not os.path.exists(path):
        raise SceneError(
            "SCENE_NOT_FOUND", f"No saved scene named '{name}'.", details={"name": name}
        )
    os.remove(path)
    return {"status": "ok", "name": name}
