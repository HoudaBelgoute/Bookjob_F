"""Entreprises (Google Maps nettoyé), coordonnées, distance, matching profil ↔ secteur."""
import hashlib
import json
import math
import re

import pandas as pd
import requests

from . import config as C
from .store import LOCK, split_list

# Centres approximatifs des quartiers (le fichier Google Places n'a pas de latitude/longitude).
QUARTIER_COORDS = {
    "Guéliz": (31.6346, -8.0089), "Hivernage": (31.6230, -8.0095), "Médina": (31.6258, -7.9891),
    "Sidi Ghanem": (31.6760, -8.0330), "Targa": (31.6520, -8.0480), "Massira": (31.6100, -8.0350),
    "Non précisé": (31.6295, -7.9811),
}
TONES = ["blue", "gold", "green", "violet"]

# Mots-clés par secteur, comparés aux compétences du profil (estimation, pas une probabilité d'embauche).
SECTOR_KEYWORDS = {
    "IT / Dev / Data": ["python", "sql", "etl", "data", "analyse", "power", "bi", "powerbi", "java", "javascript", "react",
                        "web", "machine", "learning", "excel", "pandas", "tableau", "git", "django", "api"],
    "Digital / Marketing": ["marketing", "seo", "communication", "digital", "analytics", "excel", "design", "réseaux",
                            "contenu", "data", "analyse", "powerbi", "bi"],
    "Banque / Finance": ["excel", "sql", "analyse", "finance", "comptabilité", "powerbi", "bi", "python", "risque", "data", "etl"],
    "Conseil": ["analyse", "excel", "powerbi", "bi", "sql", "python", "communication", "data", "gestion", "etl"],
    "Hôtellerie": ["communication", "langues", "excel", "gestion", "anglais", "français", "analyse", "data"],
    "Centre d'appel / BPO": ["communication", "langues", "anglais", "français", "excel", "analyse", "data", "sql"],
}

_cache: dict = {"df": None}


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def short_name(name: str) -> str:
    n = re.split(r"\s[-–—|:]\s|\s\|\s|\s:\s|!", str(name))[0].strip(" -–|:!")
    n = n if len(n) >= 3 else str(name)
    return n[:60]


def initials(name: str) -> str:
    words = [w for w in re.findall(r"[A-Za-zÀ-ÿ0-9]+", name) if w]
    if not words:
        return "?"
    return (words[0][0] + (words[1][0] if len(words) > 1 else (words[0][1] if len(words[0]) > 1 else ""))).upper()


