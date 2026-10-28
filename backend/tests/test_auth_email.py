import json
import re

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import config as C
from app import accounts
from app import email_confirmations
from app import main


def test_login_protects_api_and_sets_session_cookie(monkeypatch, tmp_path, supabase_client):
    monkeypatch.setattr(C, "DATA_DIR", tmp_path / "legacy-data")
    monkeypatch.setattr(C, "REGISTRATION_KEY", "")
    accounts.initialize()
    client = TestClient(main.app)

    assert client.get("/api/auth/status").json()["authenticated"] is False
    assert client.get("/api/meta").status_code == 401
    assert client.post("/api/auth/login", json={
        "email": "candidate@example.com", "password": "incorrect-password",
    }).status_code == 401

    response = client.post("/api/auth/register", json={
        "full_name": "Candidate Example",
        "email": "candidate@example.com", "password": "correct-horse-password",
    })
    assert response.status_code == 201
    assert response.headers["set-cookie"].startswith("bookjob_session=")
    assert response.json()["user"]["full_name"] == "Candidate Example"
    saved_user = (
        supabase_client.table("users")
        .select("email, full_name")
        .eq("email", "candidate@example.com")
        .execute()
        .data
    )
    assert saved_user == [{"email": "candidate@example.com", "full_name": "Candidate Example"}]
    assert client.get("/api/profile").json()["profile"]["nom"] == "Candidate Example"
    assert client.get("/api/meta").status_code == 200
    application = client.post("/api/tracking", json={
        "entreprise": "Persistent Candidate Application", "poste": "Stage Data",
    }).json()
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/meta").status_code == 401
    assert client.post("/api/auth/login", json={
        "email": "candidate@example.com", "password": "correct-horse-password",
    }).status_code == 200
    assert client.get("/api/profile").json()["profile"]["nom"] == "Candidate Example"
    assert any(
        item["id"] == application["id"]
        for item in client.get("/api/tracking").json()["items"]
    )
    assert client.post("/api/auth/logout").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200


