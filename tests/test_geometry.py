"""
test_geometry.py

Tests for the geometry engines that test_app.py / test_solver.py don't
cover directly: shapes.py (ellipse, sector, segment, polygons, ...),
solids.py, triangle_theorems.py, the CLI dispatch helpers in main.py, and
the matching Flask routes. Run from the project folder:

    pytest tests/test_geometry.py

Every expected number is a textbook value (3-4-5 triangle, r=2 quarter
circle, ...), so a failure means a real bug.
"""

import math
import unittest

import main as cli
from app import app
from shapes import (
    ShapeError,
    circle_from_radius,
    circle_from_diameter,
    circle_from_circumference,
    ellipse,
    circle_sector,
    circle_segment,
    triangle_from_sides,
    rectangle,
    square,
    parallelogram,
    rhombus_from_diagonals,
    trapezoid,
    regular_polygon,
    polygon_from_vertices,
    polygon_from_sides_and_angles,
    cyclic_polygon_from_sides,
)
from solids import (
    SolidError,
    sphere,
    cube,
    cuboid,
    cylinder,
    cone,
    square_pyramid,
    hemisphere,
    spherical_cap,
    ellipsoid,
    torus,
    truncated_cone,
    regular_pyramid,
    regular_prism,
    triangular_prism,
    tetrahedron,
    octahedron,
    dodecahedron,
    icosahedron,
)
from triangle_theorems import (
    TheoremError,
    solve_sine_rule,
    solve_cosine_rule,
    tangent_rule_check,
    ceva_check,
    menelaus_check,
)


