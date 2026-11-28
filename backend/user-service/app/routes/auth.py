"""POST /api/v1/auth/login, POST /api/v1/auth/logout, GET /api/v1/auth/me."""
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.routes.openapi_docs import AUTH, VALIDATION, errors
from app.schemas.users import AuthUser, LoginOut, LoginRequest
from app.services import users as svc
from shared.auth import CurrentUser, get_current_user, revoke_token
from shared.responses import Envelope, ok

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login", response_model=Envelope[LoginOut], summary="Sign in a guest, host or admin",
    description="Returns a 30-minute bearer token. One generic error for a wrong email, password or role; "
                "deleted accounts cannot sign in. 5 failed attempts per email in 15 minutes returns 429.",
    responses=errors((401, "INVALID_CREDENTIALS", "Email or password is incorrect."), VALIDATION,
                     (429, "RATE_LIMITED", "Too many failed sign-in attempts. Try again in 15 minutes.")),
)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_session)):
    return ok(svc.login(db, body), request)


@router.post(
    "/logout", status_code=204, summary="End the current session",
    description="Adds the token's jti to the Redis denylist until it expires. The frontend also deletes the token.",
    responses={204: {"description": "Signed out"}, **errors(*AUTH)},
)
def logout(user: CurrentUser = Depends(get_current_user)):
    revoke_token(user)
    return Response(status_code=204)


@router.get(
    "/me", response_model=Envelope[AuthUser], summary="Current identity",
    description="Restores the signed-in user after a page refresh.",
    responses=errors(*AUTH, (401, "TOKEN_REVOKED", "Token has been revoked.")),
)
def me(request: Request, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_session)):
    return ok(svc.me(db, user), request)
