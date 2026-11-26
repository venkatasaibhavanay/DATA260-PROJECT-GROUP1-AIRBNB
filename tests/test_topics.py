from shared.kafka.topics import ALL_TOPICS, DOMAIN_TOPICS, dlq_topic

REQUIRED = [
    "user.registered",
    "guest.deleted",
    "property.created",
    "property.updated",
    "property.deleted",
    "property.viewed",
    "property.saved",
    "property.unsaved",
    "availability.updated",
    "booking.requested",
    "booking.pending",
    "booking.rejected",
    "booking.approved",
    "booking.declined",
    "booking.cancelled",
    "message.sent",
    "message.read",
    "review.created",
    "review.responded",
    "ai.requests",
    "ai.parsed",
    "debate.round.0",
    "debate.round.1",
    "debate.round.2",
    "ai.results",
    "ai.decisions",
]


def test_all_required_domain_topics_defined():
    assert DOMAIN_TOPICS == REQUIRED  # exact list, exact order
    assert len(REQUIRED) == 26


def test_every_topic_has_dlq():
    for t in DOMAIN_TOPICS:
        assert dlq_topic(t) in ALL_TOPICS
    assert len(ALL_TOPICS) == 2 * len(DOMAIN_TOPICS)


def test_every_topic_has_a_constant():
    from shared.kafka import topics

    for t in DOMAIN_TOPICS:
        assert getattr(topics, t.upper().replace(".", "_")) == t