# ---------------------------------------------------------------------------
# Shapes
# ---------------------------------------------------------------------------
class ShapeTests(unittest.TestCase):

    def test_circle_variants_agree(self):
        self.assertAlmostEqual(circle_from_radius(5)["area"], 25 * math.pi, places=6)
        self.assertAlmostEqual(circle_from_diameter(10)["area"], 25 * math.pi, places=6)
        self.assertAlmostEqual(
            circle_from_circumference(2 * math.pi)["area"], math.pi, places=6
        )

    def test_ellipse(self):
        r = ellipse(5, 3)
        self.assertAlmostEqual(r["area"], 15 * math.pi, places=6)
        self.assertAlmostEqual(r["eccentricity"], 0.8, places=6)
        self.assertAlmostEqual(r["perimeter"], 25.527, delta=0.01)

    def test_ellipse_with_equal_axes_is_a_circle(self):
        r = ellipse(4, 4)
        self.assertAlmostEqual(r["perimeter"], 8 * math.pi, places=6)
        self.assertAlmostEqual(r["eccentricity"], 0.0, places=9)

    def test_ellipse_minor_greater_than_major_rejected(self):
        with self.assertRaises(ShapeError) as cm:
            ellipse(3, 5)
        self.assertEqual(cm.exception.code, "INVALID_DIMENSION")

    def test_circle_sector_quarter(self):
        r = circle_sector(2, 90)
        self.assertAlmostEqual(r["area"], math.pi, places=6)
        self.assertAlmostEqual(r["arc_length"], math.pi, places=6)
        self.assertAlmostEqual(r["perimeter"], 4 + math.pi, places=6)

    def test_circle_sector_full_circle(self):
        self.assertAlmostEqual(circle_sector(1, 360)["area"], math.pi, places=6)

    def test_circle_sector_bad_angles(self):
        for bad in (0, -10, 361):
            with self.assertRaises(ShapeError) as cm:
                circle_sector(2, bad)
            self.assertEqual(cm.exception.code, "INVALID_DIMENSION")

    def test_circle_segment_quarter(self):
        r = circle_segment(2, 90)
        self.assertAlmostEqual(r["area"], math.pi - 2, places=6)
        self.assertAlmostEqual(r["chord_length"], 2 * math.sqrt(2), places=6)
        self.assertAlmostEqual(r["arc_length"], math.pi, places=6)

    def test_circle_segment_rejects_full_circle(self):
        with self.assertRaises(ShapeError):
            circle_segment(2, 360)

    def test_triangle_3_4_5(self):
        r = triangle_from_sides(3, 4, 5)
        self.assertAlmostEqual(r["area"], 6.0, places=6)
        self.assertAlmostEqual(r["perimeter"], 12.0, places=6)
        self.assertTrue(r["is_right_triangle"])

    def test_triangle_inequality_violation(self):
        with self.assertRaises(ShapeError) as cm:
            triangle_from_sides(1, 2, 10)
        self.assertEqual(cm.exception.code, "INVALID_TRIANGLE")

    def test_rectangle_and_square(self):
        r = rectangle(3, 4)
        self.assertAlmostEqual(r["area"], 12.0)
        self.assertAlmostEqual(r["diagonal"], 5.0)
        s = square(4)
        self.assertAlmostEqual(s["area"], 16.0)
        self.assertAlmostEqual(s["diagonal"], 4 * math.sqrt(2), places=6)

    def test_parallelogram(self):
        r = parallelogram(5, 4, 3)
        self.assertAlmostEqual(r["area"], 15.0)
        self.assertAlmostEqual(r["perimeter"], 18.0)

    def test_parallelogram_height_greater_than_side_rejected(self):
        with self.assertRaises(ShapeError):
            parallelogram(5, 3, 4)

    def test_rhombus(self):
        r = rhombus_from_diagonals(6, 8)
        self.assertAlmostEqual(r["area"], 24.0)
        self.assertAlmostEqual(r["side"], 5.0)
        self.assertAlmostEqual(r["perimeter"], 20.0)

    def test_trapezoid_with_and_without_legs(self):
        r = trapezoid(4, 6, 3)
        self.assertAlmostEqual(r["area"], 15.0)
        self.assertIsNone(r["perimeter"])
        r2 = trapezoid(4, 6, 3, 3, 3)
        self.assertAlmostEqual(r2["perimeter"], 16.0)

    def test_regular_hexagon(self):
        r = regular_polygon(6, 2)
        self.assertAlmostEqual(r["area"], 6 * math.sqrt(3), places=6)
        self.assertAlmostEqual(r["interior_angle_degrees"], 120.0)
        self.assertAlmostEqual(r["perimeter"], 12.0)

    def test_regular_polygon_too_few_sides(self):
        with self.assertRaises(ShapeError) as cm:
            regular_polygon(2, 3)
        self.assertEqual(cm.exception.code, "INVALID_POLYGON")

    def test_polygon_from_vertices(self):
        r = polygon_from_vertices([(0, 0), (4, 0), (4, 3), (0, 3)])
        self.assertAlmostEqual(r["area"], 12.0)
        self.assertAlmostEqual(r["perimeter"], 14.0)
        self.assertEqual(r["orientation"], "counter-clockwise")

    def test_polygon_collinear_points_rejected(self):
        with self.assertRaises(ShapeError) as cm:
            polygon_from_vertices([(0, 0), (1, 1), (2, 2)])
        self.assertEqual(cm.exception.code, "DEGENERATE_POLYGON")

    def test_polygon_from_sides_and_angles_regular_pentagon(self):
        r = polygon_from_sides_and_angles([5] * 5, [108] * 5)
        self.assertAlmostEqual(r["area"], regular_polygon(5, 5)["area"], places=6)

    def test_polygon_from_sides_and_angles_bad_sum(self):
        with self.assertRaises(ShapeError) as cm:
            polygon_from_sides_and_angles([3, 3, 3], [100, 100, 100])
        self.assertEqual(cm.exception.code, "INVALID_ANGLE_SUM")

    def test_polygon_from_sides_and_angles_mismatched_lengths(self):
        with self.assertRaises(ShapeError) as cm:
            polygon_from_sides_and_angles([3, 3, 3, 3], [90, 90, 90])
        self.assertEqual(cm.exception.code, "MISMATCHED_INPUT")

    def test_cyclic_polygon_triangle_matches_heron(self):
        r = cyclic_polygon_from_sides([3, 4, 5])
        self.assertAlmostEqual(r["area"], 6.0, places=6)
        self.assertAlmostEqual(r["circumradius"], 2.5, places=6)

    def test_cyclic_polygon_obtuse_triangle_matches_heron(self):
        # Obtuse triangle: the circumcentre lies OUTSIDE the polygon, which
        # needs the reflex-arc branch in cyclic_polygon_from_sides.
        a, b, c = 2.0, 2.0, 3.9
        s = (a + b + c) / 2
        heron = math.sqrt(s * (s - a) * (s - b) * (s - c))
        r = cyclic_polygon_from_sides([a, b, c])
        self.assertAlmostEqual(r["area"], heron, places=6)
        self.assertAlmostEqual(r["circumradius"], a * b * c / (4 * heron), places=6)
        self.assertEqual(r["circumcenter"], "outside")

    def test_cyclic_polygon_square(self):
        r = cyclic_polygon_from_sides([1, 1, 1, 1])
        self.assertAlmostEqual(r["area"], 1.0, places=6)

    def test_cyclic_polygon_brahmagupta_rectangle(self):
        # Sides 3,4,3,4 -> Brahmagupta: sqrt(4*3*4*3) = 12.
        r = cyclic_polygon_from_sides([3, 4, 3, 4])
        self.assertAlmostEqual(r["area"], 12.0, places=6)


