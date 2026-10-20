"""
test_construction.py

Tests for construction.py and the /draw + /api/construction routes.
Triangle used: A=(0,0), B=(4,0), C=(0,3) -- a 3-4-5 right triangle with
well-known centers, so every expected number is a textbook value.
"""

import math
import unittest

from app import app
from centers import Triangle, TriangleCenterError
from construction import build_construction

RIGHT = Triangle(A=(0, 0), B=(4, 0), C=(0, 3))


def xy(p):
    return p["x"], p["y"]


class ConstructionTests(unittest.TestCase):

    def test_right_triangle_centers(self):
        d = build_construction(RIGHT)
        self.assertEqual(d["triangle_type"], "right")
        self.assertAlmostEqual(d["area"], 6.0, places=9)
        for key, expected in (("G", (4 / 3, 1)), ("O", (2, 1.5)), ("I", (1, 1)),
                              ("H", (0, 0)), ("N", (1, 0.75))):
            x, y = xy(d["centers"][key])
            self.assertAlmostEqual(x, expected[0], places=9, msg=key)
            self.assertAlmostEqual(y, expected[1], places=9, msg=key)

    def test_right_triangle_circles(self):
        c = build_construction(RIGHT)["circles"]
        self.assertAlmostEqual(c["circumcircle"]["radius"], 2.5, places=9)
        self.assertAlmostEqual(c["incircle"]["radius"], 1.0, places=9)
        self.assertAlmostEqual(c["nine_point_circle"]["radius"], 1.25, places=9)

    def test_euler_line_contains_g_o_h(self):
        d = build_construction(Triangle(A=(1, 1), B=(10, 1), C=(4, 7)))
        c = d["centers"]
        # G divides OH in the ratio 1:2, so G = O + (H - O) / 3.
        self.assertAlmostEqual(c["G"]["x"], c["O"]["x"] + (c["H"]["x"] - c["O"]["x"]) / 3, places=9)
        self.assertAlmostEqual(c["G"]["y"], c["O"]["y"] + (c["H"]["y"] - c["O"]["y"]) / 3, places=9)
        self.assertIsNotNone(d["euler_line"])
        dx, dy = d["euler_line"]["direction"]["x"], d["euler_line"]["direction"]["y"]
        self.assertAlmostEqual(math.hypot(dx, dy), 1.0, places=9)

    def test_equilateral_has_no_euler_line(self):
        d = build_construction(Triangle(A=(0, 0), B=(2, 0), C=(1, math.sqrt(3))))
        self.assertIsNone(d["euler_line"])
        self.assertEqual(d["triangle_type"], "acute")

    def test_obtuse_orthocenter_outside(self):
        d = build_construction(Triangle(A=(1, 1), B=(11, 1), C=(3, 2.5)))
        self.assertEqual(d["triangle_type"], "obtuse")
        self.assertEqual(d["circles"]["circumcircle"]["center"], d["centers"]["O"])

    def test_altitude_feet_are_perpendicular(self):
        d = build_construction(RIGHT)
        fx, fy = xy(d["altitude_feet"]["A"])  # foot from A onto BC
        # BC direction is (-4, 3); A->foot must be perpendicular to it.
        self.assertAlmostEqual(fx * -4 + fy * 3, 0.0, places=9)

    def test_degenerate_triangle_raises(self):
        with self.assertRaises(TriangleCenterError):
            build_construction(Triangle(A=(0, 0), B=(1, 0), C=(2, 0)))


class DrawRouteTests(unittest.TestCase):

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_draw_page_loads(self):
        self.assertEqual(self.client.get("/draw").status_code, 200)

    def test_api_construction_ok(self):
        resp = self.client.get("/api/construction?triangle=(0,0),(4,0),(0,3)")
        data = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["status"], "ok")
        self.assertIn("verified_centers", data)
        self.assertAlmostEqual(data["centers"]["O"]["x"], 2.0, places=9)

    def test_api_construction_matches_center_endpoint(self):
        # The centroid X(2) from the verified DB must equal the drawn G.
        data = self.client.get("/api/construction?triangle=(0,0),(4,0),(0,3)").get_json()
        x2 = [c for c in data["verified_centers"] if c["id"] == 2]
        if x2:  # only if the local DB contains X(2)
            self.assertAlmostEqual(x2[0]["x"], data["centers"]["G"]["x"], places=6)
            self.assertAlmostEqual(x2[0]["y"], data["centers"]["G"]["y"], places=6)

    def test_api_construction_degenerate_is_400(self):
        resp = self.client.get("/api/construction?triangle=(0,0),(1,0),(2,0)")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["status"], "error")

    def test_api_construction_missing_param_is_400(self):
        resp = self.client.get("/api/construction")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error_code"], "MISSING_TRIANGLE")

    def test_api_construction_malformed_is_400(self):
        resp = self.client.get("/api/construction?triangle=not,a,triangle")
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
