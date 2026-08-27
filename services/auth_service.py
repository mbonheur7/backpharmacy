from datetime import datetime, timedelta, timezone

import bcrypt

from config import Config
from models import User, LoginHistory


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed hash in the DB shouldn't 500 the login endpoint — treat as a failed check.
        return False


class AuthResult:
    def __init__(self, user=None, error=None, status=200):
        self.user = user
        self.error = error
        self.status = status


def authenticate(db_session, username: str, password: str, ip_address: str = None) -> AuthResult:
    """
    Single entry point for login. Always writes a login_history row —
    success or failure, known user or not — and applies the approved
    lockout policy: 5 failed attempts -> 15 minute lock (from Config,
    which reads LOCKOUT_MAX_FAILED_ATTEMPTS / LOCKOUT_DURATION_MINUTES).
    """
    now = datetime.now(timezone.utc)
    user = db_session.query(User).filter(User.username == username).first()

    def record(success, user_id=None):
        db_session.add(LoginHistory(
            user_id=user_id, username_tried=username, success=success, ip_address=ip_address,
        ))

    if user is None:
        record(False)
        db_session.commit()
        return AuthResult(error="Wrong username or password.", status=401)

    locked_until = user.locked_until
    if locked_until is not None and locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)

    if locked_until and locked_until > now:
        record(False, user.id)
        db_session.commit()
        minutes_left = max(1, int((locked_until - now).total_seconds() // 60) + 1)
        return AuthResult(error=f"Account locked. Try again in {minutes_left} minute(s).", status=423)

    if not user.is_active:
        record(False, user.id)
        db_session.commit()
        return AuthResult(error="This account has been disabled. Contact an administrator.", status=403)

    if not verify_password(password, user.password_hash):
        user.failed_logins += 1
        locked_now = False
        if user.failed_logins >= Config.LOCKOUT_MAX_FAILED_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=Config.LOCKOUT_DURATION_MINUTES)
            locked_now = True
        record(False, user.id)
        db_session.commit()
        if locked_now:
            return AuthResult(
                error=f"Too many failed attempts. Account locked for {Config.LOCKOUT_DURATION_MINUTES} minutes.",
                status=423,
            )
        return AuthResult(error="Wrong username or password.", status=401)

    # Success
    user.failed_logins = 0
    user.locked_until = None
    record(True, user.id)
    db_session.commit()
    return AuthResult(user=user, status=200)
