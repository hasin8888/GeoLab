"""
routes/scenes_api.py

Save / load / delete geometry-workspace scenes.
"""

import os

from flask import Blueprint, jsonify, request
from flask_login import current_user

from scene_store import (
    SceneError,
    list_scenes,
    save_scene,
    load_scene,
    delete_scene,
)

bp = Blueprint("scenes", __name__)


@bp.before_request
def _protect_scene_changes():
    """On a public site set GEOLAB_PROTECT_SCENES=1: then only logged-in users
    can save or delete scenes (anyone can still list and load them). Left
    unset (the default) nothing changes, so local use and the tests behave
    exactly as before."""
    if (os.environ.get("GEOLAB_PROTECT_SCENES") == "1"
            and request.method in ("PUT", "DELETE")
            and not current_user.is_authenticated):
        return jsonify({
            "status": "error",
            "error_code": "LOGIN_REQUIRED",
            "message": "Please log in to save or delete scenes.",
        }), 401


@bp.route("/api/scenes", methods=["GET"])
def api_list_scenes():
    return jsonify({"status": "ok", "scenes": list_scenes()})


@bp.route("/api/scenes/<name>", methods=["GET"])
def api_load_scene(name):
    try:
        return jsonify(load_scene(name)), 200
    except SceneError as exc:
        code = 404 if exc.code == "SCENE_NOT_FOUND" else 400
        return jsonify(exc.to_payload()), code


@bp.route("/api/scenes/<name>", methods=["PUT"])
def api_save_scene(name):
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({
            "status": "error",
            "error_code": "INVALID_JSON",
            "message": "Request body must be valid JSON.",
        }), 400
    try:
        return jsonify(save_scene(name, data)), 200
    except SceneError as exc:
        return jsonify(exc.to_payload()), 400


@bp.route("/api/scenes/<name>", methods=["DELETE"])
def api_delete_scene(name):
    try:
        return jsonify(delete_scene(name)), 200
    except SceneError as exc:
        code = 404 if exc.code == "SCENE_NOT_FOUND" else 400
        return jsonify(exc.to_payload()), code
