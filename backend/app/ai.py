"""Génération CV / e-mail et assistant. Les clés restent côté serveur (jamais envoyées au navigateur).
Fournisseur IA unique : Groq."""
import json

import requests
from cryptography.fernet import Fernet, InvalidToken

from . import config as C
from .store import split_list


def _secret_path():
    if not C.current_user_id():
        return None
    return C.user_path(C.DATA_DIR / "secrets" / "groq-api-key.enc")


def _cipher() -> Fernet:
    if not C.AI_KEY_ENCRYPTION_KEY:
        raise AIError("Le stockage chiffré des clés IA personnelles n'est pas configuré sur le serveur.")
    try:
        return Fernet(C.AI_KEY_ENCRYPTION_KEY.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as ex:
        raise AIError("La configuration de chiffrement des clés IA est invalide.") from ex


def personal_api_key() -> str:
    path = _secret_path()
    if path is None or not path.exists():
        return ""
    try:
        return _cipher().decrypt(path.read_bytes()).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError) as ex:
        raise AIError("La clé IA personnelle ne peut pas être déchiffrée avec la configuration actuelle.") from ex


def api_key() -> str:
    return personal_api_key() or C.GROQ_API_KEY


def provider() -> str:
    try:
        return "groq" if api_key() else "none"
    except AIError:
        return "unavailable"


def key_status() -> dict:
    path = _secret_path()
    personal_configured = bool(path and path.exists())
    try:
        _cipher()
        encryption_available = True
    except AIError:
        encryption_available = False
    personal_key_usable = False
    if personal_configured and encryption_available:
        try:
            personal_key_usable = bool(personal_api_key())
        except AIError:
            pass
    if personal_configured and not personal_key_usable:
        mode = "unavailable"
    elif personal_configured:
        mode = "personal"
    elif C.GROQ_API_KEY:
        mode = "server"
    else:
        mode = "none"
    return {
        "provider": "groq" if mode in {"personal", "server"} else "none",
        "mode": mode,
        "personal_key_configured": personal_configured,
        "encryption_available": encryption_available,
        "masked_key": "••••••••" if personal_configured else "",
    }


def test_api_key(key: str) -> None:
    try:
        response = requests.get(
            "https://api.groq.com/openai/v1/models",
            timeout=15,
            headers={"Authorization": f"Bearer {key}"},
        )
    except requests.RequestException as ex:
        raise AIError("Impossible de joindre le fournisseur Groq pour vérifier la clé.") from ex
    if response.status_code in {401, 403}:
        raise AIError("Groq a refusé cette clé. Vérifie-la puis réessaie.")
    if not response.ok:
        raise AIError("Groq n'a pas pu vérifier la clé pour le moment.")


def save_personal_api_key(key: str) -> None:
    path = _secret_path()
    if path is None:
        raise AIError("Connexion BookJob requise pour enregistrer une clé personnelle.")
    cleaned = key.strip()
    if not cleaned or len(cleaned) > 512 or "\n" in cleaned or "\r" in cleaned:
        raise AIError("Saisis une clé Groq valide.")
    cipher = _cipher()
    test_api_key(cleaned)
    path.write_bytes(cipher.encrypt(cleaned.encode("utf-8")))


def remove_personal_api_key() -> None:
    path = _secret_path()
    if path and path.exists():
        path.unlink()


def candidate_name(profile: dict) -> str:
    return " ".join(x for x in [profile.get("prenom"), profile.get("nom_famille")] if x).strip() or profile.get("nom", "")


class AIError(Exception):
    pass


def complete(system: str, messages: list[dict], max_tokens: int = 2000) -> str:
    key = api_key()
    if not key:
        raise AIError("Configure une clé Groq personnelle dans les paramètres ou la clé serveur GROQ_API_KEY.")
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            timeout=120,
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": C.GROQ_MODEL,
                "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": system}, *messages],
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except requests.RequestException as ex:
        raise AIError("Le fournisseur IA n'a pas pu traiter la demande.") from ex
    except (KeyError, IndexError, TypeError) as ex:
        raise AIError("Le fournisseur IA a renvoyé une réponse invalide.") from ex