def test_tracking_and_email_history_are_isolated_between_accounts(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(C, "REGISTRATION_KEY", "")
    accounts.initialize()
    first = TestClient(main.app)
    second = TestClient(main.app)
    assert first.post("/api/auth/register", json={
        "full_name": "First Candidate",
        "email": "first@example.com", "password": "correct-horse-password",
    }).status_code == 201
    created = first.post("/api/tracking", json={
        "entreprise": "Private application", "poste": "Stage Data",
    })
    assert created.status_code == 200
    tracking_id = created.json()["id"]
    assert second.post("/api/auth/register", json={
        "full_name": "Second Candidate",
        "email": "second@example.com", "password": "correct-horse-password",
    }).status_code == 201

    assert first.get("/api/profile").json()["profile"]["nom"] == "First Candidate"
    assert second.get("/api/profile").json()["profile"]["nom"] == "Second Candidate"
    assert all(item["id"] != tracking_id for item in second.get("/api/tracking").json()["items"])
    assert second.get(f"/api/tracking/{tracking_id}/events").status_code == 404
    assert second.get(f"/api/tracking/{tracking_id}/emails").status_code == 404


def test_two_account_spaces_isolate_favorites_applications_and_cvs(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(C, "CV_LIB_DIR", C.DATA_DIR / "uploads" / "cv_bibliotheque")
    monkeypatch.setattr(C, "CV_SENT_DIR", C.DATA_DIR / "uploads" / "cv_envoyes")
    monkeypatch.setattr(C, "REGISTRATION_KEY", "")
    accounts.initialize()
    user_a = TestClient(main.app)
    user_b = TestClient(main.app)

    created_a = user_a.post("/api/auth/register", json={
        "full_name": "User A",
        "email": "user-a@example.com",
        "password": "correct-horse-password",
    })
    assert created_a.status_code == 201
    for company_id in ("MRK-003", "MRK-004"):
        assert user_a.post(f"/api/favorites/{company_id}").status_code == 200
    application = user_a.post("/api/tracking", json={
        "entreprise": "User A private application",
        "poste": "Stage Data",
    })
    assert application.status_code == 200
    tracking_id = application.json()["id"]
    upload = user_a.post(
        "/api/cvs",
        files={"file": ("user-a-cv.pdf", b"%PDF-1.4 user-a-private-cv", "application/pdf")},
    )
    assert upload.status_code == 200
    cv_id = upload.json()["items"][0]["id"]

    assert user_a.post("/api/auth/logout").status_code == 200
    created_b = user_b.post("/api/auth/register", json={
        "full_name": "User B",
        "email": "user-b@example.com",
        "password": "correct-horse-password",
    })
    assert created_b.status_code == 201

    assert user_b.get("/api/profile").json()["profile"]["nom"] == "User B"
    assert user_b.get("/api/favorites").json()["favorites"] == []
    assert all(item["id"] != tracking_id for item in user_b.get("/api/tracking").json()["items"])
    assert user_b.get("/api/cvs").json()["items"] == []
    assert user_b.get(f"/api/cvs/{cv_id}/file").status_code == 404
    assert user_b.delete(f"/api/cvs/{cv_id}").status_code == 404
    assert user_b.get(f"/api/tracking/{tracking_id}/events").status_code == 404

    anonymous = TestClient(main.app)
    assert anonymous.get("/api/profile").status_code == 401
    assert anonymous.get("/api/cvs").status_code == 401

    assert user_b.post("/api/auth/logout").status_code == 200
    login_a = user_a.post("/api/auth/login", json={
        "email": "user-a@example.com",
        "password": "correct-horse-password",
    })
    assert login_a.status_code == 200
    assert set(user_a.get("/api/favorites").json()["favorites"]) == {"MRK-003", "MRK-004"}
    assert any(item["id"] == tracking_id for item in user_a.get("/api/tracking").json()["items"])
    assert any(item["id"] == cv_id for item in user_a.get("/api/cvs").json()["items"])
    assert user_a.get(f"/api/cvs/{cv_id}/file").content == b"%PDF-1.4 user-a-private-cv"


def test_legacy_gmail_connection_migrates_only_to_first_account(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(C, "GOOGLE_TOKEN_FILE", tmp_path / "legacy" / "google_oauth_token.json")
    monkeypatch.setattr(C, "GOOGLE_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setattr(C, "GOOGLE_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(C, "GOOGLE_OAUTH_REDIRECT_URI", "https://bookjob.example/api/google/callback")
    monkeypatch.setattr(C, "REGISTRATION_KEY", "")
    C.GOOGLE_TOKEN_FILE.parent.mkdir(parents=True)
    C.GOOGLE_TOKEN_FILE.write_text(json.dumps({
        "refresh_token": "legacy-refresh-token",
        "email": "owner@gmail.com",
        "scopes": [main.gmail.GMAIL_READ_SCOPE],
    }), encoding="utf-8")
    accounts.initialize()
    first = TestClient(main.app)
    second = TestClient(main.app)

    first_user = first.post("/api/auth/register", json={
        "full_name": "First Candidate",
        "email": "first@gmail.com",
        "password": "correct-horse-password",
    })
    assert first_user.status_code == 201
    assert second.post("/api/auth/register", json={
        "full_name": "Second Candidate",
        "email": "second@gmail.com",
        "password": "correct-horse-password",
    }).status_code == 201

    assert second.get("/api/google/status").json()["connected"] is False
    assert C.GOOGLE_TOKEN_FILE.exists()
    first_status = first.get("/api/google/status").json()
    assert first_status["connected"] is True
    assert first_status["sender"] == "owner@gmail.com"
    assert C.GOOGLE_TOKEN_FILE.exists() is False
    assert second.get("/api/google/status").json()["connected"] is False


def test_logout_revokes_session_and_preserves_google_connection(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "DATA_DIR", tmp_path / "legacy-data")
    monkeypatch.setattr(C, "REGISTRATION_KEY", "")
    accounts.initialize()
    monkeypatch.setattr(main.gmail, "status", lambda: {"connected": True})
    monkeypatch.setattr(main.gmail, "disconnect", lambda: pytest.fail("logout must preserve Gmail OAuth"))

    client = TestClient(main.app)
    registration = client.post("/api/auth/register", json={
        "full_name": "Candidate Example",
        "email": "candidate@example.com", "password": "correct-horse-password",
    })
    session_token = registration.cookies[C.SESSION_COOKIE_NAME]
    response = client.post("/api/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert "bookjob_session=" in response.headers["set-cookie"]
    assert client.get("/api/meta").status_code == 401
    assert client.post("/api/auth/logout").status_code == 200
    replay = TestClient(main.app)
    replay.cookies.set(C.SESSION_COOKIE_NAME, session_token)
    assert replay.get("/api/meta").status_code == 401


def _configure_application(monkeypatch, tmp_path, *, send=None):
    cv_dir = tmp_path / "cvs"
    cv_dir.mkdir()
    (cv_dir / "application.pdf").write_bytes(b"%PDF-1.4 test")
    row = {column: "" for column in C.COLS}
    row.update(
        ID="EXT-TEST",
        Entreprise="Entreprise test",
        Secteur="Informatique",
        Poste_visé="Stage Data",
        Email_contact="",
        Statut="À envoyer",
        Fichier_CV="application.pdf",
    )
    state = {
        "tracking": pd.DataFrame([row], columns=C.COLS),
        "saved": [],
        "messages": [],
        "drafts": [],
        "deleted_drafts": [],
    }

    def save_tracking(updated):
        copy = updated.copy(deep=True)
        state["saved"].append(copy)
        state["tracking"] = copy

    monkeypatch.setattr(C, "DATA_DIR", tmp_path / "legacy-data")
    monkeypatch.setattr(C, "REGISTRATION_KEY", "")
    accounts.initialize()
    monkeypatch.setattr(C, "user_path", lambda path: path)
    monkeypatch.setattr(C, "CV_SENT_DIR", cv_dir)
    monkeypatch.setattr(C, "EMAIL_CONFIRMATIONS_FILE", tmp_path / "pending.json")
    monkeypatch.setattr(C, "BOOKJOB_PUBLIC_URL", "http://testserver")
    monkeypatch.setattr(main.gmail, "status", lambda: {
        "configured": True, "connected": True, "draft_authorized": True,
        "sender": "sender@gmail.com",
    })
    drafts = {}

    def create_draft(message):
        drafts["draft-id"] = message
        state["drafts"].append(message)
        return "draft-id"

    def send_draft(draft_id):
        state["messages"].append(drafts[draft_id])

    monkeypatch.setattr(main.gmail, "create_draft", create_draft)
    monkeypatch.setattr(main.gmail, "send_draft", send_draft)
    monkeypatch.setattr(
        main.gmail,
        "delete_draft",
        lambda draft_id: state["deleted_drafts"].append(draft_id),
    )
    monkeypatch.setattr(
        main.gmail,
        "send",
        send or (lambda message: state["messages"].append(message)),
    )
    monkeypatch.setattr(main.S, "load_tracking", lambda: state["tracking"].copy(deep=True))
    monkeypatch.setattr(main.S, "save_tracking", save_tracking)
    monkeypatch.setattr(main.S, "load_profile", lambda: {
        "competences": "Python, SQL", "nom": "Candidate",
    })
    monkeypatch.setattr(main.S, "default_relance", lambda _: "2026-10-21")
    monkeypatch.setattr(main.co, "companies_df", lambda: pd.DataFrame(columns=["ID"]))
    monkeypatch.setattr(
        main,
        "_track_out",
        lambda saved_row: {"id": saved_row["ID"], "statut": saved_row["Statut"]},
    )
    client = TestClient(main.app)
    response = client.post("/api/auth/register", json={
        "full_name": "Candidate Example",
        "email": "candidate@example.com", "password": "correct-horse-password",
    })
    assert response.status_code == 201
    return state, client


def _request_confirmation(client):
    response = client.post("/api/tracking/EXT-TEST/send", data={
        "recipient": "recrutement@example.com",
        "subject": "Candidature stage Data",
        "body": "Bonjour, voici ma candidature.",
        "cover_letter": "Madame, Monsieur,\nJe souhaite effectuer mon stage chez vous.",
        "offer_title": "Stage Data",
        "offer_url": "https://example.com/jobs/stage-data",
        "offer_description": "Nous recherchons des compétences Python et analyse de données.",
    })
    return response


def test_preview_email_requires_separate_one_time_confirmation(monkeypatch, tmp_path):
    state, client = _configure_application(monkeypatch, tmp_path)

    response = _request_confirmation(client)

    assert response.status_code == 200
    assert response.json()["confirmation_required"] is True
    assert response.json()["sender"] == "sender@gmail.com"
    assert len(state["messages"]) == 1
    assert len(state["drafts"]) == 1
    assert state["drafts"][0]["To"] == "recrutement@example.com"
    assert [item.get_filename() for item in state["drafts"][0].iter_attachments()] == [
        "application.pdf", "lettre_motivation.txt",
    ]
    preview = state["messages"][0]
    assert preview["To"] == "sender@gmail.com"
    assert "À confirmer" in preview["Subject"]
    assert "recrutement@example.com" in preview.get_body(preferencelist=("plain",)).get_content()
    assert "Python" in preview.get_body(preferencelist=("plain",)).get_content()
    attachments = list(preview.iter_attachments())
    assert [item.get_filename() for item in attachments] == [
        "application.pdf", "lettre_motivation.txt",
    ]
    assert state["tracking"].iloc[0]["Statut"] == "À envoyer"
    assert state["saved"][0].iloc[0]["Email_contact"] == "recrutement@example.com"

    token_match = re.search(r"/api/email/confirm#([A-Za-z0-9_-]+)", preview.get_body(
        preferencelist=("plain",),
    ).get_content())
    assert token_match
    token = token_match.group(1)
    portal = client.get("/api/email/confirm")
    assert portal.status_code == 200
    assert "window.location.hash" in portal.text
    details = client.post(
        "/api/email/confirm/details",
        json={"token": token},
        headers={"X-BookJob-Confirmation-Token": token},
    )
    assert details.status_code == 200
    assert details.json()["recipient"] == "recrutement@example.com"
    assert len(state["messages"]) == 1

    confirmed = client.post(
        "/api/email/confirm",
        json={"token": token},
        headers={"X-BookJob-Confirmation-Token": token},
    )
    assert confirmed.status_code == 200
    assert "recrutement@example.com" in confirmed.json()["message"]
    assert len(state["messages"]) == 2
    application = state["messages"][1]
    assert application["To"] == "recrutement@example.com"
    assert application["Subject"] == "Candidature stage Data"
    assert [item.get_filename() for item in application.iter_attachments()] == [
        "application.pdf", "lettre_motivation.txt",
    ]
    assert state["tracking"].iloc[0]["Statut"] == "Candidature envoyée"
    assert client.post(
        "/api/email/confirm/details",
        json={"token": token},
        headers={"X-BookJob-Confirmation-Token": token},
    ).status_code == 404
    assert client.get("/api/tracking/EXT-TEST/send-status").json() == {
        "sent": True, "pending": False, "expires_at": None,
    }


def test_send_preview_requires_authorized_gmail_account(monkeypatch, tmp_path):
    _state, client = _configure_application(monkeypatch, tmp_path)
    monkeypatch.setattr(main.gmail, "status", lambda: {
        "configured": True, "connected": False, "sender": "",
    })

    response = _request_confirmation(client)

    assert response.status_code == 503
    assert "Connecte ton compte Gmail" in response.json()["detail"]


def test_uploaded_cover_letter_is_attached_to_preview_and_final_email(monkeypatch, tmp_path):
    state, client = _configure_application(monkeypatch, tmp_path)
    form = {
        "recipient": "recrutement@example.com",
        "subject": "Candidature stage Data",
        "body": "Bonjour, voici ma candidature.",
        "offer_title": "Stage Data",
        "offer_description": "Python et analyse de données.",
    }
    response = client.post(
        "/api/tracking/EXT-TEST/send",
        data=form,
        files={"cover_letter_file": ("lettre.docx", b"document-word", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert response.status_code == 200
    preview = state["messages"][0]
    assert [item.get_filename() for item in preview.iter_attachments()] == [
        "application.pdf", "EXT_TEST_lettre.docx",
    ]
    token = re.search(
        r"/api/email/confirm#([A-Za-z0-9_-]+)",
        preview.get_body(preferencelist=("plain",)).get_content(),
    ).group(1)

    confirmed = client.post(
        "/api/email/confirm",
        json={"token": token},
        headers={"X-BookJob-Confirmation-Token": token},
    )

    assert confirmed.status_code == 200
    application = state["messages"][1]
    attachments = list(application.iter_attachments())
    assert [item.get_filename() for item in attachments] == [
        "application.pdf", "EXT_TEST_lettre.docx",
    ]
    assert attachments[1].get_payload(decode=True) == b"document-word"


def test_expired_confirmation_cannot_be_used(monkeypatch, tmp_path):
    state, client = _configure_application(monkeypatch, tmp_path)
    response = _request_confirmation(client)
    assert response.status_code == 200
    preview = state["messages"][0]
    token = re.search(
        r"/api/email/confirm#([A-Za-z0-9_-]+)",
        preview.get_body(preferencelist=("plain",)).get_content(),
    ).group(1)

    pending = email_confirmations.load(C.EMAIL_CONFIRMATIONS_FILE)
    token_hash = email_confirmations.token_digest(token)
    request_data = pending[token_hash]
    request_data["expires_at"] = 0
    email_confirmations.save(C.EMAIL_CONFIRMATIONS_FILE, pending)

    details = client.post(
        "/api/email/confirm/details",
        json={"token": token},
        headers={"X-BookJob-Confirmation-Token": token},
    )

    assert details.status_code == 410
    assert len(email_confirmations.load(C.EMAIL_CONFIRMATIONS_FILE)) == 0
    assert state["deleted_drafts"] == ["draft-id"]


def test_preview_delivery_failure_leaves_application_unsent(monkeypatch, tmp_path):
    def failed_send(_message):
        raise main.gmail.GmailError("Google a refusé l'envoi.")

    state, client = _configure_application(monkeypatch, tmp_path, send=failed_send)

    response = _request_confirmation(client)

    assert response.status_code == 502
    assert state["tracking"].iloc[0]["Statut"] == "À envoyer"
    assert not C.EMAIL_CONFIRMATIONS_FILE.exists() or C.EMAIL_CONFIRMATIONS_FILE.read_text() == "{}"


def test_google_oauth_callback_requires_matching_state(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "DATA_DIR", tmp_path / "legacy-data")
    monkeypatch.setattr(C, "REGISTRATION_KEY", "")
    accounts.initialize()
    monkeypatch.setattr(C, "BOOKJOB_ENV", "development")
    monkeypatch.setattr(C, "GOOGLE_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setattr(C, "GOOGLE_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(C, "GOOGLE_OAUTH_REDIRECT_URI", "http://testserver/api/google/callback")
    monkeypatch.setattr(
        main.gmail,
        "exchange_code",
        lambda code: "sender@gmail.com" if code == "oauth-code" else "",
    )
    client = TestClient(main.app)
    registration = client.post("/api/auth/register", json={
        "full_name": "Candidate Example",
        "email": "candidate@example.com", "password": "correct-horse-password",
    })
    assert registration.status_code == 201

    connected = client.get("/api/google/connect", follow_redirects=False)
    assert connected.status_code == 302
    assert "gmail.send" in connected.headers["location"]
    assert "gmail.compose" in connected.headers["location"]
    assert "gmail.readonly" in connected.headers["location"]
    state = client.cookies[C.GOOGLE_STATE_COOKIE]
    callback = client.get("/api/google/callback", params={"code": "oauth-code", "state": state})
    assert callback.status_code == 200
    assert "sender@gmail.com" in callback.text
    assert "bookjob-gmail-connected" in callback.text
    assert C.GOOGLE_STATE_COOKIE not in client.cookies

    invalid = client.get("/api/google/callback", params={"code": "oauth-code", "state": "wrong"})
    assert invalid.status_code == 400
    assert "vérification de sécurité" in invalid.text
