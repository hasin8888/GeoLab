"""
routes/auth.py

Authentication routes: Login, Register, Logout.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User

bp = Blueprint("auth", __name__)


@bp.route("/register", methods=["GET", "POST"])
def register():
    """User registration page."""
    if current_user.is_authenticated:
        return redirect(url_for("pages.home_page"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        # Validation
        errors = []

        if not username or len(username) < 3:
            errors.append("Username must be at least 3 characters long.")
        if not email or "@" not in email:
            errors.append("Please enter a valid email address.")
        if not password or len(password) < 6:
            errors.append("Password must be at least 6 characters long.")
        if password != password_confirm:
            errors.append("Passwords do not match.")

        # Check if user already exists
        if User.query.filter_by(username=username).first():
            errors.append("Username already taken.")
        if User.query.filter_by(email=email).first():
            errors.append("Email already registered.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return redirect(url_for("auth.register"))

        # Create new user
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash(f"Account created successfully! Welcome {username}. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    """User login page."""
    if current_user.is_authenticated:
        return redirect(url_for("pages.home_page"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        remember = request.form.get("remember", False)

        if not email or not password:
            flash("Please enter email and password.", "danger")
            return redirect(url_for("auth.login"))

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            flash(f"Welcome back, {user.username}!", "success")
            return redirect(url_for("pages.home_page"))
        else:
            flash("Invalid email or password.", "danger")
            return redirect(url_for("auth.login"))

    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    """Log out the current user."""
    username = current_user.username
    logout_user()
    flash(f"Logged out successfully. Goodbye, {username}!", "info")
    return redirect(url_for("pages.home_page"))


@bp.route("/profile")
@login_required
def profile():
    """User profile page."""
    return render_template("profile.html", user=current_user)


@bp.route("/api/user")
def get_user_info():
    """Get current user info (for AJAX requests)."""
    if current_user.is_authenticated:
        return jsonify({
            "status": "ok",
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "authenticated": True
        })
    return jsonify({
        "status": "ok",
        "authenticated": False
    })
