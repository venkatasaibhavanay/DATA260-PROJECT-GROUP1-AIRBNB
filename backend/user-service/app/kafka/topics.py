"""Kafka topics this service is planned to produce and consume.

Topic names are defined centrally in shared/kafka/topics.py.
Every message must be a validated shared.kafka.EventEnvelope.
"""
PRODUCES: list[str] = []
CONSUMES: list[str] = []
