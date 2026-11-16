import pandas as pd
from cryptography.fernet import Fernet

from app import ai, config as C, data_sources, integrations, main


def _set_owner(user_id):
    return C.set_current_user(user_id)


def test_personal_keys_are_encrypted_and_isolated_by_account(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "AI_KEY_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.setattr(C, "API_KEY_ENCRYPTION_KEY", "")

    def user_path(path):
        destination = tmp_path / C.current_user_id() / path.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        return destination

    monkeypatch.setattr(C, "user_path", user_path)
    monkeypatch.setattr(integrations, "validate_key", lambda provider, key: None)

    owner = _set_owner("account-one")
    try:
        integrations.save_key("anthropic", "personal-secret")
        status = integrations.key_status("anthropic")
        stored = integrations.secret_path("anthropic").read_bytes()
        assert stored != b"personal-secret"
        assert integrations.personal_key("anthropic") == "personal-secret"
        assert status["personal_key_configured"] and status["personal_key_usable"]
        assert status["masked_key"] == "••••••••"
        assert "personal-secret" not in repr(status)
    finally:
        C.reset_current_user(owner)

    owner = _set_owner("account-two")
    try:
        assert integrations.key_status("anthropic")["personal_key_configured"] is False
        assert integrations.resolve_key("anthropic") == C.ANTHROPIC_API_KEY
    finally:
        C.reset_current_user(owner)


def test_key_requires_encryption_and_live_validation_before_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "AI_KEY_ENCRYPTION_KEY", "")
    monkeypatch.setattr(C, "API_KEY_ENCRYPTION_KEY", "")
    monkeypatch.setattr(C, "user_path", lambda path: tmp_path / path.name)
    owner = _set_owner("account-one")
    try:
        try:
            integrations.save_key("groq", "unvalidated-secret")
        except integrations.IntegrationError as error:
            assert "chiffré" in str(error)
        else:
            raise AssertionError("Saving a personal key must require encryption.")
        assert not list(tmp_path.iterdir())
    finally:
        C.reset_current_user(owner)


def test_anthropic_key_validation_and_completion_use_real_provider_contract(monkeypatch):
    calls = []

    class Response:
        ok = True
        status_code = 200

        def raise_for_status(self):
            pass

        @staticmethod
        def json():
            return {"content": [{"type": "text", "text": "Lettre générée"}]}

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(integrations.requests, "post", post)
    integrations.validate_key("anthropic", "anthropic-test-key")
    monkeypatch.setattr(C, "ANTHROPIC_API_KEY", "anthropic-test-key")
    monkeypatch.setattr(C, "GROQ_API_KEY", "")
    assert ai.provider() == "anthropic"
    assert ai.complete("Instructions", [{"role": "user", "content": "Profil"}], 123) == "Lettre générée"
    assert calls[0][0] == "https://api.anthropic.com/v1/messages"
    assert calls[0][1]["headers"]["x-api-key"] == "anthropic-test-key"
    assert calls[0][1]["json"]["max_tokens"] == 1
    assert calls[1][1]["json"]["max_tokens"] == 123
    assert calls[1][1]["json"]["system"] == "Instructions"
    assert calls[1][1]["headers"]["x-api-key"] == "anthropic-test-key"


def test_jooble_search_uses_personal_or_server_key_and_normalizes_results(monkeypatch):
    monkeypatch.setattr(C, "JOOBLE_API_KEY", "server-jooble-key")
    captured = {}

    class Response:
        def raise_for_status(self):
            pass

        @staticmethod
        def json():
            return {"jobs": [{
                "id": "job-1", "title": "Stage Data", "company": "Acme",
                "location": "Marrakech", "link": "https://jobs.example/job-1",
                "snippet": "Analyse de données",
            }]}

    def post(url, *, timeout, json):
        captured.update(url=url, timeout=timeout, payload=json)
        return Response()

    monkeypatch.setattr(data_sources.requests, "post", post)
    results = data_sources.search("jooble", "stage data", "Marrakech")
    assert captured == {
        "url": "https://jooble.org/api/server-jooble-key",
        "timeout": 20,
        "payload": {"keywords": "stage data", "location": "Marrakech"},
    }
    assert results[0]["source"] == "Jooble"
    assert results[0]["title"] == "Stage Data"
    assert results[0]["company"] == "Acme"
    assert results[0]["url"] == "https://jobs.example/job-1"
    assert results[0]["retrieved_at"]


