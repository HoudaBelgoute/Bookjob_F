"""Clés API personnelles chiffrées et intégrations externes BookJob."""
from cryptography.fernet import Fernet, InvalidToken
import requests

from . import config as C


PROVIDERS = {
    "groq": {"category": "ai", "label": "Groq"},
    "anthropic": {"category": "ai", "label": "Anthropic / Claude"},
    "google_places": {"category": "data", "label": "Google Places"},
    "jooble": {"category": "data", "label": "Jooble"},
}


class IntegrationError(Exception):
    pass


def _cipher() -> Fernet:
    encryption_key = C.API_KEY_ENCRYPTION_KEY or C.AI_KEY_ENCRYPTION_KEY
    if not encryption_key:
        raise IntegrationError("Le stockage chiffré des clés personnelles n'est pas configuré sur le serveur.")
    try:
        return Fernet(encryption_key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as ex:
        raise IntegrationError("La configuration de chiffrement des clés personnelles est invalide.") from ex


def secret_path(provider: str):
    if not C.current_user_id():
        return None
    return C.user_path(C.DATA_DIR / "secrets" / "api-keys" / f"{provider}.enc")


def _legacy_groq_path():
    if not C.current_user_id():
        return None
    return C.user_path(C.DATA_DIR / "secrets" / "groq-api-key.enc")


def _configured_path(provider: str):
    path = secret_path(provider)
    if path and path.exists():
        return path
    if provider == "groq":
        legacy = _legacy_groq_path()
        if legacy and legacy.exists():
            return legacy
    return None


def personal_key(provider: str) -> str:
    if provider not in PROVIDERS:
        raise IntegrationError("Fournisseur non pris en charge.")
    path = _configured_path(provider)
    if path is None:
        return ""
    try:
        return _cipher().decrypt(path.read_bytes()).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError) as ex:
        raise IntegrationError("La clé personnelle est illisible avec la configuration actuelle.") from ex


def server_key(provider: str) -> str:
    return {
        "groq": C.GROQ_API_KEY,
        "anthropic": C.ANTHROPIC_API_KEY,
        "google_places": C.GOOGLE_API_KEY,
        "jooble": C.JOOBLE_API_KEY,
    }.get(provider, "")


def resolve_key(provider: str) -> str:
    personal = personal_key(provider)
    return personal or server_key(provider)


def _check_response(response, provider: str) -> None:
    if response.status_code in {401, 403}:
        raise IntegrationError(f"{PROVIDERS[provider]['label']} a refusé cette clé ou son accès à l'API.")
    if not response.ok:
        raise IntegrationError(f"{PROVIDERS[provider]['label']} n'a pas pu vérifier la clé pour le moment.")


def validate_key(provider: str, key: str) -> None:
    if provider not in PROVIDERS:
        raise IntegrationError("Fournisseur non pris en charge.")
    try:
        if provider == "groq":
            response = requests.get(
                "https://api.groq.com/openai/v1/models", timeout=15,
                headers={"Authorization": f"Bearer {key}"},
            )
        elif provider == "anthropic":
            response = requests.post(
                "https://api.anthropic.com/v1/messages", timeout=20,
                headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                json={"model": C.ANTHROPIC_MODEL, "max_tokens": 1,
                      "messages": [{"role": "user", "content": "OK"}]},
            )
        elif provider == "google_places":
            response = requests.post(
                "https://places.googleapis.com/v1/places:searchText", timeout=15,
                headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": "places.id"},
                json={"textQuery": "Marrakech", "pageSize": 1},
            )
        else:
            response = requests.post(
                f"https://jooble.org/api/{key}", timeout=15,
                json={"keywords": "stage", "location": "Marrakech"},
            )
    except requests.RequestException:
        raise IntegrationError(f"Impossible de joindre {PROVIDERS[provider]['label']} pour vérifier la clé.") from None
    _check_response(response, provider)


def save_key(provider: str, key: str) -> None:
    if provider not in PROVIDERS:
        raise IntegrationError("Fournisseur non pris en charge.")
    path = secret_path(provider)
    if path is None:
        raise IntegrationError("Connexion BookJob requise pour enregistrer une clé personnelle.")
    cleaned = key.strip()
    if not cleaned or len(cleaned) > 4096 or "\n" in cleaned or "\r" in cleaned:
        raise IntegrationError("Saisis une clé API valide.")
    cipher = _cipher()
    validate_key(provider, cleaned)
    path.write_bytes(cipher.encrypt(cleaned.encode("utf-8")))


def remove_key(provider: str) -> None:
    if provider not in PROVIDERS:
        raise IntegrationError("Fournisseur non pris en charge.")
    for path in (secret_path(provider), _legacy_groq_path() if provider == "groq" else None):
        if path and path.exists():
            path.unlink()


def key_status(provider: str) -> dict:
    if provider not in PROVIDERS:
        raise IntegrationError("Fournisseur non pris en charge.")
    configured = _configured_path(provider) is not None
    try:
        _cipher()
        encryption_available = True
    except IntegrationError:
        encryption_available = False
    usable = False
    if configured and encryption_available:
        try:
            usable = bool(personal_key(provider))
        except IntegrationError:
            pass
    return {
        "provider": provider,
        "category": PROVIDERS[provider]["category"],
        "label": PROVIDERS[provider]["label"],
        "personal_key_configured": configured,
        "personal_key_usable": usable,
        "server_key_configured": bool(server_key(provider)),
        "encryption_available": encryption_available,
        "mode": "unavailable" if configured and not usable else
                "personal" if configured else "server" if server_key(provider) else "none",
        "masked_key": "••••••••" if configured else "",
    }


def all_key_statuses() -> list[dict]:
    return [key_status(provider) for provider in PROVIDERS]
