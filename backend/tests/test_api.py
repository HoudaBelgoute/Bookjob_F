import os
import shutil
import sys
import tempfile
import uuid
from datetime import date, timedelta
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent
tmp = Path(tempfile.mkdtemp())
shutil.copytree(SRC / "data", tmp / "data", ignore=shutil.ignore_patterns("auth.sqlite3*", "users"))
os.environ["BOOKJOB_DATA"] = str(tmp / "data")
os.environ["BOOKJOB_FRONT_DIST"] = str(tmp / "nodist")
os.environ["BOOKJOB_REGISTRATION_KEY"] = ""
sys.path.insert(0, str(SRC))

from fastapi.testclient import TestClient  # noqa: E402
from app import accounts, config as C  # noqa: E402
from app.main import app  # noqa: E402

C.DATA_DIR = tmp / "data"
C.UPLOAD_DIR = C.DATA_DIR / "uploads"
C.CV_SENT_DIR = C.UPLOAD_DIR / "cv_envoyes"
C.CV_LIB_DIR = C.UPLOAD_DIR / "cv_bibliotheque"
C.XLSX = C.DATA_DIR / "donnees_nettoyees.xlsx"
C.SUIVI = C.DATA_DIR / "suivi.csv"
C.PROFIL = C.DATA_DIR / "profil.json"
C.STATE = C.DATA_DIR / "state.json"
C.GEOCACHE = C.DATA_DIR / "geocode_cache.json"
C.AUTH_DB = C.DATA_DIR / "auth.sqlite3"
C.EMAIL_CONFIRMATIONS_FILE = C.DATA_DIR / "email_confirmations.json"
C.GOOGLE_TOKEN_FILE = tmp / "google_oauth_token.json"
C.FRONT_DIST = tmp / "nodist"
C.REGISTRATION_KEY = ""
accounts.initialize()

c = TestClient(app)
registration = c.post("/api/auth/register", json={
    "full_name": "API Candidate", "email": "api-test@example.com", "password": "a-long-test-password",
})
assert registration.status_code == 201


def test_meta_and_companies():
    m = c.get("/api/meta").json()
    assert m["total_entreprises"] == 374 and "IT / Dev / Data" in m["secteurs"]
    r = c.get("/api/companies", params={"secteur": "IT / Dev / Data", "priorite": ["A"], "sort": "score"}).json()
    assert r["total"] > 0 and r["items"][0]["score"] >= r["items"][-1]["score"]
    r = c.get("/api/companies", params={"q": "gitex"}).json()
    assert any("Gitex" in i["name"] for i in r["items"])
    assert r["items"][0]["match"] is not None  # profil avec compétences


def test_distance_filter():
    r = c.get("/api/companies", params={"lat": 31.6346, "lon": -8.0089, "dmax": 2, "sort": "distance"}).json()
    ds = [i["distance_km"] for i in r["items"]]
    assert ds and ds == sorted(ds) and max(ds) <= 2


def test_favorites_and_tracking_flow():
    assert c.post("/api/favorites/MRK-003").json()["favorite"] is True
    assert c.post("/api/favorites/MRK-003").json()["favorite"] is False
    t = c.get("/api/tracking").json()
    assert t["items"]
    # ajout d'une entreprise du fichier (pas encore suivie)
    free = next(i for i in c.get("/api/companies", params={"suivi": "non"}).json()["items"])
    r = c.post("/api/tracking", json={"company_id": free["id"]})
    assert r.status_code == 200 and r.json()["statut"] == "Brouillon"
    assert c.post("/api/tracking", json={"company_id": free["id"]}).status_code == 409
    # offre externe
    e = c.post("/api/tracking", json={"entreprise": "Acme", "source": "LinkedIn", "poste": "Stage Data"}).json()
    assert e["id"].startswith("EXT-")
    # changement de statut -> date + relance auto
    p = c.patch(f"/api/tracking/{e['id']}", json={"statut": "CV envoyé"}).json()
    assert p["date_candidature"] and p["date_relance"]
    assert c.get(f"/api/tracking/{e['id']}/events").json()["items"][0]["new_status"] == "Candidature envoyée"
    assert c.get(f"/api/tracking/{e['id']}/emails").json()["items"] == []
    assert c.patch(f"/api/tracking/{e['id']}", json={"statut": "nimporte"}).status_code == 400
    assert c.delete(f"/api/tracking/{e['id']}").json()["ok"]


