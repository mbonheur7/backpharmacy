"""
Report access split:

- inventory / sales-by-period / best-selling /
  lowest-selling / expired-medicines:
  available to logged-in users.

- purchase report and profit report:
  Super Admin and Admin Viewer only.

Sales reports now include:

- gross revenue
- expenses
- net revenue

Net revenue:

    gross revenue - expenses

Breakdowns:

- daily   -> one day
- weekly  -> Monday through Sunday
- monthly -> day by day
- yearly  -> month by month
- custom  -> day by day
"""

from datetime import (
    datetime,
    timedelta,
)

from zoneinfo import (
    ZoneInfo,
)

from flask import (
    Blueprint,
    request,
    jsonify,
)

from sqlalchemy import (
    func as sa_func,
)

from extensions import (
    db_session,
)

from models import (
    Medicine,
    Sale,
    SaleItem,
    Expense,
)

from services.permission_service import (
    login_required,
    require_role,
)

from utils import (
    error_response,
)


reports_bp = Blueprint(
    "reports",
    __name__,
)


RWANDA_TZ = ZoneInfo(
    "Africa/Kigali"
)


# =========================================================
# INVENTORY REPORT
# =========================================================

@reports_bp.get(
    "/inventory"
)
@login_required
def inventory_report():

    meds = (
        db_session.query(
            Medicine
        )
        .filter(
            Medicine.status
            == "Active"
        )
        .all()
    )

    total_items = sum(
        m.quantity
        for m in meds
    )

    selling_value = sum(
        float(
            m.selling_price
        )
        * m.quantity
        for m in meds
    )

    return jsonify({

        "different_medicines": (
            len(meds)
        ),

        "total_items": (
            total_items
        ),

        "selling_value": (
            selling_value
        ),

    }), 200


# =========================================================
# PURCHASE REPORT
# =========================================================

@reports_bp.get(
    "/purchase"
)
@require_role(
    "Super Admin",
    "Admin Viewer",
)
def purchase_report():

    meds = (
        db_session.query(
            Medicine
        )
        .filter(
            Medicine.status
            == "Active"
        )
        .all()
    )

    purchase_value = sum(
        float(
            m.purchase_price
        )
        * m.quantity
        for m in meds
    )

    return jsonify({

        "different_medicines": (
            len(meds)
        ),

        "purchase_value": (
            purchase_value
        ),

    }), 200


# =========================================================
# PROFIT REPORT
# =========================================================

@reports_bp.get(
    "/profit"
)
@require_role(
    "Super Admin",
    "Admin Viewer",
)
def profit_report():

    meds = (
        db_session.query(
            Medicine
        )
        .filter(
            Medicine.status
            == "Active"
        )
        .all()
    )

    purchase_value = sum(
        float(
            m.purchase_price
        )
        * m.quantity
        for m in meds
    )

    selling_value = sum(
        float(
            m.selling_price
        )
        * m.quantity
        for m in meds
    )

    expected_inventory_profit = (
        selling_value
        - purchase_value
    )

    realized_profit = (
        db_session.query(
            sa_func.coalesce(
                sa_func.sum(
                    Sale.total_profit
                ),
                0,
            )
        )
        .scalar()
    )

    return jsonify({

        "expected_inventory_profit": (
            expected_inventory_profit
        ),

        "realized_profit_all_time": (
            float(
                realized_profit
            )
        ),

    }), 200


# =========================================================
# TIME HELPERS
# =========================================================

def _to_rwanda_time(
    value
):
    """
    Convert a database date/datetime into Rwanda time.

    Handles both:
    - datetime values from Sale.sale_date
    - date values from Expense.expense_date
    """

    # -----------------------------------------------------
    # Expense dates may be plain datetime.date objects.
    # Convert them to a datetime at midnight in Rwanda.
    # -----------------------------------------------------

    if (
        not isinstance(
            value,
            datetime,
        )
    ):

        return datetime.combine(
            value,
            datetime.min.time(),
            tzinfo=RWANDA_TZ,
        )

    # -----------------------------------------------------
    # Datetime values
    # -----------------------------------------------------

    if value.tzinfo is None:

        return value.replace(
            tzinfo=RWANDA_TZ
        )

    return value.astimezone(
        RWANDA_TZ
    )


def _rwanda_today_range():
    """
    Beginning of today and beginning of tomorrow
    using Africa/Kigali time.
    """

    rwanda_now = datetime.now(
        RWANDA_TZ
    )

    start_of_today = (
        rwanda_now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
    )

    start_of_tomorrow = (
        start_of_today
        + timedelta(days=1)
    )

    return (
        start_of_today,
        start_of_tomorrow,
    )


