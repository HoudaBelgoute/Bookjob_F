import json
from pathlib import Path

import pandas as pd
import pytest

from app.pipeline import cleaning as K
from app.pipeline.run import run_pipeline
from app.pipeline.sources import RAW_COLS, ExcelSource, GooglePlacesSource, SourceResult, collect_all

DATA = Path(__file__).resolve().parent.parent / "data"
MAPS = "https://maps.google.com/?cid={}&g_mp=x"


def _raw():
    rows = [
        ["Alpha Web", "Services", "Rue X, Gueliz, Marrakech 40000, Morocco", 4.5, 100, "https://www.alpha.ma/",
         "06 61 34 71 60", MAPS.format(1), "entreprise informatique Marrakech"],
        ["Alpha Web", "Services", "Rue X, Gueliz, Marrakech 40000, Morocco", 4.5, 100, "https://www.alpha.ma/",
         "06 61 34 71 60", MAPS.format(1), "agence digitale Marrakech"],
        ["Beta Agadir", "Services", "Av. Hassan II, Agadir 80000, Morocco", 4.0, 12, None, None, MAPS.format(2),
         "entreprise informatique Marrakech"],
        ["Gamma PC", "Electronics Store", "Massira, Marrakech 40140, Morocco", 4.8, 300, None, None,
         MAPS.format(3), "entreprise informatique Marrakech"],
        ["Delta Banque", None, "شارع محمد الخامس، مراكش 40000", None, None, "https://facebook.com/delta",
         "+212 5 24", MAPS.format(4), "banque Marrakech"],
        [None, "Services", "Marrakech", 3.0, 2, None, None, MAPS.format(5), "startup Marrakech"],
    ]
    return pd.DataFrame(rows, columns=RAW_COLS)


@pytest.mark.parametrize("address, city", [
    ("Rue X, Marrakech 40000, Morocco", "Marrakech"),
    ("Marrakesh 40160, Morocco", "Marrakech"),
    ("شارع محمد الخامس، مراكش", "Marrakech"),
    ("Bd Moulay Ismail, Casablanca 20290, Morocco", "Casablanca"),
    ("Rue de la Liberté, Guéliz 40000", "Marrakech"),
    ("", "Non précisé"),
])
def test_detect_city(address, city):
    assert K.detect_city(address) == city


def test_unit_rules():
    assert K.extract_cid(MAPS.format(123)) == "123" and K.extract_cid("https://x.com") is None
    assert K.normalize_phone("06 61 34 71 60") == ("+212661347160", True)
    assert K.normalize_phone("+212 5 24") == ("+212 5 24", False)
    assert K.normalize_phone(None) == (None, True)
    assert K.site_type("https://www.facebook.com/page") == "Réseau social/OTA"
    assert K.site_type("http://www.alpha.ma/") == "Site propre" and K.site_domain("http://www.alpha.ma/") == "alpha.ma"
    assert K.site_type(None) == "Aucun"
    assert K.detect_quartier("Rue X, Guéliz, Marrakech") == "Guéliz"
    assert K.postal_code("Marrakech 40100, Morocco") == "40100"
    assert K.sector_from_queries("agence digitale Marrakech | startup Marrakech | agence marketing digital Marrakech") \
        == "IT / Dev / Data"
    assert K.sector_from_queries("") == K.OTHER_SECTOR
    assert [K.priority(s) for s in (85, 70, 40)] == ["A", "B", "C"]


