"""Génération CV / e-mail et assistant avec Groq ou Anthropic."""
import json

import requests

from . import config as C, integrations
from .store import split_list


def personal_api_key() -> str:
    try:
        return integrations.personal_key("groq")
    except integrations.IntegrationError as ex:
        raise AIError(str(ex)) from ex


def api_key() -> str:
    return _active_provider()[1]


def provider() -> str:
    try:
        return _active_provider()[0]
    except AIError:
        return "unavailable"


def key_status() -> dict:
    status = integrations.key_status("groq")
    return {
        "provider": "groq" if status["mode"] in {"personal", "server"} else "none",
        "mode": status["mode"],
        "personal_key_configured": status["personal_key_configured"],
        "encryption_available": status["encryption_available"],
        "masked_key": status["masked_key"],
    }


def test_api_key(key: str) -> None:
    try:
        integrations.validate_key("groq", key)
    except integrations.IntegrationError as ex:
        raise AIError(str(ex)) from ex


def save_personal_api_key(key: str) -> None:
    try:
        integrations.save_key("groq", key)
    except integrations.IntegrationError as ex:
        raise AIError(str(ex)) from ex


def remove_personal_api_key() -> None:
    integrations.remove_key("groq")


def _active_provider() -> tuple[str, str]:
    preference = "auto"
    if C.current_user_id():
        from . import store
        preference = store.load_state()["settings"].get("aiProvider", "auto")
    if preference in {"groq", "anthropic"}:
        candidates = [preference]
    else:
        candidates = ["groq", "anthropic"]

    if preference == "auto":
        # A personal key is preferred to a shared server key, while existing Groq
        # server configuration remains the default when no personal key is saved.
        for name in candidates:
            path = integrations._configured_path(name)
            if path:
                try:
                    return name, integrations.personal_key(name)
                except integrations.IntegrationError as ex:
                    raise AIError(str(ex)) from ex
        for name in candidates:
            if integrations.server_key(name):
                return name, integrations.server_key(name)
        return "none", ""

    try:
        key = integrations.resolve_key(preference)
        return (preference if key else "none"), key
    except integrations.IntegrationError as ex:
        raise AIError(str(ex)) from ex


def candidate_name(profile: dict) -> str:
    return " ".join(x for x in [profile.get("prenom"), profile.get("nom_famille")] if x).strip() or profile.get("nom", "")


class AIError(Exception):
    pass


def complete(system: str, messages: list[dict], max_tokens: int = 2000) -> str:
    name, key = _active_provider()
    if not key:
        raise AIError("Configure une clé Groq ou Anthropic personnelle dans les paramètres, ou une clé serveur.")
    try:
        if name == "anthropic":
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                timeout=120,
                headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                json={
                    "model": C.ANTHROPIC_MODEL,
                    "max_tokens": max_tokens,
                    "system": system,
                    "messages": messages,
                },
            )
        else:
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
        response = r.json()
        if name == "anthropic":
            return "".join(part["text"] for part in response["content"] if part["type"] == "text")
        return response["choices"][0]["message"]["content"]
    except requests.RequestException:
        raise AIError("Le fournisseur IA n'a pas pu traiter la demande.") from None
    except (KeyError, IndexError, TypeError):
        raise AIError("Le fournisseur IA a renvoyé une réponse invalide.") from None


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
