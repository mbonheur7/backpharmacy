from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, request, jsonify

from extensions import db_session
from models import (
    ChatGroup,
    ChatMember,
    ChatMessage,
    ChatMessageRead,
)
from services.permission_service import login_required, get_current_user


chat_bp = Blueprint("chat", __name__)

RWANDA_TZ = ZoneInfo("Africa/Kigali")


# =========================================================
# ROLE / PERMISSION HELPERS
# =========================================================

def normalize_role(user):
    """
    Convert the role into a predictable lowercase string.

    Examples:
    "Admin Viewer" -> "admin viewer"
    "viewer" -> "viewer"
    "SUPER_ADMIN" -> "super_admin"
    """

    return (user.role or "").strip().lower()


def is_viewer(user):
    """
    Detect viewer accounts.

    This intentionally checks whether the word 'viewer'
    appears in the role because your system currently
    displays roles such as 'Admin Viewer'.
    """

    return "viewer" in normalize_role(user)


def is_admin_group(group):
    """
    The Admin Viewer can write only in Admin Group.
    """

    return (
        group.name or ""
    ).strip().lower() == "admin group"


def is_group_member(group_id, user_id):
    """
    Check normal membership.
    """

    return (
        db_session.query(ChatMember)
        .filter(
            ChatMember.group_id == group_id,
            ChatMember.user_id == user_id,
        )
        .first()
        is not None
    )


def can_view_group(user, group):
    """
    Decide whether the user can READ a group.

    Admin Viewer:
        Can see ALL chat groups.

    Everyone else:
        Must be a normal member of the group.
    """

    if is_viewer(user):
        return True

    return is_group_member(
        group.id,
        user.id,
    )


def can_send_to_group(user, group):
    """
    Decide whether the user can SEND messages.

    Admin Viewer:
        Can send ONLY in Admin Group.

    Everyone else:
        Must be a normal member.
    """

    if is_viewer(user):
        return is_admin_group(group)

    return is_group_member(
        group.id,
        user.id,
    )


# =========================================================
# GROUP LOOKUP
# =========================================================

def get_group_for_user(group_id, user):
    """
    Get a group if the user is allowed to VIEW it.
    """

    group = (
        db_session.query(ChatGroup)
        .filter(
            ChatGroup.id == group_id
        )
        .first()
    )

    if not group:
        return None

    if not can_view_group(user, group):
        return None

    return group


# =========================================================
# SERIALIZATION
# =========================================================

def serialize_message(message):
    return {
        "id": message.id,
        "group_id": message.group_id,
        "sender_id": message.sender_id,
        "sender_username": message.sender.username,
        "sender_fullname": message.sender.fullname,
        "message": message.message,
        "created_at": (
            message.created_at.isoformat()
            if message.created_at
            else None
        ),
    }


# =========================================================
# GET CHAT GROUPS
# =========================================================

@chat_bp.get("/groups")
@login_required
def list_chat_groups():
    user = get_current_user()

    # -----------------------------------------------------
    # ADMIN VIEWER
    #
    # Viewer can SEE every group.
    # -----------------------------------------------------

    if is_viewer(user):

        groups = (
            db_session.query(ChatGroup)
            .order_by(ChatGroup.name)
            .all()
        )

    # -----------------------------------------------------
    # NORMAL USERS
    #
    # See only groups where they are members.
    # -----------------------------------------------------

    else:

        groups = (
            db_session.query(ChatGroup)
            .join(
                ChatMember,
                ChatMember.group_id == ChatGroup.id,
            )
            .filter(
                ChatMember.user_id == user.id
            )
            .order_by(ChatGroup.name)
            .all()
        )

    return jsonify({
        "groups": [
            {
                "id": group.id,
                "name": group.name,

                # VERY IMPORTANT:
                #
                # Frontend uses this value to decide
                # whether to display the message input.
                "can_send": can_send_to_group(
                    user,
                    group,
                ),
            }
            for group in groups
        ]
    }), 200


# =========================================================
# GET MESSAGES
# =========================================================

