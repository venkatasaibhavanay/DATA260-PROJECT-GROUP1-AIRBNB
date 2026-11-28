"""POST /api/v1/auth/login, POST /api/v1/auth/logout, GET /api/v1/auth/me."""
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.schemas.users import AuthUser, LoginOut, LoginRequest
from app.services import users as svc
from shared.auth import CurrentUser, get_current_user, revoke_token
from shared.responses import Envelope, ok

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Envelope[LoginOut], summary="Sign in a guest, host or admin")
def login(body: LoginRequest, request: Request, db: Session = Depends(get_session)):
    return ok(svc.login(db, body), request)


@router.post("/logout", status_code=204, summary="End the current session (denylists the token)")
def logout(user: CurrentUser = Depends(get_current_user)):
    revoke_token(user)
    return Response(status_code=204)


@router.get("/me", response_model=Envelope[AuthUser], summary="Current identity")
def me(request: Request, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_session)):
    return ok(svc.me(db, user), request)