# ---------------------------------------------------------------------------
# Solids
# ---------------------------------------------------------------------------
class SolidTests(unittest.TestCase):

    def test_sphere(self):
        r = sphere(3)
        self.assertAlmostEqual(r["volume"], 36 * math.pi, places=6)
        self.assertAlmostEqual(r["surface_area"], 36 * math.pi, places=6)

    def test_cube(self):
        r = cube(2)
        self.assertAlmostEqual(r["volume"], 8.0)
        self.assertAlmostEqual(r["surface_area"], 24.0)
        self.assertAlmostEqual(r["space_diagonal"], 2 * math.sqrt(3), places=6)

    def test_cuboid(self):
        r = cuboid(2, 3, 4)
        self.assertAlmostEqual(r["volume"], 24.0)
        self.assertAlmostEqual(r["surface_area"], 52.0)
        self.assertAlmostEqual(r["space_diagonal"], math.sqrt(29), places=6)

    def test_cylinder(self):
        r = cylinder(2, 5)
        self.assertAlmostEqual(r["volume"], 20 * math.pi, places=6)
        self.assertAlmostEqual(r["lateral_surface_area"], 20 * math.pi, places=6)
        self.assertAlmostEqual(r["surface_area"], 28 * math.pi, places=6)

    def test_cone_3_4_5(self):
        r = cone(3, 4)
        self.assertAlmostEqual(r["slant_height"], 5.0)
        self.assertAlmostEqual(r["volume"], 12 * math.pi, places=6)
        self.assertAlmostEqual(r["surface_area"], 24 * math.pi, places=6)

    def test_square_pyramid(self):
        r = square_pyramid(6, 4)
        self.assertAlmostEqual(r["slant_height"], 5.0)
        self.assertAlmostEqual(r["volume"], 48.0)
        self.assertAlmostEqual(r["surface_area"], 96.0)
        self.assertAlmostEqual(r["lateral_edge_length"], math.sqrt(34), places=6)

    def test_solid_validation(self):
        with self.assertRaises(SolidError) as cm:
            sphere(-1)
        self.assertEqual(cm.exception.code, "INVALID_DIMENSION")
        with self.assertRaises(SolidError) as cm:
            cube(None)
        self.assertEqual(cm.exception.code, "MISSING_VALUE")
        with self.assertRaises(SolidError) as cm:
            cube("abc")
        self.assertEqual(cm.exception.code, "INVALID_VALUE")


