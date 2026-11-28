"""Test setup: SQLite in-memory DB, fake Kafka publisher, in-memory Redis stand-ins."""
import os
import tempfile

os.environ.setdefault("JWT_SECRET", "test-secret-0123456789-test-secret")
os.environ["USER_MEDIA_ROOT"] = tempfile.mkdtemp(prefix="g1-media-")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import shared.auth.jwt_auth as jwt_auth  # noqa: E402
from app.database.session import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.services import rate_limit  # noqa: E402
from app.services.events import get_publisher  # noqa: E402
from shared.database import Base  # noqa: E402
from shared.errors import AppError  # noqa: E402

PROCESSED_DDL = """CREATE TABLE user_processed_events (consumer_group VARCHAR(64) NOT NULL,
 idempotency_key VARCHAR(256) NOT NULL, processed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY (consumer_group, idempotency_key))"""


class FakePublisher:
    def __init__(self):
        self.events = []
        self.fail = False

    def publish(self, topic, envelope, key=None, timeout_s=10):
        if self.fail:
            raise AppError(503, "SERVICE_UNAVAILABLE", "Event broker unavailable. Please try again.")
        assert envelope.event_type == topic
        self.events.append({"topic": topic, "key": key, "env": envelope})


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    import app.models  # noqa: F401  (register tables)
    Base.metadata.create_all(eng)
    with eng.begin() as c:
        c.execute(text(PROCESSED_DDL))
    yield eng
    eng.dispose()


@pytest.fixture
def db_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def publisher():
    return FakePublisher()


@pytest.fixture
def client(db_factory, publisher, monkeypatch):
    def _session():
        s = db_factory()
        try:
            yield s
        finally:
            s.close()

    denied, failures = set(), {}
    monkeypatch.setattr(jwt_auth, "is_revoked", lambda jti: jti in denied)
    monkeypatch.setattr(jwt_auth, "revoke_token", lambda user: denied.add(user.jti))
    import app.routes.auth as auth_routes
    import app.services.users as user_svc
    monkeypatch.setattr(auth_routes, "revoke_token", lambda user: denied.add(user.jti))
    monkeypatch.setattr(user_svc, "revoke_token", lambda user: denied.add(user.jti))
    monkeypatch.setattr(rate_limit, "is_locked", lambda e: failures.get(e, 0) >= rate_limit.MAX_FAILURES)
    monkeypatch.setattr(rate_limit, "record_failure", lambda e: failures.__setitem__(e, failures.get(e, 0) + 1))
    monkeypatch.setattr(rate_limit, "clear", lambda e: failures.pop(e, None))

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_publisher] = lambda: publisher
    yield TestClient(app)
    app.dependency_overrides.clear()


GUEST = {"first_name": "Maya", "last_name": "Chen", "email": "maya.chen@example.com",
         "password": "StrongPass1!", "phone": "+14085550101", "location": "San Jose, CA",
         "preferences": {"preferred_locations": ["San Jose"], "budget_max": "250.00",
                         "amenities": ["parking", "kitchen"], "property_types": ["apartment"],
                         "travel_purpose": "business"}}
HOST = {"name": "Daniel Ortiz", "email": "daniel.ortiz@example.com", "password": "StrongPass1!",
        "phone": "+14085550199"}


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def guest(client):
    r = client.post("/api/v1/guests/create", json=GUEST)
    assert r.status_code == 201, r.text
    d = r.json()["data"]
    return {"id": d["guest"]["guest_id"], "token": d["access_token"]}


@pytest.fixture
def host(client):
    r = client.post("/api/v1/hosts/create", json=HOST)
    assert r.status_code == 201, r.text
    d = r.json()["data"]
    return {"id": d["host"]["host_id"], "token": d["access_token"]}


@pytest.fixture
def admin_token(db_factory):
    from app.models import Admin
    from app.services.security import hash_password
    from shared.auth import create_access_token

    with db_factory() as s:
        a = Admin(name="Grader", email="admin@example.com", password_hash=hash_password("AdminPass1"))
        s.add(a)
        s.commit()
        return create_access_token(a.admin_id, "admin")
