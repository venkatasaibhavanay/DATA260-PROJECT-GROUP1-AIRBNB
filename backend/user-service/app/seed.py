"""Load sample guests and hosts for local development and demos.

    cd backend/user-service
    PYTHONPATH=.:../.. ../../.venv/bin/python -m app.seed                   # DB rows only
    PYTHONPATH=.:../.. ../../.venv/bin/python -m app.seed --publish-events  # + user.registered events

Safe to run repeatedly: accounts are matched by email and never duplicated or overwritten.
Every sample account uses the password SAMPLE_PASSWORD below (local sample data only).
Counters and host response metrics start at 0/null: the Kafka consumers maintain them from
real property/booking/message events. The admin account is created separately (python -m app.seed_admin).
"""
import argparse
import sys
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.database.connection import get_mysql_engine
from app.models import Guest, Host
from app.repositories.users import get_guest_by_email, get_host_by_email
from app.services.security import hash_password

SAMPLE_PASSWORD = "SamplePass1"
DOMAIN = "seed.group1.dev"

# first, last, city, phone, preferences
GUESTS = [
    ("Maya", "Chen", "San Jose, CA", "+14085550101",
     {"preferred_locations": ["San Jose"], "budget_max": "250.00", "amenities": ["parking", "kitchen"],
      "property_types": ["apartment"], "travel_purpose": "business"}),
    ("Liam", "Patel", "Sunnyvale, CA", "+14085550102",
     {"preferred_locations": ["Sunnyvale", "Mountain View"], "budget_max": "180.00", "amenities": ["wifi", "workspace"],
      "property_types": ["private_room", "apartment"], "travel_purpose": "business"}),
    ("Sofia", "Garcia", "Cupertino, CA", "+14085550103",
     {"preferred_locations": ["Cupertino"], "budget_max": "400.00", "amenities": ["pool", "kitchen", "parking"],
      "property_types": ["house"], "travel_purpose": "family"}),
    ("Noah", "Kim", "Santa Clara, CA", "+14085550104",
     {"preferred_locations": ["Santa Clara", "San Jose"], "budget_max": "150.00", "amenities": ["wifi"],
      "property_types": ["shared_room", "private_room"], "travel_purpose": "student"}),
    ("Ava", "Nguyen", "Mountain View, CA", "+16505550105",
     {"preferred_locations": ["Mountain View", "Palo Alto"], "budget_max": "320.00", "amenities": ["ev_charger", "parking", "wifi"],
      "property_types": ["condo", "apartment"], "travel_purpose": "business"}),
    ("Ethan", "Brown", "Palo Alto, CA", "+16505550106",
     {"preferred_locations": ["Palo Alto"], "budget_max": "500.00", "amenities": ["hot_tub", "pool", "air_conditioning"],
      "property_types": ["house", "cabin"], "travel_purpose": "leisure"}),
    ("Isabella", "Rossi", "San Jose, CA", "+14085550107",
     {"preferred_locations": ["San Jose", "Santa Clara"], "budget_max": "220.00", "amenities": ["pet_friendly", "parking"],
      "property_types": ["house", "condo"], "travel_purpose": "family"}),
    ("Lucas", "Martin", "Sunnyvale, CA", "+14085550108", None),
    ("Mia", "Johnson", "Cupertino, CA", None,
     {"budget_max": "200.00", "amenities": ["washer", "kitchen"]}),
    ("Arjun", "Rao", "Santa Clara, CA", "+14085550110",
     {"preferred_locations": ["Santa Clara"], "budget_max": "275.00", "amenities": ["workspace", "wifi", "tv"],
      "property_types": ["apartment", "condo"], "travel_purpose": "business"}),
    ("Chloe", "Wilson", "Mountain View, CA", "+16505550111",
     {"preferred_locations": ["Mountain View"], "budget_max": "160.00", "amenities": ["heating", "wifi"],
      "property_types": ["private_room"], "travel_purpose": "leisure"}),
    ("Daniel", "Lee", "Palo Alto, CA", "+16505550112",
     {"preferred_locations": ["Palo Alto", "Cupertino"], "budget_max": "350.00", "amenities": ["parking", "pool"],
      "property_types": ["house"], "travel_purpose": "family"}),
]

