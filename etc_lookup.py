"""
etc_lookup.py

Live lookup of any Kimberling center X(1) through X(84000) directly from
Clark Kimberling's Encyclopedia of Triangle Centers (ETC) website.

This does NOT compute a triangle position -- it fetches the center's
name and trilinear/barycentric formulas (as published) straight from
the live ETC page. For centers already in the local database (see
setup_db.py), position CALCULATION is available via
/center/<id>?triangle=... using verified, safely-evaluated formulas.
For everything else (up to X(84000)), this module provides pure
reference lookup: "what is X(12345)?" -- name and formulas only.

ONE PARSER FOR ETC PAGES
Every center on every ETC part-page starts with a heading like
    <h3 id="X1">X(1)&nbsp;=&nbsp;INCENTER</h3>
This module is the single place that knows that markup:
    find_center_html()      one center's raw HTML (heading up to the next one)
    parse_entry_html()      name / trilinears / barycentrics of one entry
    parse_part_by_headings() the same for a whole part-page (used by
                            populate_etc_cache.py)
The live lookup (/info fallback, main.py --info), the bulk cache and
etc_position.py all go through these, so they can never disagree about what
a center is called. (An older loose text-matching parser used to live here;
it sometimes mistook relationship lines such as "X(3) = isogonal conjugate
of X(4)" for a name, and was removed.)

NOTE: Part 1 in particular (ETC.html, covering X(1)-X(1000)) is a very
large page (the introduction plus a thousand detailed center entries),
so fetches can be slow -- a generous timeout and one retry are used.

NOTE: Some entries (especially higher-numbered ones) are defined only
as "X(n) = <relationship> of X(m)" with no independent trilinear or
barycentric line of their own -- those fields will legitimately be
null for such entries; that is not a parsing failure.
"""

import html as _html
import os
import re
import threading
import time

import requests

# Exact ETC part-page boundaries. NOT a uniform arithmetic progression --
# Part 5 spans 3000 IDs (7001-10000) while every other part after Part 1
# spans exactly 2000 -- so this is a literal table, not a formula, to
# avoid an off-by-one at that irregular boundary.
ETC_PART_RANGES = [
    (1, 1, 1000),
    (2, 1001, 3000),
    (3, 3001, 5000),
    (4, 5001, 7000),
    (5, 7001, 10000),
    (6, 10001, 12000),
    (7, 12001, 14000),
    (8, 14001, 16000),
    (9, 16001, 18000),
    (10, 18001, 20000),
    (11, 20001, 22000),
    (12, 22001, 24000),
    (13, 24001, 26000),
    (14, 26001, 28000),
    (15, 28001, 30000),
    (16, 30001, 32000),
    (17, 32001, 34000),
    (18, 34001, 36000),
    (19, 36001, 38000),
    (20, 38001, 40000),
    (21, 40001, 42000),
    (22, 42001, 44000),
    (23, 44001, 46000),
    (24, 46001, 48000),
    (25, 48001, 50000),
    (26, 50001, 52000),
    (27, 52001, 54000),
    (28, 54001, 56000),
    (29, 56001, 58000),
    (30, 58001, 60000),
    (31, 60001, 62000),
    (32, 62001, 64000),
    (33, 64001, 66000),
    (34, 66001, 68000),
    (35, 68001, 70000),
    (36, 70001, 72000),
    (37, 72001, 74000),
    (38, 74001, 76000),
    (39, 76001, 78000),
    (40, 78001, 80000),
    (41, 80001, 82000),
    (42, 82001, 84000),
]

MAX_KNOWN_ID = ETC_PART_RANGES[-1][2]

# In-memory cache so repeat lookups on the same part-page (very likely,
# since a page holds up to 3000 centers) don't re-fetch every time.
_page_cache: dict[int, str] = {}

# On-disk cache directory: an ETC part-page rarely changes once published,
# so once a part is fetched it is saved to disk and never fetched again --
# not even across server restarts. This is what makes repeat lookups (the
# common case, since each page covers up to 3000 centers) instant instead
# of a multi-second network round trip every single time.
_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".etc_cache")


def _disk_cache_path(part_num: int) -> str:
    return os.path.join(_CACHE_DIR, f"part_{part_num}.html")