def test_apply_with_cv_and_download():
    bad = c.post("/api/tracking/apply", data={"entreprise": "X"}, files={"file": ("a.exe", b"zz")})
    assert bad.status_code == 400
    sent_on = (date.today() - timedelta(days=8)).isoformat()
    follow_up = (date.today() - timedelta(days=1)).isoformat()
    entreprise = f"Entreprise test {uuid.uuid4().hex}"
    ok = c.post("/api/tracking/apply", data={"entreprise": entreprise, "poste": "Stage",
                "date_candidature": sent_on, "statut": "CV envoyé"}, files={"file": ("cv.pdf", b"%PDF-1.4 test")})
    assert ok.status_code == 200, ok.text
    j = ok.json()
    assert j["fichier_cv"].endswith(".pdf") and j["date_relance"] == follow_up
    d = c.get(f"/api/tracking/{j['id']}/cv")
    assert d.status_code == 200 and d.content.startswith(b"%PDF")
    assert c.get("/api/tracking").json()["relances_dues"]
    assert c.get("/api/notifications").json()["items"]
    assert c.get("/api/export/suivi.csv").status_code == 200


def test_prepared_application_is_not_counted_as_sent():
    before = c.get("/api/dashboard").json()["kpis"]["envoyees"]
    entreprise = f"Candidature préparée {uuid.uuid4().hex}"
    prepared = c.post("/api/tracking/apply", data={
        "entreprise": entreprise, "poste": "Stage Data", "statut": "À postuler",
        "lien_offre": "https://example.com/careers",
    }, files={"file": ("cv.pdf", b"%PDF-1.4 test")})
    assert prepared.status_code == 200, prepared.text
    item = prepared.json()
    assert item["statut"] == "À envoyer"
    assert item["date_candidature"] == "" and item["date_relance"] == ""
    assert item["lien_offre"] == "https://example.com/careers"
    assert c.get("/api/dashboard").json()["kpis"]["envoyees"] == before
    assert any("reste" in n["text"] for n in c.get("/api/notifications").json()["items"])

    sent = c.patch(f"/api/tracking/{item['id']}", json={"statut": "CV envoyé"})
    assert sent.status_code == 200
    assert sent.json()["date_candidature"] and sent.json()["date_relance"]
    assert c.get("/api/dashboard").json()["kpis"]["envoyees"] == before + 1


def test_interview_date_is_saved_and_shown_on_dashboard():
    item = c.post("/api/tracking", json={"entreprise": "Entretien test", "poste": "Stage Data"}).json()
    interview_date = (date.today() + timedelta(days=2)).isoformat()
    updated = c.patch(f"/api/tracking/{item['id']}", json={"statut": "Entretien", "date_entretien": interview_date})
    assert updated.status_code == 200
    assert updated.json()["date_entretien"] == interview_date
    upcoming = c.get("/api/dashboard").json()["entretiens_a_venir"]
    assert any(i["id"] == item["id"] and i["date_entretien"] == interview_date for i in upcoming)


def test_statistics_use_real_application_dates_and_calculate_rates():
    dates_and_statuses = [
        ("2099-01-05", "Candidature envoyée"),
        ("2099-01-06", "Refusée"),
        ("2099-01-07", "Acceptée"),
    ]
    for date_sent, status in dates_and_statuses:
        item = c.post("/api/tracking", json={
            "entreprise": f"Stats {uuid.uuid4().hex}",
            "poste": "Stage Data",
        }).json()
        updated = c.patch(f"/api/tracking/{item['id']}", json={
            "statut": status, "date_candidature": date_sent,
        })
        assert updated.status_code == 200

    result = c.get("/api/stats", params={"start": "2099-01-01", "end": "2099-01-31"})
    assert result.status_code == 200
    stats = result.json()
    assert stats["kpis"]["total"] == 3
    assert stats["kpis"]["responses"] == 2
    assert stats["kpis"]["refusals"] == 1
    assert stats["kpis"]["acceptances"] == 1
    assert stats["kpis"]["response_rate"] == 66.7
    assert stats["kpis"]["acceptance_rate"] == 33.3
    assert sum(week["count"] for week in stats["weekly"]) == 3


