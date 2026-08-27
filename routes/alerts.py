from datetime import date, timedelta

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
    return jsonify({"medicines": [serialize_medicine(m) for m in meds]}), 200


@alerts_bp.get("/critical-stock")
@login_required
def critical_stock():
    meds = (
        db_session.query(Medicine)
        .filter(Medicine.status == "Active", Medicine.quantity > 0, Medicine.quantity <= Medicine.critical_stock)
        .order_by(Medicine.quantity)
        .all()
    )
    return jsonify({"medicines": [serialize_medicine(m) for m in meds]}), 200


@alerts_bp.get("/out-of-stock")
@login_required
def out_of_stock():
    meds = (
        db_session.query(Medicine)
        .filter(Medicine.status == "Active", Medicine.quantity == 0)
        .order_by(Medicine.generic_name)
        .all()
    )
    return jsonify({"medicines": [serialize_medicine(m) for m in meds]}), 200


@alerts_bp.get("/expired")
@login_required
def expired():
    today = date.today()
    meds = db_session.query(Medicine).filter(Medicine.expiry_date < today).order_by(Medicine.expiry_date).all()
    return jsonify({"medicines": [serialize_medicine(m) for m in meds]}), 200


@alerts_bp.get("/expiring-soon")
@login_required
def expiring_soon():
    today = date.today()
    warning = today + timedelta(days=EXPIRY_WARNING_DAYS)
    meds = (
        db_session.query(Medicine)
        .filter(Medicine.expiry_date >= today, Medicine.expiry_date <= warning)
        .order_by(Medicine.expiry_date)
        .all()
    )
    return jsonify({"medicines": [serialize_medicine(m) for m in meds]}), 200


@alerts_bp.get("/dashboard")
@login_required
def dashboard():
    today = date.today()
    warning = today + timedelta(days=EXPIRY_WARNING_DAYS)

    low_stock_count = db_session.query(Medicine).filter(
        Medicine.status == "Active", Medicine.quantity > 0, Medicine.quantity <= Medicine.minimum_stock,
    ).count()
    critical_count = db_session.query(Medicine).filter(
        Medicine.status == "Active", Medicine.quantity > 0, Medicine.quantity <= Medicine.critical_stock,
    ).count()
    out_count = db_session.query(Medicine).filter(
        Medicine.status == "Active", Medicine.quantity == 0,
    ).count()
    expiring_count = db_session.query(Medicine).filter(
        Medicine.expiry_date >= today, Medicine.expiry_date <= warning,
    ).count()
    expired_count = db_session.query(Medicine).filter(Medicine.expiry_date < today).count()

    todays_sales = db_session.query(Sale).filter(Sale.sale_date >= today).all()
    revenue = sum(float(s.total_amount) for s in todays_sales)

    return jsonify({
        "low_stock": low_stock_count,
        "critical_stock": critical_count,
        "out_of_stock": out_count,
        "expiring_soon": expiring_count,
        "expired": expired_count,
        "todays_revenue": revenue,
        "todays_transactions": len(todays_sales),
    }), 200
