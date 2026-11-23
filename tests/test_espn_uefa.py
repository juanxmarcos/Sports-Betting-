"""Issue #114: Champions League, Europa League and Conference League games (fixtures, odds, results).

Every network call is mocked. Team names are real clubs (the name mapping is under test); kick-off
times, scores and prices below are test data."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from sbi import competitions, config, db, leagues
from sbi import parlay_estimated as pe
from sbi.sources import espn_club as ec
from sbi.sources import espn_extra
from sbi.sources import espn_uefa as eu
from sbi.sources import football_data as fd
from sbi.sources import odds_api as oa

NOW = datetime(2026, 11, 20, 15, 0, tzinfo=timezone.utc)        # Fri 10:00 New York
DAY = "2026-11-22"                                              # second preview day
E0_TEAMS = ["Man City", "Fulham", "Arsenal", "Chelsea"]
SP1_TEAMS = ["Ath Madrid", "Betis"]


def _team(home_away, display, short, score="0"):
    return {"homeAway": home_away, "score": score, "team": {"displayName": display, "shortDisplayName": short}}


def _espn_event(espn_id, date, home, away, completed=False, score=("0", "0"), state=None):
    comp = {"competitors": [_team("home", *home, score=score[0]), _team("away", *away, score=score[1])],
            "venue": {"address": {"country": "England"}},
            "odds": [{"provider": {"name": "DraftKings"},
                      "moneyline": {"home": {"close": {"odds": "-150"}}, "away": {"close": {"odds": "+400"}}},
                      "drawOdds": {"moneyLine": 300}}]}
    st = state or ("STATUS_FULL_TIME" if completed else "STATUS_SCHEDULED")
    return {"id": espn_id, "date": date, "competitions": [comp],
            "status": {"type": {"name": st, "completed": completed}}}


UCL_GAMES = [
    _espn_event("7001", f"{DAY}T17:45Z", ("Manchester City", "Man City"), ("Galatasaray", "Galatasaray")),
    _espn_event("7002", f"{DAY}T20:00Z", ("Atlético Madrid", "Atlético"), ("Arsenal", "Arsenal")),
]
UCL_BOARD = {"events": UCL_GAMES}


@pytest.fixture
def con(tmp_path, monkeypatch):
    for k, v in (("DB_PATH", tmp_path / "t.sqlite"), ("REPORTS_DIR", tmp_path / "reports"),
                 ("SITE_DIR", tmp_path / "site"), ("DATA_DIR", tmp_path / "data"), ("ROOT", tmp_path)):
        monkeypatch.setattr(config, k, v)
    c = db.connect(tmp_path / "t.sqlite")
    ko = datetime(2026, 11, 8, 15, 0, tzinfo=timezone.utc)
    for div, teams in (("E0", E0_TEAMS), ("SP1", SP1_TEAMS)):      # football-data names stored before
        for i in range(0, len(teams), 2):
            h, a = teams[i], teams[i + 1]
            c.execute("""INSERT INTO events(event_id,sport,league,season,kickoff_utc,home,away,status,home_score,
                         away_score,source,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (fd.event_id(div, ko, h, a), "football", div, "2627", ko.isoformat(), h, a, "finished", 1, 0,
                       fd.SOURCE, "t"))
    c.commit()
    return c


def _serve(monkeypatch, boards: dict):
    """boards: {(espn league, 'YYYYMMDD'): payload}; any other league-day is an empty scoreboard."""
    urls = []

    def fake_fetch(url, max_age_hours=0):
        urls.append(url)
        lg = url.split("/soccer/")[1].split("/")[0]
        d = url.split("dates=")[1]
        return json.dumps(boards.get((lg, d), {"events": []})).encode(), None
    monkeypatch.setattr(ec, "fetch", fake_fetch)
    return urls


def _ucl(con):
    return con.execute("SELECT event_id, home, away, status, home_score, away_score FROM events "
                       "WHERE league='UCL' ORDER BY kickoff_utc").fetchall()


def test_reads_the_three_uefa_scoreboards_for_the_usual_window(con, monkeypatch):
    urls = _serve(monkeypatch, {})
    out = eu.ingest(con, NOW, polite_delay=0)
    slugs = {u.split("/soccer/")[1].split("/")[0] for u in urls}
    assert slugs == {"uefa.champions", "uefa.europa", "uefa.europa.conf"}
    assert len(urls) == 3 * (ec.BACK_DAYS + ec.AHEAD_DAYS + 1)
    assert set(out["competitions"]) == {"UCL", "UEL", "UECL"} and not out["errors"]


