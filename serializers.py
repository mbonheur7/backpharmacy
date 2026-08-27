"""
Every route returns JSON built from these functions rather than hand-rolling
dicts inline, so the "Pharmacists never see profit" rule lives in exactly
one place (serialize_sale / serialize_sale_item) instead of being repeated
— and possibly forgotten — at every call site.
"""


def serialize_user(user):
    return {
        "id": user.id,
        "username": user.username,
        "fullname": user.fullname,
        "role": user.role,
        "is_active": user.is_active,
        "failed_logins": user.failed_logins,
        "locked_until": user.locked_until.isoformat() if user.locked_until else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def serialize_medicine(m):
    return {
        "id": m.id,
        "generic_name": m.generic_name,
        "medicine_class": m.medicine_class,
        "brand_name": m.brand_name,
        "dosage": m.dosage,
        "quantity": m.quantity,
        "minimum_stock": m.minimum_stock,
        "critical_stock": m.critical_stock,
        "purchase_price": float(m.purchase_price),
        "selling_price": float(m.selling_price),
        "expiry_date": m.expiry_date.isoformat() if m.expiry_date else None,
        "date_added": m.date_added.isoformat() if m.date_added else None,
        "batch_number": m.batch_number,
        "supplier": m.supplier,
        "date_received": m.date_received.isoformat() if m.date_received else None,
        "notes": m.notes,
        "status": m.status,
    }


def serialize_stock_movement(mv):
    return {
        "id": mv.id,
        "medicine_id": mv.medicine_id,
        "change_qty": mv.change_qty,
        "reason": mv.reason,
        "note": mv.note,
        "performed_by": mv.performed_by,
        "occurred_at": mv.occurred_at.isoformat() if mv.occurred_at else None,
    }


def serialize_sale(sale, include_profit=False):
    data = {
        "id": sale.id,
        "receipt_number": sale.receipt_number,
        "sold_by": sale.sold_by,
        "sold_by_name": sale.cashier.fullname if sale.cashier else None,
        "total_amount": float(sale.total_amount),
        "sale_date": sale.sale_date.isoformat() if sale.sale_date else None,
        "items": [serialize_sale_item(i, include_profit) for i in sale.items],
    }
    if include_profit:
        data["total_profit"] = float(sale.total_profit)
    return data


def serialize_sale_item(item, include_profit=False):
    data = {
        "medicine_id": item.medicine_id,
        "generic_name": item.medicine.generic_name if item.medicine else None,
        "quantity": item.quantity,
        "selling_price": float(item.selling_price),
        "subtotal": float(item.subtotal),
    }
    if include_profit:
        data["purchase_price"] = float(item.purchase_price)
        data["profit"] = float(item.profit)
    return data


def serialize_activity_log(entry):
    return {
        "id": entry.id,
        "user_id": entry.user_id,
        "user_name": entry.user.fullname if entry.user else None,
        "action": entry.action,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "details": entry.details,
        "occurred_at": entry.occurred_at.isoformat() if entry.occurred_at else None,
    }
