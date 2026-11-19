"""JWT access tokens (PyJWT, HS256) and FastAPI auth dependencies (API doc section 2.4).

Claims: sub = "<role>:<user_id>", role, user_id, jti (UUID4), iat, exp.
Identity is read only from the token, never from the request body.

    from shared.auth import get_current_user, require_role, CurrentUser

    @router.post("/bookings/approve")
    def approve(body: ApproveIn, user: CurrentUser = Depends(require_role("host"))): ...
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Literal, Optional
from uuid import uuid4

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from shared.config import InfraSettings
from shared.errors import AppError

logger = logging.getLogger("shared.auth")

Role = Literal["guest", "host", "admin", "service"]
ROLES: tuple[str, ...] = ("guest", "host", "admin", "service")
DENYLIST_PREFIX = "g1:auth:denylist:"
WS_CLOSE_UNAUTHORIZED = 4401


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    role: str
    actor_id: str  # == sub, e.g. "guest:1001"
    jti: str
    exp: int       # unix seconds


@lru_cache
def _settings() -> InfraSettings:
    return InfraSettings()


def _secret() -> str:
    secret = _settings().jwt_secret
    if not secret:
        raise RuntimeError("JWT_SECRET is not set (run ./scripts/setup-env.sh)")
    return secret


def _unauthorized() -> AppError:
    return AppError(401, "UNAUTHORIZED", "Missing or invalid token.")


def create_access_token(user_id: int | str, role: Role, expires_minutes: Optional[int] = None) -> str:
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}")
    s = _settings()
    now = datetime.now(timezone.utc)
    minutes = expires_minutes if expires_minutes is not None else s.jwt_expiry_minutes
    claims = {
        "sub": f"{role}:{user_id}",
        "role": role,
        "user_id": str(user_id),
        "jti": str(uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    return jwt.encode(claims, _secret(), algorithm=s.jwt_algorithm)


def decode_access_token(token: Optional[str]) -> CurrentUser:
    if not token:
        raise _unauthorized()
    s = _settings()
    try:
        claims = jwt.decode(
            token, _secret(), algorithms=[s.jwt_algorithm],
            options={"require": ["sub", "role", "user_id", "jti", "iat", "exp"]},
        )
    except jwt.ExpiredSignatureError:
        raise AppError(401, "TOKEN_EXPIRED", "Token expired.") from None
    except jwt.PyJWTError:
        raise _unauthorized() from None
    role = claims.get("role")
    if role not in ROLES or claims.get("sub") != f"{role}:{claims.get('user_id')}":
        raise _unauthorized()
    return CurrentUser(
        user_id=str(claims["user_id"]), role=role, actor_id=claims["sub"],
        jti=str(claims["jti"]), exp=int(claims["exp"]),
    )


# ---------- denylist (Redis) ----------

def _redis():
    import redis

    s = _settings()
    return redis.Redis(host=s.redis_host, port=s.redis_port, password=s.redis_password or None,
                       socket_timeout=1, socket_connect_timeout=1)


def revoke_token(user: CurrentUser) -> None:
    """Denylist the token's jti until it expires (logout)."""
    ttl = max(1, user.exp - int(datetime.now(timezone.utc).timestamp()))
    try:
        _redis().set(f"{DENYLIST_PREFIX}{user.jti}", "1", ex=ttl)
    except Exception as exc:  # noqa: BLE001
        logger.warning("jwt_denylist_unavailable op=revoke jti=%s error=%s", user.jti, exc)


def is_revoked(jti: str) -> bool:
    """True if denylisted. If Redis is unreachable, log a warning and return False."""
    try:
        return bool(_redis().exists(f"{DENYLIST_PREFIX}{jti}"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("jwt_denylist_unavailable op=check jti=%s error=%s", jti, exc)
        return False


def _check_not_revoked(user: CurrentUser) -> CurrentUser:
    if is_revoked(user.jti):
        raise AppError(401, "TOKEN_REVOKED", "Token has been revoked.")
    return user


# ---------- FastAPI dependencies ----------

_bearer = HTTPBearer(auto_error=False)


def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)) -> CurrentUser:
    if creds is None or not creds.credentials:
        raise _unauthorized()
    return _check_not_revoked(decode_access_token(creds.credentials))


def optional_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)) -> Optional[CurrentUser]:
    if creds is None or not creds.credentials:
        return None
    return _check_not_revoked(decode_access_token(creds.credentials))


def require_role(*roles: str):
    allowed = set(roles)

    def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed:
            raise AppError(403, "ROLE_FORBIDDEN", "This action is not allowed for your role.")
        return user

    return _dep


def ws_user_from_token(token: Optional[str]) -> CurrentUser:
    """Auth for WebSockets (?token=...). On AppError, close the socket with code 4401."""
    return _check_not_revoked(decode_access_token(token))
