from datetime import date, datetime, timezone

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from extensions import db_session
from models.expense import Expense
from models.activity_log import ActivityLog

from services.permission_service import (
    login_required,
    get_current_user,
)


expenses_bp = Blueprint(
    "expenses",
    __name__,
    url_prefix="/expenses",
)


# =========================================================
# HELPERS
# =========================================================

def can_manage_expenses(user):
    """
    Only Super Admin can create, edit, or delete expenses.
    Admin Viewer can view.
    Pharmacist cannot access financial expenses.
    """

    return user.role == "Super Admin"


def can_view_expenses(user):
    """
    Financial information is available only to:

    - Super Admin
    - Admin Viewer
    """

    return user.role in [
        "Super Admin",
        "Admin Viewer",
    ]


def forbidden(message):
    return jsonify({
        "error": message,
    }), 403


def not_found(message):
    return jsonify({
        "error": message,
    }), 404


def bad_request(message):
    return jsonify({
        "error": message,
    }), 400


def serialize_expense(expense):

    return {
        "id": expense.id,

        "title": expense.title,

        "category": expense.category,

        "description": expense.description,

        "amount": float(
            expense.amount
        ),

        "expense_date": (
            expense.expense_date.isoformat()
            if expense.expense_date
            else None
        ),

        "created_by_id": expense.created_by_id,

        "created_by_name": (
            expense.created_by.fullname
            if expense.created_by
            else None
        ),

        "created_at": (
            expense.created_at.isoformat()
            if expense.created_at
            else None
        ),

        "updated_at": (
            expense.updated_at.isoformat()
            if expense.updated_at
            else None
        ),
    }


def log_activity(
    user_id,
    action,
    details,
):
    """
    Creates an activity log entry.

    This helper assumes your ActivityLog model has:
    - user_id
    - action
    - details
    """

    activity = ActivityLog(
        user_id=user_id,
        action=action,
        details=details,
    )

    db_session.add(
        activity
    )


# =========================================================
# GET ALL EXPENSES
# =========================================================

@expenses_bp.route(
    "",
    methods=["GET"],
)
@login_required
def list_expenses():

    current_user = (
        get_current_user()
    )


    if not can_view_expenses(
        current_user
    ):

        return forbidden(
            "You do not have permission to view expenses."
        )


    # -----------------------------------------------------
    # Optional filters
    # -----------------------------------------------------

    category = request.args.get(
        "category"
    )

    start = request.args.get(
        "start"
    )

    end = request.args.get(
        "end"
    )


    query = (
        db_session
        .query(Expense)
    )


    # -----------------------------------------------------
    # CATEGORY FILTER
    # -----------------------------------------------------

    if category:

        query = (
            query.filter(
                Expense.category ==
                category
            )
        )


    # -----------------------------------------------------
    # DATE RANGE FILTER
    # -----------------------------------------------------

    if start:

        try:

            start_date = (
                datetime
                .fromisoformat(
                    start
                )
                .date()
            )

        except ValueError:

            return bad_request(
                "Invalid start date."
            )


        query = (
            query.filter(
                Expense.expense_date >=
                start_date
            )
        )


    if end:

        try:

            end_date = (
                datetime
                .fromisoformat(
                    end
                )
                .date()
            )

        except ValueError:

            return bad_request(
                "Invalid end date."
            )


        query = (
            query.filter(
                Expense.expense_date <=
                end_date
            )
        )


    # -----------------------------------------------------
    # FETCH
    # -----------------------------------------------------

    expenses = (

        query

        .order_by(
            Expense.expense_date.desc(),
            Expense.created_at.desc(),
        )

        .all()

    )


    return jsonify({

        "expenses": [

            serialize_expense(
                expense
            )

            for expense in expenses

        ],

        "total": len(
            expenses
        ),

    }), 200


# =========================================================
# CREATE EXPENSE
# =========================================================

