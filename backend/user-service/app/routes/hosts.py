"""Host profile routes (API doc 6.3) and profile photo upload."""
from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.routes.openapi_docs import AUTH, EMAIL_EXISTS, KAFKA_DOWN, ROLE_FORBIDDEN, VALIDATION, errors, ok_doc
from app.schemas.users import (
    HostCreate, HostIdRequest, HostProfileOut, HostSignupOut, HostUpdate, HostUpdatedOut, PhotoOut,
)
from app.services import photos
from app.services import users as svc
from app.services.events import Publisher, get_publisher
from shared.auth import CurrentUser, get_current_user, require_role
from shared.responses import Envelope, ok

router = APIRouter(prefix="/hosts", tags=["hosts"])
photo_router = APIRouter(prefix="/users", tags=["profile photo"])

NOT_FOUND = (404, "HOST_NOT_FOUND", "Host not found.")


@router.post(
    "/create", status_code=201, response_model=Envelope[HostSignupOut], summary="Host signup",
    description="Creates a host account and returns a token. verification_status starts unverified, access_level "
                "standard, host_since today; response metrics start null. Publishes `user.registered` (entity host).",
    responses=errors(EMAIL_EXISTS, VALIDATION, KAFKA_DOWN),
)
def create(body: HostCreate, request: Request, db: Session = Depends(get_session),
           pub: Publisher = Depends(get_publisher)):
    return ok(svc.create_host(db, pub, request, body), request)


@router.post(
    "/get", summary="Read a host profile",
    description="Any signed-in user. email, phone and access_level only for the host themself and admins. "
                "response_rate and response_time_minutes are maintained by the user-host-metrics consumer.",
    responses={**ok_doc(Envelope[HostProfileOut]), **errors(*AUTH, NOT_FOUND, VALIDATION)},
)
def get(body: HostIdRequest, request: Request, db: Session = Depends(get_session),
        user: CurrentUser = Depends(get_current_user)):
    return ok(svc.get_host(db, user, body.host_id), request)


@router.post(
    "/update", summary="Update a host profile (own, or any as admin)",
    description="Hosts may edit name, email, phone and profile_photo_url. verification_status and access_level are "
                "admin only (403 FIELD_NOT_EDITABLE). response_rate, response_time and host_since are never editable.",
    responses={**ok_doc(Envelope[HostUpdatedOut]),
               **errors(*AUTH, ROLE_FORBIDDEN, (403, "NOT_PROFILE_OWNER", "You can only change your own profile."),
                        (403, "FIELD_NOT_EDITABLE", "One or more fields cannot be changed.",
                         {"verification_status": "This field is not editable."}),
                        NOT_FOUND, EMAIL_EXISTS, VALIDATION,
                        (422, "FIELD_NOT_EDITABLE", "One or more fields cannot be changed.",
                         {"host_since": "This field is not editable."}))},
)
def update(body: HostUpdate, request: Request, db: Session = Depends(get_session),
           user: CurrentUser = Depends(require_role("host", "admin"))):
    return ok(svc.update_host(db, user, body), request)


@photo_router.post(
    "/profile-photo", response_model=Envelope[PhotoOut], summary="Upload or replace your profile photo",
    description="multipart/form-data with `file`: JPEG or PNG up to 5 MB. Stored by role and id and served at the "
                "returned relative URL; no filesystem path is returned.",
    responses=errors(*AUTH, ROLE_FORBIDDEN, (413, "FILE_TOO_LARGE", "Photo must be 5 MB or smaller."),
                     (415, "UNSUPPORTED_MEDIA_TYPE", "Photo must be a JPEG or PNG image."),
                     (422, "INVALID_IMAGE", "The file is not a valid image.")),
)
async def upload_photo(request: Request, file: UploadFile = File(...), db: Session = Depends(get_session),
                       user: CurrentUser = Depends(require_role("guest", "host"))):
    data = await file.read(photos.MAX_BYTES + 1)
    url = photos.save_profile_photo(user.role, int(user.user_id), file.content_type, data)
    svc.set_photo_url(db, user, url)
    return ok({"profile_photo_url": url}, request)
