import base64
from datetime import date
from email import policy
from email.parser import BytesParser

import pandas as pd

from app import config as C, email_followups, email_sync, gmail


def _application(tracking_id, *, status="Candidature envoyée", sent="2026-10-01", email="recruteur@example.com"):
    row = {column: "" for column in C.COLS}
    row.update(
        ID=tracking_id,
        Entreprise="Entreprise Exemple",
        Poste_visé="Stage Data",
        Email_contact=email,
        Statut=status,
        Date_candidature=sent,
    )
    return row


def test_due_followups_only_include_unanswered_sent_applications_after_seven_days():
    tracking = pd.DataFrame([
        _application("due"),
        _application("recent", sent="2026-10-02"),
        _application("draft", status="À envoyer"),
        _application("answered", status="En cours de traitement"),
        _application("invalid-email", email="invalid"),
        _application("reviewed-response"),
    ])

    due = email_followups.due_followups(
        tracking,
        date(2026, 10, 8),
        {"reviewed-response"},
    )

    assert [row["ID"] for row in due] == ["due"]


def test_automatic_followups_are_disabled_by_default(monkeypatch):
    monkeypatch.setattr(email_followups.S, "load_state", lambda: {"settings": {"automaticFollowups": False}})
    monkeypatch.setattr(email_followups.gmail, "status", lambda: (_ for _ in ()).throw(AssertionError("Gmail must not be accessed")))

    assert email_followups.send_due_followups("user-1") == {"sent": 0, "failed": 0, "skipped": 0}


def test_followup_message_uses_application_and_candidate_details_without_attachments():
    message = email_followups._message(
        "candidate@example.com",
        _application("due", sent="2026-10-01"),
        {"prenom": "Amina", "nom_famille": "El Amrani", "tel": "+212600000000"},
    )
    parsed = BytesParser(policy=policy.default).parsebytes(message.as_bytes())

    assert parsed["To"] == "recruteur@example.com"
    assert "Stage Data" in parsed["Subject"]
    assert "Entreprise Exemple" in parsed["Subject"]
    assert "envoyée le 2026-10-01" in parsed.get_body(preferencelist=("plain",)).get_content()
    assert "Amina El Amrani" in parsed.get_body(preferencelist=("plain",)).get_content()
    assert not list(parsed.iter_attachments())


def test_enabled_followup_sends_once_and_records_completion(monkeypatch):
    tracking = pd.DataFrame([_application("due")], columns=C.COLS)
    claimed = set()
    sent = []
    finished = []

    monkeypatch.setattr(email_followups.S, "load_state", lambda: {"settings": {"automaticFollowups": True}})
    monkeypatch.setattr(email_followups.gmail, "status", lambda: {
        "connected": True,
        "send_authorized": True,
        "read_authorized": True,
        "sender": "candidate@example.com",
    })
    monkeypatch.setattr(email_followups.S, "load_tracking", lambda: tracking.copy(deep=True))
    monkeypatch.setattr(email_followups.S, "load_profile", lambda: {"nom": "Candidate"})
    monkeypatch.setattr(email_followups.S, "save_tracking", lambda updated: tracking.update(updated))
    monkeypatch.setattr(email_followups.accounts, "email_response_tracking_ids", lambda _user_id: set())
    monkeypatch.setattr(email_followups.accounts, "email_messages", lambda *_args, **_kwargs: [])

    def claim(_user_id, tracking_id):
        if tracking_id in claimed:
            return False
        claimed.add(tracking_id)
        return True

    monkeypatch.setattr(email_followups.accounts, "claim_automatic_followup", claim)
    monkeypatch.setattr(email_followups.accounts, "finish_automatic_followup",
                        lambda _user_id, tracking_id, status, error="": finished.append((tracking_id, status, error)))
    monkeypatch.setattr(email_followups.gmail, "send", sent.append)

    first = email_followups.send_due_followups("user-1", date(2026, 10, 8))
    second = email_followups.send_due_followups("user-1", date(2026, 10, 8))

    assert first == {"sent": 1, "failed": 0, "skipped": 0}
    assert second == {"sent": 0, "failed": 0, "skipped": 1}
    assert len(sent) == 1
    assert finished == [("due", "sent", "")]


