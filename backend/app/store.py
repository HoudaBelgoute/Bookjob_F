"""Persistance fichiers : suivi.csv, profil.json, state.json (favoris, alertes, réglages, conversations, CV)."""
import json
import re
import threading
import uuid
from datetime import date, timedelta

import pandas as pd

from . import config as C

LOCK = threading.RLock()

DEFAULT_STATE = {
    "favorites": [],
    "alerts": [],
    "settings": {"emailAlerts": True, "useProfileForAI": True},
    "chats": [],
    "cvs": [],          # [{id, name, file, size, uploaded, main}]
    "home": None,       # {lat, lon, label}
}


def new_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def sanitize(txt) -> str:
    return "".join(c if c.isalnum() else "_" for c in str(txt))[:40]


# ---------- state ----------
def load_state() -> dict:
    path = C.user_path(C.STATE)
    with LOCK:
        if path.exists():
            try:
                s = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                s = {}
        else:
            s = {}
    out = json.loads(json.dumps(DEFAULT_STATE))
    out.update(s)
    out["settings"] = {**DEFAULT_STATE["settings"], **s.get("settings", {})}
    return out


def save_state(s: dict) -> None:
    path = C.user_path(C.STATE)
    with LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)


# ---------- profil ----------
def load_profile() -> dict:
    p = {}
    path = C.user_path(C.PROFIL)
    if path.exists():
        try:
            p = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            p = {}
    return {k: str(p.get(k, "") or "") for k in C.PROFILE_FIELDS}


def save_profile(p: dict) -> dict:
    clean = {k: str(p.get(k, "") or "").strip() for k in C.PROFILE_FIELDS}
    path = C.user_path(C.PROFIL)
    with LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(clean, ensure_ascii=False, indent=1), encoding="utf-8")
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
    ("nom", "Nom complet", 10), ("titre", "Intitulé visé", 10), ("email", "E-mail", 10), ("tel", "Téléphone", 5),
    ("ville", "Ville", 5), ("resume", "Résumé professionnel", 10), ("competences", "Compétences", 15),
    ("formation", "Formation", 10), ("experiences", "Expériences", 10), ("projets", "Projets", 10),
    ("langues", "Langues", 3), ("certifs", "Certifications", 2),
]


def profile_completion(p: dict) -> dict:
    done = [{"field": f, "label": l, "done": bool(p.get(f, "").strip())} for f, l, _ in PROFILE_SECTIONS]
    total = sum(w for *_, w in PROFILE_SECTIONS)
    got = sum(w for (f, _, w) in PROFILE_SECTIONS if p.get(f, "").strip())
    return {"percent": round(100 * got / total), "items": done}


# ---------- suivi ----------
def load_tracking() -> pd.DataFrame:
    path = C.user_path(C.SUIVI)
    workbook = C.user_path(C.XLSX) if C.current_user_id() else C.XLSX
    def normalize(data: pd.DataFrame) -> pd.DataFrame:
        data = data.reindex(columns=C.COLS, fill_value="")
        data["Statut"] = data["Statut"].replace(C.LEGACY_STATUTS)
        return data

    with LOCK:
        if path.exists():
            d = pd.read_csv(path, dtype=str).fillna("")
            return normalize(d)
        try:
            d = pd.read_excel(workbook, sheet_name="Suivi").fillna("").astype(str)
            d["Lien_offre"] = ""
            d["Fichier_CV"] = ""
            return normalize(d)
        except Exception:
            return pd.DataFrame(columns=C.COLS)


def save_tracking(d: pd.DataFrame) -> None:
    path = C.user_path(C.SUIVI)
    with LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        saved = d.reindex(columns=C.COLS, fill_value="").copy()
        saved["Statut"] = saved["Statut"].replace(C.LEGACY_STATUTS)
        saved.to_csv(path, index=False)


def default_relance(date_candidature: str, days: int = 7) -> str:
    try:
        return str(date.fromisoformat(date_candidature) + timedelta(days=days))
    except ValueError:
        return ""
