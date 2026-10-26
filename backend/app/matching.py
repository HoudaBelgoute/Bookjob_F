"""Conservative, explainable matching of declared profile skills to an offer."""
import re
import unicodedata

from .store import split_list


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold())
    without_accents = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9+#.]+", " ", without_accents)


def match_profile_to_offer(profile: dict, offer_title: str, offer_description: str) -> dict:
    skills = list(dict.fromkeys(
        skill.strip() for skill in split_list(profile.get("competences", ""))
        if len(_normalize(skill).strip()) >= 2
    ))
    if not offer_description.strip():
        return {
            "score": None,
            "matched_skills": [],
            "unmentioned_skills": skills,
            "explanation": "Ajoute le texte de l'offre pour calculer une correspondance indicative.",
        }
    offer_text = f"{offer_title}\n{offer_description}"
    normalized_offer = f" {_normalize(offer_text)} "
    matched = [
        skill for skill in skills
        if f" {_normalize(skill).strip()} " in normalized_offer
    ]
    unmentioned = [skill for skill in skills if skill not in matched]
    if not skills:
        return {
            "score": None,
            "matched_skills": [],
            "unmentioned_skills": [],
            "explanation": "Ajoute tes compétences dans ton profil pour calculer la correspondance.",
        }
    score = round(100 * len(matched) / len(skills))
    return {
        "score": score,
        "matched_skills": matched,
        "unmentioned_skills": unmentioned,
        "explanation": (
            f"{len(matched)} compétence(s) déclarée(s) sur {len(skills)} "
            "sont explicitement mentionnées dans le texte de l'offre."
        ),
    }
