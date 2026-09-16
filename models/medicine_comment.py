from sqlalchemy import (
    Column,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    func,
)
from sqlalchemy.orm import relationship

from db import Base


class MedicineComment(Base):
    __tablename__ = "medicine_comments"

    id = Column(
        Integer,
        primary_key=True,
    )

    medicine_id = Column(
        Integer,
        ForeignKey(
            "medicines.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    comment = Column(
        Text,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    medicine = relationship(
        "Medicine",
        back_populates="comments",
    )

    user = relationship(
        "User",
        back_populates="medicine_comments",
    )

    def __repr__(self):
        return (
            f"<MedicineComment "
            f"id={self.id} "
            f"medicine={self.medicine_id} "
            f"user={self.user_id}>"
        )