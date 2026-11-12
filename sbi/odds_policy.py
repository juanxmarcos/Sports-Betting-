"""Source-specific odds freshness: how old a quote may be to count as ACTIONABLE.

A quote that is still in the database is not necessarily still available. Limits depend on
how often each feed is refreshed and on how close the event is (prices move most late).
"""
from __future__ import annotations

from . import config


def max_age_hours(source: str | None, hours_to_start: float | None) -> float:
    src = (source or "").lower()
    h = hours_to_start if hours_to_start is not None else 999
    if "espn" in src:
        limit = 6.0          # re-read every run; an older ESPN quote has left the feed
    elif "odds-api" in src:
        limit = 6.0 if h <= 10 else (12.0 if h <= 36 else 24.0)   # matches the refresh schedule
    elif "football-data" in src:
        limit = 12.0 if h <= 10 else 24.0   # twice-weekly snapshot: never treated as a late price
    else:
        limit = 12.0
    return min(limit, config.RULES.max_odds_age_hours)
