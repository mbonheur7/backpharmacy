from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    CheckConstraint,
    func,
)

from sqlalchemy.orm import relationship

from db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
    )

    username = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    password_hash = Column(
        String(255),
        nullable=False,
    )

    fullname = Column(
        String(100),
        nullable=False,
    )

    role = Column(
        String(20),
        nullable=False,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    failed_logins = Column(
        Integer,
        nullable=False,
        default=0,
    )

    locked_until = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


    # =====================================================
    # LOGIN HISTORY
    # =====================================================

    login_attempts = relationship(
        "LoginHistory",
        back_populates="user",
    )


    # =====================================================
    # ACTIVITY LOGS
    # =====================================================

    activity_entries = relationship(
        "ActivityLog",
        back_populates="user",
    )


    # =====================================================
    # MEDICINE COMMENTS
    # =====================================================

    medicine_comments = relationship(
        "MedicineComment",
        back_populates="user",
    )


    # =====================================================
    # EXPENSES
    # =====================================================

    expenses = relationship(
        "Expense",
        back_populates="created_by",
    )


    # =====================================================
    # ROLE VALIDATION
    # =====================================================

    __table_args__ = (

        CheckConstraint(
            "role IN "
            "('Super Admin', 'Admin Viewer', 'Pharmacist')",
            name="ck_users_role",
        ),

    )


    def __repr__(self):

        return (
            f"<User "
            f"{self.username} "
            f"({self.role})>"
        )


class LoginHistory(Base):
    __tablename__ = "login_history"

    id = Column(
        Integer,
        primary_key=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    username_tried = Column(
        String(50),
        nullable=False,
    )

    success = Column(
        Boolean,
        nullable=False,
    )

    ip_address = Column(
        String(64),
        nullable=True,
    )

    occurred_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


    user = relationship(
        "User",
        back_populates="login_attempts",
    )


    def __repr__(self):

        outcome = (
            "success"
            if self.success
            else "failed"
        )

        return (

            f"<LoginHistory "
            f"{self.username_tried} "
            f"{outcome} "
            f"at {self.occurred_at}>"

        )