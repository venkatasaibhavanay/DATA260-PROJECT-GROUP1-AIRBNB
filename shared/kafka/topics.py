"""Kafka topic names. The list lives in topics.txt so shell scripts can share it."""
from pathlib import Path

DLQ_SUFFIX = ".dlq"

USER_REGISTERED = "user.registered"
GUEST_DELETED = "guest.deleted"
PROPERTY_CREATED = "property.created"
PROPERTY_UPDATED = "property.updated"
PROPERTY_DELETED = "property.deleted"
PROPERTY_VIEWED = "property.viewed"
PROPERTY_SAVED = "property.saved"
PROPERTY_UNSAVED = "property.unsaved"
AVAILABILITY_UPDATED = "availability.updated"
BOOKING_REQUESTED = "booking.requested"
BOOKING_PENDING = "booking.pending"
BOOKING_REJECTED = "booking.rejected"
BOOKING_APPROVED = "booking.approved"
BOOKING_DECLINED = "booking.declined"
BOOKING_CANCELLED = "booking.cancelled"
MESSAGE_SENT = "message.sent"
MESSAGE_READ = "message.read"
REVIEW_CREATED = "review.created"
REVIEW_RESPONDED = "review.responded"
AI_REQUESTS = "ai.requests"
AI_PARSED = "ai.parsed"
DEBATE_ROUND_0 = "debate.round.0"
DEBATE_ROUND_1 = "debate.round.1"
DEBATE_ROUND_2 = "debate.round.2"
AI_RESULTS = "ai.results"
AI_DECISIONS = "ai.decisions"


def _load() -> list[str]:
    lines = (Path(__file__).with_name("topics.txt")).read_text().splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


DOMAIN_TOPICS: list[str] = _load()


def dlq_topic(topic: str) -> str:
    """Dead-letter topic for messages from `topic` that fail validation/processing."""
    return f"{topic}{DLQ_SUFFIX}"


ALL_TOPICS: list[str] = DOMAIN_TOPICS + [dlq_topic(t) for t in DOMAIN_TOPICS]
