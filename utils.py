import random
from datetime import date, datetime

from flask import jsonify

from models import Sale


def generate_receipt_number(db_session):
    """
    Same format as the original prototype (REC + YYYYMMDD + 4 random digits),
    but checked for uniqueness against the database before being returned —
    the prototype never checked this since collisions were astronomically
    unlikely in a single local session, but a shared multi-user system
    should not assume that.
    """
    for _ in range(20):
        candidate = "REC" + date.today().strftime("%Y%m%d") + str(random.randint(1000, 9999))
        exists = db_session.query(Sale.id).filter(Sale.receipt_number == candidate).first()
        if not exists:
            return candidate
    raise RuntimeError("Could not generate a unique receipt number after 20 attempts.")


def error_response(message, status=400):
    return jsonify({"error": message}), status


def parse_date(value, field_name):
    """Parses 'YYYY-MM-DD' into a date, or returns None for an empty value.
    Raises ValueError with a user-facing message on bad input."""
    if value in (None, ""):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise ValueError(f"{field_name} must be in YYYY-MM-DD format.")


def missing_fields(data, fields):
    return [f for f in fields if data.get(f) in (None, "")]
