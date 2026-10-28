import base64

import pandas as pd
import pytest

from app import accounts, config as C, email_sync, gmail, store as S


def _application(tracking_id="EXT-TEST", status="Candidature envoyée", date_sent="2026-10-01"):
    row = {column: "" for column in C.COLS}
    row.update(
        ID=tracking_id,
        Entreprise="Acme Analytics",
        Poste_visé="Data Analyst",
        Email_contact="recruitment@acme.example",
        Statut=status,
        Date_candidature=date_sent,
    )
    return row


def _setup_sync(monkeypatch, tmp_path, tracking):
    monkeypatch.setattr(C, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(C, "REGISTRATION_KEY", "")
    accounts.initialize()
    user, _token = accounts.create_user(
        "sync@example.com", "correct-horse-password", full_name="Sync Candidate",
    )
    state = {"tracking": pd.DataFrame(tracking, columns=C.COLS)}
    monkeypatch.setattr(S, "load_tracking", lambda: state["tracking"].copy(deep=True))
    monkeypatch.setattr(
        S, "save_tracking",
        lambda updated: state.update(tracking=updated.copy(deep=True)),
    )
    monkeypatch.setattr(gmail, "status", lambda: {
        "connected": True, "read_authorized": True,
    })
    return user["id"], state


def _gmail_message(message_id="message-1"):
    body = "Thank you for applying. We have received your application for Data Analyst at Acme Analytics."
    encoded = base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
    return {
        "id": message_id,
        "internalDate": "1792454400000",
        "snippet": body,
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": "Recruitment <recruitment@acme.example>"},
                {"name": "Subject", "value": "Application received - Data Analyst at Acme Analytics"},
            ],
            "body": {"data": encoded},
        },
    }


def test_classifier_recognizes_recruitment_outcomes_without_guessing():
    assert email_sync.classify_message(
        "Application received", "Thank you for applying. We have received your application.",
    )[0] == "En cours de traitement"
    assert email_sync.classify_message(
        "Interview invitation", "Please select a time for your interview.",
    )[0] == "Entretien programmé"
    assert email_sync.classify_message(
        "Application update", "We regret to inform you that you were not selected.",
    )[0] == "Refusée"
    assert email_sync.classify_message("Hello", "Thanks for your message.") is None


def test_matching_leaves_tied_applications_for_manual_review():
    data = pd.DataFrame([_application("EXT-A"), _application("EXT-B")])
    index, confidence = email_sync.match_message(
        data,
        "Recruitment <recruitment@acme.example>",
        "Application received - Data Analyst at Acme Analytics",
        "Thank you for applying to Acme Analytics for Data Analyst.",
    )
    assert index is None
    assert confidence > 0


def test_sync_updates_only_sent_application_and_deduplicates_message(monkeypatch, tmp_path):
    user_id, state = _setup_sync(monkeypatch, tmp_path, [_application()])
    messages = {"message-1": _gmail_message()}
    monkeypatch.setattr(gmail, "search_messages", lambda *_args, **_kwargs: [{"id": "message-1"}])
    monkeypatch.setattr(gmail, "get_message", lambda message_id: messages[message_id])

    first = email_sync.sync_user(user_id)
    second = email_sync.sync_user(user_id)

    assert first["new_messages"] == 1
    assert first["updated_applications"] == 1
    assert second["new_messages"] == 0
    assert second["updated_applications"] == 0
    assert state["tracking"].iloc[0]["Statut"] == "En cours de traitement"
    assert len(accounts.email_messages(user_id)) == 1


def test_sync_does_not_mark_draft_as_sent_or_apply_email_status(monkeypatch, tmp_path):
    draft = _application(status="À envoyer", date_sent="")
    user_id, state = _setup_sync(monkeypatch, tmp_path, [draft])
    monkeypatch.setattr(gmail, "search_messages", lambda *_args, **_kwargs: [{"id": "message-1"}])
    monkeypatch.setattr(gmail, "get_message", lambda _message_id: _gmail_message())

    result = email_sync.sync_user(user_id)

    assert result["updated_applications"] == 0
    assert state["tracking"].iloc[0]["Statut"] == "À envoyer"
    review = accounts.email_messages(user_id, reviews_only=True)
    assert len(review) == 1
    assert review[0]["tracking_id"] is None


def test_sync_error_is_recorded_and_absence_of_messages_is_not_a_refusal(monkeypatch, tmp_path):
    user_id, state = _setup_sync(monkeypatch, tmp_path, [_application()])
    monkeypatch.setattr(gmail, "search_messages", lambda *_args, **_kwargs: [])
    result = email_sync.sync_user(user_id)
    assert result["new_messages"] == 0
    assert state["tracking"].iloc[0]["Statut"] == "Candidature envoyée"

    def fail_search(*_args, **_kwargs):
        raise gmail.GmailError("Gmail unavailable")

    monkeypatch.setattr(gmail, "search_messages", fail_search)
    with pytest.raises(gmail.GmailError, match="Gmail unavailable"):
        email_sync.sync_user(user_id)
    assert accounts.email_sync_state(user_id)["status"] == "error"
    assert accounts.email_sync_state(user_id)["error"] == "Gmail unavailable"
