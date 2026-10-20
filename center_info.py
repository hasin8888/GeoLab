"""
center_info.py

The "look up a Kimberling center by number" logic, shared by the Flask routes
(routes/centers_api.py) and the command line (main.py), so the two can never
give different answers for the same center. Like dispatch.py, every function
returns (payload, http_status); the CLI just ignores the status.

Lookup order for /info/<id> and `main.py --info`:
  1. Local VERIFIED database (triangle_centers table) -- fastest, and the only
     source that also supports position calculation.
  2. Local ENCYCLOPEDIA cache (etc_encyclopedia table, filled in bulk by
     populate_etc_cache.py) -- also instant; reference/display only.
  3. Live ETC fetch -- last resort, for a center in neither local table.
"""

import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, Optional, Tuple

import centers
from centers import TriangleCenterError, fetch_center
from etc_lookup import EtcLookupError, fetch_center_info

Result = Tuple[Dict[str, Any], int]


@contextmanager
def get_db():
    """Open the SQLite database (rows behave like dicts) and always close it."""
    conn = sqlite3.connect(centers.DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def list_verified_centers(query: str = "") -> Result:
    """List locally verified centers. A non-empty `query` keeps only centers
    whose name contains it (case-insensitive)."""
    if not os.path.exists(centers.DB_PATH):
        return {
            "status": "error",
            "error_code": "DATABASE_NOT_FOUND",
            "message": f"Database not found at '{centers.DB_PATH}'. Run setup_db.py first.",
        }, 500

    query = (query or "").strip()
    with get_db() as conn:
        cur = conn.cursor()
        if query:
            cur.execute(
                "SELECT kimberling_id, name FROM triangle_centers "
                "WHERE name LIKE ? ORDER BY kimberling_id",
                (f"%{query}%",),
            )
        else:
            cur.execute("SELECT kimberling_id, name FROM triangle_centers ORDER BY kimberling_id")
        rows = [dict(r) for r in cur.fetchall()]
    return {"status": "ok", "query": query or None, "count": len(rows), "centers": rows}, 200


def fetch_local_encyclopedia_entry(kimberling_id: int) -> Optional[Dict[str, Any]]:
    """Name + trilinear formula from the bulk-populated etc_encyclopedia table
    (see populate_etc_cache.py). None if the table doesn't exist yet (script
    never run) or the id isn't cached."""
    if not os.path.exists(centers.DB_PATH):
        return None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT kimberling_id, name, trilinear_formula, source_url "
                "FROM etc_encyclopedia WHERE kimberling_id = ?",
                (kimberling_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    except sqlite3.OperationalError:
        return None


def lookup_info(kimberling_id: int) -> Result:
    """Name and full definition of any center X(1)..X(84000); no triangle
    needed and no (x, y) position is computed."""
    local_record = None
    try:
        local_record = fetch_center(kimberling_id)
    except TriangleCenterError:
        pass  # not in the verified DB -- other sources may still know it

    if local_record is not None:
        return {
            "status": "ok",
            "kimberling_id": kimberling_id,
            "name": local_record["name"],
            "trilinear_formula": local_record["trilinear"],
            "barycentric_formula": local_record["barycentric"],
            "description": local_record["etc_notes"],
            "supports_calculation": True,
            "sources": {
                "local_verified_database": True,
                "local_encyclopedia_cache": False,
                "live_etc_fetch": False,
            },
        }, 200

    cached = fetch_local_encyclopedia_entry(kimberling_id)
    if cached is not None:
        return {
            "status": "ok",
            "kimberling_id": kimberling_id,
            "name": cached["name"],
            "trilinear_formula": cached["trilinear_formula"],
            "barycentric_formula": None,
            "description": None,
            "supports_calculation": False,
            "sources": {
                "local_verified_database": False,
                "local_encyclopedia_cache": True,
                "live_etc_fetch": False,
            },
            "etc_source_url": cached["source_url"],
        }, 200

    try:
        etc_result = fetch_center_info(kimberling_id)
    except EtcLookupError as exc:
        payload = exc.to_payload()
        status = 404 if payload.get("error_code") in (
            "CENTER_NOT_FOUND_ON_PAGE", "ID_OUT_OF_RANGE") else 502
        return payload, status

    payload = {
        "status": "ok",
        "kimberling_id": kimberling_id,
        "name": etc_result.get("name"),
        "trilinear_formula": etc_result.get("trilinear_formula"),
        "barycentric_formula": None,  # only ever from the local, vetted DB
        "description": None,
        "supports_calculation": False,
        "sources": {
            "local_verified_database": False,
            "local_encyclopedia_cache": False,
            "live_etc_fetch": True,
        },
        "etc_source_url": etc_result.get("source_url"),
        "etc_raw_text": etc_result.get("raw_etc_text"),
    }
    if etc_result.get("note"):
        payload["etc_note"] = etc_result["note"]
    return payload, 200
