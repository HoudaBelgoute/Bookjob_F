"""Per-user Google OAuth and Gmail API access."""
import base64
import json
import os
import secrets
import time
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import requests

from . import config as C

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
DRAFTS_URL = "https://gmail.googleapis.com/gmail/v1/users/me/drafts"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_READ_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
SCOPES = f"openid email {GMAIL_SEND_SCOPE} {GMAIL_READ_SCOPE} {GMAIL_COMPOSE_SCOPE}"


class GmailError(Exception):
    """An OAuth or Gmail API operation failed."""


def configured() -> bool:
    return bool(C.GOOGLE_OAUTH_CLIENT_ID and C.GOOGLE_OAUTH_CLIENT_SECRET and C.GOOGLE_OAUTH_REDIRECT_URI)


def authorization_url(state: str) -> str:
    if not configured():
        raise GmailError("La connexion Google n'est pas configurée sur le serveur.")
    params = {
        "client_id": C.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": C.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent select_account",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def _migrate_legacy_credentials(token_file: Path) -> None:
    user_id = C.current_user_id()
    if not user_id or token_file.exists():
        return

    from . import accounts

    legacy_file = C.GOOGLE_TOKEN_FILE
    if user_id != accounts.first_user_id() or legacy_file == token_file or not legacy_file.is_file():
        return

    try:
        payload = legacy_file.read_bytes()
        credentials = json.loads(payload)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as ex:
        raise GmailError("L'ancien jeton Google local est illisible. Reconnecte ton compte Gmail.") from ex
    if not isinstance(credentials, dict) or not credentials.get("refresh_token"):
        return

    token_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = token_file.with_name(f".{token_file.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp")
    try:
        temporary.write_bytes(payload)
        if os.name == "posix":
            temporary.chmod(0o600)
        temporary.replace(token_file)
        legacy_file.unlink(missing_ok=True)
    except OSError as ex:
        temporary.unlink(missing_ok=True)
        raise GmailError("Impossible de restaurer la connexion Gmail de ton compte existant.") from ex


def _read_credentials() -> dict:
    token_file = C.user_path(C.GOOGLE_TOKEN_FILE)
    _migrate_legacy_credentials(token_file)
    try:
        credentials = json.loads(token_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise GmailError("Aucun compte Gmail n'est connecté à BookJob.")
    except (json.JSONDecodeError, OSError) as ex:
        raise GmailError("Le jeton Google local est illisible. Reconnecte ton compte Gmail.") from ex
    if not isinstance(credentials, dict) or not credentials.get("refresh_token"):
        raise GmailError("Le jeton Google est incomplet. Reconnecte ton compte Gmail.")
    return credentials


def _write_credentials(credentials: dict) -> None:
    path = C.user_path(C.GOOGLE_TOKEN_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(credentials), encoding="utf-8")
    if os.name == "posix":
        temporary.chmod(0o600)
    temporary.replace(path)


def _request_json(url: str, *, data: dict | None = None, headers: dict | None = None) -> dict:
    try:
        response = requests.post(url, data=data, headers=headers, timeout=20)
    except requests.RequestException as ex:
        raise GmailError("Google n'est pas joignable. Vérifie ta connexion Internet.") from ex
    if not response.ok:
        raise GmailError(f"Google a refusé la requête (HTTP {response.status_code}).")
    try:
        result = response.json()
    except ValueError as ex:
        raise GmailError("Google a renvoyé une réponse invalide.") from ex
    if not isinstance(result, dict):
        raise GmailError("Google a renvoyé une réponse invalide.")
    return result


def _userinfo(access_token: str) -> str:
    try:
        response = requests.get(
            USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
    except requests.RequestException as ex:
        raise GmailError("Impossible de vérifier le compte Google connecté.") from ex
    if not response.ok:
        raise GmailError(f"Google n'a pas permis de vérifier le compte (HTTP {response.status_code}).")
    try:
        email = response.json().get("email", "")
    except (ValueError, AttributeError) as ex:
        raise GmailError("Google a renvoyé une identité de compte invalide.") from ex
    if not isinstance(email, str) or "@" not in email:
        raise GmailError("Google n'a pas renvoyé l'adresse du compte autorisé.")
    return email


def exchange_code(code: str) -> str:
    if not configured():
        raise GmailError("La connexion Google n'est pas configurée sur le serveur.")
    token = _request_json(TOKEN_URL, data={
        "code": code,
        "client_id": C.GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": C.GOOGLE_OAUTH_CLIENT_SECRET,
        "redirect_uri": C.GOOGLE_OAUTH_REDIRECT_URI,
        "grant_type": "authorization_code",
    })
    access_token = token.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise GmailError("Google n'a pas fourni de jeton d'accès.")
    granted_scopes = set(str(token.get("scope", "")).split())
    required_scopes = {GMAIL_SEND_SCOPE, GMAIL_READ_SCOPE, GMAIL_COMPOSE_SCOPE}
    if not required_scopes.issubset(granted_scopes):
        raise GmailError("Les autorisations Gmail de lecture, d'envoi et de création de brouillons n'ont pas toutes été accordées.")

    try:
        stored_credentials = json.loads(C.user_path(C.GOOGLE_TOKEN_FILE).read_text(encoding="utf-8"))
    except FileNotFoundError:
        previous_refresh_token = ""
    except (json.JSONDecodeError, OSError) as ex:
        raise GmailError("Le jeton Google local est illisible. Reconnecte ton compte Gmail.") from ex
    else:
        if not isinstance(stored_credentials, dict):
            raise GmailError("Le jeton Google local est invalide. Reconnecte ton compte Gmail.")
        previous_refresh_token = stored_credentials.get("refresh_token", "")
    refresh_token = token.get("refresh_token") or previous_refresh_token
    if not refresh_token:
        raise GmailError("Google n'a pas fourni de jeton de renouvellement. Réessaie l'autorisation.")
    email = _userinfo(access_token)
    credentials = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": time.time() + int(token.get("expires_in", 3600)),
        "email": email,
        "scopes": sorted(granted_scopes),
    }
    _write_credentials(credentials)
    return email


def status() -> dict:
    if not configured():
        return {"configured": False, "connected": False, "sender": "", "callback_origin": ""}
    callback = urlsplit(C.GOOGLE_OAUTH_REDIRECT_URI)
    callback_origin = f"{callback.scheme}://{callback.netloc}" if callback.scheme and callback.netloc else ""
    try:
        credentials = _read_credentials()
    except GmailError as ex:
        return {
            "configured": True, "connected": False, "sender": "",
            "callback_origin": callback_origin, "error": str(ex),
        }
    sender = credentials.get("email", "")
    return {
        "configured": True, "connected": bool(sender), "sender": sender,
        "callback_origin": callback_origin,
        "read_authorized": GMAIL_READ_SCOPE in credentials.get("scopes", []),
        "draft_authorized": GMAIL_COMPOSE_SCOPE in credentials.get("scopes", []),
    }


def _access_token(force_refresh: bool = False) -> str:
    credentials = _read_credentials()
    try:
        expires_at = float(credentials.get("expires_at", 0))
    except (TypeError, ValueError) as ex:
        raise GmailError("Le jeton Google local est invalide. Reconnecte ton compte Gmail.") from ex
    if not force_refresh and expires_at > time.time() + 60:
        return str(credentials["access_token"])
    token = _request_json(TOKEN_URL, data={
        "client_id": C.GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": C.GOOGLE_OAUTH_CLIENT_SECRET,
        "refresh_token": credentials["refresh_token"],
        "grant_type": "refresh_token",
    })
    access_token = token.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise GmailError("Google n'a pas renouvelé le jeton. Reconnecte ton compte Gmail.")
    credentials["access_token"] = access_token
    credentials["expires_at"] = time.time() + int(token.get("expires_in", 3600))
    _write_credentials(credentials)
    return access_token


def send(message: EmailMessage) -> None:
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii").rstrip("=")
    access_token = _access_token()
    for attempt in range(2):
        try:
            response = requests.post(
                SEND_URL,
                json={"raw": raw_message},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30,
            )
        except requests.RequestException as ex:
            raise GmailError("Google Gmail n'est pas joignable. L'e-mail n'a pas été envoyé.") from ex
        if response.ok:
            return
        if response.status_code == 401 and attempt == 0:
            access_token = _access_token(force_refresh=True)
            continue
        raise GmailError(f"Gmail a refusé l'envoi (HTTP {response.status_code}).")


def _gmail_post(url: str, payload: dict, operation: str):
    access_token = _access_token()
    for attempt in range(2):
        try:
            response = requests.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30,
            )
        except requests.RequestException as ex:
            raise GmailError(f"Gmail n'est pas joignable. {operation} impossible.") from ex
        if response.ok:
            return response
        if response.status_code == 401 and attempt == 0:
            access_token = _access_token(force_refresh=True)
            continue
        raise GmailError(f"Gmail a refusé l'opération « {operation} » (HTTP {response.status_code}).")
    raise GmailError(f"La session Gmail a expiré. {operation} impossible.")


def create_draft(message: EmailMessage) -> str:
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii").rstrip("=")
    response = _gmail_post(
        DRAFTS_URL,
        {"message": {"raw": raw_message}},
        "création du brouillon",
    )
    try:
        draft_id = response.json().get("id")
    except (ValueError, AttributeError) as ex:
        raise GmailError("Gmail n'a pas renvoyé l'identifiant du brouillon.") from ex
    if not isinstance(draft_id, str) or not draft_id:
        raise GmailError("Gmail n'a pas renvoyé l'identifiant du brouillon.")
    return draft_id


def send_draft(draft_id: str) -> None:
    if not draft_id:
        raise GmailError("Le brouillon Gmail n'est plus disponible.")
    _gmail_post(
        f"{DRAFTS_URL}/send",
        {"id": draft_id},
        "envoi du brouillon",
    )


def delete_draft(draft_id: str) -> None:
    if not draft_id:
        return
    access_token = _access_token()
    for attempt in range(2):
        try:
            response = requests.delete(
                f"{DRAFTS_URL}/{draft_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=20,
            )
        except requests.RequestException as ex:
            raise GmailError("Gmail n'est pas joignable. Le brouillon n'a pas pu être supprimé.") from ex
        if response.ok or response.status_code == 404:
            return
        if response.status_code == 401 and attempt == 0:
            access_token = _access_token(force_refresh=True)
            continue
        raise GmailError(f"Gmail a refusé la suppression du brouillon (HTTP {response.status_code}).")
    raise GmailError("La session Gmail a expiré. Le brouillon n'a pas pu être supprimé.")


def _get_json(url: str, *, params: dict | None = None) -> dict:
    access_token = _access_token()
    for attempt in range(2):
        try:
            response = requests.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=20,
            )
        except requests.RequestException as ex:
            raise GmailError("Gmail n'est pas joignable pour synchroniser les réponses.") from ex
        if response.status_code == 401 and attempt == 0:
            access_token = _access_token(force_refresh=True)
            continue
        if not response.ok:
            if response.status_code == 403:
                raise GmailError(
                    "Gmail refuse la lecture des messages. Reconnecte le compte et autorise la lecture Gmail."
                )
            raise GmailError(f"Gmail a refusé la synchronisation (HTTP {response.status_code}).")
        try:
            result = response.json()
        except ValueError as ex:
            raise GmailError("Gmail a renvoyé une réponse invalide pendant la synchronisation.") from ex
        if not isinstance(result, dict):
            raise GmailError("Gmail a renvoyé une réponse invalide pendant la synchronisation.")
        return result
    raise GmailError("La session Gmail a expiré. Reconnecte le compte.")


