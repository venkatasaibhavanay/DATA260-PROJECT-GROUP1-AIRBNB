"""Kafka topics this service is planned to produce and consume.

Topic names are defined centrally in shared/kafka/topics.py.
Every message must be a validated shared.kafka.EventEnvelope.
"""
PRODUCES: list[str] = ['booking.requested', 'booking.pending', 'booking.rejected', 'booking.approved', 'booking.declined', 'booking.cancelled']
CONSUMES: list[str] = ['booking.requested', 'guest.deleted', 'property.deleted', 'ai.results']