CV_SYSTEM = """Tu rédiges en français un CV d'une page compatible ATS et un e-mail de candidature pour un stage.
RÈGLES STRICTES : utilise UNIQUEMENT les informations du PROFIL fourni. N'invente aucun diplôme, employeur, date,
chiffre, outil ou compétence. Tu peux reformuler, réordonner et mettre en avant ce qui correspond à l'offre et au secteur.
Présente le prénom, le nom, la filière, le profil professionnel, les diplômes, la formation, l'expérience professionnelle,
les compétences, l'engagement associatif, les langues et les coordonnées lorsqu'ils sont renseignés.
Utilise une seule colonne, des titres de section classiques, sans tableau, icône ni mise en page décorative.
Si une information utile manque, ne la crée pas : signale-la dans une section finale 'À compléter'.
Format de sortie : le CV en Markdown, puis une ligne '===MAIL===', puis l'objet (ligne 'Objet : ...') et le corps de l'e-mail (5-7 lignes)."""

LETTER_SYSTEM = """Tu rédiges en français une lettre de motivation (250 mots maximum) pour un stage.
Utilise UNIQUEMENT les informations du PROFIL. N'invente rien (diplômes, employeurs, chiffres, outils).
Ton demandé : {tone}. Termine par une formule de politesse et le nom du candidat."""

CHAT_SYSTEM = """Tu es l'assistant BookJob, qui aide un étudiant à trouver un stage à Marrakech.
Rédige en français correct, avec des phrases naturelles, une orthographe soignée et une réponse bien organisée.
Commence par répondre directement à la question. Pour une réponse développée, utilise au maximum trois titres courts
sur leur propre ligne, sans syntaxe Markdown, des paragraphes brefs et des listes dont chaque élément commence par « • ».
Évite les répétitions et les blocs de texte longs. Reste concis, concret et professionnel ; adapte la longueur à la question.
Tu connais l'entreprise ciblée (données Google Maps) mais PAS ses offres internes ni ses recrutements : ne prétends jamais
qu'elle recrute. {profile_rule}
Tu peux expliquer le secteur, comparer le profil au secteur, proposer des compétences à renforcer, préparer un entretien
ou suggérer des questions. N'invente aucun fait sur l'entreprise ni sur le profil. Signale clairement les informations
manquantes et distingue les faits des conseils."""


def cv_modele(p: dict, offre: str = "") -> str:
    """Sans IA : mise en page du profil, compétences pertinentes remontées en premier."""
    mots = set(offre.lower().replace(",", " ").split())
    comp = split_list(p.get("competences", ""))
    comp.sort(key=lambda c: -any(m in c.lower() for m in mots))
    bloc = lambda t, k: f"\n## {t}\n{p[k]}\n" if p.get(k, "").strip() else ""
    full_name = candidate_name(p)
    contact = " · ".join(x for x in [p.get("email"), p.get("tel"), p.get("ville"), p.get("linkedin")] if x)
    profile = "\n".join(x for x in [p.get("filiere"), p.get("resume")] if x)
    education = "\n".join(x for x in [p.get("diplomes"), p.get("formation")] if x)
    return (f"# {full_name}\n{p.get('titre', '')}\n\n{contact}\n"
            + (f"\n## Profil\n{profile}\n" if profile else "")
            + (f"\n## Compétences\n{' · '.join(comp)}\n" if comp else "")
            + (f"\n## Formation\n{education}\n" if education else "")
            + bloc("Expérience professionnelle", "experiences")
            + bloc("Engagement associatif", "engagement_associatif")
            + bloc("Projets", "projets") + bloc("Langues", "langues") + bloc("Certifications", "certifs"))


def mail_modele(p: dict, entreprise: str, poste: str) -> str:
    return (f"Objet : Candidature au poste de {poste}\n\nBonjour,\n\nJe vous adresse ma candidature spontanée pour un stage "
            f"({poste}) chez {entreprise}. Vous trouverez mon CV en pièce jointe et je reste disponible pour échanger.\n\n"
            f"Cordialement,\n{candidate_name(p)}\n{p.get('tel', '')}")


def generer(p: dict, entreprise: str, secteur: str, poste: str, offre: str, use_ai: bool) -> dict:
    if use_ai and provider() != "none":
        txt = complete(CV_SYSTEM, [{"role": "user", "content":
                       f"PROFIL (JSON) :\n{json.dumps(p, ensure_ascii=False)}\n\n"
                       f"CIBLE : entreprise={entreprise} ; secteur={secteur} ; poste={poste}\nOFFRE :\n{offre or '(non fournie)'}"}], 2500)
        cv, _, mail = txt.partition("===MAIL===")
        return {"cv": cv.strip(), "mail": mail.strip() or mail_modele(p, entreprise, poste), "mode": provider()}
    return {"cv": cv_modele(p, offre), "mail": mail_modele(p, entreprise, poste), "mode": "modele"}