def test_clean_merges_duplicates_excludes_and_keeps_ids_stable():
    result = K.clean(_raw(), previous_ids={"1": "MRK-007"})
    clean = result.clean.set_index("Entreprise")

    assert list(result.clean.columns) == K.OUTPUT_COLS
    assert sorted(clean.index) == ["Alpha Web", "Delta Banque"]
    assert result.clean["cid"].is_unique and result.clean["ID"].is_unique

    alpha = clean.loc["Alpha Web"]
    assert alpha["ID"] == "MRK-007"
    assert alpha["Nb_requetes"] == 2
    assert alpha["Requetes_sources"] == "entreprise informatique Marrakech | agence digitale Marrakech"
    assert alpha["Telephone"] == "+212661347160" and alpha["Quartier"] == "Guéliz"
    assert alpha["Secteur"] == "IT / Dev / Data" and alpha["Domaine"] == "alpha.ma"
    assert 0 <= alpha["Score"] <= 100 and alpha["Priorite"] in {"A", "B", "C"}

    delta = clean.loc["Delta Banque"]
    assert delta["ID"] == "MRK-008"
    assert delta["Ville"] == "Marrakech" and delta["Site_type"] == "Réseau social/OTA"
    assert delta["Note_manquante"] == 1 and delta["Secteur"] == "Banque / Finance"
    assert delta["Note_lissee"] > 0  # note absente → moyenne globale, pas 0

    named = result.excluded.dropna(subset=["Entreprise"])
    motifs = dict(zip(named["Entreprise"], named["Motif_exclusion"]))
    assert motifs == {"Beta Agadir": "Hors Marrakech", "Gamma PC": "Commerce/DAB hors cible"}
    assert result.excluded["Motif_exclusion"].tolist().count("Nom manquant") == 1

    report = result.report.set_index("Problème détecté")["Nb lignes"]
    assert report[[p for p in report.index if p.startswith("Doublons cachés")][0]] == 1
    assert report["Téléphones non standard (format différent de 0X XX XX XX XX)"] == 1


def test_failing_source_does_not_stop_the_others():
    class Broken:
        name = "broken"

        def collect(self):
            raise RuntimeError("API indisponible")

    class Ok:
        name = "ok"

        def collect(self):
            return SourceResult("ok", _raw().head(2))

    raw, log = collect_all([Broken(), Ok()])
    assert len(raw) == 2 and set(raw["Source"]) == {"ok"}
    assert {s["source"]: s["statut"] for s in log} == {"broken": "échec", "ok": "succès"}
    assert "API indisponible" in log[0]["erreurs"]


def test_google_places_connector_maps_fields_and_handles_missing_key():
    assert GooglePlacesSource("").collect().errors == ["GOOGLE_API_KEY non configurée"]

    class Response:
        status_code = 200

        def json(self):
            return {"places": [{
                "displayName": {"text": "Alpha Web"}, "primaryTypeDisplayName": {"text": "Services"},
                "formattedAddress": "Marrakech 40000, Morocco", "rating": 4.6, "userRatingCount": 20,
                "websiteUri": "https://alpha.ma", "nationalPhoneNumber": "06 61 34 71 60",
                "googleMapsUri": MAPS.format(9),
            }]}

    class Session:
        calls = []

        def post(self, url, json, timeout, headers):
            self.calls.append((json, headers))
            return Response()

    session = Session()
    result = GooglePlacesSource("test-key", ["startup Marrakech"], session=session).collect()
    assert result.errors == [] and result.rows.iloc[0]["Entreprise"] == "Alpha Web"
    assert result.rows.iloc[0]["Requete"] == "startup Marrakech"
    assert session.calls[0][1]["X-Goog-Api-Key"] == "test-key"


def test_run_pipeline_writes_before_after_excel_and_history(tmp_path):
    raw_path = tmp_path / "brut.xlsx"
    _raw().to_excel(raw_path, index=False)
    out = tmp_path / "nettoye.xlsx"
    runs = tmp_path / "runs.json"

    run = run_pipeline([ExcelSource(raw_path), ExcelSource(tmp_path / "absent.xlsx")], out, runs_file=runs)

    assert run["statut"] == "partiel" and run["lignes_brutes"] == 6 and run["lignes_nettoyees"] == 2
    sheets = pd.read_excel(out, sheet_name=None)
    assert {"Données nettoyées", "Lignes exclues", "Rapport nettoyage", "Dictionnaire", "Journal collecte"} <= set(sheets)
    assert len(json.loads(runs.read_text(encoding="utf-8"))) == 1


@pytest.mark.skipif(not (DATA / "donnees_brutes_places.xlsx").exists(), reason="export brut absent")
def test_real_raw_export_is_cleaned_consistently():
    raw = ExcelSource(DATA / "donnees_brutes_places.xlsx").collect()
    assert raw.errors == []
    result = K.clean(raw.rows)
    assert len(result.clean) < len(raw.rows)
    assert result.clean["cid"].dropna().is_unique
    assert set(result.clean["Ville"]) <= {"Marrakech", "Non précisé"}
    assert result.clean["Score"].between(0, 100).all()
    assert not result.report.empty
