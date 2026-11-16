from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app import accounts, db, main


def test_pool_opens_without_waiting_and_is_reused(monkeypatch):
    created = []

    class FakePool:
        check_connection = staticmethod(lambda connection: None)

        def __init__(self, conninfo, **kwargs):
            self.conninfo = conninfo
            self.options = kwargs
            self.open_wait = None
            created.append(self)

        def open(self, *, wait):
            self.open_wait = wait

    monkeypatch.setattr(db, "_pool", None)
    monkeypatch.setattr(db, "ConnectionPool", FakePool)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db.example.test/postgres")
    monkeypatch.delenv("DB_POOL_MIN", raising=False)
    monkeypatch.delenv("DB_POOL_MAX", raising=False)
    monkeypatch.delenv("DB_POOL_TIMEOUT", raising=False)

    pool = db._get_pool()

    assert db._get_pool() is pool
    assert len(created) == 1
    assert pool.open_wait is False
    assert pool.options["min_size"] == 0
    assert pool.options["max_size"] == 1
    assert pool.options["timeout"] == 10
    assert pool.options["num_workers"] == 1
    assert pool.options["kwargs"]["connect_timeout"] == 5


def test_anonymous_auth_status_allows_registration_without_counting_users(monkeypatch):
    monkeypatch.setenv("BOOKJOB_REGISTRATION_KEY", "legacy-value-is-ignored")
    monkeypatch.setattr(accounts, "resolve_session", lambda token: None)

    def unexpected_user_count():
        pytest.fail("Public auth status must not query user count.")

    monkeypatch.setattr(accounts, "user_count", unexpected_user_count)

    response = TestClient(main.app).get("/api/auth/status")

    assert response.status_code == 200
    assert response.json() == {
        "required": True,
        "authenticated": False,
        "user": None,
        "registration_open": True,
        "google_login": main.google_login.configured(),
    }


def test_registration_route_works_without_legacy_invitation_key(monkeypatch):
    monkeypatch.setenv("BOOKJOB_REGISTRATION_KEY", "legacy-value-is-ignored")
    monkeypatch.setattr(accounts, "resolve_session", lambda token: None)
    monkeypatch.setattr(main, "_check_auth_rate_limit", lambda request: "test-client")
    created = {}

    def create_user(email, password, full_name):
        created.update(email=email, password=password, full_name=full_name)
        return ({"id": "public-user", "email": email, "full_name": full_name}, "session-token")

    monkeypatch.setattr(accounts, "create_user", create_user)
    response = TestClient(main.app).post("/api/auth/register", json={
        "full_name": "Public Candidate",
        "email": "public@example.com",
        "password": "a-long-test-password",
    })

    assert response.status_code == 201
    assert response.json()["user"]["id"] == "public-user"
    assert created == {
        "email": "public@example.com",
        "password": "a-long-test-password",
        "full_name": "Public Candidate",
    }


def test_google_account_creation_ignores_legacy_invitation_key(monkeypatch):
    monkeypatch.setenv("BOOKJOB_REGISTRATION_KEY", "legacy-value-is-ignored")

    class Connection:
        @staticmethod
        def execute(query, params):
            return type("Result", (), {"fetchone": lambda self: None})()

    @contextmanager
    def connection():
        yield Connection()

    monkeypatch.setattr(accounts, "_connect", connection)
    calls = []

    def create_user(email, password, full_name):
        calls.append((email, full_name))
        return ({"id": "google-user"}, "session-token")

    monkeypatch.setattr(accounts, "create_user", create_user)
    user, token = accounts.login_with_google("candidate@example.com", "Google Candidate")

    assert user["id"] == "google-user" and token == "session-token"
    assert calls == [("candidate@example.com", "Google Candidate")]


def test_auth_status_does_not_hide_database_errors(monkeypatch):
    def database_failure(token):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(accounts, "resolve_session", database_failure)

    with pytest.raises(RuntimeError, match="database unavailable"):
        TestClient(main.app).get("/api/auth/status")
