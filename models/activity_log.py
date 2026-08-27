from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from db import Base


class ActivityLog(Base):
    """
    Admin-viewable audit trail. Separate from LoginHistory because those
    are specifically login attempts (including ones with no valid user);
    this table covers everything else worth auditing: medicine changes,
    user management, sales, etc.
    """
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(50), nullable=False)
    entity_type = Column(String(30), nullable=True)
    entity_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User", back_populates="activity_entries")

    def __repr__(self):
        return f"<ActivityLog {self.action} by user={self.user_id} at {self.occurred_at}>"
