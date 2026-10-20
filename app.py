"""
app.py

Flask app entry point for the Triangle Centers & Geometry toolkit.

Run it with:
    python app.py

Then open http://127.0.0.1:5000/ in a browser. All routes live in the
`routes/` package (one Blueprint per feature area):

    routes/pages.py         /  /api  /app  /geometry  /solver
    routes/auth.py          /login  /register  /logout  /profile
    routes/centers_api.py   /centers  /info/<id>  /center/<id>  /position/<id>
    routes/etc_formulas_api.py  /api/center-formulas
    routes/shapes_api.py    /shapes  /shape/<type>
    routes/solids_api.py    /solids  /solid/<type>
    routes/theorems_api.py  /theorems  /theorem/<type>
    routes/solver_api.py    /api/solve  /api/solver/quantities
    routes/scenes_api.py    /api/scenes[/<name>]

Make sure you've already run `python app.py` once to create the database.
"""

import os

from flask import Flask, jsonify
from flask_login import LoginManager, current_user
from werkzeug.exceptions import HTTPException

from models import db, User
from routes import register_blueprints

app = Flask(__name__)

# Database configuration
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///geolab.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Secret key for sessions (in production, use environment variable)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

# Initialize database
db.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for session management."""
    return User.query.get(int(user_id))


# Create database tables
with app.app_context():
    db.create_all()

# Reject huge request bodies before they are read into memory. Scenes are
# capped at 2 MB (scene_store.MAX_SCENE_BYTES); leave a little headroom.
app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024
register_blueprints(app)


@app.errorhandler(HTTPException)
def _http_error(exc):
    """404 / 405 / 413 ... as JSON, like every other error in this API."""
    return jsonify({
        "status": "error",
        "error_code": (exc.name or "HTTP_ERROR").upper().replace(" ", "_"),
        "message": exc.description,
    }), exc.code


@app.errorhandler(Exception)
def _unexpected_error(exc):
    """Last resort: never leak an HTML traceback page. With FLASK_DEBUG=1 the
    exception is re-raised so the Werkzeug debugger still works."""
    if app.debug:
        raise exc
    app.logger.exception("Unhandled error")
    return jsonify({
        "status": "error",
        "error_code": "INTERNAL_ERROR",
        "message": "Unexpected server error.",
    }), 500


def _lan_ip():
    """This computer's address on the local network (what a phone on the same
    Wi-Fi types in), or None. The UDP "connect" sends no packet; it only makes
    the OS pick the network interface it would use."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


if __name__ == "__main__":
    # debug=True gives auto-reload + helpful error pages while developing, but
    # the Werkzeug debugger lets anyone who can reach the server run code, so
    # it is OFF unless you ask for it: `set FLASK_DEBUG=1` (Windows) or
    # `export FLASK_DEBUG=1` before running `python app.py`.
    debug_mode = os.environ.get("FLASK_DEBUG", "0") in ("1", "true", "True")

    # By default only this computer can reach the site. To open it from a phone
    # on the same Wi-Fi, start it with FLASK_HOST=0.0.0.0 (run_mobile.bat does
    # this for you). PORT changes the port (default 5000).
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    on_network = host not in ("127.0.0.1", "localhost", "::1")

    if on_network and debug_mode:
        # The Werkzeug debugger lets anyone who can reach the server run code.
        print("WARNING: debug mode is switched off because the site is reachable "
              "from the network.")
        debug_mode = False
    if on_network:
        ip = _lan_ip()
        if ip:
            print(f"\n  On your phone (same Wi-Fi) open:  http://{ip}:{port}/\n")

    app.run(debug=debug_mode, host=host, port=port)
