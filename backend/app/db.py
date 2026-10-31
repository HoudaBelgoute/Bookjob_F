"""Connexion Postgres (Supabase) partagée par tout le backend.

Variable d'environnement requise : DATABASE_URL
(Supabase > Connect > Transaction pooler, port 6543, recommandé pour Vercel).
Le schéma (supabase/schema.sql) est appliqué automatiquement une fois par processus.
"""
import os
import threading
from contextlib import contextmanager
from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "supabase" / "schema.sql"

_pool: ConnectionPool | None = None
_lock = threading.RLock()
_schema_ready = False


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL n'est pas défini : renseigne la chaîne de connexion Supabase (Transaction pooler)."
        )
    return url


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        with _lock:
            if _pool is None:
                pool = ConnectionPool(
                    _database_url(),
                    min_size=int(os.getenv("DB_POOL_MIN", "1")),
                    max_size=int(os.getenv("DB_POOL_MAX", "4")),
                    max_idle=60,
                    # prepare_threshold=None : obligatoire avec le Transaction pooler (pgbouncer/supavisor)
                    kwargs={"row_factory": dict_row, "prepare_threshold": None},
                    check=ConnectionPool.check_connection,
                    open=False,
                )
                pool.open(wait=True, timeout=30)
                _pool = pool
    return _pool


def ensure_schema() -> None:
    """Crée les tables manquantes (idempotent, protégé contre les démarrages simultanés)."""
    global _schema_ready
    if _schema_ready:
        return
    with _lock:
        if _schema_ready:
            return
        with _get_pool().connection() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(727000)")
            conn.execute(SCHEMA_FILE.read_text(encoding="utf-8"))
        _schema_ready = True


@contextmanager
def connection():
    """`with connection() as conn:` — commit automatique en sortie, rollback en cas d'erreur."""
    ensure_schema()
    with _get_pool().connection() as conn:
        yield conn
