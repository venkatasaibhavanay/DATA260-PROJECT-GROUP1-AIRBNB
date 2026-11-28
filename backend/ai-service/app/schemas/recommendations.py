# backend/ai-service/app/schemas/recommendations.py
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RecommendationSchema(BaseModel):
    # Catch misspelled fields and trim whitespace before validating text.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class StayDates(RecommendationSchema):
    check_in: date
    check_out: date

    @model_validator(mode="after")
    def validate_date_order(self) -> Self:
        if self.check_out <= self.check_in:
            raise ValueError("Check-out must be after check-in.")
        return self


class RecommendationRequest(StayDates):
    """Request body for POST /api/v1/ai/requests."""

    text: str = Field(min_length=1, max_length=2000)


class GuestRequirements(StayDates):
    """Structured requirements published by the parser on ai.parsed."""

    city: str = Field(min_length=1)
    guests: int = Field(ge=1)
    nightly_price_ceiling: Decimal = Field(gt=0, decimal_places=2)
    amenities: list[str] = Field(default_factory=list)
    minimum_rating: Decimal | None = Field(default=None, ge=0, le=5)


class RecommendationStatus(str, Enum):
    QUEUED = "queued"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    NEEDS_CLARIFICATION = "needs_clarification"
    PENDING_REVIEW = "pending_review"
    NO_MATCH = "no_match"
    APPROVED = "approved"
    REJECTED = "rejected"


class RecommendationAccepted(RecommendationSchema):
    """Response returned after the request is published to Kafka."""

    task_id: UUID
    status: RecommendationStatus = RecommendationStatus.QUEUED


class ReviewDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class RecommendationDecision(RecommendationSchema):
    """Request body for POST /api/v1/ai/requests/{task_id}/decision."""

    proposal_event_id: UUID
    decision: ReviewDecision
    reason: str = Field(min_length=1, max_length=1000)
    edited_property_id: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_edit(self) -> Self:
        if self.edited_property_id and self.decision != ReviewDecision.APPROVED:
            raise ValueError("A revised property can only accompany approval.")
        return self