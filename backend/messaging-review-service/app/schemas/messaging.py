from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, PositiveInt
from pydantic import Field

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

class GetThreadRequest(BaseModel):
    thread_id: str

class ThreadsByUserRequest(BaseModel):
    unread_only: bool = False
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

class ListMessagesRequest(BaseModel):
    thread_id: str
    before: datetime | None = None
    limit: int = Field(default=50, ge=1, le=100)

class SendMessageRequest(BaseModel):
    thread_id: str
    message_text: str = Field(
        min_length=1,
        max_length=2000,
    )

class MarkMessagesReadRequest(BaseModel):
    thread_id: str
    up_to_message_id: str

class CreateReviewRequest(BaseModel):
    reservation_id: UUID
    rating: int = Field(
        ge=1,
        le=5,
    )
    review_text: str = Field(
        min_length=10,
        max_length=2000,
    )