def search_messages(query: str, max_results: int = 100) -> list[dict]:
    if not status().get("read_authorized"):
        raise GmailError("Reconnecte Gmail et autorise la lecture des messages pour activer le suivi.")
    result = _get_json(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages",
        params={"q": query, "maxResults": min(max(max_results, 1), 100)},
    )
    messages = result.get("messages", [])
    if not isinstance(messages, list):
        raise GmailError("Gmail a renvoyé une liste de messages invalide.")
    return [message for message in messages if isinstance(message, dict) and message.get("id")]


def get_message(message_id: str) -> dict:
    if not status().get("read_authorized"):
        raise GmailError("Reconnecte Gmail et autorise la lecture des messages pour activer le suivi.")
    result = _get_json(
        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
        params={"format": "full"},
    )
    if not isinstance(result.get("payload"), dict):
        raise GmailError("Gmail n'a pas fourni le contenu du message.")
    return result


def disconnect() -> None:
    credentials = _read_credentials()
    try:
        try:
            response = requests.post(
                REVOKE_URL,
                data={"token": credentials["refresh_token"]},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=20,
            )
        except requests.RequestException as ex:
            raise GmailError(
                "Google est injoignable. Le compte a été déconnecté de BookJob, "
                "mais la révocation Google n'a pas pu être confirmée."
            ) from ex
        if not response.ok and response.status_code != 400:
            raise GmailError(
                f"Google a refusé la révocation (HTTP {response.status_code}). "
                "Le compte a été déconnecté de BookJob."
            )
    finally:
        C.user_path(C.GOOGLE_TOKEN_FILE).unlink(missing_ok=True)
