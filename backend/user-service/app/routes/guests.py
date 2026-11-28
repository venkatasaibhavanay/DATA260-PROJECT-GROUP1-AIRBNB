"""Guest profile routes (API doc 6.2)."""
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.routes.openapi_docs import AUTH, EMAIL_EXISTS, KAFKA_DOWN, ROLE_FORBIDDEN, VALIDATION, errors, ok_doc
from app.schemas.users import (
    GuestCreate, GuestIdRequest, GuestProfileOut, GuestSearch, GuestSearchPage, GuestSignupOut, GuestUpdate,
    GuestUpdatedOut,
)
from app.services import users as svc
from app.services.events import Publisher, get_publisher
from shared.auth import CurrentUser, require_role
from shared.responses import Envelope, ok

router = APIRouter(prefix="/guests", tags=["guests"])

NOT_FOUND = (404, "GUEST_NOT_FOUND", "Guest not found.")
NOT_OWNER = (403, "NOT_PROFILE_OWNER", "You can only change your own profile.")


@router.post(
    "/create", status_code=201, response_model=Envelope[GuestSignupOut], summary="Guest signup",
    description="Creates a guest account and returns a token. Publishes `user.registered` (entity guest). "
                "first_name/last_name 1-60 chars, location required, password ≥ 8 chars with a letter and a digit, "
                "phone in E.164. preferences is optional and validated against the amenity and property_type enums.",
    responses=errors(EMAIL_EXISTS, VALIDATION, KAFKA_DOWN),
)
def create(body: GuestCreate, request: Request, db: Session = Depends(get_session),
           pub: Publisher = Depends(get_publisher)):
    return ok(svc.create_guest(db, pub, request, body), request)


@router.post(
    "/get", summary="Read a guest profile",
    description="Guest (own) and admin: every field. Host: first_name, last_name initial, location, "
                "profile_photo_url and profile_created_datetime only.",
    responses={**ok_doc(Envelope[GuestProfileOut]),
               **errors(*AUTH, ROLE_FORBIDDEN, (403, "NOT_PROFILE_OWNER", "You can only view your own guest profile."),
                        NOT_FOUND, VALIDATION)},
)
def get(body: GuestIdRequest, request: Request, db: Session = Depends(get_session),
        user: CurrentUser = Depends(require_role("guest", "host", "admin"))):
    return ok(svc.get_guest(db, user, body.guest_id), request)


@router.post(
    "/update", summary="Update your own guest profile",
    description="Only supplied fields change; preferences is replaced as a whole object. guest_id must match the "
                "token. saved_properties_count, booking_count and profile_created_datetime are not editable.",
    responses={**ok_doc(Envelope[GuestUpdatedOut]),
               **errors(*AUTH, ROLE_FORBIDDEN, NOT_OWNER, NOT_FOUND, EMAIL_EXISTS, VALIDATION,
                        (422, "FIELD_NOT_EDITABLE", "One or more fields cannot be changed.",
                         {"booking_count": "This field is not editable."}))},
)
def update(body: GuestUpdate, request: Request, db: Session = Depends(get_session),
           user: CurrentUser = Depends(require_role("guest"))):
    return ok(svc.update_guest(db, user, body), request)


@router.post(
    "/delete", status_code=204, summary="Delete your own guest profile",
    description="Soft delete: status deleted, email and phone anonymized, token revoked. Publishes `guest.deleted`; "
                "booking-service then cancels open reservations.",
    responses={204: {"description": "Deleted"}, **errors(*AUTH, ROLE_FORBIDDEN, NOT_OWNER, NOT_FOUND, VALIDATION, KAFKA_DOWN)},
)
def delete(body: GuestIdRequest, request: Request, db: Session = Depends(get_session),
           pub: Publisher = Depends(get_publisher), user: CurrentUser = Depends(require_role("guest"))):
    svc.delete_guest(db, pub, request, user, body.guest_id)
    return Response(status_code=204)


@router.post(
    "/search", summary="Search guests (host or admin)",
    description="q matches first or last name; location matches part of the location. Hosts get the public subset; "
                "admins also get email. page ≥ 1, page_size 1-100.",
    responses={**ok_doc(Envelope[GuestSearchPage]),
               **errors(*AUTH, ROLE_FORBIDDEN,
                        (422, "INVALID_FILTER", "One or more filters are invalid.",
                         {"page_size": "page_size must be between 1 and 100."}))},
)
def search(body: GuestSearch, request: Request, db: Session = Depends(get_session),
           user: CurrentUser = Depends(require_role("host", "admin"))):
    return ok(svc.search_guests(db, user, body), request)
