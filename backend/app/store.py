"""Persistance Postgres (Supabase) : suivi, profil, state (favoris, alertes, réglages, conversations, CV).

Les fonctions publiques gardent les mêmes noms/signatures que l'ancienne version fichiers.
"""
import re
import threading
import uuid
from datetime import date, timedelta

import pandas as pd
from psycopg.types.json import Jsonb

from . import config as C
from . import db

LOCK = threading.RLock()  # conservé : d'autres modules peuvent l'importer

DEFAULT_STATE = {
    "favorites": [],
    "alerts": [],
    "settings": {"emailAlerts": True, "useProfileForAI": True},
    "chats": [],
    "cvs": [],          # [{id, name, file, size, uploaded, main}]
    "home": None,       # {lat, lon, label}
}

_TABLES = {"user_state": "data", "user_profile": "data", "user_tracking": "rows"}


def _uid() -> str:
    return str(C.current_user_id() or "default")


def _read(table: str, column: str):
    assert _TABLES.get(table) == column
    with db.connection() as conn:
        row = conn.execute(
            f"SELECT {column} FROM {table} WHERE user_id = %s", (_uid(),)
        ).fetchone()
    return row[column] if row else None


def _write(table: str, column: str, value) -> None:
    assert _TABLES.get(table) == column
    with db.connection() as conn:
        conn.execute(
            f"""INSERT INTO {table} (user_id, {column}, updated_at)
                VALUES (%s, %s, now())
                ON CONFLICT (user_id)
                DO UPDATE SET {column} = EXCLUDED.{column}, updated_at = now()""",
            (_uid(), Jsonb(value)),
        )


def new_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def sanitize(txt) -> str:
    return "".join(c if c.isalnum() else "_" for c in str(txt))[:40]


# ---------- state ----------
def load_state() -> dict:
    s = _read("user_state", "data") or {}
    out = json_copy(DEFAULT_STATE)
    out.update(s)
    out["settings"] = {**DEFAULT_STATE["settings"], **s.get("settings", {})}
    return out


def save_state(s: dict) -> None:
    _write("user_state", "data", s)


def json_copy(obj):
    import json
    return json.loads(json.dumps(obj))


# ---------- profil ----------
def load_profile() -> dict:
    p = _read("user_profile", "data") or {}
    return {k: str(p.get(k, "") or "") for k in C.PROFILE_FIELDS}


def save_profile(p: dict) -> dict:
    clean = {k: str(p.get(k, "") or "").strip() for k in C.PROFILE_FIELDS}
    _write("user_profile", "data", clean)
    return clean


def split_list(txt: str) -> list[str]:
    """Compétences/langues : séparées par virgules, point-virgules, retours ligne ; à défaut par espaces."""
    txt = (txt or "").strip()
    if not txt:
        return []
    parts = re.split(r"[,;\n]+", txt)
    if len(parts) == 1:
        parts = txt.split()
    return [x.strip() for x in parts if x.strip()]


PROFILE_SECTIONS = [  # (champ, libellé, poids)
    ("nom", "Nom complet", 10), ("prenom", "Prénom", 2), ("nom_famille", "Nom", 2),
    ("titre", "Intitulé visé", 10), ("email", "E-mail", 10), ("tel", "Téléphone", 5),
    ("ville", "Ville / localisation", 5), ("filiere", "Filière", 2), ("diplomes", "Diplômes", 3),
    ("resume", "Profil professionnel", 10), ("competences", "Compétences", 15),
    ("formation", "Formation", 10), ("experiences", "Expérience professionnelle", 10),
    ("engagement_associatif", "Engagement associatif", 1), ("projets", "Projets", 10),
    ("langues", "Langues", 3), ("certifs", "Certifications", 2),
]


def profile_completion(p: dict) -> dict:
    done = [{"field": f, "label": l, "done": bool(p.get(f, "").strip())} for f, l, _ in PROFILE_SECTIONS]
    total = sum(w for *_, w in PROFILE_SECTIONS)
    got = sum(w for (f, _, w) in PROFILE_SECTIONS if p.get(f, "").strip())
    return {"percent": round(100 * got / total), "items": done}


# ---------- suivi ----------
def _normalize(data: pd.DataFrame) -> pd.DataFrame:
    data = data.reindex(columns=C.COLS, fill_value="")
    data["Statut"] = data["Statut"].replace(C.LEGACY_STATUTS)
    return data


def load_tracking() -> pd.DataFrame:
    rows = _read("user_tracking", "rows")
    if rows is not None:
        return _normalize(pd.DataFrame(rows, columns=C.COLS).fillna("").astype(str))
    if C.current_user_id():
        # Compte sans suivi enregistré : liste vide (l'import initial se fait à la création du 1er compte).
        return pd.DataFrame(columns=C.COLS)
    return tracking_from_workbook(C.XLSX)


def tracking_from_workbook(workbook) -> pd.DataFrame:
    """Feuille « Suivi » du classeur Excel livré avec le dépôt (lecture seule)."""
    try:
        d = pd.read_excel(workbook, sheet_name="Suivi").fillna("").astype(str)
        d["Lien_offre"] = ""
        d["Fichier_CV"] = ""
        return _normalize(d)
    except Exception:
        return pd.DataFrame(columns=C.COLS)


def save_tracking(d: pd.DataFrame) -> None:
    saved = d.reindex(columns=C.COLS, fill_value="").copy()
    saved["Statut"] = saved["Statut"].replace(C.LEGACY_STATUTS)
    _write("user_tracking", "rows", saved.fillna("").astype(str).to_dict(orient="records"))


def default_relance(date_candidature: str, days: int = 7) -> str:
    try:
        return str(date.fromisoformat(date_candidature) + timedelta(days=days))
    except ValueError:
        return ""