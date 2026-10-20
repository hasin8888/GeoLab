"""
test_solver.py

Sanity tests for solver.py. Run from the project folder:

    pytest tests/test_solver.py

Uses unittest-style classes, which pytest runs as-is. Every expected number below is a well-known textbook value, so a failure means a real bug.
"""

import math
import unittest

from solver import solve, SolverError


def close(x, y, tol=1e-6):
    return abs(x - y) <= tol * max(1.0, abs(x), abs(y))


class SolverTests(unittest.TestCase):

    def test_sss_13_14_15(self):
        # The classic 13-14-15 triangle: area 84, R = 65/8, r = 4.
        r = solve({"a": 13, "b": 14, "c": 15})
        k = r["conclusion"]["known"]
        self.assertTrue(close(k["s"], 21))
        self.assertTrue(close(k["Delta"], 84))
        self.assertTrue(close(k["R"], 65 / 8))
        self.assertTrue(close(k["r"], 4))
        self.assertTrue(close(k["h_b"], 12))       # 2*84/14
        self.assertTrue(close(k["alpha"] + k["beta"] + k["gamma"], 180))
        self.assertTrue(r["consistency_check"]["all_hold"])

    def test_right_triangle_3_4_5(self):
        r = solve({"a": 3, "b": 4, "c": 5})
        k = r["conclusion"]["known"]
        self.assertTrue(close(k["gamma"], 90))
        self.assertTrue(close(k["Delta"], 6))
        self.assertTrue(close(k["R"], 2.5))        # hypotenuse / 2
        self.assertTrue(close(k["r"], 1))          # (3+4-5)/2

    def test_sas(self):
        # a=5, b=7, gamma=60  ->  c^2 = 25+49-35 = 39
        r = solve({"a": 5, "b": 7, "gamma": 60})
        k = r["conclusion"]["known"]
        self.assertTrue(close(k["c"], math.sqrt(39)))
        self.assertTrue(close(k["Delta"], 0.5 * 5 * 7 * math.sin(math.radians(60))))
        self.assertTrue(r["consistency_check"]["all_hold"])

    def test_asa(self):
        # a=10, alpha=40, beta=65 -> gamma=75
        r = solve({"a": 10, "alpha": 40, "beta": 65})
        k = r["conclusion"]["known"]
        self.assertTrue(close(k["gamma"], 75))
        self.assertTrue(close(k["b"], 10 * math.sin(math.radians(65)) / math.sin(math.radians(40))))
        self.assertTrue(r["consistency_check"]["all_hold"])

    def test_equilateral_from_side_only_needs_more(self):
        # One side alone cannot fix a triangle: solver must NOT invent values.
        r = solve({"a": 5}, want=["b"])
        self.assertNotIn("b", r["conclusion"]["known"])
        self.assertTrue(any("Could not derive" in w for w in r["warnings"]))

    def test_ssa_two_solutions_is_flagged(self):
        # a=6, b=8, alpha=30 -> sin(beta)=2/3 -> two valid triangles.
        r = solve({"a": 6, "b": 8, "alpha": 30})
        self.assertTrue(any("ambiguous" in w.lower() for w in r["warnings"]))
        k = r["conclusion"]["known"]
        self.assertTrue(close(k["beta"], math.degrees(math.asin(2 / 3))))  # acute root

    def test_ssa_no_triangle(self):
        # a=2, b=8, alpha=30 -> sin(beta)=2 > 1 -> impossible.
        with self.assertRaises(SolverError) as cm:
            solve({"a": 2, "b": 8, "alpha": 30})
        self.assertEqual(cm.exception.code, "NO_TRIANGLE")

    def test_angles_only_warns_about_size(self):
        r = solve({"alpha": 60, "beta": 60})
        k = r["conclusion"]["known"]
        self.assertTrue(close(k["gamma"], 60))
        self.assertTrue(any("SIZE" in w for w in r["warnings"]))

    def test_angle_sum_violation(self):
        with self.assertRaises(SolverError):
            solve({"alpha": 100, "beta": 90})

    def test_triangle_inequality_violation(self):
        with self.assertRaises(SolverError):
            solve({"a": 1, "b": 2, "c": 10})

    def test_rejects_nonpositive_and_bad_angles(self):
        for bad in ({"a": -3}, {"a": 0}, {"alpha": 0}, {"alpha": 180}, {"a": "abc"}):
            with self.assertRaises(SolverError):
                solve(bad)

    def test_unknown_quantity(self):
        with self.assertRaises(SolverError) as cm:
            solve({"x": 3})
        self.assertEqual(cm.exception.code, "UNKNOWN_QUANTITY")

    def test_medians_apollonius(self):
        # Right triangle 3-4-5: median to hypotenuse = 2.5.
        r = solve({"a": 3, "b": 4, "c": 5})
        self.assertTrue(close(r["conclusion"]["known"]["m_c"], 2.5))

    def test_radii_round_trip(self):
        # Give R and Delta-related info back: 13-14-15 from (a, b, c, R).
        r = solve({"a": 13, "b": 14, "c": 15, "R": 65 / 8})
        self.assertTrue(close(r["conclusion"]["known"]["Delta"], 84))

    def test_steps_are_justified(self):
        r = solve({"a": 13, "b": 14, "c": 15})
        for s in r["steps"]:
            self.assertTrue(s["theorem"])
            self.assertTrue(s["formula"])
            self.assertIn("uses", s)

