"""Shared JWT authentication (HS256) and role checks."""
from shared.auth.jwt_auth import (
    ROLES,
    WS_CLOSE_UNAUTHORIZED,
    CurrentUser,
    create_access_token,
    decode_access_token,
    get_current_user,
    is_revoked,
    optional_user,
    require_role,
    revoke_token,
    ws_user_from_token,
)

__all__ = [
    "ROLES", "WS_CLOSE_UNAUTHORIZED", "CurrentUser", "create_access_token", "decode_access_token",
    "get_current_user", "optional_user", "require_role", "revoke_token", "is_revoked",
    "ws_user_from_token",
]
