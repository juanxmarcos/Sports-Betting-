"""Issue #66: upcoming club-soccer fixtures from the ESPN scoreboard.

Every network call is mocked. Team names are real Premier League clubs (the name mapping is what is
under test); kick-off times, scores and prices below are test data."""
import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from sbi import config, db
from sbi import parlay_estimated as pe
from sbi.sources import espn_club as ec
from sbi.sources import espn_extra
from sbi.sources import football_data as fd
from sbi.sources import odds_api as oa

NOW = datetime(2026, 11, 18, 15, 0, tzinfo=timezone.utc)        # Wed 10:00 New York (morning run)
SAT = "2026-11-21"                                              # third preview day
E0_TEAMS = ["Man United", "Tottenham", "Nott'm Forest", "Bournemouth", "Man City", "Fulham", "Arsenal", "Chelsea"]


def _team(home_away, display, short, score="0"):
    return {"homeAway": home_away, "score": score, "team": {"displayName": display, "shortDisplayName": short}}


def _espn_event(espn_id, date, home, away, completed=False, score=("0", "0"), odds=True):
    comp = {"competitors": [_team("home", *home, score=score[0]), _team("away", *away, score=score[1])],
            "venue": {"address": {"country": "England"}}}
    if odds:
        comp["odds"] = [{"provider": {"name": "DraftKings"},
                         "moneyline": {"home": {"close": {"odds": "-110"}}, "away": {"close": {"odds": "+250"}}},
                         "drawOdds": {"moneyLine": 260}}]
    return {"id": espn_id, "date": date, "competitions": [comp],
            "status": {"type": {"name": "STATUS_FULL_TIME" if completed else "STATUS_SCHEDULED",
                                "completed": completed}}}


UPCOMING = {"events": [
    _espn_event("901", f"{SAT}T12:30Z", ("Manchester United", "Man Utd"), ("Tottenham Hotspur", "Spurs")),
    _espn_event("902", f"{SAT}T15:00Z", ("AFC Bournemouth", "Bournemouth"), ("Nottingham Forest", "Nottm Forest")),
    _espn_event("903", f"{SAT}T17:30Z", ("Wrexham", "Wrexham"), ("Arsenal", "Arsenal")),    # not an E0 team
]}


