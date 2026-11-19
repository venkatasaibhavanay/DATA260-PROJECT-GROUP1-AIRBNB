"""Kafka topics this service is planned to produce and consume.

Topic names are defined centrally in shared/kafka/topics.py.
Every message must be a validated shared.kafka.EventEnvelope.
"""
PRODUCES: list[str] = ['user.registered', 'guest.deleted']
CONSUMES: list[str] = ['property.saved', 'property.unsaved', 'booking.approved', 'message.sent']