# =========================================================
# SALES + EXPENSES SUMMARY
# =========================================================

def _period_summary(
    start,
    end,
):
    """
    Returns the financial reality for a period.

    Sales are never changed by expenses.

    gross_revenue:
        total money from medicine sales

    expenses:
        total money recorded as expenses

    net_revenue:
        gross_revenue - expenses
    """

    sales = (
        db_session.query(
            Sale
        )
        .filter(
            Sale.sale_date >= start
        )
        .filter(
            Sale.sale_date < end
        )
        .all()
    )

    expenses = (
        db_session.query(
            Expense
        )
        .filter(
            Expense.expense_date >= start
        )
        .filter(
            Expense.expense_date < end
        )
        .all()
    )

    gross_revenue = sum(
        float(
            sale.total_amount
        )
        for sale in sales
    )

    total_expenses = sum(
        float(
            expense.amount
        )
        for expense in expenses
    )

    net_revenue = (
        gross_revenue
        - total_expenses
    )

    return {

        "transactions": (
            len(sales)
        ),

        "gross_revenue": (
            gross_revenue
        ),

        "expenses": (
            total_expenses
        ),

        "net_revenue": (
            net_revenue
        ),

        # Backwards compatibility.
        #
        # "revenue" now represents the
        # actual money remaining after expenses.
        "revenue": (
            net_revenue
        ),
    }


# =========================================================
# DAILY BREAKDOWN
# =========================================================

def _daily_breakdown(
    start,
    end,
):
    """
    Creates one entry per day.

    Used by:
    - Today
    - This week
    - This month
    - Custom range
    """

    buckets = {}

    current = (
        start.date()
    )

    end_date = (
        end.date()
    )

    while current < end_date:

        buckets[
            current.isoformat()
        ] = {

            "date": (
                current.isoformat()
            ),

            "label": (
                current.strftime(
                    "%A"
                )
            ),

            "transactions": 0,

            "gross_revenue": 0.0,

            "expenses": 0.0,

            "net_revenue": 0.0,

        }

        current = (
            current
            + timedelta(days=1)
        )

    sales = (
        db_session.query(
            Sale
        )
        .filter(
            Sale.sale_date >= start
        )
        .filter(
            Sale.sale_date < end
        )
        .all()
    )

    expenses = (
        db_session.query(
            Expense
        )
        .filter(
            Expense.expense_date >= start
        )
        .filter(
            Expense.expense_date < end
        )
        .all()
    )

    # -----------------------------------------------------
    # Add sales
    # -----------------------------------------------------

    for sale in sales:

        sale_time = (
            _to_rwanda_time(
                sale.sale_date
            )
        )

        key = (
            sale_time.date()
            .isoformat()
        )

        if key in buckets:

            buckets[key][
                "transactions"
            ] += 1

            buckets[key][
                "gross_revenue"
            ] += float(
                sale.total_amount
            )

    # -----------------------------------------------------
    # Add expenses
    # -----------------------------------------------------

    for expense in expenses:

        expense_time = (
            _to_rwanda_time(
                expense.expense_date
            )
        )

        key = (
            expense_time.date()
            .isoformat()
        )

        if key in buckets:

            buckets[key][
                "expenses"
            ] += float(
                expense.amount
            )

    # -----------------------------------------------------
    # Calculate net revenue
    # -----------------------------------------------------

    results = []

    for bucket in (
        buckets.values()
    ):

        bucket[
            "net_revenue"
        ] = (
            bucket[
                "gross_revenue"
            ]
            - bucket[
                "expenses"
            ]
        )

        results.append(
            bucket
        )

    return results


# =========================================================
# YEARLY MONTHLY BREAKDOWN
# =========================================================

