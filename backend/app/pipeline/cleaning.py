"""Nettoyage des données Google Maps : règles reproductibles issues du « Rapport nettoyage ».

Chaque règle compte les lignes concernées et alimente le rapport (problème → nombre → traitement),
pour que l'Excel « après nettoyage » documente exactement ce qui a été corrigé.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from urllib.parse import urlparse

import numpy as np
import pandas as pd

from .sources import RAW_COLS

TARGET_CITY = "Marrakech"
UNKNOWN = "Non précisé"
OTHER_CITIES = ["Agadir", "Casablanca", "Rabat", "Tanger", "Fès", "Meknès", "Essaouira", "Safi", "El Jadida",
                "Kénitra", "Oujda", "Tétouan", "Benguerir", "Ouarzazate", "Mohammedia", "Salé"]
# Catégories Google de commerces / services non employeurs pour un stage (configurable).
NON_EMPLOYER_CATEGORIES = {
    "electronics store", "atm", "cafe", "coffee shop", "store", "shopping mall", "supermarket", "grocery store",
    "clothing store", "cell phone store", "furniture store", "convenience store", "restaurant", "bakery",
}
SOCIAL_DOMAINS = ("facebook.com", "instagram.com", "linkedin.com", "booking.com", "tripadvisor.", "airbnb.",
                  "wa.me", "whatsapp.com", "linktr.ee", "tiktok.com", "youtube.com", "twitter.com", "x.com",
                  "expedia.", "hotels.com", "business.site", "sites.google.com")
QUARTIERS = {
    "Guéliz": ["gueliz"], "Hivernage": ["hivernage"], "Médina": ["medina"], "Sidi Ghanem": ["sidi ghanem"],
    "Targa": ["targa"], "Massira": ["massira"],
}
# Ordre = priorité en cas d'égalité : une requête est classée dans le premier secteur reconnu.
SECTOR_RULES = [
    ("Centre d'appel / BPO", ["centre d'appel", "call center", "bpo", "relation client"]),
    ("Banque / Finance", ["banque", "finance", "assurance", "comptab", "fiduciaire", "audit"]),
    ("Hôtellerie", ["hotel", "riad", "tourisme", "resort"]),
    ("Conseil", ["conseil", "consulting", "bureau d'etudes", "cabinet"]),
    ("Digital / Marketing", ["marketing", "communication", "publicite", "evenementiel"]),
    ("IT / Dev / Data", ["informatique", "developpement", "web", "logiciel", "data", "digital", "startup",
                         "numerique"]),
]
SECTOR_POINTS = {"IT / Dev / Data": 50, "Digital / Marketing": 45, "Conseil": 40, "Banque / Finance": 40,
                 "Centre d'appel / BPO": 30, "Hôtellerie": 25}
OTHER_SECTOR = "Autre"
BAYES_WEIGHT = 20       # poids de la moyenne globale dans la note lissée
VISIBILITY_CAP = 2000   # au-delà, le nombre d'avis n'apporte plus de points (outliers hôtels / banques)

OUTPUT_COLS = ["ID", "Entreprise", "Secteur", "Categorie", "Quartier", "Ville", "Adresse", "Telephone", "Site_web",
               "Site_type", "Domaine", "Note", "Nb_avis", "Note_lissee", "Nb_requetes", "Score", "Priorite",
               "Requetes_sources", "Lien_Maps", "cid", "Note_manquante", "Nb_avis_manquant", "Code_postal"]
EXCLUDED_COLS = ["Entreprise", "Ville", "Categorie", "Adresse", "Motif_exclusion"]

DICTIONARY = [
    ("ID", "Identifiant interne stable (clé du suivi)", "texte"),
    ("Entreprise", "Nom Google Maps (displayName)", "texte"),
    ("Secteur", "Secteur reconstruit à partir des requêtes", "catégoriel"),
    ("Categorie", "Type principal Google (peu discriminant)", "catégoriel"),
    ("Quartier", "Extrait de l'adresse par mots-clés", "catégoriel"),
    ("Ville", "Normalisée FR/AR", "catégoriel"),
    ("Adresse", "Adresse formatée Google", "texte"),
    ("Telephone", "Format +212…", "texte"),
    ("Site_web", "URL déclarée sur la fiche", "url"),
    ("Site_type", "Site propre / réseau social / aucun", "catégoriel"),
    ("Domaine", "Domaine du site (base pour trouver l'e-mail RH)", "texte"),
    ("Note", "Note Google 1-5 (brute)", "numérique"),
    ("Nb_avis", "Nombre d'avis Google (proxy de taille/visibilité)", "numérique"),
    ("Note_lissee", f"Moyenne bayésienne : (n×note + {BAYES_WEIGHT}×moy)/(n+{BAYES_WEIGHT})", "numérique"),
    ("Nb_requetes", "Nb de requêtes ayant remonté l'entreprise", "numérique"),
    ("Score", "Pertinence /100 = secteur (≤50) + réputation (≤30) + visibilité (≤10) + contactabilité (≤10)",
     "numérique"),
    ("Priorite", "A ≥ 80 · B 65-80 · C < 65", "catégoriel"),
    ("Requetes_sources", "Requêtes d'origine", "texte"),
    ("Lien_Maps", "Lien Google Maps", "url"),
    ("cid", "Identifiant Google du lieu (clé de dédoublonnage)", "texte"),
    ("Note_manquante / Nb_avis_manquant", "Indicateurs de valeur absente", "booléen"),
    ("Code_postal", "Extrait de l'adresse", "texte"),
]


@dataclass
class CleaningResult:
    clean: pd.DataFrame
    excluded: pd.DataFrame
    report: pd.DataFrame

    def dictionary(self) -> pd.DataFrame:
        return pd.DataFrame(DICTIONARY, columns=["Colonne", "Signification", "Type"])


# ---------- règles unitaires (testées séparément) ----------
def norm(text) -> str:
    text = unicodedata.normalize("NFD", str(text or "").lower())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def text_or_none(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    value = re.sub(r"\s+", " ", str(value)).strip()
    return value or None


def extract_cid(link) -> str | None:
    match = re.search(r"[?&]cid=(\d+)", str(link or ""))
    return match.group(1) if match else None


def has_arabic(text) -> bool:
    return bool(re.search(r"[\u0600-\u06FF]", str(text or "")))


def detect_city(address) -> str:
    if not address:
        return UNKNOWN
    if "مراكش" in address:
        return TARGET_CITY
    a = norm(address)
    if "marrakech" in a or "marrakesh" in a:
        return TARGET_CITY
    for city in OTHER_CITIES:
        if re.search(rf"\b{re.escape(norm(city))}\b", a):
            return city
    if (postal_code(address) or "").startswith("40"):  # codes postaux 40xxx = zone de Marrakech
        return TARGET_CITY
    found = re.findall(r"([A-Za-zÀ-ÿ' -]{3,}?)\s+\d{5}", address)
    return found[-1].strip().title() if found else UNKNOWN


def postal_code(address) -> str | None:
    found = re.findall(r"\b(\d{5})\b", str(address or ""))
    return found[-1] if found else None


def detect_quartier(address) -> str:
    a = norm(address)
    for name, keywords in QUARTIERS.items():
        if any(k in a for k in keywords):
            return name
    return UNKNOWN


def normalize_phone(phone) -> tuple[str | None, bool]:
    """Renvoie (téléphone, est_standard). Format standard marocain → +212XXXXXXXXX."""
    if not phone:
        return None, True
    digits = re.sub(r"\D", "", str(phone))
    if re.fullmatch(r"0[5-8]\d{8}", digits):
        return "+212" + digits[1:], True
    if re.fullmatch(r"212[5-8]\d{8}", digits):
        return "+" + digits, True
    return str(phone).strip(), False


def site_domain(url) -> str | None:
    if not url or not isinstance(url, str):
        return None
    netloc = urlparse(url if "://" in url else "http://" + url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else (netloc or None)


def site_type(url) -> str:
    domain = site_domain(url)
    if not domain:
        return "Aucun"
    if any(s in domain for s in SOCIAL_DOMAINS):
        return "Réseau social/OTA"
    return "Site propre"


def query_sector(query) -> str | None:
    q = norm(query) + " "
    for sector, keywords in SECTOR_RULES:
        if any(k in q for k in keywords):
            return sector
    return None


def sector_from_queries(queries) -> str:
    votes = Counter(s for s in (query_sector(q) for q in str(queries or "").split(" | ")) if s)
    if not votes:
        return OTHER_SECTOR
    return max(votes, key=lambda s: (votes[s], SECTOR_POINTS.get(s, 0)))


def priority(score: float) -> str:
    return "A" if score >= 80 else ("B" if score >= 65 else "C")


# ---------- pipeline complet ----------
def clean(raw: pd.DataFrame, previous_ids: dict[str, str] | None = None) -> CleaningResult:
    """Nettoie un export brut. ``previous_ids`` (cid → ID) garde des ID stables d'une exécution à l'autre."""
    df = raw.copy()
    for col in RAW_COLS:
        if col not in df.columns:
            df[col] = None
    report: list[dict] = []

    def add(problem: str, count, treatment: str) -> None:
        if int(count):
            report.append({"Problème détecté": problem, "Nb lignes": int(count), "Traitement": treatment})

    for col in ["Entreprise", "Categorie", "Adresse", "Site_web", "Telephone", "Lien_Maps", "Requete"]:
        df[col] = df[col].map(text_or_none)
    df["Note"] = pd.to_numeric(df["Note"], errors="coerce")
    df["Nb_avis"] = pd.to_numeric(df["Nb_avis"], errors="coerce")

    excluded = []
    no_name = df["Entreprise"].isna()
    if no_name.any():
        excluded.append(df[no_name].assign(Ville=UNKNOWN, Motif_exclusion="Nom manquant"))
        add("Lignes sans nom d'entreprise", no_name.sum(), "Exclues")
        df = df[~no_name].copy()

    bad_note = df["Note"].notna() & ~df["Note"].between(1, 5)
    add("Notes hors de l'intervalle 1-5", bad_note.sum(), "Mises à vide")
    df.loc[bad_note, "Note"] = np.nan
    bad_count = df["Nb_avis"].notna() & (df["Nb_avis"] < 0)
    add("Nombre d'avis négatif", bad_count.sum(), "Mis à vide")
    df.loc[bad_count, "Nb_avis"] = np.nan

    # Doublons : même lieu Google (cid) remonté par plusieurs requêtes.
    df["cid"] = df["Lien_Maps"].map(extract_cid)
    fallback = "nom:" + df["Entreprise"].map(norm) + "|" + df["Adresse"].map(norm)
    df["_key"] = df["cid"].where(df["cid"].notna(), fallback)
    add("Doublons exacts (lignes identiques)", df.duplicated(subset=RAW_COLS).sum(),
        "Supprimés (inclus dans la fusion ci-dessous)")
    before = len(df)
    grouped = df.groupby("_key", sort=False)["Requete"]
    queries = grouped.agg(lambda s: " | ".join(dict.fromkeys(q for q in s if q)))
    n_queries = grouped.agg(lambda s: len({q for q in s if q}))
    df = df.drop_duplicates("_key", keep="first").set_index("_key")
    df["Requetes_sources"] = queries
    df["Nb_requetes"] = n_queries
    df = df.reset_index(drop=True)
    add("Doublons cachés (même CID Google, requêtes différentes) - invisibles pour drop_duplicates()",
        before - len(df), "Fusion : 1 ligne/établissement, requêtes cumulées")

    for col, treatment in [
        ("Categorie", "Conservée vide, secteur déduit de la requête"),
        ("Note", "Laissée vide (un fillna(0) fausserait la moyenne) + indicateur"),
        ("Nb_avis", "Laissé vide + indicateur"),
        ("Site_web", "Vide = pas de site : signal utile, non imputé"),
        ("Telephone", "Vide conservé"),
    ]:
        add(f"Valeurs manquantes : {col}", df[col].isna().sum(), treatment)
    df["Note_manquante"] = df["Note"].isna().astype(int)
    df["Nb_avis_manquant"] = df["Nb_avis"].isna().astype(int)

    df["Ville"] = df["Adresse"].map(detect_city)
    add("Adresses avec caractères arabes (mix FR/AR)", df["Adresse"].map(has_arabic).sum(),
        "Ville normalisée (مراكش → Marrakech)")
    df["Code_postal"] = df["Adresse"].map(postal_code)
    df["Quartier"] = df["Adresse"].map(detect_quartier)

    phones = df["Telephone"].map(normalize_phone)
    df["Telephone"] = phones.map(lambda p: p[0])
    add("Téléphones non standard (format différent de 0X XX XX XX XX)", phones.map(lambda p: not p[1]).sum(),
        "Non normalisés, à vérifier")

    df["Site_type"] = df["Site_web"].map(site_type)
    df["Domaine"] = df["Site_web"].map(site_domain).where(df["Site_type"].eq("Site propre"))
    add("Site web = page réseau social / plateforme (pas un vrai site)", df["Site_type"].eq("Réseau social/OTA").sum(),
        "Typé 'Réseau social/OTA'")

    add("Notes 5.0 avec < 10 avis (non fiables)", (df["Note"].eq(5) & df["Nb_avis"].lt(10)).sum(),
        "Note bayésienne (lissage) dans le score")
    add(f"Établissements > {VISIBILITY_CAP} avis (outliers, surtout hôtels/banques)",
        df["Nb_avis"].gt(VISIBILITY_CAP).sum(), "Log-échelle plafonnée pour la visibilité")
    add("Catégorie Google 'Services' trop vague", df["Categorie"].map(norm).eq("services").sum(),
        "Secteur reconstruit depuis les requêtes")
    df["Secteur"] = df["Requetes_sources"].map(sector_from_queries)

    out_of_city = ~df["Ville"].isin([TARGET_CITY, UNKNOWN])
    shops = df["Categorie"].map(norm).isin(NON_EMPLOYER_CATEGORIES) & ~out_of_city
    add("Établissements hors Marrakech (Agadir, Casablanca, Rabat…)", out_of_city.sum(), "Exclus")
    add("Commerces / DAB non employeurs (boutiques, ATM, café…)", shops.sum(), "Exclus")
    excluded.append(df[out_of_city].assign(Motif_exclusion="Hors Marrakech"))
    excluded.append(df[shops].assign(Motif_exclusion="Commerce/DAB hors cible"))
    df = df[~(out_of_city | shops)].copy()

    mean_note = df["Note"].mean()
    mean_note = 4.0 if pd.isna(mean_note) else float(mean_note)
    reviews = df["Nb_avis"].fillna(0)
    note = df["Note"].fillna(mean_note)
    df["Note_lissee"] = ((reviews * note + BAYES_WEIGHT * mean_note) / (reviews + BAYES_WEIGHT)).round(2)
    reputation = df["Note_lissee"] / 5 * 30
    visibility = np.log1p(reviews.clip(upper=VISIBILITY_CAP)) / math.log1p(VISIBILITY_CAP) * 10
    contact = (df["Site_type"].map({"Site propre": 5, "Réseau social/OTA": 2}).fillna(0)
               + df["Telephone"].notna().astype(int) * 5)
    sector = df["Secteur"].map(SECTOR_POINTS).fillna(20)
    df["Score"] = (sector + reputation + visibility + contact).round(1)
    df["Priorite"] = df["Score"].map(priority)

    df = df.sort_values(["Score", "Entreprise"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
    df["ID"] = _assign_ids(df["cid"], previous_ids or {})

    excluded_df = (pd.concat(excluded, ignore_index=True)[EXCLUDED_COLS] if excluded
                   else pd.DataFrame(columns=EXCLUDED_COLS))
    report_df = pd.DataFrame(report, columns=["Problème détecté", "Nb lignes", "Traitement"])
    return CleaningResult(df[OUTPUT_COLS], excluded_df, report_df)


def _assign_ids(cids: pd.Series, previous: dict[str, str]) -> list[str]:
    numbers = [int(m.group(1)) for v in previous.values() if (m := re.fullmatch(r"MRK-(\d+)", str(v)))]
    next_number = max(numbers, default=0) + 1
    ids = []
    for cid in cids:
        if cid and cid in previous:
            ids.append(previous[cid])
        else:
            ids.append(f"MRK-{next_number:03d}")
            next_number += 1
    return ids


def previous_ids_from(clean_df: pd.DataFrame) -> dict[str, str]:
    """Reconstitue la table cid → ID depuis un fichier nettoyé existant (via Lien_Maps, sans perte de précision)."""
    if clean_df is None or clean_df.empty or "ID" not in clean_df or "Lien_Maps" not in clean_df:
        return {}
    pairs = zip(clean_df["Lien_Maps"].map(extract_cid), clean_df["ID"])
    return {cid: str(i) for cid, i in pairs if cid}