@pytest.fixture
def con(tmp_path, monkeypatch):
    for k, v in (("DB_PATH", tmp_path / "t.sqlite"), ("REPORTS_DIR", tmp_path / "reports"),
                 ("SITE_DIR", tmp_path / "site"), ("DATA_DIR", tmp_path / "data"), ("ROOT", tmp_path)):
        monkeypatch.setattr(config, k, v)
    c = db.connect(tmp_path / "t.sqlite")
    ko = datetime(2026, 11, 8, 15, 0, tzinfo=timezone.utc)
    for i in range(0, len(E0_TEAMS), 2):            # football-data has stored these E0 teams before
        h, a = E0_TEAMS[i], E0_TEAMS[i + 1]
        c.execute("""INSERT INTO events(event_id,sport,league,season,kickoff_utc,home,away,status,home_score,away_score,
                     source,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (fd.event_id("E0", ko, h, a), "football", "E0", "2627", ko.isoformat(), h, a, "finished", 1, 0,
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


def _club(con):
    return con.execute("SELECT event_id, home, away, status, home_score, away_score, source FROM events "
                       "WHERE league='E0' AND status='scheduled' ORDER BY kickoff_utc").fetchall()


def test_resolve_uses_aliases_short_names_and_accents_never_guesses():
    known = {"Man United", "Bournemouth", "Alaves", "Dundee", "Dundee United", "Ath Madrid"}
    assert ec.resolve("Manchester United", "Man Utd", known) == "Man United"
    assert ec.resolve("AFC Bournemouth", "Bournemouth", known) == "Bournemouth"     # ESPN short name
    assert ec.resolve("Alavés", "Alavés", known) == "Alaves"                        # accents ignored
    assert ec.resolve("Atlético Madrid", "Atlético", known) == "Ath Madrid"
    assert ec.resolve("Dundee United", "Dundee Utd", known) == "Dundee United"      # exact, not "Dundee"
    assert ec.resolve("Wrexham", "Wrexham", known) is None                          # not a known team
    assert ec.resolve("Manchester City", "Man City", known) is None                 # alias target not in league


def test_every_active_league_has_an_espn_slug():
    assert set(ec.ESPN_LEAGUES) == set(config.FOOTBALL_LEAGUES)


def test_creates_club_events_once_with_football_data_ids(con, monkeypatch):
    urls = _serve(monkeypatch, {("eng.1", "20261121"): UPCOMING})
    out = ec.ingest(con, NOW, polite_delay=0)
    assert out["created"] == 2 and out["leagues"]["E0"]["unmapped"] == ["Wrexham"]
    rows = _club(con)
    assert [(r["home"], r["away"]) for r in rows] == [("Man United", "Tottenham"), ("Bournemouth", "Nott'm Forest")]
    assert rows[0]["event_id"] == "football:E0:20261121:man-united:tottenham"
    assert rows[0]["event_id"] == fd.event_id("E0", datetime(2026, 11, 21, 12, 30, tzinfo=timezone.utc),
                                              "Man United", "Tottenham")
    # DraftKings 1X2 from the scoreboard is stored as a pre-match quote
    px = {r["selection"]: r["price"] for r in con.execute(
        "SELECT selection, price FROM odds WHERE event_id=? AND market='1X2'", (rows[0]["event_id"],))}
    assert px == pytest.approx({"H": 1 + 100 / 110, "A": 3.5, "D": 3.6})
    # one request per league-day (2 days back, today, 7 ahead); a league with no stored football-data
    # teams to map names to is reported and not read
    assert len(urls) == 10 and all("/soccer/eng.1/" in u for u in urls)
    assert any(e.startswith("E1: no stored football-data teams") for e in out["errors"])
    n = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    again = ec.ingest(con, NOW + timedelta(hours=12), polite_delay=0)
    assert again["created"] == 0 and con.execute("SELECT COUNT(*) FROM events").fetchone()[0] == n


def _fd_frame(rows):
    """A football-data style frame: Div, Date (UK), Time (UK), teams, optional goals."""
    return pd.DataFrame([{"Div": "E0", "Date": d, "Time": t, "HomeTeam": h, "AwayTeam": a, "FTHG": hg, "FTAG": ag}
                         for d, t, h, a, hg, ag in rows])


def test_football_data_result_updates_the_same_event(con, monkeypatch):
    _serve(monkeypatch, {("eng.1", "20261121"): UPCOMING})
    ec.ingest(con, NOW, polite_delay=0)
    n = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    m = fd.parse_matches(_fd_frame([("21/11/2026", "12:30", "Man United", "Tottenham", 2, 1)]))
    fd.upsert_events(con, m, "https://www.football-data.co.uk/mmz4281/2627/E0.csv", finished=True)
    assert con.execute("SELECT COUNT(*) FROM events").fetchone()[0] == n
    r = con.execute("SELECT status, home_score, away_score, source FROM events "
                    "WHERE event_id='football:E0:20261121:man-united:tottenham'").fetchone()
    assert tuple(r) == ("finished", 2, 1, fd.SOURCE)


def test_moved_kickoff_on_football_data_merges_into_the_espn_event(con, monkeypatch):
    _serve(monkeypatch, {("eng.1", "20261121"): UPCOMING})
    ec.ingest(con, NOW, polite_delay=0)
    n = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    # football-data lists the game a day later (moved to Sunday): a different ID, still the same game
    m = fd.parse_matches(_fd_frame([("22/11/2026", "16:30", "Bournemouth", "Nott'm Forest", None, None)]))
    m["hg"], m["ag"] = float("nan"), float("nan")
    fd.upsert_events(con, m, "https://www.football-data.co.uk/fixtures.csv", finished=False)
    assert con.execute("SELECT COUNT(*) FROM events").fetchone()[0] == n
    eid = "football:E0:20261121:bournemouth:nott-m-forest"
    assert m["event_id"].iloc[0] == eid                       # odds inserted next attach to the same event
    assert con.execute("SELECT kickoff_utc FROM events WHERE event_id=?", (eid,)).fetchone()[0] == \
        "2026-11-22T16:30:00+00:00"
    # ESPN still lists the old time: it no longer moves an event football-data has taken over
    ec.ingest(con, NOW + timedelta(hours=12), polite_delay=0)
    assert con.execute("SELECT kickoff_utc FROM events WHERE event_id=?", (eid,)).fetchone()[0] == \
        "2026-11-22T16:30:00+00:00"


def test_espn_final_score_settles_an_espn_created_game(con, monkeypatch):
    _serve(monkeypatch, {("eng.1", "20261121"): UPCOMING})
    ec.ingest(con, NOW, polite_delay=0)
    done = {"events": [_espn_event("901", f"{SAT}T12:30Z", ("Manchester United", "Man Utd"),
                                   ("Tottenham Hotspur", "Spurs"), completed=True, score=("3", "1"))]}
    later = datetime(2026, 11, 22, 15, 0, tzinfo=timezone.utc)
    _serve(monkeypatch, {("eng.1", "20261121"): done})
    out = ec.ingest(con, later, polite_delay=0)
    assert out["results_filled"] == 1
    r = con.execute("SELECT status, home_score, away_score FROM events "
                    "WHERE event_id='football:E0:20261121:man-united:tottenham'").fetchone()
    assert tuple(r) == ("finished", 3, 1)
    # a football-data score already stored is never overwritten by ESPN
    ko = datetime(2026, 11, 8, 15, 0, tzinfo=timezone.utc)
    old = {"events": [_espn_event("800", "2026-11-08T15:00Z", ("Manchester United", "Man Utd"),
                                  ("Tottenham Hotspur", "Spurs"), completed=True, score=("0", "4"))]}
    _serve(monkeypatch, {("eng.1", "20261108"): old})
    ec.ingest(con, datetime(2026, 11, 9, 12, tzinfo=timezone.utc), polite_delay=0)
    r = con.execute("SELECT home_score, away_score FROM events WHERE event_id=?",
                    (fd.event_id("E0", ko, "Man United", "Tottenham"),)).fetchone()
    assert tuple(r) == (1, 0)


def test_settlement_uses_the_espn_result(con, monkeypatch):
    from sbi import settle
    _serve(monkeypatch, {("eng.1", "20261121"): UPCOMING})
    ec.ingest(con, NOW, polite_delay=0)
    eid = "football:E0:20261121:man-united:tottenham"
    con.execute("""INSERT INTO recommendations(rec_id,event_id,published_at,sport,league,kickoff_utc,home,away,market,
                   selection,line,bookmaker,odds,model_prob,final_prob,fair_odds,ev,ev_lower,stake_units,model_version)
                   VALUES ('r1',?,?,'football','E0','2026-11-21T12:30:00+00:00','Man United','Tottenham','1X2','H',NULL,
                   'Bet365',2.0,0.55,0.55,1.82,0.1,0.05,1,'t')""", (eid, NOW.isoformat()))
    done = {"events": [_espn_event("901", f"{SAT}T12:30Z", ("Manchester United", "Man Utd"),
                                   ("Tottenham Hotspur", "Spurs"), completed=True, score=("2", "0"))]}
    later = datetime(2026, 11, 22, 15, 0, tzinfo=timezone.utc)
    _serve(monkeypatch, {("eng.1", "20261121"): done})
    ec.ingest(con, later, polite_delay=0)
    assert settle.settle_all(con, later)["settled"] == 1
    assert con.execute("SELECT status FROM recommendations WHERE rec_id='r1'").fetchone()[0] == "won"


def _odds_api_event(home, away, commence, soft_home=2.25):
    def bk(key, title, h, d, a):
        return {"key": key, "title": title, "last_update": "2026-11-18T14:00:00Z",
                "markets": [{"key": "h2h", "outcomes": [{"name": home, "price": h}, {"name": away, "price": a},
                                                        {"name": "Draw", "price": d}]}]}
    return {"home_team": home, "away_team": away, "commence_time": commence,
            "bookmakers": [bk("pinnacle", "Pinnacle", 2.0, 3.6, 3.9), bk("unibet_uk", "Unibet", 1.98, 3.5, 3.8),
                           bk("williamhill", "William Hill", 1.97, 3.5, 3.8),
                           bk("betvictor", "BetVictor", soft_home, 3.4, 3.6)]}


EPL = [_odds_api_event("Manchester United", "Tottenham Hotspur", f"{SAT}T12:30:00Z"),
       _odds_api_event("AFC Bournemouth", "Nottingham Forest", f"{SAT}T15:00:00Z")]


def _fake_odds_api(monkeypatch, odds_calls, sports=("soccer_epl",), payload=None):
    def fake_get(path, params, api_key):
        u = {"remaining": "400", "used": "100", "last": "0"}
        if path == "/sports":
            return [{"key": k, "active": True} for k in sports], u
        if path.endswith("/events"):
            return (payload or {}).get(path.split("/")[2], EPL), u
        odds_calls.append(path)
        return (payload or {}).get(path.split("/")[2], EPL), {**u, "last": "2"}
    monkeypatch.setenv("ODDS_API_KEY", "dummy")
    monkeypatch.setattr(oa, "_get", fake_get)


def test_odds_api_matches_the_new_club_events(con, monkeypatch):
    calls = []
    _fake_odds_api(monkeypatch, calls)
    before = oa.ingest(con, NOW)                              # no upcoming E0 events stored yet
    assert before["skipped_no_matching_event"] == ["soccer_epl"] and not calls
    _serve(monkeypatch, {("eng.1", "20261121"): UPCOMING})
    ec.ingest(con, NOW, polite_delay=0)
    out = oa.ingest(con, NOW + timedelta(minutes=5))
    assert out["skipped_no_matching_event"] == [] and out["matched"] == 2 and calls == ["/sports/soccer_epl/odds"]
    n = con.execute("""SELECT COUNT(DISTINCT bookmaker) FROM odds WHERE source=? AND
                       event_id='football:E0:20261121:man-united:tottenham'""", (oa.SOURCE,)).fetchone()[0]
    assert n == 4


def test_preview_day_with_priced_club_games_gets_a_preview_parlay(con, monkeypatch):
    _serve(monkeypatch, {("eng.1", "20261121"): UPCOMING})
    ec.ingest(con, NOW, polite_delay=0)
    _fake_odds_api(monkeypatch, [])
    oa.ingest(con, NOW)
    p = pe.build_preview(con, NOW + timedelta(minutes=5), SAT)
    assert p["coverage"]["by_sport"]["soccer"] == {"events": 2, "with_prices": 2}
    [r] = p["recommendations"]
    assert r["preview"] is True and len(r["legs"]) == 2 and r["price_basis"] == "consensus"
    assert all(x["price_books"] >= 2 for x in r["legs"])            # issue #112: typical price, 2+ books
    cov = pe.preview_coverage(con, NOW + timedelta(minutes=5))
    assert list(cov) == ["2026-11-19", "2026-11-20", SAT]
    assert cov[SAT]["events"] == 2 and cov[SAT]["with_prices"] == 2 and cov["2026-11-19"]["events"] == 0
    assert pe.coverage_line(SAT, cov[SAT]) == f"{SAT}: 2 events, 2 with prices (soccer 2/2)"
    assert pe.coverage_line("2026-11-19", cov["2026-11-19"]) == "2026-11-19: 0 events, 0 with prices"


def test_club_games_get_price_only_espn_summaries(con, monkeypatch):
    _serve(monkeypatch, {("eng.1", "20261121"): UPCOMING})
    ec.ingest(con, NOW, polite_delay=0)
    seen = []

    def fake_summary(path, espn_id):
        seen.append((path, espn_id))
        return {"odds": [{"provider": {"name": "Bet365"}, "homeTeamOdds": {"moneyLine": 120},
                          "awayTeamOdds": {"moneyLine": 200}, "drawOdds": {"moneyLine": 250}}],
                "predictor": {"homeTeam": {"gameProjection": "50"}, "awayTeam": {"gameProjection": "25"}}}
    monkeypatch.setattr(espn_extra, "_summary", fake_summary)
    out = espn_extra.enrich_events(con, NOW)
    assert sorted(seen) == [("soccer/eng.1", "901"), ("soccer/eng.1", "902")]
    assert out["club_summaries"] == 2 and out["club_odds"] == 6
    assert con.execute("SELECT COUNT(*) FROM external_forecasts").fetchone()[0] == 0     # prices only
    px = con.execute("""SELECT price FROM odds WHERE event_id='football:E0:20261121:man-united:tottenham'
                        AND bookmaker='Bet365' AND selection='H'""").fetchone()[0]
    assert px == pytest.approx(2.2)


def test_evening_run_spends_leftover_on_future_days_within_the_same_allowance(con, monkeypatch):
    """Morning buys today's NBA and the weekend EPL; the evening run (same New York day) refreshes both
    with what is left of the day's allowance, and the NBA response's next-day games are stored."""
    _serve(monkeypatch, {("eng.1", "20261121"): UPCOMING})
    ec.ingest(con, NOW, polite_delay=0)
    today_ko = datetime(2026, 11, 19, 0, 30, tzinfo=timezone.utc)      # 19:30 New York tonight
    tomorrow_ko = datetime(2026, 11, 20, 0, 30, tzinfo=timezone.utc)   # 19:30 New York tomorrow
    for i, ko in enumerate((today_ko, tomorrow_ko)):
        con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?)""", (f"nba:{i}", "nba", "NBA", ko.isoformat(), f"Home{i} Club",
                                                     f"Away{i} Club", "scheduled", "t", "t"))
    con.commit()

    def nba_ev(i, ko):
        return {"home_team": f"Home{i} Club", "away_team": f"Away{i} Club",
                "commence_time": ko.isoformat().replace("+00:00", "Z"),
                "bookmakers": [{"key": "pinnacle", "title": "Pinnacle", "last_update": "2026-11-18T14:00:00Z",
                                "markets": [{"key": "h2h", "outcomes": [{"name": f"Home{i} Club", "price": 1.9},
                                                                        {"name": f"Away{i} Club", "price": 1.95}]}]}]}
    morning_nba = [nba_ev(0, today_ko)]                                # books have not posted tomorrow yet
    evening_nba = [nba_ev(0, today_ko), nba_ev(1, tomorrow_ko)]
    calls = []
    _fake_odds_api(monkeypatch, calls, sports=("basketball_nba", "soccer_epl"),
                   payload={"basketball_nba": morning_nba, "soccer_epl": EPL})
    with db.job(con, "ingest-odds-api") as d:
        d.update(oa.ingest(con, NOW))
    assert calls == ["/sports/basketball_nba/odds", "/sports/soccer_epl/odds"]   # today's games first
    morning_spent = d["credits_spent"]
    evening = datetime(2026, 11, 18, 22, 50, tzinfo=timezone.utc)      # 17:50 New York, same day
    calls.clear()
    _fake_odds_api(monkeypatch, calls, sports=("basketball_nba", "soccer_epl"),
                   payload={"basketball_nba": evening_nba, "soccer_epl": EPL})
    with db.job(con, "ingest-odds-api") as d:
        d.update(oa.ingest(con, evening))
    assert calls == ["/sports/basketball_nba/odds", "/sports/soccer_epl/odds"]
    daily = oa.budget(400, evening, spent_today=morning_spent, slot="evening") + morning_spent
    assert morning_spent + d["credits_spent"] <= daily                  # the day's total is unchanged
    assert con.execute("SELECT COUNT(*) FROM odds WHERE event_id='nba:1'").fetchone()[0] == 2


def test_due_allows_one_evening_look_at_far_competitions():
    import sqlite3
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    soon = NOW + timedelta(days=3)
    assert oa._due(c, "soccer_epl", soon, NOW)                                     # never fetched
    c.execute("INSERT INTO odds_api_fetches VALUES ('soccer_epl', ?, 2)", (NOW.isoformat(),))
    assert not oa._due(c, "soccer_epl", soon, NOW + timedelta(hours=1))           # morning again: no
    evening = datetime(2026, 11, 18, 22, 50, tzinfo=timezone.utc)
    assert oa._due(c, "soccer_epl", soon, evening)                                # evening after a morning look
    c.execute("INSERT INTO odds_api_fetches VALUES ('soccer_epl', ?, 2)", (evening.isoformat(),))
    assert not oa._due(c, "soccer_epl", soon, evening + timedelta(hours=1))       # once per evening
    assert oa._due(c, "soccer_epl", soon, NOW + timedelta(days=1))                # next New York day
