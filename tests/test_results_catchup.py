"""Missed runs must not leave games unsettled (2026-11-23: NBA games of Nov 19-20 stayed "scheduled")."""
from datetime import date, datetime, timezone

from sbi import catchup, db, us


def _event(con, eid, league, sport, ko, status="scheduled"):
    con.execute("""INSERT INTO events(event_id,sport,league,season,kickoff_utc,home,away,status,source,source_url,updated_at)
                   VALUES (?,?,?,?,?,'H','A',?,'s','u',?)""", (eid, sport, league, "2026", ko, status, ko))


def test_stale_dates_lists_overdue_unfinished_games_by_new_york_date(tmp_path):
    con = db.connect(tmp_path / "t.sqlite")
    now = datetime(2026, 11, 23, 14, 30, tzinfo=timezone.utc)
    _event(con, "a", "NBA", "nba", "2026-11-20T01:00:00+00:00")                 # Nov 19 evening in New York
    _event(con, "b", "NBA", "nba", "2026-11-21T03:00:00+00:00")                 # Nov 20 evening in New York
    _event(con, "c", "NBA", "nba", "2026-11-22T01:00:00+00:00", "finished")     # finished: not stale
    _event(con, "d", "NBA", "nba", "2026-11-23T13:00:00+00:00")                 # within the grace period
    _event(con, "e", "NBA", "nba", "2026-11-01T01:00:00+00:00")                 # older than the window
    _event(con, "f", "SP1", "football", "2026-11-20T20:00:00+00:00")            # another league
    assert catchup.stale_dates(con, now, "NBA") == {date(2026, 11, 19), date(2026, 11, 20)}
    assert catchup.stale_dates(con, now, "SP1") == {date(2026, 11, 20)}


def test_us_ingest_rereads_stale_days(tmp_path, monkeypatch):
    con = db.connect(tmp_path / "t.sqlite")
    now = datetime(2026, 11, 23, 14, 30, tzinfo=timezone.utc)
    _event(con, "a", "NBA", "nba", "2026-11-20T01:00:00+00:00")
    asked = []
    monkeypatch.setattr(us, "scoreboard", lambda sport, d, age: asked.append(d) or [])
    us.ingest(con, now, "nba", ahead_days=1)
    assert date(2026, 11, 19) in asked                       # outside the normal 2-day look-back
    assert date(2026, 11, 21) in asked and date(2026, 11, 24) in asked
