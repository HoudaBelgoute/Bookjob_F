"""Connecteurs de collecte. Chaque source renvoie un DataFrame au format brut commun ``RAW_COLS``.

Une source qui échoue n'interrompt pas les autres : l'erreur est consignée dans le journal d'exécution.
LinkedIn n'est pas collecté automatiquement (conditions d'utilisation restrictives, pas d'API publique
d'offres) : les offres LinkedIn sont ajoutées manuellement dans le suivi (champ « Source »).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
import re
import unicodedata
from urllib.parse import urljoin

import pandas as pd
import requests

RAW_COLS = ["Entreprise", "Categorie", "Adresse", "Note", "Nb_avis", "Site_web", "Telephone", "Lien_Maps", "Requete"]
OPPORTUNITY_COLS = ["Intitule", "Employeur", "Ville", "Type", "Date_limite", "Lien", "Source"]
PUBLIC_JOBS_URL = "https://www.emploi-public.ma/fr/concours-liste"

# Requêtes utilisées pour la collecte Google Maps (Marrakech). Modifiables via --queries.
DEFAULT_QUERIES = [
    "entreprise informatique Marrakech",
    "société de développement web Marrakech",
    "agence digitale Marrakech",
    "agence marketing digital Marrakech",
    "startup Marrakech",
    "entreprise intelligence artificielle Marrakech",
    "entreprise cybersécurité Marrakech",
    "entreprise télécommunications Marrakech",
    "cabinet recrutement Marrakech",
    "agence intérim Marrakech",
    "centre de formation professionnelle Marrakech",
    "école de formation informatique Marrakech",
    "école de langues Marrakech",
    "université Marrakech",
    "bureau d'études Marrakech",
    "cabinet ingénierie Marrakech",
    "cabinet de conseil Marrakech",
    "cabinet comptable Marrakech",
    "banque Marrakech",
    "assurance Marrakech",
    "centre d'appel Marrakech",
    "laboratoire médical Marrakech",
    "clinique Marrakech",
    "industrie Marrakech",
    "entreprise BTP Marrakech",
    "entreprise logistique Marrakech",
    "entreprise tourisme Marrakech",
    "hôtel Marrakech",
]

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Bounding box autour de Marrakech; les adresses manquantes sont explicitement localisées dans cette zone.
MARRAKECH_BBOX = (31.52, -8.12, 31.75, -7.80)
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


@dataclass
class OpportunityResult:
    name: str
    rows: pd.DataFrame
    errors: list[str] = field(default_factory=list)


class _PublicListingParser(HTMLParser):
    """Extrait les cartes de concours du HTML public d'Emploi Public."""

    def __init__(self):
        super().__init__()
        self.div_depth = 0
        self.card_depth: int | None = None
        self.card: dict | None = None
        self.capture: str | None = None
        self.capture_tag: str | None = None
        self.cards: list[dict] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if tag == "div":
            if self.card is None and "s-item" in classes:
                self.card_depth = self.div_depth
                self.card = {"title": [], "employer": [], "text": [], "href": None}
            elif self.card is not None and "card-text" in classes:
                self.capture, self.capture_tag = "employer", tag
            self.div_depth += 1
        elif tag == "h2" and self.card is not None:
            self.capture, self.capture_tag = "title", tag
        elif tag == "a" and self.card is not None:
            href = attributes.get("href") or ""
            if "/concours/details/" in href:
                self.card["href"] = href

    def handle_endtag(self, tag: str) -> None:
        if tag == self.capture_tag:
            self.capture = self.capture_tag = None
        if tag == "div":
            self.div_depth -= 1
            if self.card is not None and self.div_depth == self.card_depth:
                self.cards.append(self.card)
                self.card = None
                self.card_depth = None

    def handle_data(self, data: str) -> None:
        if self.card is None:
            return
        text = " ".join(data.split())
        if not text:
            return
        self.card["text"].append(text)
        if self.capture:
            self.card[self.capture].append(text)