# A part page that has no "<h3 id="X..."> headings is a placeholder for centers
# ETC has not published yet (e.g. parts 38-42 are ~12 KB stubs). Such a page
# must not be trusted for long, or the center would never show up once ETC
# publishes it.
_STUB_MAX_AGE_SECONDS = 24 * 3600


def _is_stub_page(text: str) -> bool:
    return '<h3 id="X' not in text


def _load_from_disk_cache(part_num: int):
    path = _disk_cache_path(part_num)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            if _is_stub_page(text) and time.time() - os.path.getmtime(path) > _STUB_MAX_AGE_SECONDS:
                return None  # stale placeholder: fetch again
            return text
        except OSError:
            return None
    return None


def _save_to_disk_cache(part_num: int, text: str) -> None:
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        path = _disk_cache_path(part_num)
        # Write to a temp file and rename, so a crash or a second process
        # can never leave a half-written page that is then served forever.
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except OSError:
        pass  # caching is a pure optimization -- never fail the request over it


class EtcLookupError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def to_payload(self):
        return {"status": "error", "error_code": self.code, "message": self.message}


def get_part_number(n: int) -> int:
    if n < 1:
        raise EtcLookupError("INVALID_ID", "Kimberling ID must be a positive integer.")
    for part_num, lo, hi in ETC_PART_RANGES:
        if lo <= n <= hi:
            return part_num
    raise EtcLookupError(
        "ID_OUT_OF_RANGE",
        f"X({n}) is outside the currently known ETC range (1-{MAX_KNOWN_ID}). "
        "The encyclopedia grows over time, so very new centers may not be covered yet.",
    )


def part_url(part_num: int) -> str:
    # IMPORTANT: Part 1 (X1-X1000) lives at plain ETC.html, not
    # ETCPart1.html (that URL 404s). Every other part (2-42) uses
    # the ETCPart<N>.html pattern with a capital "Part".
    if part_num == 1:
        return "https://faculty.evansville.edu/ck6/encyclopedia/ETC.html"
    return f"https://faculty.evansville.edu/ck6/encyclopedia/ETCPart{part_num}.html"


_part_locks: dict = {}
_part_locks_guard = threading.Lock()


def _lock_for(part_num: int) -> threading.Lock:
    with _part_locks_guard:
        return _part_locks.setdefault(part_num, threading.Lock())


def _fetch_part_page(part_num: int, timeout: int) -> str:
    """Fetch (with in-memory + on-disk caching, and one retry) the raw
    HTML of a part page. Checked in order: memory cache (fastest, this
    process), disk cache (fast, survives restarts), then a live network
    fetch (slow, only happens once per part ever).

    A per-part lock makes concurrent requests for the same part wait for ONE
    download instead of each starting their own multi-megabyte fetch."""
    if part_num in _page_cache:
        return _page_cache[part_num]

    with _lock_for(part_num):
        if part_num in _page_cache:  # another thread finished while we waited
            return _page_cache[part_num]

        disk_text = _load_from_disk_cache(part_num)
        if disk_text is not None:
            _page_cache[part_num] = disk_text
            return disk_text

        url = part_url(part_num)
        last_exc = None
        for attempt in range(2):  # try twice before giving up
            try:
                resp = requests.get(
                    url, timeout=(5, timeout), headers={"User-Agent": "Mozilla/5.0"}
                )
                resp.raise_for_status()
                _page_cache[part_num] = resp.text
                _save_to_disk_cache(part_num, resp.text)
                return resp.text
            except requests.RequestException as exc:
                last_exc = exc
                if attempt == 0:
                    time.sleep(1)  # brief pause before retrying once
        raise EtcLookupError(
            "FETCH_FAILED",
            f"Could not fetch ETC part {part_num} ({url}) after 2 attempts: {last_exc}",
        )


# ---------------------------------------------------------------------------
# The ONE parser for ETC pages (heading-based)
# ---------------------------------------------------------------------------

_H3_RE = re.compile(r'<h3 id="X(\d+)">(.*?)</h3>', re.DOTALL)
_NAME_FROM_HEADING_RE = re.compile(r"X\(\d+\)?\s*[=:]?\s*(.*)")
_TRILINEAR_RE = re.compile(
    r"Trilinears\s*(?:&nbsp;|\s)+(.+?)(?:<br\s*/?>|\n\s*\n|</p>|$)", re.DOTALL
)
_BARYCENTRIC_RE = re.compile(
    r"Barycentrics\s*(?:&nbsp;|\s)+(.+?)(?:<br\s*/?>|\n\s*\n|</p>|$)", re.DOTALL
)


