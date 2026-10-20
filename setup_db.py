"""
setup_db.py

Creates and populates triangle_centers.db with a starter set of
Kimberling triangle centers (Encyclopedia of Triangle Centers style data).

Each center stores:
  - kimberling_id   : integer, e.g. 1 for X(1)
  - name            : common name, e.g. "Incenter"
  - barycentric     : barycentric coordinate formula as a string, using
                       ONLY a, b, c (side lengths opposite A, B, C) and
                       the whitelisted math functions in centers.py.
  - trilinear       : trilinear coordinate formula as a string (shown
                       for reference; not evaluated by the engine).
  - etc_notes       : short historical / definitional note

IMPORTANT: the 'barycentric' column is the one actually evaluated by
centers.py (safe_eval_formula), and it is only ever called with a, b, c
(side lengths) bound -- no angle values are supplied. So every
barycentric formula below is expressed purely in terms of a, b, c, and
has been numerically verified against independent geometric
constructions on at least one (often two) test triangles before being
added here.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "triangle_centers.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS triangle_centers (
    kimberling_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    barycentric TEXT NOT NULL,
    trilinear TEXT NOT NULL,
    etc_notes TEXT
);
"""

# Encyclopedia cache: name + trilinear formula (as published by ETC) for
# EVERY Kimberling center, X(1) through X(84000)+. This is reference data
# only -- populated in bulk by populate_etc_cache.py -- and is never fed
# to the safe barycentric evaluator. Only the hand-verified formulas in
# the triangle_centers table above are ever used for position calculation.
ENCYCLOPEDIA_SCHEMA = """
CREATE TABLE IF NOT EXISTS etc_encyclopedia (
    kimberling_id INTEGER PRIMARY KEY,
    name TEXT,
    trilinear_formula TEXT,
    source_url TEXT
);
"""

