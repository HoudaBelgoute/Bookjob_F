"""SQLite-backed BookJob accounts and revocable server-side sessions."""
import hashlib
import hmac
import json
import os
import secrets
import shutil
import sqlite3
import time
from pathlib import Path

from . import config as C

_PASSWORD_ROUNDS = 310_000


def _connect() -> sqlite3.Connection:
    C.AUTH_DB.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(C.AUTH_DB, timeout=10)
    if os.name == "posix":
        C.AUTH_DB.chmod(0o600)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize() -> None:
    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                full_name TEXT NOT NULL DEFAULT '',
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS sessions_user_id_idx ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS sessions_expiry_idx ON sessions(expires_at);
            CREATE TABLE IF NOT EXISTS application_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                tracking_id TEXT NOT NULL,
                old_status TEXT NOT NULL,
                new_status TEXT NOT NULL,
                source TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT '',
                occurred_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS email_messages (
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                message_id TEXT NOT NULL,
                tracking_id TEXT,
                classification TEXT NOT NULL,
                confidence REAL NOT NULL,
                subject TEXT NOT NULL,
                sender TEXT NOT NULL,
                received_at TEXT NOT NULL,
                snippet TEXT NOT NULL,
                review_required INTEGER NOT NULL,
                PRIMARY KEY (user_id, message_id)
            );
            CREATE TABLE IF NOT EXISTS email_sync_state (
                user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                last_checked TEXT,
                status TEXT NOT NULL DEFAULT 'never',
                error TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS confirmation_owners (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL
            );
            """
        )
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(users)").fetchall()
        }
        if "full_name" not in columns:
            connection.execute("ALTER TABLE users ADD COLUMN full_name TEXT NOT NULL DEFAULT ''")


def _public_user(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "email": row["email"], "full_name": row["full_name"]}


def _password_digest(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PASSWORD_ROUNDS)


def _import_legacy_data(user_id: str) -> None:
    """Give the pre-account local data to the first account only; never copy credentials."""
    target = C.user_data_dir(user_id)
    target.mkdir(parents=True, exist_ok=True)
    for name in ("suivi.csv", "profil.json", "state.json", "donnees_nettoyees.xlsx"):
        source = C.DATA_DIR / name
        if source.is_file():
            shutil.copy2(source, target / name)
    source_uploads = C.DATA_DIR / "uploads"
    if source_uploads.is_dir():
        shutil.copytree(source_uploads, target / "uploads", dirs_exist_ok=True)
    confirmations = C.DATA_DIR / "email_confirmations.json"
    if confirmations.is_file():
        shutil.copy2(confirmations, target / confirmations.name)


def _initialize_user_profile(user_id: str, full_name: str, email: str) -> None:
    context_token = C.set_current_user(user_id)
    try:
        path = C.user_path(C.PROFIL)
    finally:
        C.reset_current_user(context_token)
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                profile = loaded
        except json.JSONDecodeError:
            pass
    profile["nom"] = full_name
    profile["email"] = email
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(profile, ensure_ascii=False, indent=1), encoding="utf-8")
    temporary.replace(path)


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
        connection.execute("BEGIN IMMEDIATE")
        count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count and C.REGISTRATION_KEY and not hmac.compare_digest(
            registration_key.encode(), C.REGISTRATION_KEY.encode()
        ):
            raise PermissionError("Une clé d’invitation valide est nécessaire pour créer un compte.")
        user_id = secrets.token_hex(16)
        salt = secrets.token_bytes(16)
        try:
            connection.execute(
                """INSERT INTO users (id, email, full_name, password_hash, password_salt, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, normalized_email, normalized_name, _password_digest(password, salt).hex(),
                 salt.hex(), int(time.time())),
            )
        except sqlite3.IntegrityError as ex:
            raise ValueError("Un compte existe déjà avec cette adresse e-mail.") from ex

    if count == 0:
        _import_legacy_data(user_id)
    _initialize_user_profile(user_id, normalized_name, normalized_email)
    with _connect() as connection:
        user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _public_user(user), create_session(user_id)


