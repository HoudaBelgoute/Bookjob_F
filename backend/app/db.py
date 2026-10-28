"""Pool de connexions Postgres (Supabase) partagé par accounts.py et store.py."""
import os
import threading

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_pool = None
_lock = threading.Lock()


def connection():
    """Renvoie un gestionnaire de contexte : `with connection() as conn:` (commit/rollback automatiques)."""
    global _pool
    if _pool is None:
        with _lock:
            if _pool is None:
                pool = ConnectionPool(
                    os.environ["DATABASE_URL"],
                    min_size=1,
                    max_size=int(os.getenv("DB_POOL_MAX", "4")),
                    kwargs={"row_factory": dict_row, "prepare_threshold": None},
                    check=ConnectionPool.check_connection,
                    open=False,
                )
                pool.open()
                _pool = pool
    return _pool.connection()