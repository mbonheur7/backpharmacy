from models import ActivityLog


def log_activity(db_session, user, action, entity_type=None, entity_id=None, details=None):
    """Does not commit — bundled into the same transaction as whatever
    action triggered it, so a logged action and its log entry always
    succeed or fail together."""
    entry = ActivityLog(
        user_id=user.id if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    db_session.add(entry)
    return entry
