from shared.kafka.topics import ALL_TOPICS, DOMAIN_TOPICS, dlq_topic

REQUIRED = {
    "property.viewed", "property.saved", "booking.requested", "booking.approved",
    "booking.cancelled", "message.sent", "review.created", "ai.requests",
    "debate.round.0", "debate.round.1", "debate.round.2", "ai.results",
}


def test_all_required_domain_topics_defined():
    assert set(DOMAIN_TOPICS) == REQUIRED


def test_every_topic_has_dlq():
    for t in DOMAIN_TOPICS:
        assert dlq_topic(t) in ALL_TOPICS
    assert len(ALL_TOPICS) == 2 * len(DOMAIN_TOPICS)
