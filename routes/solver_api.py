"""
routes/solver_api.py

Coordinate-free triangle problem solver endpoints.
"""

from flask import Blueprint, jsonify, request

from solver import SolverError, SUPPORTED_QUANTITIES, solve as solve_problem

bp = Blueprint("solver", __name__)


@bp.route("/api/solve", methods=["POST"])
def api_solve():
    """
    Body: {"given": {"a": 5, "b": 7, "gamma": 60, ...}, "want": ["R", "r"]}
    Angles are in degrees. No coordinates are accepted or used.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({
            "status": "error",
            "error_code": "INVALID_JSON",
            "message": "Request body must be a JSON object.",
        }), 400
    try:
        return jsonify(solve_problem(data.get("given"), data.get("want"))), 200
    except SolverError as exc:
        return jsonify(exc.to_payload()), 400


@bp.route("/api/solver/quantities")
def api_solver_quantities():
    return jsonify({"status": "ok", "quantities": SUPPORTED_QUANTITIES})
