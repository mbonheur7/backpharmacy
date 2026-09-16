from sqlalchemy import (
    Column, Integer, String, Numeric, Date, DateTime, Text,
    CheckConstraint, ForeignKey, func
)
from sqlalchemy.orm import relationship

from db import Base


class Medicine(Base):
    __tablename__ = "medicines"

    id = Column(Integer, primary_key=True)

    # Carried over from the original prototype
    generic_name = Column(String(100), nullable=False, index=True)
    medicine_class = Column(String(100), nullable=True)
    brand_name = Column(String(100), nullable=False)
    dosage = Column(String(50), nullable=True)
    quantity = Column(Integer, nullable=False, default=0)
    minimum_stock = Column(Integer, nullable=False, default=10)
    purchase_price = Column(Numeric(10, 2), nullable=False)
    selling_price = Column(Numeric(10, 2), nullable=False)
    expiry_date = Column(Date, nullable=False)
    date_added = Column(Date, nullable=False, server_default=func.current_date())

    # New fields required by the VI-PHARMACY spec
    batch_number = Column(String(50), nullable=True)
    supplier = Column(String(100), nullable=True, index=True)
    date_received = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="Active")
    critical_stock = Column(Integer, nullable=False, default=3)

    stock_movements = relationship(
        "StockMovement",
        back_populates="medicine",
    )

    sale_items = relationship(
        "SaleItem",
        back_populates="medicine",
    )

    comments = relationship(
        "MedicineComment",
        back_populates="medicine",
    )
    __table_args__ = (
        CheckConstraint("status IN ('Active', 'Discontinued')", name="ck_medicines_status"),
        CheckConstraint("quantity >= 0", name="ck_medicines_quantity_nonnegative"),
        CheckConstraint("purchase_price >= 0", name="ck_medicines_purchase_price_nonnegative"),
        CheckConstraint("selling_price >= 0", name="ck_medicines_selling_price_nonnegative"),
        CheckConstraint("minimum_stock >= 0", name="ck_medicines_minimum_stock_nonnegative"),
        CheckConstraint("critical_stock >= 0", name="ck_medicines_critical_stock_nonnegative"),
    )

    def __repr__(self):
        return f"<Medicine {self.generic_name} ({self.status})>"


class StockMovement(Base):
    """
    The only history of quantity changes. Every sale checkout and every
    manual stock-in/stock-out/adjustment writes exactly one row here.
    medicines.quantity is a running total; this table is the audit trail
    behind it.
    """
    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True)
    medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=False)
    change_qty = Column(Integer, nullable=False)  # positive = stock in, negative = stock out
    reason = Column(String(30), nullable=False)
    note = Column(Text, nullable=True)
    performed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    medicine = relationship("Medicine", back_populates="stock_movements")
    user = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "reason IN ('received','sale','adjustment','damaged','expired','correction','other')",
            name="ck_stock_movements_reason",
        ),
        CheckConstraint("change_qty <> 0", name="ck_stock_movements_change_qty_nonzero"),
    )

    def __repr__(self):
        return f"<StockMovement medicine={self.medicine_id} qty={self.change_qty} reason={self.reason}>"
