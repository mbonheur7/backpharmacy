"""
Import every model here so that a single `from models import *` (used by
Alembic's env.py) registers all tables on Base.metadata. If you add a new
model file later, import it here too, or Alembic autogenerate will silently
miss it.
"""

from models.user import User, LoginHistory
from models.medicine import Medicine, StockMovement
from models.sale import Sale, SaleItem
from models.activity_log import ActivityLog

__all__ = [
    "User",
    "LoginHistory",
    "Medicine",
    "StockMovement",
    "Sale",
    "SaleItem",
    "ActivityLog",
]
