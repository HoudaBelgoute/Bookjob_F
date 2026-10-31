"""Migration unique des données locales vers Supabase.

Copie :
  - backend/data/auth.sqlite3 : comptes, historique des statuts, e-mails analysés, état de synchro Gmail ;
  - backend/data/users/<id>/  : profil.json, state.json, suivi.csv et tous les fichiers (CV, avatar, jeton Gmail…).

Usage (depuis le dossier backend, DATABASE_URL défini) :
    python -m scripts.migrate_local_to_supabase            # simulation
    python -m scripts.migrate_local_to_supabase --apply    # écrit dans Supabase

Idempotent : les lignes déjà présentes ne sont pas dupliquées (les fichiers sont écrasés).
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app import config as C, db, store  # noqa: E402
from app.blobs import BlobPath  # noqa: E402

SQLITE_FILE = C.DATA_DIR / "auth.sqlite3"
USERS_DIR = C.DATA_DIR / "users"

TABLES = {
    "users": (["id", "email", "full_name", "password_hash", "password_salt", "created_at"], "(id)"),
    "email_sync_state": (["user_id", "last_checked", "status", "error"], "(user_id)"),
    "email_messages": ([
        "user_id", "message_id", "tracking_id", "classification", "confidence", "subject",
        "sender", "received_at", "snippet", "review_required",
    ], "(user_id, message_id)"),
}
EVENT_COLUMNS = ["user_id", "tracking_id", "old_status", "new_status", "source", "details", "occurred_at"]


def _sqlite_rows(conn: sqlite3.Connection, table: str, columns: list[str]) -> list[tuple]:
    present = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if not present:
        return []
    select = ", ".join(c if c in present else "NULL" for c in columns)
    return conn.execute(f"SELECT {select} FROM {table}").fetchall()


def migrate_sqlite(apply: bool) -> set[str]:
    if not SQLITE_FILE.is_file():
        print(f"- Pas de base SQLite ({SQLITE_FILE}) : étape ignorée")
        return set()
    src = sqlite3.connect(SQLITE_FILE)
    user_ids = {row[0] for row in src.execute("SELECT id FROM users")}
    for table, (columns, conflict) in TABLES.items():
        rows = _sqlite_rows(src, table, columns)
        print(f"- {table} : {len(rows)} ligne(s)")
        if apply and rows:
            placeholders = ", ".join(["%s"] * len(columns))
            with db.connection() as conn:
                with conn.cursor() as cur:
                    cur.executemany(
                        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) "
                        f"ON CONFLICT {conflict} DO NOTHING",
                        rows,
                    )
    events = _sqlite_rows(src, "application_events", EVENT_COLUMNS)
    print(f"- application_events : {len(events)} ligne(s)")
    if apply and events:
        with db.connection() as conn:
            existing = {
                tuple(r.values()) for r in conn.execute(
                    f"SELECT {', '.join(EVENT_COLUMNS)} FROM application_events"
                ).fetchall()
            }
            fresh = [row for row in events if tuple(row) not in existing]
            with conn.cursor() as cur:
                cur.executemany(
                    f"INSERT INTO application_events ({', '.join(EVENT_COLUMNS)}) "
                    f"VALUES ({', '.join(['%s'] * len(EVENT_COLUMNS))})",
                    fresh,
                )
    src.close()
    return user_ids


def migrate_user_dir(user_dir: Path, known_users: set[str], apply: bool) -> None:
    user_id = user_dir.name
    if known_users and user_id not in known_users:
        print(f"- {user_id} : aucun compte correspondant, ignoré")
        return
    print(f"- Utilisateur {user_id}")
    token = C.set_current_user(user_id)
    try:
        profil = user_dir / "profil.json"
        if profil.is_file():
            print("    profil.json")
            if apply:
                store.save_profile(json.loads(profil.read_text(encoding="utf-8")))
        state = user_dir / "state.json"
        if state.is_file():
            print("    state.json")
            if apply:
                store.save_state(json.loads(state.read_text(encoding="utf-8")))
        suivi = user_dir / "suivi.csv"
        if suivi.is_file():
            print("    suivi.csv")
            if apply:
                store.save_tracking(pd.read_csv(suivi, dtype=str).fillna(""))
        elif (user_dir / "donnees_nettoyees.xlsx").is_file():
            seeded = store.tracking_from_workbook(user_dir / "donnees_nettoyees.xlsx")
            print(f"    suivi depuis donnees_nettoyees.xlsx ({len(seeded)} ligne(s))")
            if apply and not seeded.empty:
                store.save_tracking(seeded)
        skip = {"profil.json", "state.json", "suivi.csv", "donnees_nettoyees.xlsx"}
        for path in sorted(p for p in user_dir.rglob("*") if p.is_file()):
            relative = path.relative_to(user_dir).as_posix()
            if relative in skip or relative.endswith(".tmp"):
                continue
            print(f"    fichier {relative} ({path.stat().st_size} o)")
            if apply:
                BlobPath(user_id, relative).write_bytes(path.read_bytes())
    finally:
        C.reset_current_user(token)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="écrit réellement dans Supabase")
    args = parser.parse_args()
    if args.apply:
        db.ensure_schema()
    print("Mode :", "ÉCRITURE" if args.apply else "simulation (ajoute --apply pour écrire)")
    known = migrate_sqlite(args.apply)
    if USERS_DIR.is_dir():
        for user_dir in sorted(p for p in USERS_DIR.iterdir() if p.is_dir()):
            migrate_user_dir(user_dir, known, args.apply)
    print("Terminé.")


if __name__ == "__main__":
    main()
