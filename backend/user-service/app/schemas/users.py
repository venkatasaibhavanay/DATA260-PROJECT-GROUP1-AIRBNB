"""Request/response schemas for user-service (API doc sections 4 and 6)."""
import re
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    model_config = ConfigDict(json_schema_extra={"examples": [{"email": "maya.chen@example.com", "password": "StrongPass1!", "role": "guest"}]})

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
    model_config = ConfigDict(json_schema_extra={"examples": [{"first_name": "Maya", "last_name": "Chen", "email": "maya.chen@example.com", "password": "StrongPass1!", "phone": "+14085550101", "location": "San Jose, CA", "preferences": {"preferred_locations": ["San Jose"], "budget_max": "250.00", "amenities": ["parking", "kitchen"], "property_types": ["apartment"], "travel_purpose": "business"}}]})

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
    model_config = ConfigDict(json_schema_extra={"examples": [{"guest_id": 1001}]})

    guest_id: int = Field(ge=1)


class GuestUpdate(StrictModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"guest_id": 1001, "phone": "+14085550102", "location": "Sunnyvale, CA", "preferences": {"budget_max": "300.00", "amenities": ["parking", "kitchen", "wifi"]}}]})

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
    model_config = ConfigDict(json_schema_extra={"examples": [{"q": "chen", "location": "San Jose", "page": 1, "page_size": 20}]})

    q: Optional[str] = None
    location: Optional[str] = None
    page: int = 1
    page_size: int = 20


# ---------- hosts ----------

class HostCreate(StrictModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"name": "Daniel Ortiz", "email": "daniel.ortiz@example.com", "password": "StrongPass1!", "phone": "+14085550199"}]})

    name: str = Field(min_length=1, max_length=120)
    email: str
    password: str = Field(max_length=128)
    phone: Optional[str] = None

    _e = field_validator("email")(_email)
    _p = field_validator("phone")(_phone)


class HostIdRequest(StrictModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"host_id": 501}]})

    host_id: int = Field(ge=1)


class HostUpdate(StrictModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"host_id": 501, "name": "Daniel Ortiz", "phone": "+14085550198"}]})

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


# ---------- documented response shapes (Swagger) ----------

class GuestProfileOut(BaseModel):
    """Own profile and admins: every field. Hosts: only guest_id, first_name, last_name initial,
    location, profile_photo_url and profile_created_datetime (other keys are omitted, not null)."""
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "guest_id": 1001, "first_name": "Maya", "last_name": "Chen", "email": "maya.chen@example.com",
        "phone": "+14085550101", "location": "San Jose, CA", "profile_photo_url": "/media/profiles/guests/1001.jpg",
        "preferences": {"preferred_locations": ["San Jose"], "budget_max": "250.00", "amenities": ["parking", "kitchen"],
                        "property_types": ["apartment"], "travel_purpose": "business"},
        "saved_properties_count": 4, "booking_count": 2, "profile_created_datetime": "2026-11-02T18:30:00Z"}]})

    guest_id: int
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    location: str
    profile_photo_url: Optional[str] = None
    preferences: Optional[dict] = None
    saved_properties_count: Optional[int] = None
    booking_count: Optional[int] = None
    profile_created_datetime: datetime


class GuestSearchItem(BaseModel):
    guest_id: int
    first_name: str
    last_name: str = Field(examples=["C."])
    location: str
    profile_photo_url: Optional[str] = None
    email: Optional[str] = Field(default=None, description="Admins only")


class GuestSearchPage(BaseModel):
    items: list[GuestSearchItem]
    page: int
    page_size: int
    total: int
    total_pages: int


class GuestUpdatedOut(BaseModel):
    guest_id: int
    updated_datetime: datetime


class HostProfileOut(BaseModel):
    """email, phone and access_level are returned only to the host themself and to admins."""
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "host_id": 501, "name": "Daniel Ortiz", "email": "daniel.ortiz@example.com", "phone": "+14085550199",
        "profile_photo_url": "/media/profiles/hosts/501.jpg", "verification_status": "verified",
        "response_rate": "0.96", "response_time_minutes": 42, "host_since": "2026-11-02", "access_level": "standard"}]})

    host_id: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    profile_photo_url: Optional[str] = None
    verification_status: VerificationStatus
    response_rate: Optional[str] = Field(default=None, description="Decimal string 0.00-1.00; null until measured")
    response_time_minutes: Optional[int] = None
    host_since: date
    access_level: Optional[AccessLevel] = None


class HostUpdatedOut(BaseModel):
    host_id: int
    updated_datetime: datetime
