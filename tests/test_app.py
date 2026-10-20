"""
test_app.py

Basic smoke/regression tests for app.py's Flask routes, using Flask's own
test client (no server needs to be running). Run from the project folder:

    pytest tests/test_app.py

triangle_centers.db is created automatically by tests/conftest.py if missing.
"""

import json
import math
import unittest

from app import app


class AppTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def get_json(self, path):
        resp = self.client.get(path)
        return resp, resp.get_json()

    # ---------------------------------------------------------------- pages
    def test_home_page_loads(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)

    def test_api_index(self):
        resp, data = self.get_json("/api")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["status"], "ok")

    def test_solver_page_loads(self):
        resp = self.client.get("/solver")
        self.assertEqual(resp.status_code, 200)

    def test_geometry_page_loads(self):
        resp = self.client.get("/geometry")
        self.assertEqual(resp.status_code, 200)

    def test_app_page_loads(self):
        resp = self.client.get("/app")
        self.assertEqual(resp.status_code, 200)

    # -------------------------------------------------------------- centers
    def test_list_centers(self):
        resp, data = self.get_json("/centers")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["status"], "ok")
        self.assertIsInstance(data["centers"], list)

    def test_list_centers_query_filters_by_name(self):
        resp, data = self.get_json("/centers?q=centroid")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["status"], "ok")
        self.assertGreater(len(data["centers"]), 0)
        self.assertTrue(
            all("centroid" in c["name"].lower() for c in data["centers"])
        )

    def test_list_centers_query_no_match_returns_empty_list(self):
        resp, data = self.get_json("/centers?q=zzz_no_such_center_zzz")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["centers"], [])

    def test_get_center_valid_triangle(self):
        resp, data = self.get_json("/center/1?triangle=(0,0),(4,0),(0,3)")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["status"], "ok")
        self.assertIn("cartesian_position", data)

    def test_get_center_degenerate_triangle(self):
        resp, data = self.get_json("/center/1?triangle=(0,0),(1,0),(2,0)")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data["status"], "error")

    def test_get_center_malformed_triangle_returns_400_not_500(self):
        # This is the bug class _float_or_none/parse_triangle guard against:
        # bad input should be a clean 400, never an unhandled 500.
        resp, data = self.get_json("/center/1?triangle=not,a,triangle")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data["error_code"], "INVALID_TRIANGLE_INPUT")

    def test_get_center_missing_triangle_param(self):
        resp, data = self.get_json("/center/1")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data["error_code"], "MISSING_TRIANGLE")

    # ----------------------------------------------------------------- info
    def test_info_local_db(self):
        resp, data = self.get_json("/info/1")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(data["sources"]["local_verified_database"])

    # --------------------------------------------------------------- shapes
    def test_shape_circle(self):
        resp, data = self.get_json("/shape/circle?radius=4")
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(data["area"], 3.14159265 * 16, places=3)

    def test_shape_isosceles_triangle(self):
        resp, data = self.get_json("/shape/isosceles_triangle?leg=5&base=6")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["status"], "ok")
        self.assertAlmostEqual(data["area"], 12.0, places=3)
        self.assertAlmostEqual(data["apex_angle_degrees"] + 2 * data["base_angle_degrees"], 180.0, places=3)
        self.assertIn("vertices", data)

    def test_shape_isosceles_triangle_invalid(self):
        # legs too short to span the base.
        resp, data = self.get_json("/shape/isosceles_triangle?leg=2&base=10")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data["error_code"], "INVALID_TRIANGLE")

    def test_shape_equilateral_triangle(self):
        resp, data = self.get_json("/shape/equilateral_triangle?side=4")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["status"], "ok")
        self.assertAlmostEqual(data["perimeter"], 12.0, places=6)
        for ang in data["angles_degrees"].values():
            self.assertAlmostEqual(ang, 60.0, places=6)
        self.assertIn("vertices", data)

    def test_shape_missing_value(self):
        resp, data = self.get_json("/shape/circle")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data["error_code"], "MISSING_VALUE")

    def test_shape_bad_value_returns_400_not_500(self):
        resp, data = self.get_json("/shape/circle?radius=abc")
        self.assertEqual(resp.status_code, 400)

    def test_shape_polygon_malformed_points_returns_400_not_500(self):
        # Regression test for the IndexError gap in _parse_points.
        resp, data = self.get_json("/shape/polygon?points=(1),(2),(3)")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data["error_code"], "INVALID_VALUE")

    def test_shape_unknown_type(self):
        resp, data = self.get_json("/shape/not_a_shape")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data["error_code"], "UNKNOWN_SHAPE")

    # --------------------------------------------------------------- solids
    def test_solid_sphere(self):
        resp, data = self.get_json("/solid/sphere?radius=3")
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(data["volume"], (4 / 3) * 3.14159265 * 27, places=2)

    # ------------------------------------------------------------- theorems
    def test_theorem_cosine_rule_sss(self):
        resp, data = self.get_json("/theorem/cosine_rule?a=3&b=4&c=5")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["status"], "ok")

    def test_theorem_bad_value_returns_400_not_500(self):
        # Regression test for the unguarded float(val) crash in _float_or_none.
        resp, data = self.get_json("/theorem/sine_rule?a=abc&angle_A_degrees=40")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data["error_code"], "INVALID_VALUE")

    # -------------------------------------------------------------- solver
    def test_api_solve_sss(self):
        resp = self.client.post(
            "/api/solve",
            data=json.dumps({"given": {"a": 13, "b": 14, "c": 15}}),
            content_type="application/json",
        )
        data = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(data["conclusion"]["known"]["Delta"], 84, places=2)

    def test_api_solve_invalid_json(self):
        resp = self.client.post("/api/solve", data="not json", content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_api_solve_bad_triangle(self):
        resp = self.client.post(
            "/api/solve",
            data=json.dumps({"given": {"a": 1, "b": 2, "c": 10}}),
            content_type="application/json",
        )
        data = resp.get_json()
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data["error_code"], "INVALID_TRIANGLE")

    # -------------------------------------------------------------- scenes
    def test_scene_save_load_delete_roundtrip(self):
        name = "test_roundtrip_scene"
        scene_data = {"objects": []}

        put_resp = self.client.put(
            f"/api/scenes/{name}",
            data=json.dumps(scene_data),
            content_type="application/json",
        )
        self.assertEqual(put_resp.status_code, 200)

        get_resp, get_data = self.get_json(f"/api/scenes/{name}")
        self.assertEqual(get_resp.status_code, 200)

        del_resp = self.client.delete(f"/api/scenes/{name}")
        self.assertEqual(del_resp.status_code, 200)

        get_resp2, get_data2 = self.get_json(f"/api/scenes/{name}")
        self.assertEqual(get_resp2.status_code, 404)

    def test_scenes_list(self):
        resp, data = self.get_json("/api/scenes")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["status"], "ok")
        self.assertIsInstance(data["scenes"], list)

    def test_scene_load_missing_returns_404(self):
        resp, data = self.get_json("/api/scenes/no_such_scene_zzz")
        self.assertEqual(resp.status_code, 404)

    def test_scene_save_invalid_json_returns_400(self):
        resp = self.client.put(
            "/api/scenes/test_bad_json_scene",
            data="not json",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_solver_quantities(self):
        resp, data = self.get_json("/api/solver/quantities")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["status"], "ok")

    # ------------------------------------------------- listing endpoints
    def test_list_shapes_solids_theorems(self):
        for path, key in (("/shapes", "supported_shapes"),
                          ("/solids", "supported_solids"),
                          ("/theorems", "supported_theorems")):
            resp, data = self.get_json(path)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(data["status"], "ok")
            self.assertTrue(data[key])

    # ------------------------------------------- more 2D shapes
    def test_shape_ellipse(self):
        resp, data = self.get_json("/shape/ellipse?semi_major=5&semi_minor=3")
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(data["area"], 15 * math.pi, places=6)
        self.assertAlmostEqual(data["eccentricity"], 0.8, places=6)
        # Ramanujan's approximation for a=5, b=3 is about 25.527.
        self.assertAlmostEqual(data["perimeter"], 25.527, places=2)

    def test_shape_ellipse_minor_greater_than_major_returns_400(self):
        resp, data = self.get_json("/shape/ellipse?semi_major=3&semi_minor=5")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data["error_code"], "INVALID_DIMENSION")

    def test_shape_circle_sector(self):
        resp, data = self.get_json("/shape/circle_sector?radius=6&angle_degrees=90")
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(data["area"], 9 * math.pi, places=6)
        self.assertAlmostEqual(data["arc_length"], 3 * math.pi, places=6)
        self.assertAlmostEqual(data["perimeter"], 12 + 3 * math.pi, places=6)

    def test_shape_circle_sector_bad_angle_returns_400(self):
        for angle in ("0", "361", "-10"):
            resp, data = self.get_json(
                f"/shape/circle_sector?radius=6&angle_degrees={angle}")
            self.assertEqual(resp.status_code, 400)
            self.assertEqual(data["error_code"], "INVALID_DIMENSION")

    def test_shape_circle_segment_half_circle(self):
        # A 180-degree segment is a half disc: area = pi*r^2/2, chord = 2r.
        resp, data = self.get_json("/shape/circle_segment?radius=2&angle_degrees=180")
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(data["area"], 2 * math.pi, places=6)
        self.assertAlmostEqual(data["chord_length"], 4.0, places=6)

    def test_shape_circle_segment_full_circle_returns_400(self):
        resp, data = self.get_json("/shape/circle_segment?radius=2&angle_degrees=360")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data["error_code"], "INVALID_DIMENSION")

    def test_shape_polygon_rectangle_points(self):
        resp, data = self.get_json("/shape/polygon?points=(0,0),(4,0),(4,3),(0,3)")
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(data["area"], 12.0, places=6)
        self.assertAlmostEqual(data["perimeter"], 14.0, places=6)

    def test_shape_regular_polygon_square(self):
        resp, data = self.get_json("/shape/regular_polygon?num_sides=4&side_length=2")
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(data["area"], 4.0, places=6)
        self.assertAlmostEqual(data["perimeter"], 8.0, places=6)

    def test_shape_polygon_from_sides_angles_square(self):
        resp, data = self.get_json(
            "/shape/polygon_from_sides_angles?sides=2,2,2,2&angles_degrees=90,90,90,90")
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(data["area"], 4.0, places=6)

    def test_shape_polygon_from_sides_angles_bad_angle_sum_returns_400(self):
        resp, data = self.get_json(
            "/shape/polygon_from_sides_angles?sides=2,2,2,2&angles_degrees=90,90,90,80")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data["error_code"], "INVALID_ANGLE_SUM")

    def test_shape_cyclic_polygon_brahmagupta(self):
        # Cyclic quadrilateral 4,5,6,7: s = 11, area = sqrt(7*6*5*4) = sqrt(840).
        resp, data = self.get_json("/shape/cyclic_polygon?sides=4,5,6,7")
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(data["area"], math.sqrt(840), places=4)

    # ------------------------------------------------------- solids
    def test_solid_cube(self):
        resp, data = self.get_json("/solid/cube?side=2")
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(data["volume"], 8.0, places=6)
        self.assertAlmostEqual(data["surface_area"], 24.0, places=6)
        self.assertAlmostEqual(data["space_diagonal"], 2 * math.sqrt(3), places=6)

    def test_solid_cuboid(self):
        resp, data = self.get_json("/solid/cuboid?length=2&width=3&height=4")
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(data["volume"], 24.0, places=6)
        self.assertAlmostEqual(data["surface_area"], 52.0, places=6)

    def test_solid_cylinder(self):
        resp, data = self.get_json("/solid/cylinder?radius=1&height=2")
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(data["volume"], 2 * math.pi, places=6)
        self.assertAlmostEqual(data["surface_area"], 6 * math.pi, places=6)

    def test_solid_cone(self):
        # radius 3, height 4 -> slant height 5.
        resp, data = self.get_json("/solid/cone?radius=3&height=4")
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(data["slant_height"], 5.0, places=6)
        self.assertAlmostEqual(data["volume"], 12 * math.pi, places=6)
        self.assertAlmostEqual(data["surface_area"], 24 * math.pi, places=6)

    def test_solid_square_pyramid(self):
        # base 6, height 4 -> slant height 5, lateral area 60.
        resp, data = self.get_json("/solid/square_pyramid?base_side=6&height=4")
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(data["slant_height"], 5.0, places=6)
        self.assertAlmostEqual(data["volume"], 48.0, places=6)
        self.assertAlmostEqual(data["surface_area"], 96.0, places=6)

    def test_solid_negative_dimension_returns_400(self):
        resp, data = self.get_json("/solid/sphere?radius=-1")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data["error_code"], "INVALID_DIMENSION")

    def test_solid_missing_value_returns_400(self):
        resp, data = self.get_json("/solid/sphere")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data["error_code"], "MISSING_VALUE")

    def test_solid_bad_value_returns_400_not_500(self):
        resp, data = self.get_json("/solid/sphere?radius=abc")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data["error_code"], "INVALID_VALUE")

    def test_solid_unknown_type(self):
        resp, data = self.get_json("/solid/not_a_solid")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data["error_code"], "UNKNOWN_SOLID")

    # ------------------------------------------------- more theorems
    def test_theorem_sine_rule_ssa_ambiguous(self):
        resp, data = self.get_json("/theorem/sine_rule?a=6&b=8&angle_A_degrees=30")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(data["ambiguous"])
        self.assertEqual(data["num_solutions"], 2)

    def test_theorem_sine_rule_no_triangle(self):
        resp, data = self.get_json("/theorem/sine_rule?a=2&b=8&angle_A_degrees=30")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data["error_code"], "NO_TRIANGLE")

    def test_theorem_cosine_rule_sas(self):
        # a=5, b=7, C=60 -> c^2 = 25 + 49 - 35 = 39.
        resp, data = self.get_json("/theorem/cosine_rule?a=5&b=7&angle_C_degrees=60")
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(data["c"], math.sqrt(39), places=6)

    def test_theorem_cosine_rule_triangle_inequality(self):
        resp, data = self.get_json("/theorem/cosine_rule?a=1&b=2&c=10")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data["error_code"], "INVALID_TRIANGLE")

    def test_theorem_tangent_rule_identity_holds(self):
        # Right triangle 3-4-5: A = asin(3/5), B = asin(4/5).
        resp, data = self.get_json(
            "/theorem/tangent_rule?a=3&b=4"
            "&angle_A_degrees=36.86989765&angle_B_degrees=53.13010235")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(data["identity_holds"])

    def test_theorem_tangent_rule_identity_fails_for_inconsistent_triangle(self):
        resp, data = self.get_json(
            "/theorem/tangent_rule?a=3&b=4&angle_A_degrees=50&angle_B_degrees=60")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(data["identity_holds"])

    def test_theorem_ceva_medians_concurrent(self):
        resp, data = self.get_json("/theorem/ceva?bd_dc=1&ce_ea=1&af_fb=1")
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(data["product"], 1.0, places=6)
        self.assertTrue(data["concurrent"])

    def test_theorem_ceva_not_concurrent(self):
        resp, data = self.get_json("/theorem/ceva?bd_dc=2&ce_ea=1&af_fb=1")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(data["concurrent"])

    def test_theorem_ceva_zero_ratio_returns_400(self):
        # Query-string values arrive as strings; '0' must still be rejected.
        resp, data = self.get_json("/theorem/ceva?bd_dc=0&ce_ea=1&af_fb=1")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data["error_code"], "INVALID_VALUE")

    def test_theorem_menelaus_collinear(self):
        # 2 * (-1) * 0.5 = -1  ->  collinear.
        resp, data = self.get_json("/theorem/menelaus?bd_dc=2&ce_ea=-1&af_fb=0.5")
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(data["product"], -1.0, places=6)
        self.assertTrue(data["collinear"])

    def test_theorem_menelaus_not_collinear(self):
        resp, data = self.get_json("/theorem/menelaus?bd_dc=1&ce_ea=1&af_fb=1")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(data["collinear"])

    def test_theorem_unknown_type(self):
        resp, data = self.get_json("/theorem/not_a_theorem")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data["error_code"], "UNKNOWN_THEOREM")

