import base64
import json
import time
from email import message_from_bytes
from email.message import EmailMessage
from urllib.parse import parse_qs, urlsplit

from app import config as C
from app import gmail


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.payload = payload or {}

    def json(self):
        return self.payload


def test_authorization_requests_gmail_read_and_preserves_previously_granted_scopes(monkeypatch):
    monkeypatch.setattr(C, "GOOGLE_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setattr(C, "GOOGLE_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(C, "GOOGLE_OAUTH_REDIRECT_URI", "https://bookjob.example/api/google/callback")

    query = parse_qs(urlsplit(gmail.authorization_url("oauth-state")).query)

    assert gmail.GMAIL_READ_SCOPE in query["scope"][0].split()
    assert gmail.GMAIL_SEND_SCOPE in query["scope"][0].split()
    assert gmail.GMAIL_COMPOSE_SCOPE in query["scope"][0].split()
    assert query["include_granted_scopes"] == ["true"]
    assert "consent" in query["prompt"][0]


def test_oauth_code_exchange_stores_refresh_token_without_a_gmail_password(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "GOOGLE_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setattr(C, "GOOGLE_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(C, "GOOGLE_OAUTH_REDIRECT_URI", "https://bookjob.example/api/google/callback")
    monkeypatch.setattr(C, "GOOGLE_TOKEN_FILE", tmp_path / "oauth.json")
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(payload={
            "access_token": "access-token", "refresh_token": "refresh-token", "expires_in": 3600,
            "scope": (
                f"openid email {gmail.GMAIL_SEND_SCOPE} {gmail.GMAIL_READ_SCOPE} "
                f"{gmail.GMAIL_COMPOSE_SCOPE}"
            ),
        })

    monkeypatch.setattr(gmail.requests, "post", post)
    monkeypatch.setattr(gmail, "_userinfo", lambda _token: "person@gmail.com")

    sender = gmail.exchange_code("temporary-code")
    token_data = json.loads(C.GOOGLE_TOKEN_FILE.read_text(encoding="utf-8"))

    assert sender == "person@gmail.com"
    assert token_data["refresh_token"] == "refresh-token"
    assert token_data["email"] == sender
    assert calls[0][1]["data"]["code"] == "temporary-code"
    assert "password" not in calls[0][1]["data"]
    assert gmail.GMAIL_COMPOSE_SCOPE in token_data["scopes"]


def test_send_refreshes_expired_token_and_posts_mime_message_to_gmail(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "GOOGLE_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setattr(C, "GOOGLE_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(C, "GOOGLE_OAUTH_REDIRECT_URI", "https://bookjob.example/api/google/callback")
    monkeypatch.setattr(C, "GOOGLE_TOKEN_FILE", tmp_path / "oauth.json")
    C.GOOGLE_TOKEN_FILE.write_text(json.dumps({
        "access_token": "expired", "refresh_token": "refresh-token", "expires_at": time.time() - 10,
        "email": "person@gmail.com",
        "scopes": [gmail.GMAIL_SEND_SCOPE],
    }), encoding="utf-8")
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        if url == gmail.TOKEN_URL:
            return FakeResponse(payload={"access_token": "fresh-token", "expires_in": 3600})
        return FakeResponse()

    monkeypatch.setattr(gmail.requests, "post", post)
    message = EmailMessage()
    message["From"] = "person@gmail.com"
    message["To"] = "recruitment@example.com"
    message["Subject"] = "Application"
    message.set_content("Please find my CV attached.")

    gmail.send(message)

    assert calls[0][0] == gmail.TOKEN_URL
    assert calls[1][0] == gmail.SEND_URL
    assert calls[1][1]["headers"]["Authorization"] == "Bearer fresh-token"
    raw = calls[1][1]["json"]["raw"]
    raw += "=" * (-len(raw) % 4)
    decoded = message_from_bytes(base64.urlsafe_b64decode(raw))
    assert decoded["To"] == "recruitment@example.com"
    assert decoded["Subject"] == "Application"


def test_gmail_draft_is_created_and_sent_only_after_request(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "GOOGLE_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setattr(C, "GOOGLE_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(C, "GOOGLE_OAUTH_REDIRECT_URI", "https://bookjob.example/api/google/callback")
    monkeypatch.setattr(C, "GOOGLE_TOKEN_FILE", tmp_path / "oauth.json")
    C.GOOGLE_TOKEN_FILE.write_text(json.dumps({
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "expires_at": time.time() + 3600,
        "email": "person@gmail.com",
        "scopes": [gmail.GMAIL_COMPOSE_SCOPE],
    }), encoding="utf-8")
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(payload={"id": "draft-123"})

    monkeypatch.setattr(gmail.requests, "post", post)
    message = EmailMessage()
    message["From"] = "person@gmail.com"
    message["To"] = "recruitment@example.com"
    message["Subject"] = "Application"
    message.set_content("Please find my CV attached.")

    draft_id = gmail.create_draft(message)

    assert draft_id == "draft-123"
    assert calls[0][0] == gmail.DRAFTS_URL
    raw = calls[0][1]["json"]["message"]["raw"]
    raw += "=" * (-len(raw) % 4)
    decoded = message_from_bytes(base64.urlsafe_b64decode(raw))
    assert decoded["To"] == "recruitment@example.com"

    gmail.send_draft(draft_id)

    assert calls[1][0] == f"{gmail.DRAFTS_URL}/send"
    assert calls[1][1]["json"] == {"id": "draft-123"}


def test_gmail_draft_requires_compose_scope_before_calling_google(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "GOOGLE_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setattr(C, "GOOGLE_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(C, "GOOGLE_OAUTH_REDIRECT_URI", "https://bookjob.example/api/google/callback")
    monkeypatch.setattr(C, "GOOGLE_TOKEN_FILE", tmp_path / "oauth.json")
    C.GOOGLE_TOKEN_FILE.write_text(json.dumps({
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "expires_at": time.time() + 3600,
        "email": "person@gmail.com",
        "scopes": [gmail.GMAIL_SEND_SCOPE],
    }), encoding="utf-8")
    monkeypatch.setattr(
        gmail.requests, "post",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Gmail API should not be called")),
    )

    try:
        gmail.create_draft(EmailMessage())
    except gmail.GmailError as error:
        assert "gmail.compose" in str(error)
    else:
        raise AssertionError("Expected missing Gmail compose scope to be rejected")


def test_gmail_draft_403_explains_when_gmail_api_is_disabled(monkeypatch):
    monkeypatch.setattr(gmail, "_access_token", lambda **_kwargs: "access-token")
    monkeypatch.setattr(
        gmail.requests, "post",
        lambda *_args, **_kwargs: FakeResponse(
            status_code=403,
            payload={"error": {"errors": [{"reason": "accessNotConfigured"}]}},
        ),
    )

    try:
        gmail._gmail_post(gmail.DRAFTS_URL, {}, "création du brouillon")
    except gmail.GmailError as error:
        assert "API Gmail n’est pas activée" in str(error)
        assert "Google Cloud" in str(error)
    else:
        raise AssertionError("Expected disabled Gmail API to be reported")


def test_gmail_draft_403_explains_when_oauth_scope_is_missing(monkeypatch):
    monkeypatch.setattr(gmail, "_access_token", lambda **_kwargs: "access-token")
    monkeypatch.setattr(
        gmail.requests, "post",
        lambda *_args, **_kwargs: FakeResponse(
            status_code=403,
            payload={"error": {"errors": [{"reason": "insufficientPermissions"}]}},
        ),
    )

    try:
        gmail._gmail_post(gmail.DRAFTS_URL, {}, "création du brouillon")
    except gmail.GmailError as error:
        assert "Renouveler Gmail" in str(error)
        assert "gmail.compose" in str(error)
    else:
        raise AssertionError("Expected missing OAuth scope to be reported")


def test_disconnect_removes_local_credentials_when_google_cannot_be_reached(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "GOOGLE_TOKEN_FILE", tmp_path / "oauth.json")
    C.GOOGLE_TOKEN_FILE.write_text(json.dumps({
        "refresh_token": "refresh-token", "email": "person@gmail.com",
    }), encoding="utf-8")

    def post(*_args, **_kwargs):
        raise gmail.requests.RequestException("network unavailable")

    monkeypatch.setattr(gmail.requests, "post", post)

    try:
        gmail.disconnect()
    except gmail.GmailError as error:
        assert "déconnecté de BookJob" in str(error)
    else:
        raise AssertionError("Expected GmailError when Google cannot be reached")

    assert not C.GOOGLE_TOKEN_FILE.exists()
