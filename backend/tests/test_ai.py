from cryptography.fernet import Fernet

from app import ai


def test_personal_groq_key_is_tested_encrypted_and_never_returned(monkeypatch, tmp_path):
    encrypted_path = tmp_path / "groq-api-key.enc"
    monkeypatch.setattr(ai.C, "AI_KEY_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.setattr(ai.C, "GROQ_API_KEY", "server-key")
    monkeypatch.setattr(ai.C, "user_path", lambda _path: encrypted_path)
    owner_token = ai.C.set_current_user("test-user")
    calls = []

    class Response:
        status_code = 200
        ok = True

    def get(url, *, timeout, headers):
        calls.append((url, timeout, headers))
        return Response()

    monkeypatch.setattr(ai.requests, "get", get)
    try:
        ai.save_personal_api_key("personal-key")
        status = ai.key_status()
        assert encrypted_path.read_bytes() != b"personal-key"
        assert ai.personal_api_key() == "personal-key"
        assert ai.api_key() == "personal-key"
        assert status == {
            "provider": "groq",
            "mode": "personal",
            "personal_key_configured": True,
            "encryption_available": True,
            "masked_key": "••••••••",
        }
        assert "personal-key" not in repr(status)
        assert calls == [(
            "https://api.groq.com/openai/v1/models",
            15,
            {"Authorization": "Bearer personal-key"},
        )]
        ai.remove_personal_api_key()
        assert ai.api_key() == "server-key"
        assert ai.key_status()["mode"] == "server"
    finally:
        ai.C.reset_current_user(owner_token)


def test_personal_key_is_not_saved_without_encryption_or_provider_acceptance(monkeypatch, tmp_path):
    encrypted_path = tmp_path / "groq-api-key.enc"
    monkeypatch.setattr(ai.C, "AI_KEY_ENCRYPTION_KEY", "")
    monkeypatch.setattr(ai.C, "user_path", lambda _path: encrypted_path)
    owner_token = ai.C.set_current_user("test-user")
    try:
        try:
            ai.save_personal_api_key("personal-key")
        except ai.AIError as error:
            assert "stockage" in str(error)
        else:
            raise AssertionError("Expected encryption configuration to be required")
        assert not encrypted_path.exists()

        monkeypatch.setattr(ai.C, "AI_KEY_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))

        class RejectedResponse:
            status_code = 401
            ok = False

        monkeypatch.setattr(ai.requests, "get", lambda *args, **kwargs: RejectedResponse())
        try:
            ai.save_personal_api_key("invalid-key")
        except ai.AIError as error:
            assert "refusé" in str(error)
        else:
            raise AssertionError("Expected invalid provider key to be rejected")
        assert not encrypted_path.exists()
    finally:
        ai.C.reset_current_user(owner_token)


def test_unreadable_personal_key_does_not_silently_fall_back_to_server_key(monkeypatch, tmp_path):
    encrypted_path = tmp_path / "groq-api-key.enc"
    encrypted_path.write_bytes(b"not-a-fernet-token")
    monkeypatch.setattr(ai.C, "AI_KEY_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.setattr(ai.C, "GROQ_API_KEY", "server-key")
    monkeypatch.setattr(ai.C, "user_path", lambda _path: encrypted_path)
    owner_token = ai.C.set_current_user("test-user")
    try:
        assert ai.provider() == "unavailable"
        assert ai.key_status()["mode"] == "unavailable"
        try:
            ai.api_key()
        except ai.AIError:
            pass
        else:
            raise AssertionError("Unreadable personal keys must not silently use the server key")
    finally:
        ai.C.reset_current_user(owner_token)


def test_groq_completion_uses_groq_api_and_takes_precedence(monkeypatch):
    monkeypatch.setattr(ai.C, "GROQ_API_KEY", "test-groq-key")
    monkeypatch.setattr(ai.C, "GROQ_MODEL", "openai/gpt-oss-120b")
    calls = {}

    class Response:
        def raise_for_status(self):
            pass

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": "CV rédigé par Groq"}}]}

    def post(url, *, timeout, headers, json):
        calls.update(url=url, timeout=timeout, headers=headers, payload=json)
        return Response()

    monkeypatch.setattr(ai.requests, "post", post)

    assert ai.provider() == "groq"
    assert ai.complete("Consigne", [{"role": "user", "content": "Profil"}], 321) == "CV rédigé par Groq"
    assert calls["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert calls["timeout"] == 120
    assert calls["headers"] == {"Authorization": "Bearer test-groq-key"}
    assert calls["payload"]["model"] == "openai/gpt-oss-120b"
    assert calls["payload"]["max_tokens"] == 321
    assert calls["payload"]["messages"] == [
        {"role": "system", "content": "Consigne"},
        {"role": "user", "content": "Profil"},
    ]


def test_ai_chat_requests_clear_french_structure(monkeypatch):
    monkeypatch.setattr(ai, "provider", lambda: "grok")
    captured = {}

    def complete(system, messages, max_tokens):
        captured.update(system=system, messages=messages, max_tokens=max_tokens)
        return "Préparer l'entretien\n\n• Premier conseil.\n• Deuxième conseil."

    monkeypatch.setattr(ai, "complete", complete)
    result = ai.chat(
        [{"role": "user", "content": "Comment préparer l'entretien ?"}],
        None,
        {},
        False,
    )

    assert result["reply"].startswith("Préparer l'entretien")
    assert "français correct" in captured["system"]
    assert "paragraphes brefs" in captured["system"]
    assert "N'invente aucun fait" in captured["system"]
    assert captured["max_tokens"] == 900


def test_chat_fallback_describes_sector_keyword_overlap_without_claiming_skill_gaps():
    reply = ai.chat_fallback(
        "Comment mon profil correspond à cette entreprise ?",
        {
            "match": 50,
            "match_skills": ["Python"],
            "missing_skills": ["UX design"],
            "match_explanation": "1 compétence(s) sur 2 déclarées contiennent un mot-clé du secteur.",
            "short": "Acme",
            "secteur": "IT",
        },
        {},
        True,
    )

    assert "50/100" in reply
    assert "Compétences rapprochées : Python" in reply
    assert "Compétences sans mot-clé correspondant : UX design" in reply
    assert "ni une analyse d'offre ni une probabilité d'embauche" in reply
    assert "À développer" not in reply
