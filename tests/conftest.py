"""
tests/conftest.py

Shared pytest setup.

- Makes sure triangle_centers.db exists before any test runs, so you no
  longer have to remember to run `python setup_db.py` first. (If the file is
  already there it is left untouched.)
- Provides a `client` fixture (Flask test client) for new pytest-style tests.
"""

import os

import pytest

from setup_db import DB_PATH, init_db


@pytest.fixture(scope="session", autouse=True)
def _ensure_database():
    if not os.path.exists(DB_PATH):
        init_db()


@pytest.fixture
def client():
    from app import app

    app.config["TESTING"] = True
    return app.test_client()
