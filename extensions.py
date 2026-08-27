"""
Wires the plain SQLAlchemy session from db.py (Stage 1) into Flask's request
lifecycle, using scoped_session rather than adding Flask-SQLAlchemy as a new
dependency. Every route imports `db_session` from here and uses it exactly
like a normal SQLAlchemy Session — Flask just guarantees it's cleaned up
(and a fresh one started) at the end of every request.
"""

from sqlalchemy.orm import scoped_session

from db import SessionLocal

db_session = scoped_session(SessionLocal)


def init_db_session(app):
    @app.teardown_appcontext
    def remove_db_session(exception=None):
        db_session.remove()
