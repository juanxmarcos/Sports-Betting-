from datetime import datetime, timedelta, timezone

import pytest

from sbi import config, db
from sbi.sources import odds_api as oa

EVENT = {"id": "x", "sport_key": "soccer_uefa_nations_league", "commence_time": "2026-11-14T17:00:00Z",
         "home_team": "Norway", "away_team": "Wales",
         "bookmakers": [
             {"key": "pinnacle", "title": "Pinnacle", "last_update": "2026-11-14T08:00:00Z",
              "markets": [{"key": "h2h", "outcomes": [{"name": "Norway", "price": 1.25}, {"name": "Wales", "price": 12.5},
                                                      {"name": "Draw", "price": 6.6}]},
                          {"key": "totals", "outcomes": [{"name": "Over", "price": 1.9, "point": 2.5},
                                                         {"name": "Under", "price": 1.98, "point": 2.5}]}]},
             {"key": "betfair_ex_eu", "title": "Betfair", "last_update": "2026-11-14T08:01:00Z",
              "markets": [{"key": "h2h", "outcomes": [{"name": "Norway", "price": 1.26}, {"name": "Wales", "price": 13.0},
                                                      {"name": "Draw", "price": 6.8}]},
                          {"key": "spreads", "outcomes": [{"name": "Norway", "price": 1.95, "point": -1.5},
                                                          {"name": "Wales", "price": 1.95, "point": 1.5}]}]}]}


def test_parse_odds():
    rows = oa.parse_odds(EVENT)
    d = {(b, m, s, l): p for b, m, s, l, p, _ in rows}
    assert d[("Pinnacle", "1X2", "H", None)] == 1.25
    assert d[("Pinnacle", "1X2", "D", None)] == 6.6
    assert d[("Pinnacle", "OU", "over", 2.5)] == 1.9
    assert d[("Betfair Exchange", "AH", "home", -1.5)] == 1.95
    assert d[("Betfair Exchange", "AH", "away", -1.5)] == 1.95  # home-perspective line


def test_name_similarity():
    assert oa.similarity("Manchester City", "Man City") >= 0.6
    assert oa.similarity("Bosnia & Herzegovina", "Bosnia and Herzegovina") == 1.0
    assert oa.similarity("Türkiye", "Turkiye") == 1.0
    assert oa.similarity("Norway", "Wales") < 0.6


def test_budget():
    now = datetime(2026, 11, 12, tzinfo=timezone.utc)  # 19 days left -> 38 runs
    assert oa.budget(None, now) == oa.MAX_CREDITS_PER_RUN
    assert oa.budget(420, now) == oa.MAX_CREDITS_PER_RUN      # daily (420-20)/19 = 21 -> capped at 8/run
    assert oa.budget(420, now, spent_today=16) == 5            # (436-20)/19 = 21.9 - 16
    assert oa.budget(100, now) == 4                            # (100-20)/19 = 4.2
    assert oa.budget(15, now) == 0


def test_no_key_skips(monkeypatch, tmp_path):
    monkeypatch.delenv("ODDS_API_KEY", raising=False)
    con = db.connect(tmp_path / "t.sqlite")
    assert oa.ingest(con, datetime.now(timezone.utc)) == {"skipped": "ODDS_API_KEY not set"}


def test_ingest_matches_and_stores(monkeypatch, tmp_path):
    con = db.connect(tmp_path / "t.sqlite")
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,updated_at)
                   VALUES ('football:INT:uefa.nations:20261114:1','football','INT:uefa.nations',
                   '2026-11-14T17:00:00+00:00','Norway','Wales','scheduled','t','t')""")
    monkeypatch.setenv("ODDS_API_KEY", "dummy")
    calls = []

    def fake_get(path, params, api_key):
        calls.append(path)
        usage = {"remaining": "400", "used": "100", "last": "0"}
        if path == "/sports":
            return [{"key": "soccer_uefa_nations_league", "active": True}], usage
        if path.endswith("/events"):
            return [EVENT], usage
        return [EVENT], {**usage, "remaining": "398", "last": "2"}

    monkeypatch.setattr(oa, "_get", fake_get)
    now = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)
    out = oa.ingest(con, now)
    assert out["matched"] == 1 and out["credits_spent"] == 2 and out["odds_rows"] > 5
    assert "/sports/soccer_uefa_nations_league/odds" in calls
    url = con.execute("SELECT source_url FROM odds LIMIT 1").fetchone()[0]
    assert "apiKey" not in url and "dummy" not in url


def test_parse_two_way():
    ev = {"home_team": "Detroit Lions", "away_team": "New England Patriots", "bookmakers": [
        {"key": "pinnacle", "title": "Pinnacle", "last_update": "2026-11-14T08:00:00Z", "markets": [
            {"key": "h2h", "outcomes": [{"name": "Detroit Lions", "price": 1.65}, {"name": "New England Patriots", "price": 2.35}]},
            {"key": "spreads", "outcomes": [{"name": "Detroit Lions", "price": 1.91, "point": -2.5},
                                            {"name": "New England Patriots", "price": 1.95, "point": 2.5}]},
            {"key": "totals", "outcomes": [{"name": "Over", "price": 1.9, "point": 51.5}, {"name": "Under", "price": 1.95, "point": 51.5}]}]}]}
    d = {(m, s, l): p for _, m, s, l, p, _ in oa.parse_odds(ev, two_way=True)}
    assert d[("ML", "home", None)] == 1.65
    assert d[("SPREAD", "home", -2.5)] == 1.91 and d[("SPREAD", "away", -2.5)] == 1.95
    assert d[("TOTAL", "over", 51.5)] == 1.9


def test_due_schedule(tmp_path):
    con = db.connect(tmp_path / "t.sqlite")
    now = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)
    assert oa._due(con, "basketball_nba", now + timedelta(hours=8), now)       # never fetched
    con.execute("INSERT INTO odds_api_fetches VALUES ('basketball_nba', ?, 3)", ((now - timedelta(hours=2)).isoformat(),))
    assert not oa._due(con, "basketball_nba", now + timedelta(hours=8), now)   # fetched 2h ago, game in 8h
    assert oa._due(con, "basketball_nba", now + timedelta(hours=2), now)       # final pre-game refresh
    assert not oa._due(con, "basketball_nba", now + timedelta(hours=30), now)  # already looked today


def test_book_normalisation():
    from sbi.sources.books import normalize_book
    assert normalize_book("Bet 365") == normalize_book("Bet365") == "Bet365"
    assert normalize_book("DraftKings - Live Odds") == ""
    assert normalize_book("Unibet (SE)") == normalize_book("Unibet (UK)")
