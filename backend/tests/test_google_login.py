from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app import accounts, config as C, main


@pytest.fixture
def google(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(C, "DATA_DIR", tmp_path / "legacy-data")
    monkeypatch.setattr(C, "REGISTRATION_KEY", "")
    monkeypatch.setattr(C, "BOOKJOB_ENV", "development")
    monkeypatch.setattr(C, "GOOGLE_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setattr(C, "GOOGLE_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(C, "GOOGLE_OAUTH_REDIRECT_URI", "http://testserver/api/google/callback")
    accounts.initialize()
    identities = {"good-code": ("Etudiante@Gmail.com", "Étudiante Test")}

    def identity(code):
        if code not in identities:
            raise main.gmail.GmailError("Code Google invalide.")
        return identities[code]

    monkeypatch.setattr(main.google_login, "identity", identity)
    return identities


def _start(client):
    started = client.get("/api/auth/google", follow_redirects=False)
    assert started.status_code == 302
    query = parse_qs(urlsplit(started.headers["location"]).query)
    assert query["scope"] == ["openid email profile"]  # aucun scope Gmail pour une simple connexion
    return client.cookies[C.GOOGLE_STATE_COOKIE]


def test_google_login_creates_account_and_session(google):
    client = TestClient(main.app, follow_redirects=False)
    assert client.get("/api/auth/status").json()["google_login"] is True
    state = _start(client)

    done = client.get("/api/google/callback", params={"code": "good-code", "state": state})

    assert done.status_code == 303 and done.headers["location"] == "/"
    status = client.get("/api/auth/status").json()
    assert status["authenticated"] is True
    assert status["user"]["email"] == "etudiante@gmail.com"
    assert status["user"]["full_name"] == "Étudiante Test"
    assert client.get("/api/profile").status_code == 200


def test_google_login_reuses_existing_password_account(google):
    first = TestClient(main.app)
    registered = first.post("/api/auth/register", json={
        "full_name": "Compte Existant", "email": "etudiante@gmail.com", "password": "a-long-test-password",
    }).json()

    client = TestClient(main.app, follow_redirects=False)
    state = _start(client)
    client.get("/api/google/callback", params={"code": "good-code", "state": state})

    assert client.get("/api/auth/status").json()["user"]["id"] == registered["user"]["id"]


def test_google_login_rejects_bad_state_and_bad_code(google):
    client = TestClient(main.app, follow_redirects=False)
    _start(client)
    forged = client.get("/api/google/callback", params={"code": "good-code", "state": "login.forged"})
    assert forged.status_code == 303 and client.get("/api/auth/status").json()["authenticated"] is False

    state = _start(client)
    refused = client.get("/api/google/callback", params={"code": "bad-code", "state": state})
    assert refused.status_code == 303 and "erreur_google" in refused.headers["location"]
    assert client.get("/api/auth/status").json()["authenticated"] is False


def test_google_login_respects_invitation_key(google, monkeypatch):
    TestClient(main.app).post("/api/auth/register", json={
        "full_name": "Premier", "email": "premier@example.com", "password": "a-long-test-password",
    })
    monkeypatch.setattr(C, "REGISTRATION_KEY", "secret-invite")

    client = TestClient(main.app, follow_redirects=False)
    state = _start(client)
    refused = client.get("/api/google/callback", params={"code": "good-code", "state": state})

    assert "erreur_google" in refused.headers["location"]
    assert client.get("/api/auth/status").json()["authenticated"] is False


def test_google_login_unavailable_without_configuration(google, monkeypatch):
    monkeypatch.setattr(C, "GOOGLE_OAUTH_CLIENT_SECRET", "")
    client = TestClient(main.app, follow_redirects=False)
    assert client.get("/api/auth/status").json()["google_login"] is False
    assert client.get("/api/auth/google").status_code == 503
