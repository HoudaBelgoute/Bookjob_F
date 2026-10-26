"""Connexion « Continuer avec Google » (OpenID Connect).

Utilise le même client OAuth et la même URI de redirection que la connexion Gmail, mais uniquement les
scopes ``openid email profile`` : se connecter avec Google ne donne aucun accès à la boîte mail.
"""
from urllib.parse import urlencode

import requests

from . import config as C, gmail

LOGIN_SCOPES = "openid email profile"
STATE_PREFIX = "login."  # secrets.token_urlsafe ne produit jamais de « . » : pas de confusion avec Gmail


def configured() -> bool:
    return gmail.configured()


def authorization_url(state: str) -> str:
    params = {
        "client_id": C.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": C.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": LOGIN_SCOPES,
        "prompt": "select_account",
        "state": state,
    }
    return f"{gmail.AUTH_URL}?{urlencode(params)}"


def identity(code: str) -> tuple[str, str]:
    """Échange le code contre un jeton puis renvoie (e-mail vérifié, nom affiché)."""
    token = gmail._request_json(gmail.TOKEN_URL, data={
        "code": code,
        "client_id": C.GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": C.GOOGLE_OAUTH_CLIENT_SECRET,
        "redirect_uri": C.GOOGLE_OAUTH_REDIRECT_URI,
        "grant_type": "authorization_code",
    })
    access_token = token.get("access_token")
    if not access_token:
        raise gmail.GmailError("Google n'a pas renvoyé de jeton d'accès.")
    try:
        response = requests.get(gmail.USERINFO_URL, headers={"Authorization": "Bearer " + access_token}, timeout=20)
        info = response.json() if response.ok else None
    except (requests.RequestException, ValueError) as ex:
        raise gmail.GmailError("Impossible de vérifier le compte Google.") from ex
    if not isinstance(info, dict):
        raise gmail.GmailError("Google n'a pas permis de vérifier le compte.")
    email = info.get("email")
    if not isinstance(email, str) or "@" not in email:
        raise gmail.GmailError("Google n'a pas renvoyé d'adresse e-mail.")
    if info.get("verified_email") is not True:
        raise gmail.GmailError("L'adresse de ce compte Google n'est pas vérifiée.")
    name = info.get("name") if isinstance(info.get("name"), str) else ""
    return email, name.strip()
