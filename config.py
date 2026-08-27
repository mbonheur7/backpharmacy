"""
All configuration comes from environment variables — nothing sensitive is
hardcoded here. Load a .env file (via python-dotenv) before importing this
module in local development; in production (Render/Railway) the platform
injects real environment variables directly, so no .env file is needed there.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Required environment variable '{name}' is not set. "
            f"Copy .env.example to .env and fill it in for local development."
        )
    return value


def _bool_env(name: str, default: str) -> bool:
    return os.environ.get(name, default).strip().lower() in ("true", "1", "yes")


# Computed as plain module-level values first, then assigned onto Config
# below — this makes every Stage 2 setting a single, unambiguous line with
# no dependency on class-body evaluation order, so a partial/stale copy of
# this file is easy to spot by diffing against the source of truth rather
# than failing at Flask startup with an AttributeError.
_database_url = _require("DATABASE_URL")
_secret_key = os.environ.get("SECRET_KEY", "")
_lockout_max_failed_attempts = int(os.environ.get("LOCKOUT_MAX_FAILED_ATTEMPTS", "5"))
_lockout_duration_minutes = int(os.environ.get("LOCKOUT_DURATION_MINUTES", "15"))

# SESSION_COOKIE_SECURE controls whether the browser will only send the
# session cookie over HTTPS. Defaults to False specifically so local
# development over plain http://127.0.0.1 works without any extra setup —
# set SESSION_COOKIE_SECURE=true in your deployed environment's variables
# once it's actually served over HTTPS.
_session_cookie_secure = _bool_env("SESSION_COOKIE_SECURE", "false")
_session_lifetime_hours = int(os.environ.get("SESSION_LIFETIME_HOURS", "8"))

_cors_raw = os.environ.get("CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]


class Config:
    DATABASE_URL = _database_url
    SECRET_KEY = _secret_key
    LOCKOUT_MAX_FAILED_ATTEMPTS = _lockout_max_failed_attempts
    LOCKOUT_DURATION_MINUTES = _lockout_duration_minutes
    SESSION_COOKIE_SECURE = _session_cookie_secure
    SESSION_LIFETIME_HOURS = _session_lifetime_hours
    CORS_ORIGINS = _cors_origins


# Fails fast and loudly, at import time, with a message that names the
# exact missing attribute and how to fix it — instead of letting Flask
# crash later with a bare AttributeError pointing at app.py. If you ever
# see this fire, it means config.py on disk is out of date; replace it
# with the version from the latest backend delivery.
_EXPECTED_CONFIG_ATTRS = (
    "DATABASE_URL", "SECRET_KEY", "LOCKOUT_MAX_FAILED_ATTEMPTS",
    "LOCKOUT_DURATION_MINUTES", "SESSION_COOKIE_SECURE",
    "SESSION_LIFETIME_HOURS", "CORS_ORIGINS",
)
_missing = [a for a in _EXPECTED_CONFIG_ATTRS if not hasattr(Config, a)]
if _missing:
    raise RuntimeError(
        f"config.py is missing expected setting(s): {', '.join(_missing)}. "
        f"This usually means an old copy of config.py is on disk instead of "
        f"the current one — replace this file with the latest version."
    )