def _jitter(cid: str):
    h = int(hashlib.md5(str(cid).encode()).hexdigest(), 16)
    return ((h % 1000) / 1000 - 0.5) * 0.012, (((h // 1000) % 1000) / 1000 - 0.5) * 0.012


def load_geocache() -> dict:
    with LOCK:
        if C.GEOCACHE.exists():
            try:
                return json.loads(C.GEOCACHE.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {}
    return {}


def _save_geocache(c: dict) -> None:
    with LOCK:
        C.GEOCACHE.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")


def companies_df(force: bool = False) -> pd.DataFrame:
    if _cache["df"] is not None and not force:
        return _cache["df"]
    d = pd.read_excel(C.XLSX, sheet_name="Données nettoyées")
    d = d.where(pd.notna(d), None)
    d["Nom_court"] = d["Entreprise"].map(short_name)
    d["Initiales"] = d["Nom_court"].map(initials)
    d["Tone"] = d["ID"].map(lambda i: TONES[int(hashlib.md5(str(i).encode()).hexdigest(), 16) % len(TONES)])
    gc = load_geocache()
    lat, lon, exact = [], [], []
    for _, r in d.iterrows():
        key = f"company:{r.ID}"
        if gc.get(key):
            lat.append(gc[key][0]); lon.append(gc[key][1]); exact.append(True)
        else:
            base = QUARTIER_COORDS.get(r.Quartier, QUARTIER_COORDS["Non précisé"])
            jl, jo = _jitter(r.ID)
            lat.append(base[0] + jl); lon.append(base[1] + jo); exact.append(False)
    d["lat"], d["lon"], d["coord_exacte"] = lat, lon, exact
    _cache["df"] = d
    return d


def reload() -> None:
    _cache["df"] = None


def match_info(row, profile: dict) -> dict:
    """Estimation de compatibilité profil ↔ secteur (mots-clés). None si le profil n'a pas de compétences."""
    skills = {s.lower() for s in split_list(profile.get("competences", ""))}
    skills |= {w.lower() for s in list(skills) for w in re.findall(r"\w+", s)}
    if not skills:
        return {"match": None, "match_skills": [], "missing_skills": []}
    kws = SECTOR_KEYWORDS.get(row["Secteur"], SECTOR_KEYWORDS["Conseil"])
    hit = [k for k in kws if k in skills]
    missing = [k for k in kws if k not in skills][:6]
    ratio = len(hit) / max(1, min(len(kws), 8))
    score = round(min(98, 25 + 60 * min(1.0, ratio) + (float(row["Score"] or 50) - 50) * 0.2))
    return {"match": int(score), "match_skills": hit, "missing_skills": missing}


def logo_url(row) -> str | None:
    """Logo public de l'entreprise (icône de son site officiel). Aucune image pour les pages Facebook/OTA."""
    domain = row.get("Domaine") if hasattr(row, "get") else None
    if not domain or not isinstance(domain, str) or row.get("Site_type") != "Site propre":
        return None
    domain = domain.strip().lower()
    if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", domain):
        return None
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=128"


def to_item(row, profile: dict, favorites: set, tracked: dict, home=None) -> dict:
    m = match_info(row, profile)
    t = tracked.get(row["ID"])
    dist = None
    if home:
        dist = round(haversine_km(home["lat"], home["lon"], row["lat"], row["lon"]), 1)
    f = lambda k: (None if row[k] is None or (isinstance(row[k], float) and math.isnan(row[k])) else row[k])
    tracked_email = (t or {}).get("Email_contact", "")
    data_email = next((f(key) for key in ("Email_contact", "Email", "E-mail", "email")
                       if key in row.index and f(key)), None)
    return {
        "id": row["ID"], "name": row["Entreprise"], "short": row["Nom_court"], "initials": row["Initiales"],
        "tone": row["Tone"], "logo_url": logo_url(row), "secteur": row["Secteur"], "categorie": f("Categorie"), "quartier": row["Quartier"],
        "ville": row["Ville"], "adresse": f("Adresse"), "telephone": f("Telephone"), "site_web": f("Site_web"),
        "email": tracked_email or data_email or "",
        "site_type": f("Site_type"), "note": f("Note"), "nb_avis": None if f("Nb_avis") is None else int(row["Nb_avis"]),
        "score": float(row["Score"]), "priorite": row["Priorite"], "lien_maps": f("Lien_Maps"),
        "lat": row["lat"], "lon": row["lon"], "coord_exacte": bool(row["coord_exacte"]), "distance_km": dist,
        "favorite": row["ID"] in favorites, "statut": t["Statut"] if t else None,
        "requetes": f("Requetes_sources"), **m,
    }


# ---------- géocodage ----------
def _norm(t: str) -> str:
    import unicodedata
    return "".join(ch for ch in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(ch) != "Mn")


def quartier_lookup(adresse: str):
    """Si l'adresse est (ou contient) un quartier connu, position approximative sans réseau."""
    a = _norm(adresse)
    for name, xy in QUARTIER_COORDS.items():
        if name != "Non précisé" and _norm(name) in a and len(a) <= len(_norm(name)) + 20:
            return xy
    return None


def geocoder_adresse(adresse: str):
    """Nominatim (OpenStreetMap, sans clé), résultat mis en cache dans geocode_cache.json."""
    cache = load_geocache()
    if adresse in cache:
        return tuple(cache[adresse]) if cache[adresse] else None
    result = None
    try:
        q = adresse if "marrakech" in adresse.lower() else adresse + ", Marrakech, Maroc"
        r = requests.get("https://nominatim.openstreetmap.org/search", params={"q": q, "format": "json", "limit": 1},
                         headers={"User-Agent": "bookjob-marrakech/1.0"}, timeout=8)
        data = r.json()
        result = (float(data[0]["lat"]), float(data[0]["lon"])) if data else None
    except Exception:
        return None  # erreur réseau : ne pas mettre en cache
    cache[adresse] = list(result) if result else None
    _save_geocache(cache)
    return result


def geocode_google(adresse: str):
    """Géocodage précis optionnel (variable GOOGLE_API_KEY, clé jamais exposée au navigateur)."""
    if not C.GOOGLE_API_KEY:
        return None
    try:
        r = requests.get("https://maps.googleapis.com/maps/api/geocode/json",
                         params={"address": adresse, "region": "ma", "key": C.GOOGLE_API_KEY}, timeout=8)
        j = r.json()
        if j.get("status") == "OK":
            loc = j["results"][0]["geometry"]["location"]
            return float(loc["lat"]), float(loc["lng"])
    except Exception:
        return None
    return None


def geocode_companies_google(limit: int = 400) -> dict:
    """Affine les coordonnées des entreprises à partir de leur adresse (une seule fois, mis en cache)."""
    if not C.GOOGLE_API_KEY:
        return {"ok": False, "detail": "GOOGLE_API_KEY non configurée"}
    d = companies_df()
    cache = load_geocache()
    done = fail = 0
    for _, r in d.iterrows():
        key = f"company:{r.ID}"
        if key in cache or not r.Adresse or done + fail >= limit:
            continue
        res = geocode_google(r.Adresse)
        if res:
            cache[key] = list(res); done += 1
        else:
            fail += 1
    _save_geocache(cache)
    reload()
    return {"ok": True, "geocoded": done, "failed": fail}