@expenses_bp.route(
    "",
    methods=["POST"],
)
@login_required
def create_expense():

    current_user = (
        get_current_user()
    )


    if not can_manage_expenses(
        current_user
    ):

        return forbidden(
            "You do not have permission to create expenses."
        )


    data = (
        request.get_json(
            silent=True
        )
        or {}
    )


    # -----------------------------------------------------
    # READ VALUES
    # -----------------------------------------------------

    title = (
        data.get(
            "title"
        )
        or ""
    ).strip()


    category = (
        data.get(
            "category"
        )
        or ""
    ).strip()


    description = (
        data.get(
            "description"
        )
        or ""
    ).strip()


    amount = (
        data.get(
            "amount"
        )
    )


    expense_date_value = (
        data.get(
            "expense_date"
        )
    )


    # -----------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------

    if not title:

        return bad_request(
            "Expense title is required."
        )


    if not category:

        return bad_request(
            "Expense category is required."
        )


    if amount is None:

        return bad_request(
            "Expense amount is required."
        )


    try:

        amount = float(
            amount
        )

    except (
        TypeError,
        ValueError,
    ):

        return bad_request(
            "Expense amount must be a valid number."
        )


    if amount <= 0:

        return bad_request(
            "Expense amount must be greater than zero."
        )


    if not expense_date_value:

        expense_date = (
            date.today()
        )

    else:

        try:

            expense_date = (
                datetime
                .fromisoformat(
                    expense_date_value
                )
                .date()
            )

        except ValueError:

            return bad_request(
                "Invalid expense date."
            )


    # -----------------------------------------------------
    # CREATE EXPENSE
    # -----------------------------------------------------

    expense = Expense(

        title=title,

        category=category,

        description=(
            description
            if description
            else None
        ),

        amount=amount,

        expense_date=expense_date,

        created_by_id=(
            current_user.id
        ),

    )


    db_session.add(
        expense
    )


    # -----------------------------------------------------
    # ACTIVITY LOG
    # -----------------------------------------------------

    log_activity(

        user_id=(
            current_user.id
        ),

        action=(
            "CREATED_EXPENSE"
        ),

        details=(
            f"Created expense "
            f"'{title}' "
            f"({category}) "
            f"for {amount}"
        ),

    )


    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    db_session.commit()

    db_session.refresh(
        expense
    )


    return jsonify({

        "message":
            "Expense created successfully.",

        "expense":
            serialize_expense(
                expense
            ),

    }), 201


# =========================================================
# GET ONE EXPENSE
# =========================================================

@expenses_bp.route(
    "/<int:expense_id>",
    methods=["GET"],
)
@login_required
def get_expense(
    expense_id
):

    current_user = (
        get_current_user()
    )


    if not can_view_expenses(
        current_user
    ):

        return forbidden(
            "You do not have permission to view expenses."
        )


    expense = (

        db_session
        .query(Expense)
        .filter(
            Expense.id ==
            expense_id
        )
        .first()

    )


    if not expense:

        return not_found(
            "Expense not found."
        )


    return jsonify({

        "expense":
            serialize_expense(
                expense
            ),

    }), 200


# =========================================================
# UPDATE EXPENSE
# =========================================================

@expenses_bp.route(
    "/<int:expense_id>",
    methods=["PUT"],
)
@login_required
def update_expense(
    expense_id
):

    current_user = (
        get_current_user()
    )


    if not can_manage_expenses(
        current_user
    ):

        return forbidden(
            "You do not have permission to update expenses."
        )


    expense = (

        db_session
        .query(Expense)
        .filter(
            Expense.id ==
            expense_id
        )
        .first()

    )


    if not expense:

        return not_found(
            "Expense not found."
        )


    data = (
        request.get_json(
            silent=True
        )
        or {}
    )


    # -----------------------------------------------------
    # TITLE
    # -----------------------------------------------------

    if (
        "title"
        in data
    ):

        title = (
            data["title"]
            or ""
        ).strip()


        if not title:

            return bad_request(
                "Expense title cannot be empty."
            )


        expense.title = (
            title
        )


    # -----------------------------------------------------
    # CATEGORY
    # -----------------------------------------------------

    if (
        "category"
        in data
    ):

        category = (
            data["category"]
            or ""
        ).strip()


        if not category:

            return bad_request(
                "Expense category cannot be empty."
            )


        expense.category = (
            category
        )


    # -----------------------------------------------------
    # DESCRIPTION
    # -----------------------------------------------------

    if (
        "description"
        in data
    ):

        description = (
            data["description"]
            or ""
        ).strip()


        expense.description = (

            description
            if description
            else None

        )


    # -----------------------------------------------------
    # AMOUNT
    # -----------------------------------------------------

    if (
        "amount"
        in data
    ):

        try:

            amount = float(
                data["amount"]
            )

        except (
            TypeError,
            ValueError,
        ):

            return bad_request(
                "Expense amount must be a valid number."
            )


        if amount <= 0:

            return bad_request(
                "Expense amount must be greater than zero."
            )


        expense.amount = (
            amount
        )


    # -----------------------------------------------------
    # EXPENSE DATE
    # -----------------------------------------------------

    if (
        "expense_date"
        in data
    ):

        try:

            expense.expense_date = (

                datetime
                .fromisoformat(
                    data[
                        "expense_date"
                    ]
                )
                .date()

            )

        except (
            TypeError,
            ValueError,
        ):

            return bad_request(
                "Invalid expense date."
            )


    # -----------------------------------------------------
    # ACTIVITY LOG
    # -----------------------------------------------------

    log_activity(

        user_id=(
            current_user.id
        ),

        action=(
            "UPDATED_EXPENSE"
        ),

        details=(
            f"Updated expense "
            f"#{expense.id} "
            f"('{expense.title}')"
        ),

    )


    db_session.commit()

    db_session.refresh(
        expense
    )


    return jsonify({

        "message":
            "Expense updated successfully.",

        "expense":
            serialize_expense(
                expense
            ),

    }), 200


