import json
from datetime import datetime, timedelta, timezone

import pytest

from sbi import db
from sbi.sources import espn_extra as ex


@pytest.fixture
def con(tmp_path):
    return db.connect(tmp_path / "t.sqlite")


def _inj(players):
    return json.dumps({"injuries": [{"displayName": "Philadelphia 76ers", "injuries": [
        {"status": s, "shortComment": "c", "date": "2026-11-12T10:00Z", "athlete": {"displayName": p}} for p, s in players]}]}).encode()


def test_injury_change_log(con, monkeypatch):
    seq = iter([_inj([("LeBron James", "Questionable")]), _inj([("LeBron James", "Out")]), _inj([])])
    monkeypatch.setattr(ex, "fetch", lambda url, max_age_hours: (next(seq), None))
    assert ex.injuries(con, "nba")["changes"] == 1
    assert ex.injuries(con, "nba")["changes"] == 1          # Questionable -> Out
    assert ex.injuries(con, "nba")["changes"] == 1          # cleared
    rows = [tuple(r) for r in con.execute("SELECT player, old_status, new_status FROM injury_changes ORDER BY id")]
    assert rows == [("LeBron James", None, "Questionable"), ("LeBron James", "Questionable", "Out"), ("LeBron James", "Out", "Cleared")]


def test_enrich_forecast_lineups_extra_books(con, monkeypatch):
    now = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)
    ko = (now + timedelta(hours=5)).isoformat()
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,updated_at)
                   VALUES ('football:INT:uefa.nations:20261113:77','football','INT:uefa.nations',?,'Norway','Wales','scheduled','t','t')""", (ko,))
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,updated_at)
                   VALUES ('nba:NBA:20261113:88','nba','NBA',?,'Philadelphia 76ers','Toronto Raptors','scheduled','t','t')""", (ko,))
    soccer = {"predictor": {"homeTeam": {"gameProjection": "62.0"}, "awayTeam": {"gameProjection": "16.0"}},
              "odds": [{"provider": {"name": "Bet 365"}, "homeTeamOdds": {"moneyLine": -250}, "awayTeamOdds": {"moneyLine": 650},
                        "drawOdds": {"moneyLine": 375}},
                       {"provider": {"name": "DraftKings - Live Odds"}, "homeTeamOdds": {"moneyLine": -200},
                        "awayTeamOdds": {"moneyLine": 500}, "drawOdds": {"moneyLine": 300}}],
              "rosters": [{"team": {"displayName": t}, "roster": [{"starter": True, "athlete": {"displayName": f"{t}{i}"}} for i in range(11)]}
                          for t in ("Norway", "Wales")]}
    nba = {"predictor": {"homeTeam": {"gameProjection": "72.7"}, "awayTeam": {"gameProjection": "27.3"}},
           "leaders": [{"team": {"displayName": "Philadelphia 76ers"}, "leaders": [{"name": "points", "leaders": [{"athlete": {"displayName": "LeBron James"}}]}]}]}
    monkeypatch.setattr(ex, "fetch", lambda url, max_age_hours: (json.dumps(soccer if "soccer" in url else nba).encode(), None))
    out = ex.enrich_events(con, now)
    assert out["forecasts"] == 2 and out["lineups"] == 2 and out["extra_odds"] == 3   # live feed excluded
    assert {r[0] for r in con.execute("SELECT DISTINCT bookmaker FROM odds")} == {"Bet365"}
    con.execute("INSERT INTO injuries_current VALUES ('nba','Philadelphia 76ers','LeBron James','Out','','','t','u')")
    ctx = ex.context_for(con, "nba:NBA:20261113:88", "nba", "Philadelphia 76ers", "Toronto Raptors")
    assert ctx["injuries"]["Philadelphia 76ers"][0] == {"player": "LeBron James", "status": "Out", "key": True}
    assert ctx["external_forecast"]["probs"]["Philadelphia 76ers"] == pytest.approx(0.727)
    sc = ex.context_for(con, "football:INT:uefa.nations:20261113:77", "soccer", "Norway", "Wales")
    assert sc["lineups_confirmed"] is True and sc["external_forecast"]["probs"]["Draw"] == pytest.approx(0.22)
