"""BookJob API : toutes les fonctions de l'app Streamlit « Stages Marrakech » exposées pour le front React."""
import asyncio
import hmac
import json
import logging
import mimetypes
import os
import re
import secrets
import threading
import time
import uuid
from email.message import EmailMessage
from datetime import date, datetime, timedelta, timezone
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from typing import Optional
from html import escape
from urllib.parse import urlencode

import pandas as pd
from a2wsgi import WSGIMiddleware
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import accounts, ai, companies as co, config as C, dash_dashboard, email_confirmations, email_discovery, email_sync, gmail, google_login, matching, store as S

app = FastAPI(title="BookJob API", version="1.0")

_LOGIN_ATTEMPTS: dict[str, tuple[int, float]] = {}
_LOGIN_LOCK = threading.Lock()
_EMAIL_LOCK = threading.Lock()
_LOGIN_LIMIT = 10
_LOGIN_WINDOW = 15 * 60
_EMAIL_SYNC_TASK: asyncio.Task | None = None
_LOGGER = logging.getLogger("bookjob.email_sync")


def _auth_enabled() -> bool:
    return True


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        C.SESSION_COOKIE_NAME,
        token,
        max_age=C.SESSION_MAX_AGE,
        httponly=True,
        secure=C.BOOKJOB_ENV == "production",
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


def _check_auth_rate_limit(request: Request) -> str:
    now = time.monotonic()
    client = request.client.host if request.client else "unknown"
    with _LOGIN_LOCK:
        attempts, started = _LOGIN_ATTEMPTS.get(client, (0, now))
        if now - started >= _LOGIN_WINDOW:
            attempts, started = 0, now
        if attempts >= _LOGIN_LIMIT:
            raise HTTPException(429, "Trop de tentatives. Réessaie dans 15 minutes.")
        _LOGIN_ATTEMPTS[client] = (attempts + 1, started)
    return client


class RequireLoginMiddleware:
    def __init__(self, downstream):
        self.downstream = downstream

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.downstream(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        path = request.url.path
        public_api = {
            "/api/auth/status", "/api/auth/login", "/api/auth/register", "/api/auth/logout",
            "/api/email/confirm", "/api/email/confirm/details", "/api/health",
            "/api/auth/google", "/api/google/callback",
            "/api/cron/email-sync",
        }
        protected_api = path.startswith("/api/") and path not in public_api and request.method != "OPTIONS"
        protected_dash = path == "/dash" or path.startswith("/dash/")
        user = accounts.resolve_session(request.cookies.get(C.SESSION_COOKIE_NAME, ""))

        if path in {"/api/email/confirm/details", "/api/email/confirm"} and request.method == "POST":
            token = request.headers.get("X-BookJob-Confirmation-Token", "")
            if token:
                owner_id = accounts.confirmation_user(email_confirmations.token_digest(token))
                user = {"id": owner_id, "email": ""} if owner_id else None
            else:
                user = None
            if not user:
                response = JSONResponse(
                    {"detail": "Ce lien a déjà été utilisé ou n'existe pas."}, status_code=404,
                )
                response.headers["Cache-Control"] = "no-store"
                await response(scope, receive, send)
                return

        if (protected_api or protected_dash) and not user:
            if protected_dash:
                response = RedirectResponse("/", status_code=303)
            else:
                response = JSONResponse({"detail": "Connexion requise"}, status_code=401)
            response.headers["Cache-Control"] = "no-store"
            await response(scope, receive, send)
            return

        context_token = C.set_current_user(user["id"] if user else None)

        async def add_no_store(message):
            if (
                message["type"] == "http.response.start"
                and (protected_api or protected_dash or path.startswith("/api/auth/"))
            ):
                headers = [
                    (key, value) for key, value in message.get("headers", [])
                    if key.lower() != b"cache-control"
                ]
                headers.append((b"cache-control", b"no-store"))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.downstream(scope, receive, add_no_store)
        finally:
            C.reset_current_user(context_token)


app.add_middleware(RequireLoginMiddleware)


class DashUserContextMiddleware:
    """Restore request identity inside Dash's WSGI worker thread."""

    def __init__(self, downstream):
        self.downstream = downstream

    def __call__(self, environ, start_response):
        def response():
            cookies = SimpleCookie()
            try:
                cookies.load(environ.get("HTTP_COOKIE", ""))
            except CookieError:
                cookies = SimpleCookie()
            session_cookie = cookies.get(C.SESSION_COOKIE_NAME)
            user = accounts.resolve_session(session_cookie.value if session_cookie else "")
            if not user:
                body = b"Connexion requise."
                start_response(
                    "401 Unauthorized",
                    [
                        ("Content-Type", "text/plain; charset=utf-8"),
                        ("Cache-Control", "no-store"),
                        ("Content-Length", str(len(body))),
                    ],
                )
                yield body
                return

            context_token = C.set_current_user(user["id"])
            try:
                yield from self.downstream(environ, start_response)
            finally:
                C.reset_current_user(context_token)

        return response()


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class RegisterIn(LoginIn):
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=10, max_length=256)
    registration_key: str = Field(default="", max_length=256)


@app.get("/api/auth/status")
def auth_status(request: Request):
    user = accounts.resolve_session(request.cookies.get(C.SESSION_COOKIE_NAME, ""))
    user_count = accounts.user_count()
    return {
        "required": True,
        "authenticated": bool(user),
        "user": user,
        "registration_open": True,
        "registration_key_required": bool(C.REGISTRATION_KEY) and user_count > 0,
        "google_login": google_login.configured(),
    }


@app.get("/api/auth/google")
def google_login_start():
    if not google_login.configured():
        raise HTTPException(503, "La connexion avec Google n'est pas configurée sur le serveur.")
    state = google_login.STATE_PREFIX + secrets.token_urlsafe(32)
    response = RedirectResponse(google_login.authorization_url(state), status_code=302)
    response.set_cookie(
        C.GOOGLE_STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=C.BOOKJOB_ENV == "production",
        samesite="lax",
        path="/",
    )
    return response


def _google_login_finish(code: str, error: str) -> Response:
    def fail(message: str) -> Response:
        return RedirectResponse("/?" + urlencode({"erreur_google": message}), status_code=303)

    if error or not code:
        return fail("La connexion avec Google a été annulée.")
    try:
        email, name = google_login.identity(code)
        _, token = accounts.login_with_google(email, name)
    except (PermissionError, ValueError, gmail.GmailError) as ex:
        return fail(str(ex))
    response = RedirectResponse("/", status_code=303)
    _set_session_cookie(response, token)
    return response


@app.post("/api/auth/login")
def login(body: LoginIn, request: Request):
    client = _check_auth_rate_limit(request)
    result = accounts.authenticate(body.email, body.password)
    if result is None:
        raise HTTPException(401, "Adresse e-mail ou mot de passe incorrect.")
    user, token = result
    with _LOGIN_LOCK:
        _LOGIN_ATTEMPTS.pop(client, None)
    response = JSONResponse({"ok": True, "user": user})
    _set_session_cookie(response, token)
    return response


@app.post("/api/auth/register")
def register(body: RegisterIn, request: Request):
    client = _check_auth_rate_limit(request)
    try:
        user, token = accounts.create_user(
            body.email, body.password, body.registration_key, body.full_name,
        )
    except PermissionError as ex:
        raise HTTPException(403, str(ex)) from ex
    except ValueError as ex:
        raise HTTPException(400, str(ex)) from ex
    with _LOGIN_LOCK:
        _LOGIN_ATTEMPTS.pop(client, None)
    response = JSONResponse({"ok": True, "user": user}, status_code=201)
    _set_session_cookie(response, token)
    return response


