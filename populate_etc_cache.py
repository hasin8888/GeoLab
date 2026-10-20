"""
populate_etc_cache.py

Run this file ONCE (from PyCharm's terminal: `python populate_etc_cache.py`)
to download every Kimberling center's name + trilinear formula from the
Encyclopedia of Triangle Centers and store them in the local database
(etc_encyclopedia table in triangle_centers.db). After this finishes, every
Encyclopedia lookup in the app answers instantly from the local database --
no live network fetch, no waiting, even for the very first search of a
given center.

This is a ONE-TIME, LONG-RUNNING job:
  - It fetches all 42 ETC part-pages (some of them multi-megabyte).
  - Each page is also saved to the .etc_cache/ folder (etc_lookup.py's
    existing disk cache), so even if this script is interrupted and
    re-run, already-downloaded pages are not re-fetched over the network.
  - Expect this to take anywhere from a few minutes to ~15-20 minutes
    depending on your internet connection, since ETC's server is not
    fast and some pages are large.
  - It is safe to stop (Ctrl+C) and re-run later -- it resumes using the
    disk cache and INSERT OR REPLACE, so nothing is duplicated or lost.

What gets stored per center: kimberling_id, name, trilinear_formula,
source_url. This is reference/display data ONLY. It is never fed to the
app's safe barycentric evaluator -- position CALCULATION continues to use
only the small, hand-verified formula set in setup_db.py's CENTERS list.
"""

import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from setup_db import DB_PATH, init_db
from etc_lookup import (
    ETC_PART_RANGES,
    MAX_KNOWN_ID,
    _fetch_part_page,
    _load_from_disk_cache,
    parse_part_by_headings,
    part_url,
    EtcLookupError,
)

# The page parser (parse_part_by_headings) lives in etc_lookup.py, so this bulk
# job and the live lookup always read ETC pages the same way.

# How many part-pages to fetch over the network at the same time. The
# bottleneck here is network WAIT time (ETC's server is slow to respond),
# not CPU, so fetching several parts concurrently gives a large speedup
# with minimal risk -- each fetch is independent (own HTTP request, own
# disk-cache file, own list entry), so there's no contention between threads.
MAX_CONCURRENT_FETCHES = 8


def _prefetch_all(timeout: int) -> None:
    """Warm the disk cache for every not-yet-cached part, several at once.
    Already-cached parts are skipped instantly (cheap disk check) and never
    hit the network. This is pure I/O prefetching -- no parsing or DB
    writes happen here, so it's safe to run before the sequential pass below."""
    to_fetch = [p for p in ETC_PART_RANGES if _load_from_disk_cache(p[0]) is None]
    if not to_fetch:
        return

    print(f"Prefetching {len(to_fetch)} part-page(s) not yet in .etc_cache/ "
          f"(up to {MAX_CONCURRENT_FETCHES} at a time)...")

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_FETCHES) as pool:
        futures = {
            pool.submit(_fetch_part_page, part_num, timeout): part_num
            for part_num, _, _ in to_fetch
        }
        for fut in as_completed(futures):
            part_num = futures[fut]
            try:
                fut.result()
                print(f"  [OK] Part {part_num} downloaded and cached.")
            except EtcLookupError as exc:
                print(f"  !! Part {part_num} failed to download: {exc}")
                print("     It will be retried on the next run.")


def populate(db_path: str = DB_PATH, timeout: int = 30) -> None:
    # Make sure both tables exist before we start writing to them.
    init_db(db_path)

    # Phase 1: fetch every missing part-page concurrently, so we're not
    # waiting on ETC's slow server one page at a time. This only touches
    # the disk cache -- no parsing, no DB writes -- so it's safe to do
    # before the sequential parsing/storing pass below.
    _prefetch_all(timeout)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    total_parts = len(ETC_PART_RANGES)
    grand_total_found = 0
    grand_total_missing = 0
    started_at = time.time()

    for idx, (part_num, lo, hi) in enumerate(ETC_PART_RANGES, start=1):
        print(f"\n[{idx}/{total_parts}] Part {part_num}  (X({lo}) .. X({hi}))")

        # NOTE: there is intentionally NO "skip if already stored" shortcut
        # here. Earlier runs used a buggy parser that left thousands of rows
        # with NULL/wrong names, so every part is re-parsed from the local
        # .etc_cache/ files and rewritten with INSERT OR REPLACE. Parsing is
        # fast (~0.01s per part), and no duplicates can result.

        try:
            page_text = _fetch_part_page(part_num, timeout)
        except EtcLookupError as exc:
            print(f"  !! Failed to fetch part {part_num}: {exc}")
            print("     Skipping this part -- re-run the script later to retry it.")
            continue

        # GUARD: some ETC parts (currently Parts 38-42, X(74001)+) are not
        # published yet -- the site returns only a small navigation shell
        # page with no center entries. Skip it explicitly (rather than rely on
        # finding no headings) so a navigation shell can never be mistaken for
        # real data. A real part page is megabytes;
        # a shell is ~13 KB, so anything under 100 KB is treated as empty.
        if len(page_text) < 100_000:
            print(f"  -> Part {part_num} looks like an unpublished/empty shell "
                  f"page ({len(page_text):,} chars). Skipping -- nothing stored.")
            continue

        url = part_url(part_num)
        found_in_part = 0
        missing_in_part = 0
        rows = []

        parsed = parse_part_by_headings(page_text)

        for kimberling_id in range(lo, hi + 1):
            entry = parsed.get(kimberling_id)
            if entry is None:
                missing_in_part += 1
                continue
            name, trilinear = entry
            # Store the row even if only a name (no trilinear) was found --
            # some ETC entries are defined purely by relationship to
            # another center and legitimately have no formula of their own.
            rows.append((kimberling_id, name, trilinear, url))
            found_in_part += 1

        if rows:
            cur.executemany(
                """
                INSERT OR REPLACE INTO etc_encyclopedia
                    (kimberling_id, name, trilinear_formula, source_url)
                VALUES (?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()

        grand_total_found += found_in_part
        grand_total_missing += missing_in_part
        print(f"  -> stored {found_in_part} centers, {missing_in_part} IDs in this "
              f"range are not (yet) published on ETC.")

    conn.close()

    elapsed = time.time() - started_at
    print("\n" + "=" * 60)
    print(f"Done in {elapsed / 60:.1f} minutes.")
    print(f"Total centers cached: {grand_total_found}")
    print(f"Total unpublished IDs skipped: {grand_total_missing}")
    print(f"Highest known ID: X({MAX_KNOWN_ID})")
    print("Every Encyclopedia lookup in the app will now answer instantly")
    print("from the local database for any of these centers.")
    print("=" * 60)


if __name__ == "__main__":
    try:
        populate()
    except KeyboardInterrupt:
        print("\n\nStopped early. Already-cached parts are saved -- just")
        print("re-run `python populate_etc_cache.py` later to pick up where")
        print("you left off (it will skip parts already in .etc_cache/).")
        sys.exit(1)
