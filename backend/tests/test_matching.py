from app.matching import match_profile_to_offer


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