def authenticate(email: str, password: str) -> tuple[dict, str] | None:
    normalized_email = email.strip().casefold()
    with _connect() as connection:
        user = connection.execute("SELECT * FROM users WHERE email = ?", (normalized_email,)).fetchone()
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
        user = connection.execute("SELECT * FROM users WHERE email = ?", (normalized_email,)).fetchone()
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
        connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        connection.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
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
               WHERE sessions.token_hash = ? AND sessions.expires_at > ?""",
            (_token_digest(token), now),
        ).fetchone()
        connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
    return _public_user(row) if row else None


def revoke_session(token: str) -> None:
    if not token:
        return
    with _connect() as connection:
        connection.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_digest(token),))


def user_count() -> int:
    with _connect() as connection:
        return int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])


def list_user_ids() -> list[str]:
    with _connect() as connection:
        rows = connection.execute("SELECT id FROM users ORDER BY created_at").fetchall()
    return [row["id"] for row in rows]


def first_user_id() -> str | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT id FROM users ORDER BY created_at, rowid LIMIT 1"
        ).fetchone()
    return row["id"] if row else None


def add_confirmation_owner(token_hash: str, user_id: str, expires_at: int) -> None:
    with _connect() as connection:
        connection.execute(
            """INSERT OR REPLACE INTO confirmation_owners (token_hash, user_id, expires_at)
               VALUES (?, ?, ?)""",
            (token_hash, user_id, expires_at),
        )


def confirmation_user(token_hash: str) -> str | None:
    now = int(time.time())
    with _connect() as connection:
        row = connection.execute(
            "SELECT user_id FROM confirmation_owners WHERE token_hash = ? AND expires_at > ?",
            (token_hash, now),
        ).fetchone()
        connection.execute("DELETE FROM confirmation_owners WHERE expires_at <= ?", (now,))
    return row["user_id"] if row else None


def remove_confirmation_owner(token_hash: str) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM confirmation_owners WHERE token_hash = ?", (token_hash,))


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
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, tracking_id, old_status, new_status, source, details, occurred_at),
        )


def status_events(user_id: str, tracking_id: str) -> list[dict]:
    with _connect() as connection:
        rows = connection.execute(
            """SELECT old_status, new_status, source, details, occurred_at
               FROM application_events WHERE user_id = ? AND tracking_id = ?
               ORDER BY id DESC""",
            (user_id, tracking_id),
        ).fetchall()
    return [dict(row) for row in rows]


def save_email_message(user_id: str, message: dict) -> bool:
    with _connect() as connection:
        cursor = connection.execute(
            """INSERT OR IGNORE INTO email_messages
               (user_id, message_id, tracking_id, classification, confidence, subject,
                sender, received_at, snippet, review_required)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id, message["message_id"], message.get("tracking_id"),
                message["classification"], message["confidence"], message["subject"],
                message["sender"], message["received_at"], message["snippet"],
                int(message["review_required"]),
            ),
        )
    return cursor.rowcount == 1


def email_messages(user_id: str, *, reviews_only: bool = False) -> list[dict]:
    where = " AND review_required = 1" if reviews_only else ""
    with _connect() as connection:
        rows = connection.execute(
            """SELECT message_id, tracking_id, classification, confidence, subject,
                      sender, received_at, snippet, review_required
               FROM email_messages WHERE user_id = ?""" + where + " ORDER BY received_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def resolve_email_review(user_id: str, message_id: str, tracking_id: str, status: str) -> bool:
    with _connect() as connection:
        cursor = connection.execute(
            """UPDATE email_messages SET tracking_id = ?, classification = ?, review_required = 0
               WHERE user_id = ? AND message_id = ? AND review_required = 1""",
            (tracking_id, status, user_id, message_id),
        )
    return cursor.rowcount == 1


def save_email_sync_state(user_id: str, status: str, last_checked: str = "", error: str = "") -> None:
    with _connect() as connection:
        connection.execute(
            """INSERT INTO email_sync_state (user_id, last_checked, status, error)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                 last_checked = excluded.last_checked, status = excluded.status, error = excluded.error""",
            (user_id, last_checked or None, status, error),
        )


def email_sync_state(user_id: str) -> dict:
    with _connect() as connection:
        row = connection.execute(
            "SELECT last_checked, status, error FROM email_sync_state WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else {"last_checked": None, "status": "never", "error": ""}


def email_response_tracking_ids(user_id: str) -> set[str]:
    with _connect() as connection:
        rows = connection.execute(
            """SELECT DISTINCT tracking_id FROM email_messages
               WHERE user_id = ? AND tracking_id IS NOT NULL AND review_required = 0""",
            (user_id,),
        ).fetchall()
    return {row["tracking_id"] for row in rows}
