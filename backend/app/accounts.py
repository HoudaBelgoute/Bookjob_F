"""Comptes BookJob et sessions serveur révocables, stockés dans Postgres (Supabase).

Mêmes fonctions publiques que l'ancienne version SQLite.
Variable d'environnement requise : DATABASE_URL (Supabase, Transaction pooler, port 6543).
"""
import hashlib
import hmac
import logging
import os
import secrets
import shutil
import time

import json

import pandas as pd
import psycopg
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row

from . import config as C
from . import db
from . import store

log = logging.getLogger(__name__)

_PASSWORD_ROUNDS = 310_000

_SCHEMA_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT NOT NULL UNIQUE,
        full_name TEXT NOT NULL DEFAULT '',
        password_hash TEXT NOT NULL,
        password_salt TEXT NOT NULL,
        created_at BIGINT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS sessions (
        token_hash TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at BIGINT NOT NULL,
        created_at BIGINT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS sessions_user_id_idx ON sessions(user_id)",
    "CREATE INDEX IF NOT EXISTS sessions_expiry_idx ON sessions(expires_at)",
    """CREATE TABLE IF NOT EXISTS application_events (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        tracking_id TEXT NOT NULL,
        old_status TEXT NOT NULL,
        new_status TEXT NOT NULL,
        source TEXT NOT NULL,
        details TEXT NOT NULL DEFAULT '',
        occurred_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS email_messages (
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        message_id TEXT NOT NULL,
        tracking_id TEXT,
        classification TEXT NOT NULL,
        confidence DOUBLE PRECISION NOT NULL,
        subject TEXT NOT NULL,
        sender TEXT NOT NULL,
        received_at TEXT NOT NULL,
        snippet TEXT NOT NULL,
        review_required INTEGER NOT NULL,
        PRIMARY KEY (user_id, message_id)
    )""",
    """CREATE TABLE IF NOT EXISTS email_sync_state (
        user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        last_checked TEXT,
        status TEXT NOT NULL DEFAULT 'never',
        error TEXT NOT NULL DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS confirmation_owners (
        token_hash TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at BIGINT NOT NULL
    )""",
    # Bloque l'accès public via l'API Supabase (le backend, rôle postgres, n'est pas concerné).
    "ALTER TABLE users ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE sessions ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE application_events ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE email_messages ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE email_sync_state ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE confirmation_owners ENABLE ROW LEVEL SECURITY",
]


def _connect():
    return db.connection()


def initialize() -> None:
    with _connect() as connection:
        for statement in _SCHEMA_STATEMENTS:
            connection.execute(statement)


def _public_user(row: dict) -> dict:
    return {"id": row["id"], "email": row["email"], "full_name": row["full_name"]}


def _password_digest(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PASSWORD_ROUNDS)