class PublicEmploymentSource:
    """Concours/emplois publics de Marrakech encore ouverts, depuis le portail officiel."""

    name = "emploi_public"

    def __init__(self, session: requests.Session | None = None, max_pages: int = 5,
                 today: date | None = None, timeout: int = 25):
        self.http = session or requests.Session()
        self.max_pages = max_pages
        self.today = today or date.today()
        self.timeout = timeout

    @staticmethod
    def _deadline(text: str) -> date | None:
        match = re.search(r"limite de dépôt\s*:\s*(\d{1,2})\s+([a-zéèêûîôàùç]+)\s+(\d{4})",
                          text, re.IGNORECASE)
        if not match:
            return None
        month_name = unicodedata.normalize("NFD", match.group(2).lower())
        month_name = "".join(char for char in month_name if unicodedata.category(char) != "Mn")
        months = {
            "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
            "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
        }
        month = months.get(month_name)
        if not month:
            return None
        try:
            return datetime(int(match.group(3)), month, int(match.group(1))).date()
        except ValueError:
            return None

    def collect(self) -> OpportunityResult:
        rows, errors, seen = [], [], set()
        for page in range(1, self.max_pages + 1):
            try:
                response = self.http.get(
                    PUBLIC_JOBS_URL,
                    params={"key_word": "Marrakech", "page": page},
                    timeout=self.timeout,
                    headers={"User-Agent": "BookJob/1.0 (public opportunity links; contact: bookjob)"},
                )
                if response.status_code != 200:
                    raise RuntimeError(f"HTTP {response.status_code} : {response.text[:200]}")
                parser = _PublicListingParser()
                parser.feed(response.text)
            except Exception as ex:
                errors.append(f"Page {page} : {ex}")
                break

            if not parser.cards:
                break
            new_cards = 0
            for card in parser.cards:
                href = card.get("href")
                if not href or href in seen:
                    continue
                seen.add(href)
                new_cards += 1
                text = " ".join(card["text"])
                title = " ".join(card["title"]).strip()
                employer = " ".join(card["employer"]).strip() or None
                deadline = self._deadline(text)
                if not title or not deadline or deadline < self.today:
                    continue
                if not re.search(r"\bannonce\b", text, re.IGNORECASE):
                    continue
                rows.append({
                    "Intitule": title,
                    "Employeur": employer,
                    "Ville": "Marrakech",
                    "Type": "Stage" if re.search(r"\b(stage|stagiaire)\b", title, re.IGNORECASE)
                    else "Concours / emploi public",
                    "Date_limite": deadline.isoformat(),
                    "Lien": urljoin(PUBLIC_JOBS_URL, href),
                    "Source": "Emploi Public",
                })
            if new_cards == 0:
                break

        data = pd.DataFrame(rows, columns=OPPORTUNITY_COLS) if rows else pd.DataFrame(columns=OPPORTUNITY_COLS)
        return OpportunityResult(self.name, data, errors)


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


class OpenStreetMapSource:
    """Organisations, recruteurs et lieux de formation locaux via l'API Overpass, sans clé API."""

    name = "openstreetmap"

    def __init__(self, session: requests.Session | None = None, timeout: int = 60):
        self.http = session or requests.Session()
        self.timeout = timeout

    @staticmethod
    def _query() -> str:
        south, west, north, east = MARRAKECH_BBOX
        bbox = f"{south},{west},{north},{east}"
        return f"""[out:json][timeout:45];
(
  nwr["office"~"company|employment_agency|educational_institution|consulting|it"]({bbox});
  nwr["amenity"~"college|university|language_school|training"]({bbox});
  nwr["craft"~"it|engineering|accountant|advertising"]({bbox});
);
out center tags;"""

    @staticmethod
    def _category(tags: dict) -> str:
        for key in ("office", "amenity", "craft"):
            if tags.get(key):
                return str(tags[key]).replace("_", " ").title()
        return "Entreprise"

    @staticmethod
    def _address(tags: dict) -> str:
        parts = [
            " ".join(filter(None, [tags.get("addr:housenumber"), tags.get("addr:street")])),
            tags.get("addr:suburb") or tags.get("addr:district"),
            tags.get("addr:postcode"),
            tags.get("addr:city") or "Marrakech",
            "Morocco",
        ]
        return ", ".join(part for part in parts if part)

    @classmethod
    def to_row(cls, element: dict) -> dict | None:
        tags = element.get("tags") or {}
        name = tags.get("name") or tags.get("name:fr") or tags.get("brand")
        if not name:
            return None
        object_type = element.get("type")
        object_id = element.get("id")
        maps_url = (f"https://www.openstreetmap.org/{object_type}/{object_id}"
                    if object_type and object_id is not None else None)
        website = tags.get("website") or tags.get("contact:website")
        phone = tags.get("phone") or tags.get("contact:phone")
        category = cls._category(tags)
        query = ("centre de formation Marrakech" if any(
            word in category.lower() for word in ("school", "college", "university", "training", "education")
        ) else ("recrutement Marrakech" if "employment" in category.lower() else f"entreprise {category} Marrakech"))
        return {
            "Entreprise": name,
            "Categorie": category,
            "Adresse": cls._address(tags),
            "Note": None,
            "Nb_avis": None,
            "Site_web": website,
            "Telephone": phone,
            "Lien_Maps": maps_url,
            "Requete": query,
        }

    def collect(self) -> SourceResult:
        try:
            for attempt in range(3):
                response = self.http.post(
                    OVERPASS_URL,
                    data={"data": self._query()},
                    timeout=self.timeout,
                    headers={"User-Agent": "BookJob/1.0 (Marrakech employment and training directory)"},
                )
                if response.status_code == 200:
                    break
                if response.status_code not in {429, 502, 503, 504} or attempt == 2:
                    raise RuntimeError(f"HTTP {response.status_code} : {response.text[:200]}")
                time.sleep(2 ** attempt)
            elements = response.json().get("elements", [])
            rows = [row for item in elements if (row := self.to_row(item)) is not None]
            return SourceResult(self.name, pd.DataFrame(rows, columns=RAW_COLS) if rows else _empty())
        except Exception as ex:
            return SourceResult(self.name, _empty(), [f"Collecte Overpass impossible : {ex}"])


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
