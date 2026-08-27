"""
This is where "Admin vs Pharmacist" is actually enforced. Every protected
route uses @login_required or @require_role(...) from here — React hiding a
button is cosmetic; this is the real gate. A request that skips the
frontend entirely (curl, Postman, a modified fetch call) still hits these
checks and gets rejected the same way.
"""

from functools import wraps

from flask import session, jsonify, g

from extensions import db_session
from models import User


def get_current_user():
    """Loads (and caches for this request) the User for the current session,
    or None if there isn't a valid, active, logged-in user."""
    if hasattr(g, "_current_user"):
        return g._current_user

    user_id = session.get("user_id")
    if not user_id:
        g._current_user = None
        return None

    user = db_session.query(User).get(user_id)
    if not user or not user.is_active:
        # A disabled account's existing session stops working the moment
        # an admin flips is_active to False — not just on next login.
        g._current_user = None
        return None

    g._current_user = user
    return user


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if get_current_user() is None:
            return jsonify({"error": "Authentication required."}), 401
        return fn(*args, **kwargs)
    return wrapper


def require_role(*roles):
    """@require_role("Admin") or @require_role("Admin", "Pharmacist").
    Implies login_required — a role check with no logged-in user is always
    a 401, never a 403."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if user is None:
                return jsonify({"error": "Authentication required."}), 401
            if user.role not in roles:
                return jsonify({"error": "You do not have permission to perform this action."}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
