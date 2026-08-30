"""
Report access split:

- inventory / sales-by-period (daily, weekly, monthly, yearly, custom
  range) / best-selling / lowest-selling / expired-medicines: both roles.
  None of these expose cost or profit figures.
- purchase report and profit report: Admin only.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from flask import Blueprint, request, jsonify
from sqlalchemy import func as sa_func

from extensions import db_session
from models import Medicine, Sale, SaleItem
from services.permission_service import login_required, require_role
from utils import error_response

reports_bp = Blueprint("reports", __name__)

RWANDA_TZ = ZoneInfo("Africa/Kigali")


@reports_bp.get("/inventory")
@login_required
def inventory_report():
    meds = db_session.query(Medicine).filter(
        Medicine.status == "Active"
    ).all()

    total_items = sum(m.quantity for m in meds)
    selling_value = sum(
        float(m.selling_price) * m.quantity
        for m in meds
    )

    return jsonify({
        "different_medicines": len(meds),
        "total_items": total_items,
        "selling_value": selling_value,
    }), 200


@reports_bp.get("/purchase")
@require_role("Admin")
def purchase_report():
    meds = db_session.query(Medicine).filter(
        Medicine.status == "Active"
    ).all()

    purchase_value = sum(
        float(m.purchase_price) * m.quantity
        for m in meds
    )

    return jsonify({
        "different_medicines": len(meds),
        "purchase_value": purchase_value,
    }), 200


@reports_bp.get("/profit")
@require_role("Admin")
def profit_report():
    meds = db_session.query(Medicine).filter(
        Medicine.status == "Active"
    ).all()

    purchase_value = sum(
        float(m.purchase_price) * m.quantity
        for m in meds
    )

    selling_value = sum(
        float(m.selling_price) * m.quantity
        for m in meds
    )

    expected_inventory_profit = selling_value - purchase_value

    realized_profit = (
        db_session.query(
            sa_func.coalesce(
                sa_func.sum(Sale.total_profit),
                0
            )
        ).scalar()
    )

    return jsonify({
        "expected_inventory_profit": expected_inventory_profit,
        "realized_profit_all_time": float(realized_profit),
    }), 200


# =========================================================
# SALES REPORT HELPERS
# =========================================================

def _sales_summary(start=None, end=None):
    query = db_session.query(Sale)

    if start:
        query = query.filter(Sale.sale_date >= start)

    if end:
        query = query.filter(Sale.sale_date < end)

    sales = query.all()

    return {
        "transactions": len(sales),
        "revenue": sum(
            float(s.total_amount)
            for s in sales
        ),
    }


def _rwanda_today_range():
    """
    Return the beginning of today and the beginning of tomorrow
    using Rwanda/Kigali time.

    This matches the Dashboard's definition of "today".
    """

    rwanda_now = datetime.now(RWANDA_TZ)

    start_of_today = rwanda_now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    start_of_tomorrow = start_of_today + timedelta(days=1)

    return start_of_today, start_of_tomorrow


# =========================================================
# SALES — DAILY
# =========================================================

@reports_bp.get("/sales/daily")
@login_required
def daily_sales():

    start_of_today, start_of_tomorrow = _rwanda_today_range()

    return jsonify(
        _sales_summary(
            start=start_of_today,
            end=start_of_tomorrow,
        )
    ), 200


# =========================================================
# SALES — WEEKLY
# =========================================================

@reports_bp.get("/sales/weekly")
@login_required
def weekly_sales():

    rwanda_now = datetime.now(RWANDA_TZ)

    today = rwanda_now.date()

    start_date = today - timedelta(
        days=today.weekday()
    )

    start = datetime.combine(
        start_date,
        datetime.min.time(),
        tzinfo=RWANDA_TZ,
    )

    end = start + timedelta(days=7)

    return jsonify(
        _sales_summary(
            start=start,
            end=end,
        )
    ), 200


# =========================================================
# SALES — MONTHLY
# =========================================================

@reports_bp.get("/sales/monthly")
@login_required
def monthly_sales():

    rwanda_now = datetime.now(RWANDA_TZ)

    today = rwanda_now.date()

    start_date = today.replace(day=1)

    start = datetime.combine(
        start_date,
        datetime.min.time(),
        tzinfo=RWANDA_TZ,
    )

    if start_date.month == 12:
        next_month = start_date.replace(
            year=start_date.year + 1,
            month=1,
            day=1,
        )
    else:
        next_month = start_date.replace(
            month=start_date.month + 1,
            day=1,
        )

    end = datetime.combine(
        next_month,
        datetime.min.time(),
        tzinfo=RWANDA_TZ,
    )

    return jsonify(
        _sales_summary(
            start=start,
            end=end,
        )
    ), 200


# =========================================================
# SALES — YEARLY
# =========================================================

@reports_bp.get("/sales/yearly")
@login_required
def yearly_sales():

    rwanda_now = datetime.now(RWANDA_TZ)

    today = rwanda_now.date()

    start_date = today.replace(
        month=1,
        day=1,
    )

    end_date = start_date.replace(
        year=start_date.year + 1,
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

    return jsonify(
        _sales_summary(
            start=start,
            end=end,
        )
    ), 200


# =========================================================
# SALES — CUSTOM RANGE
# =========================================================

@reports_bp.get("/sales/range")
@login_required
def range_sales():

    start_str = request.args.get("start")
    end_str = request.args.get("end")

    if not start_str or not end_str:
        return error_response(
            "start and end (YYYY-MM-DD) are required."
        )

    try:
        start_date = datetime.strptime(
            start_str,
            "%Y-%m-%d"
        ).date()

        end_date = datetime.strptime(
            end_str,
            "%Y-%m-%d"
        ).date()

    except ValueError:
        return error_response(
            "start/end must be in YYYY-MM-DD format."
        )

    start = datetime.combine(
        start_date,
        datetime.min.time(),
        tzinfo=RWANDA_TZ,
    )

    end = datetime.combine(
        end_date + timedelta(days=1),
        datetime.min.time(),
        tzinfo=RWANDA_TZ,
    )

    return jsonify(
        _sales_summary(
            start=start,
            end=end,
        )
    ), 200


# =========================================================
# BEST SELLING
# =========================================================

@reports_bp.get("/best-selling")
@login_required
def best_selling():

    rows = (
        db_session.query(
            Medicine.generic_name,
            sa_func.sum(
                SaleItem.quantity
            ).label("sold")
        )
        .join(
            SaleItem,
            SaleItem.medicine_id == Medicine.id
        )
        .group_by(Medicine.generic_name)
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
                "generic_name": r[0],
                "quantity_sold": int(r[1]),
            }
            for r in rows
        ]
    }), 200


# =========================================================
# LOWEST SELLING
# =========================================================

@reports_bp.get("/lowest-selling")
@login_required
def lowest_selling():

    rows = (
        db_session.query(
            Medicine.generic_name,
            sa_func.sum(
                SaleItem.quantity
            ).label("sold")
        )
        .join(
            SaleItem,
            SaleItem.medicine_id == Medicine.id
        )
        .group_by(Medicine.generic_name)
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
                "generic_name": r[0],
                "quantity_sold": int(r[1]),
            }
            for r in rows
        ]
    }), 200


# =========================================================
# EXPIRED MEDICINES
# =========================================================

@reports_bp.get("/expired-medicines")
@login_required
def expired_medicines_report():

    today = datetime.now(
        RWANDA_TZ
    ).date()

    meds = (
        db_session.query(Medicine)
        .filter(
            Medicine.expiry_date < today
        )
        .order_by(
            Medicine.expiry_date
        )
        .all()
    )

    return jsonify({
        "medicines": [
            {
                "generic_name": m.generic_name,
                "expiry_date": m.expiry_date.isoformat(),
                "quantity": m.quantity,
            }
            for m in meds
        ]
    }), 200