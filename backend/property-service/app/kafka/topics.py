"""Kafka topics this service is planned to produce and consume.

Topic names are defined centrally in shared/kafka/topics.py.
Every message must be a validated shared.kafka.EventEnvelope.
"""
PRODUCES: list[str] = ['property.created', 'property.updated', 'property.deleted', 'property.viewed', 'property.saved', 'property.unsaved', 'availability.updated']
CONSUMES: list[str] = ['booking.pending', 'booking.approved', 'booking.declined', 'booking.cancelled', 'review.created']
