"""Counts for sent applications, based only on valid dates and explicit sent statuses."""
from datetime import date, timedelta

import pandas as pd

from . import config as C


def weekly_sent_count(tracking: pd.DataFrame, today: date) -> int:
    week_start = today - timedelta(days=today.weekday())
    count = 0
    for row in tracking.to_dict(orient="records"):
        if row.get("Statut") not in C.STATUTS_ENVOYES:
            continue
        try:
            sent_date = date.fromisoformat(str(row.get("Date_candidature", ""))[:10])
        except ValueError:
            continue
        if week_start <= sent_date <= today:
            count += 1
    return count


def followup_reminder_day(status: str, sent_at: str, today: date) -> int:
    if status != "Candidature envoyée":
        return 0
    try:
        sent_date = date.fromisoformat(str(sent_at)[:10])
    except ValueError:
        return 0
    days_since_sent = (today - sent_date).days
    if days_since_sent >= 14:
        return 14
    if days_since_sent >= 7:
        return 7
    return 0
