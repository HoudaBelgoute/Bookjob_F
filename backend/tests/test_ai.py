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
