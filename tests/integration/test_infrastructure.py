"""Checks the running Docker infrastructure. Run with: ./scripts/run-tests.sh --integration"""
import os

import pytest

from shared.config import InfraSettings
from shared.dependencies import check_dependencies
from shared.kafka.topics import ALL_TOPICS

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="set RUN_INTEGRATION=1"),
]

settings = InfraSettings()


@pytest.mark.parametrize("dep", ["mysql", "mongodb", "redis", "kafka"])
def test_dependency_reachable(dep):
    result = check_dependencies(settings, [dep])[dep]
    assert result["status"] == "ok", result["detail"]


def test_redis_cache_round_trip():
    import redis

    r = redis.Redis(host=settings.redis_host, port=settings.redis_port,
                    password=settings.redis_password or None, decode_responses=True)
    r.set("g1:selftest", "ok", ex=30)
    assert r.get("g1:selftest") == "ok"
    r.delete("g1:selftest")


def test_kafka_topics_created():
    from kafka import KafkaAdminClient

    admin = KafkaAdminClient(bootstrap_servers=settings.kafka_bootstrap_servers)
    try:
        missing = set(ALL_TOPICS) - set(admin.list_topics())
    finally:
        admin.close()
    assert not missing, f"missing topics: {sorted(missing)}"


def test_kafka_publish_and_consume_envelope():
    from kafka import KafkaConsumer

    from shared.kafka import decode_event, new_event
    from shared.kafka.producer import EnvelopeProducer

    topic = "ai.requests"
    env = new_event(topic, actor_id="selftest", entity_type="selftest", entity_id="g1-selftest")
    consumer = KafkaConsumer(topic, bootstrap_servers=settings.kafka_bootstrap_servers,
                             group_id=None, auto_offset_reset="latest",
                             consumer_timeout_ms=10000)
    consumer.poll(timeout_ms=2000)  # join + get assignment before producing
    producer = EnvelopeProducer(settings.kafka_bootstrap_servers)
    try:
        producer.publish(topic, env)
        received = [decode_event(m.value) for m in consumer]
    finally:
        producer.close()
        consumer.close()
    assert any(e.trace_id == env.trace_id for e in received)
