"""Request/response schemas for user-service (API doc sections 4 and 6)."""
import re
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from shared.schemas import Money, StrictModel

Amenity = Literal["wifi", "kitchen", "parking", "washer", "air_conditioning", "heating", "pool",
                  "pet_friendly", "workspace", "tv", "hot_tub", "ev_charger"]
PropertyType = Literal["apartment", "house", "condo", "cabin", "private_room", "shared_room"]
LoginRole = Literal["guest", "host", "admin"]
VerificationStatus = Literal["unverified", "pending", "verified"]
AccessLevel = Literal["standard", "superhost", "suspended"]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+[1-9]\d{1,14}$")


def _email(v: str) -> str:
    v = v.strip().lower()
    if len(v) > 254 or not EMAIL_RE.match(v):
        raise ValueError("Enter a valid email address.")
    return v


def _phone(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    if not PHONE_RE.match(v):
        raise ValueError("Phone must be in E.164 format, for example +14085550101.")
    return v


def _unique(v: Optional[list]) -> Optional[list]:
    if v is not None and len(set(v)) != len(v):
        raise ValueError("Values must be unique.")
    return v


class Preferences(StrictModel):
    preferred_locations: Optional[list[str]] = Field(default=None, max_length=10)
    budget_max: Optional[Money] = None
    amenities: Optional[list[Amenity]] = None
    property_types: Optional[list[PropertyType]] = None
    travel_purpose: Optional[str] = Field(default=None, max_length=40)

    _u = field_validator("amenities", "property_types", "preferred_locations")(_unique)


# ---------- auth ----------

class LoginRequest(StrictModel):
    email: str
    password: str = Field(min_length=1, max_length=128)
    role: LoginRole

    _e = field_validator("email")(_email)


class AuthUser(BaseModel):
    id: int
    role: str
    name: str
    email: str


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class LoginOut(TokenOut):
    user: AuthUser


# ---------- guests ----------

class GuestCreate(StrictModel):
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    email: str
    password: str = Field(max_length=128)
    phone: Optional[str] = None
    location: str = Field(min_length=1, max_length=120)
    preferences: Optional[Preferences] = None

    _e = field_validator("email")(_email)
    _p = field_validator("phone")(_phone)

    @field_validator("first_name", "last_name", "location")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("This field is required.")
        return v


class GuestIdRequest(StrictModel):
    guest_id: int = Field(ge=1)


class GuestUpdate(StrictModel):
    guest_id: int = Field(ge=1)
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = Field(default=None, min_length=1, max_length=120)
    profile_photo_url: Optional[str] = Field(default=None, max_length=255)
    preferences: Optional[Preferences] = None
    # Not editable: present only so we can answer 422 FIELD_NOT_EDITABLE.
    saved_properties_count: Optional[int] = None
    booking_count: Optional[int] = None
    profile_created_datetime: Optional[str] = None

    _e = field_validator("email")(lambda v: None if v is None else _email(v))
    _p = field_validator("phone")(_phone)


class GuestSummary(BaseModel):
    guest_id: int
    first_name: str
    last_name: str
    email: str
    saved_properties_count: int
    booking_count: int
    profile_created_datetime: datetime


class GuestSignupOut(TokenOut):
    guest: GuestSummary


class GuestSearch(StrictModel):
    q: Optional[str] = None
    location: Optional[str] = None
    page: int = 1
    page_size: int = 20


# ---------- hosts ----------

class HostCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    email: str
    password: str = Field(max_length=128)
    phone: Optional[str] = None

    _e = field_validator("email")(_email)
    _p = field_validator("phone")(_phone)


class HostIdRequest(StrictModel):
    host_id: int = Field(ge=1)


class HostUpdate(StrictModel):
    host_id: int = Field(ge=1)
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    email: Optional[str] = None
    phone: Optional[str] = None
    profile_photo_url: Optional[str] = Field(default=None, max_length=255)
    verification_status: Optional[VerificationStatus] = None  # admin only
    access_level: Optional[AccessLevel] = None                # admin only
    # Never editable: present only so we can answer FIELD_NOT_EDITABLE.
    response_rate: Optional[str] = None
    response_time: Optional[int] = None
    response_time_minutes: Optional[int] = None
    host_since: Optional[date] = None

    _e = field_validator("email")(lambda v: None if v is None else _email(v))
    _p = field_validator("phone")(_phone)


class HostSummary(BaseModel):
    host_id: int
    name: str
    verification_status: str
    access_level: str
    host_since: date


class HostSignupOut(TokenOut):
    host: HostSummary


class UpdatedOut(BaseModel):
    updated_datetime: datetime


class PhotoOut(BaseModel):
    profile_photo_url: str
