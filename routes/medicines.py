from flask import Blueprint, request, jsonify
from sqlalchemy import desc

from extensions import db_session
from models import Medicine, StockMovement
from services.permission_service import login_required, require_role, get_current_user
from services.stock_service import adjust_stock, StockError
from services.activity_log_service import log_activity
from serializers import serialize_medicine, serialize_stock_movement
from utils import error_response, parse_date


medicines_bp = Blueprint("medicines", __name__)


# Fields any logged-in user (Admin or Pharmacist) may edit through the
# general PATCH endpoint.
NON_PRICE_FIELDS = {
    "generic_name",
    "brand_name",
    "medicine_class",
    "dosage",
    "expiry_date",
    "batch_number",
    "supplier",
    "date_received",
    "notes",
}

DATE_FIELDS = {"expiry_date", "date_received"}


# These fields NEVER go through the general PATCH endpoint.
# They have their own dedicated, separately-permissioned endpoints.
BLOCKED_ON_GENERIC_PATCH = {
    "purchase_price",
    "selling_price",
    "status",
    "quantity",
}


def _strict_number(value):
    """
    Return True only for real JSON numbers.

    Important:
    Python considers bool a subclass of int, so this explicitly excludes
    True and False.
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _strict_integer(value):
    """
    Return True only for real JSON integers.

    This rejects:
        True
        False
        2.5
        "2"
    """
    return isinstance(value, int) and not isinstance(value, bool)


# ---------------------------------------------------------------- list/get


@medicines_bp.get("")
@login_required
def list_medicines():
    query = db_session.query(Medicine)

    search = request.args.get("search", "").strip()

    if search:
        like = f"%{search}%"

        query = query.filter(
            Medicine.generic_name.ilike(like)
            | Medicine.brand_name.ilike(like)
            | Medicine.medicine_class.ilike(like)
            | Medicine.supplier.ilike(like)
        )

    status_filter = request.args.get("status")

    if status_filter in ("Active", "Discontinued"):
        query = query.filter(
            Medicine.status == status_filter
        )

    expiry_before = request.args.get("expiry_before")

    if expiry_before:
        try:
            query = query.filter(
                Medicine.expiry_date
                <= parse_date(
                    expiry_before,
                    "expiry_before"
                )
            )
        except ValueError as e:
            return error_response(str(e))

    medicines = (
        query
        .order_by(Medicine.generic_name)
        .all()
    )

    return jsonify(
        {
            "medicines": [
                serialize_medicine(m)
                for m in medicines
            ]
        }
    ), 200


@medicines_bp.get("/<int:medicine_id>")
@login_required
def get_medicine(medicine_id):
    medicine = (
        db_session.query(Medicine)
        .get(medicine_id)
    )

    if not medicine:
        return error_response(
            "Medicine not found.",
            404,
        )

    return jsonify(
        {
            "medicine": serialize_medicine(medicine)
        }
    ), 200


# --------------------------------------------------------------------- add


@medicines_bp.post("")
@require_role("Super Admin", "Pharmacist")
def create_medicine():
    """
    Both Admin and Pharmacist can add medicines.

    Initial stock is applied through stock_service rather than directly
    modifying quantity.

    Duplicate rule:
    An ACTIVE medicine with the same generic name AND dosage cannot
    be created again.

    Example:
        Amoxicillin + 500mg -> duplicate
        Amoxicillin + 250mg -> allowed
        Amoxicillin + 500mg with different brand -> duplicate

    Discontinued medicines are ignored by the duplicate check.
    """

    data = request.get_json(silent=True) or {}

    required = [
        "generic_name",
        "brand_name",
        "purchase_price",
        "selling_price",
        "expiry_date",
    ]

    missing = [
        field
        for field in required
        if data.get(field) in (None, "")
    ]

    if missing:
        return error_response(
            f"Missing required fields: {', '.join(missing)}"
        )

    # ----------------------------- names / dosage

    generic_name = data["generic_name"].strip()

    dosage = (
        (data.get("dosage") or "").strip()
        or None
    )

    # ----------------------------- duplicate medicine check
    #
    # A medicine is considered a duplicate when an ACTIVE medicine
    # has the same generic name AND dosage.
    #
    # Brand name does not matter.
    #
    # Discontinued medicines are intentionally ignored.

    duplicate_query = (
        db_session
        .query(Medicine)
        .filter(
            Medicine.status == "Active",
            Medicine.generic_name.ilike(generic_name),
        )
    )

    if dosage is None:
        duplicate_query = duplicate_query.filter(
            Medicine.dosage.is_(None)
        )
    else:
        duplicate_query = duplicate_query.filter(
            Medicine.dosage.ilike(dosage)
        )

    existing_medicine = duplicate_query.first()

    if existing_medicine:
        medicine_description = (
            existing_medicine.generic_name
        )

        if existing_medicine.dosage:
            medicine_description += (
                f" ({existing_medicine.dosage})"
            )

        return error_response(
            f"{medicine_description} already exists. "
            "Please adjust its stock instead of adding it again.",
            409,
        )

    # ----------------------------- dates

    try:
        expiry_date = parse_date(
            data["expiry_date"],
            "expiry_date",
        )

        date_received = parse_date(
            data.get("date_received"),
            "date_received",
        )

    except ValueError as e:
        return error_response(str(e))

    # ----------------------------- prices

    if not _strict_number(
        data["purchase_price"]
    ):
        return error_response(
            "purchase_price and selling_price must be numbers."
        )

    if not _strict_number(
        data["selling_price"]
    ):
        return error_response(
            "purchase_price and selling_price must be numbers."
        )

    purchase_price = float(
        data["purchase_price"]
    )

    selling_price = float(
        data["selling_price"]
    )

    if (
        purchase_price < 0
        or selling_price < 0
    ):
        return error_response(
            "Prices cannot be negative."
        )

    # ----------------------------- quantities

    initial_quantity = data.get(
        "initial_quantity",
        0,
    )

    minimum_stock = data.get(
        "minimum_stock",
        10,
    )

    critical_stock = data.get(
        "critical_stock",
        3,
    )

    if not _strict_integer(
        initial_quantity
    ):
        return error_response(
            "initial_quantity, minimum_stock, and critical_stock "
            "must be whole numbers."
        )

    if not _strict_integer(
        minimum_stock
    ):
        return error_response(
            "initial_quantity, minimum_stock, and critical_stock "
            "must be whole numbers."
        )

    if not _strict_integer(
        critical_stock
    ):
        return error_response(
            "initial_quantity, minimum_stock, and critical_stock "
            "must be whole numbers."
        )

    if (
        initial_quantity < 0
        or minimum_stock < 0
        or critical_stock < 0
    ):
        return error_response(
            "initial_quantity, minimum_stock, and critical_stock "
            "cannot be negative."
        )

    # ----------------------------- create medicine

    medicine = Medicine(
        generic_name=generic_name,

        brand_name=data["brand_name"].strip(),

        medicine_class=(
            (data.get("medicine_class") or "").strip()
            or None
        ),

        dosage=dosage,

        quantity=0,

        minimum_stock=minimum_stock,

        critical_stock=critical_stock,

        purchase_price=purchase_price,

        selling_price=selling_price,

        expiry_date=expiry_date,

        batch_number=(
            (data.get("batch_number") or "").strip()
            or None
        ),

        supplier=(
            (data.get("supplier") or "").strip()
            or None
        ),

        date_received=date_received,

        notes=(
            (data.get("notes") or "").strip()
            or None
        ),

        status="Active",
    )

    db_session.add(medicine)

    # Assign medicine.id before creating the initial stock movement.
    db_session.flush()

    user = get_current_user()

    if initial_quantity > 0:

        try:
            adjust_stock(
                db_session,
                medicine,
                initial_quantity,
                "received",
                user,
                note="Initial stock on creation",
            )

        except StockError as e:
            db_session.rollback()
            return error_response(
                e.message,
                e.status,
            )

    log_activity(
        db_session,
        user,
        "medicine_added",
        entity_type="medicine",
        entity_id=medicine.id,
        details=(
            f"Added {medicine.generic_name} "
            f"({medicine.brand_name})"
        ),
    )

    db_session.commit()

    return jsonify(
        {
            "medicine": serialize_medicine(
                medicine
            )
        }
    ), 201


# ------------------------------------------------------- general edit


@medicines_bp.patch("/<int:medicine_id>")
@require_role("Super Admin", "Pharmacist")
def update_medicine(medicine_id):

    medicine = (
        db_session.query(Medicine)
        .get(medicine_id)
    )

    if not medicine:
        return error_response(
            "Medicine not found.",
            404,
        )

    data = request.get_json(
        silent=True
    ) or {}

    blocked_present = (
        BLOCKED_ON_GENERIC_PATCH
        & set(data.keys())
    )

    if blocked_present:
        return error_response(
            "These fields must be changed through their "
            "dedicated endpoints: "
            f"{', '.join(sorted(blocked_present))}",
            403,
        )

    changed = []

    for field in NON_PRICE_FIELDS:

        if field not in data:
            continue

        value = data[field]

        if field in DATE_FIELDS:

            try:
                value = parse_date(
                    value,
                    field,
                )

            except ValueError as e:
                return error_response(
                    str(e)
                )

        elif isinstance(value, str):

            value = value.strip() or None

        setattr(
            medicine,
            field,
            value,
        )

        changed.append(field)

    if not changed:
        return error_response(
            "No editable fields were provided."
        )

    user = get_current_user()

    log_activity(
        db_session,
        user,
        "medicine_updated",
        entity_type="medicine",
        entity_id=medicine.id,
        details=(
            f"Updated fields: "
            f"{', '.join(changed)}"
        ),
    )

    db_session.commit()

    return jsonify(
        {
            "medicine": serialize_medicine(
                medicine
            )
        }
    ), 200


# ------------------------------------------------------- admin-only pricing


@medicines_bp.patch("/<int:medicine_id>/pricing")
@require_role("Super Admin")
def update_pricing(medicine_id):

    medicine = (
        db_session.query(Medicine)
        .get(medicine_id)
    )

    if not medicine:
        return error_response(
            "Medicine not found.",
            404,
        )

    data = request.get_json(
        silent=True
    ) or {}

    if (
        "purchase_price" not in data
        and "selling_price" not in data
    ):
        return error_response(
            "Provide purchase_price and/or selling_price."
        )

    if "purchase_price" in data:

        if not _strict_number(
            data["purchase_price"]
        ):
            return error_response(
                "purchase_price must be a number."
            )

        purchase_price = float(
            data["purchase_price"]
        )

        if purchase_price < 0:
            return error_response(
                "purchase_price cannot be negative."
            )

        medicine.purchase_price = purchase_price

    if "selling_price" in data:

        if not _strict_number(
            data["selling_price"]
        ):
            return error_response(
                "selling_price must be a number."
            )

        selling_price = float(
            data["selling_price"]
        )

        if selling_price < 0:
            return error_response(
                "selling_price cannot be negative."
            )

        medicine.selling_price = selling_price

    user = get_current_user()

    log_activity(
        db_session,
        user,
        "medicine_pricing_updated",
        entity_type="medicine",
        entity_id=medicine.id,
        details=(
            f"purchase_price={medicine.purchase_price}, "
            f"selling_price={medicine.selling_price}"
        ),
    )

    db_session.commit()

    return jsonify(
        {
            "medicine": serialize_medicine(
                medicine
            )
        }
    ), 200


# ------------------------------------------------------- admin-only status


@medicines_bp.patch("/<int:medicine_id>/status")
@require_role("Super Admin")
def update_status(medicine_id):

    medicine = (
        db_session.query(Medicine)
        .get(medicine_id)
    )

    if not medicine:
        return error_response(
            "Medicine not found.",
            404,
        )

    data = request.get_json(
        silent=True
    ) or {}

    new_status = data.get("status")

    if new_status not in (
        "Active",
        "Discontinued",
    ):
        return error_response(
            "status must be 'Active' or 'Discontinued'."
        )

    medicine.status = new_status

    user = get_current_user()

    log_activity(
        db_session,
        user,
        "medicine_status_changed",
        entity_type="medicine",
        entity_id=medicine.id,
        details=f"status={new_status}",
    )

    db_session.commit()

    return jsonify(
        {
            "medicine": serialize_medicine(
                medicine
            )
        }
    ), 200


@medicines_bp.post("/<int:medicine_id>/deactivate")
@require_role("Super Admin")
def deactivate_medicine(medicine_id):
    """
    The spec uses deactivation instead of hard deletion.
    There is intentionally no DELETE route for medicines.
    """

    medicine = (
        db_session.query(Medicine)
        .get(medicine_id)
    )

    if not medicine:
        return error_response(
            "Medicine not found.",
            404,
        )

    if medicine.status == "Discontinued":
        return error_response(
            "Medicine is already discontinued."
        )

    medicine.status = "Discontinued"

    user = get_current_user()

    log_activity(
        db_session,
        user,
        "medicine_deactivated",
        entity_type="medicine",
        entity_id=medicine.id,
        details=(
            f"Deactivated "
            f"{medicine.generic_name}"
        ),
    )

    db_session.commit()

    return jsonify(
        {
            "medicine": serialize_medicine(
                medicine
            )
        }
    ), 200


@medicines_bp.post("/<int:medicine_id>/reactivate")
@require_role("Super Admin")
def reactivate_medicine(medicine_id):

    medicine = (
        db_session.query(Medicine)
        .get(medicine_id)
    )

    if not medicine:
        return error_response(
            "Medicine not found.",
            404,
        )

    if medicine.status == "Active":
        return error_response(
            "Medicine is already active."
        )

    medicine.status = "Active"

    user = get_current_user()

    log_activity(
        db_session,
        user,
        "medicine_reactivated",
        entity_type="medicine",
        entity_id=medicine.id,
        details=(
            f"Reactivated "
            f"{medicine.generic_name}"
        ),
    )

    db_session.commit()

    return jsonify(
        {
            "medicine": serialize_medicine(
                medicine
            )
        }
    ), 200


# ------------------------------------------------------- stock movements


@medicines_bp.post(
    "/<int:medicine_id>/stock-movements"
)
@require_role("Super Admin", "Pharmacist")
def create_stock_movement(medicine_id):
    """
    Both roles can create stock movements.

    This is the ONLY way quantity changes outside of a sale.
    """

    medicine = (
        db_session.query(Medicine)
        .get(medicine_id)
    )

    if not medicine:
        return error_response(
            "Medicine not found.",
            404,
        )

    data = request.get_json(
        silent=True
    ) or {}

    change_qty = data.get(
        "change_qty"
    )

    if not _strict_integer(
        change_qty
    ):
        return error_response(
            "change_qty must be a whole number."
        )

    reason = data.get("reason")
    note = data.get("note")

    user = get_current_user()

    try:

        movement = adjust_stock(
            db_session,
            medicine,
            change_qty,
            reason,
            user,
            note=note,
        )

    except StockError as e:

        db_session.rollback()

        return error_response(
            e.message,
            e.status,
        )

    log_activity(
        db_session,
        user,
        "stock_added"
        if change_qty > 0
        else "stock_removed",
        entity_type="medicine",
        entity_id=medicine.id,
        details=(
            f"{change_qty:+d} ({reason})"
            + (
                f" — {note}"
                if note
                else ""
            )
        ),
    )

    db_session.commit()

    return jsonify(
        {
            "medicine": serialize_medicine(
                medicine
            ),
            "movement": serialize_stock_movement(
                movement
            ),
        }
    ), 201


@medicines_bp.get(
    "/<int:medicine_id>/stock-movements"
)
@login_required
def list_stock_movements(medicine_id):

    medicine = (
        db_session.query(Medicine)
        .get(medicine_id)
    )

    if not medicine:
        return error_response(
            "Medicine not found.",
            404,
        )

    movements = (
        db_session
        .query(StockMovement)
        .filter(
            StockMovement.medicine_id
            == medicine_id
        )
        .order_by(
            desc(
                StockMovement.occurred_at
            )
        )
        .all()
    )

    return jsonify(
        {
            "movements": [
                serialize_stock_movement(m)
                for m in movements
            ]
        }
    ), 200