def _monthly_breakdown(
    start,
    end,
):
    """
    Creates one entry per month.

    Used by the yearly report.
    """

    buckets = {}

    current = (
        start.replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
    )

    while current < end:

        key = (
            current.strftime(
                "%Y-%m"
            )
        )

        buckets[key] = {

            "month": (
                key
            ),

            "label": (
                current.strftime(
                    "%B"
                )
            ),

            "transactions": 0,

            "gross_revenue": 0.0,

            "expenses": 0.0,

            "net_revenue": 0.0,

        }

        if current.month == 12:

            current = current.replace(
                year=current.year + 1,
                month=1,
            )

        else:

            current = current.replace(
                month=current.month + 1
            )

    sales = (
        db_session.query(
            Sale
        )
        .filter(
            Sale.sale_date >= start
        )
        .filter(
            Sale.sale_date < end
        )
        .all()
    )

    expenses = (
        db_session.query(
            Expense
        )
        .filter(
            Expense.expense_date >= start
        )
        .filter(
            Expense.expense_date < end
        )
        .all()
    )

    # -----------------------------------------------------
    # Sales
    # -----------------------------------------------------

    for sale in sales:

        sale_time = (
            _to_rwanda_time(
                sale.sale_date
            )
        )

        key = (
            sale_time.strftime(
                "%Y-%m"
            )
        )

        if key in buckets:

            buckets[key][
                "transactions"
            ] += 1

            buckets[key][
                "gross_revenue"
            ] += float(
                sale.total_amount
            )

    # -----------------------------------------------------
    # Expenses
    # -----------------------------------------------------

    for expense in expenses:

        expense_time = (
            _to_rwanda_time(
                expense.expense_date
            )
        )

        key = (
            expense_time.strftime(
                "%Y-%m"
            )
        )

        if key in buckets:

            buckets[key][
                "expenses"
            ] += float(
                expense.amount
            )

    # -----------------------------------------------------
    # Net revenue
    # -----------------------------------------------------

    results = []

    for bucket in (
        buckets.values()
    ):

        bucket[
            "net_revenue"
        ] = (
            bucket[
                "gross_revenue"
            ]
            - bucket[
                "expenses"
            ]
        )

        results.append(
            bucket
        )

    return results


# =========================================================
# SALES — TODAY
# =========================================================

@reports_bp.get(
    "/sales/daily"
)
@login_required
def daily_sales():

    (
        start_of_today,
        start_of_tomorrow,
    ) = (
        _rwanda_today_range()
    )

    summary = (
        _period_summary(
            start_of_today,
            start_of_tomorrow,
        )
    )

    summary[
        "breakdown"
    ] = (
        _daily_breakdown(
            start_of_today,
            start_of_tomorrow,
        )
    )

    return jsonify(
        summary
    ), 200


# =========================================================
# SALES — THIS WEEK
#
# Monday -> Sunday
# =========================================================

@reports_bp.get(
    "/sales/weekly"
)
@login_required
def weekly_sales():

    rwanda_now = datetime.now(
        RWANDA_TZ
    )

    today = (
        rwanda_now.date()
    )

    start_date = (
        today
        - timedelta(
            days=today.weekday()
        )
    )

    start = datetime.combine(
        start_date,
        datetime.min.time(),
        tzinfo=RWANDA_TZ,
    )

    end = (
        start
        + timedelta(days=7)
    )

    summary = (
        _period_summary(
            start,
            end,
        )
    )

    summary[
        "breakdown"
    ] = (
        _daily_breakdown(
            start,
            end,
        )
    )

    return jsonify(
        summary
    ), 200


# =========================================================
# SALES — THIS MONTH
#
# Day-by-day breakdown
# =========================================================

@reports_bp.get(
    "/sales/monthly"
)
@login_required
def monthly_sales():

    rwanda_now = datetime.now(
        RWANDA_TZ
    )

    today = (
        rwanda_now.date()
    )

    start_date = (
        today.replace(
            day=1
        )
    )

    start = datetime.combine(
        start_date,
        datetime.min.time(),
        tzinfo=RWANDA_TZ,
    )

    if start_date.month == 12:

        next_month = (
            start_date.replace(
                year=(
                    start_date.year
                    + 1
                ),
                month=1,
                day=1,
            )
        )

    else:

        next_month = (
            start_date.replace(
                month=(
                    start_date.month
                    + 1
                ),
                day=1,
            )
        )

    end = datetime.combine(
        next_month,
        datetime.min.time(),
        tzinfo=RWANDA_TZ,
    )

    summary = (
        _period_summary(
            start,
            end,
        )
    )

    summary[
        "breakdown"
    ] = (
        _daily_breakdown(
            start,
            end,
        )
    )

    return jsonify(
        summary
    ), 200


# =========================================================
# SALES — THIS YEAR
#
# Month-by-month breakdown
# =========================================================

