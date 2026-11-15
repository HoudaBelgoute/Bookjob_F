from app.matching import match_profile_to_offer
from app.companies import match_info


def test_matching_reports_only_declared_skills_found_in_the_supplied_offer():
    report = match_profile_to_offer(
        {"competences": "Python, SQL, Power BI"},
        "Stage analyste",
        "Le candidat utilisera Python et Power BI pour les rapports.",
    )

    assert report["score"] == 67
    assert report["matched_skills"] == ["Python", "Power BI"]
    assert report["unmentioned_skills"] == ["SQL"]
    assert "2 compétence(s) déclarée(s) sur 3" in report["explanation"]


def test_matching_does_not_invent_a_score_without_offer_text_or_profile_skills():
    no_offer = match_profile_to_offer({"competences": "Python"}, "Stage Data", "")
    no_skills = match_profile_to_offer({"competences": ""}, "Stage Data", "Python")

    assert no_offer["score"] is None
    assert "texte de l'offre" in no_offer["explanation"]
    assert no_skills["score"] is None
    assert "compétences dans ton profil" in no_skills["explanation"]


def test_company_match_is_an_explainable_share_of_declared_skills():
    row = {"Secteur": "IT / Dev / Data"}
    report = match_info(row, {"competences": "Python, Tableau, UX design"})
    no_overlap = match_info(row, {"competences": "Accounting"})
    no_profile = match_info(row, {"competences": ""})

    assert report["match"] == 67
    assert report["match_skills"] == ["Python", "Tableau"]
    assert report["missing_skills"] == ["UX design"]
    assert "2 compétence(s) sur 3" in report["match_explanation"]
    assert no_overlap["match"] == 0
    assert no_overlap["missing_skills"] == ["Accounting"]
    assert no_profile["match"] is None


def test_company_match_uses_whole_keyword_tokens():
    report = match_info({"Secteur": "IT / Dev / Data"}, {"competences": "ability"})
    assert report["match"] == 0
