from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    ForeignKey,
    CheckConstraint,
    func,
)

from sqlalchemy.orm import relationship

from db import Base


class Sale(Base):
    __tablename__ = "sales"

    id = Column(
        Integer,
        primary_key=True,
    )

    receipt_number = Column(
        String(30),
        unique=True,
        nullable=False,
        index=True,
    )

    sold_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    total_amount = Column(
        Numeric(10, 2),
        nullable=False,
    )

    total_profit = Column(
        Numeric(10, 2),
        nullable=False,
    )

    sale_date = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    cashier = relationship(
        "User",
    )

    items = relationship(
        "SaleItem",
        back_populates="sale",
    )

    def __repr__(self):
        return (
            f"<Sale "
            f"{self.receipt_number} "
            f"total={self.total_amount}>"
        )


class SaleItem(Base):
    """
    purchase_price and selling_price are snapshotted
    at sale time.

    Historical receipts remain accurate even when
    medicine prices change later.
    """

    __tablename__ = "sale_items"

    id = Column(
        Integer,
        primary_key=True,
    )

    sale_id = Column(
        Integer,
        ForeignKey("sales.id"),
        nullable=False,
    )

    medicine_id = Column(
        Integer,
        ForeignKey("medicines.id"),
        nullable=False,
    )

    quantity = Column(
        Integer,
        nullable=False,
    )

    purchase_price = Column(
        Numeric(10, 2),
        nullable=False,
    )

    selling_price = Column(
        Numeric(10, 2),
        nullable=False,
    )

    subtotal = Column(
        Numeric(10, 2),
        nullable=False,
    )

    profit = Column(
        Numeric(10, 2),
        nullable=False,
    )

    sale = relationship(
        "Sale",
        back_populates="items",
    )

    medicine = relationship(
        "Medicine",
        back_populates="sale_items",
    )

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_sale_items_quantity_positive",
        ),
    )

    def __repr__(self):
        return (
            f"<SaleItem "
            f"sale={self.sale_id} "
            f"medicine={self.medicine_id} "
            f"qty={self.quantity}>"
        )