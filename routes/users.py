from flask import Blueprint, request, jsonify

from extensions import db_session
from models import User, ChatGroup, ChatMember
from services.auth_service import hash_password
from services.permission_service import require_role, get_current_user
from services.activity_log_service import log_activity
from serializers import serialize_user
from utils import error_response


users_bp = Blueprint("users", __name__)


# Users are never deleted.
# Accounts are disabled/enabled using the is_active field.


def sync_chat_membership(user):
    """
    Synchronize a user's chat memberships with their current role.

    Chat rules:
        Super Admin  -> Admin Group + Management & Pharmacy
        Admin Viewer -> Admin Group only
        Pharmacist   -> Management & Pharmacy only
    """

    # Remove the user's existing memberships first.
    db_session.query(ChatMember).filter(
        ChatMember.user_id == user.id
    ).delete(synchronize_session=False)

    if user.role == "Super Admin":
        group_names = [
            "Admin Group",
            "Management & Pharmacy",
        ]

    elif user.role == "Admin Viewer":
        group_names = [
            "Admin Group",
        ]

    elif user.role == "Pharmacist":
        group_names = [
            "Management & Pharmacy",
        ]

    else:
        group_names = []

    for group_name in group_names:
        group = (
            db_session.query(ChatGroup)
            .filter(ChatGroup.name == group_name)
            .first()
        )

        if group:
            db_session.add(
                ChatMember(
                    group_id=group.id,
                    user_id=user.id,
                )
            )


@users_bp.get("")
@require_role("Super Admin", "Admin Viewer")
def list_users():
    users = db_session.query(User).order_by(User.fullname).all()

    return jsonify({
        "users": [serialize_user(u) for u in users]
    }), 200


@users_bp.post("")
@require_role("Super Admin")
def create_user():
    data = request.get_json(silent=True) or {}

    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    fullname = (data.get("fullname") or "").strip()
    role = data.get("role")

    if not username or not password or not fullname:
        return error_response(
            "username, password, and fullname are required."
        )

    if role not in (
        "Super Admin",
        "Admin Viewer",
        "Pharmacist",
    ):
        return error_response(
            "role must be 'Super Admin', 'Admin Viewer', or 'Pharmacist'."
        )

    # Maximum of 2 active Super Admins.
    if role == "Super Admin":
        super_admin_count = (
            db_session.query(User)
            .filter(
                User.role == "Super Admin",
                User.is_active.is_(True),
            )
            .count()
        )

        if super_admin_count >= 2:
            return error_response(
                "The system can have a maximum of 2 active Super Admins."
            )

    if len(password) < 8:
        return error_response(
            "Password must be at least 8 characters."
        )

    existing = (
        db_session.query(User)
        .filter(User.username == username)
        .first()
    )

    if existing:
        return error_response(
            "That username is already taken."
        )

    user = User(
        username=username,
        password_hash=hash_password(password),
        fullname=fullname,
        role=role,
        is_active=True,
    )

    db_session.add(user)
    db_session.flush()

    # Automatically place the new user in the correct chat space.
    sync_chat_membership(user)

    admin = get_current_user()

    log_activity(
        db_session,
        admin,
        "user_created",
        entity_type="user",
        entity_id=user.id,
        details=f"Created {role} account '{username}'",
    )

    db_session.commit()

    return jsonify({
        "user": serialize_user(user)
    }), 201


@users_bp.patch("/<int:user_id>/role")
@require_role("Super Admin")
def change_user_role(user_id):
    """
    Change a user's role and automatically synchronize
    their chat-group membership.
    """

    user = db_session.query(User).get(user_id)

    if not user:
        return error_response(
            "User not found.",
            404,
        )

    data = request.get_json(silent=True) or {}
    new_role = data.get("role")

    if new_role not in (
        "Super Admin",
        "Admin Viewer",
        "Pharmacist",
    ):
        return error_response(
            "role must be 'Super Admin', 'Admin Viewer', or 'Pharmacist'."
        )

    admin = get_current_user()

    # Do not allow the logged-in Super Admin to change
    # their own role. This prevents accidentally removing
    # the last full administrator from the system.
    if user.id == admin.id and new_role != "Super Admin":
        return error_response(
            "You cannot change your own Super Admin role."
        )

    # Maximum of 2 active Super Admins.
    if (
        new_role == "Super Admin"
        and user.role != "Super Admin"
        and user.is_active
    ):
        super_admin_count = (
            db_session.query(User)
            .filter(
                User.role == "Super Admin",
                User.is_active.is_(True),
            )
            .count()
        )

        if super_admin_count >= 2:
            return error_response(
                "The system can have a maximum of 2 active Super Admins."
            )

    old_role = user.role

    user.role = new_role

    # Automatically adjust the user's chat access.
    sync_chat_membership(user)

    log_activity(
        db_session,
        admin,
        "user_role_changed",
        entity_type="user",
        entity_id=user.id,
        details=(
            f"Changed '{user.username}' role "
            f"from {old_role} to {new_role}"
        ),
    )

    db_session.commit()

    return jsonify({
        "user": serialize_user(user)
    }), 200


@users_bp.patch("/<int:user_id>/password")
@require_role("Super Admin")
def reset_password(user_id):
    user = db_session.query(User).get(user_id)

    if not user:
        return error_response(
            "User not found.",
            404,
        )

    data = request.get_json(silent=True) or {}
    new_password = data.get("password") or ""

    if len(new_password) < 8:
        return error_response(
            "Password must be at least 8 characters."
        )

    user.password_hash = hash_password(new_password)
    user.failed_logins = 0
    user.locked_until = None

    admin = get_current_user()

    log_activity(
        db_session,
        admin,
        "user_password_reset",
        entity_type="user",
        entity_id=user.id,
        details=f"Password reset for '{user.username}'",
    )

    db_session.commit()

    return jsonify({
        "message": "Password reset."
    }), 200


@users_bp.patch("/<int:user_id>/status")
@require_role("Super Admin")
def set_user_status(user_id):
    """
    Enable or disable a user account.

    Users are never deleted.
    Disabling an account sets is_active=False.
    """

    user = db_session.query(User).get(user_id)

    if not user:
        return error_response(
            "User not found.",
            404,
        )

    data = request.get_json(silent=True) or {}
    is_active = data.get("is_active")

    if not isinstance(is_active, bool):
        return error_response(
            "is_active must be true or false."
        )

    # Get the currently logged-in Super Admin.
    admin = get_current_user()

    # A Super Admin cannot disable their own account.
    if user.id == admin.id and not is_active:
        return error_response(
            "You cannot disable your own account."
        )

    # Never allow the last active Super Admin to be disabled.
    if (
        user.role == "Super Admin"
        and not is_active
    ):
        active_super_admins = (
            db_session.query(User)
            .filter(
                User.role == "Super Admin",
                User.is_active.is_(True),
            )
            .count()
        )

        if active_super_admins <= 1:
            return error_response(
                "The last active Super Admin cannot be disabled."
            )

    user.is_active = is_active

    if not is_active:
        # A disabled account does not need a lockout timer.
        user.locked_until = None

    log_activity(
        db_session,
        admin,
        "user_enabled" if is_active else "user_disabled",
        entity_type="user",
        entity_id=user.id,
        details=f"'{user.username}' set is_active={is_active}",
    )

    db_session.commit()

    return jsonify({
        "user": serialize_user(user)
    }), 200