@chat_bp.get(
    "/groups/<int:group_id>/messages"
)
@login_required
def list_messages(group_id):

    user = get_current_user()

    group = get_group_for_user(
        group_id,
        user,
    )

    if not group:
        return jsonify({
            "error": (
                "You are not allowed to view "
                "this chat."
            )
        }), 403

    messages = (
        db_session.query(ChatMessage)
        .filter(
            ChatMessage.group_id == group_id
        )
        .order_by(
            ChatMessage.created_at.asc(),
            ChatMessage.id.asc(),
        )
        .all()
    )

    return jsonify({

        "group": {
            "id": group.id,
            "name": group.name,
            "can_send": can_send_to_group(
                user,
                group,
            ),
        },

        "messages": [
            serialize_message(message)
            for message in messages
        ],

    }), 200


# =========================================================
# SEND MESSAGE
# =========================================================

@chat_bp.post(
    "/groups/<int:group_id>/messages"
)
@login_required
def send_message(group_id):

    user = get_current_user()

    group = get_group_for_user(
        group_id,
        user,
    )

    if not group:
        return jsonify({
            "error": (
                "You are not allowed to access "
                "this chat."
            )
        }), 403

    # -----------------------------------------------------
    # IMPORTANT SECURITY CHECK
    #
    # Even if someone manipulates the frontend,
    # they still cannot send without backend permission.
    # -----------------------------------------------------

    if not can_send_to_group(
        user,
        group,
    ):
        return jsonify({
            "error": (
                "You have view-only access "
                "to this chat."
            )
        }), 403

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    message_text = (
        data.get("message") or ""
    ).strip()

    if not message_text:
        return jsonify({
            "error": (
                "Message cannot be empty."
            )
        }), 400

    if len(message_text) > 5000:
        return jsonify({
            "error": (
                "Message cannot exceed "
                "5000 characters."
            )
        }), 400

    message = ChatMessage(
        group_id=group.id,
        sender_id=user.id,
        message=message_text,
    )

    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)

    return jsonify({
        "message": serialize_message(
            message
        )
    }), 201


# =========================================================
# MARK GROUP AS READ
# =========================================================

@chat_bp.post(
    "/groups/<int:group_id>/read"
)
@login_required
def mark_group_read(group_id):

    user = get_current_user()

    group = get_group_for_user(
        group_id,
        user,
    )

    if not group:
        return jsonify({
            "error": (
                "You are not allowed to view "
                "this chat."
            )
        }), 403

    messages = (
        db_session.query(ChatMessage)
        .filter(
            ChatMessage.group_id == group_id
        )
        .all()
    )

    now = datetime.now(
        RWANDA_TZ
    )

    for message in messages:

        existing = (
            db_session.query(
                ChatMessageRead
            )
            .filter(
                ChatMessageRead.message_id
                == message.id,

                ChatMessageRead.user_id
                == user.id,
            )
            .first()
        )

        if not existing:

            db_session.add(
                ChatMessageRead(
                    message_id=message.id,
                    user_id=user.id,
                    read_at=now,
                )
            )

    db_session.commit()

    return jsonify({
        "message": (
            "Messages marked as read."
        )
    }), 200


# =========================================================
# UNREAD COUNTS
# =========================================================

@chat_bp.get("/unread")
@login_required
def unread_counts():

    user = get_current_user()

    # -----------------------------------------------------
    # VIEWER SEES ALL GROUPS
    # -----------------------------------------------------

    if is_viewer(user):

        groups = (
            db_session.query(ChatGroup)
            .all()
        )

    # -----------------------------------------------------
    # NORMAL USERS SEE THEIR GROUPS
    # -----------------------------------------------------

    else:

        groups = (
            db_session.query(ChatGroup)
            .join(
                ChatMember,
                ChatMember.group_id
                == ChatGroup.id,
            )
            .filter(
                ChatMember.user_id
                == user.id
            )
            .all()
        )

    result = []

    for group in groups:

        unread_count = (
            db_session.query(
                ChatMessage
            )
            .outerjoin(
                ChatMessageRead,

                (
                    (
                        ChatMessageRead.message_id
                        == ChatMessage.id
                    )
                    &
                    (
                        ChatMessageRead.user_id
                        == user.id
                    )
                ),
            )
            .filter(

                ChatMessage.group_id
                == group.id,

                ChatMessage.sender_id
                != user.id,

                ChatMessageRead.id.is_(None),

            )
            .count()
        )

        result.append({

            "group_id": group.id,

            "group_name": group.name,

            "unread_count": unread_count,

        })

    return jsonify({
        "unread": result
    }), 200