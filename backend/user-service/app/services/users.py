"""Business rules for accounts and profiles (API doc section 6)."""
from datetime import timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Guest, Host
from app.repositories import users as repo
from app.schemas.users import (
    GuestCreate, GuestSearch, GuestUpdate, HostCreate, HostUpdate, LoginRequest,
)
from app.services import rate_limit
from app.services.events import Publisher, publish_guest_deleted, publish_user_registered
from app.services.security import DUMMY_HASH, hash_password, password_problem, verify_password
from shared.auth import CurrentUser, create_access_token, revoke_token
from shared.errors import AppError
from shared.schemas import make_page


# ---------- helpers ----------

def _z(dt):
    """Naive-UTC DB value -> aware UTC (serializes with Z/+00:00)."""
    return None if dt is None else dt.replace(tzinfo=timezone.utc)


def _token(user_id: int, role: str) -> dict:
    return {
        "access_token": create_access_token(user_id, role),
        "token_type": "bearer",
        "expires_in": settings.jwt_expiry_minutes * 60,
    }


def _check_password(password: str) -> None:
    problem = password_problem(password)
    if problem:
        raise AppError(422, "VALIDATION_ERROR", "One or more fields are invalid.", fields={"password": problem})


def _email_taken() -> AppError:
    return AppError(409, "EMAIL_ALREADY_EXISTS", "An account with this email already exists.",
                    fields={"email": "Email is already registered."})


def _not_editable(names: set[str], status: int = 422) -> AppError:
    return AppError(status, "FIELD_NOT_EDITABLE", "One or more fields cannot be changed.",
                    fields={n: "This field is not editable." for n in sorted(names)})


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _email_taken() from None


def guest_full(g: Guest) -> dict:
    return {
        "guest_id": g.guest_id, "first_name": g.first_name, "last_name": g.last_name,
        "email": g.email, "phone": g.phone, "location": g.location,
        "profile_photo_url": g.profile_photo_url, "preferences": g.preferences or {},
        "saved_properties_count": g.saved_properties_count, "booking_count": g.booking_count,
        "profile_created_datetime": _z(g.profile_created_datetime),
    }


def guest_public(g: Guest, *, with_email: bool = False) -> dict:
    out = {
        "guest_id": g.guest_id, "first_name": g.first_name,
        "last_name": f"{g.last_name[:1]}." if g.last_name else "",
        "location": g.location, "profile_photo_url": g.profile_photo_url,
        "profile_created_datetime": _z(g.profile_created_datetime),
    }
    if with_email:
        out["email"] = g.email
    return out


def host_view(h: Host, *, private: bool) -> dict:
    out = {
        "host_id": h.host_id, "name": h.name, "profile_photo_url": h.profile_photo_url,
        "verification_status": h.verification_status,
        "response_rate": None if h.response_rate is None else f"{Decimal(h.response_rate):.2f}",
        "response_time_minutes": h.response_time_minutes, "host_since": h.host_since,
    }
    if private:
        out.update({"email": h.email, "phone": h.phone, "access_level": h.access_level})
    return out


# ---------- auth ----------

def login(db: Session, body: LoginRequest) -> dict:
    if rate_limit.is_locked(body.email):
        raise AppError(429, "RATE_LIMITED", "Too many failed sign-in attempts. Try again in 15 minutes.")

    account, user_id, name = None, None, None
    if body.role == "guest":
        account = repo.get_guest_by_email(db, body.email)
        if account and account.status == "active":
            user_id, name = account.guest_id, f"{account.first_name} {account.last_name}"
    elif body.role == "host":
        account = repo.get_host_by_email(db, body.email)
        if account and account.status == "active":
            user_id, name = account.host_id, account.name
    else:
        account = repo.get_admin_by_email(db, body.email)
        if account:
            user_id, name = account.admin_id, account.name

    valid = verify_password(body.password, account.password_hash if user_id else DUMMY_HASH)
    if not (user_id and valid):
        rate_limit.record_failure(body.email)
        raise AppError(401, "INVALID_CREDENTIALS", "Email or password is incorrect.")

    rate_limit.clear(body.email)
    return {**_token(user_id, body.role),
            "user": {"id": user_id, "role": body.role, "name": name, "email": account.email}}


