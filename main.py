"""
main.py

CLI for the Triangle Centers engine.

Usage examples:
    python main.py --center 1 --triangle "(0,0),(4,0),(0,3)"
    python main.py --center 4 --triangle "(0,0),(6,0),(2,5)" --pretty
    python main.py --list
    python main.py --list --query centroid
    python main.py --info 1
    python main.py --list-shapes
    python main.py --shape circle --param radius=5 --pretty
    python main.py --shape triangle --param a=3 --param b=4 --param c=5
    python main.py --shape rectangle --param length=4 --param width=3
    python main.py --shape regular_polygon --param num_sides=6 --param side_length=2
    python main.py --shape polygon --param "points=(0,0),(4,0),(4,3),(0,3)"
    python main.py --shape ellipse --param semi_major=5 --param semi_minor=3
    python main.py --shape circle_sector --param radius=2 --param angle_degrees=90
    python main.py --shape circle_segment --param radius=2 --param angle_degrees=90
    python main.py --list-solids
    python main.py --solid sphere --param radius=3 --pretty
    python main.py --solid cuboid --param length=2 --param width=3 --param height=4
    python main.py --solid cone --param radius=3 --param height=4
    python main.py --list-theorems
    python main.py --theorem cosine_rule --param a=3 --param b=4 --param c=5

Run `python setup_db.py` once first to create/populate the database.

The shape / solid / theorem dispatch is shared with the Flask routes and lives
in dispatch.py; the center lookup (--info / --list) lives in center_info.py.
So the CLI and the web API can never drift apart.
"""

import argparse
import json
import sys

from center_info import list_verified_centers, lookup_info
from centers import Triangle, compute_center, TriangleCenterError
from dispatch import parse_triangle, run_shape, run_solid, run_theorem
from shapes import SUPPORTED_SHAPES
from solids import SUPPORTED_SOLIDS
from triangle_theorems import SUPPORTED_THEOREMS


def get_info(kimberling_id: int):
    """Name and full definition of any X(1)-X(84000). Shared with the
    /info/<id> Flask route (center_info.lookup_info)."""
    return lookup_info(kimberling_id)[0]


def list_centers(query: str = ""):
    """List locally verified centers, optionally filtered by name. Shared
    with the /centers Flask route (center_info.list_verified_centers)."""
    return list_verified_centers(query)[0]


def solve_shape(shape_type: str, params: dict):
    """Solve a 2D shape from CLI --param values (shared with /shape/<type>)."""
    return run_shape(shape_type, params)[0]


def solve_solid(solid_type: str, params: dict):
    """Solve a 3D solid from CLI --param values (shared with /solid/<type>)."""
    return run_solid(solid_type, params)[0]


def solve_theorem(theorem_type: str, params: dict):
    """Apply a triangle theorem to CLI --param values (shared with
    /theorem/<type>)."""
    return run_theorem(theorem_type, params)[0]


def parse_shape_params(pairs):
    """Turn ['radius=5', 'height=3'] into {'radius': '5', 'height': '3'}."""
    params = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise SystemExit(
                f"Invalid --param '{pair}': expected key=value, e.g. radius=5"
            )
        key, value = pair.split("=", 1)
        params[key.strip()] = value.strip()
    return params