class MoreSolidTests(unittest.TestCase):
    """hemisphere, cap, ellipsoid, torus, frustum, prisms, pyramid, Platonic."""

    def test_hemisphere(self):
        r = hemisphere(3)
        self.assertAlmostEqual(r["volume"], 18 * math.pi, places=6)
        self.assertAlmostEqual(r["surface_area"], 27 * math.pi, places=6)
        self.assertAlmostEqual(r["curved_surface_area"], 18 * math.pi, places=6)

    def test_spherical_cap_special_cases(self):
        # Height = radius -> hemisphere; height = diameter -> whole sphere.
        self.assertAlmostEqual(spherical_cap(3, 3)["volume"], hemisphere(3)["volume"], places=6)
        self.assertAlmostEqual(spherical_cap(3, 3)["surface_area"], hemisphere(3)["surface_area"], places=6)
        self.assertAlmostEqual(spherical_cap(2, 4)["volume"], sphere(2)["volume"], places=6)
        self.assertAlmostEqual(spherical_cap(2, 4)["surface_area"], sphere(2)["surface_area"], places=6)

    def test_spherical_cap_value(self):
        r = spherical_cap(5, 2)
        self.assertAlmostEqual(r["volume"], 52 * math.pi / 3, places=6)
        self.assertAlmostEqual(r["base_radius"], 4.0, places=6)

    def test_spherical_cap_taller_than_sphere_rejected(self):
        with self.assertRaises(SolidError) as cm:
            spherical_cap(2, 4.5)
        self.assertEqual(cm.exception.code, "INVALID_DIMENSION")

    def test_ellipsoid_with_equal_axes_is_a_sphere(self):
        r = ellipsoid(2, 2, 2)
        self.assertAlmostEqual(r["volume"], sphere(2)["volume"], places=6)
        self.assertAlmostEqual(r["surface_area"], sphere(2)["surface_area"], places=6)
        self.assertTrue(r["surface_area_is_approximate"])

    def test_ellipsoid_surface_area_close_to_known_value(self):
        # Prolate spheroid a=b=1, c=2: exact area is about 21.4803.
        self.assertAlmostEqual(ellipsoid(1, 1, 2)["surface_area"], 21.48, delta=0.3)

    def test_torus(self):
        r = torus(3, 1)
        self.assertAlmostEqual(r["volume"], 6 * math.pi ** 2, places=6)
        self.assertAlmostEqual(r["surface_area"], 12 * math.pi ** 2, places=6)

    def test_torus_tube_larger_than_ring_rejected(self):
        with self.assertRaises(SolidError) as cm:
            torus(1, 2)
        self.assertEqual(cm.exception.code, "INVALID_DIMENSION")

    def test_truncated_cone(self):
        r = truncated_cone(2, 1, 3)
        # Full cone (r=2, h=6) minus the removed top cone (r=1, h=3).
        self.assertAlmostEqual(r["volume"], cone(2, 6)["volume"] - cone(1, 3)["volume"], places=6)
        self.assertAlmostEqual(r["volume"], 7 * math.pi, places=6)
        self.assertAlmostEqual(r["slant_height"], math.sqrt(10), places=6)
        self.assertAlmostEqual(r["lateral_surface_area"], 3 * math.pi * math.sqrt(10), places=6)

    def test_truncated_cone_with_equal_radii_is_a_cylinder(self):
        r = truncated_cone(3, 3, 5)
        c = cylinder(3, 5)
        self.assertAlmostEqual(r["volume"], c["volume"], places=6)
        self.assertAlmostEqual(r["surface_area"], c["surface_area"], places=6)

    def test_regular_prism_matches_cuboid_and_hexagon(self):
        sq = regular_prism(4, 2, 5)
        box = cuboid(2, 2, 5)
        self.assertAlmostEqual(sq["volume"], box["volume"], places=6)
        self.assertAlmostEqual(sq["surface_area"], box["surface_area"], places=6)
        hexa = regular_prism(6, 2, 3)
        self.assertAlmostEqual(hexa["volume"], 18 * math.sqrt(3), places=6)

    def test_regular_prism_accepts_string_side_count(self):
        self.assertAlmostEqual(regular_prism("4", "2", "5")["volume"], 20.0, places=6)
        self.assertAlmostEqual(regular_prism("4.0", 2, 5)["volume"], 20.0, places=6)

    def test_regular_prism_bad_side_count(self):
        for bad in (2, 3.5, 0, -4):
            with self.assertRaises(SolidError) as cm:
                regular_prism(bad, 2, 5)
            self.assertEqual(cm.exception.code, "INVALID_POLYGON")
        with self.assertRaises(SolidError) as cm:
            regular_prism(None, 2, 5)
        self.assertEqual(cm.exception.code, "MISSING_VALUE")

    def test_triangular_prism_3_4_5(self):
        r = triangular_prism(3, 4, 5, 10)
        self.assertAlmostEqual(r["base_area"], 6.0, places=6)
        self.assertAlmostEqual(r["volume"], 60.0, places=6)
        self.assertAlmostEqual(r["surface_area"], 132.0, places=6)

    def test_triangular_prism_invalid_triangle(self):
        with self.assertRaises(SolidError) as cm:
            triangular_prism(1, 2, 10, 1)
        self.assertEqual(cm.exception.code, "INVALID_TRIANGLE")

    def test_regular_pyramid_square_matches_square_pyramid(self):
        r = regular_pyramid(4, 6, 4)
        s = square_pyramid(6, 4)
        for key in ("volume", "surface_area", "slant_height", "lateral_edge_length"):
            self.assertAlmostEqual(r[key], s[key], places=6, msg=key)

    def test_regular_pyramid_triangular_base(self):
        # Regular tetrahedron with edge 1: base is an equilateral triangle and
        # the apex height is sqrt(2/3).
        r = regular_pyramid(3, 1, math.sqrt(2 / 3))
        t = tetrahedron(1)
        self.assertAlmostEqual(r["volume"], t["volume"], places=6)
        self.assertAlmostEqual(r["surface_area"], t["surface_area"], places=6)
        self.assertAlmostEqual(r["lateral_edge_length"], 1.0, places=6)

    def test_platonic_solids_known_values(self):
        s5 = math.sqrt(5)
        self.assertAlmostEqual(tetrahedron(1)["volume"], math.sqrt(2) / 12, places=6)
        self.assertAlmostEqual(tetrahedron(1)["surface_area"], math.sqrt(3), places=6)
        self.assertAlmostEqual(octahedron(1)["volume"], math.sqrt(2) / 3, places=6)
        self.assertAlmostEqual(octahedron(1)["surface_area"], 2 * math.sqrt(3), places=6)
        self.assertAlmostEqual(dodecahedron(1)["volume"], (15 + 7 * s5) / 4, places=6)
        self.assertAlmostEqual(icosahedron(1)["volume"], 5 * (3 + s5) / 12, places=6)
        self.assertAlmostEqual(icosahedron(1)["surface_area"], 5 * math.sqrt(3), places=6)

    def test_platonic_solids_volume_equals_area_times_inradius_over_three(self):
        # A convex polyhedron with an inscribed sphere has V = (1/3) * A * r.
        for solid in (tetrahedron, octahedron, dodecahedron, icosahedron):
            r = solid(2.5)
            self.assertAlmostEqual(
                r["volume"], r["surface_area"] * r["inradius"] / 3, places=6,
                msg=r["solid"],
            )

    def test_platonic_solids_scale_with_edge(self):
        # Volume scales with edge cubed, area with edge squared.
        for solid in (tetrahedron, octahedron, dodecahedron, icosahedron):
            one, two = solid(1), solid(2)
            self.assertAlmostEqual(two["volume"], 8 * one["volume"], places=6)
            self.assertAlmostEqual(two["surface_area"], 4 * one["surface_area"], places=6)

    def test_new_solids_reject_bad_input(self):
        for call in (
            lambda: hemisphere(-1),
            lambda: ellipsoid(1, 0, 2),
            lambda: tetrahedron(0),
            lambda: icosahedron(-3),
            lambda: truncated_cone(2, -1, 3),
        ):
            with self.assertRaises(SolidError) as cm:
                call()
            self.assertEqual(cm.exception.code, "INVALID_DIMENSION")
        with self.assertRaises(SolidError) as cm:
            torus("abc", 1)
        self.assertEqual(cm.exception.code, "INVALID_VALUE")

    def test_every_listed_solid_has_a_handler_and_vice_versa(self):
        from dispatch import SOLID_HANDLERS
        from solids import SUPPORTED_SOLIDS
        self.assertEqual(set(SOLID_HANDLERS), set(SUPPORTED_SOLIDS))


