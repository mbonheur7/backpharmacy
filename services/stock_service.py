"""
Every quantity change in VI-PHARMACY — a sale, a manual restock, a
correction, a damaged/expired write-off — goes through adjust_stock().
Nothing else in the codebase should ever write to medicine.quantity
directly. That's what makes stock_movements a trustworthy history instead
of a log that can drift from reality.
"""

from models import StockMovement

MANUAL_REASONS = {"received", "adjustment", "damaged", "expired", "correction", "other"}
ALL_REASONS = MANUAL_REASONS | {"sale"}


class StockError(Exception):
    def __init__(self, message, status=400):
        self.message = message
        self.status = status
        super().__init__(message)


def adjust_stock(db_session, medicine, change_qty, reason, user, note=None, allow_sale_reason=False):
    """
    Applies change_qty to medicine.quantity and records a StockMovement.
    Does NOT commit — the caller commits, so a sale's stock movements and
    its Sale/SaleItem rows land in one transaction together.

    `allow_sale_reason` defaults to False so that the manual stock-movement
    API endpoint (used by both roles) can never be used to fake a 'sale'
    movement — only the checkout code path passes allow_sale_reason=True.

    Discontinued-medicine rule: a Discontinued medicine can still have its
    stock corrected or written off (adjustment/damaged/expired/correction/
    other) — you don't need to reactivate something just to record that its
    remaining stock expired. What's blocked is 'received' (you wouldn't be
    receiving new stock for something you've discontinued — reactivate it
    first if that's genuinely what's happening) and 'sale' (checkout.py
    already blocks selling a discontinued medicine before it ever calls
    this function, but the check is repeated here too, since this function
    is meant to be the only gate on quantity — it shouldn't depend on every
    future caller remembering to check status first).
    """
    try:
        change_qty = int(change_qty)
    except (TypeError, ValueError):
        raise StockError("Stock change amount must be a whole number.")

    if change_qty == 0:
        raise StockError("Stock change amount cannot be zero.")

    allowed_reasons = ALL_REASONS if allow_sale_reason else MANUAL_REASONS
    if reason not in allowed_reasons:
        raise StockError(f"Invalid stock movement reason: {reason!r}")

    if medicine.status == "Discontinued":
        if reason == "received":
            raise StockError(
                f"{medicine.generic_name} is discontinued — cannot receive new stock for it. "
                f"Reactivate the medicine first if you actually intend to restock it."
            )
        if reason == "sale":
            raise StockError(f"{medicine.generic_name} is discontinued and cannot be sold.")

    new_quantity = medicine.quantity + change_qty
    if new_quantity < 0:
        raise StockError(
            f"Not enough stock. {medicine.generic_name} only has {medicine.quantity} available."
        )

    medicine.quantity = new_quantity

    movement = StockMovement(
        medicine_id=medicine.id,
        change_qty=change_qty,
        reason=reason,
        note=note,
        performed_by=user.id,
    )
    db_session.add(movement)
    return movement
