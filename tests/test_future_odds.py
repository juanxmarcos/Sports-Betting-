"""Issue #61: free prices for the 3-day parlay previews.

ESPN scoreboards for today and the next three New York dates are stored as normal `pre` quotes
with their real retrieval time, previews are built from them with the #58 rules, and every run
reports how many requests it sent. All network calls are mocked. Every game, team and price here is
test data (tests/fixtures/espn_scoreboard)."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sbi import config, db, us
from sbi import parlay_estimated as pe
from sbi.sources import espn_extra, http

FIX = Path(__file__).parent / "fixtures" / "espn_scoreboard"
NOW = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)          # 10:00 in New York
RETRIEVED = (NOW - timedelta(minutes=10)).isoformat()
PREVIEW_DAYS = ["2026-11-14", "2026-11-15", "2026-11-16"]


@pytest.fixture
def con(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(db, "utcnow", lambda: RETRIEVED)

    def no_network(*a, **k):
        raise AssertionError("tests must not touch the network")
    monkeypatch.setattr(http.requests, "get", no_network)
    return db.connect(tmp_path / "t.sqlite")


def _fixture_fetch(url, max_age_hours=0.0):
    d = url.rsplit("dates=", 1)[1]
    p = FIX / f"nba_{d}.json"
    return (p.read_bytes() if p.exists() else b'{"events": []}'), None


def _model(con, prob_home=0.50):
    """Stand-in for `us.analyse`: a stored model probability for every scheduled NBA game."""
    run = "nba-points-0.1:NBA:test"
    con.execute("INSERT OR IGNORE INTO model_runs VALUES (?,?,?,?,?,?,?)",
                (run, "nba-points-0.1", "NBA", NOW.isoformat(), 500, "{}", RETRIEVED))
    for (eid,) in con.execute("SELECT event_id FROM events WHERE league='NBA'").fetchall():
        for sel, p in (("home", prob_home), ("away", 1 - prob_home)):
            con.execute("""INSERT INTO predictions(run_id,event_id,market,selection,line,model_prob,created_at)
                           VALUES (?,?,?,?,?,?,?)""", (run, eid, "ML", sel, None, p, RETRIEVED))
    con.commit()


def test_future_scoreboards_fill_the_odds_table_and_the_previews(con, monkeypatch):
    monkeypatch.setattr(us, "fetch", _fixture_fetch)
    out = us.ingest(con, NOW, "nba")
    assert out["events"] == 8 and out["odds"] == 16 and out["errors"] == []
    rows = con.execute("""SELECT e.kickoff_utc, o.kind, o.source, o.retrieved_at, o.bookmaker FROM odds o
                          JOIN events e USING(event_id)""").fetchall()
    assert {r["kind"] for r in rows} == {"pre"}
    assert {r["source"] for r in rows} == {"espn.com (public scoreboard)"}
    assert {r["retrieved_at"] for r in rows} == {RETRIEVED}           # the real retrieval time
    future = {pe._ny_day(datetime.fromisoformat(r["kickoff_utc"])) for r in rows}
    assert set(PREVIEW_DAYS) <= future

    _model(con)
    previews = pe.build_previews(con, NOW)
    assert [p["date"] for p in previews] == PREVIEW_DAYS
    for p in previews:
        cov = p["coverage"]
        assert cov["events_today"] == 2 and cov["events_with_fresh_prices"] == 2
        assert cov["by_sport"] == {"nba": {"events": 2, "with_prices": 2}}
        [card] = p["recommendations"]                               # one bookmaker is enough (#58)
        assert card["preview"] is True and card["bookmaker"] == "DraftKings" and card["n_legs"] == 2
        assert card["estimated_odds"] == pytest.approx(2.2 * 2.2)
        assert card["prices_at"] == RETRIEVED
        assert pe.card_problem(card, NOW, p["date"], preview=True) is None


def test_inserting_again_never_rewrites_a_stored_quote(con, monkeypatch):
    monkeypatch.setattr(us, "fetch", _fixture_fetch)
    us.ingest(con, NOW, "nba")
    before = [tuple(r) for r in con.execute("SELECT * FROM odds ORDER BY id")]
    us.ingest(con, NOW, "nba")                                       # a second read of the same scoreboards
    after = [tuple(r) for r in con.execute("SELECT * FROM odds ORDER BY id")]
    assert after[:len(before)] == before                             # insert-only: stored rows untouched


def test_todays_estimated_block_has_no_by_sport_breakdown(con, monkeypatch):
    """Today's coverage and cards are built exactly as before (#61 changes previews only)."""
    monkeypatch.setattr(us, "fetch", _fixture_fetch)
    us.ingest(con, NOW, "nba")
    _model(con)
    block = pe.build(con, NOW)
    assert "by_sport" not in block["coverage"] and block["coverage"]["events_today"] == 2


