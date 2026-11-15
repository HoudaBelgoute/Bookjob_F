import pandas as pd

from app.main import _sent_application_rows


def test_sent_application_metrics_exclude_drafts_cancelled_and_invalid_dates():
    rows = pd.DataFrame([
        {"ID": "sent", "Statut": "Candidature envoyée", "Date_candidature": "2026-11-10"},
        {"ID": "interview", "Statut": "Entretien programmé", "Date_candidature": "2026-11-11"},
        {"ID": "refused", "Statut": "Refusée", "Date_candidature": "2026-11-12"},
        {"ID": "draft", "Statut": "Brouillon", "Date_candidature": "2026-11-13"},
        {"ID": "to-send", "Statut": "À envoyer", "Date_candidature": ""},
        {"ID": "cancelled", "Statut": "Offre expirée ou candidature annulée", "Date_candidature": "2026-11-14"},
        {"ID": "invalid-date", "Statut": "Candidature envoyée", "Date_candidature": "inconnue"},
    ])

    sent = _sent_application_rows(rows)

    assert sent["ID"].tolist() == ["sent", "interview", "refused"]
