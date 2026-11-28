"""Tests for the user-counters and user-host-metrics consumers (no broker needed)."""
from datetime import datetime, timedelta, timezone

import pytest

from app.models import Guest, Host
from app.repositories.users import add_guest, add_host
from app.workers.handlers import COUNTERS_GROUP, HOST_METRICS_GROUP, make_handler
from shared.kafka import new_event
from shared.kafka.consumer import process_message
from shared.kafka.envelope import encode_event


@pytest.fixture
def people(db_factory):
    with db_factory() as db, db.begin():
        g = add_guest(db, first_name="M", last_name="C", email="m@x.com", password_hash="x", location="SJ")
        h = add_host(db, name="D", email="d@x.com", password_hash="x")
        return g.guest_id, h.host_id


def ev(topic, payload, entity_type="property", entity_id="2001", key=None):
    return new_event(topic, source_service="test", actor_id="service:test", entity_type=entity_type,
                     entity_id=entity_id, payload=payload, idempotency_key=key)


def guest_row(db_factory, gid) -> Guest:
    with db_factory() as db:
        return db.get(Guest, gid)


def host_row(db_factory, hid) -> Host:
    with db_factory() as db:
        return db.get(Host, hid)


def test_saved_unsaved_and_booking_counters(db_factory, people):
    gid, _ = people
    handle = make_handler(db_factory, COUNTERS_GROUP)
    handle(ev("property.saved", {"property_id": 2001, "guest_id": gid}, key="property.saved:2001:1"))
    handle(ev("property.saved", {"property_id": 2002, "guest_id": gid}, key="property.saved:2002:1"))
    handle(ev("property.unsaved", {"property_id": 2001, "guest_id": gid}, key="property.unsaved:2001:1"))
    handle(ev("booking.approved", {"reservation_id": "r1", "property_id": 2001, "guest_id": gid, "host_id": 501},
              entity_type="reservation", entity_id="r1"))
    g = guest_row(db_factory, gid)
    assert g.saved_properties_count == 1 and g.booking_count == 1


def test_duplicate_event_applied_once(db_factory, people):
    gid, _ = people
    handle = make_handler(db_factory, COUNTERS_GROUP)
    e = ev("property.saved", {"property_id": 2001, "guest_id": gid}, key="property.saved:2001:dup")
    assert handle(e) is True
    assert handle(e) is False  # redelivery skipped via user_processed_events
    assert guest_row(db_factory, gid).saved_properties_count == 1


def test_counter_never_negative(db_factory, people):
    gid, _ = people
    make_handler(db_factory, COUNTERS_GROUP)(ev("property.unsaved", {"property_id": 1, "guest_id": gid}))
    assert guest_row(db_factory, gid).saved_properties_count == 0


def test_bad_payload_goes_to_dlq(db_factory, people):
    dlq = []
    status, _ = process_message("property.saved", encode_event(ev("property.saved", {"property_id": 1})),
                                make_handler(db_factory, COUNTERS_GROUP),
                                lambda t, v, h: dlq.append(t), sleep=lambda s: None)
    assert status == "dlq" and dlq == ["property.saved.dlq"]


def _msg(thread, sender, receiver, at, first=False, reply_to=None, n=0):
    p = {"message_id": f"m{n}", "thread_id": thread, "property_id": 2001, "sender_id": sender,
         "receiver_id": receiver, "timestamp": at.strftime("%Y-%m-%dT%H:%M:%SZ"), "is_first_guest_message": first}
    if reply_to:
        p["reply_to_guest_message_at"] = reply_to.strftime("%Y-%m-%dT%H:%M:%SZ")
    return ev("message.sent", p, entity_type="message", entity_id=f"m{n}")


def test_host_response_metrics(db_factory, people):
    gid, hid = people
    handle = make_handler(db_factory, HOST_METRICS_GROUP)
    now = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=3)
    g, h = f"guest:{gid}", f"host:{hid}"
    # thread A: replied after 30 min; thread B: replied after 30 h (late); thread C: never replied
    handle(_msg("A", g, h, now, first=True, n=1))
    handle(_msg("A", h, g, now + timedelta(minutes=30), reply_to=now, n=2))
    handle(_msg("A", h, g, now + timedelta(minutes=90), reply_to=now, n=3))  # second reply ignored
    handle(_msg("B", g, h, now, first=True, n=4))
    handle(_msg("B", h, g, now + timedelta(hours=30), reply_to=now, n=5))
    handle(_msg("C", g, h, now, first=True, n=6))
    row = host_row(db_factory, hid)
    assert str(row.response_rate) == "0.33"
    assert row.response_time_minutes == round((30 + 30 * 60) / 2)


def test_plain_integer_ids_accepted(db_factory, people):
    gid, hid = people
    handle = make_handler(db_factory, HOST_METRICS_GROUP)
    now = datetime.now(timezone.utc) - timedelta(hours=1)
    handle(_msg("T", gid, hid, now, first=True, n=1))
    handle(_msg("T", hid, gid, now + timedelta(minutes=10), reply_to=now, n=2))
    row = host_row(db_factory, hid)
    assert str(row.response_rate) == "1.00" and row.response_time_minutes == 10
