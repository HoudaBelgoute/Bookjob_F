from fastapi.testclient import TestClient

from app import config as C
from app import accounts
from app.main import app


def _component_ids(component):
    if isinstance(component, dict):
        if "id" in component:
            yield component["id"]
        for value in component.values():
            yield from _component_ids(value)
    elif isinstance(component, list):
        for value in component:
            yield from _component_ids(value)


def _component_content(component, component_id):
    if isinstance(component, dict):
        props = component.get("props", {})
        if props.get("id") == component_id:
            return props.get("children")
        for value in component.values():
            content = _component_content(value, component_id)
            if content is not None:
                return content
    elif isinstance(component, list):
        for value in component:
            content = _component_content(value, component_id)
            if content is not None:
                return content
    return None


def _authenticated_client(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(C, "REGISTRATION_KEY", "")
    accounts.initialize()
    client = TestClient(app)
    response = client.post("/api/auth/register", json={
        "full_name": "Dash Candidate",
        "email": "dash-test@example.com", "password": "a-long-test-password",
    })
    assert response.status_code == 201
    return client


def test_dash_dashboard_is_mounted_and_serves_interactive_layout(monkeypatch, tmp_path):
    client = _authenticated_client(monkeypatch, tmp_path)
    page = client.get("/dash/")
    layout = client.get("/dash/_dash-layout")

    assert page.status_code == 200
    assert "/dash/_favicon.ico" in page.text
    assert layout.status_code == 200
    assert {
        "status-filter",
        "status-chart",
        "timeline-chart",
        "sector-chart",
    }.issubset(set(_component_ids(layout.json())))

    update = client.post(
        "/dash/_dash-update-component",
        json={
            "output": "..status-chart.figure...timeline-chart.figure..",
            "outputs": [
                {"id": "status-chart", "property": "figure"},
                {"id": "timeline-chart", "property": "figure"},
            ],
            "inputs": [{"id": "status-filter", "property": "value", "value": "Brouillon"}],
            "state": [],
            "changedPropIds": ["status-filter.value"],
        },
    )

    assert update.status_code == 200
    chart_labels = update.json()["response"]["status-chart"]["figure"]["data"][0]["labels"]
    assert set(chart_labels).issubset({"Brouillon", "Aucune donnée"})


def test_dash_dashboard_requires_bookjob_login(monkeypatch, tmp_path):
    accounts.initialize()
    client = TestClient(app, follow_redirects=False)

    response = client.get("/dash/")

    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_dash_dashboard_uses_the_authenticated_accounts_tracking(monkeypatch, tmp_path):
    first = _authenticated_client(monkeypatch, tmp_path)
    created = first.post("/api/tracking", json={
        "entreprise": "First account private application",
        "poste": "Stage Data",
    })
    assert created.status_code == 200

    second = TestClient(app)
    registered = second.post("/api/auth/register", json={
        "full_name": "Second Candidate",
        "email": "second-dash@example.com",
        "password": "a-long-test-password",
    })
    assert registered.status_code == 201

    first_layout = first.get("/dash/_dash-layout")
    second_layout = second.get("/dash/_dash-layout")

    assert first_layout.status_code == 200
    assert second_layout.status_code == 200
    assert _component_content(first_layout.json(), "kpi-tracked") == "1"
    assert _component_content(second_layout.json(), "kpi-tracked") == "0"
