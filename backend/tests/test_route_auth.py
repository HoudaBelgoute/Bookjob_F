from fastapi.testclient import TestClient

from app.main import app


def test_tracking_export_requires_a_bookjob_session():
    response = TestClient(app).get("/api/export/suivi.csv")

    assert response.status_code == 401
    assert response.json() == {"detail": "Connexion requise"}
    assert response.headers["cache-control"] == "no-store"
