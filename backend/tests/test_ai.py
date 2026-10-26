from app import ai


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
