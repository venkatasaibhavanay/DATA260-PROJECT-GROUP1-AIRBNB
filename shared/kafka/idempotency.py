"""Consumer-side duplicate protection (API doc section 3.3).

Every consumer that writes to a database records (consumer_group, idempotency_key)
in its own processed-events store INSIDE the same transaction as the business
write. If the key is already there, the event was already applied: skip the write
and let the offset be committed.

Naming convention: each service owns its own table or collection named
``<prefix>_processed_events``, for example ``property_processed_events``,
``booking_processed_events``, ``messaging_processed_events``.

MySQL DDL template (one table per service, in that service's init script):

    CREATE TABLE <table> (consumer_group VARCHAR(64) NOT NULL, idempotency_key VARCHAR(256) NOT NULL, processed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (consumer_group, idempotency_key));

MySQL usage (inside the caller's transaction):

    with engine.begin() as conn:
        if mysql_already_processed(conn, "booking_processed_events", group, event.idempotency_key):
            return
        ... business writes on conn ...
        mysql_mark_processed(conn, "booking_processed_events", group, event.idempotency_key)

MongoDB usage:

    ensure_mongo_index(db.messaging_processed_events)   # once at startup
    if not mongo_already_processed(coll, group, key):
        ... writes (optionally in a session) ...
        mongo_mark_processed(coll, group, key, session=session)
"""
import re
from datetime import datetime, timezone
from typing import Any

_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


def _table(name: str) -> str:
    # Table names cannot be bound parameters, so validate them strictly.
    if not _TABLE_RE.match(name):
        raise ValueError(f"invalid table name: {name!r}")
    return name


# ---------- MySQL (SQLAlchemy Connection) ----------

def mysql_already_processed(conn: Any, table: str, consumer_group: str, idempotency_key: str) -> bool:
    from sqlalchemy import text

    row = conn.execute(
        text(f"SELECT 1 FROM {_table(table)} WHERE consumer_group = :g AND idempotency_key = :k LIMIT 1"),
        {"g": consumer_group, "k": idempotency_key},
    ).first()
    return row is not None


def mysql_mark_processed(conn: Any, table: str, consumer_group: str, idempotency_key: str) -> None:
    """Insert the key. A duplicate raises IntegrityError, which rolls back the caller's transaction."""
    from sqlalchemy import text

    conn.execute(
        text(f"INSERT INTO {_table(table)} (consumer_group, idempotency_key) VALUES (:g, :k)"),
        {"g": consumer_group, "k": idempotency_key},
    )


# ---------- MongoDB (pymongo Collection) ----------

def ensure_mongo_index(collection: Any) -> None:
    collection.create_index(
        [("consumer_group", 1), ("idempotency_key", 1)],
        unique=True,
        name="uniq_consumer_group_idempotency_key",
    )


def mongo_already_processed(collection: Any, consumer_group: str, idempotency_key: str) -> bool:
    return collection.find_one(
        {"consumer_group": consumer_group, "idempotency_key": idempotency_key},
        projection={"_id": 1},
    ) is not None


def mongo_mark_processed(collection: Any, consumer_group: str, idempotency_key: str, session: Any = None) -> None:
    """Insert the key. A duplicate raises pymongo.errors.DuplicateKeyError."""
    collection.insert_one(
        {
            "consumer_group": consumer_group,
            "idempotency_key": idempotency_key,
            "processed_at": datetime.now(timezone.utc),
        },
        session=session,
    )
