"""
check_coverage.py

Reports for which Kimberling centers a diagram can be drawn, i.e. for which
etc_position.locate_center() finds a position on a sample triangle.

Usage (from the project folder):
    python check_coverage.py              # X(1) .. X(200)
    python check_coverage.py 1 1000       # X(1) .. X(1000)
    python check_coverage.py 5001 5100

Prints a summary grouped by result/error code and writes the failures to
coverage_failures.csv, so the most common failure reasons can be fixed first.
Uses the .etc_cache pages, so a part page is only downloaded once.
"""

import csv
import sys
from collections import Counter

from centers import Triangle
from etc_position import locate_center

TRIANGLE = Triangle(A=(0.0, 0.0), B=(7.0, 0.0), C=(2.0, 5.0))


def main() -> None:
    lo = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    counts: Counter = Counter()
    failures = []

    for n in range(lo, hi + 1):
        res = locate_center(n, TRIANGLE)
        if res.get("status") == "ok":
            counts["ok:" + res.get("method", "?")] += 1
        else:
            code = res.get("error_code", "UNKNOWN")
            counts["FAIL:" + code] += 1
            failures.append((n, code, res.get("message", "")))
        if n % 25 == 0:
            print(f"  ... X({n})", flush=True)

    total = hi - lo + 1
    ok = sum(v for k, v in counts.items() if k.startswith("ok:"))
    print(f"\nX({lo})..X({hi}): {ok}/{total} placed ({100 * ok / total:.1f}%)")
    for key, value in counts.most_common():
        print(f"  {key:40s} {value}")

    with open("coverage_failures.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["kimberling_id", "error_code", "message"])
        w.writerows(failures)
    print(f"\n{len(failures)} failures written to coverage_failures.csv")


if __name__ == "__main__":
    main()
