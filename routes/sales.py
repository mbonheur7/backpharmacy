from datetime import date, datetime, timedelta

from flask import Blueprint, request, jsonify
from sqlalchemy import desc

from extensions import db_session
from models import Medicine, Sale, SaleItem
from services.permission_service import (
    login_required,
    require_role,
    get_current_user,
)
from services.stock_service import adjust_stock, StockError
from services.activity_log_service import log_activity
from serializers import serialize_sale
from utils import error_response, generate_receipt_number


sales_bp = Blueprint("sales", __name__)


def _strict_integer(value):
    """
    Return True only for real JSON integers.

    Rejects:
        True
        False
        2.5
        "2"
    """
    return isinstance(value, int) and not isinstance(value, bool)


@sales_bp.post("")
@require_role("Super Admin", "Pharmacist")
def checkout():
    """
    All-or-nothing checkout.

    Every line is validated before anything is written:
    - items must be a non-empty list
    - medicine must exist
    - medicine must be Active
    - medicine must not be expired
    - medicine must have stock
    - quantity must be a positive integer
    - the same medicine cannot appear more than once
    - enough stock must be available

    Nothing is committed until all validation succeeds.
    """
    data = request.get_json(silent=True) or {}

    items = data.get("items")

    if not items or not isinstance(items, list):
        return error_response(
            "A non-empty list of items is required."
        )

    user = get_current_user()
    today = date.today()

    resolved = []
    seen_medicine_ids = set()

    # -------------------------------------------------------------
    # Validate every cart line before writing anything
    # -------------------------------------------------------------

    for raw in items:

        if not isinstance(raw, dict):
            return error_response(
                "Each item must be an object."
            )

        medicine_id = raw.get("medicine_id")

        # Medicine IDs must be real integers, not strings/bools.
        if not _strict_integer(medicine_id):
            return error_response(
                "medicine_id must be a whole number."
            )

        # Prevent duplicate medicine lines in one sale.
        if medicine_id in seen_medicine_ids:
            return error_response(
                f"Medicine {medicine_id} appears more than once in the sale."
            )

        seen_medicine_ids.add(medicine_id)

        quantity = raw.get("quantity")

        # Quantity must be a real integer, not "2", 2.5, True, etc.
        if not _strict_integer(quantity):
            return error_response(
                "Each item needs a whole-number quantity."
            )

        if quantity <= 0:
            return error_response(
                "Quantity must be greater than zero for every item."
            )

        medicine = db_session.query(Medicine).get(medicine_id)

        if not medicine:
            return error_response(
                f"Medicine {medicine_id} not found.",
                404,
            )

        if medicine.status == "Discontinued":
            return error_response(
                f"{medicine.generic_name} is discontinued and cannot be sold."
            )

        if medicine.expiry_date and medicine.expiry_date < today:
            return error_response(
                f"{medicine.generic_name} is expired and cannot be sold."
            )

        if medicine.quantity <= 0:
            return error_response(
                f"{medicine.generic_name} is out of stock."
            )

        if quantity > medicine.quantity:
            return error_response(
                f"Not enough stock for {medicine.generic_name}. "
                f"Only {medicine.quantity} available."
            )

        resolved.append((medicine, quantity))

    # -------------------------------------------------------------
    # Calculate totals
    # -------------------------------------------------------------

    total_amount = sum(
        m.selling_price * q
        for m, q in resolved
    )

    total_profit = sum(
        (m.selling_price - m.purchase_price) * q
        for m, q in resolved
    )

    receipt_number = generate_receipt_number(db_session)

    # -------------------------------------------------------------
    # Create sale
    # -------------------------------------------------------------

    sale = Sale(
        receipt_number=receipt_number,
        sold_by=user.id,
        total_amount=total_amount,
        total_profit=total_profit,
    )

    db_session.add(sale)
    db_session.flush()

    # -------------------------------------------------------------
    # Create sale items and reduce stock
    # -------------------------------------------------------------

    for medicine, quantity in resolved:

        subtotal = medicine.selling_price * quantity

        profit = (
            medicine.selling_price
            - medicine.purchase_price
        ) * quantity

        db_session.add(
            SaleItem(
                sale_id=sale.id,
                medicine_id=medicine.id,
                quantity=quantity,
                purchase_price=medicine.purchase_price,
                selling_price=medicine.selling_price,
                subtotal=subtotal,
                profit=profit,
            )
        )

        try:
            adjust_stock(
                db_session,
                medicine,
                -quantity,
                "sale",
                user,
                note=f"Sale {receipt_number}",
                allow_sale_reason=True,
            )

        except StockError as e:
            db_session.rollback()
            return error_response(
                e.message,
                e.status,
            )

    # -------------------------------------------------------------
    # Activity log
    # -------------------------------------------------------------

    log_activity(
        db_session,
        user,
        "sale_completed",
        entity_type="sale",
        entity_id=sale.id,
        details=f"{receipt_number} — ${total_amount:.2f}",
    )

    db_session.commit()

    include_profit = user.role in ("Super Admin", "Admin Viewer")

    return jsonify(
        {
            "sale": serialize_sale(
                sale,
                include_profit=include_profit,
            )
        }
    ), 201


@sales_bp.get("")
@login_required
def list_sales():
    """
    Search/list past receipts.

    Both roles can view sales.
    Profit is only included for Admin users by the serializer.
    """
    query = db_session.query(Sale)

    receipt_number = request.args.get(
        "receipt_number",
        "",
    ).strip()

    if receipt_number:
        query = query.filter(
            Sale.receipt_number.ilike(
                f"%{receipt_number}%"
            )
        )

    start = request.args.get("start")
    end = request.args.get("end")

    try:
        if start:
            query = query.filter(
                Sale.sale_date
                >= datetime.strptime(
                    start,
                    "%Y-%m-%d",
                )
            )

        if end:
            query = query.filter(
                Sale.sale_date
                < datetime.strptime(
                    end,
                    "%Y-%m-%d",
                ) + timedelta(days=1)
            )

    except ValueError:
        return error_response(
            "start/end must be in YYYY-MM-DD format."
        )

    sales = (
        query
        .order_by(desc(Sale.sale_date))
        .limit(200)
        .all()
    )

    include_profit = (
        get_current_user().role in ("Super Admin", "Admin Viewer")
    )

    return jsonify(
        {
            "sales": [
                serialize_sale(
                    sale,
                    include_profit=include_profit,
                )
                for sale in sales
            ]
        }
    ), 200


@sales_bp.get("/<int:sale_id>")
@login_required
def get_sale(sale_id):
    """Reprint a specific receipt."""

    sale = db_session.query(Sale).get(sale_id)

    if not sale:
        return error_response(
            "Receipt not found.",
            404,
        )

    include_profit = (
        get_current_user().role in ("Super Admin", "Admin Viewer")
    )

    return jsonify(
        {
            "sale": serialize_sale(
                sale,
                include_profit=include_profit,
            )
        }
    ), 200