def clean_html_text(s: str) -> str:
    """HTML -> plain text on one line: drop tags, unescape entities (&nbsp;
    included), collapse whitespace."""
    s = re.sub(r"<[^>]+>", " ", s)
    s = _html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def find_center_html(page_html: str, kimberling_id: int):
    """The raw HTML of X(kimberling_id)'s entry: from its
    <h3 id="X<n>"> heading up to the next center's heading. None if the page
    has no such heading. This is the one place that knows how ETC marks up
    an entry; etc_position.py uses it too."""
    start = page_html.find(f'<h3 id="X{kimberling_id}">')
    if start < 0:
        return None
    end = page_html.find('<h3 id="X', start + 10)
    return page_html[start: end if end > 0 else len(page_html)]


def parse_entry_html(entry_html: str) -> dict:
    """Name and published formulas of ONE entry (what find_center_html returns,
    or one slice of a part page).

    The name comes from the <h3> heading only -- never from lines further
    down such as "X(3) = isogonal conjugate of X(4)", which describe the
    center but are not its name. It tolerates ETC's own typos in a few
    headings, e.g. "X(80)  NAME" (missing '=') and "X(164 = NAME" (missing
    ')'). Any field ETC does not publish is None."""
    m = _H3_RE.search(entry_html)
    if not m:
        return {"name": None, "trilinear_formula": None, "barycentric_formula": None}
    heading = clean_html_text(m.group(2))
    nm = _NAME_FROM_HEADING_RE.match(heading)
    name = nm.group(1).strip() if nm and nm.group(1).strip() else None

    body = entry_html[m.end():]
    tm = _TRILINEAR_RE.search(body)
    bm = _BARYCENTRIC_RE.search(body)
    trilinear = clean_html_text(tm.group(1)) if tm else None
    barycentric = clean_html_text(bm.group(1)) if bm else None
    return {
        "name": name,
        "trilinear_formula": trilinear or None,
        "barycentric_formula": barycentric or None,
    }


def parse_part_by_headings(page_text: str) -> dict:
    """{kimberling_id: (name, trilinear_formula)} for one whole part-page.
    Splits the page on its <h3 id="X..."> headings, so it is exact and fast."""
    heads = list(_H3_RE.finditer(page_text))
    result = {}
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(page_text)
        fields = parse_entry_html(page_text[m.start():end])
        result[int(m.group(1))] = (fields["name"], fields["trilinear_formula"])
    return result


def fetch_center_info(kimberling_id: int, timeout: int = 15) -> dict:
    """
    Full pipeline: resolve which ETC part-page holds this ID, fetch it live
    (cached per part-page, with one retry on failure), cut out this
    center's entry, and return a structured payload.
    Raises EtcLookupError on any failure.
    """
    part_num = get_part_number(kimberling_id)
    url = part_url(part_num)

    page_text = _fetch_part_page(part_num, timeout)

    block = find_center_html(page_text, kimberling_id)
    if block is None:
        raise EtcLookupError(
            "CENTER_NOT_FOUND_ON_PAGE",
            f"X({kimberling_id}) does not appear on {url}. This ID falls "
            f"within ETC's numbering range (1-{MAX_KNOWN_ID}), but the "
            "encyclopedia does not yet have every number in that range "
            "filled in -- Kimberling reserves ranges in advance and new "
            "centers are added over time, so this specific ID likely just "
            "hasn't been published yet. (It's also possible ETC's page "
            "structure changed since this tool was built.)",
        )

    fields = parse_entry_html(block)
    return {
        "status": "ok",
        "kimberling_id": kimberling_id,
        "source": "live_etc_fetch",
        "source_url": url,
        "name": fields["name"],
        "trilinear_formula": fields["trilinear_formula"],
        "barycentric_formula": fields["barycentric_formula"],
        "note": (
            None
            if fields["trilinear_formula"] or fields["barycentric_formula"]
            else "This center is defined by its relationship to another "
            "center rather than an independent formula -- see 'name' above."
        ),
        "raw_etc_text": clean_html_text(block)[:2000],  # cap size for a sane response
    }