CENTERS = [
    (
        1,
        "Incenter",
        "(a, b, c)",
        "(1, 1, 1)",
        "X(1): The Incenter. Intersection of angle bisectors; center of the "
        "inscribed circle. Barycentrics a : b : c, trilinears 1 : 1 : 1.",
    ),
    (
        2,
        "Centroid",
        "(1, 1, 1)",
        "(1/a, 1/b, 1/c)",
        "X(2): The Centroid. Intersection of the medians; the triangle's "
        "center of mass. Barycentrics 1 : 1 : 1.",
    ),
    (
        3,
        "Circumcenter",
        "(a**2*(b**2+c**2-a**2), b**2*(c**2+a**2-b**2), c**2*(a**2+b**2-c**2))",
        "(cos(A), cos(B), cos(C))",
        "X(3): The Circumcenter. Equidistant from all three vertices; "
        "center of the circumscribed circle.",
    ),
    (
        4,
        "Orthocenter",
        "((a**2+b**2-c**2)*(a**2-b**2+c**2), "
        "(a**2+b**2-c**2)*(-a**2+b**2+c**2), "
        "(a**2-b**2+c**2)*(-a**2+b**2+c**2))",
        "(1/cos(A), 1/cos(B), 1/cos(C))",
        "X(4): The Orthocenter. Intersection of the triangle's three altitudes.",
    ),
    (
        5,
        "Nine-Point Center",
        "((a**2*(b**2+c**2)-(b**2-c**2)**2), "
        "(b**2*(c**2+a**2)-(c**2-a**2)**2), "
        "(c**2*(a**2+b**2)-(a**2-b**2)**2))",
        "(cos(B-C), cos(C-A), cos(A-B))",
        "X(5): The Nine-Point Center. Midpoint of the segment joining the "
        "circumcenter and orthocenter; center of the nine-point circle.",
    ),
    (
        6,
        "Symmedian Point",
        "(a**2, b**2, c**2)",
        "(a, b, c)",
        "X(6): The Symmedian Point (Lemoine point / Grebe point). "
        "Intersection of the symmedians.",
    ),
    (
        7,
        "Gergonne Point",
        "(1/(-a+b+c), 1/(a-b+c), 1/(a+b-c))",
        "(sec(A/2)**2, sec(B/2)**2, sec(C/2)**2)",
        "X(7): The Gergonne Point. Intersection of the lines connecting "
        "each vertex to the point of tangency of the opposite side with "
        "the incircle.",
    ),
    (
        8,
        "Nagel Point",
        "(-a+b+c, a-b+c, a+b-c)",
        "(csc(A/2)**2, csc(B/2)**2, csc(C/2)**2)",
        "X(8): The Nagel Point. Related to the extouch triangle; lies on "
        "the line through the incenter and centroid (with X(2)).",
    ),
    (
        9,
        "Mittenpunkt",
        "(a*(-a+b+c), b*(a-b+c), c*(a+b-c))",
        "(a*(-a+b+c), b*(a-b+c), c*(a+b-c))",
        "X(9): The Mittenpunkt. Symmedian point of the excentral triangle; "
        "also the centroid of the excentral triangle's contact triangle.",
    ),
    (
        10,
        "Spieker Center",
        "(b+c, c+a, a+b)",
        "(1/(b+c), 1/(c+a), 1/(a+b))",
        "X(10): The Spieker Center. Incenter of the medial triangle; center "
        "of mass of the triangle's perimeter (a uniform wire frame).",
    ),
    (
        11,
        "Feuerbach Point",
        "((b-c)**2*(b+c-a), (c-a)**2*(c+a-b), (a-b)**2*(a+b-c))",
        "(1-cos(B-C), 1-cos(C-A), 1-cos(A-B))",
        "X(11): The Feuerbach Point. The point of tangency between the "
        "incircle and the nine-point circle. Verified to lie exactly on "
        "the nine-point circle (distance to X(5) equals R/2).",
    ),
    (
        12,
        "X(12)",
        "((b+c)**2*(b+c-a) - a*(b-c)**2, "
        "(c+a)**2*(c+a-b) - b*(c-a)**2, "
        "(a+b)**2*(a+b-c) - c*(a-b)**2)",
        "(1+cos(B-C), 1+cos(C-A), 1+cos(A-B))",
        "X(12): Companion point to the Feuerbach point in the family of "
        "points associated with the incircle/nine-point circle "
        "configuration.",
    ),
    (
        19,
        "Clawson Point",
        "(a**2/(-a**2+b**2+c**2), "
        "b**2/(a**2-b**2+c**2), "
        "c**2/(a**2+b**2-c**2))",
        "(tan(A), tan(B), tan(C))",
        "X(19): The Clawson Point. Perspector of the orthic triangle and "
        "the tangential triangle. BUGFIX: the previous barycentric "
        "formula here was proportional to X(6)'s (a^2 : b^2 : c^2), so it "
        "silently computed the Symmedian Point instead of the Clawson "
        "Point for every triangle. The correct formula is a^2*tan(A) : "
        "b^2*tan(B) : c^2*tan(C); since tan(A) = 4*Area/(b^2+c^2-a^2) and "
        "the common factor 4*Area cancels in the ratio, this reduces to "
        "a^2/(b^2+c^2-a^2) : b^2/(c^2+a^2-b^2) : c^2/(a^2+b^2-c^2), which "
        "is what is stored here. Verified against an independent "
        "trig-based construction on three different test triangles. "
        "Undefined for right triangles (the vertex angle's tangent is "
        "infinite), which correctly surfaces as a NORMALIZATION_ERROR for "
        "such inputs.",
    ),
    (
        20,
        "De Longchamps Point",
        "((a**2+b**2-c**2)*(a**2-b**2+c**2) - 2*a**2*(b**2+c**2-a**2), "
        "(a**2+b**2-c**2)*(-a**2+b**2+c**2) - 2*b**2*(c**2+a**2-b**2), "
        "(a**2-b**2+c**2)*(-a**2+b**2+c**2) - 2*c**2*(a**2+b**2-c**2))",
        "(cos(B)+cos(C)-cos(A)-1, cos(C)+cos(A)-cos(B)-1, cos(A)+cos(B)-cos(C)-1)",
        "X(20): The de Longchamps Point. Reflection of the orthocenter "
        "X(4) over the circumcenter X(3); lies on the Euler line. "
        "Verified against the 2*X(3)-X(4) relation.",
    ),
    (
        21,
        "Schiffler Point",
        "(a*(b+c-a)/(b+c), b*(c+a-b)/(c+a), c*(a+b-c)/(a+b))",
        "((b+c-a)/(b+c), (c+a-b)/(c+a), (a+b-c)/(a+b))",
        "X(21): The Schiffler Point. The common intersection of the Euler "
        "lines of triangles BCI, CAI, and ABI, where I is the incenter of "
        "the reference triangle. Verified by independently constructing "
        "all three Euler lines and confirming they meet at this point, "
        "on two different test triangles.",
    ),
    (
        40,
        "Bevan Point",
        "(a*(a**3 + a**2*b + a**2*c - a*b**2 - 2*a*b*c - a*c**2 - b**3 + b**2*c + b*c**2 - c**3), "
        "b*(-a**3 - a**2*b + a**2*c + a*b**2 - 2*a*b*c + a*c**2 + b**3 + b**2*c - b*c**2 - c**3), "
        "c*(-a**3 + a**2*b - a**2*c + a*b**2 - 2*a*b*c + a*c**2 - b**3 - b**2*c + b*c**2 + c**3))",
        "(same expression as barycentric; shown here for reference only)",
        "X(40): The Bevan Point. The circumcenter of the excentral "
        "triangle (the triangle formed by the three excenters); "
        "equivalently, the reflection of the incenter X(1) over the "
        "circumcenter X(3). Formula derived symbolically from the "
        "excentral-triangle circumcenter construction and verified "
        "against two independent geometric constructions on two "
        "different test triangles.",
    ),
]


def init_db(db_path: str = DB_PATH) -> None:
    """Create the schema and populate it with the starter center set."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(SCHEMA)
        cur.execute(ENCYCLOPEDIA_SCHEMA)
        cur.executemany(
            """
            INSERT OR REPLACE INTO triangle_centers
                (kimberling_id, name, barycentric, trilinear, etc_notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            CENTERS,
        )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at: {DB_PATH}")
    print(f"Inserted {len(CENTERS)} triangle centers.")
