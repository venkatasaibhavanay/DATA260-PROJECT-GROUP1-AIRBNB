from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, PositiveInt


class OpenThreadRequest(BaseModel):
    property_id: PositiveInt
    guest_id: PositiveInt | None = None
    reservation_id: UUID | None = None


class ThreadResponse(BaseModel):
    thread_id: str
    property_id: int
    guest_id: int
    host_id: int
    reservation_id: UUID | None = None
    created_datetime: datetime
    last_message_at: datetime | None = None
    unread_count: int = 0