def test_profile_and_generation():
    pr = c.put("/api/profile", json={"resume": "Étudiante motivée"}).json()
    assert pr["profile"]["nom"] == "API Candidate" and pr["completion"]["percent"] > 40
    assert "SQL" in pr["skills"]  # compétences séparées par espaces
    g = c.post("/api/generate/cv", json={"company_id": "MRK-001", "poste": "Stage Data", "use_ai": True}).json()
    assert g["mode"] == "modele" and "API Candidate" in g["cv"] and "Objet" in g["mail"]
    L = c.post("/api/generate/letter", json={"company_id": "MRK-001", "use_ai": False}).json()
    assert "Cordialement" in L["lettre"]


def test_cv_library():
    before = c.get("/api/cvs").json()["items"]
    r = c.post("/api/cvs", files={"file": ("mon cv.docx", b"PK123")}).json()
    cv = r["items"][-1]
    assert cv["main"] is (len(before) == 0)
    assert sum(item["main"] for item in r["items"]) == 1
    assert c.get(f"/api/cvs/{cv['id']}/file").content == b"PK123"
    ok = c.post("/api/tracking/apply", data={"entreprise": "Acme2", "cv_id": cv["id"]})
    assert ok.status_code == 200
    remaining = c.delete(f"/api/cvs/{cv['id']}").json()["items"]
    assert len(remaining) == len(before) and all(item["id"] != cv["id"] for item in remaining)


def test_home_chat_dashboard():
    assert c.put("/api/home", json={"lat": 31.63, "lon": -8.0, "label": "x"}).status_code == 200
    assert c.get("/api/companies", params={"limit": 1}).json()["items"][0]["distance_km"] is not None
    r = c.post("/api/chat", json={"message": "Est-ce que mon profil correspond ?", "company_id": "MRK-001"}).json()
    assert "%" in r["chat"]["messages"][-1]["content"]
    dsh = c.get("/api/dashboard").json()
    assert dsh["kpis"]["suivies"] >= 40 and len(dsh["recommandees"]) == 3
    assert c.post("/api/alerts", json={"query": "data"}).json()["items"]
    assert c.put("/api/settings", json={"emailAlerts": False}).json()["emailAlerts"] is False
    assert c.post("/api/geocode/companies").status_code == 400  # pas de clé Google


def test_quartier_geocode_offline():
    r = c.post("/api/geocode", json={"adresse": "Gueliz, Marrakech"}).json()
    assert abs(r["lat"] - 31.6346) < 1e-3


def test_health_is_public_but_data_requires_login():
    anonymous = TestClient(app)
    assert anonymous.get("/api/health").json() == {"ok": True}
    assert anonymous.get("/api/data-quality").status_code == 401


def test_data_quality_exposes_cleaning_report_and_completeness():
    q = c.get("/api/data-quality")
    assert q.status_code == 200, q.text
    q = q.json()
    assert q["rows_clean"] == 374 and q["duplicate_ids"] == 0
    assert q["report"] and {"probleme", "lignes", "traitement"} <= set(q["report"][0])
    assert all(0 <= f["percent"] <= 100 for f in q["completeness"])
    assert set(q["priorities"]) <= {"A", "B", "C"}


def test_profile_rejects_invalid_values():
    assert c.put("/api/profile", json={"resume": {"nested": True}}).status_code == 422
    assert c.put("/api/profile", json={"resume": "x" * 5001}).status_code == 422
    assert c.put("/api/profile", json={"inconnu": "ignoré"}).status_code == 200


# ---------- CV importé / candidature / photo de profil ----------
def _second_user_client():
    client = TestClient(app)
    created = client.post("/api/auth/register", json={
        "full_name": "Second Candidate", "email": f"second-{uuid.uuid4().hex[:6]}@example.com",
        "password": "a-long-test-password",
    })
    assert created.status_code == 201
    return client