def _import_legacy_data(user_id: str) -> None:
    """Donne les anciennes données locales au premier compte uniquement ; ne copie jamais d'identifiants."""
    token = C.set_current_user(user_id)
    try:
        legacy_tracking = C.DATA_DIR / "suivi.csv"
        if legacy_tracking.is_file():
            store.save_tracking(pd.read_csv(legacy_tracking, dtype=str).fillna(""))
        legacy_profile = C.DATA_DIR / "profil.json"
        if legacy_profile.is_file():
            loaded = json.loads(legacy_profile.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                store.save_profile(loaded)
        legacy_state = C.DATA_DIR / "state.json"
        if legacy_state.is_file():
            loaded = json.loads(legacy_state.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                store.save_state(loaded)
    except Exception:
        log.exception("Import des anciennes données impossible (le compte est créé quand même)")
    finally:
        C.reset_current_user(token)

    # Fichiers (classeur Excel, uploads) : copie « au mieux » ; sur Vercel le disque est en lecture seule.
    try:
        target = C.user_data_dir(user_id)
        target.mkdir(parents=True, exist_ok=True)
        workbook = C.DATA_DIR / "donnees_nettoyees.xlsx"
        if workbook.is_file():
            shutil.copy2(workbook, target / workbook.name)
        source_uploads = C.DATA_DIR / "uploads"
        if source_uploads.is_dir():
            shutil.copytree(source_uploads, target / "uploads", dirs_exist_ok=True)
        confirmations = C.DATA_DIR / "email_confirmations.json"
        if confirmations.is_file():
            shutil.copy2(confirmations, target / confirmations.name)
    except OSError:
        log.warning("Copie des fichiers locaux ignorée (disque en lecture seule ?)")


def _initialize_user_profile(user_id: str, full_name: str, email: str) -> None:
    token = C.set_current_user(user_id)
    try:
        profile = store.load_profile()
        profile["nom"] = full_name
        profile["email"] = email
        store.save_profile(profile)
    finally:
        C.reset_current_user(token)


def create_user(
    email: str,
    password: str,
    registration_key: str = "",
    full_name: str = "",
) -> tuple[dict, str]:
    normalized_email = email.strip().casefold()
    normalized_name = full_name.strip()
    if len(normalized_email) > 254 or normalized_email.count("@") != 1:
        raise ValueError("Saisis une adresse e-mail valide.")
    local, domain = normalized_email.split("@", 1)
    if not local or not domain or "." not in domain:
        raise ValueError("Saisis une adresse e-mail valide.")
    if len(password) < 10:
        raise ValueError("Le mot de passe doit contenir au moins 10 caractères.")
    if not normalized_name or len(normalized_name) > 120:
        raise ValueError("Saisis ton nom complet (120 caractères maximum).")

    with _connect() as connection:
        # Verrou de transaction : évite deux créations simultanées (remplace BEGIN IMMEDIATE).
        connection.execute("SELECT pg_advisory_xact_lock(727001)")
        count = connection.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        if count and C.REGISTRATION_KEY and not hmac.compare_digest(
            registration_key.encode(), C.REGISTRATION_KEY.encode()
        ):
            raise PermissionError("Une clé d’invitation valide est nécessaire pour créer un compte.")
        user_id = secrets.token_hex(16)
        salt = secrets.token_bytes(16)
        try:
            connection.execute(
                """INSERT INTO users (id, email, full_name, password_hash, password_salt, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (user_id, normalized_email, normalized_name, _password_digest(password, salt).hex(),
                 salt.hex(), int(time.time())),
            )
        except UniqueViolation as ex:
            raise ValueError("Un compte existe déjà avec cette adresse e-mail.") from ex

    if count == 0:
        _import_legacy_data(user_id)
    _initialize_user_profile(user_id, normalized_name, normalized_email)
    with _connect() as connection:
        user = connection.execute("SELECT * FROM users WHERE id = %s", (user_id,)).fetchone()
    return _public_user(user), create_session(user_id)


def authenticate(email: str, password: str) -> tuple[dict, str] | None:
    normalized_email = email.strip().casefold()
    with _connect() as connection:
        user = connection.execute("SELECT * FROM users WHERE email = %s", (normalized_email,)).fetchone()
    if user is None:
        # Perform the same work for unknown users to reduce account enumeration timing.
        _password_digest(password, b"\0" * 16)
        return None
    try:
        salt = bytes.fromhex(user["password_salt"])
        expected = bytes.fromhex(user["password_hash"])
    except ValueError:
        return None
    if not hmac.compare_digest(_password_digest(password, salt), expected):
        return None
    return _public_user(user), create_session(user["id"])


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def login_with_google(email: str, full_name: str = "") -> tuple[dict, str]:
    """Connexion par un e-mail vérifié par Google : rattache le compte existant ou en crée un.

    Un compte créé ainsi reçoit un mot de passe aléatoire inconnu : il se connecte uniquement via Google.
    """
    normalized_email = email.strip().casefold()
    with _connect() as connection:
        user = connection.execute("SELECT * FROM users WHERE email = %s", (normalized_email,)).fetchone()
    if user is not None:
        return _public_user(user), create_session(user["id"])
    if C.REGISTRATION_KEY and user_count() > 0:
        raise PermissionError("Les inscriptions se font sur invitation : crée d'abord ton compte avec la clé.")
    name = (full_name or normalized_email.split("@", 1)[0]).strip()[:120]
    return create_user(normalized_email, secrets.token_urlsafe(32), C.REGISTRATION_KEY, name)


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(48)
    now = int(time.time())
    with _connect() as connection:
        connection.execute("DELETE FROM sessions WHERE expires_at <= %s", (now,))
        connection.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at, created_at) VALUES (%s, %s, %s, %s)",
            (_token_digest(token), user_id, now + C.SESSION_MAX_AGE, now),
        )
    return token


def resolve_session(token: str) -> dict | None:
    if not token:
        return None
    now = int(time.time())
    with _connect() as connection:
        row = connection.execute(
            """SELECT users.id, users.email, users.full_name, sessions.token_hash
               FROM sessions JOIN users ON users.id = sessions.user_id
               WHERE sessions.token_hash = %s AND sessions.expires_at > %s""",
            (_token_digest(token), now),
        ).fetchone()
        connection.execute("DELETE FROM sessions WHERE expires_at <= %s", (now,))
    return _public_user(row) if row else None


def revoke_session(token: str) -> None:
    if not token:
        return
    with _connect() as connection:
        connection.execute("DELETE FROM sessions WHERE token_hash = %s", (_token_digest(token),))


def user_count() -> int:
    with _connect() as connection:
        return int(connection.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"])


def list_user_ids() -> list[str]:
    with _connect() as connection:
        rows = connection.execute("SELECT id FROM users ORDER BY created_at").fetchall()
    return [row["id"] for row in rows]


def first_user_id() -> str | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT id FROM users ORDER BY created_at, id LIMIT 1"
        ).fetchone()
    return row["id"] if row else None


def add_confirmation_owner(token_hash: str, user_id: str, expires_at: int) -> None:
    with _connect() as connection:
        connection.execute(
            """INSERT INTO confirmation_owners (token_hash, user_id, expires_at)
               VALUES (%s, %s, %s)
               ON CONFLICT (token_hash) DO UPDATE SET
                 user_id = EXCLUDED.user_id, expires_at = EXCLUDED.expires_at""",
            (token_hash, user_id, expires_at),
        )


def confirmation_user(token_hash: str) -> str | None:
    now = int(time.time())
    with _connect() as connection:
        row = connection.execute(
            "SELECT user_id FROM confirmation_owners WHERE token_hash = %s AND expires_at > %s",
            (token_hash, now),
        ).fetchone()
        connection.execute("DELETE FROM confirmation_owners WHERE expires_at <= %s", (now,))
    return row["user_id"] if row else None


def remove_confirmation_owner(token_hash: str) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM confirmation_owners WHERE token_hash = %s", (token_hash,))


def record_status_event(
    user_id: str | None,
    tracking_id: str,
    old_status: str,
    new_status: str,
    source: str,
    details: str,
    occurred_at: str,
) -> None:
    if not user_id or old_status == new_status:
        return
    with _connect() as connection:
        connection.execute(
            """INSERT INTO application_events
               (user_id, tracking_id, old_status, new_status, source, details, occurred_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (user_id, tracking_id, old_status, new_status, source, details, occurred_at),
        )


def status_events(user_id: str, tracking_id: str) -> list[dict]:
    with _connect() as connection:
        rows = connection.execute(
            """SELECT old_status, new_status, source, details, occurred_at
               FROM application_events WHERE user_id = %s AND tracking_id = %s
               ORDER BY id DESC""",
            (user_id, tracking_id),
        ).fetchall()
    return [dict(row) for row in rows]


def save_email_message(user_id: str, message: dict) -> bool:
    with _connect() as connection:
        cursor = connection.execute(
            """INSERT INTO email_messages
               (user_id, message_id, tracking_id, classification, confidence, subject,
                sender, received_at, snippet, review_required)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (user_id, message_id) DO NOTHING""",
            (
                user_id, message["message_id"], message.get("tracking_id"),
                message["classification"], message["confidence"], message["subject"],
                message["sender"], message["received_at"], message["snippet"],
                int(message["review_required"]),
            ),
        )
        inserted = cursor.rowcount == 1
    return inserted


def email_messages(user_id: str, *, reviews_only: bool = False) -> list[dict]:
    where = " AND review_required = 1" if reviews_only else ""
    with _connect() as connection:
        rows = connection.execute(
            """SELECT message_id, tracking_id, classification, confidence, subject,
                      sender, received_at, snippet, review_required
               FROM email_messages WHERE user_id = %s""" + where + " ORDER BY received_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def resolve_email_review(user_id: str, message_id: str, tracking_id: str, status: str) -> bool:
    with _connect() as connection:
        cursor = connection.execute(
            """UPDATE email_messages SET tracking_id = %s, classification = %s, review_required = 0
               WHERE user_id = %s AND message_id = %s AND review_required = 1""",
            (tracking_id, status, user_id, message_id),
        )
        updated = cursor.rowcount == 1
    return updated


def save_email_sync_state(user_id: str, status: str, last_checked: str = "", error: str = "") -> None:
    with _connect() as connection:
        connection.execute(
            """INSERT INTO email_sync_state (user_id, last_checked, status, error)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (user_id) DO UPDATE SET
                 last_checked = EXCLUDED.last_checked, status = EXCLUDED.status, error = EXCLUDED.error""",
            (user_id, last_checked or None, status, error),
        )


def email_sync_state(user_id: str) -> dict:
    with _connect() as connection:
        row = connection.execute(
            "SELECT last_checked, status, error FROM email_sync_state WHERE user_id = %s",
            (user_id,),
        ).fetchone()
    return dict(row) if row else {"last_checked": None, "status": "never", "error": ""}


def email_response_tracking_ids(user_id: str) -> set[str]:
    with _connect() as connection:
        rows = connection.execute(
            """SELECT DISTINCT tracking_id FROM email_messages
               WHERE user_id = %s AND tracking_id IS NOT NULL AND review_required = 0""",
            (user_id,),
        ).fetchall()
    return {row["tracking_id"] for row in rows}