def lettre(p: dict, entreprise: str, poste: str, ton: str, use_ai: bool) -> dict:
    if use_ai and provider() != "none":
        txt = complete(LETTER_SYSTEM.format(tone=ton), [{"role": "user", "content":
                       f"PROFIL :\n{json.dumps(p, ensure_ascii=False)}\n\nENTREPRISE : {entreprise}\nPOSTE : {poste}"}], 1200)
        return {"lettre": txt.strip(), "mode": provider()}
    comp = ", ".join(split_list(p.get("competences", "")))
    parcours = p.get("diplomes") or p.get("formation") or p.get("filiere") or "formation"
    corps = (f"Madame, Monsieur,\n\nÉtudiant(e) en {parcours}, je souhaite effectuer un stage ({poste}) "
             f"au sein de {entreprise}.\n\n" + (f"Mes compétences : {comp}.\n\n" if comp else "")
             + (f"Parmi mes projets : {p['projets']}.\n\n" if p.get("projets") else "")
             + "Je serais ravi(e) de vous rencontrer pour échanger sur ma candidature.\n\nCordialement,\n" + candidate_name(p))
    return {"lettre": corps, "mode": "modele"}


def chat_fallback(question: str, company: dict | None, profile: dict, use_profile: bool) -> str:
    """Réponse sans IA, uniquement à partir des données réelles."""
    q = question.lower()
    if company and any(k in q for k in ("correspond", "profil", "compatib", "match")):
        if not use_profile or company.get("match") is None:
            return "Pour afficher cet indice\n\nActivez « Utiliser mon profil » et renseignez vos compétences."
        ms = ", ".join(company["match_skills"]) or "aucune"
        miss = ", ".join(company["missing_skills"]) or "aucune"
        explanation = company.get("match_explanation") or (
            "Cet indice compte les compétences déclarées qui partagent un mot-clé du secteur."
        )
        return (f"Indice de mots-clés profil / secteur\n\n{company['short']} — secteur {company['secteur']} : "
                f"{company['match']}/100.\n{explanation}\n\n• Compétences rapprochées : {ms}.\n"
                f"• Compétences sans mot-clé correspondant : {miss}.\n\n"
                "Ce n'est ni une analyse d'offre ni une probabilité d'embauche.")
    if any(k in q for k in ("manque", "compétence")):
        if company and use_profile:
            return (f"Compétences sans mot-clé correspondant\n\nPour le secteur {company['secteur']} : "
                    f"{', '.join(company['missing_skills']) or 'aucune'}.\n"
                    "Cela ne signifie pas que ces compétences sont inutiles ou insuffisantes.")
        return "Comparaison du profil\n\nRenseignez votre profil pour comparer vos compétences au secteur visé."
    if any(k in q for k in ("entretien", "préparer", "preparer")):
        nom = company["short"] if company else "l'entreprise"
        return (f"Préparer l'entretien chez {nom}\n\n• Préparez trois exemples précis : un projet, un travail d'équipe "
                "et une difficulté résolue.\n• Renseignez-vous sur l'activité de l'entreprise à partir de son site officiel.\n"
                "• Préparez deux questions sur les missions du stage.")
    if company:
        return (f"{company['short']}\n\n• Secteur : {company['secteur']}.\n• Quartier : {company['quartier']}.\n"
                f"• Note Google : {company['note'] if company['note'] is not None else 'non communiquée'} "
                f"({company['nb_avis'] or 0} avis).\n\nJe n'ai pas d'information sur ses offres de stage. "
                "Une candidature spontanée peut être envisagée.\n\nMode sans IA : réponse limitée aux données disponibles.")
    return ("Mode sans IA\n\nAucune clé IA n'est configurée. Je peux répondre à des questions simples sur "
            "la compatibilité, les compétences ou la préparation d'un entretien, à partir des données disponibles.")


def chat(history: list[dict], company: dict | None, profile: dict, use_profile: bool) -> dict:
    question = history[-1]["content"]
    if provider() == "none":
        return {"reply": chat_fallback(question, company, profile, use_profile), "mode": "modele"}
    rule = ("Utilise le PROFIL ci-dessous pour personnaliser, sans rien inventer.\nPROFIL : " + json.dumps(profile, ensure_ascii=False)
            if use_profile else "N'utilise aucune donnée personnelle du candidat (permission non accordée).")
    ctx = ""
    if company:
        ctx = ("\nENTREPRISE CIBLÉE : " + json.dumps({k: company.get(k) for k in
               ("short", "secteur", "quartier", "adresse", "site_web", "note", "nb_avis")}, ensure_ascii=False))
    reply = complete(CHAT_SYSTEM.format(profile_rule=rule) + ctx, history[-12:], 900)
    return {"reply": reply.strip(), "mode": provider()}
