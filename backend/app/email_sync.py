"""Read-only Gmail synchronization and conservative application-response matching."""
import base64
import re
import threading
import unicodedata
from datetime import datetime, timezone
from email.utils import parseaddr

import pandas as pd

from . import accounts, gmail, store as S
from . import config as C

_SYNC_LOCK = threading.Lock()
_STOP_WORDS = {
    "a", "au", "aux", "de", "des", "du", "en", "et", "la", "le", "les", "pour",
    "stage", "emploi", "candidature", "offre", "chez", "the", "and", "for", "job",
}
_CLASSIFIERS = [
    (
        "Entretien programmé",
        re.compile(r"\b(entretien|interview|meeting invitation|schedule an interview|convocation)\b", re.I),
    ),
    (
        "Refusée",
        re.compile(
            r"(nous avons décidé de ne pas donner suite|candidature.{0,40}(?:pas retenue|non retenue)|"
            r"nous ne pouvons pas retenir|we regret to inform|not selected for|"
            r"unfortunately.{0,50}(?:application|candidacy).{0,30}(?:not|unsuccessful))",
            re.I,
        ),
    ),
    (
        "Acceptée",
        re.compile(
            r"(nous avons le plaisir de vous (?:annoncer|confirmer)|"
            r"nous souhaitons vous proposer|votre candidature est retenue|"
            r"we are pleased to offer|we would like to offer you|"
            r"you have been selected for)",
            re.I,
        ),
    ),
    (
        "En cours de traitement",
        re.compile(
            r"(informations? supplémentaires?|additional information|"
            r"please provide|veuillez nous transmettre|documents? manquants?|"
            r"application is under review|candidature est en cours d'étude)",
            re.I,
        ),
    ),
    (
        "En cours de traitement",
        re.compile(
            r"(accusé de réception|nous avons bien reçu|candidature.{0,30}reçue|"
            r"application.{0,20}received|thank you for applying|"
            r"thank you for your application)",
            re.I,
        ),
    ),
]


def _normalized(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in folded if not unicodedata.combining(char))


def classify_message(subject: str, body: str) -> tuple[str, float] | None:
    content = f"{subject}\n{body}"
    for status, pattern in _CLASSIFIERS:
        if pattern.search(content):
            confidence = 0.94 if status in {"Refusée", "Acceptée", "Entretien programmé"} else 0.86
            return status, confidence
    return None


def _message_text(part: dict) -> str:
    payload = part.get("payload", {})
    contents: list[str] = []

    def visit(node: dict) -> None:
        mime_type = node.get("mimeType", "")
        body = node.get("body", {})
        data = body.get("data") if isinstance(body, dict) else None
        if mime_type == "text/plain" and isinstance(data, str):
            try:
                raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
                contents.append(raw.decode("utf-8", errors="replace"))
            except (ValueError, TypeError):
                return
        for child in node.get("parts", []):
            if isinstance(child, dict):
                visit(child)

    if isinstance(payload, dict):
        visit(payload)
    return "\n".join(contents)[:30_000]


def _headers(message: dict) -> dict[str, str]:
    payload = message.get("payload", {})
    raw_headers = payload.get("headers", []) if isinstance(payload, dict) else []
    return {
        str(header.get("name", "")).casefold(): str(header.get("value", ""))
        for header in raw_headers
        if isinstance(header, dict)
    }


def _candidate_score(row: pd.Series, sender: str, subject: str, body: str) -> int:
    haystack = _normalized(f"{subject} {body}")
    score = 0
    recipient = str(row.get("Email_contact", "")).casefold().strip()
    sender_domain = parseaddr(sender)[1].rsplit("@", 1)[-1].casefold()
    recipient_domain = recipient.rsplit("@", 1)[-1] if "@" in recipient else ""
    if sender_domain and recipient_domain and sender_domain == recipient_domain:
        score += 3

    company_terms = [
        term for term in re.findall(r"[a-z0-9]{3,}", _normalized(str(row.get("Entreprise", ""))))
        if term not in _STOP_WORDS
    ]
    company_hits = sum(term in haystack for term in set(company_terms))
    if company_hits:
        score += 2 + min(company_hits, 2)

    job_terms = [
        term for term in re.findall(r"[a-z0-9]{3,}", _normalized(str(row.get("Poste_visé", ""))))
        if term not in _STOP_WORDS
    ]
    if job_terms:
        ratio = sum(term in haystack for term in set(job_terms)) / len(set(job_terms))
        if ratio >= 0.5:
            score += 2

    offer_url = str(row.get("Lien_offre", "")).casefold()
    if offer_url and offer_url.startswith("http") and offer_url.split("/", 3)[2] in haystack:
        score += 3
    return score


