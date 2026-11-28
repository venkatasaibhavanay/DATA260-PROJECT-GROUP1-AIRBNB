"""Entity models. Column definitions mirror database/mysql/02_users.sql."""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import JSON, Date, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class Guest(Base):
    __tablename__ = "guests"

    guest_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(60))
    last_name: Mapped[str] = mapped_column(String(60))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    phone: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    location: Mapped[str] = mapped_column(String(120))
    profile_photo_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    preferences: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    saved_properties_count: Mapped[int] = mapped_column(Integer, default=0)
    booking_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active")
    profile_created_datetime: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_datetime: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Host(Base):
    __tablename__ = "hosts"

    host_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    phone: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    profile_photo_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(16), default="unverified")
    access_level: Mapped[str] = mapped_column(String(16), default="standard")
    response_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2), nullable=True)
    response_time_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    host_since: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_datetime: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_datetime: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Admin(Base):
    __tablename__ = "admins"

    admin_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    created_datetime: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class HostThreadResponse(Base):
    __tablename__ = "host_thread_responses"

    thread_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    host_id: Mapped[int] = mapped_column(Integer, index=True)
    guest_first_message_at: Mapped[datetime] = mapped_column(DateTime)
    host_first_reply_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
