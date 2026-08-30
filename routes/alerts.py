from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify

from extensions import db_session
from models import Medicine, Sale
from services.permission_service import login_required
from serializers import serialize_medicine

alerts_bp = Blueprint("alerts", __name__)

EXPIRY_WARNING_DAYS = 30


@alerts_bp.get("/low-stock")
@login_required
def low_stock():
    """Between critical_stock and minimum_stock — not yet critical."""
    meds = (
        db_session.query(Medicine)
        .filter(
            Medicine.status == "Active",
            Medicine.quantity > 0,
            Medicine.quantity <= Medicine.minimum_stock,
            Medicine.quantity > Medicine.critical_stock,
        )
        .order_by(Medicine.quantity)
        .all()
    )

    return jsonify(
        {"medicines": [serialize_medicine(m) for m in meds]}
    ), 200


@alerts_bp.get("/critical-stock")
@login_required
def critical_stock():
    meds = (
        db_session.query(Medicine)
        .filter(
            Medicine.status == "Active",
            Medicine.quantity > 0,
            Medicine.quantity <= Medicine.critical_stock,
        )
        .order_by(Medicine.quantity)
        .all()
    )

    return jsonify(
        {"medicines": [serialize_medicine(m) for m in meds]}
    ), 200


@alerts_bp.get("/out-of-stock")
@login_required
def out_of_stock():
    meds = (
        db_session.query(Medicine)
        .filter(
            Medicine.status == "Active",
            Medicine.quantity == 0,
        )
        .order_by(Medicine.generic_name)
        .all()
    )

    return jsonify(
        {"medicines": [serialize_medicine(m) for m in meds]}
    ), 200


@alerts_bp.get("/expired")
@login_required
def expired():
    today = datetime.now(ZoneInfo("Africa/Kigali")).date()

    meds = (
        db_session.query(Medicine)
        .filter(Medicine.expiry_date < today)
        .order_by(Medicine.expiry_date)
        .all()
    )

    return jsonify(
        {"medicines": [serialize_medicine(m) for m in meds]}
    ), 200


@alerts_bp.get("/expiring-soon")
@login_required
def expiring_soon():
    today = datetime.now(ZoneInfo("Africa/Kigali")).date()
    warning = today + timedelta(days=EXPIRY_WARNING_DAYS)

    meds = (
        db_session.query(Medicine)
        .filter(
            Medicine.expiry_date >= today,
            Medicine.expiry_date <= warning,
        )
        .order_by(Medicine.expiry_date)
        .all()
    )

    return jsonify(
        {"medicines": [serialize_medicine(m) for m in meds]}
    ), 200


@alerts_bp.get("/dashboard")
@login_required
def dashboard():
    # -------------------------------------------------------------
    # Use Rwanda time for "today"
    # -------------------------------------------------------------
    rwanda_now = datetime.now(ZoneInfo("Africa/Kigali"))

    today = rwanda_now.date()

    # Midnight at the beginning of today in Rwanda
    start_of_today = rwanda_now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    # Midnight at the beginning of tomorrow in Rwanda
    start_of_tomorrow = start_of_today + timedelta(days=1)

    warning = today + timedelta(days=EXPIRY_WARNING_DAYS)

    # -------------------------------------------------------------
    # Stock counts
    # -------------------------------------------------------------

    low_stock_count = (
        db_session.query(Medicine)
        .filter(
            Medicine.status == "Active",
            Medicine.quantity > 0,
            Medicine.quantity <= Medicine.minimum_stock,
        )
        .count()
    )

    critical_count = (
        db_session.query(Medicine)
        .filter(
            Medicine.status == "Active",
            Medicine.quantity > 0,
            Medicine.quantity <= Medicine.critical_stock,
        )
        .count()
    )

    out_count = (
        db_session.query(Medicine)
        .filter(
            Medicine.status == "Active",
            Medicine.quantity == 0,
        )
        .count()
    )

    # -------------------------------------------------------------
    # Expiry counts
    # -------------------------------------------------------------

    expiring_count = (
        db_session.query(Medicine)
        .filter(
            Medicine.expiry_date >= today,
            Medicine.expiry_date <= warning,
        )
        .count()
    )

    expired_count = (
        db_session.query(Medicine)
        .filter(
            Medicine.expiry_date < today,
        )
        .count()
    )

    # -------------------------------------------------------------
    # Today's sales
    #
    # IMPORTANT:
    # Use a Rwanda-time range rather than:
    #
    #     Sale.sale_date >= today
    #
    # This prevents UTC/Rwanda timezone differences from causing
    # today's sales to disappear from the dashboard.
    # -------------------------------------------------------------

    todays_sales = (
        db_session.query(Sale)
        .filter(
            Sale.sale_date >= start_of_today,
            Sale.sale_date < start_of_tomorrow,
        )
        .all()
    )

    revenue = sum(
        float(s.total_amount)
        for s in todays_sales
    )

    # -------------------------------------------------------------
    # Dashboard response
    # -------------------------------------------------------------

    return jsonify({
        "low_stock": low_stock_count,
        "critical_stock": critical_count,
        "out_of_stock": out_count,
        "expiring_soon": expiring_count,
        "expired": expired_count,
        "todays_revenue": revenue,
        "todays_transactions": len(todays_sales),
    }), 200