# Triangle Centers & Geometry Toolkit

A Python geometry project with three ways to use the same engines:

- a **Flask web app / JSON API** (`app.py`)
- a **command-line tool** (`main.py`)
- plain **Python modules** you can import

It covers Kimberling triangle centers (Encyclopedia of Triangle Centers),
2D shapes, 3D solids, classic triangle theorems, a coordinate-free triangle
problem solver, and an interactive geometry workspace.

## Setup

Requires Python 3.10+.

```bash
# recommended: uv (uv.lock is included; also installs pytest)
uv sync
uv run python app.py

# or with pip
pip install flask requests pytest
```

Create the triangle-centers database once:

```bash
python setup_db.py
# optional: bulk-cache the whole encyclopedia for instant /info lookups
python populate_etc_cache.py
```

## Run the web app

```bash
python app.py
```

Then open <http://127.0.0.1:5000/>.

| Page | What it is |
|------|------------|
| `/` | Home page linking to everything |
| `/app` | Full single-page frontend (centers, encyclopedia, shapes, solids, theorems) |
| `/solver` | Coordinate-free triangle problem solver |
| `/geometry` | Interactive geometry workspace (points, segments, lines, polygons, circles, ellipses) |
| `/api` | JSON index of every API endpoint |

Debug mode is **off** by default. For development (auto-reload and error
pages) turn it on with `set FLASK_DEBUG=1` (Windows) or `export FLASK_DEBUG=1`
before `python app.py`. Never run a public site with debug on.

### Use it on your phone

Phone and computer must be on the **same Wi-Fi**. Double-click
`run_mobile.bat` (or set `FLASK_HOST=0.0.0.0` before `python app.py`). It
prints an address like `http://192.168.x.x:5000/`; type that into the phone's
browser. If Windows asks, allow Python through the firewall on *Private*
networks. Debug mode is always switched off in this mode.

On a touch screen: one finger uses the active tool, two fingers pinch-zoom and
pan the drawing, and the **Panel** button opens the side panel. **Done**,
**Cancel** and **Flip** replace the Enter, Esc and F keys.

### API endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /centers?q=<text>` | List locally verified centers |
| `GET /info/<id>` | Name and formulas for any center X(1)..X(84000) |
| `GET /center/<id>?triangle=(x1,y1),(x2,y2),(x3,y3)` | Compute a center's (x, y) for a triangle |
| `GET /position/<id>?triangle=...` | Position of any center whose ETC entry gives a formula or construction (used for Encyclopedia diagrams) |
| `GET /shapes`, `GET /shape/<type>?...` | 2D shapes: area, perimeter, angles |
| `GET /solids`, `GET /solid/<type>?...` | 3D solids: volume, surface area |
| `GET /theorems`, `GET /theorem/<type>?...` | Sine/cosine/tangent rules, Ceva, Menelaus |
| `POST /api/solve` | Solve a triangle from any known lengths/angles/radii |
| `GET /api/center-formulas` | Barycentric formulas of every verified center as small JavaScript expressions (used by the geometry workspace to keep centers live while you drag a vertex) |
| `GET/PUT/DELETE /api/scenes/<name>` | Save, load and delete geometry-workspace scenes |

Examples:

```
/center/1?triangle=(0,0),(4,0),(0,3)
/shape/ellipse?semi_major=5&semi_minor=3
/solid/cone?radius=3&height=4
/theorem/ceva?bd_dc=1&ce_ea=1&af_fb=1
```

Errors are always JSON with `status: "error"`, an `error_code` and a
`message`; bad input returns HTTP 400, never a 500.

## Command line

```bash
python main.py --center 1 --triangle "(0,0),(4,0),(0,3)" --pretty
python main.py --info 1
python main.py --list --query centroid
python main.py --list-shapes
python main.py --shape ellipse --param semi_major=5 --param semi_minor=3
python main.py --list-solids
python main.py --solid cone --param radius=3 --param height=4
python main.py --list-theorems
python main.py --theorem cosine_rule --param a=3 --param b=4 --param c=5
```

Add `--pretty` for indented JSON. Run `python main.py` with no arguments
for the full help.

## Project layout

| File | Role |
|------|------|
| `app.py` | Flask app entry point (registers the blueprints) |
| `routes/` | One Flask Blueprint per area: `pages`, `centers_api`, `etc_formulas_api`, `shapes_api`, `solids_api`, `theorems_api`, `solver_api`, `scenes_api` |
| `main.py` | Command-line interface |
| `dispatch.py` | Shape / solid / theorem tables and error handling shared by the routes and the CLI |
| `center_info.py` | Center lookup (`/info`, `/centers`, `--info`, `--list`) shared by the routes and the CLI |
| `centers.py` | Triangle-center formulas and the verified database |
| `etc_lookup.py`, `populate_etc_cache.py` | Live ETC lookup and bulk cache |
| `shapes.py` | 2D shapes |
| `solids.py` | 3D solids |
| `triangle_theorems.py` | Sine/cosine/tangent rules, Ceva, Menelaus |
| `solver.py` | Coordinate-free triangle solver |
| `scene_store.py` | Persistence for geometry-workspace scenes (`scenes/`) |
| `setup_db.py` | Creates and fills `triangle_centers.db` |
| `tests/` | pytest test suite (`test_app.py`, `test_geometry.py`, `test_solver.py`, `test_etc_formulas.py`, `test_scenes.py`, `conftest.py`) |
| `templates/`, `static/` | Front end |
| `_removed/`, `_backup/` | Old or retired files kept for reference (not used by the app) |

## Tests

```bash
pytest            # or: uv run pytest
pytest tests/test_solver.py   # a single file
```

Tests live in `tests/`. `tests/conftest.py` creates `triangle_centers.db`
automatically if it is missing, so no manual `setup_db.py` step is needed
for testing. `test_app.py` also writes and then deletes a temporary scene in
`scenes/`.