@app.post("/api/auth/logout")
def logout(request: Request):
    accounts.revoke_session(request.cookies.get(C.SESSION_COOKIE_NAME, ""))
    response = JSONResponse({"ok": True})
    response.delete_cookie(
        C.SESSION_COOKIE_NAME,
        httponly=True,
        secure=C.BOOKJOB_ENV == "production",
        samesite="lax",
        path="/",
    )
    response.delete_cookie(
        C.GOOGLE_STATE_COOKIE,
        httponly=True,
        secure=C.BOOKJOB_ENV == "production",
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def _google_oauth_result_page(message: str, *, connected: bool, status_code: int = 200) -> HTMLResponse:
    safe_message = escape(message)
    notification = (
        '<script>if(window.opener){window.opener.postMessage({type:"bookjob-gmail-connected"},'
        'window.location.origin);window.close();}</script>'
        if connected else ""
    )
    return HTMLResponse(
        f"<!doctype html><html lang='fr'><meta charset='utf-8'><title>BookJob — Gmail</title>"
        f"<body><main><h1>BookJob — Gmail</h1><p>{safe_message}</p>"
        f"<p>Tu peux fermer cette fenêtre.</p></main>{notification}</body></html>",
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/google/status")
def google_status():
    return gmail.status()


@app.get("/api/google/connect")
def google_connect():
    if not gmail.configured():
        raise HTTPException(503, "La connexion Google n'est pas configurée sur le serveur.")
    state = secrets.token_urlsafe(32)
    response = RedirectResponse(gmail.authorization_url(state), status_code=302)
    response.set_cookie(
        C.GOOGLE_STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=C.BOOKJOB_ENV == "production",
        samesite="lax",
        path="/",
    )
    return response


@app.get("/api/google/callback")
def google_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    expected_state = request.cookies.get(C.GOOGLE_STATE_COOKIE, "")
    state_ok = bool(expected_state and state and hmac.compare_digest(expected_state, state))
    if state_ok and state.startswith(google_login.STATE_PREFIX):
        response = _google_login_finish(code, error)
    elif not C.current_user_id():
        response = RedirectResponse("/", status_code=303)
    elif not state_ok:
        response = _google_oauth_result_page("La vérification de sécurité a échoué. Recommence la connexion Gmail.",
                                             connected=False, status_code=400)
    elif error:
        response = _google_oauth_result_page("L'autorisation Google a été annulée ou refusée.", connected=False,
                                             status_code=400)
    elif not code:
        response = _google_oauth_result_page("Google n'a pas renvoyé de code d'autorisation.", connected=False,
                                             status_code=400)
    else:
        try:
            sender = gmail.exchange_code(code)
        except gmail.GmailError as ex:
            response = _google_oauth_result_page(str(ex), connected=False, status_code=502)
        else:
            response = _google_oauth_result_page(f"Le compte {sender} est connecté à BookJob.", connected=True)
    response.delete_cookie(
        C.GOOGLE_STATE_COOKIE,
        httponly=True,
        secure=C.BOOKJOB_ENV == "production",
        samesite="lax",
        path="/",
    )
    return response


@app.post("/api/google/disconnect")
def google_disconnect():
    try:
        gmail.disconnect()
    except gmail.GmailError as ex:
        raise HTTPException(502, str(ex)) from ex
    return {"ok": True}


# ---------- utilitaires ----------
def _tracked_map() -> dict:
    d = S.load_tracking()
    return {r["ID"]: r for r in d.to_dict("records")}


def _company_row(cid: str):
    d = co.companies_df()
    m = d[d.ID == cid]
    if m.empty:
        raise HTTPException(404, "Entreprise introuvable")
    return m.iloc[0]


def _item(cid_or_row, home=None) -> dict:
    row = _company_row(cid_or_row) if isinstance(cid_or_row, str) else cid_or_row
    st = S.load_state()
    return co.to_item(row, S.load_profile(), set(st["favorites"]), _tracked_map(), home or st["home"])


def _track_out(r: dict, d: pd.DataFrame | None = None) -> dict:
    out = {
        "id": r["ID"], "entreprise": r["Entreprise"], "secteur": r["Secteur"], "poste": r["Poste_visé"],
        "email": r["Email_contact"], "source": r["Source"], "lien_offre": r["Lien_offre"], "statut": r["Statut"] or "Brouillon",
        "date_candidature": r["Date_candidature"], "date_relance": r["Date_relance"],
        "date_entretien": r["Date_entretien"], "fichier_cv": r["Fichier_CV"],
        "date_modification": r["Date_modification"], "derniere_activite": r["Derniere_activite"],
        "derniere_verification_email": r["Derniere_verification_email"],
        "remarque": r["Remarque"], "short": co.short_name(r["Entreprise"]), "initials": co.initials(co.short_name(r["Entreprise"])),
        "tone": "blue", "quartier": None, "ville": "Marrakech", "company_id": None,
    }
    cdf = co.companies_df()
    m = cdf[cdf.ID == r["ID"]]
    if not m.empty:
        c = m.iloc[0]
        out.update(tone=c.Tone, quartier=c.Quartier, ville=c.Ville, company_id=c.ID, short=c.Nom_court, initials=c.Initiales,
                   logo_url=co.logo_url(c))
    out["relance_due"] = bool(r["Date_relance"] and r["Date_relance"] <= str(date.today()) and r["Statut"] in C.STATUTS_RELANCE)
    return out


def _save_upload(f: UploadFile, folder: Path, base: str) -> tuple[str, int]:
    ext = (f.filename or "").rsplit(".", 1)[-1].lower() if "." in (f.filename or "") else ""
    if ext not in C.ALLOWED_CV_EXT:
        raise HTTPException(400, "Format non pris en charge : PDF ou Word (doc, docx) uniquement")
    data = f.file.read(C.MAX_UPLOAD + 1)
    if len(data) > C.MAX_UPLOAD:
        raise HTTPException(400, "Fichier trop volumineux (5 Mo maximum)")
    if not data:
        raise HTTPException(400, "Fichier vide")
    name = f"{S.sanitize(base)}.{ext}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(data)
    return name, len(data)


def _safe(folder: Path, name: str) -> Path:
    p = (folder / name).resolve()
    if folder.resolve() not in p.parents or not p.exists():
        raise HTTPException(404, "Fichier introuvable")
    return p


def _add_cv_to_library(source: Path, original_filename: str) -> None:
    """Copie un CV importé dans la bibliothèque (sauf s'il y est déjà : même nom et même taille)."""
    st = S.load_state()
    stem = (original_filename or "cv").rsplit(".", 1)[0] or "cv"
    ext = source.suffix.lstrip(".").lower()
    size = source.stat().st_size
    if any(c["name"] == stem and c["size"] == size and c["file"].lower().endswith(f".{ext}") for c in st["cvs"]):
        return
    cid = S.new_id("cv")
    lib_dir = C.user_path(C.CV_LIB_DIR)
    lib_dir.mkdir(parents=True, exist_ok=True)
    name = f"{S.sanitize(f'{cid}_{stem}')}.{ext}"
    (lib_dir / name).write_bytes(source.read_bytes())
    st["cvs"].append({"id": cid, "name": stem, "file": name, "size": size, "uploaded": str(date.today()),
                      "main": not any(c.get("main") for c in st["cvs"])})
    S.save_state(st)


def _application_email_message(sender: str, request_data: dict) -> EmailMessage:
    attachment = _safe(C.user_path(C.CV_SENT_DIR), request_data["cv_filename"])
    message = EmailMessage()
    try:
        message["From"] = sender
        message["To"] = request_data["recipient"]
        message["Subject"] = request_data["subject"]
    except ValueError as ex:
        raise HTTPException(400, "Adresse ou objet d'e-mail invalide") from ex
    message.set_content(request_data["body"])
    mime_type, _ = mimetypes.guess_type(attachment.name)
    maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
    message.add_attachment(
        attachment.read_bytes(),
        maintype=maintype,
        subtype=subtype,
        filename=attachment.name,
    )
    letter_filename = request_data.get("cover_letter_file", "")
    if letter_filename:
        letter_attachment = _safe(C.user_path(C.CV_SENT_DIR), letter_filename)
        letter_type, _ = mimetypes.guess_type(letter_attachment.name)
        letter_main, letter_sub = (letter_type or "application/octet-stream").split("/", 1)
        message.add_attachment(
            letter_attachment.read_bytes(),
            maintype=letter_main,
            subtype=letter_sub,
            filename=letter_attachment.name,
        )
    elif request_data.get("cover_letter"):
        message.add_attachment(
            request_data["cover_letter"],
            subtype="plain",
            charset="utf-8",
            filename="lettre_motivation.txt",
        )
    else:
        raise HTTPException(400, "La lettre de motivation n'est plus disponible.")
    return message


# ---------- méta ----------
@app.get("/api/meta")
def meta():
    d = co.companies_df()
    return {
        "secteurs": sorted(d.Secteur.unique()), "quartiers": sorted(d.Quartier.unique()), "priorites": ["A", "B", "C"],
        "statuts": C.STATUTS, "sources": C.SOURCES, "total_entreprises": int(len(d)),
        "ai": {"enabled": ai.provider() != "none", "provider": ai.provider()},
        "email": gmail.status(),
        "google_geocoding": bool(C.GOOGLE_API_KEY),
        "secteur_counts": d.Secteur.value_counts().to_dict(),
    }


# ---------- entreprises / opportunités ----------
@app.get("/api/companies")
def list_companies(q: str = "", secteur: list[str] = Query(default=[]), priorite: list[str] = Query(default=[]),
                   quartier: list[str] = Query(default=[]), score_min: float = 0, note_min: float = 0,
                   avec_site: bool = False, favorites_only: bool = False, suivi: str = "",
                   sort: str = "score", dmax: Optional[float] = None, lat: Optional[float] = None, lon: Optional[float] = None,
                   limit: int = 500, offset: int = 0):
    d = co.companies_df()
    st = S.load_state()
    prof = S.load_profile()
    tracked = _tracked_map()
    home = {"lat": lat, "lon": lon} if lat is not None and lon is not None else st["home"]
    m = d[d.Score >= score_min]
    if priorite: m = m[m.Priorite.isin(priorite)]
    if secteur: m = m[m.Secteur.isin(secteur)]
    if quartier: m = m[m.Quartier.isin(quartier)]
    if note_min: m = m[m.Note.fillna(0).astype(float) >= note_min]
    if avec_site: m = m[m.Site_web.notna()]
    if q: m = m[(m.Entreprise.str.contains(q, case=False, na=False)) | (m.Secteur.str.contains(q, case=False, na=False))
                | (m.Requetes_sources.fillna("").str.contains(q, case=False)) | (m.Domaine.fillna("").str.contains(q, case=False))]
    if favorites_only: m = m[m.ID.isin(st["favorites"])]
    if suivi == "oui": m = m[m.ID.isin(tracked)]
    elif suivi == "non": m = m[~m.ID.isin(tracked)]
    items = [co.to_item(r, prof, set(st["favorites"]), tracked, home) for _, r in m.iterrows()]
    if dmax is not None and home:
        items = [i for i in items if i["distance_km"] is not None and i["distance_km"] <= dmax]
    keys = {
        "score": lambda i: -i["score"], "note": lambda i: -(i["note"] or 0), "avis": lambda i: -(i["nb_avis"] or 0),
        "nom": lambda i: i["short"].lower(), "match": lambda i: -(i["match"] if i["match"] is not None else -1),
        "distance": lambda i: (i["distance_km"] is None, i["distance_km"] or 0),
    }
    items.sort(key=keys.get(sort, keys["score"]))
    total = len(items)
    return {"total": total, "items": items[offset: offset + limit]}


@app.post("/api/companies/{cid}/contact-emails")
def discover_company_emails(cid: str):
    company = _company_row(cid)
    site_url = company.get("Site_web")
    if not site_url:
        raise HTTPException(404, "Aucun site web officiel n'est enregistré pour cette entreprise.")
    try:
        matches = email_discovery.find_public_emails(str(site_url))
    except email_discovery.EmailDiscoveryError as ex:
        raise HTTPException(502, str(ex)) from ex
    return {"site": str(site_url), "emails": matches}


@app.get("/api/companies/{cid}")
def get_company(cid: str):
    it = _item(cid)
    d = co.companies_df()
    sim = d[(d.Secteur == it["secteur"]) & (d.ID != cid)].sort_values("Score", ascending=False).head(4)
    st = S.load_state()
    prof, tr = S.load_profile(), _tracked_map()
    similar = [co.to_item(r, prof, set(st["favorites"]), tr, st["home"]) for _, r in sim.iterrows()]
    t = tr.get(cid)
    return {**it, "similar": similar, "suivi": _track_out(t) if t else None}


# ---------- favoris ----------
@app.post("/api/favorites/{cid}")
def toggle_favorite(cid: str):
    _company_row(cid)
    st = S.load_state()
    if cid in st["favorites"]:
        st["favorites"].remove(cid)
    else:
        st["favorites"].append(cid)
    S.save_state(st)
    return {"favorites": st["favorites"], "favorite": cid in st["favorites"]}


@app.get("/api/favorites")
def get_favorites():
    return {"favorites": S.load_state()["favorites"]}


# ---------- suivi / candidatures ----------
class TrackIn(BaseModel):
    company_id: Optional[str] = None
    entreprise: Optional[str] = None
    secteur: str = ""
    poste: str = ""
    source: str = ""
    lien_offre: str = ""
    email: str = ""
    statut: str = "Brouillon"
    remarque: str = ""


class TrackPatch(BaseModel):
    statut: Optional[str] = None
    poste: Optional[str] = None
    email: Optional[str] = None
    lien_offre: Optional[str] = None
    date_candidature: Optional[str] = None
    date_relance: Optional[str] = None
    date_entretien: Optional[str] = None
    remarque: Optional[str] = None
    source: Optional[str] = None


class ConfirmationTokenIn(BaseModel):
    token: str = Field(min_length=40, max_length=100)


def _check_statut(s: str):
    s = C.LEGACY_STATUTS.get(s, s)
    if s not in C.STATUTS:
        raise HTTPException(400, f"Statut invalide : {s}")
    return s


def _record_status_change(tracking_id: str, old_status: str, new_status: str, source: str, details: str = ""):
    accounts.record_status_event(
        C.current_user_id(),
        tracking_id,
        old_status,
        new_status,
        source,
        details,
        datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


@app.get("/api/tracking")
def get_tracking():
    d = S.load_tracking()
    items = [_track_out(r) for r in d.to_dict("records")]
    due = [i for i in items if i["relance_due"]]
    counts = {s: 0 for s in C.STATUTS}
    for i in items:
        counts[i["statut"]] = counts.get(i["statut"], 0) + 1
    return {"items": items, "counts": counts, "relances_dues": due}


@app.post("/api/tracking")
def add_tracking(b: TrackIn):
    statut = _check_statut(b.statut)
    d = S.load_tracking()
    row = {c: "" for c in C.COLS}
    if b.company_id:
        c = _company_row(b.company_id)
        if (d.ID == c.ID).any():
            raise HTTPException(409, "Déjà dans le suivi")
        row.update(ID=c.ID, Entreprise=c.Entreprise, Secteur=c.Secteur, Source="Google Maps",
                   Poste_visé=b.poste or "Stage PFE / Data-IT")
    else:
        if not (b.entreprise or "").strip():
            raise HTTPException(400, "Nom de l'entreprise requis")
        n = 1 + sum(1 for i in d.ID if i.startswith("EXT-"))
        row.update(ID=f"EXT-{n:03d}", Entreprise=b.entreprise.strip(), Secteur=b.secteur, Poste_visé=b.poste,
                   Source=b.source or "Autre")
        while (d.ID == row["ID"]).any():
            n += 1; row["ID"] = f"EXT-{n:03d}"
    row.update(
        Lien_offre=b.lien_offre, Email_contact=b.email, Statut=statut, Remarque=b.remarque,
        Date_modification=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    d.loc[len(d)] = row
    S.save_tracking(d)
    _record_status_change(row["ID"], "", statut, "manual", "Candidature ajoutée au suivi.")
    return _track_out(row)


@app.patch("/api/tracking/{tid}")
def patch_tracking(tid: str, b: TrackPatch):
    d = S.load_tracking()
    idx = d.index[d.ID == tid]
    if len(idx) == 0:
        raise HTTPException(404, "Candidature introuvable")
    mapping = {"statut": "Statut", "poste": "Poste_visé", "email": "Email_contact", "lien_offre": "Lien_offre",
               "date_candidature": "Date_candidature", "date_relance": "Date_relance", "date_entretien": "Date_entretien",
               "remarque": "Remarque", "source": "Source"}
    data = b.model_dump(exclude_none=True)
    if "statut" in data:
        data["statut"] = _check_statut(data["statut"])
    old_status = str(d.loc[idx[0], "Statut"])
    for k, v in data.items():
        d.loc[idx[0], mapping[k]] = v
    if data.get("statut") == "Candidature envoyée" and not d.loc[idx[0], "Date_candidature"]:
        d.loc[idx[0], "Date_candidature"] = str(date.today())
        if not d.loc[idx[0], "Date_relance"]:
            d.loc[idx[0], "Date_relance"] = S.default_relance(str(date.today()))
    d.loc[idx[0], "Date_modification"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    S.save_tracking(d)
    if "statut" in data:
        _record_status_change(tid, old_status, str(d.loc[idx[0], "Statut"]), "manual")
    return _track_out(d.loc[idx[0]].to_dict())


@app.delete("/api/tracking/{tid}")
def delete_tracking(tid: str):
    d = S.load_tracking()
    if not (d.ID == tid).any():
        raise HTTPException(404, "Candidature introuvable")
    f = d.loc[d.ID == tid, "Fichier_CV"].iloc[0]
    S.save_tracking(d[d.ID != tid])
    if f and (C.user_path(C.CV_SENT_DIR) / f).exists():
        (C.user_path(C.CV_SENT_DIR) / f).unlink()
    return {"ok": True}


@app.post("/api/tracking/apply")
def apply(entreprise: str = Form(...), poste: str = Form(""), date_candidature: str = Form(""),
          statut: str = Form("À envoyer"), company_id: str = Form(""), email: str = Form(""),
          cv_id: str = Form(""), lien_offre: str = Form(""), file: Optional[UploadFile] = File(None)):
    """Prépare une candidature avec un CV; l'utilisateur confirme lui-même l'envoi externe."""
    statut = _check_statut(statut)
    ent = entreprise.strip()
    if not ent:
        raise HTTPException(400, "Indique le nom de l'entreprise")
    dc = date_candidature or ("" if statut in C.STATUTS_NON_ENVOYES else str(date.today()))
    d = S.load_tracking()
    existe = d.index[(d.ID == company_id) if company_id else (d.Entreprise == ent)]
    sent_dir = C.user_path(C.CV_SENT_DIR)
    sent_dir.mkdir(parents=True, exist_ok=True)  # absent pour les comptes créés après le premier
    uid = uuid.uuid4().hex[:6]  # nom unique : deux candidatures ne partagent jamais le même fichier
    fname = ""
    if file is not None and file.filename:
        fname, _ = _save_upload(file, sent_dir, f"{uid}_{ent}_{dc}")
        # Le CV importé depuis « Postuler » est aussi conservé dans la bibliothèque de l'utilisateur.
        _add_cv_to_library(sent_dir / fname, file.filename)
    elif cv_id:
        cv = next((c for c in S.load_state()["cvs"] if c["id"] == cv_id), None)
        if not cv:
            raise HTTPException(404, "CV introuvable : choisis un autre CV ou importe-le à nouveau.")
        source = C.user_path(C.CV_LIB_DIR) / cv["file"]
        if not source.is_file():
            raise HTTPException(404, "Le fichier de ce CV n'existe plus sur le serveur. Importe-le à nouveau.")
        ext = cv["file"].rsplit(".", 1)[-1]
        fname = f"{S.sanitize(f'{uid}_{ent}_{dc}')}.{ext}"
        (sent_dir / fname).write_bytes(source.read_bytes())
    else:
        raise HTTPException(400, "Importe ton fichier CV avant d'enregistrer")
    relance = S.default_relance(dc) if statut in C.STATUTS_RELANCE else ""
    transition = None
    if len(existe):
        i = existe[0]
        old_status = str(d.loc[i, "Statut"])
        old_date = str(d.loc[i, "Date_candidature"])
        previous_cv = str(d.loc[i, "Fichier_CV"] or "")
        if previous_cv and previous_cv != fname and not (d.Fichier_CV.eq(previous_cv).sum() > 1):
            (sent_dir / previous_cv).unlink(missing_ok=True)
        d.loc[i, ["Poste_visé", "Date_candidature", "Fichier_CV", "Statut"]] = [poste or d.loc[i, "Poste_visé"], dc, fname, statut]
        d.loc[i, "Date_modification"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if lien_offre:
            d.loc[i, "Lien_offre"] = lien_offre
        if statut in C.STATUTS_NON_ENVOYES:
            d.loc[i, "Date_relance"] = ""
        elif statut in C.STATUTS_RELANCE and (dc != old_date or not d.loc[i, "Date_relance"]):
            d.loc[i, "Date_relance"] = relance
        elif statut not in C.STATUTS_RELANCE:
            d.loc[i, "Date_relance"] = ""
        if email: d.loc[i, "Email_contact"] = email
        tid = d.loc[i, "ID"]
        transition = (str(tid), old_status, statut)
    else:
        row = {c: "" for c in C.COLS}
        if company_id:
            c = _company_row(company_id)
            row.update(ID=c.ID, Secteur=c.Secteur, Source="Google Maps", Lien_offre=lien_offre)
        else:
            n = len(d) + 1
            while (d.ID == f"CV-{n:03d}").any():
                n += 1
            row.update(ID=f"CV-{n:03d}", Source="Candidature directe", Lien_offre=lien_offre)
        row.update(Entreprise=ent, Poste_visé=poste, Date_candidature=dc, Date_relance=relance, Fichier_CV=fname,
                   Statut=statut, Email_contact=email,
                   Date_modification=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        d.loc[len(d)] = row
        tid = row["ID"]
        transition = (tid, "", statut)
    S.save_tracking(d)
    if transition:
        _record_status_change(*transition, "manual", "Dossier de candidature préparé.")
    return _track_out(d[d.ID == tid].iloc[0].to_dict())


@app.post("/api/tracking/{tid}/send")
def request_application_confirmation(
    tid: str,
    recipient: str = Form(...),
    subject: str = Form(...),
    body: str = Form(...),
    cover_letter: str = Form(""),
    offer_title: str = Form(""),
    offer_url: str = Form(""),
    offer_description: str = Form(""),
    cover_letter_file: Optional[UploadFile] = File(None),
):
    email_status = gmail.status()
    if not email_status["configured"]:
        raise HTTPException(503, "La connexion Google OAuth n'est pas configurée sur le serveur.")
    if not email_status["connected"]:
        raise HTTPException(503, "Connecte ton compte Gmail avec Google avant l'envoi.")
    if not email_status.get("draft_authorized"):
        raise HTTPException(
            503,
            "Reconnecte Gmail et autorise la création de brouillons pour préparer l'envoi.",
        )
    recipient = recipient.strip()
    subject = subject.strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", recipient):
        raise HTTPException(400, "Adresse e-mail destinataire invalide")
    if not subject or "\r" in subject or "\n" in subject:
        raise HTTPException(400, "Objet d'e-mail invalide")
    if len(body) > 20000 or len(cover_letter) > 20000 or len(offer_description) > 30000:
        raise HTTPException(413, "Le message ou le texte de l'offre dépasse la taille autorisée.")
    if len(offer_title) > 300 or len(offer_url) > 2000 or "\r" in offer_url or "\n" in offer_url:
        raise HTTPException(400, "Le titre ou le lien de l'offre est invalide.")
    if offer_url and not re.fullmatch(r"https?://[^\s]+", offer_url):
        raise HTTPException(400, "Le lien de l'offre doit commencer par http:// ou https://.")
    if not body.strip() or (not cover_letter.strip() and not (cover_letter_file and cover_letter_file.filename)):
        raise HTTPException(400, "Le message et une lettre de motivation (texte ou fichier) sont obligatoires.")

    with _EMAIL_LOCK:
        d = S.load_tracking()
        matches = d.index[d.ID == tid]
        if len(matches) == 0:
            raise HTTPException(404, "Candidature introuvable")
        index = matches[0]
        row = d.loc[index]
        row_status = _check_statut(str(row["Statut"]))
        d.loc[index, "Statut"] = row_status
        if row_status not in C.STATUTS_NON_ENVOYES:
            raise HTTPException(409, "Cette candidature n'est plus un brouillon et ne peut pas être envoyée à nouveau")
        if not row["Fichier_CV"]:
            raise HTTPException(400, "Ajoute un CV à la candidature avant l'envoi")
        attachment = _safe(C.user_path(C.CV_SENT_DIR), row["Fichier_CV"])
        letter_filename = ""
        if cover_letter_file is not None and cover_letter_file.filename:
            letter_filename, _ = _save_upload(cover_letter_file, C.user_path(C.CV_SENT_DIR), f"{tid}_lettre")

        company_info = {
            "name": str(row["Entreprise"]),
            "sector": str(row["Secteur"]),
            "category": "",
            "address": "",
            "website": "",
            "source": "Suivi BookJob",
        }
        company_rows = co.companies_df()
        company_matches = company_rows[company_rows.ID == tid]
        if not company_matches.empty:
            company_row = company_matches.iloc[0]
            company_info.update(
                category=str(company_row.get("Categorie") or ""),
                address=str(company_row.get("Adresse") or ""),
                website=str(company_row.get("Site_web") or ""),
                source="Fiche entreprise importée dans BookJob",
            )
        profile = S.load_profile()
        match_report = matching.match_profile_to_offer(
            profile,
            offer_title or str(row["Poste_visé"]),
            offer_description,
        )
        token = secrets.token_urlsafe(36)
        token_hash = email_confirmations.token_digest(token)
        created_at = time.time()
        confirm_url = f"{C.BOOKJOB_PUBLIC_URL}/api/email/confirm#{token}"
        pending_request = {
            "tracking_id": tid,
            "sender": email_status["sender"],
            "recipient": recipient,
            "cv_filename": row["Fichier_CV"],
            "subject": subject,
            "body": body.strip(),
            "cover_letter": cover_letter.strip(),
            "cover_letter_file": letter_filename,
            "company": company_info,
            "offer_title": offer_title.strip() or str(row["Poste_visé"]),
            "offer_url": offer_url.strip(),
            "offer_description": offer_description.strip(),
            "match": match_report,
            "created_at": created_at,
            "expires_at": created_at + C.EMAIL_CONFIRMATION_TTL_SECONDS,
        }
        try:
            draft = _application_email_message(email_status["sender"], {
                **pending_request,
                "cv_filename": row["Fichier_CV"],
            })
            draft_id = gmail.create_draft(draft)
        except gmail.GmailError as ex:
            if letter_filename:
                (C.user_path(C.CV_SENT_DIR) / letter_filename).unlink(missing_ok=True)
            raise HTTPException(502, "Le brouillon Gmail n'a pas pu être créé. " + str(ex)) from ex
        except HTTPException:
            if letter_filename:
                (C.user_path(C.CV_SENT_DIR) / letter_filename).unlink(missing_ok=True)
            raise
        pending_request["cv_filename"] = row["Fichier_CV"]
        pending_request["gmail_draft_id"] = draft_id
        try:
            pending = email_confirmations.load(C.user_path(C.EMAIL_CONFIRMATIONS_FILE))
            pending = {
                key: value for key, value in pending.items()
                if float(value.get("expires_at", 0)) > created_at and value.get("tracking_id") != tid
            }
            pending[token_hash] = pending_request
            email_confirmations.save(C.user_path(C.EMAIL_CONFIRMATIONS_FILE), pending)
            if C.current_user_id():
                accounts.add_confirmation_owner(
                    token_hash, C.current_user_id(), int(pending_request["expires_at"]),
                )
        except (email_confirmations.ConfirmationStoreError, ValueError, TypeError) as ex:
            try:
                gmail.delete_draft(draft_id)
            except gmail.GmailError as cleanup_error:
                raise HTTPException(
                    500,
                    "Impossible d'enregistrer la confirmation. Le brouillon Gmail existe toujours : "
                    + str(cleanup_error),
                ) from ex
            if letter_filename:
                (C.user_path(C.CV_SENT_DIR) / letter_filename).unlink(missing_ok=True)
            raise HTTPException(500, "Impossible de préparer le lien sécurisé de confirmation.") from ex

        company_lines = [
            f"Entreprise : {company_info['name']}",
            f"Secteur : {company_info['sector'] or 'non précisé'}",
            f"Activité/catégorie déclarée : {company_info['category'] or 'non fournie dans les données BookJob'}",
            f"Adresse : {company_info['address'] or 'non fournie'}",
            f"Site web : {company_info['website'] or 'non fourni'}",
            f"Source entreprise : {company_info['source']}",
        ]
        if match_report["score"] is None:
            match_lines = [match_report["explanation"]]
        else:
            match_lines = [
                f"Correspondance textuelle indicative : {match_report['score']} %",
                match_report["explanation"],
                "Compétences de ton profil citées dans l'offre : "
                + (", ".join(match_report["matched_skills"]) or "aucune"),
                "Compétences du profil non mentionnées dans le texte : "
                + (", ".join(match_report["unmentioned_skills"]) or "aucune"),
            ]
        offer_lines = [
            f"Offre/poste : {pending_request['offer_title']}",
            f"Lien de l'offre : {pending_request['offer_url'] or 'non fourni'}",
            "Texte de l'offre :",
            pending_request["offer_description"] or "Aucun texte d'offre fourni : il s'agit d'une candidature spontanée.",
        ]
        preview_text = (
            "Une demande de candidature attend ta confirmation.\n\n"
            f"Destinataire prévu : {recipient}\nObjet prévu : {subject}\n\n"
            + "\n".join(company_lines)
            + "\n\n" + "\n".join(offer_lines)
            + "\n\n" + "\n".join(match_lines)
            + "\n\nMessage qui sera envoyé :\n" + body.strip()
            + "\n\nLettre : " + (cover_letter.strip() or f"Fichier joint : {letter_filename}")
            + f"\n\nCV joint : {row['Fichier_CV']}"
            + "\n\nVérifie le brouillon dans Gmail sans l'envoyer ni le modifier."
            + f"\n\nPour envoyer la candidature à l'entreprise, confirme ici (valable 20 minutes) :\n{confirm_url}"
            + "\nSi tu n'es pas à l'origine de cette demande, ignore ce message."
        )
        html_items = "".join(f"<li>{escape(line)}</li>" for line in company_lines)
        match_html = "".join(f"<li>{escape(line)}</li>" for line in match_lines)
        offer_html = (
            f"<p><strong>Offre/poste :</strong> {escape(pending_request['offer_title'])}</p>"
            f"<p><strong>Source de l'offre :</strong> "
            f"<a href=\"{escape(pending_request['offer_url'], quote=True)}\">"
            f"{escape(pending_request['offer_url'] or 'non fournie')}</a></p>"
            f"<p><strong>Description saisie :</strong><br>{escape(pending_request['offer_description'] or 'Aucun texte d’offre fourni : candidature spontanée.').replace(chr(10), '<br>')}</p>"
        )
        preview_message = EmailMessage()
        try:
            preview_message["From"] = email_status["sender"]
            preview_message["To"] = email_status["sender"]
            preview_message["Subject"] = f"À confirmer : {subject}"
        except ValueError as ex:
            if letter_filename:
                (C.user_path(C.CV_SENT_DIR) / letter_filename).unlink(missing_ok=True)
            raise HTTPException(400, "Adresse ou objet d'e-mail invalide") from ex
        preview_message.set_content(preview_text)
        preview_message.add_alternative(
            f"""<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="referrer" content="no-referrer">
            <body><h1>Confirme ta candidature avant l'envoi</h1>
            <p>Le CV et la lettre ne seront transmis à l'entreprise qu'après ton clic sur le bouton ci-dessous.</p>
            <p><strong>Destinataire prévu :</strong> {escape(recipient)}<br>
            <strong>Objet :</strong> {escape(subject)}</p>
            <h2>Informations disponibles sur l'entreprise</h2><ul>{html_items}</ul>
            <h2>Offre et matching avec ton profil</h2>{offer_html}<ul>{match_html}</ul>
            <h2>Message prévu</h2><pre>{escape(body.strip())}</pre>
            <p><strong>Pièces jointes prévues :</strong> CV {escape(str(row["Fichier_CV"]))};
            lettre {escape(letter_filename or 'lettre_motivation.txt')}.</p>
            <p>Vérifie le brouillon dans Gmail sans l'envoyer ni le modifier.</p>
            <p><a href="{escape(confirm_url, quote=True)}">Vérifier puis confirmer l'envoi à l'entreprise</a></p>
            <p>Ce lien expire dans 20 minutes. Si tu n'as pas demandé cette candidature, ignore cet e-mail.</p>
            </body></html>""",
            subtype="html",
        )
        mime_type, _ = mimetypes.guess_type(attachment.name)
        maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
        preview_message.add_attachment(
            attachment.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=attachment.name,
        )
        if letter_filename:
            letter_attachment = _safe(C.user_path(C.CV_SENT_DIR), letter_filename)
            letter_type, _ = mimetypes.guess_type(letter_attachment.name)
            letter_main, letter_sub = (letter_type or "application/octet-stream").split("/", 1)
            preview_message.add_attachment(
                letter_attachment.read_bytes(),
                maintype=letter_main,
                subtype=letter_sub,
                filename=letter_attachment.name,
            )
        elif cover_letter.strip():
            preview_message.add_attachment(
                cover_letter.strip(),
                subtype="plain",
                charset="utf-8",
                filename="lettre_motivation.txt",
            )

        try:
            gmail.send(preview_message)
        except gmail.GmailError as ex:
            cleanup_error = ""
            try:
                pending = email_confirmations.load(C.user_path(C.EMAIL_CONFIRMATIONS_FILE))
                pending.pop(token_hash, None)
                email_confirmations.save(C.user_path(C.EMAIL_CONFIRMATIONS_FILE), pending)
                accounts.remove_confirmation_owner(token_hash)
            except email_confirmations.ConfirmationStoreError as cleanup_ex:
                cleanup_error = f" La confirmation temporaire n'a pas pu être supprimée : {cleanup_ex}"
            try:
                gmail.delete_draft(draft_id)
            except gmail.GmailError as cleanup_ex:
                cleanup_error += f" Le brouillon Gmail n'a pas pu être supprimé : {cleanup_ex}"
            if letter_filename:
                (C.user_path(C.CV_SENT_DIR) / letter_filename).unlink(missing_ok=True)
            raise HTTPException(
                502,
                "L'e-mail de prévisualisation n'a pas pu être envoyé. " + str(ex) + cleanup_error,
            ) from ex

        d.loc[index, "Email_contact"] = recipient
        if offer_url:
            d.loc[index, "Lien_offre"] = offer_url
        S.save_tracking(d)
        return {
            "ok": True,
            "confirmation_required": True,
            "sender": email_status["sender"],
            "expires_at": pending_request["expires_at"],
        }


@app.get("/api/email/confirm")
def show_email_confirmation():
    nonce = secrets.token_urlsafe(18)
    return HTMLResponse(
        f"""<!doctype html><html lang="fr"><meta charset="utf-8">
        <meta name="referrer" content="no-referrer"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>BookJob — Confirmer une candidature</title>
        <style>body{{font:16px system-ui;max-width:760px;margin:4rem auto;padding:0 1rem;color:#17233b}}
        pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f6f8;padding:1rem}}
        button{{padding:.8rem 1rem;cursor:pointer}}</style>
        <main><h1>BookJob — Vérifier ta candidature</h1>
        <p>Rien ne sera envoyé à l'entreprise avant ton clic sur le bouton ci-dessous.</p>
        <div id="details">Chargement de la prévisualisation…</div>
        <p id="error" role="alert"></p>
        <button id="confirm" type="button" disabled>Confirmer et envoyer maintenant</button>
        </main>
        <script nonce="{nonce}">
        const token = window.location.hash.slice(1);
        history.replaceState(null, document.title, window.location.pathname);
        const errorBox = document.getElementById("error");
        const button = document.getElementById("confirm");
        const detailsBox = document.getElementById("details");
        const addText = (parent, label, value) => {{
          const p = document.createElement("p");
          const strong = document.createElement("strong");
          strong.textContent = label;
          p.append(strong, document.createTextNode(" " + (value || "non fourni")));
          parent.appendChild(p);
        }};
        const renderDetails = (data) => {{
          detailsBox.replaceChildren();
          addText(detailsBox, "Entreprise :", data.company.name);
          addText(detailsBox, "Destinataire :", data.recipient);
          addText(detailsBox, "Objet :", data.subject);
          addText(detailsBox, "Poste/offre :", data.offer_title);
          addText(detailsBox, "Matching textuel indicatif :", data.match.score === null ? data.match.explanation : data.match.score + " % — " + data.match.explanation);
          addText(detailsBox, "Compétences citées :", data.match.matched_skills.join(", ") || "aucune");
          addText(detailsBox, "Compétences non citées :", data.match.unmentioned_skills.join(", ") || "aucune");
          addText(detailsBox, "Pièces jointes :", data.attachments.join(", "));
          for (const [label, value] of [["Description de l'offre :", data.offer_description], ["Message envoyé :", data.body]]) {{
            const heading = document.createElement("h2");
            heading.textContent = label;
            const pre = document.createElement("pre");
            pre.textContent = value || "non fourni";
            detailsBox.append(heading, pre);
          }}
          button.disabled = false;
        }};
        const callApi = async (path, method) => {{
          const response = await fetch(path, {{
            method, headers: {{"Content-Type": "application/json", "X-BookJob-Confirmation-Token": token}},
            body: JSON.stringify({{token}})
          }});
          const data = await response.json();
          if (!response.ok) throw new Error(data.detail || "La demande a échoué.");
          return data;
        }};
        if (!token) {{
          errorBox.textContent = "Le lien ne contient pas de jeton de confirmation.";
          detailsBox.textContent = "";
        }} else {{
          callApi("/api/email/confirm/details", "POST")
            .then(renderDetails)
            .catch((error) => {{ errorBox.textContent = error.message; detailsBox.textContent = ""; }});
        }}
        button.addEventListener("click", async () => {{
          button.disabled = true;
          errorBox.textContent = "";
          try {{
            const result = await callApi("/api/email/confirm", "POST");
            detailsBox.textContent = result.message;
            button.hidden = true;
          }} catch (error) {{
            errorBox.textContent = error.message;
            button.disabled = false;
          }}
        }});
        </script></html>""",
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": f"default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-{nonce}'; connect-src 'self'",
        },
    )


def _get_pending_confirmation(token: str) -> tuple[str, dict, dict]:
    token_hash = email_confirmations.token_digest(token)
    try:
        pending = email_confirmations.load(C.user_path(C.EMAIL_CONFIRMATIONS_FILE))
    except email_confirmations.ConfirmationStoreError as ex:
        raise HTTPException(500, str(ex)) from ex
    request_data = pending.get(token_hash)
    if not request_data:
        raise HTTPException(404, "Ce lien a déjà été utilisé ou n'existe pas.")
    if float(request_data.get("expires_at", 0)) <= time.time():
        try:
            gmail.delete_draft(request_data.get("gmail_draft_id", ""))
        except gmail.GmailError as ex:
            raise HTTPException(
                502,
                "Le lien a expiré, mais le brouillon Gmail n'a pas pu être supprimé. " + str(ex),
            ) from ex
        pending.pop(token_hash, None)
        try:
            email_confirmations.save(C.user_path(C.EMAIL_CONFIRMATIONS_FILE), pending)
        except email_confirmations.ConfirmationStoreError as ex:
            raise HTTPException(500, str(ex)) from ex
        accounts.remove_confirmation_owner(token_hash)
        raise HTTPException(410, "Ce lien a expiré. Demande une nouvelle prévisualisation dans BookJob.")
    if request_data.get("sending"):
        raise HTTPException(409, "Cette confirmation est déjà en cours. Vérifie ta boîte Envoyés avant de réessayer.")
    return token_hash, request_data, pending


@app.post("/api/email/confirm/details")
def email_confirmation_details(body: ConfirmationTokenIn):
    with _EMAIL_LOCK:
        _token_hash, request_data, _pending = _get_pending_confirmation(body.token)
        return {
            "company": request_data["company"],
            "recipient": request_data["recipient"],
            "subject": request_data["subject"],
            "offer_title": request_data["offer_title"],
            "offer_description": request_data["offer_description"],
            "body": request_data["body"],
            "match": request_data["match"],
            "attachments": [
                request_data.get("cv_filename", ""),
                request_data.get("cover_letter_file") or "lettre_motivation.txt",
            ],
        }


@app.post("/api/email/confirm")
def confirm_email_application(body: ConfirmationTokenIn):
    with _EMAIL_LOCK:
        token_hash, request_data, pending = _get_pending_confirmation(body.token)
        request_data["sending"] = True
        try:
            email_confirmations.save(C.user_path(C.EMAIL_CONFIRMATIONS_FILE), pending)
        except email_confirmations.ConfirmationStoreError as ex:
            raise HTTPException(500, str(ex)) from ex
        email_status = gmail.status()
        if not email_status["connected"] or email_status["sender"].casefold() != request_data["sender"].casefold():
            request_data.pop("sending", None)
            try:
                email_confirmations.save(C.user_path(C.EMAIL_CONFIRMATIONS_FILE), pending)
            except email_confirmations.ConfirmationStoreError as ex:
                raise HTTPException(500, str(ex)) from ex
            raise HTTPException(403, "Reconnecte le compte Gmail qui a reçu la prévisualisation.")
        d = S.load_tracking()
        matches = d.index[d.ID == request_data["tracking_id"]]
        if len(matches) == 0:
            pending.pop(token_hash, None)
            try:
                email_confirmations.save(C.user_path(C.EMAIL_CONFIRMATIONS_FILE), pending)
            except email_confirmations.ConfirmationStoreError as ex:
                raise HTTPException(500, str(ex)) from ex
            raise HTTPException(404, "Cette candidature n'existe plus.")
        index = matches[0]
        row = d.loc[index]
        row_status = _check_statut(str(row["Statut"]))
        d.loc[index, "Statut"] = row_status
        if row_status not in C.STATUTS_NON_ENVOYES:
            pending.pop(token_hash, None)
            try:
                email_confirmations.save(C.user_path(C.EMAIL_CONFIRMATIONS_FILE), pending)
            except email_confirmations.ConfirmationStoreError as ex:
                raise HTTPException(500, str(ex)) from ex
            raise HTTPException(409, "Cette candidature n'est plus un brouillon.")
        try:
            gmail.send_draft(request_data.get("gmail_draft_id", ""))
        except gmail.GmailError as ex:
            request_data.pop("sending", None)
            try:
                email_confirmations.save(C.user_path(C.EMAIL_CONFIRMATIONS_FILE), pending)
            except email_confirmations.ConfirmationStoreError as save_ex:
                raise HTTPException(
                    500,
                    f"{ex} La confirmation ne peut pas être réessayée automatiquement : {save_ex}",
                ) from save_ex
            raise HTTPException(502, str(ex)) from ex

        letter_filename = request_data.get("cover_letter_file", "")
        sent_date = str(date.today())
        old_status = str(d.loc[index, "Statut"])
        d.loc[index, ["Email_contact", "Statut", "Date_candidature", "Date_relance", "Date_modification"]] = [
            request_data["recipient"], "Candidature envoyée", sent_date, S.default_relance(sent_date),
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ]
        S.save_tracking(d)
        _record_status_change(
            str(request_data["tracking_id"]), old_status, "Candidature envoyée",
            "email_send", f"Envoi Gmail confirmé pour {request_data['recipient']}.",
        )
        pending.pop(token_hash, None)
        email_confirmations.save(C.user_path(C.EMAIL_CONFIRMATIONS_FILE), pending)
        accounts.remove_confirmation_owner(token_hash)
        if letter_filename:
            (C.user_path(C.CV_SENT_DIR) / letter_filename).unlink(missing_ok=True)
        return {
            "ok": True,
            "message": (
                f"La candidature de {request_data['company']['name']} a été envoyée à "
                f"{request_data['recipient']} avec le CV et la lettre de motivation."
            ),
        }


@app.get("/api/tracking/{tid}/send-status")
def application_send_status(tid: str):
    d = S.load_tracking()
    rows = d[d.ID == tid]
    if rows.empty:
        raise HTTPException(404, "Candidature introuvable")
    if rows.iloc[0]["Statut"] == "Candidature envoyée":
        return {"sent": True, "pending": False, "expires_at": None}
    now = time.time()
    with _EMAIL_LOCK:
        try:
            pending = email_confirmations.load(C.user_path(C.EMAIL_CONFIRMATIONS_FILE))
        except email_confirmations.ConfirmationStoreError as ex:
            raise HTTPException(500, str(ex)) from ex
        valid = [item for item in pending.values() if item.get("tracking_id") == tid
                 and float(item.get("expires_at", 0)) > now]
        return {
            "sent": False,
            "pending": bool(valid),
            "expires_at": max((item["expires_at"] for item in valid), default=None),
        }


@app.get("/api/tracking/{tid}/cv")
def download_tracking_cv(tid: str):
    d = S.load_tracking()
    m = d[d.ID == tid]
    if m.empty or not m.iloc[0]["Fichier_CV"]:
        raise HTTPException(404, "Aucun CV pour cette candidature")
    p = _safe(C.user_path(C.CV_SENT_DIR), m.iloc[0]["Fichier_CV"])
    return FileResponse(p, filename=p.name)


@app.get("/api/export/suivi.csv")
def export_suivi():
    return Response(S.load_tracking().to_csv(index=False).encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=suivi.csv"})


# ---------- profil ----------
AVATAR_MAX_BYTES = 2 * 1024 * 1024
AVATAR_MEDIA_TYPES = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}


def _avatar_dir() -> Path:
    return C.user_path(C.UPLOAD_DIR / "avatar")


def _avatar_file() -> Optional[Path]:
    folder = _avatar_dir()
    for ext in AVATAR_MEDIA_TYPES:
        candidate = folder / f"avatar.{ext}"
        if candidate.is_file():
            return candidate
    return None


def _avatar_url() -> Optional[str]:
    path = _avatar_file()
    return f"/api/profile/avatar?v={int(path.stat().st_mtime)}" if path else None


def _image_extension(data: bytes) -> Optional[str]:
    """Type réel de l'image d'après ses premiers octets (le type MIME envoyé par le navigateur n'est pas fiable)."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def _profile_payload(p: dict) -> dict:
    return {"profile": p, "completion": S.profile_completion(p), "skills": S.split_list(p["competences"]),
            "languages": S.split_list(p["langues"]), "avatar_url": _avatar_url()}


@app.get("/api/profile")
def get_profile():
    return _profile_payload(S.load_profile())


@app.put("/api/profile")
def put_profile(body: dict):
    clean = {}
    for key, value in body.items():
        if key not in C.PROFILE_FIELDS:
            continue
        if value is None:
            value = ""
        if not isinstance(value, (str, int, float)):
            raise HTTPException(422, f"Valeur invalide pour le champ « {key} ».")
        value = str(value).strip()
        if len(value) > 5000:
            raise HTTPException(422, f"Le champ « {key} » est trop long (5000 caractères maximum).")
        clean[key] = value
    p = S.save_profile({**S.load_profile(), **clean})
    return _profile_payload(p)


@app.get("/api/profile/avatar")
def get_avatar():
    path = _avatar_file()
    if not path:
        raise HTTPException(404, "Aucune photo de profil")
    return FileResponse(path, media_type=AVATAR_MEDIA_TYPES[path.suffix.lstrip(".")],
                        headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"})


@app.post("/api/profile/avatar")
def upload_avatar(file: UploadFile = File(...)):
    data = file.file.read(AVATAR_MAX_BYTES + 1)
    if len(data) > AVATAR_MAX_BYTES:
        raise HTTPException(400, "Image trop volumineuse (2 Mo maximum)")
    if not data:
        raise HTTPException(400, "Fichier vide")
    ext = _image_extension(data)
    if not ext:
        raise HTTPException(400, "Format non pris en charge : PNG, JPG ou WebP uniquement")
    folder = _avatar_dir()
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / f"avatar.{ext}.tmp"
    tmp.write_bytes(data)
    for old in AVATAR_MEDIA_TYPES:
        (folder / f"avatar.{old}").unlink(missing_ok=True)
    tmp.replace(folder / f"avatar.{ext}")
    return {"avatar_url": _avatar_url()}


@app.delete("/api/profile/avatar")
def delete_avatar():
    for ext in AVATAR_MEDIA_TYPES:
        (_avatar_dir() / f"avatar.{ext}").unlink(missing_ok=True)
    return {"avatar_url": None}


# ---------- bibliothèque de CV (CV Studio) ----------
@app.get("/api/cvs")
def list_cvs():
    return {"items": S.load_state()["cvs"]}


@app.post("/api/cvs")
def upload_cv(file: UploadFile = File(...)):
    st = S.load_state()
    cid = S.new_id("cv")
    stem = (file.filename or "cv").rsplit(".", 1)[0]
    name, size = _save_upload(file, C.user_path(C.CV_LIB_DIR), f"{cid}_{stem}")
    st["cvs"].append({"id": cid, "name": stem, "file": name, "size": size, "uploaded": str(date.today()),
                      "main": not st["cvs"]})
    S.save_state(st)
    return {"items": st["cvs"]}


@app.post("/api/cvs/{cid}/main")
def main_cv(cid: str):
    st = S.load_state()
    if not any(c["id"] == cid for c in st["cvs"]):
        raise HTTPException(404, "CV introuvable")
    for c in st["cvs"]:
        c["main"] = c["id"] == cid
    S.save_state(st)
    return {"items": st["cvs"]}


@app.delete("/api/cvs/{cid}")
def delete_cv(cid: str):
    st = S.load_state()
    cv = next((c for c in st["cvs"] if c["id"] == cid), None)
    if not cv:
        raise HTTPException(404, "CV introuvable")
    st["cvs"] = [c for c in st["cvs"] if c["id"] != cid]
    if st["cvs"] and not any(c["main"] for c in st["cvs"]):
        st["cvs"][0]["main"] = True
    S.save_state(st)
    f = C.user_path(C.CV_LIB_DIR) / cv["file"]
    if f.exists(): f.unlink()
    return {"items": st["cvs"]}


@app.get("/api/cvs/{cid}/file")
def cv_file(cid: str):
    cv = next((c for c in S.load_state()["cvs"] if c["id"] == cid), None)
    if not cv:
        raise HTTPException(404, "CV introuvable")
    p = _safe(C.user_path(C.CV_LIB_DIR), cv["file"])
    return FileResponse(p, filename=f"{cv['name']}.{p.suffix.lstrip('.')}")


# ---------- génération CV / e-mail / lettre ----------
class GenIn(BaseModel):
    company_id: Optional[str] = None
    entreprise: str = ""
    secteur: str = ""
    poste: str = ""
    offre: str = ""
    use_ai: bool = True
    ton: str = "formel"


def _gen_target(b: GenIn):
    p = S.load_profile()
    if not p["nom"]:
        raise HTTPException(400, "Remplis d'abord ton profil (nom au minimum)")
    ent, sec = b.entreprise, b.secteur
    if b.company_id:
        c = _company_row(b.company_id)
        ent, sec = c.Nom_court, c.Secteur
    return p, ent or "l'entreprise", sec, b.poste or p["titre"] or "Stage"


@app.post("/api/generate/cv")
def generate_cv(b: GenIn):
    p, ent, sec, poste = _gen_target(b)
    try:
        return ai.generer(p, ent, sec, poste, b.offre, b.use_ai)
    except ai.AIError as ex:
        raise HTTPException(502, f"Génération IA impossible ({ex}). Désactive l'IA pour utiliser le modèle simple.")


@app.post("/api/generate/letter")
def generate_letter(b: GenIn):
    p, ent, _, poste = _gen_target(b)
    try:
        return ai.lettre(p, ent, poste, b.ton, b.use_ai)
    except ai.AIError as ex:
        raise HTTPException(502, f"Génération IA impossible ({ex}). Désactive l'IA pour utiliser le modèle simple.")


# ---------- carte / localisation ----------
class GeoIn(BaseModel):
    adresse: str


class HomeIn(BaseModel):
    lat: float
    lon: float
    label: str = ""


@app.post("/api/geocode")
def geocode(b: GeoIn):
    a = b.adresse.strip()
    if not a:
        raise HTTPException(400, "Adresse vide")
    res = co.quartier_lookup(a) or co.geocode_google(a) or co.geocoder_adresse(a)
    if not res:
        raise HTTPException(404, "Adresse introuvable. Essaie un nom de quartier plus simple, ou les coordonnées GPS.")
    return {"lat": res[0], "lon": res[1], "label": a}


@app.put("/api/home")
def set_home(b: HomeIn):
    if not (-90 <= b.lat <= 90 and -180 <= b.lon <= 180):
        raise HTTPException(400, "Coordonnées invalides")
    st = S.load_state()
    st["home"] = b.model_dump()
    S.save_state(st)
    return {"home": st["home"]}


@app.delete("/api/home")
def clear_home():
    st = S.load_state(); st["home"] = None; S.save_state(st)
    return {"home": None}


@app.get("/api/home")
def get_home():
    return {"home": S.load_state()["home"]}


@app.post("/api/geocode/companies")
def geocode_all():
    r = co.geocode_companies_google()
    if not r["ok"]:
        raise HTTPException(400, r["detail"])
    return r


# ---------- assistant ----------
class ChatIn(BaseModel):
    chat_id: Optional[str] = None
    message: str
    company_id: Optional[str] = None
    use_profile: bool = True


@app.get("/api/chats")
def get_chats():
    return {"items": S.load_state()["chats"]}


@app.post("/api/chats")
def new_chat():
    st = S.load_state()
    ch = {"id": S.new_id("ch"), "title": "Nouvelle conversation", "messages": []}
    st["chats"].insert(0, ch)
    S.save_state(st)
    return ch


@app.delete("/api/chats/{chid}")
def delete_chat(chid: str):
    st = S.load_state()
    st["chats"] = [c for c in st["chats"] if c["id"] != chid]
    S.save_state(st)
    return {"items": st["chats"]}


@app.post("/api/chat")
def chat(b: ChatIn):
    msg = b.message.strip()
    if not msg:
        raise HTTPException(400, "Message vide")
    st = S.load_state()
    ch = next((c for c in st["chats"] if c["id"] == b.chat_id), None)
    if ch is None:
        ch = {"id": S.new_id("ch"), "title": "Nouvelle conversation", "messages": []}
        st["chats"].insert(0, ch)
    if ch["title"] == "Nouvelle conversation":
        ch["title"] = msg[:38]
    ch["messages"].append({"id": S.new_id("m"), "role": "user", "content": msg})
    company = _item(b.company_id) if b.company_id else None
    history = [{"role": "assistant" if m["role"] == "ai" else "user", "content": m["content"]} for m in ch["messages"]]
    try:
        r = ai.chat(history, company, S.load_profile(), b.use_profile)
        reply, mode = r["reply"], r["mode"]
    except ai.AIError as ex:
        reply, mode = f"L'assistant IA est indisponible pour le moment ({ex}).", "erreur"
    ch["messages"].append({"id": S.new_id("m"), "role": "ai", "content": reply, "mode": mode})
    S.save_state(st)
    return {"chat": ch, "mode": mode}


# ---------- alertes / réglages ----------
class AlertIn(BaseModel):
    query: str


@app.get("/api/alerts")
def get_alerts():
    return {"items": S.load_state()["alerts"]}


@app.post("/api/alerts")
def add_alert(b: AlertIn):
    st = S.load_state()
    st["alerts"].append({"id": S.new_id("al"), "query": b.query.strip() or "Toutes les entreprises"})
    S.save_state(st)
    return {"items": st["alerts"]}


@app.delete("/api/alerts/{aid}")
def del_alert(aid: str):
    st = S.load_state()
    st["alerts"] = [a for a in st["alerts"] if a["id"] != aid]
    S.save_state(st)
    return {"items": st["alerts"]}


@app.get("/api/settings")
def get_settings():
    return S.load_state()["settings"]


@app.put("/api/settings")
def put_settings(body: dict):
    st = S.load_state()
    st["settings"].update({k: v for k, v in body.items() if k in S.DEFAULT_STATE["settings"]})
    S.save_state(st)
    return st["settings"]


# ---------- tableau de bord / notifications ----------
@app.get("/api/dashboard")
def dashboard():
    d = S.load_tracking()
    cdf = co.companies_df()
    prof = S.load_profile()
    st = S.load_state()
    tr = get_tracking()
    sent = int((~d.Statut.replace("", "Brouillon").isin(C.STATUTS_NON_ENVOYES)).sum()) if len(d) else 0
    sec = cdf.groupby("Secteur").Score.agg(["mean", "count"]).reset_index()
    today = str(date.today())
    interviews = [
        _track_out(r) for _, r in d.iterrows()
        if r["Statut"] == "Entretien programmé" and r["Date_entretien"] and r["Date_entretien"] >= today
    ]
    interviews.sort(key=lambda i: i["date_entretien"])
    top = []
    if prof["competences"].strip():
        tracked = _tracked_map()
        its = [co.to_item(r, prof, set(st["favorites"]), tracked, st["home"]) for _, r in cdf.iterrows()]
        top = sorted(its, key=lambda i: (-(i["match"] or 0), -i["score"]))[:3]
    else:
        tracked = _tracked_map()
        top = [co.to_item(r, prof, set(st["favorites"]), tracked, st["home"]) for _, r in cdf.sort_values("Score", ascending=False).head(3).iterrows()]
    recent = [i for i in tr["items"] if i["statut"] not in C.STATUTS_NON_ENVOYES][-5:][::-1]
    return {
        "kpis": {"suivies": int(len(d)), "envoyees": sent,
                 "entretiens": int(d.Statut.isin(["Entretien programmé", "Acceptée"]).sum()) if len(d) else 0,
                 "reponses": int(d.Statut.isin(["En cours de traitement", "Entretien programmé", "Acceptée", "Refusée"]).sum()) if len(d) else 0,
                 "favoris": len(st["favorites"]), "relances": len(tr["relances_dues"])},
        "par_statut": tr["counts"],
        "par_secteur": cdf.Secteur.value_counts().to_dict(),
        "score_moyen_secteur": {r.Secteur: round(float(r["mean"]), 1) for _, r in sec.iterrows()},
        "recommandees": top, "recentes": recent, "relances_dues": tr["relances_dues"],
        "profil": S.profile_completion(prof), "nom": prof["nom"],
        "nb_cv": len(st["cvs"]), "entretiens_a_venir": interviews,
    }


@app.get("/api/notifications")
def notifications():
    tr = get_tracking()
    out = [{"id": f"r-{i['id']}", "text": f"Relance à faire : {i['short']} (prévue le {i['date_relance']})", "link": "/candidatures"}
           for i in tr["relances_dues"]]
    n_contact = tr["counts"].get("Brouillon", 0)
    if n_contact:
        out.append({"id": "contact", "text": f"{n_contact} entreprise(s) du suivi restent à contacter.", "link": "/candidatures"})
    n_prepared = tr["counts"].get("À envoyer", 0)
    if n_prepared:
        out.append({"id": "prepared", "text": f"{n_prepared} candidature(s) préparée(s) restent à envoyer à l’employeur.", "link": "/candidatures"})
    return {"items": out}


@app.get("/api/tracking/{tid}/events")
def application_events(tid: str):
    d = S.load_tracking()
    if not (d.ID == tid).any():
        raise HTTPException(404, "Candidature introuvable")
    user_id = C.current_user_id()
    return {"items": accounts.status_events(user_id or "", tid)}


@app.get("/api/tracking/{tid}/emails")
def application_emails(tid: str):
    d = S.load_tracking()
    if not (d.ID == tid).any():
        raise HTTPException(404, "Candidature introuvable")
    user_id = C.current_user_id()
    items = accounts.email_messages(user_id or "")
    return {"items": [item for item in items if item["tracking_id"] == tid]}


class EmailReviewIn(BaseModel):
    tracking_id: str = Field(min_length=1, max_length=128)
    status: str


@app.get("/api/email-sync/status")
def email_sync_status():
    user_id = C.current_user_id()
    if not user_id:
        raise HTTPException(401, "Connexion BookJob requise.")
    state = accounts.email_sync_state(user_id)
    state["gmail"] = gmail.status()
    state["pending_reviews"] = len(accounts.email_messages(user_id, reviews_only=True))
    return state


@app.post("/api/email-sync/run")
def run_email_sync():
    try:
        return email_sync.sync_current_user()
    except gmail.GmailError as ex:
        raise HTTPException(502, str(ex)) from ex


@app.get("/api/email-sync/reviews")
def email_sync_reviews():
    user_id = C.current_user_id()
    if not user_id:
        raise HTTPException(401, "Connexion BookJob requise.")
    return {"items": accounts.email_messages(user_id, reviews_only=True)}


@app.post("/api/email-sync/reviews/{message_id}")
def resolve_email_sync_review(message_id: str, body: EmailReviewIn):
    user_id = C.current_user_id()
    if not user_id:
        raise HTTPException(401, "Connexion BookJob requise.")
    status = _check_statut(body.status)
    if status not in {"En cours de traitement", "Entretien programmé", "Acceptée", "Refusée"}:
        raise HTTPException(400, "Choisis un statut de réponse reçu par e-mail.")
    d = S.load_tracking()
    rows = d.index[d.ID == body.tracking_id]
    if len(rows) == 0:
        raise HTTPException(404, "Candidature introuvable.")
    messages = accounts.email_messages(user_id, reviews_only=True)
    message = next((item for item in messages if item["message_id"] == message_id), None)
    if not message:
        raise HTTPException(404, "E-mail de vérification introuvable ou déjà traité.")
    index = rows[0]
    old_status = str(d.loc[index, "Statut"])
    occurred_at = message["received_at"] or datetime.now(timezone.utc).isoformat(timespec="seconds")
    d.loc[index, "Statut"] = status
    d.loc[index, "Derniere_activite"] = message["subject"]
    d.loc[index, "Date_modification"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    S.save_tracking(d)
    if not accounts.resolve_email_review(user_id, message_id, body.tracking_id, status):
        raise HTTPException(409, "Cet e-mail vient d’être traité. Actualise la page.")
    _record_status_change(
        body.tracking_id, old_status, status, "gmail_manual",
        f"{message['subject']} — {message['snippet']}",
    )
    return _track_out(d.loc[index].to_dict())


_QUALITY_FIELDS = {
    "Telephone": "Téléphone", "Site_web": "Site web", "Note": "Note Google", "Nb_avis": "Nombre d'avis",
    "Categorie": "Catégorie", "Adresse": "Adresse",
}


def _sheet_or_empty(sheet: str) -> pd.DataFrame:
    try:
        return pd.read_excel(C.XLSX, sheet_name=sheet)
    except (ValueError, OSError):
        return pd.DataFrame()


@app.get("/api/data-quality")
def data_quality():
    """Qualité du jeu de données : rapport de nettoyage, complétude réelle, exclusions et exécutions du pipeline."""
    from .pipeline.run import load_runs

    companies = co.companies_df()
    total = int(len(companies))
    completeness = []
    for column, label in _QUALITY_FIELDS.items():
        if column in companies:
            filled = int(companies[column].map(lambda v: v is not None and str(v).strip() != "").sum())
            completeness.append({"field": label, "filled": filled,
                                 "percent": round(100 * filled / total, 1) if total else 0.0})
    report = _sheet_or_empty("Rapport nettoyage")
    if not report.empty:
        report = report.iloc[:, :3].astype(object)
        report.columns = ["probleme", "lignes", "traitement"][: len(report.columns)]
        report = report.where(pd.notna(report), None)
    excluded = _sheet_or_empty("Lignes exclues")
    raw_file = C.DATA_DIR / "donnees_brutes_places.xlsx"
    raw_rows = None
    if raw_file.exists():
        try:
            raw_rows = int(len(pd.read_excel(raw_file)))
        except (ValueError, OSError):
            raw_rows = None
    reasons = (excluded["Motif_exclusion"].value_counts().to_dict()
               if "Motif_exclusion" in excluded else {})
    return {
        "rows_raw": raw_rows,
        "rows_clean": total,
        "rows_excluded": int(len(excluded)),
        "excluded_reasons": [{"reason": k, "count": int(v)} for k, v in reasons.items()],
        "duplicate_ids": int(companies["ID"].duplicated().sum()),
        "completeness": completeness,
        "priorities": {str(k): int(v) for k, v in companies["Priorite"].value_counts().sort_index().items()},
        "exact_coordinates": int(companies["coord_exacte"].sum()),
        "report": report.to_dict("records") if not report.empty else [],
        "runs": load_runs()[-10:][::-1],
    }


@app.get("/api/stats")
def application_statistics(start: str = "", end: str = ""):
    today = date.today()
    try:
        end_date = date.fromisoformat(end) if end else today
        start_date = date.fromisoformat(start) if start else end_date - timedelta(days=83)
    except ValueError as ex:
        raise HTTPException(400, "Les dates doivent être au format YYYY-MM-DD.") from ex
    if start_date > end_date:
        raise HTTPException(400, "La date de début doit précéder la date de fin.")

    data = S.load_tracking().drop_duplicates(subset=["ID"], keep="last").copy()
    data["Date_candidature"] = pd.to_datetime(data["Date_candidature"], errors="coerce").dt.date
    sent_statuses = {
        "Candidature envoyée", "En cours de traitement", "Entretien programmé", "Acceptée", "Refusée",
    }
    sent = data[data["Statut"].isin(sent_statuses) & data["Date_candidature"].notna()].copy()
    within_period = sent[
        (sent["Date_candidature"] >= start_date) & (sent["Date_candidature"] <= end_date)
    ].copy()
    responses = {"En cours de traitement", "Entretien programmé", "Acceptée", "Refusée"}
    responded_ids = accounts.email_response_tracking_ids(C.current_user_id() or "")
    responded = within_period[
        within_period["ID"].isin(responded_ids) | within_period["Statut"].isin(responses)
    ]
    sent_total = len(within_period)
    reply_total = len(responded)
    accepted = int((within_period["Statut"] == "Acceptée").sum())
    interviews = int((within_period["Statut"] == "Entretien programmé").sum())
    declined = int((within_period["Statut"] == "Refusée").sum())

    current_monday = today - timedelta(days=today.weekday())
    previous_monday = current_monday - timedelta(days=7)
    sent_this_week = int(
        (
            (sent["Date_candidature"] >= max(start_date, current_monday))
            & (sent["Date_candidature"] <= min(end_date, today))
        ).sum()
    )
    sent_previous_week = int(
        (
            (sent["Date_candidature"] >= max(start_date, previous_monday))
            & (sent["Date_candidature"] < min(end_date + timedelta(days=1), current_monday))
        ).sum()
    )
    status_counts = within_period["Statut"].value_counts().to_dict()
    positive_negative = {"positives": interviews + accepted, "negative": declined}

    week_starts: list[date] = []
    first_week = start_date - timedelta(days=start_date.weekday())
    week = first_week
    while week <= end_date:
        week_starts.append(week)
        week += timedelta(days=7)
    weekly = [
        {
            "week": week.isoformat(),
            "count": int(
                ((within_period["Date_candidature"] >= week)
                 & (within_period["Date_candidature"] < week + timedelta(days=7))).sum()
            ),
        }
        for week in week_starts
    ]
    top_companies = (
        within_period.groupby("Entreprise").size().sort_values(ascending=False).head(10).to_dict()
    )
    return {
        "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "kpis": {
            "total": len(within_period),
            "sent_this_week": sent_this_week,
            "sent_previous_week": sent_previous_week,
            "responses": reply_total,
            "refusals": declined,
            "acceptances": accepted,
            "interviews": interviews,
            "response_rate": round(100 * reply_total / sent_total, 1) if sent_total else 0,
            "acceptance_rate": round(100 * accepted / sent_total, 1) if sent_total else 0,
        },
        "weekly": weekly,
        "by_status": {status: int(status_counts.get(status, 0)) for status in C.STATUTS},
        "positive_negative": positive_negative,
        "top_companies": [{"company": name, "count": int(count)} for name, count in top_companies.items()],
    }


async def _email_sync_worker():
    while True:
        await asyncio.sleep(30)
        try:
            for user_id in accounts.list_user_ids():
                token = C.set_current_user(user_id)
                try:
                    status = gmail.status()
                finally:
                    C.reset_current_user(token)
                if not status.get("connected") or not status.get("read_authorized"):
                    continue
                try:
                    await asyncio.to_thread(email_sync.sync_user, user_id)
                except (gmail.GmailError, RuntimeError):
                    _LOGGER.warning("Gmail sync failed for account %s", user_id, exc_info=True)
        except Exception:
            _LOGGER.exception("Boucle de synchronisation Gmail interrompue, nouvelle tentative plus tard")
        await asyncio.sleep(15 * 60)


@app.on_event("startup")
async def start_email_sync_worker():
    global _EMAIL_SYNC_TASK
    if os.getenv("VERCEL"):
        return
    accounts.initialize()
    if _EMAIL_SYNC_TASK is None or _EMAIL_SYNC_TASK.done():
        _EMAIL_SYNC_TASK = asyncio.create_task(_email_sync_worker())


@app.on_event("shutdown")
async def stop_email_sync_worker():
    global _EMAIL_SYNC_TASK
    if _EMAIL_SYNC_TASK:
        _EMAIL_SYNC_TASK.cancel()
        try:
            await _EMAIL_SYNC_TASK
        except asyncio.CancelledError:
            pass
        _EMAIL_SYNC_TASK = None


@app.get("/api/cron/email-sync")
def cron_email_sync(request: Request):
    secret = os.getenv("CRON_SECRET", "")
    auth = request.headers.get("authorization", "")
    if not secret or not hmac.compare_digest(auth, f"Bearer {secret}"):
        raise HTTPException(401, "Non autorisé")
    done = 0
    for user_id in accounts.list_user_ids():
        token = C.set_current_user(user_id)
        try:
            status = gmail.status()
            if not status.get("connected") or not status.get("read_authorized"):
                continue
            email_sync.sync_user(user_id)
            done += 1
        except (gmail.GmailError, RuntimeError):
            _LOGGER.warning("Gmail sync failed for account %s", user_id, exc_info=True)
        finally:
            C.reset_current_user(token)
    return {"ok": True, "synced": done}

@app.post("/api/reset/tracking")
def reset_tracking():
    d = S.load_tracking()
    for f in d.Fichier_CV:
        if f and (C.user_path(C.CV_SENT_DIR) / f).exists():
            (C.user_path(C.CV_SENT_DIR) / f).unlink()
    S.save_tracking(pd.DataFrame(columns=C.COLS))
    return {"ok": True}


@app.get("/api/health")
def health():
    return {"ok": True}


@app.exception_handler(Exception)
async def unhandled(request: Request, ex: Exception):
    # Le détail technique reste dans les logs serveur : il ne doit jamais être renvoyé au navigateur.
    logging.getLogger("bookjob").exception("Erreur non gérée sur %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Erreur serveur inattendue. Réessaie plus tard ou contacte l'administrateur."},
    )


# ---------- front (build Vite) ----------
_dash_app = dash_dashboard.create_dash_app(S.load_tracking, co.companies_df)
app.mount(
    "/dash",
    WSGIMiddleware(DashUserContextMiddleware(_dash_app.server)),
    name="dash",
)

if C.FRONT_DIST.exists():
    app.mount("/assets", StaticFiles(directory=C.FRONT_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        f = (C.FRONT_DIST / path).resolve()
        if path and C.FRONT_DIST.resolve() in f.parents and f.is_file():
            return FileResponse(f)
        return FileResponse(C.FRONT_DIST / "index.html")