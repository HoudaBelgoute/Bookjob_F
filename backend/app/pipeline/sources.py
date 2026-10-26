"""Connecteurs de collecte. Chaque source renvoie un DataFrame au format brut commun ``RAW_COLS``.

Une source qui échoue n'interrompt pas les autres : l'erreur est consignée dans le journal d'exécution.
LinkedIn n'est pas collecté automatiquement (conditions d'utilisation restrictives, pas d'API publique
d'offres) : les offres LinkedIn sont ajoutées manuellement dans le suivi (champ « Source »).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import requests

RAW_COLS = ["Entreprise", "Categorie", "Adresse", "Note", "Nb_avis", "Site_web", "Telephone", "Lien_Maps", "Requete"]

# Requêtes utilisées pour la collecte Google Maps (Marrakech). Modifiables via --queries.
DEFAULT_QUERIES = [
    "entreprise informatique Marrakech",
    "société de développement web Marrakech",
    "agence digitale Marrakech",
    "agence marketing digital Marrakech",
    "startup Marrakech",
    "bureau d'études Marrakech",
    "cabinet de conseil Marrakech",
    "cabinet comptable Marrakech",
    "banque Marrakech",
    "assurance Marrakech",
    "centre d'appel Marrakech",
    "hôtel Marrakech",
]

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
PLACES_FIELDS = ",".join([
    "places.displayName", "places.primaryTypeDisplayName", "places.formattedAddress", "places.rating",
    "places.userRatingCount", "places.websiteUri", "places.nationalPhoneNumber", "places.googleMapsUri",
    "nextPageToken",
])


@dataclass
class SourceResult:
    name: str
    rows: pd.DataFrame
    errors: list[str] = field(default_factory=list)


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=RAW_COLS)


class ExcelSource:
    """Import d'un export brut existant (ex. ``donnees_brutes_places.xlsx``)."""

    name = "excel"

    def __init__(self, path: Path):
        self.path = Path(path)

    def collect(self) -> SourceResult:
        try:
            data = pd.read_excel(self.path)
        except Exception as ex:  # fichier absent / illisible : la source échoue seule
            return SourceResult(self.name, _empty(), [f"Lecture impossible de {self.path.name} : {ex}"])
        missing = [c for c in RAW_COLS if c not in data.columns]
        if missing:
            return SourceResult(self.name, _empty(), [f"Colonnes manquantes dans {self.path.name} : {missing}"])
        return SourceResult(self.name, data[RAW_COLS].copy())


class GooglePlacesSource:
    """Google Places API (New) — Text Search. Nécessite GOOGLE_API_KEY (jamais exposée au navigateur)."""

    name = "google_places"

    def __init__(self, api_key: str, queries: list[str] | None = None, max_pages: int = 3,
                 session: requests.Session | None = None, pause: float = 2.0):
        self.api_key = api_key
        self.queries = queries or DEFAULT_QUERIES
        self.max_pages = max_pages
        self.http = session or requests.Session()
        self.pause = pause

    def _search(self, query: str) -> list[dict]:
        places, token = [], None
        for _ in range(self.max_pages):
            body = {"textQuery": query, "languageCode": "fr", "regionCode": "MA", "pageSize": 20}
            if token:
                body["pageToken"] = token
            r = self.http.post(PLACES_URL, json=body, timeout=15, headers={
                "X-Goog-Api-Key": self.api_key, "X-Goog-FieldMask": PLACES_FIELDS,
            })
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code} : {r.text[:200]}")
            payload = r.json()
            places.extend(payload.get("places", []))
            token = payload.get("nextPageToken")
            if not token:
                break
            time.sleep(self.pause)  # le jeton de page suivante n'est pas valide immédiatement
        return places

    @staticmethod
    def to_row(place: dict, query: str) -> dict:
        return {
            "Entreprise": (place.get("displayName") or {}).get("text"),
            "Categorie": (place.get("primaryTypeDisplayName") or {}).get("text"),
            "Adresse": place.get("formattedAddress"),
            "Note": place.get("rating"),
            "Nb_avis": place.get("userRatingCount"),
            "Site_web": place.get("websiteUri"),
            "Telephone": place.get("nationalPhoneNumber"),
            "Lien_Maps": place.get("googleMapsUri"),
            "Requete": query,
        }

    def collect(self) -> SourceResult:
        if not self.api_key:
            return SourceResult(self.name, _empty(), ["GOOGLE_API_KEY non configurée"])
        rows, errors = [], []
        for query in self.queries:
            try:
                rows.extend(self.to_row(p, query) for p in self._search(query))
            except Exception as ex:  # une requête en échec n'arrête pas les autres
                errors.append(f"« {query} » : {ex}")
        data = pd.DataFrame(rows, columns=RAW_COLS) if rows else _empty()
        return SourceResult(self.name, data, errors)


def collect_all(sources) -> tuple[pd.DataFrame, list[dict]]:
    """Exécute chaque source, isole les échecs et renvoie (données brutes concaténées, journal)."""
    frames, log = [], []
    for source in sources:
        started = time.time()
        try:
            result = source.collect()
        except Exception as ex:
            result = SourceResult(getattr(source, "name", "source"), _empty(), [str(ex)])
        if not result.rows.empty:
            frames.append(result.rows.assign(Source=result.name))
        log.append({
            "source": result.name,
            "lignes": int(len(result.rows)),
            "statut": "succès" if not result.errors else ("partiel" if len(result.rows) else "échec"),
            "erreurs": " ; ".join(result.errors),
            "duree_s": round(time.time() - started, 2),
        })
    if frames:
        raw = pd.concat(frames, ignore_index=True)
    else:
        raw = pd.DataFrame(columns=RAW_COLS + ["Source"])
    return raw, log
