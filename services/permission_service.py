"""
Central permission enforcement.

The frontend may hide buttons, but all important permissions are
enforced here on the backend.

Roles:

    Super Admin
        - Full system access.

    Pharmacist
        - Can perform pharmacist-related operations.

    Admin Viewer
        - Can view everything available to the Super Admin.
        - Cannot create, edit, delete, sell, manage stock,
          change prices, manage users, or perform other system changes.
        - Chat permission is handled separately:
            * Can view all chat groups.
            * Can send messages only in Admin Group.
"""

from functools import wraps

from flask import session, jsonify, g

from extensions import db_session
from models import User


# =========================================================
# ROLE NORMALIZATION
# =========================================================

def normalize_role(role):

    return (
        role or ""
    ).strip().lower()


# =========================================================
# CURRENT USER
# =========================================================

def get_current_user():
    """
    Load and cache the current active user for this request.

    Returns:
        User object if the session contains a valid active user.
        None otherwise.
    """

    if hasattr(
        g,
        "_current_user",
    ):
        return g._current_user


    user_id = session.get(
        "user_id"
    )


    if not user_id:

        g._current_user = None

        return None


    user = (
        db_session
        .query(User)
        .get(user_id)
    )


    if (
        not user
        or not user.is_active
    ):

        # If an account is disabled,
        # its existing session immediately
        # stops being valid.

        g._current_user = None

        return None


    g._current_user = user

    return user


# =========================================================
# LOGIN REQUIRED
# =========================================================

def login_required(fn):

    @wraps(fn)

    def wrapper(
        *args,
        **kwargs,
    ):

        user = (
            get_current_user()
        )


        if user is None:

            return jsonify(
                {
                    "error":
                        "Authentication required."
                }
            ), 401


        return fn(
            *args,
            **kwargs,
        )


    return wrapper


# =========================================================
# ROLE REQUIRED
# =========================================================

def require_role(
    *roles
):
    """
    Restrict an endpoint to specific roles.

    Example:

        @require_role("Super Admin")

    Or:

        @require_role(
            "Super Admin",
            "Pharmacist",
        )

    Role names are normalized so capitalization
    and extra spaces do not cause permission problems.
    """

    allowed_roles = {

        normalize_role(
            role
        )

        for role in roles

    }


    def decorator(fn):

        @wraps(fn)

        def wrapper(
            *args,
            **kwargs,
        ):

            user = (
                get_current_user()
            )


            # ---------------------------------------------
            # NOT LOGGED IN
            # ---------------------------------------------

            if user is None:

                return jsonify(
                    {
                        "error":
                            "Authentication required."
                    }
                ), 401


            # ---------------------------------------------
            # ROLE CHECK
            # ---------------------------------------------

            user_role = (
                normalize_role(
                    user.role
                )
            )


            if (
                user_role
                not in allowed_roles
            ):

                return jsonify(
                    {
                        "error":
                            "You do not have permission "
                            "to perform this action."
                    }
                ), 403


            return fn(
                *args,
                **kwargs,
            )


        return wrapper


    return decorator


# =========================================================
# ADMIN VIEWER HELPER
# =========================================================

def is_admin_viewer(
    user
):
    """
    Return True if the user is an Admin Viewer.

    Supports possible variations such as:

        Viewer
        Admin Viewer
        admin_viewer
    """

    if not user:
        return False


    role = (
        normalize_role(
            user.role
        )
    )


    return role in {

        "viewer",
        "admin viewer",
        "admin_viewer",

    }