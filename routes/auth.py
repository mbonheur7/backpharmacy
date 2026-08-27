from flask import Blueprint, request, session, jsonify

from extensions import db_session
from services.auth_service import authenticate
from services.activity_log_service import log_activity
from services.permission_service import login_required, get_current_user
from serializers import serialize_user

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400

    result = authenticate(db_session, username, password, ip_address=request.remote_addr)

    if result.user is None:
        return jsonify({"error": result.error}), result.status

    # New session on every login (prevents session fixation across accounts
    # on a shared browser).
    session.clear()
    session["user_id"] = result.user.id
    session.permanent = True

    log_activity(db_session, result.user, "login")
    db_session.commit()

    return jsonify({"user": serialize_user(result.user)}), 200


@auth_bp.post("/logout")
@login_required
def logout():
    user = get_current_user()
    log_activity(db_session, user, "logout")
    db_session.commit()
    session.clear()
    return jsonify({"message": "Logged out."}), 200


@auth_bp.get("/me")
@login_required
def me():
    return jsonify({"user": serialize_user(get_current_user())}), 200