def test_ucl_events_created_once_with_stable_ids_and_mapped_names(con, monkeypatch):
    _serve(monkeypatch, {("uefa.champions", "20261122"): UCL_BOARD})
    first = eu.ingest(con, NOW, polite_delay=0)
    assert first["created"] == 2 and first["odds"] > 0
    rows = _ucl(con)
    assert [tuple(r)[:4] for r in rows] == [
        ("football:UCL:20261122:7001", "Man City", "Galatasaray", "scheduled"),     # football-data name kept
        ("football:UCL:20261122:7002", "Ath Madrid", "Arsenal", "scheduled")]
    assert "Galatasaray" in first["competitions"]["UCL"]["unmapped"]                 # ESPN name, information only
    again = eu.ingest(con, NOW + timedelta(hours=1), polite_delay=0)                 # re-run: no duplicates
    assert again["created"] == 0 and again["competitions"]["UCL"]["existing"] == 2
    assert len(_ucl(con)) == 2
    meta = con.execute("SELECT competition FROM event_meta WHERE event_id='football:UCL:20261122:7001'").fetchone()
    assert meta[0] == "Champions League"
    dk = con.execute("""SELECT price FROM odds WHERE event_id='football:UCL:20261122:7001' AND bookmaker='DraftKings'
                        AND market='1X2' AND selection='H' AND kind='pre'""").fetchone()[0]
    assert dk == pytest.approx(1 + 100 / 150)


def test_moved_kickoff_keeps_the_same_event(con, monkeypatch):
    _serve(monkeypatch, {("uefa.champions", "20261122"): UCL_BOARD})
    eu.ingest(con, NOW, polite_delay=0)
    moved = {"events": [_espn_event("7001", "2026-11-23T20:00Z", ("Manchester City", "Man City"),
                                    ("Galatasaray", "Galatasaray"))]}
    _serve(monkeypatch, {("uefa.champions", "20261123"): moved})
    out = eu.ingest(con, NOW + timedelta(hours=1), polite_delay=0)
    assert out["created"] == 0
    r = con.execute("SELECT kickoff_utc FROM events WHERE event_id='football:UCL:20261122:7001'").fetchone()
    assert r[0] == "2026-11-23T20:00:00+00:00" and len(_ucl(con)) == 2


def test_competition_labels():
    assert competitions.competition_name(event_id="football:UCL:20261122:7001") == "Champions League"
    assert competitions.competition_name("UEL") == "Europa League"
    assert competitions.competition_name("UECL") == "Conference League"
    assert leagues.status("UCL") == "uefa_club" and "UCL" not in leagues.active()


def test_finished_ucl_scoreboard_settles_a_leg(con, monkeypatch):
    _serve(monkeypatch, {("uefa.champions", "20261122"): UCL_BOARD})
    eu.ingest(con, NOW, polite_delay=0)
    leg = {"event_id": "football:UCL:20261122:7001", "market": "1X2", "selection": "H"}
    ou = {"event_id": "football:UCL:20261122:7001", "market": "OU", "selection": "over", "line": 2.5}
    assert pe.leg_result(con, leg) == "open"
    done = {"events": [_espn_event("7001", f"{DAY}T17:45Z", ("Manchester City", "Man City"),
                                   ("Galatasaray", "Galatasaray"), completed=True, score=("3", "1"))]}
    later = datetime(2026, 11, 23, 15, 0, tzinfo=timezone.utc)
    _serve(monkeypatch, {("uefa.champions", "20261122"): done})
    out = eu.ingest(con, later, polite_delay=0)
    assert out["results_filled"] == 1
    assert pe.leg_result(con, leg) == "won" and pe.leg_result(con, ou) == "won"
    assert pe.leg_result(con, {**leg, "selection": "A"}) == "lost"