def test_failed_followup_is_not_retried_automatically(monkeypatch):
    tracking = pd.DataFrame([_application("due")], columns=C.COLS)
    claimed = set()
    attempts = []
    finished = []

    monkeypatch.setattr(email_followups.S, "load_state", lambda: {"settings": {"automaticFollowups": True}})
    monkeypatch.setattr(email_followups.gmail, "status", lambda: {
        "connected": True,
        "send_authorized": True,
        "read_authorized": True,
        "sender": "candidate@example.com",
    })
    monkeypatch.setattr(email_followups.S, "load_tracking", lambda: tracking.copy(deep=True))
    monkeypatch.setattr(email_followups.S, "load_profile", lambda: {})
    monkeypatch.setattr(email_followups.accounts, "email_response_tracking_ids", lambda _user_id: set())
    monkeypatch.setattr(email_followups.accounts, "email_messages", lambda *_args, **_kwargs: [])

    def claim(_user_id, tracking_id):
        if tracking_id in claimed:
            return False
        claimed.add(tracking_id)
        return True

    def fail_send(_message):
        attempts.append("attempt")
        raise gmail.GmailError("Gmail unavailable")

    monkeypatch.setattr(email_followups.accounts, "claim_automatic_followup", claim)
    monkeypatch.setattr(email_followups.accounts, "finish_automatic_followup",
                        lambda _user_id, tracking_id, status, error="": finished.append((tracking_id, status, error)))
    monkeypatch.setattr(email_followups.gmail, "send", fail_send)

    first = email_followups.send_due_followups("user-1", date(2026, 10, 8))
    second = email_followups.send_due_followups("user-1", date(2026, 10, 8))

    assert first == {"sent": 0, "failed": 1, "skipped": 0}
    assert second == {"sent": 0, "failed": 0, "skipped": 1}
    assert attempts == ["attempt"]
    assert finished == [("due", "failed", "Gmail unavailable")]


def test_unassigned_matching_reply_blocks_automatic_followup():
    application = _application("due")
    pending_review = {
        "tracking_id": None,
        "sender": "Recrutement <recruteur@example.com>",
        "subject": "Stage Data - Entreprise Exemple",
        "snippet": "Bonjour, merci pour votre candidature. Nous vous contacterons après examen.",
        "received_at": "2026-10-05T10:00:00+00:00",
    }

    assert email_followups._has_pending_reply(application, [pending_review])


def test_unclassified_company_reply_is_saved_for_review_and_blocks_followup(monkeypatch):
    tracking = pd.DataFrame([_application("due")], columns=C.COLS)
    review_messages = []
    body = "Bonjour, merci pour votre candidature. Nous vous contacterons après examen."
    encoded_body = base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
    message = {
        "id": "reply-1",
        "internalDate": "1791417600000",
        "snippet": body,
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": "Recrutement <recruteur@example.com>"},
                {"name": "Subject", "value": "Candidature Stage Data - Entreprise Exemple"},
            ],
            "body": {"data": encoded_body},
        },
    }

    monkeypatch.setattr(C, "set_current_user", lambda _user_id: None)
    monkeypatch.setattr(C, "reset_current_user", lambda _token: None)
    monkeypatch.setattr(gmail, "status", lambda: {"connected": True, "read_authorized": True})
    monkeypatch.setattr(gmail, "search_messages", lambda *_args, **_kwargs: [{"id": "reply-1"}])
    monkeypatch.setattr(gmail, "get_message", lambda _message_id: message)
    monkeypatch.setattr(email_sync.S, "load_tracking", lambda: tracking.copy(deep=True))
    monkeypatch.setattr(email_sync.S, "save_tracking", lambda _data: None)
    monkeypatch.setattr(email_sync.accounts, "save_email_message",
                        lambda _user_id, item: review_messages.append(item) or True)
    monkeypatch.setattr(email_sync.accounts, "save_email_sync_state", lambda *_args: None)
    monkeypatch.setattr(email_sync.accounts, "email_response_tracking_ids",
                        lambda _user_id: {item["tracking_id"] for item in review_messages if item["tracking_id"]})
    monkeypatch.setattr(email_sync.accounts, "record_status_event", lambda *_args: None)

    result = email_sync.sync_user("user-1")

    assert result["updated_applications"] == 0
    assert review_messages[0]["tracking_id"] == "due"
    assert review_messages[0]["review_required"] is True
    assert email_sync.classify_message(message["payload"]["headers"][1]["value"], body) is None
    assert email_followups.due_followups(tracking, date(2026, 10, 10), {"due"}) == []