def match_message(data: pd.DataFrame, sender: str, subject: str, body: str) -> tuple[int | None, float]:
    scored = sorted(
        ((_candidate_score(row, sender, subject, body), index) for index, row in data.iterrows()),
        reverse=True,
    )
    if not scored or scored[0][0] < 3:
        return None, 0.0
    margin = scored[0][0] - (scored[1][0] if len(scored) > 1 else 0)
    confidence = min(0.99, 0.62 + scored[0][0] * 0.055 + max(margin, 0) * 0.025)
    if margin < 2 or confidence < 0.82:
        return None, confidence
    return scored[0][1], confidence


def _received_at(message: dict) -> str:
    try:
        milliseconds = int(message["internalDate"])
        return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc).isoformat(timespec="seconds")
    except (KeyError, TypeError, ValueError, OSError):
        return ""


def sync_current_user() -> dict:
    user_id = C.current_user_id()
    if not user_id:
        raise gmail.GmailError("Connexion BookJob requise pour synchroniser Gmail.")
    return sync_user(user_id)


def sync_user(user_id: str) -> dict:
    if not _SYNC_LOCK.acquire(blocking=False):
        raise gmail.GmailError("Une synchronisation Gmail est déjà en cours.")
    context_token = C.set_current_user(user_id)
    try:
        status = gmail.status()
        if not status.get("connected"):
            raise gmail.GmailError("Connecte Gmail pour synchroniser les réponses aux candidatures.")
        if not status.get("read_authorized"):
            raise gmail.GmailError("Reconnecte Gmail et autorise la lecture des messages pour activer le suivi.")

        messages = gmail.search_messages("newer_than:30d -from:me", max_results=100)
        data = S.load_tracking()
        added = 0
        auto_updated = 0
        for message_ref in messages:
            message_id = str(message_ref["id"])
            message = gmail.get_message(message_id)
            headers = _headers(message)
            subject = headers.get("subject", "")[:500]
            sender = headers.get("from", "")[:500]
            body = _message_text(message)
            snippet = str(message.get("snippet", "") or body[:500])[:1000]
            classification = classify_message(subject, body or snippet)
            if not classification:
                continue
            suggested_status, classifier_confidence = classification
            eligible = data[
                data["Date_candidature"].astype(str).str.strip().ne("")
                & ~data["Statut"].isin(
                    C.STATUTS_NON_ENVOYES | {"Offre expirée ou candidature annulée"}
                )
            ]
            match_index, match_confidence = match_message(
                eligible, sender, subject, body or snippet,
            )
            auto_match = match_index is not None and match_confidence >= 0.82 and classifier_confidence >= 0.85
            tracking_id = str(data.loc[match_index, "ID"]) if auto_match else None
            received_at = _received_at(message)
            record = {
                "message_id": message_id,
                "tracking_id": tracking_id,
                "classification": suggested_status,
                "confidence": min(classifier_confidence, match_confidence) if auto_match else classifier_confidence,
                "subject": subject,
                "sender": sender,
                "received_at": received_at,
                "snippet": snippet,
                "review_required": not auto_match,
            }
            if not accounts.save_email_message(user_id, record):
                continue
            added += 1
            if not auto_match:
                continue

            row_index = match_index
            previous_status = str(data.loc[row_index, "Statut"])
            if previous_status == suggested_status:
                data.loc[row_index, "Derniere_activite"] = subject
                data.loc[row_index, "Derniere_verification_email"] = received_at
                continue
            data.loc[row_index, "Statut"] = suggested_status
            data.loc[row_index, "Derniere_activite"] = subject
            data.loc[row_index, "Derniere_verification_email"] = received_at
            data.loc[row_index, "Date_modification"] = received_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
            if suggested_status == "Entretien programmé":
                data.loc[row_index, "Date_entretien"] = ""
            accounts.record_status_event(
                user_id,
                tracking_id,
                previous_status,
                suggested_status,
                "gmail",
                f"{subject} — {snippet}",
                received_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
            auto_updated += 1
        if auto_updated:
            S.save_tracking(data)
        checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if not data.empty:
            data["Derniere_verification_email"] = checked_at
            S.save_tracking(data)
        accounts.save_email_sync_state(user_id, "ok", checked_at)
        return {"checked_at": checked_at, "new_messages": added, "updated_applications": auto_updated}
    except gmail.GmailError as ex:
        accounts.save_email_sync_state(
            user_id, "error", datetime.now(timezone.utc).isoformat(timespec="seconds"), str(ex),
        )
        raise
    except (OSError, ValueError, KeyError, TypeError) as ex:
        message = "Erreur pendant la synchronisation des e-mails."
        accounts.save_email_sync_state(
            user_id, "error", datetime.now(timezone.utc).isoformat(timespec="seconds"), message,
        )
        raise RuntimeError(message) from ex
    finally:
        C.reset_current_user(context_token)
        _SYNC_LOCK.release()