def test_apply_with_library_cv_works_for_a_new_account():
    """Régression « CV introuvable » : le dossier des CV envoyés n'existait pas pour les nouveaux comptes."""
    client = _second_user_client()
    pdf = b"%PDF-1.4 mon cv"
    uploaded = client.post("/api/cvs", files={"file": ("monCV.pdf", pdf, "application/pdf")})
    assert uploaded.status_code == 200
    cv_id = uploaded.json()["items"][0]["id"]
    applied = client.post("/api/tracking/apply", data={"entreprise": "ACME", "poste": "Stage", "cv_id": cv_id})
    assert applied.status_code == 200, applied.text
    row = applied.json()
    assert client.get(f"/api/tracking/{row['id']}/cv").content == pdf


def test_apply_with_new_file_also_saves_it_in_the_library():
    client = _second_user_client()
    pdf = b"%PDF-1.4 cv importe dans postuler"
    assert client.get("/api/cvs").json()["items"] == []
    for company in ("Alpha", "Beta"):
        r = client.post("/api/tracking/apply", data={"entreprise": company, "poste": "Stage"},
                        files={"file": ("cv.pdf", pdf, "application/pdf")})
        assert r.status_code == 200, r.text
    items = client.get("/api/cvs").json()["items"]
    assert len(items) == 1 and items[0]["main"] is True and items[0]["name"] == "cv"  # pas de doublon
    assert client.get(f"/api/cvs/{items[0]['id']}/file").content == pdf
    files = {t["fichier_cv"] for t in client.get("/api/tracking").json()["items"] if t["entreprise"] in ("Alpha", "Beta")}
    assert len(files) == 2  # chaque candidature a son propre fichier


def test_apply_reports_a_missing_library_file_clearly():
    client = _second_user_client()
    cv = client.post("/api/cvs", files={"file": ("a.pdf", b"%PDF-1.4 a", "application/pdf")}).json()["items"][0]
    unknown = client.post("/api/tracking/apply", data={"entreprise": "X", "cv_id": "cv-inexistant"})
    assert unknown.status_code == 404 and "CV introuvable" in unknown.json()["detail"]
    for stored in C.DATA_DIR.glob(f"users/*/uploads/cv_bibliotheque/{cv['file']}"):
        stored.unlink()  # fichier perdu sur le disque alors que l'entrée existe encore
    lost = client.post("/api/tracking/apply", data={"entreprise": "X", "cv_id": cv["id"]})
    assert lost.status_code == 404 and "n'existe plus" in lost.json()["detail"]


PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360f8cfc0f01f00050001ff895e4ffb0000000049454e44ae426082"
)


def test_profile_avatar_upload_replace_and_delete():
    client = _second_user_client()
    assert client.get("/api/profile").json()["avatar_url"] is None
    assert client.get("/api/profile/avatar").status_code == 404
    up = client.post("/api/profile/avatar", files={"file": ("me.png", PNG_1PX, "image/png")})
    assert up.status_code == 200 and up.json()["avatar_url"].startswith("/api/profile/avatar?v=")
    assert client.get("/api/profile").json()["avatar_url"]
    got = client.get("/api/profile/avatar")
    assert got.status_code == 200 and got.content == PNG_1PX and got.headers["content-type"] == "image/png"
    # un autre compte ne voit pas cette photo
    other = _second_user_client()
    assert other.get("/api/profile").json()["avatar_url"] is None
    # remplacement par un JPEG : l'ancien fichier disparaît
    jpeg = b"\xff\xd8\xff\xe0" + b"0" * 20
    assert client.post("/api/profile/avatar", files={"file": ("me.jpg", jpeg, "image/jpeg")}).status_code == 200
    assert client.get("/api/profile/avatar").headers["content-type"] == "image/jpeg"
    assert client.delete("/api/profile/avatar").json() == {"avatar_url": None}
    assert client.get("/api/profile/avatar").status_code == 404


def test_profile_avatar_rejects_non_images_and_big_files():
    client = _second_user_client()
    bad = client.post("/api/profile/avatar", files={"file": ("x.png", b"<svg onload=alert(1)>", "image/png")})
    assert bad.status_code == 400
    svg = client.post("/api/profile/avatar", files={"file": ("x.svg", b"<svg xmlns='http://www.w3.org/2000/svg'/>", "image/svg+xml")})
    assert svg.status_code == 400
    big = client.post("/api/profile/avatar", files={"file": ("big.png", PNG_1PX + b"0" * (2 * 1024 * 1024), "image/png")})
    assert big.status_code == 400
    assert client.get("/api/profile/avatar").status_code == 404
