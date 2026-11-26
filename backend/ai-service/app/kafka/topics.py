"""Kafka topics this service is planned to produce and consume.

Topic names are defined centrally in shared/kafka/topics.py.
Every message must be a validated shared.kafka.EventEnvelope.
"""
PRODUCES: list[str] = ['ai.requests', 'ai.parsed', 'debate.round.0', 'debate.round.1', 'debate.round.2', 'ai.results', 'ai.decisions']
CONSUMES: list[str] = ['ai.requests', 'ai.parsed', 'debate.round.0', 'debate.round.1', 'debate.round.2', 'ai.results', 'ai.decisions']
