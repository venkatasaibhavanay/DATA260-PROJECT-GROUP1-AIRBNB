"""Data access for guests, hosts and admins."""
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.models import Admin, Guest, Host, HostThreadResponse


def utcnow() -> datetime:
    """Naive UTC, matching the DATETIME columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------- guests ----------

def get_guest(db: Session, guest_id: int, *, include_deleted: bool = False) -> Optional[Guest]:
    guest = db.get(Guest, guest_id)
    if guest is None or (guest.status == "deleted" and not include_deleted):
        return None
    return guest


def get_guest_by_email(db: Session, email: str) -> Optional[Guest]:
    return db.scalar(select(Guest).where(Guest.email == email))


def add_guest(db: Session, **fields) -> Guest:
    now = utcnow()
    guest = Guest(profile_created_datetime=now, updated_datetime=now, status="active",
                  saved_properties_count=0, booking_count=0, **fields)
    db.add(guest)
    db.flush()  # assigns guest_id
    return guest


def search_guests(db: Session, q: Optional[str], location: Optional[str],
                  page: int, page_size: int) -> tuple[list[Guest], int]:
    stmt = select(Guest).where(Guest.status == "active")
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Guest.first_name).like(like), func.lower(Guest.last_name).like(like)))
    if location:
        stmt = stmt.where(func.lower(Guest.location).like(f"%{location.lower()}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Guest.guest_id).offset((page - 1) * page_size).limit(page_size)).all()
    return list(rows), int(total)


def adjust_guest_counter(db: Session, guest_id: int, column: str, delta: int) -> int:
    """Atomically add delta to a counter, never below 0. Returns rows matched."""
    col = getattr(Guest, column)
    new_value = func.max(col + delta, 0) if db.bind.dialect.name == "sqlite" else func.greatest(col + delta, 0)
    res = db.execute(update(Guest).where(Guest.guest_id == guest_id).values({column: new_value}))
    return res.rowcount


# ---------- hosts ----------

def get_host(db: Session, host_id: int) -> Optional[Host]:
    host = db.get(Host, host_id)
    return None if host is None or host.status == "deleted" else host


def get_host_by_email(db: Session, email: str) -> Optional[Host]:
    return db.scalar(select(Host).where(Host.email == email))


def add_host(db: Session, **fields) -> Host:
    now = utcnow()
    host = Host(host_since=date.today(), created_datetime=now, updated_datetime=now, status="active",
                verification_status="unverified", access_level="standard",
                response_rate=None, response_time_minutes=None, **fields)
    db.add(host)
    db.flush()
    return host


# ---------- admins ----------

def get_admin(db: Session, admin_id: int) -> Optional[Admin]:
    return db.get(Admin, admin_id)


def get_admin_by_email(db: Session, email: str) -> Optional[Admin]:
    return db.scalar(select(Admin).where(Admin.email == email))


# ---------- host response metrics ----------

def get_thread_response(db: Session, thread_id: str) -> Optional[HostThreadResponse]:
    return db.get(HostThreadResponse, thread_id)


def add_thread_response(db: Session, thread_id: str, host_id: int, guest_first_message_at: datetime) -> None:
    db.add(HostThreadResponse(thread_id=thread_id, host_id=host_id,
                              guest_first_message_at=guest_first_message_at))
    db.flush()


def recent_thread_responses(db: Session, host_id: int, days: int = 30) -> list[HostThreadResponse]:
    since = utcnow() - timedelta(days=days)
    return list(db.scalars(select(HostThreadResponse).where(
        HostThreadResponse.host_id == host_id,
        HostThreadResponse.guest_first_message_at >= since,
    )).all())
