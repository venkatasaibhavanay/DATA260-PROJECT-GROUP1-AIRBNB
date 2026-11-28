"""API tests for user-service (API doc section 6)."""
from tests.conftest import GUEST, HOST, auth

API = "/api/v1"


# ---------- signup ----------

def test_guest_signup_returns_token_and_publishes_event(client, publisher):
    r = client.post(f"{API}/guests/create", json=GUEST)
    assert r.status_code == 201
    d = r.json()["data"]
    assert d["token_type"] == "bearer" and d["expires_in"] == 1800 and d["access_token"]
    g = d["guest"]
    assert g["first_name"] == "Maya" and g["saved_properties_count"] == 0 and g["booking_count"] == 0
    ev = publisher.events[0]
    assert ev["topic"] == "user.registered" and ev["key"] == f"guest:{g['guest_id']}"
    assert ev["env"].entity.entity_type == "guest" and ev["env"].source_service == "user-service"
    assert ev["env"].payload["location"] == "San Jose, CA"
    assert ev["env"].trace_id == r.headers["X-Trace-ID"]


def test_guest_signup_duplicate_email(client, guest):
    r = client.post(f"{API}/guests/create", json={**GUEST, "email": "MAYA.CHEN@example.com"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"


def test_same_email_allowed_for_other_role(client, guest):
    assert client.post(f"{API}/hosts/create", json={**HOST, "email": GUEST["email"]}).status_code == 201


def test_guest_signup_validation(client):
    bad = {**GUEST, "password": "short", "phone": "4085550101", "first_name": "",
           "preferences": {"amenities": ["sauna"]}, "extra": 1}
    r = client.post(f"{API}/guests/create", json=bad)
    assert r.status_code == 422
    fields = r.json()["error"]["fields"]
    assert {"phone", "first_name", "preferences.amenities.0", "extra"} <= set(fields)


def test_weak_password_rejected(client):
    r = client.post(f"{API}/guests/create", json={**GUEST, "password": "allletters"})
    assert r.status_code == 422 and "password" in r.json()["error"]["fields"]


def test_signup_rolls_back_when_kafka_down(client, publisher):
    publisher.fail = True
    r = client.post(f"{API}/guests/create", json=GUEST)
    assert r.status_code == 503
    publisher.fail = False
    assert client.post(f"{API}/guests/create", json=GUEST).status_code == 201  # nothing was saved


def test_host_signup_defaults(client, publisher):
    r = client.post(f"{API}/hosts/create", json=HOST)
    assert r.status_code == 201
    h = r.json()["data"]["host"]
    assert h["verification_status"] == "unverified" and h["access_level"] == "standard" and h["host_since"]
    assert publisher.events[0]["env"].entity.entity_type == "host"
    assert "location" not in publisher.events[0]["env"].payload


# ---------- login / me / logout ----------

def test_login_me_logout(client, guest):
    r = client.post(f"{API}/auth/login", json={"email": GUEST["email"], "password": GUEST["password"], "role": "guest"})
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["user"] == {"id": guest["id"], "role": "guest", "name": "Maya Chen", "email": GUEST["email"]}
    token = d["access_token"]
    assert client.get(f"{API}/auth/me", headers=auth(token)).json()["data"]["name"] == "Maya Chen"
    assert client.post(f"{API}/auth/logout", headers=auth(token)).status_code == 204
    r = client.get(f"{API}/auth/me", headers=auth(token))
    assert r.status_code == 401 and r.json()["error"]["code"] == "TOKEN_REVOKED"


def test_login_generic_error(client, guest):
    wrong = client.post(f"{API}/auth/login", json={"email": GUEST["email"], "password": "Wrong1234", "role": "guest"})
    missing = client.post(f"{API}/auth/login", json={"email": "nobody@example.com", "password": "Wrong1234", "role": "guest"})
    wrong_role = client.post(f"{API}/auth/login", json={"email": GUEST["email"], "password": GUEST["password"], "role": "host"})
    for r in (wrong, missing, wrong_role):
        assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert wrong.json()["error"]["message"] == missing.json()["error"]["message"]


def test_login_rate_limited_after_5_failures(client, guest):
    for _ in range(5):
        client.post(f"{API}/auth/login", json={"email": GUEST["email"], "password": "Wrong1234", "role": "guest"})
    r = client.post(f"{API}/auth/login", json={"email": GUEST["email"], "password": GUEST["password"], "role": "guest"})
    assert r.status_code == 429 and r.json()["error"]["code"] == "RATE_LIMITED"


def test_admin_login(client, admin_token):
    r = client.post(f"{API}/auth/login", json={"email": "admin@example.com", "password": "AdminPass1", "role": "admin"})
    assert r.status_code == 200 and r.json()["data"]["user"]["role"] == "admin"


# ---------- guest profile ----------

def test_guest_reads_own_full_profile(client, guest):
    r = client.post(f"{API}/guests/get", json={"guest_id": guest["id"]}, headers=auth(guest["token"]))
    d = r.json()["data"]
    assert r.status_code == 200 and d["email"] == GUEST["email"] and d["phone"] == GUEST["phone"]
    assert d["preferences"]["budget_max"] == "250.00"
    assert d["profile_created_datetime"].endswith(("Z", "+00:00"))


def test_host_sees_public_subset(client, guest, host):
    d = client.post(f"{API}/guests/get", json={"guest_id": guest["id"]}, headers=auth(host["token"])).json()["data"]
    assert d["last_name"] == "C." and "email" not in d and "phone" not in d and "preferences" not in d


def test_guest_cannot_read_other_guest(client, guest):
    other = client.post(f"{API}/guests/create", json={**GUEST, "email": "o@example.com"}).json()["data"]["guest"]
    r = client.post(f"{API}/guests/get", json={"guest_id": other["guest_id"]}, headers=auth(guest["token"]))
    assert r.status_code == 403 and r.json()["error"]["code"] == "NOT_PROFILE_OWNER"


def test_guest_not_found(client, host):
    r = client.post(f"{API}/guests/get", json={"guest_id": 999999}, headers=auth(host["token"]))
    assert r.status_code == 404 and r.json()["error"]["code"] == "GUEST_NOT_FOUND"


def test_get_requires_token(client, guest):
    assert client.post(f"{API}/guests/get", json={"guest_id": guest["id"]}).status_code == 401


def test_guest_update(client, guest):
    r = client.post(f"{API}/guests/update", headers=auth(guest["token"]), json={
        "guest_id": guest["id"], "phone": "+14085550102", "location": "Sunnyvale, CA",
        "preferences": {"budget_max": "300.00", "amenities": ["parking", "kitchen", "wifi"]}})
    assert r.status_code == 200 and r.json()["data"]["guest_id"] == guest["id"]
    d = client.post(f"{API}/guests/get", json={"guest_id": guest["id"]}, headers=auth(guest["token"])).json()["data"]
    assert d["location"] == "Sunnyvale, CA" and d["phone"] == "+14085550102"
    assert d["preferences"] == {"budget_max": "300.00", "amenities": ["parking", "kitchen", "wifi"]}  # replaced whole


def test_guest_update_rules(client, guest):
    h = auth(guest["token"])
    r = client.post(f"{API}/guests/update", headers=h, json={"guest_id": guest["id"], "booking_count": 9})
    assert r.status_code == 422 and r.json()["error"]["code"] == "FIELD_NOT_EDITABLE"
    r = client.post(f"{API}/guests/update", headers=h, json={"guest_id": guest["id"] + 1, "location": "X"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "NOT_PROFILE_OWNER"
    client.post(f"{API}/guests/create", json={**GUEST, "email": "taken@example.com"})
    r = client.post(f"{API}/guests/update", headers=h, json={"guest_id": guest["id"], "email": "taken@example.com"})
    assert r.status_code == 409
    r = client.post(f"{API}/guests/update", headers=h, json={"guest_id": guest["id"], "location": None})
    assert r.status_code == 422


def test_host_cannot_update_guest(client, guest, host):
    r = client.post(f"{API}/guests/update", headers=auth(host["token"]), json={"guest_id": guest["id"], "location": "X"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "ROLE_FORBIDDEN"


def test_guest_delete(client, guest, publisher, host):
    r = client.post(f"{API}/guests/delete", headers=auth(guest["token"]), json={"guest_id": guest["id"]})
    assert r.status_code == 204 and r.content == b""
    ev = publisher.events[-1]
    assert ev["topic"] == "guest.deleted" and ev["key"] == str(guest["id"])
    assert ev["env"].payload["guest_id"] == guest["id"]
    # token revoked, profile gone, cannot log in, email freed for a new account
    assert client.get(f"{API}/auth/me", headers=auth(guest["token"])).status_code == 401
    r = client.post(f"{API}/guests/get", json={"guest_id": guest["id"]}, headers=auth(host["token"]))
    assert r.status_code == 404
    r = client.post(f"{API}/auth/login", json={"email": GUEST["email"], "password": GUEST["password"], "role": "guest"})
    assert r.status_code == 401
    assert client.post(f"{API}/guests/create", json=GUEST).status_code == 201


def test_guest_search(client, guest, host, admin_token):
    client.post(f"{API}/guests/create", json={**GUEST, "first_name": "Ana", "last_name": "Lopez",
                                              "email": "ana@example.com", "location": "Austin, TX"})
    r = client.post(f"{API}/guests/search", headers=auth(host["token"]),
                    json={"q": "chen", "location": "San Jose", "page": 1, "page_size": 20})
    d = r.json()["data"]
    assert r.status_code == 200 and d["total"] == 1 and d["total_pages"] == 1
    assert d["items"][0] == {"guest_id": guest["id"], "first_name": "Maya", "last_name": "C.",
                             "location": "San Jose, CA", "profile_photo_url": None}
    d = client.post(f"{API}/guests/search", headers=auth(admin_token), json={"page_size": 1}).json()["data"]
    assert d["total"] == 2 and d["total_pages"] == 2 and d["items"][0]["email"]
    r = client.post(f"{API}/guests/search", headers=auth(guest["token"]), json={})
    assert r.status_code == 403
    r = client.post(f"{API}/guests/search", headers=auth(host["token"]), json={"page_size": 500})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_FILTER"


# ---------- host profile ----------

def test_host_get_privacy(client, host, guest, admin_token):
    own = client.post(f"{API}/hosts/get", json={"host_id": host["id"]}, headers=auth(host["token"])).json()["data"]
    assert own["email"] == HOST["email"] and own["access_level"] == "standard" and own["response_rate"] is None
    public = client.post(f"{API}/hosts/get", json={"host_id": host["id"]}, headers=auth(guest["token"])).json()["data"]
    assert "email" not in public and "phone" not in public and "access_level" not in public
    adm = client.post(f"{API}/hosts/get", json={"host_id": host["id"]}, headers=auth(admin_token)).json()["data"]
    assert adm["email"] == HOST["email"]
    r = client.post(f"{API}/hosts/get", json={"host_id": 99999}, headers=auth(guest["token"]))
    assert r.status_code == 404 and r.json()["error"]["code"] == "HOST_NOT_FOUND"


def test_host_update_rules(client, host, admin_token):
    h = auth(host["token"])
    r = client.post(f"{API}/hosts/update", headers=h, json={"host_id": host["id"], "name": "Dan O", "phone": "+14085550198"})
    assert r.status_code == 200
    r = client.post(f"{API}/hosts/update", headers=h, json={"host_id": host["id"], "verification_status": "verified"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "FIELD_NOT_EDITABLE"
    r = client.post(f"{API}/hosts/update", headers=h, json={"host_id": host["id"], "host_since": "2020-01-01"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "FIELD_NOT_EDITABLE"
    r = client.post(f"{API}/hosts/update", headers=h, json={"host_id": host["id"] + 1, "name": "X"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "NOT_PROFILE_OWNER"
    r = client.post(f"{API}/hosts/update", headers=auth(admin_token),
                    json={"host_id": host["id"], "verification_status": "verified", "access_level": "superhost"})
    assert r.status_code == 200
    d = client.post(f"{API}/hosts/get", json={"host_id": host["id"]}, headers=h).json()["data"]
    assert d["name"] == "Dan O" and d["verification_status"] == "verified" and d["access_level"] == "superhost"


# ---------- photo ----------

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def test_profile_photo_upload_and_serve(client, guest):
    h = auth(guest["token"])
    r = client.post(f"{API}/users/profile-photo", headers=h, files={"file": ("me.png", PNG, "image/png")})
    assert r.status_code == 200
    url = r.json()["data"]["profile_photo_url"]
    assert url == f"/media/profiles/guests/{guest['id']}.png"
    assert client.get(url).content == PNG
    d = client.post(f"{API}/guests/get", json={"guest_id": guest["id"]}, headers=h).json()["data"]
    assert d["profile_photo_url"] == url
    r = client.post(f"{API}/users/profile-photo", headers=h, files={"file": ("me.jpg", JPG, "image/jpeg")})
    assert r.json()["data"]["profile_photo_url"].endswith(".jpg")
    assert client.get(url).status_code == 404  # old png replaced


def test_profile_photo_errors(client, host):
    h = auth(host["token"])
    r = client.post(f"{API}/users/profile-photo", headers=h, files={"file": ("a.gif", b"GIF89a", "image/gif")})
    assert r.status_code == 415 and r.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"
    r = client.post(f"{API}/users/profile-photo", headers=h, files={"file": ("a.png", b"notapng", "image/png")})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_IMAGE"
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (5 * 1024 * 1024)
    r = client.post(f"{API}/users/profile-photo", headers=h, files={"file": ("a.png", big, "image/png")})
    assert r.status_code == 413 and r.json()["error"]["code"] == "FILE_TOO_LARGE"
