"""Private, one-time email confirmation requests for outgoing applications."""
import hashlib
import json
import os
from pathlib import Path


class ConfirmationStoreError(Exception):
    """The confirmation store could not be read or written safely."""


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def load(path: Path) -> dict[str, dict]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as ex:
        raise ConfirmationStoreError("Le stockage des confirmations est illisible.") from ex
    if not isinstance(value, dict):
        raise ConfirmationStoreError("Le stockage des confirmations est invalide.")
    return value


def save(path: Path, requests: dict[str, dict]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(requests, ensure_ascii=False), encoding="utf-8")
        if os.name == "posix":
            temporary.chmod(0o600)
        temporary.replace(path)
    except OSError as ex:
        raise ConfirmationStoreError("Impossible d'enregistrer la confirmation en attente.") from ex


def remove_for_tracking(requests: dict[str, dict], tracking_id: str) -> dict[str, dict]:
    return {digest: item for digest, item in requests.items() if item.get("tracking_id") != tracking_id}
