"""Opt-in, one-time Gmail follow-ups for unanswered sent applications."""
import re
from datetime import date, datetime, timezone
from email.message import EmailMessage

import pandas as pd

from . import accounts, config as C, email_sync, gmail, store as S

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_FOLLOWUP_AFTER_DAYS = 7


def due_followups(
    tracking: pd.DataFrame,
    today: date,
    responded_tracking_ids: set[str],
) -> list[dict]:
    due = []
    for row in tracking.to_dict(orient="records"):
        tracking_id = str(row.get("ID", "")).strip()
        recipient = str(row.get("Email_contact", "")).strip()
        if (
            not tracking_id
            or tracking_id in responded_tracking_ids
            or row.get("Statut") != "Candidature envoyée"
            or not _EMAIL_RE.fullmatch(recipient)
        ):
            continue
        try:
            sent_at = date.fromisoformat(str(row.get("Date_candidature", ""))[:10])
        except ValueError:
            continue
        if (today - sent_at).days >= _FOLLOWUP_AFTER_DAYS:
            due.append(row)
    return due


def _has_pending_reply(application: dict, reviews: list[dict]) -> bool:
    application_date = str(application.get("Date_candidature", ""))[:10]
    for message in reviews:
        received_at = str(message.get("received_at", ""))[:10]
        if application_date and received_at and received_at < application_date:
            continue
        if message.get("tracking_id") == application.get("ID"):
            return True
        if message.get("tracking_id"):
            continue
        candidate = pd.DataFrame([application], columns=C.COLS)
        match_index, confidence = email_sync.match_message(
            candidate,
            str(message.get("sender", "")),
            str(message.get("subject", "")),
            str(message.get("snippet", "")),
        )
        if match_index is not None and confidence >= 0.82:
            return True
    return False


def _single_line(value: object) -> str:
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())


def _message(sender: str, application: dict, profile: dict) -> EmailMessage:
    company = _single_line(application.get("Entreprise")) or "votre entreprise"
    position = _single_line(application.get("Poste_visé")) or "votre offre"
    recipient = _single_line(application.get("Email_contact"))
    sent_date = _single_line(application.get("Date_candidature"))
    candidate = " ".join(
        _single_line(profile.get(key)) for key in ("prenom", "nom_famille")
        if _single_line(profile.get(key))
    ) or _single_line(profile.get("nom"))
    phone = _single_line(profile.get("tel"))
    contact_line = f"\n{phone}" if phone else ""

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = f"Suivi de ma candidature – {position} – {company}"
    message.set_content(
        f"Bonjour,\n\n"
        f"Je me permets de revenir vers vous au sujet de ma candidature pour {position} "
        f"chez {company}, envoyée le {sent_date}.\n\n"
        "Je reste très intéressé(e) par cette opportunité et disponible pour tout complément "
        "d'information ou entretien.\n\n"
        f"Cordialement,\n{candidate}{contact_line}\n"
    )
    return message


def send_due_followups(user_id: str, today: date | None = None) -> dict:
    settings = S.load_state()["settings"]
    if not settings.get("automaticFollowups"):
        return {"sent": 0, "failed": 0, "skipped": 0}

    status = gmail.status()
    if not status.get("connected") or not status.get("send_authorized"):
        raise gmail.GmailError("Reconnecte Gmail et autorise l'envoi pour activer les relances automatiques.")
    if not status.get("read_authorized"):
        raise gmail.GmailError("L'accès Gmail en lecture est nécessaire pour vérifier les réponses avant une relance.")

    tracking = S.load_tracking()
    responded_ids = accounts.email_response_tracking_ids(user_id)
    pending_reviews = accounts.email_messages(user_id, reviews_only=True)
    candidates = due_followups(tracking, today or datetime.now(timezone.utc).date(), responded_ids)
    result = {"sent": 0, "failed": 0, "skipped": 0}

    for application in candidates:
        tracking_id = str(application["ID"])
        if _has_pending_reply(application, pending_reviews):
            result["skipped"] += 1
            continue
        if not accounts.claim_automatic_followup(user_id, tracking_id):
            result["skipped"] += 1
            continue
        try:
            gmail.send(_message(status["sender"], application, S.load_profile()))
        except gmail.GmailError as error:
            accounts.finish_automatic_followup(user_id, tracking_id, "failed", str(error))
            result["failed"] += 1
            continue

        accounts.finish_automatic_followup(user_id, tracking_id, "sent")
        row_index = tracking.index[tracking["ID"] == tracking_id]
        if len(row_index):
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            tracking.loc[row_index[0], "Date_relance"] = ""
            tracking.loc[row_index[0], "Derniere_activite"] = f"Relance automatique envoyée le {now[:10]}"
            tracking.loc[row_index[0], "Date_modification"] = now
            S.save_tracking(tracking)
        result["sent"] += 1
    return result