def me(db: Session, user: CurrentUser) -> dict:
    uid = int(user.user_id)
    if user.role == "guest" and (g := repo.get_guest(db, uid)):
        return {"id": uid, "role": "guest", "name": f"{g.first_name} {g.last_name}", "email": g.email}
    if user.role == "host" and (h := repo.get_host(db, uid)):
        return {"id": uid, "role": "host", "name": h.name, "email": h.email}
    if user.role == "admin" and (a := repo.get_admin(db, uid)):
        return {"id": uid, "role": "admin", "name": a.name, "email": a.email}
    raise AppError(401, "UNAUTHORIZED", "Missing or invalid token.")


# ---------- guests ----------

def create_guest(db: Session, pub: Publisher, request: Request, body: GuestCreate) -> dict:
    _check_password(body.password)
    if repo.get_guest_by_email(db, body.email):
        raise _email_taken()
    prefs = body.preferences.model_dump(mode="json", exclude_none=True) if body.preferences else None
    try:
        guest = repo.add_guest(db, first_name=body.first_name, last_name=body.last_name, email=body.email,
                               password_hash=hash_password(body.password), phone=body.phone,
                               location=body.location, preferences=prefs)
    except IntegrityError:
        db.rollback()
        raise _email_taken() from None
    try:
        publish_user_registered(pub, request, role="guest", user_id=guest.guest_id,
                                created=guest.profile_created_datetime, location=guest.location)
    except Exception:
        db.rollback()
        raise
    _commit(db)
    full = guest_full(guest)
    summary = {k: full[k] for k in ("guest_id", "first_name", "last_name", "email",
                                    "saved_properties_count", "booking_count", "profile_created_datetime")}
    return {**_token(guest.guest_id, "guest"), "guest": summary}


def get_guest(db: Session, user: CurrentUser, guest_id: int) -> dict:
    if user.role == "guest" and int(user.user_id) != guest_id:
        raise AppError(403, "NOT_PROFILE_OWNER", "You can only view your own guest profile.")
    guest = repo.get_guest(db, guest_id)
    if guest is None:
        raise AppError(404, "GUEST_NOT_FOUND", "Guest not found.")
    if user.role in ("guest", "admin"):
        return guest_full(guest)
    return guest_public(guest)


def _own_guest(db: Session, user: CurrentUser, guest_id: int) -> Guest:
    if int(user.user_id) != guest_id:
        raise AppError(403, "NOT_PROFILE_OWNER", "You can only change your own profile.")
    guest = repo.get_guest(db, guest_id)
    if guest is None:
        raise AppError(404, "GUEST_NOT_FOUND", "Guest not found.")
    return guest


def update_guest(db: Session, user: CurrentUser, body: GuestUpdate) -> dict:
    sent = body.model_fields_set - {"guest_id"}
    locked = sent & {"saved_properties_count", "booking_count", "profile_created_datetime"}
    if locked:
        raise _not_editable(locked)
    guest = _own_guest(db, user, body.guest_id)

    required = {f for f in ("first_name", "last_name", "email", "location") if f in sent and getattr(body, f) is None}
    if required:
        raise AppError(422, "VALIDATION_ERROR", "One or more fields are invalid.",
                       fields={f: "This field cannot be null." for f in required})
    if "email" in sent and body.email != guest.email:
        other = repo.get_guest_by_email(db, body.email)
        if other and other.guest_id != guest.guest_id:
            raise _email_taken()

    for f in ("first_name", "last_name", "email", "phone", "location", "profile_photo_url"):
        if f in sent:
            value = getattr(body, f)
            setattr(guest, f, value.strip() if isinstance(value, str) and f != "profile_photo_url" else value)
    if "preferences" in sent:  # replaced as a whole object
        guest.preferences = body.preferences.model_dump(mode="json", exclude_none=True) if body.preferences else None
    guest.updated_datetime = repo.utcnow()
    _commit(db)
    return {"guest_id": guest.guest_id, "updated_datetime": _z(guest.updated_datetime)}


def delete_guest(db: Session, pub: Publisher, request: Request, user: CurrentUser, guest_id: int) -> None:
    guest = _own_guest(db, user, guest_id)
    now = repo.utcnow()
    guest.status = "deleted"
    guest.email = f"deleted+{guest.guest_id}@deleted.invalid"
    guest.phone = None
    guest.preferences = None
    guest.deleted_datetime = now
    guest.updated_datetime = now
    try:
        publish_guest_deleted(pub, request, guest_id=guest.guest_id, deleted=now)
    except Exception:
        db.rollback()
        raise
    db.commit()
    revoke_token(user)


