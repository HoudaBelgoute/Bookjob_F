from datetime import date

import pandas as pd

from app.application_stats import followup_reminder_day, weekly_sent_count


def test_weekly_goal_progress_counts_only_valid_sent_applications_this_week():
    tracking = pd.DataFrame([
        {"Statut": "Candidature envoyée", "Date_candidature": "2026-11-16"},
        {"Statut": "Entretien programmé", "Date_candidature": "2026-11-15"},
        {"Statut": "Refusée", "Date_candidature": "2026-11-17"},
        {"Statut": "Brouillon", "Date_candidature": "2026-11-16"},
        {"Statut": "Candidature envoyée", "Date_candidature": "2026-11-09"},
        {"Statut": "Candidature envoyée", "Date_candidature": "2026-11-18"},
        {"Statut": "Candidature envoyée", "Date_candidature": "2026-11-31"},
        {"Statut": "Candidature envoyée", "Date_candidature": ""},
    ])

    assert weekly_sent_count(tracking, date(2026, 11, 17)) == 2


def test_followup_draft_reminder_stages_are_limited_to_unanswered_sent_status():
    today = date(2026, 11, 17)
    assert followup_reminder_day("Candidature envoyée", "2026-11-10", today) == 7
    assert followup_reminder_day("Candidature envoyée", "2026-11-03", today) == 14
    assert followup_reminder_day("Entretien programmé", "2026-11-03", today) == 0
    assert followup_reminder_day("Candidature envoyée", "date inconnue", today) == 0