def test_google_place_refresh_returns_live_details_without_persisting_content(monkeypatch):
    captured = []

    class Response:
        def raise_for_status(self):
            pass

        @staticmethod
        def json():
            return {
                "id": "places/place-1",
                "displayName": {"text": "Entreprise locale"},
                "formattedAddress": "Marrakech",
                "googleMapsUri": "https://maps.google.com/?cid=1",
            }

    def get(url, *, timeout, headers):
        captured.append((url, headers))
        return Response()

    monkeypatch.setattr(data_sources.requests, "get", get)
    result = data_sources.place_details("places-test-key", ["places/place-1"])[0]
    assert captured[0][0].endswith("/places%2Fplace-1")
    assert captured[0][1]["X-Goog-Api-Key"] == "places-test-key"
    assert result["title"] == "Entreprise locale"
    assert result["external_id"] == "places/place-1"
    assert result["attribution"] == "Google Maps"


def test_jooble_import_adds_selected_offer_to_account_tracking(monkeypatch):
    item = {
        "id": "result-1", "external_id": "job-1", "kind": "job", "provider": "jooble",
        "source": "Jooble", "title": "Stage Data", "company": "Acme", "sector": "",
        "location": "Marrakech", "phone": "", "website": "",
        "url": "https://jobs.example/job-1", "description": "Analyse de données",
        "retrieved_at": "2026-11-16T15:00:00+00:00", "attribution": "Jooble",
    }
    state = {"dataSourceReviews": {"review-1": [item]}, "savedGooglePlaces": []}
    saved = {}
    monkeypatch.setattr(main.S, "load_state", lambda: state)
    monkeypatch.setattr(main.S, "save_state", lambda value: None)
    monkeypatch.setattr(main.S, "load_tracking", lambda: pd.DataFrame(columns=C.COLS))
    monkeypatch.setattr(main.S, "save_tracking", lambda data: saved.setdefault("data", data.copy()))

    result = main.import_data_source_results(main.SourceImportIn(
        provider="jooble", review_id="review-1", item_ids=["result-1"],
    ))
    row = saved["data"].iloc[0]
    assert result["imported"][0]["source"] == "Jooble"
    assert row["Entreprise"] == "Acme"
    assert row["Poste_visé"] == "Stage Data"
    assert row["Lien_offre"] == "https://jobs.example/job-1"
    assert "2026-11-16T15:00:00+00:00" in row["Remarque"]
    assert state["dataSourceReviews"] == {}


def test_google_import_persists_only_place_ids_in_account_state(monkeypatch):
    states = {
        "first-user": {"savedGooglePlaces": [], "dataSourceReviews": {}},
        "second-user": {"savedGooglePlaces": [], "dataSourceReviews": {}},
    }
    owner = _set_owner("first-user")
    try:
        monkeypatch.setattr(main.S, "load_state", lambda: states[C.current_user_id()])
        monkeypatch.setattr(main.S, "save_state", lambda value: None)
        result = main.import_data_source_results(main.SourceImportIn(
            provider="google_places", item_ids=["ChIJ-place-id"],
        ))
        assert result["saved_place_ids"] == ["ChIJ-place-id"]
        assert "Entreprise" not in repr(states["first-user"])
    finally:
        C.reset_current_user(owner)
    assert states["second-user"]["savedGooglePlaces"] == []
