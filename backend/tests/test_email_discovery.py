from app import email_discovery


def test_finds_public_email_with_the_official_page_as_source(monkeypatch):
    pages = {
        "https://company.example/": (
            "https://company.example/",
            '<html><a href="/contactez-nous">Contact</a></html>',
        ),
        "https://company.example/contact": None,
        "https://company.example/contact-us": None,
        "https://company.example/contactez-nous": (
            "https://company.example/contactez-nous",
            '<html><a href="mailto:recrutement@company.example">Écrivez-nous</a></html>',
        ),
    }
    monkeypatch.setattr(email_discovery, "_is_public_host", lambda _host: True)
    monkeypatch.setattr(email_discovery, "_fetch_page", lambda url, _host: pages.get(url))

    results = email_discovery.find_public_emails("https://company.example")

    assert results == [{
        "email": "recrutement@company.example",
        "source": "https://company.example/contactez-nous",
    }]
