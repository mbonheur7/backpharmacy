from extensions import db_session
from models import (
    ChatGroup,
    ChatMember,
    ChatMessage,
)
from services.permission_service import (
    get_current_user,
)
from socketio_extension import socketio


# =========================================================
# ROLE / PERMISSION HELPERS
# =========================================================

def normalize_role(user):

    return (
        user.role or ""
    ).strip().lower()


def is_viewer(user):

    return (
        "viewer"
        in normalize_role(user)
    )


def is_admin_group(group):

    return (
        group.name or ""
    ).strip().lower() == "admin group"


def is_member(
    group_id,
    user_id,
):

    return (
        db_session.query(
            ChatMember
        )
        .filter(

            ChatMember.group_id
            == group_id,

            ChatMember.user_id
            == user_id,

        )
        .first()
        is not None
    )


def can_view_group(
    user,
    group,
):

    # Admin Viewer can READ every group.

    if is_viewer(user):
        return True

    return is_member(
        group.id,
        user.id,
    )


def can_send_to_group(
    user,
    group,
):

    # Admin Viewer can WRITE only
    # in Admin Group.

    if is_viewer(user):
        return is_admin_group(
            group
        )

    return is_member(
        group.id,
        user.id,
    )


# =========================================================
# SERIALIZE MESSAGE
# =========================================================

def serialize_socket_message(
    message
):

    return {

        "id": message.id,

        "group_id": (
            message.group_id
        ),

        "sender_id": (
            message.sender_id
        ),

        "sender_username": (
            message.sender.username
        ),

        "sender_fullname": (
            message.sender.fullname
        ),

        "message": (
            message.message
        ),

        "created_at": (

            message.created_at.isoformat()

            if message.created_at

            else None

        ),

    }


# =========================================================
# CONNECT
# =========================================================

@socketio.on("connect")
def handle_connect():

    user = get_current_user()

    if not user:
        return False

    return True


# =========================================================
# JOIN CHAT
# =========================================================

@socketio.on("join_chat")
def handle_join_chat(data):

    user = get_current_user()

    if not user:

        return {
            "success": False,
            "error": (
                "Authentication required."
            ),
        }

    data = data or {}

    group_id = (
        data.get("group_id")
    )

    if not isinstance(
        group_id,
        int,
    ):

        return {
            "success": False,
            "error": (
                "group_id must be "
                "an integer."
            ),
        }

    group = (
        db_session.query(
            ChatGroup
        )
        .filter(
            ChatGroup.id
            == group_id
        )
        .first()
    )

    if not group:

        return {
            "success": False,
            "error": (
                "Chat group not found."
            ),
        }

    # Viewer is allowed to join ALL groups.

    if not can_view_group(
        user,
        group,
    ):

        return {
            "success": False,
            "error": (
                "You are not allowed "
                "to view this chat."
            ),
        }

    from flask_socketio import (
        join_room
    )

    join_room(
        f"chat_{group_id}"
    )

    return {

        "success": True,

        "group_id": group_id,

        "group_name": (
            group.name
        ),

        "can_send": (
            can_send_to_group(
                user,
                group,
            )
        ),

    }


# =========================================================
# LEAVE CHAT
# =========================================================

@socketio.on("leave_chat")
def handle_leave_chat(data):

    user = get_current_user()

    if not user:

        return {
            "success": False,
            "error": (
                "Authentication required."
            ),
        }

    data = data or {}

    group_id = (
        data.get("group_id")
    )

    if not isinstance(
        group_id,
        int,
    ):

        return {
            "success": False,
            "error": (
                "group_id must be "
                "an integer."
            ),
        }

    group = (
        db_session.query(
            ChatGroup
        )
        .filter(
            ChatGroup.id
            == group_id
        )
        .first()
    )

    if not group:

        return {
            "success": False,
            "error": (
                "Chat group not found."
            ),
        }

    if not can_view_group(
        user,
        group,
    ):

        return {
            "success": False,
            "error": (
                "You are not allowed "
                "to access this chat."
            ),
        }

    from flask_socketio import (
        leave_room
    )

    leave_room(
        f"chat_{group_id}"
    )

    return {

        "success": True,

        "group_id": group_id,

    }


# =========================================================
# SEND MESSAGE
# =========================================================

@socketio.on("send_message")
def handle_send_message(data):

    user = get_current_user()

    if not user:

        return {
            "success": False,
            "error": (
                "Authentication required."
            ),
        }

    data = data or {}

    group_id = (
        data.get("group_id")
    )

    message_text = (
        data.get("message")
        or ""
    ).strip()


    # -----------------------------------------------------
    # VALIDATE GROUP ID
    # -----------------------------------------------------

    if not isinstance(
        group_id,
        int,
    ):

        return {
            "success": False,
            "error": (
                "group_id must be "
                "an integer."
            ),
        }


    # -----------------------------------------------------
    # VALIDATE MESSAGE
    # -----------------------------------------------------

    if not message_text:

        return {
            "success": False,
            "error": (
                "Message cannot "
                "be empty."
            ),
        }


    if len(message_text) > 5000:

        return {
            "success": False,
            "error": (
                "Message cannot exceed "
                "5000 characters."
            ),
        }


    # -----------------------------------------------------
    # GET GROUP
    # -----------------------------------------------------

    group = (
        db_session.query(
            ChatGroup
        )
        .filter(
            ChatGroup.id
            == group_id
        )
        .first()
    )


    if not group:

        return {
            "success": False,
            "error": (
                "Chat group not found."
            ),
        }


    # -----------------------------------------------------
    # CRITICAL PERMISSION CHECK
    #
    # Admin Viewer:
    #
    # Admin Group             -> CAN SEND
    #
    # Management & Pharmacy   -> CANNOT SEND
    #
    # -----------------------------------------------------

    if not can_send_to_group(
        user,
        group,
    ):

        return {
            "success": False,
            "error": (
                "You have view-only "
                "access to this chat."
            ),
        }


    # -----------------------------------------------------
    # CREATE MESSAGE
    # -----------------------------------------------------

    message = ChatMessage(

        group_id=group_id,

        sender_id=user.id,

        message=message_text,

    )


    db_session.add(
        message
    )

    db_session.commit()

    db_session.refresh(
        message
    )


    serialized = (
        serialize_socket_message(
            message
        )
    )


    # -----------------------------------------------------
    # SEND TO EVERYONE IN ROOM
    # -----------------------------------------------------

    socketio.emit(

        "new_message",

        serialized,

        room=f"chat_{group_id}",

    )


    return {

        "success": True,

        "message": serialized,

    }