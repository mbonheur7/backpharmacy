from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from db import Base


class ChatGroup(Base):
    __tablename__ = "chat_groups"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    members = relationship(
        "ChatMember",
        back_populates="group",
        cascade="all, delete-orphan",
    )

    messages = relationship(
        "ChatMessage",
        back_populates="group",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<ChatGroup {self.name}>"


class ChatMember(Base):
    __tablename__ = "chat_members"

    id = Column(Integer, primary_key=True)

    group_id = Column(
        Integer,
        ForeignKey("chat_groups.id", ondelete="CASCADE"),
        nullable=False,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    joined_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "group_id",
            "user_id",
            name="uq_chat_member_group_user",
        ),
    )

    group = relationship(
        "ChatGroup",
        back_populates="members",
    )

    user = relationship(
        "User",
    )

    def __repr__(self):
        return f"<ChatMember group={self.group_id} user={self.user_id}>"


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)

    group_id = Column(
        Integer,
        ForeignKey("chat_groups.id", ondelete="CASCADE"),
        nullable=False,
    )

    sender_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    message = Column(
        Text,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    group = relationship(
        "ChatGroup",
        back_populates="messages",
    )

    sender = relationship(
        "User",
    )

    reads = relationship(
        "ChatMessageRead",
        back_populates="message",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<ChatMessage {self.id} group={self.group_id}>"


class ChatMessageRead(Base):
    __tablename__ = "chat_message_reads"

    id = Column(Integer, primary_key=True)

    message_id = Column(
        Integer,
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    read_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "message_id",
            "user_id",
            name="uq_chat_message_read_user",
        ),
    )

    message = relationship(
        "ChatMessage",
        back_populates="reads",
    )

    user = relationship(
        "User",
    )

    def __repr__(self):
        return (
            f"<ChatMessageRead "
            f"message={self.message_id} "
            f"user={self.user_id}>"
        )