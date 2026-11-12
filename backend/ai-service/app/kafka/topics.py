"""Kafka topics this service is planned to produce and consume.

Topic names are defined centrally in shared/kafka/topics.py.
Every message must be a validated shared.kafka.EventEnvelope.
"""
PRODUCES: list[str] = ['debate.round.0', 'debate.round.1', 'debate.round.2', 'ai.results']
CONSUMES: list[str] = ['ai.requests', 'debate.round.0', 'debate.round.1', 'debate.round.2', 'property.viewed', 'property.saved']
