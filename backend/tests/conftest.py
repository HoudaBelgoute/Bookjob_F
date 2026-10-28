import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Tests run against a dedicated Supabase project (never production).
#   SUPABASE_TEST_URL
#   SUPABASE_TEST_SERVICE_ROLE_KEY
# They are exported under the names the app reads, at import time, so that modules
# which import `app` at collection time (e.g. test_api.py) see them too.
_URL = os.environ.get("SUPABASE_TEST_URL", "")
_KEY = os.environ.get("SUPABASE_TEST_SERVICE_ROLE_KEY", "")
if _URL and _KEY:
    os.environ["SUPABASE_URL"] = _URL
    os.environ["SUPABASE_SERVICE_ROLE_KEY"] = _KEY


@pytest.fixture(scope="session")
def supabase_client():
    if not (_URL and _KEY):
        pytest.skip("Set SUPABASE_TEST_URL and SUPABASE_TEST_SERVICE_ROLE_KEY to run DB tests")
    from supabase import create_client
    return create_client(_URL, _KEY)


@pytest.fixture(autouse=True)
def _isolated_supabase_state(request, monkeypatch):
    """Replaces the old per-test tmp `auth.sqlite3`.

    Records which users exist before the test and deletes any created during it.
    Child tables (sessions, email_messages, email_sync_state, ...) must reference
    users.id with ON DELETE CASCADE so they are cleaned up too.
    """
    uses_db = bool(_URL and _KEY)
    if not uses_db:
        yield
        return
    from app import config as C
    monkeypatch.setattr(C, "SUPABASE_URL", _URL, raising=False)
    monkeypatch.setattr(C, "SUPABASE_SERVICE_ROLE_KEY", _KEY, raising=False)

    client = request.getfixturevalue("supabase_client")
    before = {row["id"] for row in client.table("users").select("id").execute().data}
    yield
    after = {row["id"] for row in client.table("users").select("id").execute().data}
    for user_id in after - before:
        client.table("users").delete().eq("id", user_id).execute()
