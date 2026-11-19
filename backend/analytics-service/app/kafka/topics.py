"""Kafka topics this service is planned to produce and consume.

Topic names are defined centrally in shared/kafka/topics.py.
Every message must be a validated shared.kafka.EventEnvelope.
"""
from shared.kafka.topics import ALL_TOPICS

PRODUCES: list[str] = []
# Every domain topic plus every .dlq topic.
CONSUMES: list[str] = list(ALL_TOPICS)
