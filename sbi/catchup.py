"""Results catch-up after missed runs (2026-11-23).

The ESPN readers re-read only the last day or two for final scores. When scheduled data runs fail
for several days (as on 2026-11-19..23), games in that gap stayed "scheduled" forever and their
picks and parlays never settled. `stale_dates` lists the past New York dates that still have an
unfinished game, so each reader can re-read exactly those days (free, cached ESPN requests).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
CATCHUP_DAYS = 14            # how far back unfinished games are looked for
GRACE_HOURS = 4              # a game is overdue this long after kickoff


def stale_dates(con, now: datetime, league: str, days: int = CATCHUP_DAYS) -> set[date]:
    """New York dates (ESPN scoreboard dates) of `league` games that kicked off between `days` ago
    and GRACE_HOURS ago and are still not finished."""
    lo = (now - timedelta(days=days)).isoformat()
    hi = (now - timedelta(hours=GRACE_HOURS)).isoformat()
    out = set()
    for (ko,) in con.execute("""SELECT kickoff_utc FROM events WHERE league=? AND status='scheduled'
                                AND kickoff_utc >= ? AND kickoff_utc <= ?""", (league, lo, hi)):
        try:
            t = datetime.fromisoformat(ko)
        except (TypeError, ValueError):
            continue
        out.add(t.astimezone(NY).date())
    return out