def main():
    parser = argparse.ArgumentParser(
        description="Query Kimberling triangle centers (ETC-style) for a given triangle."
    )
    parser.add_argument(
        "--center", type=int, help="Kimberling center ID, e.g. 1 for the Incenter (X1)."
    )
    parser.add_argument(
        "--triangle",
        type=str,
        help='Triangle vertices as "(x1,y1),(x2,y2),(x3,y3)".',
    )
    parser.add_argument(
        "--list", action="store_true", help="List all available centers in the database."
    )
    parser.add_argument(
        "--query", type=str, metavar="TEXT",
        help="With --list, only show centers whose name contains TEXT "
             "(case-insensitive), e.g. --list --query centroid.",
    )
    parser.add_argument(
        "--info", type=int, metavar="ID",
        help="Look up any Kimberling center's name and full definition by "
             "number (1 to 84000) -- no triangle needed, e.g. --info 1",
    )
    parser.add_argument(
        "--shape", type=str, metavar="TYPE",
        help="Solve a general 2D shape: circle, ellipse, circle_sector, "
             "circle_segment, triangle, rectangle, square, parallelogram, "
             "rhombus, trapezoid, regular_polygon, or polygon. "
             "Use --list-shapes for every supported type. "
             "Combine with --param key=value (repeatable).",
    )
    parser.add_argument(
        "--param", action="append", metavar="KEY=VALUE",
        help="A parameter for --shape/--solid/--theorem, e.g. --param radius=5. "
             "Repeat for multiple parameters, e.g. --param length=4 --param width=3.",
    )
    parser.add_argument(
        "--list-shapes", action="store_true",
        help="List all supported general 2D shapes and their required parameters.",
    )
    parser.add_argument(
        "--solid", type=str, metavar="TYPE",
        help="Solve a 3D solid, e.g. sphere, cube, cone, torus, regular_prism, "
             "icosahedron. Use --list-solids for every supported type. "
             "Combine with --param key=value (repeatable).",
    )
    parser.add_argument(
        "--list-solids", action="store_true",
        help="List all supported 3D solids and their required parameters.",
    )
    parser.add_argument(
        "--theorem", type=str, metavar="TYPE",
        help="Apply a classic triangle theorem: sine_rule, cosine_rule, "
             "tangent_rule, ceva, or menelaus. Combine with --param key=value "
             "(repeatable).",
    )
    parser.add_argument(
        "--list-theorems", action="store_true",
        help="List all supported triangle theorems and their required parameters.",
    )
    parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    args = parser.parse_args()

    if args.list_shapes:
        result = {"status": "ok", "supported_shapes": SUPPORTED_SHAPES}
    elif args.list_solids:
        result = {"status": "ok", "supported_solids": SUPPORTED_SOLIDS}
    elif args.list_theorems:
        result = {"status": "ok", "supported_theorems": SUPPORTED_THEOREMS}
    elif args.solid is not None:
        params = parse_shape_params(args.param)
        result = solve_solid(args.solid, params)
    elif args.theorem is not None:
        params = parse_shape_params(args.param)
        result = solve_theorem(args.theorem, params)
    elif args.shape is not None:
        params = parse_shape_params(args.param)
        result = solve_shape(args.shape, params)
    elif args.info is not None:
        result = get_info(args.info)
    elif args.list:
        result = list_centers(args.query or "")
    elif args.center is not None and args.triangle:
        try:
            points = parse_triangle(args.triangle)
            triangle = Triangle(A=points[0], B=points[1], C=points[2])
            result = compute_center(args.center, triangle)
        except TriangleCenterError as exc:
            result = exc.to_payload()
    else:
        parser.print_help()
        sys.exit(1)

    indent = 2 if args.pretty else None
    print(json.dumps(result, indent=indent))

    # Concise human-readable summary alongside the JSON.
    if result.get("status") == "ok" and "cartesian_position" in result:
        pos = result["cartesian_position"]
        print(
            f"\nSummary: X({result['kimberling_id']}) '{result['name']}' "
            f"-> ({pos['x']:.6f}, {pos['y']:.6f})"
        )
    elif result.get("status") == "ok" and "kimberling_id" in result:
        print(f"\nSummary: X({result['kimberling_id']}) = {result.get('name')}")
    elif result.get("status") == "ok" and "solid" in result:
        print(f"\nSummary: {result['solid']} -> volume={result['volume']:.6f}, "
              f"surface_area={result['surface_area']:.6f}")
    elif result.get("status") == "ok" and "shape" in result:
        parts = [f"area={result['area']:.6f}"]
        if result.get("perimeter") is not None:
            parts.append(f"perimeter={result['perimeter']:.6f}")
        print(f"\nSummary: {result['shape']} -> {', '.join(parts)}")
    elif result.get("status") == "ok" and "theorem" in result:
        if result["theorem"] == "ceva":
            print(f"\nSummary: Ceva's theorem -> product={result['product']:.6f}, "
                  f"concurrent={result['concurrent']}")
        elif result["theorem"] == "menelaus":
            print(f"\nSummary: Menelaus' theorem -> product={result['product']:.6f}, "
                  f"collinear={result['collinear']}")
        elif result["theorem"] == "law_of_tangents":
            print(f"\nSummary: Law of Tangents -> identity_holds={result['identity_holds']}")
        elif "solutions" in result:
            for i, sol in enumerate(result["solutions"], 1):
                print(f"\nSolution {i}: a={sol['a']:.6f}, b={sol['b']:.6f}, c={sol['c']:.6f}, "
                      f"A={sol['angle_A_degrees']:.4f}\u00b0, B={sol['angle_B_degrees']:.4f}\u00b0, "
                      f"C={sol['angle_C_degrees']:.4f}\u00b0")
        else:
            print(f"\nSummary: {result['theorem']} -> a={result.get('a'):.6f}, "
                  f"b={result.get('b'):.6f}, c={result.get('c'):.6f}, "
                  f"A={result.get('angle_A_degrees'):.4f}\u00b0, "
                  f"B={result.get('angle_B_degrees'):.4f}\u00b0, "
                  f"C={result.get('angle_C_degrees'):.4f}\u00b0")
    elif result.get("status") == "ok":
        pass  # e.g. --list-shapes: JSON output above is already the full answer
    else:
        print(f"\nSummary: ERROR [{result.get('error_code')}] {result.get('message')}")


if __name__ == "__main__":
    main()
