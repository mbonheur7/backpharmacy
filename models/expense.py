from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    Date,
    DateTime,
    ForeignKey,
    CheckConstraint,
    func,
)
from sqlalchemy.orm import relationship

from db import Base


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(
        Integer,
        primary_key=True,
    )

    title = Column(
        String(150),
        nullable=False,
    )

    category = Column(
        String(50),
        nullable=False,
    )

    description = Column(
        String(500),
        nullable=True,
    )

    amount = Column(
        Numeric(12, 2),
        nullable=False,
    )

    expense_date = Column(
        Date,
        nullable=False,
    )

    created_by_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    created_by = relationship(
        "User",
        back_populates="expenses",
    )

    __table_args__ = (

        CheckConstraint(
            "amount > 0",
            name="ck_expenses_amount_positive",
        ),

    )

    def __repr__(self):

        return (
            f"<Expense "
            f"{self.id} "
            f"{self.title} "
            f"{self.amount}>"
        )