import os
import sys
from pathlib import Path

import psycopg
import pytest

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Base de TEST uniquement : ces tests suppriment des lignes.
_URL = os.environ.get("TEST_DATABASE_URL", "")
if _URL:
    os.environ["DATABASE_URL"] = _URL  # avant l'import de `app`


@pytest.fixture(scope="session")
def db_conn():
    if not _URL:
        pytest.skip("Définis TEST_DATABASE_URL pour lancer les tests qui touchent la base")
    with psycopg.connect(_URL, autocommit=True) as conn:
        yield conn


@pytest.fixture(autouse=True)
def _isolated_db_state(request):
    if not _URL:
        yield
        return
    conn = request.getfixturevalue("db_conn")
    before = {r[0] for r in conn.execute("select id from users").fetchall()}
    yield
    after = {r[0] for r in conn.execute("select id from users").fetchall()}
    for user_id in after - before:
        conn.execute("delete from users where id = %s", (user_id,))
        for table in ("user_files", "user_state", "user_profile", "user_tracking"):
            conn.execute(f"delete from {table} where user_id = %s", (user_id,))