# ---------------------------------------------------------------------------
# Theorems
# ---------------------------------------------------------------------------
class TheoremTests(unittest.TestCase):

    def test_sine_rule_aas(self):
        r = solve_sine_rule(a=10, angle_A_degrees=40, angle_B_degrees=65)
        sol = r["solutions"][0]
        self.assertAlmostEqual(sol["angle_C_degrees"], 75.0, places=6)
        self.assertAlmostEqual(
            sol["b"], 10 * math.sin(math.radians(65)) / math.sin(math.radians(40)),
            places=6,
        )

    def test_sine_rule_ssa_two_solutions(self):
        r = solve_sine_rule(a=6, b=8, angle_A_degrees=30)
        self.assertTrue(r["ambiguous"])
        self.assertEqual(r["num_solutions"], 2)

    def test_sine_rule_ssa_one_solution(self):
        r = solve_sine_rule(a=8, b=6, angle_A_degrees=30)
        self.assertFalse(r["ambiguous"])
        self.assertEqual(r["num_solutions"], 1)

    def test_sine_rule_ssa_right_angle_is_single_solution(self):
        # sin(B) = 1 exactly -> B = 90 degrees, one triangle (not two).
        r = solve_sine_rule(a=4, b=8, angle_A_degrees=30)
        self.assertEqual(r["num_solutions"], 1)
        self.assertAlmostEqual(r["solutions"][0]["angle_B_degrees"], 90.0, places=4)

    def test_sine_rule_ssa_no_triangle(self):
        with self.assertRaises(TheoremError) as cm:
            solve_sine_rule(a=2, b=8, angle_A_degrees=30)
        self.assertEqual(cm.exception.code, "NO_TRIANGLE")

    def test_sine_rule_missing_input(self):
        with self.assertRaises(TheoremError) as cm:
            solve_sine_rule(a=5)
        self.assertEqual(cm.exception.code, "MISSING_VALUE")

    def test_cosine_rule_sss(self):
        r = solve_cosine_rule(a=3, b=4, c=5)
        self.assertAlmostEqual(r["angle_C_degrees"], 90.0, places=6)

    def test_cosine_rule_sas(self):
        r = solve_cosine_rule(a=3, b=4, angle_C_degrees=90)
        self.assertAlmostEqual(r["c"], 5.0, places=6)

    def test_cosine_rule_missing_input(self):
        with self.assertRaises(TheoremError) as cm:
            solve_cosine_rule(a=3, b=4)
        self.assertEqual(cm.exception.code, "MISSING_VALUE")

    def test_tangent_rule_holds_for_real_triangle(self):
        A = math.degrees(math.atan2(3, 4))
        B = math.degrees(math.atan2(4, 3))
        r = tangent_rule_check(3, 4, A, B)
        self.assertTrue(r["identity_holds"])

    def test_tangent_rule_detects_inconsistent_triangle(self):
        r = tangent_rule_check(3, 4, 50, 50)
        self.assertFalse(r["identity_holds"])

    def test_ceva(self):
        self.assertTrue(ceva_check(1, 1, 1)["concurrent"])       # medians
        self.assertFalse(ceva_check(2, 1, 1)["concurrent"])
        self.assertTrue(ceva_check("1", "1", "1")["concurrent"])  # strings OK

    def test_ceva_zero_ratio_rejected(self):
        for zero in (0, "0"):
            with self.assertRaises(TheoremError) as cm:
                ceva_check(zero, 1, 1)
            self.assertEqual(cm.exception.code, "INVALID_VALUE")

    def test_menelaus(self):
        self.assertTrue(menelaus_check(-1, -1, -1)["collinear"])
        self.assertFalse(menelaus_check(1, 1, 1)["collinear"])


