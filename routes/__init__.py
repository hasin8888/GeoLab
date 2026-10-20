"""
routes/__init__.py

One Blueprint per feature area. app.py calls register_blueprints(app), so
all URLs stay exactly the same as before the split.
"""

from . import (
    pages,
    auth,
    solver_api,
    scenes_api,
    centers_api,
    shapes_api,
    solids_api,
    theorems_api,
    etc_formulas_api,
)

_MODULES = (
    pages,
    auth,
    solver_api,
    scenes_api,
    centers_api,
    shapes_api,
    solids_api,
    theorems_api,
    etc_formulas_api,
)


def register_blueprints(app):
    for module in _MODULES:
        app.register_blueprint(module.bp)
