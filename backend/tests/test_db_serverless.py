import pytest
from fastapi.testclient import TestClient

from app import accounts, config as C, db, main


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


def test_anonymous_auth_status_skips_unneeded_user_count(monkeypatch):
    monkeypatch.setattr(C, "REGISTRATION_KEY", "")
    monkeypatch.setattr(accounts, "resolve_session", lambda token: None)

    def unexpected_user_count():
        pytest.fail("user_count should not run when no registration key is configured")

    monkeypatch.setattr(accounts, "user_count", unexpected_user_count)

    response = TestClient(main.app).get("/api/auth/status")

    assert response.status_code == 200
    assert response.json() == {
        "required": True,
        "authenticated": False,
        "user": None,
        "registration_open": True,
        "registration_key_required": False,
        "google_login": main.google_login.configured(),
    }


def test_auth_status_checks_user_count_when_registration_key_is_enabled(monkeypatch):
    monkeypatch.setattr(C, "REGISTRATION_KEY", "invite-required")
    monkeypatch.setattr(accounts, "resolve_session", lambda token: None)
    monkeypatch.setattr(accounts, "user_count", lambda: 1)

    response = TestClient(main.app).get("/api/auth/status")

    assert response.status_code == 200
    assert response.json()["registration_key_required"] is True


def test_auth_status_does_not_hide_database_errors(monkeypatch):
    monkeypatch.setattr(C, "REGISTRATION_KEY", "invite-required")
    monkeypatch.setattr(accounts, "resolve_session", lambda token: None)

    def database_failure():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(accounts, "user_count", database_failure)

    with pytest.raises(RuntimeError, match="database unavailable"):
        TestClient(main.app).get("/api/auth/status")