# name, phone, verification_status, access_level, days hosting
HOSTS = [
    ("Daniel Ortiz", "+14085550199", "verified", "superhost", 900),
    ("Priya Shah", "+14085550198", "verified", "standard", 540),
    ("Marcus Lee", "+14085550197", "pending", "standard", 120),
    ("Elena Petrova", "+16505550196", "verified", "standard", 365),
    ("Omar Haddad", "+14085550195", "unverified", "standard", 30),
    ("Grace Liu", "+16505550194", "verified", "superhost", 1200),
]


def _email(*parts: str) -> str:
    return f"{'.'.join(p.lower() for p in parts)}@{DOMAIN}"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def seed(db: Session) -> dict[str, list]:
    pw = hash_password(SAMPLE_PASSWORD)
    created: dict[str, list] = {"guests": [], "hosts": []}
    for i, (first, last, city, phone, prefs) in enumerate(GUESTS):
        email = _email(first, last)
        if get_guest_by_email(db, email):
            continue
        when = _now() - timedelta(days=60 - i * 4)
        g = Guest(first_name=first, last_name=last, email=email, password_hash=pw, phone=phone, location=city,
                  preferences=prefs, saved_properties_count=0, booking_count=0, status="active",
                  profile_created_datetime=when, updated_datetime=when)
        db.add(g)
        db.flush()
        created["guests"].append(g)
    for name, phone, verification, access, days in HOSTS:
        email = _email(*name.split())
        if get_host_by_email(db, email):
            continue
        when = _now() - timedelta(days=days)
        h = Host(name=name, email=email, password_hash=pw, phone=phone, verification_status=verification,
                 access_level=access, response_rate=None, response_time_minutes=None,
                 host_since=date.today() - timedelta(days=days), status="active",
                 created_datetime=when, updated_datetime=when)
        db.add(h)
        db.flush()
        created["hosts"].append(h)
    return created


def publish_registered(created: dict[str, list]) -> int:
    from app.config import settings
    from shared.kafka import new_event
    from shared.kafka.producer import EnvelopeProducer
    from shared.kafka.topics import USER_REGISTERED

    producer = EnvelopeProducer(settings.kafka_bootstrap_servers, client_id="user-service-seed")
    n = 0
    try:
        for role, key in (("guest", "guests"), ("host", "hosts")):
            for row in created[key]:
                uid = row.guest_id if role == "guest" else row.host_id
                when = row.profile_created_datetime if role == "guest" else row.created_datetime
                payload = {"user_id": uid, "role": role, "created_datetime": when.strftime("%Y-%m-%dT%H:%M:%SZ")}
                if role == "guest":
                    payload["location"] = row.location
                env = new_event(USER_REGISTERED, source_service="user-service", actor_id=f"{role}:{uid}",
                                entity_type=role, entity_id=str(uid), payload=payload)
                producer.publish(USER_REGISTERED, env, key=f"{role}:{uid}")
                n += 1
    finally:
        producer.close()
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--publish-events", action="store_true",
                    help="also publish user.registered for newly created accounts (needs Kafka)")
    args = ap.parse_args()

    with Session(get_mysql_engine(), expire_on_commit=False) as db, db.begin():
        created = seed(db)

    print(f"Created {len(created['guests'])} guests and {len(created['hosts'])} hosts "
          f"(existing sample accounts were left unchanged).")
    for g in created["guests"]:
        print(f"  guest {g.guest_id:>5}  {g.email}")
    for h in created["hosts"]:
        print(f"  host  {h.host_id:>5}  {h.email}")
    print(f"Sign in with any sample email and the password {SAMPLE_PASSWORD}")

    if args.publish_events and (created["guests"] or created["hosts"]):
        try:
            print(f"Published {publish_registered(created)} user.registered events.")
        except Exception as exc:  # noqa: BLE001
            print(f"Could not publish events (is Kafka running?): {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
