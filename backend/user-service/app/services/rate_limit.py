"""Login rate limit: 5 failed attempts per email per 15 minutes (Redis). Skipped if Redis is down."""
import logging

from app.database.connection import get_redis

logger = logging.getLogger("user_service.rate_limit")
MAX_FAILURES = 5
WINDOW_S = 15 * 60


def _key(email: str) -> str:
    return f"g1:user:login_fail:{email}"


def is_locked(email: str) -> bool:
    try:
        return int(get_redis().get(_key(email)) or 0) >= MAX_FAILURES
    except Exception as exc:  # noqa: BLE001
        logger.warning("login_rate_limit_unavailable error=%s", exc)
        return False


def record_failure(email: str) -> None:
    try:
        r = get_redis()
        n = r.incr(_key(email))
        if n == 1:
            r.expire(_key(email), WINDOW_S)
    except Exception as exc:  # noqa: BLE001
        logger.warning("login_rate_limit_unavailable error=%s", exc)


def clear(email: str) -> None:
    try:
        get_redis().delete(_key(email))
    except Exception:  # noqa: BLE001
        pass