# ---------- ESPN game summaries on preview days ----------

def _summary(pickcenter=True):
    s = {"predictor": {"homeTeam": {"gameProjection": "55.0"}, "awayTeam": {"gameProjection": "45.0"}},
         "leaders": [], "pickcenter": []}
    if pickcenter:
        s["pickcenter"] = [{"provider": {"name": "DraftKings"},
                            "homeTeamOdds": {"moneyLine": 120}, "awayTeamOdds": {"moneyLine": -140}},
                           {"provider": {"name": "DraftKings Live Odds"},
                            "homeTeamOdds": {"moneyLine": 300}, "awayTeamOdds": {"moneyLine": -400}}]
    return s


def _event(con, eid, ko):
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""", (eid, "nba", "NBA", ko.isoformat(), "H", "A", "scheduled", "t", RETRIEVED))


def test_summary_prices_are_read_for_preview_days_only(con, monkeypatch):
    calls = []
    monkeypatch.setattr(espn_extra, "_summary", lambda path, i: calls.append(i) or _summary())
    _event(con, "nba:NBA:20261114:1", NOW + timedelta(hours=8, minutes=30))     # today, 18:30 New York
    _event(con, "nba:NBA:20261115:2", NOW + timedelta(hours=34))                # tomorrow, inside 36h
    _event(con, "nba:NBA:20261117:3", NOW + timedelta(days=3, hours=9))         # +3, preview only
    _event(con, "nba:NBA:20261118:4", NOW + timedelta(days=4, hours=9))         # +4, outside every window
    con.commit()
    out = espn_extra.enrich_events(con, NOW)
    assert sorted(calls) == ["1", "2", "3"]
    assert out["summaries"] == 2 and out["preview_summaries"] == 1 and out["preview_odds"] == 4
    quotes = con.execute("SELECT event_id, bookmaker, selection, price, source, retrieved_at FROM odds").fetchall()
    assert {q["event_id"] for q in quotes} == {"nba:NBA:20261115:2", "nba:NBA:20261117:3"}   # never today's game
    assert {q["bookmaker"] for q in quotes} == {"DraftKings"}                                # live lines skipped
    assert {q["source"] for q in quotes} == {"espn.com (game summary)"}
    assert {(q["selection"], round(q["price"], 4)) for q in quotes} == {("home", 2.2), ("away", round(1 + 100 / 140, 4))}
    forecasts = {r[0] for r in con.execute("SELECT event_id FROM external_forecasts")}
    assert forecasts == {"nba:NBA:20261114:1", "nba:NBA:20261115:2"}       # preview-only games: prices only


def test_preview_end_is_midnight_after_the_third_new_york_day():
    assert espn_extra.preview_end(NOW).isoformat() == "2026-11-17T00:00:00-05:00"


# ---------- request counts ----------

class _Resp:
    status_code = 200
    content = b"{}"
    headers = {}

    def raise_for_status(self):
        pass


def test_fetch_counts_network_and_cache_by_host(con, monkeypatch):
    monkeypatch.setattr(http.requests, "get", lambda *a, **k: _Resp())
    http.reset_stats()
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20261114"
    http.fetch(url, max_age_hours=1)
    http.fetch(url, max_age_hours=1)
    s = http.stats()
    assert (s["network"], s["cache"], s["stale"]) == (1, 1, 0)
    assert s["by_host"] == {"site.api.espn.com": {"network": 1, "cache": 1, "stale": 0}}


def test_odds_api_requests_are_counted_without_the_key(monkeypatch):
    from sbi.sources import odds_api

    class R(_Resp):
        headers = {"x-requests-remaining": "100"}

        def json(self):
            return []
    monkeypatch.setattr(odds_api.requests, "get", lambda *a, **k: R())
    http.reset_stats()
    odds_api._get("/sports", {}, "SECRET-KEY")
    s = http.stats()
    assert s["by_host"] == {"api.the-odds-api.com": {"network": 1, "cache": 0, "stale": 0}}
    assert "SECRET-KEY" not in json.dumps(s)