def test_extra_time_result_is_not_filled_automatically(con, monkeypatch):
    _serve(monkeypatch, {("uefa.champions", "20261122"): UCL_BOARD})
    eu.ingest(con, NOW, polite_delay=0)
    aet = {"events": [_espn_event("7002", f"{DAY}T20:00Z", ("Atlético Madrid", "Atlético"), ("Arsenal", "Arsenal"),
                                  completed=True, score=("2", "1"), state="STATUS_FINAL_AET")]}
    _serve(monkeypatch, {("uefa.champions", "20261122"): aet})
    out = eu.ingest(con, datetime(2026, 11, 23, 15, 0, tzinfo=timezone.utc), polite_delay=0)
    assert out["results_filled"] == 0
    assert out["competitions"]["UCL"]["extra_time_skipped"] == ["football:UCL:20261122:7002"]
    r = con.execute("SELECT status, home_score FROM events WHERE event_id='football:UCL:20261122:7002'").fetchone()
    assert tuple(r) == ("scheduled", None)


def test_unknown_past_games_are_not_created(con, monkeypatch):
    done = {"events": [_espn_event("7009", "2026-11-19T20:00Z", ("Chelsea", "Chelsea"), ("Ajax", "Ajax"),
                                   completed=True, score=("1", "1"))]}
    _serve(monkeypatch, {("uefa.champions", "20261119"): done})
    out = eu.ingest(con, NOW, polite_delay=0)
    assert out["created"] == 0 and out["competitions"]["UCL"]["skipped_past"] == 1 and not _ucl(con)


def test_uefa_games_get_price_only_espn_summaries(con, monkeypatch):
    _serve(monkeypatch, {("uefa.champions", "20261122"): UCL_BOARD})
    eu.ingest(con, NOW, polite_delay=0)
    seen = []

    def fake_summary(path, espn_id):
        seen.append((path, espn_id))
        return {"odds": [{"provider": {"name": "Bet365"}, "homeTeamOdds": {"moneyLine": -140},
                          "awayTeamOdds": {"moneyLine": 380}, "drawOdds": {"moneyLine": 290}}]}
    monkeypatch.setattr(espn_extra, "_summary", fake_summary)
    out = espn_extra.enrich_events(con, NOW)
    assert sorted(seen) == [("soccer/uefa.champions", "7001"), ("soccer/uefa.champions", "7002")]
    assert out["club_odds"] == 6


# ---------- The Odds API ----------
def _odds_api_event(home, away, commence, h=1.62, d=4.2, a=5.2, totals=True):
    def bk(key, title, dh):
        mk = [{"key": "h2h", "outcomes": [{"name": home, "price": h + dh}, {"name": away, "price": a},
                                          {"name": "Draw", "price": d}]}]
        if totals:
            mk.append({"key": "totals", "outcomes": [{"name": "Over", "price": 1.80, "point": 2.5},
                                                     {"name": "Under", "price": 2.05, "point": 2.5}]})
        return {"key": key, "title": title, "last_update": "2026-11-20T14:00:00Z", "markets": mk}
    return {"home_team": home, "away_team": away, "commence_time": commence,
            "bookmakers": [bk("pinnacle", "Pinnacle", 0.0), bk("unibet_uk", "Unibet", -0.02),
                           bk("williamhill", "William Hill", -0.03), bk("betvictor", "BetVictor", 0.03)]}


UCL_ODDS = [_odds_api_event("Manchester City", "Galatasaray", f"{DAY}T17:45:00Z"),
            _odds_api_event("Atletico Madrid", "Arsenal", f"{DAY}T20:00:00Z", h=2.3, d=3.4, a=3.1, totals=False)]


def _fake_odds_api(monkeypatch, odds_calls, sports=("soccer_uefa_champs_league",)):
    def fake_get(path, params, api_key):
        u = {"remaining": "400", "used": "100", "last": "0"}
        if path == "/sports":
            return [{"key": k, "active": True} for k in sports], u
        if path.endswith("/events"):
            return UCL_ODDS, u
        odds_calls.append(path)
        return UCL_ODDS, {**u, "last": "2"}
    monkeypatch.setenv("ODDS_API_KEY", "dummy")
    monkeypatch.setattr(oa, "_get", fake_get)


