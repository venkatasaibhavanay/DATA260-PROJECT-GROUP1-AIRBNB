"""Guest profile routes (API doc 6.2)."""
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.schemas.users import GuestCreate, GuestIdRequest, GuestSearch, GuestSignupOut, GuestUpdate
from app.services import users as svc
from app.services.events import Publisher, get_publisher
from shared.auth import CurrentUser, require_role
from shared.responses import Envelope, ok

router = APIRouter(prefix="/guests", tags=["guests"])


@router.post("/create", status_code=201, response_model=Envelope[GuestSignupOut], summary="Guest signup")
def create(body: GuestCreate, request: Request, db: Session = Depends(get_session),
           pub: Publisher = Depends(get_publisher)):
    return ok(svc.create_guest(db, pub, request, body), request)


@router.post("/get", summary="Read a guest profile (own: all fields; host: public subset)")
def get(body: GuestIdRequest, request: Request, db: Session = Depends(get_session),
        user: CurrentUser = Depends(require_role("guest", "host", "admin"))):
    return ok(svc.get_guest(db, user, body.guest_id), request)


@router.post("/update", summary="Update supplied fields of your own guest profile")
def update(body: GuestUpdate, request: Request, db: Session = Depends(get_session),
           user: CurrentUser = Depends(require_role("guest"))):
    return ok(svc.update_guest(db, user, body), request)


@router.post("/delete", status_code=204, summary="Delete your own guest profile (soft delete)")
def delete(body: GuestIdRequest, request: Request, db: Session = Depends(get_session),
           pub: Publisher = Depends(get_publisher), user: CurrentUser = Depends(require_role("guest"))):
    svc.delete_guest(db, pub, request, user, body.guest_id)
    return Response(status_code=204)


@router.post("/search", summary="Search guests by name and location (host or admin)")
def search(body: GuestSearch, request: Request, db: Session = Depends(get_session),
           user: CurrentUser = Depends(require_role("host", "admin"))):
    return ok(svc.search_guests(db, user, body), request)
