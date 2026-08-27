from flask import Blueprint, request, jsonify

from extensions import db_session
from models import User
from services.auth_service import hash_password
from services.permission_service import require_role, get_current_user
from services.activity_log_service import log_activity
from serializers import serialize_user
from utils import error_response

users_bp = Blueprint("users", __name__)

# Deliberately no DELETE route anywhere in this file — users are soft-
# disabled via is_active, never deleted, per your instruction.


@users_bp.get("")
@require_role("Admin")
def list_users():
    users = db_session.query(User).order_by(User.fullname).all()
    return jsonify({"users": [serialize_user(u) for u in users]}), 200


@users_bp.post("")
@require_role("Admin")
def create_user():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    fullname = (data.get("fullname") or "").strip()
    role = data.get("role")

    if not username or not password or not fullname:
        return error_response("username, password, and fullname are required.")
    if role not in ("Admin", "Pharmacist"):
        return error_response("role must be 'Admin' or 'Pharmacist'.")
    if len(password) < 8:
        return error_response("Password must be at least 8 characters.")

    existing = db_session.query(User).filter(User.username == username).first()
    if existing:
        return error_response("That username is already taken.")

    user = User(
        username=username,
        password_hash=hash_password(password),
        fullname=fullname,
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    admin = get_current_user()
    log_activity(db_session, admin, "user_created", entity_type="user", entity_id=user.id,
                 details=f"Created {role} account '{username}'")
    db_session.commit()
    return jsonify({"user": serialize_user(user)}), 201


@users_bp.patch("/<int:user_id>/password")
@require_role("Admin")
def reset_password(user_id):
    user = db_session.query(User).get(user_id)
    if not user:
        return error_response("User not found.", 404)

    data = request.get_json(silent=True) or {}
    new_password = data.get("password") or ""
    if len(new_password) < 8:
        return error_response("Password must be at least 8 characters.")

    user.password_hash = hash_password(new_password)
    # A reset password is a fresh start — also clear any lockout state.
    user.failed_logins = 0
    user.locked_until = None

    admin = get_current_user()
    log_activity(db_session, admin, "user_password_reset", entity_type="user", entity_id=user.id,
                 details=f"Password reset for '{user.username}'")
    db_session.commit()
    return jsonify({"message": "Password reset."}), 200


@users_bp.patch("/<int:user_id>/status")
@require_role("Admin")
def set_user_status(user_id):
    """Enable/disable — the ONLY way an account stops working. There is
    no path in this file that deletes a user row."""
    user = db_session.query(User).get(user_id)
    if not user:
        return error_response("User not found.", 404)

    data = request.get_json(silent=True) or {}
    is_active = data.get("is_active")
    if not isinstance(is_active, bool):
        return error_response("is_active must be true or false.")

    admin = get_current_user()
    if user.id == admin.id and not is_active:
        return error_response("You cannot disable your own account.")

    user.is_active = is_active
    if not is_active:
        user.locked_until = None  # a disabled account doesn't also need a lockout timer

    log_activity(
        db_session, admin, "user_enabled" if is_active else "user_disabled",
        entity_type="user", entity_id=user.id, details=f"'{user.username}' set is_active={is_active}",
    )
    db_session.commit()
    return jsonify({"user": serialize_user(user)}), 200