# ---------------------------------------------------------------------------
# CLI dispatch helpers (main.py)
# ---------------------------------------------------------------------------
class CliTests(unittest.TestCase):

    def test_parse_shape_params(self):
        self.assertEqual(
            cli.parse_shape_params(["radius=5", "height = 3"]),
            {"radius": "5", "height": "3"},
        )

    def test_parse_shape_params_rejects_missing_equals(self):
        with self.assertRaises(SystemExit):
            cli.parse_shape_params(["radius5"])

    def test_solve_shape_new_types(self):
        r = cli.solve_shape("ellipse", {"semi_major": "5", "semi_minor": "3"})
        self.assertEqual(r["status"], "ok")
        r = cli.solve_shape("circle_sector", {"radius": "2", "angle_degrees": "90"})
        self.assertAlmostEqual(r["area"], math.pi, places=6)
        r = cli.solve_shape("circle_segment", {"radius": "2", "angle_degrees": "90"})
        self.assertAlmostEqual(r["area"], math.pi - 2, places=6)

    def test_solve_shape_unknown(self):
        self.assertEqual(cli.solve_shape("blob", {})["error_code"], "UNKNOWN_SHAPE")

    def test_solve_shape_bad_points_is_clean_error(self):
        r = cli.solve_shape("polygon", {"points": "(1),(2),(3)"})
        self.assertEqual(r["status"], "error")

    def test_solve_solid(self):
        r = cli.solve_solid("cone", {"radius": "3", "height": "4"})
        self.assertAlmostEqual(r["volume"], 12 * math.pi, places=6)
        self.assertEqual(cli.solve_solid("blob", {})["error_code"], "UNKNOWN_SOLID")

    def test_solve_new_solids_through_the_cli(self):
        r = cli.solve_solid("torus", {"major_radius": "3", "minor_radius": "1"})
        self.assertAlmostEqual(r["volume"], 6 * math.pi ** 2, places=6)
        r = cli.solve_solid("regular_prism", {"num_sides": "6", "base_side": "2", "height": "3"})
        self.assertAlmostEqual(r["volume"], 18 * math.sqrt(3), places=6)
        r = cli.solve_solid("icosahedron", {"edge": "1"})
        self.assertEqual(r["status"], "ok")

    def test_solve_theorem(self):
        r = cli.solve_theorem("cosine_rule", {"a": "3", "b": "4", "c": "5"})
        self.assertEqual(r["status"], "ok")
        self.assertEqual(
            cli.solve_theorem("blob", {})["error_code"], "UNKNOWN_THEOREM"
        )

    def test_solve_theorem_non_numeric_is_clean_error(self):
        r = cli.solve_theorem("sine_rule", {"a": "abc", "angle_A_degrees": "40"})
        self.assertEqual(r["status"], "error")
        self.assertEqual(r["error_code"], "INVALID_VALUE")