# =========================================================
# DELETE EXPENSE
# =========================================================

@expenses_bp.route(
    "/<int:expense_id>",
    methods=["DELETE"],
)
@login_required
def delete_expense(
    expense_id
):

    current_user = (
        get_current_user()
    )


    if not can_manage_expenses(
        current_user
    ):

        return forbidden(
            "You do not have permission to delete expenses."
        )


    expense = (

        db_session
        .query(Expense)
        .filter(
            Expense.id ==
            expense_id
        )
        .first()

    )


    if not expense:

        return not_found(
            "Expense not found."
        )


    # Save information before deletion

    expense_title = (
        expense.title
    )


    expense_amount = (
        expense.amount
    )


    db_session.delete(
        expense
    )


    # -----------------------------------------------------
    # ACTIVITY LOG
    # -----------------------------------------------------

    log_activity(

        user_id=(
            current_user.id
        ),

        action=(
            "DELETED_EXPENSE"
        ),

        details=(
            f"Deleted expense "
            f"'{expense_title}' "
            f"({expense_amount})"
        ),

    )


    db_session.commit()


    return jsonify({

        "message":
            "Expense deleted successfully."

    }), 200


# =========================================================
# EXPENSE SUMMARY
# =========================================================

@expenses_bp.route(
    "/summary",
    methods=["GET"],
)
@login_required
def expense_summary():

    current_user = (
        get_current_user()
    )


    if not can_view_expenses(
        current_user
    ):

        return forbidden(
            "You do not have permission to view expense summaries."
        )


    today = (
        date.today()
    )


    # -----------------------------------------------------
    # TODAY
    # -----------------------------------------------------

    today_total = (

        db_session
        .query(
            func.coalesce(
                func.sum(
                    Expense.amount
                ),
                0,
            )
        )
        .filter(
            Expense.expense_date ==
            today
        )
        .scalar()

    )


    # -----------------------------------------------------
    # MONTH
    # -----------------------------------------------------

    month_start = (
        today.replace(
            day=1
        )
    )


    month_total = (

        db_session
        .query(
            func.coalesce(
                func.sum(
                    Expense.amount
                ),
                0,
            )
        )
        .filter(
            Expense.expense_date >=
            month_start,

            Expense.expense_date <=
            today,
        )
        .scalar()

    )


    # -----------------------------------------------------
    # ALL TIME
    # -----------------------------------------------------

    all_time_total = (

        db_session
        .query(
            func.coalesce(
                func.sum(
                    Expense.amount
                ),
                0,
            )
        )
        .scalar()

    )


    # -----------------------------------------------------
    # NUMBER OF EXPENSES
    # -----------------------------------------------------

    total_expenses = (

        db_session
        .query(
            func.count(
                Expense.id
            )
        )
        .scalar()

    )


    return jsonify({

        "today":
            float(
                today_total
            ),

        "this_month":
            float(
                month_total
            ),

        "all_time":
            float(
                all_time_total
            ),

        "total_expenses":
            total_expenses,

    }), 200