def search_guests(db: Session, user: CurrentUser, body: GuestSearch) -> dict:
    bad = {}
    if body.page < 1:
        bad["page"] = "page must be 1 or greater."
    if not 1 <= body.page_size <= 100:
        bad["page_size"] = "page_size must be between 1 and 100."
    for f in ("q", "location"):
        v = getattr(body, f)
        if v is not None and len(v) > 100:
            bad[f] = f"{f} must be at most 100 characters."
    if bad:
        raise AppError(422, "INVALID_FILTER", "One or more filters are invalid.", fields=bad)
    q = (body.q or "").strip() or None
    loc = (body.location or "").strip() or None
    rows, total = repo.search_guests(db, q, loc, body.page, body.page_size)
    items = [guest_public(g, with_email=user.role == "admin") for g in rows]
    for item in items:
        item.pop("profile_created_datetime", None)
    return make_page(items, body.page, body.page_size, total).model_dump()


# ---------- hosts ----------

def create_host(db: Session, pub: Publisher, request: Request, body: HostCreate) -> dict:
    _check_password(body.password)
    name = body.name.strip()
    if not name:
        raise AppError(422, "VALIDATION_ERROR", "One or more fields are invalid.", fields={"name": "This field is required."})
    if repo.get_host_by_email(db, body.email):
        raise _email_taken()
    try:
        host = repo.add_host(db, name=name, email=body.email, password_hash=hash_password(body.password),
                             phone=body.phone)
    except IntegrityError:
        db.rollback()
        raise _email_taken() from None
    try:
        publish_user_registered(pub, request, role="host", user_id=host.host_id, created=host.created_datetime)
    except Exception:
        db.rollback()
        raise
    _commit(db)
    return {**_token(host.host_id, "host"),
            "host": {"host_id": host.host_id, "name": host.name, "verification_status": host.verification_status,
                     "access_level": host.access_level, "host_since": host.host_since}}


def get_host(db: Session, user: CurrentUser, host_id: int) -> dict:
    host = repo.get_host(db, host_id)
    if host is None:
        raise AppError(404, "HOST_NOT_FOUND", "Host not found.")
    private = user.role == "admin" or (user.role == "host" and int(user.user_id) == host_id)
    return host_view(host, private=private)


def update_host(db: Session, user: CurrentUser, body: HostUpdate) -> dict:
    sent = body.model_fields_set - {"host_id"}
    never = sent & {"response_rate", "response_time", "response_time_minutes", "host_since"}
    if never:
        raise _not_editable(never)
    is_admin = user.role == "admin"
    if not is_admin:
        if int(user.user_id) != body.host_id:
            raise AppError(403, "NOT_PROFILE_OWNER", "You can only change your own profile.")
        admin_only = sent & {"verification_status", "access_level"}
        if admin_only:
            raise _not_editable(admin_only, status=403)
    host = repo.get_host(db, body.host_id)
    if host is None:
        raise AppError(404, "HOST_NOT_FOUND", "Host not found.")

    nulls = {f for f in ("name", "email", "verification_status", "access_level") if f in sent and getattr(body, f) is None}
    if nulls:
        raise AppError(422, "VALIDATION_ERROR", "One or more fields are invalid.",
                       fields={f: "This field cannot be null." for f in nulls})
    if "email" in sent and body.email != host.email:
        other = repo.get_host_by_email(db, body.email)
        if other and other.host_id != host.host_id:
            raise _email_taken()
    for f in ("name", "email", "phone", "profile_photo_url", "verification_status", "access_level"):
        if f in sent:
            value = getattr(body, f)
            setattr(host, f, value.strip() if f == "name" else value)
    host.updated_datetime = repo.utcnow()
    _commit(db)
    return {"host_id": host.host_id, "updated_datetime": _z(host.updated_datetime)}


def set_photo_url(db: Session, user: CurrentUser, url: str) -> None:
    uid = int(user.user_id)
    entity: Optional[Any] = repo.get_guest(db, uid) if user.role == "guest" else repo.get_host(db, uid)
    if entity is None:
        raise AppError(404, "GUEST_NOT_FOUND" if user.role == "guest" else "HOST_NOT_FOUND", "Profile not found.")
    entity.profile_photo_url = url
    entity.updated_datetime = repo.utcnow()
    db.commit()