# ---------------------------------------------------------------------------
# Flask routes not covered in test_app.py
# ---------------------------------------------------------------------------
class ApiRouteTests(unittest.TestCase):

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def get_json(self, path):
        resp = self.client.get(path)
        return resp, resp.get_json()

    def test_shapes_and_solids_and_theorems_lists(self):
        for path, key in (("/shapes", "supported_shapes"),
                          ("/solids", "supported_solids"),
                          ("/theorems", "supported_theorems")):
            resp, data = self.get_json(path)
            self.assertEqual(resp.status_code, 200)
            self.assertIn(key, data)

    def test_shape_ellipse(self):
        resp, data = self.get_json("/shape/ellipse?semi_major=5&semi_minor=3")
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(data["area"], 15 * math.pi, places=6)

    def test_shape_ellipse_invalid_axes(self):
        resp, data = self.get_json("/shape/ellipse?semi_major=3&semi_minor=5")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data["error_code"], "INVALID_DIMENSION")

    def test_shape_circle_sector_and_segment(self):
        resp, data = self.get_json("/shape/circle_sector?radius=2&angle_degrees=90")
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(data["area"], math.pi, places=6)
        resp, data = self.get_json("/shape/circle_segment?radius=2&angle_degrees=90")
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(data["area"], math.pi - 2, places=6)

    def test_shape_cyclic_polygon(self):
        resp, data = self.get_json("/shape/cyclic_polygon?sides=3,4,3,4")
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(data["area"], 12.0, places=6)

    def test_all_solids(self):
        cases = {
            "/solid/cube?side=2": 8.0,
            "/solid/cuboid?length=2&width=3&height=4": 24.0,
            "/solid/cylinder?radius=2&height=5": 20 * math.pi,
            "/solid/cone?radius=3&height=4": 12 * math.pi,
            "/solid/square_pyramid?base_side=6&height=4": 48.0,
        }
        for path, volume in cases.items():
            resp, data = self.get_json(path)
            self.assertEqual(resp.status_code, 200, path)
            self.assertAlmostEqual(data["volume"], volume, places=6, msg=path)

    def test_solid_unknown_and_invalid(self):
        resp, data = self.get_json("/solid/blob")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data["error_code"], "UNKNOWN_SOLID")
        resp, data = self.get_json("/solid/sphere?radius=-2")
        self.assertEqual(resp.status_code, 400)

    def test_new_solid_routes(self):
        cases = {
            "/solid/hemisphere?radius=3": 18 * math.pi,
            "/solid/spherical_cap?radius=5&height=2": 52 * math.pi / 3,
            "/solid/ellipsoid?a=2&b=2&c=2": (4 / 3) * math.pi * 8,
            "/solid/torus?major_radius=3&minor_radius=1": 6 * math.pi ** 2,
            "/solid/truncated_cone?bottom_radius=2&top_radius=1&height=3": 7 * math.pi,
            "/solid/regular_pyramid?num_sides=4&base_side=6&height=4": 48.0,
            "/solid/regular_prism?num_sides=4&base_side=2&height=5": 20.0,
            "/solid/triangular_prism?a=3&b=4&c=5&height=10": 60.0,
            "/solid/tetrahedron?edge=1": math.sqrt(2) / 12,
            "/solid/octahedron?edge=1": math.sqrt(2) / 3,
            "/solid/dodecahedron?edge=1": (15 + 7 * math.sqrt(5)) / 4,
            "/solid/icosahedron?edge=1": 5 * (3 + math.sqrt(5)) / 12,
        }
        for path, volume in cases.items():
            resp, data = self.get_json(path)
            self.assertEqual(resp.status_code, 200, path)
            self.assertAlmostEqual(data["volume"], volume, places=6, msg=path)

    def test_new_solid_routes_reject_bad_input(self):
        for path, code in (
            ("/solid/torus?major_radius=1&minor_radius=2", "INVALID_DIMENSION"),
            ("/solid/regular_prism?num_sides=2&base_side=1&height=1", "INVALID_POLYGON"),
            ("/solid/regular_prism?base_side=1&height=1", "MISSING_VALUE"),
            ("/solid/triangular_prism?a=1&b=2&c=10&height=1", "INVALID_TRIANGLE"),
            ("/solid/spherical_cap?radius=1&height=3", "INVALID_DIMENSION"),
        ):
            resp, data = self.get_json(path)
            self.assertEqual(resp.status_code, 400, path)
            self.assertEqual(data["error_code"], code, path)

    def test_theorem_ceva_and_menelaus(self):
        resp, data = self.get_json("/theorem/ceva?bd_dc=1&ce_ea=1&af_fb=1")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(data["concurrent"])
        resp, data = self.get_json("/theorem/menelaus?bd_dc=-1&ce_ea=-1&af_fb=-1")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(data["collinear"])

    def test_theorem_unknown(self):
        resp, data = self.get_json("/theorem/blob")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data["error_code"], "UNKNOWN_THEOREM")

