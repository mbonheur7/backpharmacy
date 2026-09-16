from flask import Blueprint, request, jsonify

from extensions import db_session

from models import (
    Medicine,
    MedicineComment,
)

from services.permission_service import (
    login_required,
    get_current_user,
)


medicine_comments_bp = Blueprint(
    "medicine_comments",
    __name__,
)


# =========================================================
# ROLE HELPER
# =========================================================

def is_viewer(user):

    return (
        (user.role or "")
        .strip()
        .lower()
        == "admin viewer"
    )


# =========================================================
# GET MEDICINE COMMENTS
# =========================================================

@medicine_comments_bp.get(
    "/<int:medicine_id>/comments"
)
@login_required
def list_comments(medicine_id):

    medicine = (
        db_session.query(Medicine)
        .filter(
            Medicine.id == medicine_id
        )
        .first()
    )

    if not medicine:

        return jsonify({
            "error": "Medicine not found."
        }), 404


    comments = (
        db_session.query(MedicineComment)
        .filter(
            MedicineComment.medicine_id
            == medicine_id
        )
        .order_by(
            MedicineComment.created_at.asc()
        )
        .all()
    )


    return jsonify({

        "medicine_id": medicine.id,

        "comments": [

            {

                "id": comment.id,

                "comment": comment.comment,

                "user_id": comment.user_id,

                "username": (
                    comment.user.username
                ),

                "fullname": (
                    comment.user.fullname
                ),

                "created_at": (

                    comment.created_at.isoformat()

                    if comment.created_at

                    else None

                ),

            }

            for comment in comments

        ],

    }), 200


# =========================================================
# ADD MEDICINE COMMENT
# =========================================================

@medicine_comments_bp.post(
    "/<int:medicine_id>/comments"
)
@login_required
def add_comment(medicine_id):

    user = get_current_user()


    # -----------------------------------------------------
    # ADMIN VIEWER CANNOT WRITE COMMENTS
    # -----------------------------------------------------

    if is_viewer(user):

        return jsonify({

            "error": (
                "Admin Viewer accounts "
                "cannot add comments."
            )

        }), 403


    medicine = (
        db_session.query(Medicine)
        .filter(
            Medicine.id == medicine_id
        )
        .first()
    )


    if not medicine:

        return jsonify({

            "error": "Medicine not found."

        }), 404


    data = (
        request.get_json(
            silent=True
        )
        or {}
    )


    comment_text = (
        data.get("comment")
        or ""
    ).strip()


    if not comment_text:

        return jsonify({

            "error": (
                "Comment cannot be empty."
            )

        }), 400


    if len(comment_text) > 5000:

        return jsonify({

            "error": (
                "Comment cannot exceed "
                "5000 characters."
            )

        }), 400


    new_comment = MedicineComment(

        medicine_id=medicine.id,

        user_id=user.id,

        comment=comment_text,

    )


    db_session.add(
        new_comment
    )

    db_session.commit()

    db_session.refresh(
        new_comment
    )


    return jsonify({

        "message": (
            "Comment added successfully."
        ),

        "comment": {

            "id": new_comment.id,

            "medicine_id": (
                new_comment.medicine_id
            ),

            "user_id": (
                new_comment.user_id
            ),

            "username": (
                user.username
            ),

            "fullname": (
                user.fullname
            ),

            "comment": (
                new_comment.comment
            ),

            "created_at": (

                new_comment.created_at.isoformat()

                if new_comment.created_at

                else None

            ),

        },

    }), 201
# =========================================================
# DELETE MEDICINE COMMENT
# =========================================================

@medicine_comments_bp.delete(
    "/<int:medicine_id>/comments/<int:comment_id>"
)
@login_required
def delete_comment(
    medicine_id,
    comment_id,
):

    user = get_current_user()


    # -----------------------------------------------------
    # ADMIN VIEWER CANNOT DELETE COMMENTS
    # -----------------------------------------------------

    if is_viewer(user):

        return jsonify({

            "error": (
                "Admin Viewer accounts "
                "cannot delete comments."
            )

        }), 403


    # -----------------------------------------------------
    # CHECK MEDICINE EXISTS
    # -----------------------------------------------------

    medicine = (
        db_session.query(Medicine)
        .filter(
            Medicine.id == medicine_id
        )
        .first()
    )


    if not medicine:

        return jsonify({

            "error": "Medicine not found."

        }), 404


    # -----------------------------------------------------
    # FIND COMMENT
    # -----------------------------------------------------

    comment = (
        db_session.query(MedicineComment)
        .filter(
            MedicineComment.id == comment_id,
            MedicineComment.medicine_id == medicine_id,
        )
        .first()
    )


    if not comment:

        return jsonify({

            "error": "Comment not found."

        }), 404


    # -----------------------------------------------------
    # DELETE COMMENT
    # -----------------------------------------------------

    db_session.delete(
        comment
    )

    db_session.commit()


    return jsonify({

        "message": (
            "Comment deleted successfully."
        ),

        "comment_id": comment_id,

    }), 200