from app.models import Guest, Host
from app.seed import GUESTS, HOSTS, SAMPLE_PASSWORD, seed
from tests.conftest import auth


def test_seed_is_idempotent_and_loginable(db_factory, client):
    with db_factory() as db, db.begin():
        first = seed(db)
    with db_factory() as db, db.begin():
        second = seed(db)
    assert len(first["guests"]) == len(GUESTS) and len(first["hosts"]) == len(HOSTS)
    assert second == {"guests": [], "hosts": []}
    with db_factory() as db:
        assert db.query(Guest).count() == len(GUESTS) and db.query(Host).count() == len(HOSTS)

    r = client.post("/api/v1/auth/login", json={"email": "maya.chen@seed.group1.dev",
                                                "password": SAMPLE_PASSWORD, "role": "guest"})
    assert r.status_code == 200
    token = r.json()["data"]["access_token"]
    me = client.post("/api/v1/guests/get", json={"guest_id": r.json()["data"]["user"]["id"]}, headers=auth(token))
    assert me.json()["data"]["preferences"]["budget_max"] == "250.00"
    r = client.post("/api/v1/auth/login", json={"email": "daniel.ortiz@seed.group1.dev",
                                                "password": SAMPLE_PASSWORD, "role": "host"})
    assert r.status_code == 200
