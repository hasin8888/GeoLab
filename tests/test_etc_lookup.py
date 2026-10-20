"""
tests/test_etc_lookup.py

Tests for etc_lookup.py's single ETC page parser. No network: the part-page
is a small fake, so these tests are fast and always give the same result.
"""

import etc_lookup

PAGE = """
<html><body>
<p>Introduction text that mentions X(3) = isogonal conjugate of X(4) in passing.</p>
<h3 id="X1">X(1)&nbsp;=&nbsp;INCENTER</h3>
<p>Trilinears&nbsp;&nbsp;&nbsp;1 : 1 : 1<br>
Barycentrics&nbsp;&nbsp;&nbsp;a : b : c<br>
X(1) lies on these lines: {2, 7}</p>
<h3 id="X2">X(2)&nbsp;=&nbsp;CENTROID</h3>
<p>Trilinears&nbsp;&nbsp;&nbsp;1/a : 1/b : 1/c<br>
Barycentrics&nbsp;&nbsp;&nbsp;1 : 1 : 1</p>
<h3 id="X3">X(3)&nbsp;=&nbsp;CIRCUMCENTER</h3>
<p>X(3) = isogonal conjugate of X(4)<br>
Trilinears&nbsp;&nbsp;&nbsp;cos A : cos B : cos C</p>
<h3 id="X10">X(10) = SPIEKER CENTER</h3>
<p>defined only by a relationship, no formula line</p>
<h3 id="X80">X(80)&nbsp;&nbsp;NAME WITH A MISSING EQUALS SIGN</h3>
<h3 id="X164">X(164 = NAME WITH A MISSING BRACKET</h3>
</body></html>
"""


def test_name_comes_from_the_heading_not_from_a_relationship_line():
    fields = etc_lookup.parse_entry_html(etc_lookup.find_center_html(PAGE, 3))
    assert fields["name"] == "CIRCUMCENTER"          # not "isogonal conjugate of X(4)"
    assert fields["trilinear_formula"] == "cos A : cos B : cos C"
    assert fields["barycentric_formula"] is None


def test_formulas_are_read_and_entities_cleaned():
    fields = etc_lookup.parse_entry_html(etc_lookup.find_center_html(PAGE, 1))
    assert fields["name"] == "INCENTER"
    assert fields["trilinear_formula"] == "1 : 1 : 1"
    assert fields["barycentric_formula"] == "a : b : c"


def test_find_center_html_does_not_confuse_x1_with_x10():
    block = etc_lookup.find_center_html(PAGE, 1)
    assert "INCENTER" in block and "SPIEKER" not in block
    assert etc_lookup.find_center_html(PAGE, 5) is None


def test_entry_without_any_formula_has_none_fields():
    fields = etc_lookup.parse_entry_html(etc_lookup.find_center_html(PAGE, 10))
    assert fields == {"name": "SPIEKER CENTER", "trilinear_formula": None,
                      "barycentric_formula": None}


def test_typos_in_etc_headings_are_tolerated():
    assert etc_lookup.parse_entry_html(etc_lookup.find_center_html(PAGE, 80))["name"] == \
        "NAME WITH A MISSING EQUALS SIGN"
    assert etc_lookup.parse_entry_html(etc_lookup.find_center_html(PAGE, 164))["name"] == \
        "NAME WITH A MISSING BRACKET"


def test_bulk_and_single_parsers_agree():
    # The bulk cache job and the live lookup must read every entry identically.
    bulk = etc_lookup.parse_part_by_headings(PAGE)
    assert set(bulk) == {1, 2, 3, 10, 80, 164}
    for kid, (name, tri) in bulk.items():
        single = etc_lookup.parse_entry_html(etc_lookup.find_center_html(PAGE, kid))
        assert (single["name"], single["trilinear_formula"]) == (name, tri)


def test_fetch_center_info_uses_the_same_parser(monkeypatch):
    monkeypatch.setattr(etc_lookup, "_fetch_part_page", lambda part, timeout: PAGE)
    info = etc_lookup.fetch_center_info(1)
    assert info["status"] == "ok"
    assert info["name"] == "INCENTER"
    assert info["trilinear_formula"] == "1 : 1 : 1"
    assert info["barycentric_formula"] == "a : b : c"
    assert info["note"] is None
    assert "INCENTER" in info["raw_etc_text"]

    relation_only = etc_lookup.fetch_center_info(10)
    assert relation_only["name"] == "SPIEKER CENTER"
    assert relation_only["note"] is not None


def test_fetch_center_info_reports_a_missing_center(monkeypatch):
    monkeypatch.setattr(etc_lookup, "_fetch_part_page", lambda part, timeout: PAGE)
    try:
        etc_lookup.fetch_center_info(7)
    except etc_lookup.EtcLookupError as exc:
        assert exc.code == "CENTER_NOT_FOUND_ON_PAGE"
    else:
        raise AssertionError("expected EtcLookupError")
