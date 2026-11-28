"""Host profile routes (API doc 6.3) and profile photo upload."""
from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.schemas.users import HostCreate, HostIdRequest, HostSignupOut, HostUpdate, PhotoOut
from app.services import photos
from app.services import users as svc
from app.services.events import Publisher, get_publisher
from shared.auth import CurrentUser, get_current_user, require_role
from shared.responses import Envelope, ok

router = APIRouter(prefix="/hosts", tags=["hosts"])
photo_router = APIRouter(prefix="/users", tags=["profile photo"])


@router.post("/create", status_code=201, response_model=Envelope[HostSignupOut], summary="Host signup")
def create(body: HostCreate, request: Request, db: Session = Depends(get_session),
           pub: Publisher = Depends(get_publisher)):
    return ok(svc.create_host(db, pub, request, body), request)


@router.post("/get", summary="Read a host profile (email/phone/access_level only for self or admin)")
def get(body: HostIdRequest, request: Request, db: Session = Depends(get_session),
        user: CurrentUser = Depends(get_current_user)):
    return ok(svc.get_host(db, user, body.host_id), request)


@router.post("/update", summary="Update a host profile (own, or any as admin)")
def update(body: HostUpdate, request: Request, db: Session = Depends(get_session),
           user: CurrentUser = Depends(require_role("host", "admin"))):
    return ok(svc.update_host(db, user, body), request)


@photo_router.post("/profile-photo", response_model=Envelope[PhotoOut], summary="Upload or replace your photo")
async def upload_photo(request: Request, file: UploadFile = File(...), db: Session = Depends(get_session),
                       user: CurrentUser = Depends(require_role("guest", "host"))):
    data = await file.read(photos.MAX_BYTES + 1)
    url = photos.save_profile_photo(user.role, int(user.user_id), file.content_type, data)
    svc.set_photo_url(db, user, url)
    return ok({"profile_photo_url": url}, request)
