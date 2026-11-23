"""Issue #108: missed runs must not leave tennis matches "scheduled" (Nov 19-23 outage)."""
import json
from datetime import date, datetime, timezone

from sbi import db, tennis

NOW = datetime(2026, 11, 23, 14, 30, tzinfo=timezone.utc)


def _event(con, eid, league, ko, status="scheduled"):
    con.execute("""INSERT INTO events(event_id,sport,league,season,kickoff_utc,home,away,status,source,source_url,updated_at)
                   VALUES (?,'tennis',?,'2026',?,'Ana Alpha','Bea Beta',?,'s','u',?)""", (eid, league, ko, status, ko))


def _board(cid, d, completed):
    a = {"type": "athlete", "athlete": {"displayName": "Ana Alpha"}, "winner": completed,
         "linescores": [{"winner": completed}, {"winner": completed}]}
    b = {"type": "athlete", "athlete": {"displayName": "Bea Beta"}, "winner": False, "linescores": [{}, {}]}
    st = {"completed": completed, "name": "STATUS_FINAL" if completed else "STATUS_SCHEDULED"}
    return {"events": [{"id": "9", "name": "WTA Finals", "date": d, "groupings": [
        {"grouping": {"slug": "womens-singles", "displayName": "Women's Singles"},
         "competitions": [{"id": cid, "date": d, "competitors": [a, b], "status": {"type": st}}]}]}]}


def _fake_fetch(asked, boards=None):
    def fetch(url, max_age_hours=6.0, **k):
        asked.append((url, max_age_hours))
        return json.dumps((boards or {}).get(url, {"events": []})).encode(), None
    return fetch


def test_stale_wta_match_date_is_requested_fresh_and_finished_one_is_not(tmp_path, monkeypatch):
    con = db.connect(tmp_path / "t.sqlite")
    _event(con, "tennis:WTA:20261119:1", "TENNIS:WTA", "2026-11-19T15:00:00+00:00")              # 4 days old, unfinished
    _event(con, "tennis:WTA:20261118:2", "TENNIS:WTA", "2026-11-18T15:00:00+00:00", "finished")  # finished: no re-read
    asked = []
    monkeypatch.setattr(tennis, "fetch", _fake_fetch(asked))
    tennis.register(con, NOW)
    urls = {u: age for u, age in asked}
    for tour in ("wta", "atp"):
        u = tennis.ESPN.format(tour=tour, d="20261119")
        assert u in urls and urls[u] < 1                       # fresh read, not the year-long cache
        assert tennis.ESPN.format(tour=tour, d="20261118") not in urls
    # normal reading unchanged: today-3 .. today+7, daily
    assert tennis.ESPN.format(tour="wta", d="20261120") in urls
    assert tennis.ESPN.format(tour="wta", d="20261130") in urls


def test_catchup_settles_stored_match_but_creates_no_old_rows(tmp_path, monkeypatch):
    con = db.connect(tmp_path / "t.sqlite")
    _event(con, "tennis:WTA:20261119:1", "TENNIS:WTA", "2026-11-19T15:00:00+00:00")
    u = tennis.ESPN.format(tour="wta", d="20261119")
    board = _board("1", "2026-11-19T15:00Z", True)
    board["events"][0]["groupings"][0]["competitions"].append(
        {**board["events"][0]["groupings"][0]["competitions"][0], "id": "3"})   # never stored: must not be created
    monkeypatch.setattr(tennis, "fetch", _fake_fetch([], {u: board}))
    tennis.register(con, NOW)
    r = con.execute("SELECT status, home_score, away_score FROM events WHERE event_id='tennis:WTA:20261119:1'").fetchone()
    assert tuple(r) == ("finished", 2, 0)
    assert con.execute("SELECT 1 FROM events WHERE event_id='tennis:WTA:20261119:3'").fetchone() is None


def test_past_day_cached_while_unfinished_is_read_again(monkeypatch):
    asked = []

    def fetch(url, max_age_hours=6.0, **k):
        asked.append(max_age_hours)
        return json.dumps(_board("5", "2026-11-16T15:00Z", max_age_hours < 1)).encode(), None
    monkeypatch.setattr(tennis, "fetch", fetch)
    ms = tennis._day("wta", date(2026, 11, 16), NOW, past=True)
    assert asked[0] > 1000 and asked[1] < 1 and ms[0]["completed"]
    asked.clear()
    monkeypatch.setattr(tennis, "fetch", lambda url, max_age_hours=6.0, **k: asked.append(max_age_hours)
                        or (json.dumps(_board("5", "2026-11-16T15:00Z", True)).encode(), None))
    tennis._day("wta", date(2026, 11, 16), NOW, past=True)
    assert len(asked) == 1                                      # finished day: long cache only
