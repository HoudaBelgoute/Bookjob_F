from app.ai import cv_modele, mail_modele


def test_cv_model_formats_structured_ats_profile_fields():
    profile = {
        "prenom": "Amina",
        "nom_famille": "El Amrani",
        "titre": "Stage Data Analyst",
        "email": "amina@example.com",
        "tel": "+212600000000",
        "ville": "Marrakech",
        "filiere": "Data science",
        "diplomes": "Licence en informatique — Université X — 2025",
        "resume": "Étudiante spécialisée en analyse de données.",
        "formation": "Université X — 2022 à 2025",
        "experiences": "Aucune expérience professionnelle à ce jour",
        "competences": "Python, SQL",
        "engagement_associatif": "Aucun engagement associatif à ce jour",
    }

    cv = cv_modele(profile)

    assert cv.startswith("# Amina El Amrani")
    assert "## Profil\nData science\nÉtudiante spécialisée en analyse de données." in cv
    assert "## Formation\nLicence en informatique" in cv
    assert "Université X — 2022 à 2025" in cv
    assert "## Expérience professionnelle" in cv
    assert "## Engagement associatif" in cv
    assert "Python · SQL" in cv
    assert "Amina El Amrani" in mail_modele(profile, "Entreprise X", "Stage Data Analyst")


def test_cv_model_keeps_legacy_full_name_when_split_name_is_missing():
    assert cv_modele({"nom": "Candidate"}).startswith("# Candidate")