@reports_bp.get(
    "/sales/yearly"
)
@login_required
def yearly_sales():

    rwanda_now = datetime.now(
        RWANDA_TZ
    )

    today = (
        rwanda_now.date()
    )

    start_date = (
        today.replace(
            month=1,
            day=1,
        )
    )

    end_date = (
        start_date.replace(
            year=(
                start_date.year
                + 1
            )
        )
    )

    start = datetime.combine(
        start_date,
        datetime.min.time(),
        tzinfo=RWANDA_TZ,
    )

    end = datetime.combine(
        end_date,
        datetime.min.time(),
        tzinfo=RWANDA_TZ,
    )

    summary = (
        _period_summary(
            start,
            end,
        )
    )

    summary[
        "breakdown"
    ] = (
        _monthly_breakdown(
            start,
            end,
        )
    )

    return jsonify(
        summary
    ), 200


# =========================================================
# SALES — CUSTOM RANGE
#
# Day-by-day breakdown
# =========================================================

@reports_bp.get(
    "/sales/range"
)
@login_required
def range_sales():

    start_str = request.args.get(
        "start"
    )

    end_str = request.args.get(
        "end"
    )

    if (
        not start_str
        or not end_str
    ):

        return error_response(
            "start and end "
            "(YYYY-MM-DD) "
            "are required."
        )

    try:

        start_date = (
            datetime.strptime(
                start_str,
                "%Y-%m-%d",
            ).date()
        )

        end_date = (
            datetime.strptime(
                end_str,
                "%Y-%m-%d",
            ).date()
        )

    except ValueError:

        return error_response(
            "start/end must be in "
            "YYYY-MM-DD format."
        )

    if end_date < start_date:

        return error_response(
            "end date cannot be before start date."
        )

    start = datetime.combine(
        start_date,
        datetime.min.time(),
        tzinfo=RWANDA_TZ,
    )

    end = datetime.combine(
        (
            end_date
            + timedelta(days=1)
        ),
        datetime.min.time(),
        tzinfo=RWANDA_TZ,
    )

    summary = (
        _period_summary(
            start,
            end,
        )
    )

    summary[
        "breakdown"
    ] = (
        _daily_breakdown(
            start,
            end,
        )
    )

    return jsonify(
        summary
    ), 200


# =========================================================
# BEST SELLING
# =========================================================

@reports_bp.get(
    "/best-selling"
)
@login_required
def best_selling():

    rows = (
        db_session.query(

            Medicine.generic_name,

            sa_func.sum(
                SaleItem.quantity
            ).label(
                "sold"
            ),

        )

        .join(
            SaleItem,
            SaleItem.medicine_id
            == Medicine.id,
        )

        .group_by(
            Medicine.generic_name
        )

        .order_by(
            sa_func.sum(
                SaleItem.quantity
            ).desc()
        )

        .limit(10)

        .all()
    )

    return jsonify({

        "medicines": [

            {

                "generic_name": (
                    row[0]
                ),

                "quantity_sold": (
                    int(
                        row[1]
                    )
                ),

            }

            for row in rows

        ]

    }), 200


# =========================================================
# LOWEST SELLING
# =========================================================

@reports_bp.get(
    "/lowest-selling"
)
@login_required
def lowest_selling():

    rows = (
        db_session.query(

            Medicine.generic_name,

            sa_func.sum(
                SaleItem.quantity
            ).label(
                "sold"
            ),

        )

        .join(
            SaleItem,
            SaleItem.medicine_id
            == Medicine.id,
        )

        .group_by(
            Medicine.generic_name
        )

        .order_by(
            sa_func.sum(
                SaleItem.quantity
            ).asc()
        )

        .limit(10)

        .all()
    )

    return jsonify({

        "medicines": [

            {

                "generic_name": (
                    row[0]
                ),

                "quantity_sold": (
                    int(
                        row[1]
                    )
                ),

            }

            for row in rows

        ]

    }), 200


# =========================================================
# EXPIRED MEDICINES
# =========================================================

@reports_bp.get(
    "/expired-medicines"
)
@login_required
def expired_medicines_report():

    today = datetime.now(
        RWANDA_TZ
    ).date()

    meds = (
        db_session.query(
            Medicine
        )

        .filter(
            Medicine.expiry_date
            < today
        )

        .order_by(
            Medicine.expiry_date
        )

        .all()
    )

    return jsonify({

        "medicines": [

            {

                "generic_name": (
                    medicine.generic_name
                ),

                "expiry_date": (
                    medicine.expiry_date
                    .isoformat()
                ),

                "quantity": (
                    medicine.quantity
                ),

            }

            for medicine in meds

        ]

    }), 200