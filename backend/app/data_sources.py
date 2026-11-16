"""Recherches à la demande dans des sources autorisées et normalisation des aperçus."""
from datetime import datetime, timezone
import hashlib
from urllib.parse import quote, urlsplit

import requests

from . import integrations


class DataSourceError(Exception):
    pass


def _identifier(provider: str, external_id: str, title: str, url: str) -> str:
    value = external_id or url or title
    return hashlib.sha256(f"{provider}:{value}".encode("utf-8")).hexdigest()[:24]


def _http_url(value) -> str:
    url = str(value or "").strip()
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        parsed.port
    except ValueError:
        return ""
    return url if parsed.scheme in {"http", "https"} and hostname and not parsed.username and not parsed.password else ""


def _places(key: str, query: str, location: str) -> list[dict]:
    try:
        response = requests.post(
            "https://places.googleapis.com/v1/places:searchText",
            timeout=20,
            headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask":
                     "places.id,places.displayName,places.primaryTypeDisplayName,places.formattedAddress,"
                     "places.nationalPhoneNumber,places.websiteUri,places.googleMapsUri"},
            json={"textQuery": f"{query} {location}".strip(), "pageSize": 20},
        )
        response.raise_for_status()
        places = response.json().get("places", [])
    except requests.RequestException:
        raise DataSourceError("La recherche Google Places a échoué. Vérifie la clé et l'accès à Places API.") from None
    except (ValueError, TypeError):
        raise DataSourceError("Google Places a renvoyé une réponse invalide.") from None

    retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    results = []
    for place in places:
        name = (place.get("displayName") or {}).get("text", "").strip()
        if not name:
            continue
        external_id = str(place.get("id", ""))
        url = _http_url(place.get("googleMapsUri"))
        results.append({
            "id": _identifier("google_places", external_id, name, url),
            "external_id": external_id,
            "kind": "company",
            "provider": "google_places",
            "source": "Google Places",
            "title": name,
            "company": name,
            "sector": (place.get("primaryTypeDisplayName") or {}).get("text", ""),
            "location": place.get("formattedAddress", location),
            "phone": place.get("nationalPhoneNumber", ""),
            "website": _http_url(place.get("websiteUri")),
            "url": url,
            "description": "",
            "retrieved_at": retrieved_at,
            "attribution": "Google Maps",
        })
    return results


def _jooble(key: str, query: str, location: str) -> list[dict]:
    try:
        response = requests.post(
            f"https://jooble.org/api/{key}", timeout=20,
            json={"keywords": query, "location": location},
        )
        response.raise_for_status()
        jobs = response.json().get("jobs", [])
    except requests.RequestException:
        raise DataSourceError("La recherche Jooble a échoué. Vérifie la clé et réessaie.") from None
    except (ValueError, TypeError):
        raise DataSourceError("Jooble a renvoyé une réponse invalide.") from None

    retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    results = []
    for job in jobs:
        title = str(job.get("title", "")).strip()
        if not title:
            continue
        company = str(job.get("company", "") or "").strip()
        url = _http_url(job.get("link"))
        external_id = str(job.get("id", "") or "")
        results.append({
            "id": _identifier("jooble", external_id, title, url),
            "external_id": external_id,
            "kind": "job",
            "provider": "jooble",
            "source": "Jooble",
            "title": title,
            "company": company,
            "sector": "",
            "location": str(job.get("location", "") or location),
            "phone": "",
            "website": "",
            "url": url,
            "description": str(job.get("snippet", "") or job.get("description", ""))[:4000],
            "retrieved_at": retrieved_at,
            "attribution": "Jooble",
        })
    return results


def search(provider: str, query: str, location: str) -> list[dict]:
    if provider not in {"google_places", "jooble"}:
        raise DataSourceError("Source de données non prise en charge.")
    if not query.strip() or len(query) > 150 or len(location) > 100:
        raise DataSourceError("Renseigne une recherche (150 caractères maximum) et une localisation (100 maximum).")
    try:
        key = integrations.resolve_key(provider)
    except integrations.IntegrationError as ex:
        raise DataSourceError(str(ex)) from ex
    if not key:
        label = "Google Places" if provider == "google_places" else "Jooble"
        raise DataSourceError(f"Configure une clé {label} personnelle ou serveur dans les paramètres.")
    return _places(key, query.strip(), location.strip()) if provider == "google_places" else \
        _jooble(key, query.strip(), location.strip())


def place_details(key: str, place_ids: list[str]) -> list[dict]:
    """Fetch fresh Google Places content; callers persist only the exempt place IDs."""
    results = []
    for place_id in place_ids[:20]:
        try:
            response = requests.get(
                f"https://places.googleapis.com/v1/places/{quote(place_id, safe='')}",
                timeout=15,
                headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask":
                         "id,displayName,primaryTypeDisplayName,formattedAddress,nationalPhoneNumber,"
                         "websiteUri,googleMapsUri"},
            )
            response.raise_for_status()
            place = response.json()
        except requests.RequestException:
            raise DataSourceError("Impossible d’actualiser un lieu Google Places. Vérifie la clé et réessaie.") from None
        except (ValueError, TypeError):
            raise DataSourceError("Google Places a renvoyé une réponse invalide.") from None
        name = (place.get("displayName") or {}).get("text", "").strip()
        if not name:
            continue
        place_id = str(place.get("id", place_id))
        results.append({
            "id": _identifier("google_places", place_id, name, place.get("googleMapsUri", "")),
            "external_id": place_id,
            "kind": "company",
            "provider": "google_places",
            "source": "Google Places",
            "title": name,
            "company": name,
            "sector": (place.get("primaryTypeDisplayName") or {}).get("text", ""),
            "location": place.get("formattedAddress", ""),
            "phone": place.get("nationalPhoneNumber", ""),
            "website": _http_url(place.get("websiteUri")),
            "url": _http_url(place.get("googleMapsUri")),
            "description": "",
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "attribution": "Google Maps",
        })
    return results
