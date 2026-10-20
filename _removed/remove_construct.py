"""
remove_construct.py

Removes the "01 Construct" tab from templates/app.html.

What it does (and nothing else):
  1. Backs up templates/app.html -> templates/app.html.bak
  2. Removes the Construct-only CSS, the <section id="pane-construct"> pane,
     the Construct JS block, and the Scientific Calculator JS block
  3. Removes the Construct nav button, renumbers the rest 01-06,
     and makes "Center Library" the default tab
  4. Refuses to write anything if any safety check fails

Run from your project folder:
    python remove_construct.py
"""

import re
import shutil
import sys
from pathlib import Path

TARGET = Path(__file__).parent / "templates" / "app.html"
BACKUP = TARGET.with_suffix(".html.bak")


def die(msg):
    print("ABORTED (nothing was changed):", msg)
    sys.exit(1)


if not TARGET.exists():
    die(f"{TARGET} not found. Run this from your project folder.")

src = TARGET.read_text(encoding="utf-8")

if 'id="pane-construct"' not in src:
    die("No Construct pane found - it may already be removed.")


def cut_between(text, start_marker, end_marker, label, keep_end=True):
    """Delete text from start_marker up to (not including) end_marker."""
    if text.count(start_marker) != 1:
        die(f"{label}: start marker found {text.count(start_marker)} times (expected 1).")
    i = text.index(start_marker)
    j = text.index(end_marker, i + len(start_marker))
    return text[:i] + text[j:]


# 1. Construct-only CSS  (from #constructWrap rule up to the "/* Encyclopedia */" comment)
src = cut_between(src, "  #constructWrap {\n    display: flex;", "  /* Encyclopedia */", "CSS")

# 2. Responsive rules for the construct layout inside the media query
media = (
    "    #constructWrap { flex-direction: column; height: auto; }\n"
    "    #ctSidebar { width: auto; border-right: none; border-bottom: 1px solid var(--line); }\n"
    "    #ctCanvasWrap { height: 360px; }\n"
)
if src.count(media) != 1:
    die("Media-query rules not found exactly once.")
src = src.replace(media, "")

# 3. Empty leftover comment
src = src.replace("  /* ---------- Construct page ---------- */\n", "")

# 4. The Construct pane (HTML)
src = cut_between(
    src,
    "  <!-- ============ CONSTRUCT ============ -->",
    "  <!-- ============ CENTER LIBRARY ============ -->",
    "Construct pane",
)

# 5. Construct JS (IIFE) - ends right before the Center Library JS banner
banner_construct = (
    "/* ==================================================================\n"
    "   CONSTRUCT PAGE - GeoGebra-style multi-shape canvas"
)
# The original uses an em dash; match it loosely with a regex instead.
m = re.search(
    r"/\* =+\n\s+CONSTRUCT PAGE .{1,3} GeoGebra-style multi-shape canvas\n\s+=+ \*/\n\(function \(\) \{",
    src,
)
if not m:
    die("Construct JS block start not found.")
m_end = re.search(
    r"/\* =+\n\s+CENTER LIBRARY PAGE\n\s+=+ \*/", src[m.end():]
)
if not m_end:
    die("Construct JS block end (Center Library banner) not found.")
src = src[: m.start()] + src[m.end() + m_end.start():]

# 6. Scientific calculator JS (also lived on the Construct page)
m = re.search(
    r"/\* =+\n\s+SCIENTIFIC CALCULATOR .{1,3} collapsible panel on the Construct page\n\s+=+ \*/\n\(function \(\) \{",
    src,
)
if not m:
    die("Calculator JS block start not found.")
end_tag = src.index("</script>", m.end())
src = src[: m.start()].rstrip("\n") + "\n" + src[end_tag:]

# 7. Nav: remove Construct button, renumber, set Center Library as default
old_nav = re.search(
    r'    <button class="nav-item active" data-pane="construct">.*?</button>\n'
    r'    <button class="nav-item" data-pane="centers"><span class="n">02</span>Center Library</button>\n'
    r'    <button class="nav-item" data-pane="encyclopedia"><span class="n">03</span>Encyclopedia \(ETC\)</button>\n'
    r'    <button class="nav-item" data-pane="shapes"><span class="n">04</span>2D Shapes</button>\n'
    r'    <button class="nav-item" data-pane="solids"><span class="n">05</span>3D Solids</button>\n'
    r'    <button class="nav-item" data-pane="theorems"><span class="n">06</span>Theorems</button>\n'
    r'    <button class="nav-item" data-pane="workspace"><span class="n">07</span>Geometry Workspace</button>',
    src,
)
if not old_nav:
    die("Nav block not found in the expected form.")
new_nav = (
    '    <button class="nav-item active" data-pane="centers"><span class="n">01</span>Center Library</button>\n'
    '    <button class="nav-item" data-pane="encyclopedia"><span class="n">02</span>Encyclopedia (ETC)</button>\n'
    '    <button class="nav-item" data-pane="shapes"><span class="n">03</span>2D Shapes</button>\n'
    '    <button class="nav-item" data-pane="solids"><span class="n">04</span>3D Solids</button>\n'
    '    <button class="nav-item" data-pane="theorems"><span class="n">05</span>Theorems</button>\n'
    '    <button class="nav-item" data-pane="workspace"><span class="n">06</span>Geometry Workspace</button>'
)
src = src[: old_nav.start()] + new_nav + src[old_nav.end():]

old = '<section class="pane" id="pane-centers">'
if src.count(old) != 1:
    die("pane-centers section not found exactly once.")
src = src.replace(old, '<section class="pane active" id="pane-centers">')

# ---------------- safety checks ----------------
for bad in ("pane-construct", "ctCanvas", "ctCalcToggle", "ctSidebar", "constructWrap"):
    if bad in src:
        die(f"'{bad}' is still present after editing - refusing to write.")

panes = re.findall(r'<section class="pane[^"]*" id="pane-([^"]+)"', src)
expected = ["centers", "encyclopedia", "shapes", "solids", "theorems", "workspace"]
if panes != expected:
    die(f"Unexpected panes after edit: {panes}")

if src.count("<script>") != 1 or src.count("</script>") != 1:
    die("Script tag count changed unexpectedly.")

# Every getElementById in the JS must still exist in the HTML
html_part, js_part = src.split("<script>", 1)
missing = [
    i for i in sorted(set(re.findall(r"getElementById\('([^']+)'\)", js_part)))
    if f'id="{i}"' not in html_part
]
if missing:
    die(f"JS references ids that no longer exist in the HTML: {missing}")

# ---------------- write ----------------
shutil.copy2(TARGET, BACKUP)
TARGET.write_text(src, encoding="utf-8")
print("Done.")
print(f"  Backup of the original: {BACKUP}")
print(f"  Panes now: {', '.join(panes)}")
print("  Restart the Flask app and reload /app.")