def test_odds_api_map_has_the_uefa_keys_and_the_budget_is_unchanged():
    assert oa.UEFA == {"soccer_uefa_champs_league": "UCL", "soccer_uefa_europa_league": "UEL",
                       "soccer_uefa_europa_conference_league": "UECL"}
    assert (oa.MAX_CREDITS_PER_RUN, oa.MAX_CREDITS_PER_DAY, oa.UNKNOWN_REMAINING_CAP, oa.MORNING_SHARE,
            oa.RESERVE, oa.MARKETS, oa.REGIONS) == (40, 40, 12, 0.5, 20, "h2h,totals", "eu")
    assert oa.budget(400, NOW, 0, "evening") == 34 and oa.budget(None, NOW, 0, "morning") == 6


def test_odds_api_buys_ucl_odds_only_when_events_are_stored(con, monkeypatch):
    calls = []
    _fake_odds_api(monkeypatch, calls)
    before = oa.ingest(con, NOW)
    assert before["skipped_no_matching_event"] == ["soccer_uefa_champs_league"] and not calls
    _serve(monkeypatch, {("uefa.champions", "20261122"): UCL_BOARD})
    eu.ingest(con, NOW, polite_delay=0)
    out = oa.ingest(con, NOW + timedelta(minutes=5))
    assert calls == ["/sports/soccer_uefa_champs_league/odds"] and out["matched"] == 2
    assert out["credits_spent"] == 2


def test_preview_parlay_includes_a_ucl_leg_at_market_consensus(con, monkeypatch):
    _serve(monkeypatch, {("uefa.champions", "20261122"): UCL_BOARD})
    eu.ingest(con, NOW, polite_delay=0)
    _fake_odds_api(monkeypatch, [])
    oa.ingest(con, NOW)
    p = pe.build_preview(con, NOW + timedelta(minutes=5), DAY)
    assert p["coverage"]["by_sport"]["soccer"] == {"events": 2, "with_prices": 2}
    assert p["recommendations"], p["coverage"]
    legs = [x for r in p["recommendations"] for x in r["legs"]]
    ucl = [x for x in legs if x["league"] == "UCL"]
    assert ucl and all(x["prob_source"] == "market_consensus" for x in ucl)
    assert all(x["prob_note"] == "Probability: market consensus" for x in ucl)
    assert all(x["price_books"] >= 2 for x in ucl)
    for x in ucl:
        competitions.label(x)
        assert x["competition_name"] == "Champions League"
    for r in p["recommendations"]:                   # at most one leg per game; per-size minimum odds
        assert len({x["event_id"] for x in r["legs"]}) == len(r["legs"])
        assert r["estimated_odds"] >= pe.min_odds(len(r["legs"]))


def test_ucl_extra_markets_use_the_market_consensus(con, monkeypatch):
    _serve(monkeypatch, {("uefa.champions", "20261122"): UCL_BOARD})
    eu.ingest(con, NOW, polite_delay=0)
    _fake_odds_api(monkeypatch, [])
    oa.ingest(con, NOW)
    pool, _ = pe.build_pool(con, NOW + timedelta(minutes=5), DAY, every=True)
    ou = [x for x in pool if x["event_id"] == "football:UCL:20261122:7001" and x["market"] == "OU"]
    assert ou and all(x["prob_source"] == "market_consensus" and x["model_prob"] is None for x in ou)
    assert all(x["prob_note"] == "Probability: market consensus" for x in ou)
    # a domestic game without a model still offers no extra-market leg (unchanged rule)
    ev = {"event_id": "football:E0:x", "league": "E0", "site_sport": "soccer", "home": "A", "away": "B",
          "kickoff_utc": f"{DAY}T17:45:00+00:00"}
    books = {("OU", 2.5): {"Pinnacle": {"over": 1.8, "under": 2.05}, "Unibet": {"over": 1.8, "under": 2.05}}}
    legs, reasons = pe.extra_market_legs(ev, books, {})
    assert not legs and reasons["OU: no model probability"] == 2


def test_uefa_games_are_never_modelled(con, monkeypatch):
    from sbi import pipeline
    _serve(monkeypatch, {("uefa.champions", "20261122"): UCL_BOARD})
    eu.ingest(con, NOW, polite_delay=0)
    s = pipeline.analyse(con, NOW)
    assert "UCL" not in s["monitoring_only_events"] and "UCL" not in s["leagues"]
    assert con.execute("SELECT COUNT(*) FROM predictions WHERE event_id LIKE 'football:UCL:%'").fetchone()[0] == 0
