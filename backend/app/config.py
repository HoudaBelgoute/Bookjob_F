"""Configuration : chemins et variables d'environnement."""
from email.mime import base
import os
from contextvars import ContextVar
from pathlib import Path
from urllib.parse import urlsplit

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("BOOKJOB_DATA", BASE / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
CV_SENT_DIR = UPLOAD_DIR / "cv_envoyes"      # CV liés à une candidature
CV_LIB_DIR = UPLOAD_DIR / "cv_bibliotheque"  # CV importés dans le CV Studio
FRONT_DIST = Path(os.getenv("BOOKJOB_FRONT_DIST", BASE.parent / "frontend" / "dist"))

XLSX = DATA_DIR / "donnees_nettoyees.xlsx"
SUIVI = DATA_DIR / "suivi.csv"
PROFIL = DATA_DIR / "profil.json"
STATE = DATA_DIR / "state.json"
GEOCACHE = DATA_DIR / "geocode_cache.json"



for d in (DATA_DIR, CV_SENT_DIR, CV_LIB_DIR):
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:  # Vercel : disque en lecture seule
        pass

MAX_UPLOAD = 5 * 1024 * 1024
ALLOWED_CV_EXT = {"pdf"}

# Account authentication and private per-user storage.
BOOKJOB_ENV = os.getenv("BOOKJOB_ENV", "development").lower()
SESSION_COOKIE_NAME = "bookjob_session"
SESSION_MAX_AGE = 8 * 60 * 60
AUTH_DB = Path(os.getenv("BOOKJOB_AUTH_DB", DATA_DIR / "auth.sqlite3"))
REGISTRATION_KEY = os.getenv("BOOKJOB_REGISTRATION_KEY", "")
_CURRENT_USER_ID: ContextVar[str | None] = ContextVar("bookjob_user_id", default=None)


def set_current_user(user_id: str):
    return _CURRENT_USER_ID.set(user_id)


def reset_current_user(token) -> None:
    _CURRENT_USER_ID.reset(token)


def current_user_id() -> str | None:
    return _CURRENT_USER_ID.get()


def user_data_dir(user_id: str | None = None) -> Path | None:
    user_id = user_id or current_user_id()
    if not user_id:
        return None
    base = Path("/tmp/bookjob") if os.getenv("VERCEL") else DATA_DIR
    return base / "users" / user_id


def user_path(path: Path) -> Path:
    root = user_data_dir()
    if root is None:
        return path
    try:
        relative = Path(path).relative_to(DATA_DIR)
    except ValueError:
        relative = Path("private") / Path(path).name
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_OAUTH_REDIRECT_URI = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "")
if os.getenv("GOOGLE_TOKEN_FILE"):
    GOOGLE_TOKEN_FILE = Path(os.environ["GOOGLE_TOKEN_FILE"])
elif os.name == "nt":
    GOOGLE_TOKEN_FILE = (
        Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        / "BookJob"
        / "google_oauth_token.json"
    )
else:
    GOOGLE_TOKEN_FILE = (
        Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        / "bookjob"
        / "google_oauth_token.json"
    )
GOOGLE_STATE_COOKIE = "bookjob_google_oauth_state"
BOOKJOB_PUBLIC_URL = os.getenv("BOOKJOB_PUBLIC_URL", "http://localhost:8000").rstrip("/")
EMAIL_CONFIRMATIONS_FILE = Path(
    os.getenv("EMAIL_CONFIRMATIONS_FILE", DATA_DIR / "email_confirmations.json")
)
EMAIL_CONFIRMATION_TTL_SECONDS = 20 * 60
if BOOKJOB_ENV == "production":
    if urlsplit(BOOKJOB_PUBLIC_URL).scheme != "https":
        raise RuntimeError("BOOKJOB_PUBLIC_URL doit utiliser HTTPS en production")
    if urlsplit(GOOGLE_OAUTH_REDIRECT_URI).scheme != "https":
        raise RuntimeError("GOOGLE_OAUTH_REDIRECT_URI doit utiliser HTTPS en production")

STATUTS = [
    "Brouillon", "À envoyer", "Candidature envoyée", "En cours de traitement",
    "Entretien programmé", "Acceptée", "Refusée", "Offre expirée ou candidature annulée",
]
LEGACY_STATUTS = {
    "À contacter": "Brouillon",
    "À postuler": "À envoyer",
    "CV envoyé": "Candidature envoyée",
    "Reçu (accusé de réception)": "En cours de traitement",
    "En cours d'examen": "En cours de traitement",
    "Relancé": "Candidature envoyée",
    "Entretien": "Entretien programmé",
    "Accepté": "Acceptée",
    "Refusé": "Refusée",
    "Sans réponse": "Candidature envoyée",
}
STATUTS_NON_ENVOYES = {"Brouillon", "À envoyer"}
STATUTS_RELANCE = {"Candidature envoyée", "En cours de traitement", "Entretien programmé"}
COLS = ["ID", "Entreprise", "Secteur", "Poste_visé", "Email_contact", "Source", "Lien_offre", "Statut",
        "Date_candidature", "Date_relance", "Date_entretien", "Fichier_CV", "Remarque",
        "Date_modification", "Derniere_activite", "Derniere_verification_email"]
SOURCES = ["Google Maps", "Candidature directe", "LinkedIn", "Indeed", "Rekrute", "Emploi.ma", "Autre"]
PROFILE_FIELDS = ["nom", "titre", "email", "tel", "ville", "linkedin", "resume", "competences",
                  "formation", "experiences", "projets", "langues", "certifs"]

# IA : Groq uniquement.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
# Géocodage précis optionnel (sinon : position approximative au niveau du quartier)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
