"""Soccer league allowlist, football-data parsing edge cases and per-league coverage.

Network-free: the fixtures file is a recorded slice of football-data.co.uk/fixtures.csv
(published 2026-11-13 14:16 GMT); every HTTP call is replaced."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sbi import config, coverage, db, league_eval, leagues, pipeline
from sbi.sources import football_data as fd
from sbi.sources import http

FIXTURES = (Path(__file__).parent / "fixtures" / "football_data" / "fixtures_2026-11-13.csv").read_bytes()
LM = "2026-11-13T14:16:25+00:00"
NOW = datetime(2026, 11, 13, 17, 0, tzinfo=timezone.utc)
HEADER, *ROWS = FIXTURES.decode().strip().split("\n")


def _csv(*rows, header=HEADER) -> bytes:
    return ("\n".join([header, *rows]) + "\n").encode()


@pytest.fixture
def con(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path / "reports")
    return db.connect(tmp_path / "t.sqlite")


def _serve(monkeypatch, files: dict, default=b""):
    """Replace football_data.fetch: url suffix -> bytes, or an Exception to raise."""
    calls = []

    def fake(url, max_age_hours=6.0, **_):
        calls.append(url)
        for suffix, body in files.items():
            if url.endswith(suffix):
                if isinstance(body, Exception):
                    raise body
                return body, LM
        return default, LM
    monkeypatch.setattr(fd, "fetch", fake)
    return calls


# ---------------------------------------------------------------- allowlist

def test_allowlist_tiers_are_explicit_and_disjoint():
    assert leagues.active() == list(config.FOOTBALL_LEAGUES)          # the analysed set is unchanged
    assert leagues.monitoring() == ["E2", "E3", "EC", "SC1", "SC2", "SC3", "SP2"]
    assert not set(leagues.active()) & set(leagues.monitoring())
    assert leagues.stored() == leagues.active() + leagues.monitoring()
    assert leagues.status("E0") == "active" and leagues.status("SP2") == "monitoring"
    assert leagues.status("D2") == "unlisted" and leagues.status("INT:uefa.nations") == "international"
    assert leagues.is_analysable("E0") and not leagues.is_analysable("E2") and not leagues.is_analysable("D2")
    assert leagues.name("E2") == "England League One" and leagues.name("ZZ") == "ZZ"


def test_team_aliases_are_exact_and_scoped_to_one_division():
    assert leagues.canonical_team("E2", "MK Dons") == "Milton Keynes Dons"
    assert leagues.canonical_team("E2", "  sheffield   WEDNESDAY ") == "Sheffield Weds"
    assert leagues.canonical_team("E3", "MK Dons") == "MK Dons"            # alias belongs to E2 only
    assert leagues.canonical_team("E2", "Sheffield Utd") == "Sheffield Utd"     # similar name, different club: untouched
    assert leagues.canonical_team("SP2", " Leganes ") == "Leganes"         # unknown names are only trimmed
    for div, table in leagues.TEAM_ALIASES.items():
        assert div in leagues.LEAGUES and all(k == k.lower() for k in table)


# ---------------------------------------------------------------- parsing

def test_recorded_fixtures_parse_with_uk_time_for_every_country():
    df = fd.read_csv(FIXTURES)
    m = fd.parse_matches(df)
    assert list(m["div"]) == ["E2", "E2", "E3", "SC1", "SP2", "SP2"]
    assert m["event_id"][0] == "football:E2:20261114:afc-wimbledon:blackpool"
    # November is GMT: UK 12:30 is 12:30 UTC. The Spanish match is printed in UK time too (19:30, not 20:30 CET).
    assert m["kickoff_utc"][2].isoformat() == "2026-11-14T12:30:00+00:00"
    assert m["kickoff_utc"][4].isoformat() == "2026-11-13T19:30:00+00:00"
    assert set(m["season"]) == {"2627"}
    o = fd.parse_odds(df)
    assert set(o["kind"]) == {"pre"} and set(o["market"]) == {"1X2", "OU", "AH"}
    books = set(o[o["idx"] == 0]["bookmaker"]) - fd.AGGREGATES
    assert books == {"Bet365", "Betfred", "BetVictor", "Bwin", "Paddy Power", "Sky Bet", "Betfair Exchange"}
    # the last SP2 row has no Betfair Exchange O/U or handicap price: sparse cells are skipped, not zero-filled
    last = o[(o["idx"] == 5) & (o["bookmaker"] == "Betfair Exchange")]
    assert set(last["market"]) == {"1X2"}


def test_kickoff_summer_time_and_missing_time():
    row = ROWS[0].split(",")
    summer = ",".join(["E2", "15/08/2026", "15:00"] + row[3:])
    clocks_back = ",".join(["E2", "25/10/2026", "01:30"] + row[3:])      # ambiguous hour on the night clocks go back
    no_time = ",".join(["E2", "21/11/2026", ""] + row[3:])
    bad_time = ",".join(["E2", "28/11/2026", "TBC"] + row[3:])
    df = fd.read_csv(_csv(summer, clocks_back, no_time, bad_time))
    m = fd.parse_matches(df)
    assert m["kickoff_utc"][0].isoformat() == "2026-08-15T14:00:00+00:00"      # BST = UTC+1
    assert m["kickoff_utc"][1].isoformat() == "2026-10-25T00:30:00+00:00"      # first occurrence (still BST)
    assert m["kickoff_utc"][2].isoformat() == "2026-11-21T15:00:00+00:00"      # assumed 15:00 UK
    assert m["kickoff_utc"][3].isoformat() == "2026-11-28T15:00:00+00:00"
    assert fd.clean_rows(df)[1]["assumed_kickoff_time"] == 2                   # and the assumption is counted


def test_duplicate_and_malformed_rows_are_dropped_and_counted():
    dup = ROWS[0].replace("2.5,3.4,2.5", "9.9,9.9,9.9", 1)       # same match again with different prices
    cells = ROWS[1].split(",")
    bad_date = ",".join(["E2", "not a date"] + cells[2:])
    itself = ",".join(cells[:4] + [cells[3]] + cells[5:])        # a team "playing" itself
    blank = ",".join(cells[:3] + ["", ""] + cells[5:])           # no teams: removed when the file is read
    df = fd.read_csv(_csv(ROWS[0], dup, bad_date, itself, blank, ROWS[2]))
    kept, counts = fd.clean_rows(df)
    assert counts == {"bad_date": 1, "bad_team": 1, "duplicate": 1, "assumed_kickoff_time": 0}
    m = fd.parse_matches(df)
    assert list(m.index) == [0, 4] and m["event_id"].is_unique       # original row positions are kept
    assert list(m["home"]) == ["AFC Wimbledon", "Exeter"]


def test_duplicate_rows_never_attach_odds_to_the_wrong_event(con, monkeypatch):
    dup = ROWS[0].replace("2.5,3.4,2.5", "9.9,9.9,9.9", 1)
    _serve(monkeypatch, {"fixtures.csv": _csv(ROWS[0], dup, ROWS[2])})
    out = fd.ingest_fixtures(con, leagues.stored())
    assert out["events"] == 2 and out["rows_dropped"]["duplicate"] == 1
    assert con.execute("SELECT COUNT(*) FROM odds WHERE price=9.9").fetchone()[0] == 0     # the first row wins
    exeter = con.execute("""SELECT price FROM odds WHERE event_id LIKE '%exeter%' AND bookmaker='Bet365'
                            AND market='1X2' AND selection='H'""").fetchone()[0]
    assert exeter == 1.86


def test_zero_and_absurd_odds_are_not_prices():
    cells = ROWS[0].split(",")
    h = HEADER.split(",")
    for col, val in (("B365H", "0"), ("B365D", ""), ("B365A", "1"), ("BFDH", "-2.5"), ("BVH", "5000"), ("BWH", "abc")):
        cells[h.index(col)] = val
    o = fd.parse_odds(fd.read_csv(_csv(",".join(cells))))
    got = {(r.bookmaker, r.selection) for r in o[o["market"] == "1X2"].itertuples()}
    assert not {("Bet365", "H"), ("Bet365", "D"), ("Bet365", "A"), ("Betfred", "H"), ("BetVictor", "H"), ("Bwin", "H")} & got
    assert ("Betfred", "D") in got and (o["price"] > 1).all() and (o["price"] <= fd.MAX_PRICE).all()


def test_sparse_columns_one_bookmaker_no_time_no_handicap():
    body = "Div,Date,HomeTeam,AwayTeam,B365H,B365D,B365A\nE3,14/11/2026,Exeter,Cheltenham,1.86,3.5,3.8\n"
    df = fd.read_csv(body.encode())
    m, o = fd.parse_matches(df), fd.parse_odds(df)
    assert len(m) == 1 and m["hxg"].isna().all() and m["hg"].isna().all()      # no xG or score columns: NaN, no crash
    assert len(o) == 3 and set(o["market"]) == {"1X2"}


def test_missing_xg_columns_stay_missing():
    hist = ("Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG\nEC,07/11/2026,15:00,York,Woking,2,1\n"
            "EC,07/11/2026,15:00,Halifax,Altrincham,,\n")
    m = fd.parse_matches(fd.read_csv(hist.encode()))
    assert m["hxg"].isna().all() and m["hg"].tolist()[0] == 2 and np.isnan(m["hg"].tolist()[1])


def test_empty_feed_and_header_only(con, monkeypatch):
    for body in (b"", b"   \n", (HEADER + "\n").encode()):
        _serve(monkeypatch, {"fixtures.csv": body})
        out = fd.ingest_fixtures(con, leagues.stored())
        assert out["events"] == 0 and out["odds"] == 0
    assert con.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0


def test_schema_change_is_a_clear_error_not_a_crash(con, monkeypatch):
    renamed = FIXTURES.replace(b"HomeTeam", b"Home").replace(b"AwayTeam", b"Away")
    with pytest.raises(fd.SchemaError, match="HomeTeam"):
        fd.read_csv(renamed)
    with pytest.raises(fd.SchemaError):
        fd.read_csv(b"<html><body>Service unavailable</body></html>")
    # the job records it against the provider and still ingests the season files
    season = "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG\nE2,07/11/2026,15:00,Wigan,Barnsley,1,1\n".encode()
    _serve(monkeypatch, {"fixtures.csv": renamed, "E2.csv": season})
    out = pipeline.ingest(con, NOW)
    assert "missing column" in out["fixtures_error"] and out["E2"]["events"] == 1
    st = {r["provider"]: r for r in con.execute("SELECT * FROM provider_status")}
    assert "missing column" in st["football-data:fixtures"]["last_error"]
    assert st["football-data:E2"]["last_success"]


# ---------------------------------------------------------------- ingestion

def test_only_allowlisted_divisions_are_stored(con, monkeypatch):
    cells = ROWS[0].split(",")
    unlisted = ",".join(["D2"] + cells[1:3] + ["Hertha", "Schalke 04"] + cells[5:])
    _serve(monkeypatch, {"fixtures.csv": _csv(*ROWS, unlisted)})
    out = fd.ingest_fixtures(con, leagues.stored())
    assert out["by_division"] == {"E2": 2, "E3": 1, "SC1": 1, "SP2": 2}
    assert out["not_on_allowlist"] == {"D2": 1}                    # seen, counted, not stored
    assert con.execute("SELECT COUNT(*) FROM events WHERE league='D2'").fetchone()[0] == 0
    # the old allowlist stores none of these: the gain is measured, not assumed
    assert fd.ingest_fixtures(db.connect(config.DB_PATH.with_name("old.sqlite")), config.FOOTBALL_LEAGUES)["events"] == 0


def test_repeat_ingestion_adds_nothing(con, monkeypatch):
    _serve(monkeypatch, {"fixtures.csv": FIXTURES})
    first = fd.ingest_fixtures(con, leagues.stored())
    rows = con.execute("SELECT COUNT(*) FROM odds").fetchone()[0]
    assert first["events"] == 6 and first["odds"] == rows > 0
    for _ in range(3):                                             # the same published snapshot, read again
        again = fd.ingest_fixtures(con, leagues.stored())
        assert again["events"] == 6 and again["odds"] == 0
    assert con.execute("SELECT COUNT(*) FROM odds").fetchone()[0] == rows
    assert con.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 6
    # a NEWER snapshot repeating a 1X2 price is still recorded once, with its own publication time
    monkeypatch.setattr(fd, "fetch", lambda url, **_: (FIXTURES, "2026-11-14T09:00:00+00:00"))
    newer = fd.ingest_fixtures(con, leagues.stored())
    n1x2 = con.execute("SELECT COUNT(*) FROM odds WHERE market='1X2' AND retrieved_at=?", (LM,)).fetchone()[0]
    assert newer["odds"] == n1x2
    assert fd.ingest_fixtures(con, leagues.stored())["odds"] == 0


def test_results_then_fixture_keep_one_event_and_the_result(con, monkeypatch):
    done = HEADER + ",FTHG,FTAG\n" + ROWS[0] + ",2,1\n"
    _serve(monkeypatch, {"fixtures.csv": _csv(ROWS[0]), "E2.csv": done.encode()})
    fd.ingest_fixtures(con, leagues.stored())
    fd.ingest_results(con, "E2", "2627")
    fd.ingest_fixtures(con, leagues.stored())                      # a late fixtures read must not un-finish it
    ev = con.execute("SELECT status, home_score, away_score FROM events").fetchall()
    assert len(ev) == 1 and tuple(ev[0]) == ("finished", 2, 1)


@pytest.mark.parametrize("code", [403, 429, 401])
def test_blocked_source_is_not_retried_or_bypassed(tmp_path, monkeypatch, code):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    calls = []

    class R:
        status_code = code
        headers, content = {}, b""

    def get(url, **kw):
        calls.append(kw["headers"]["User-Agent"])
        return R()
    monkeypatch.setattr(http.requests, "get", get)
    with pytest.raises(http.SourceBlocked):
        http.fetch("https://www.football-data.co.uk/fixtures.csv")
    assert calls == [config.USER_AGENT]                            # one honest request, then stop


def test_one_blocked_division_does_not_stop_the_others(con, monkeypatch):
    season = "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG\nE3,07/11/2026,15:00,Exeter,Crewe,0,0\n".encode()
    calls = _serve(monkeypatch, {"fixtures.csv": FIXTURES, "E2.csv": http.SourceBlocked("E2.csv -> HTTP 429"),
                                 "E3.csv": season, "E0.csv": RuntimeError("fetch failed: timeout")})
    out = pipeline.ingest(con, NOW)
    assert "429" in out["E2_error"] and "timeout" in out["E0_error"]
    assert out["E3"]["events"] == 1 and out["fixtures"]["events"] == 6
    assert sum(u.endswith("E2.csv") for u in calls) == 1           # no retry loop
    st = {r["provider"]: r for r in con.execute("SELECT * FROM provider_status")}
    assert "429" in st["football-data:E2"]["last_error"] and st["football-data:E3"]["last_success"]


def test_monitoring_results_are_fetched_at_most_daily(con, monkeypatch):
    ages = {}
    monkeypatch.setattr(fd, "fetch", lambda url, max_age_hours=6.0, **_: (ages.__setitem__(url.rsplit("/", 1)[-1], max_age_hours), (b"", LM))[1])
    pipeline.ingest(con, NOW)
    assert ages["E0.csv"] == 6 and ages["E2.csv"] == pipeline.MONITORING_RESULTS_MAX_AGE_H == 24
    assert ages["fixtures.csv"] == 2 and len(ages) == 1 + len(leagues.stored())


# ---------------------------------------------------------------- no picks from monitoring leagues

def _history(now, div):
    from tests.test_ev_model import synthetic
    teams, att, dfn, H, A, HG, AG, days = synthetic(3, seed=3)
    ko = [now - timedelta(days=float(d) + 1) for d in days]
    return pd.DataFrame({"div": div, "home": H, "away": A, "kickoff_utc": pd.to_datetime(ko, utc=True),
                         "hg": HG, "ag": AG, "hxg": np.nan, "axg": np.nan, "season": "2627",
                         "event_id": [f"h{i}" for i in range(len(H))]})


def _priced_event(con, now, div, home="T0", away="T1"):
    eid = f"football:{div}:20261120:{home.lower()}:{away.lower()}"
    con.execute("""INSERT INTO events(event_id,sport,league,season,kickoff_utc,home,away,status,source,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (eid, "football", div, "2627", (now + timedelta(hours=10)).isoformat(), home, away, "scheduled", "test", db.utcnow()))
    ts = (now - timedelta(hours=2)).isoformat()
    for bk, prices in {"Pinnacle": (2.0, 3.6, 4.0), "Bet365": (2.05, 3.5, 3.9), "Bwin": (1.95, 3.6, 4.8),
                       "Betfred": (2.0, 3.4, 3.9)}.items():
        for s, p in zip("HDA", prices):
            con.execute("INSERT INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,retrieved_at) "
                        "VALUES (?,?,?,?,?,?,?,?,?)", (eid, bk, "1X2", s, None, p, "pre", "test", ts))
    con.commit()
    return eid


def test_monitoring_league_is_never_priced_or_published(con, monkeypatch):
    """The same event and prices that produce a pick in an active league produce nothing in a monitoring one."""
    from sbi import disagreement
    monkeypatch.setattr(disagreement, "EXTREME_GAP", 1.0)
    monkeypatch.setattr(config.RULES, "max_prob_sd", 1.0)
    now = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
    loaded = []
    monkeypatch.setattr(pipeline, "load_league", lambda div, seasons: (loaded.append(div), (_history(now, div), None))[1])
    _priced_event(con, now, "E2")
    s = pipeline.analyse(con, now)
    assert s["analysed_events"] == 0 and s["published"] == 0 and s["events_in_window"] == 0
    assert s["monitoring_only_events"] == {"E2": 1} and loaded == []        # history is not even loaded
    for table in ("recommendations", "predictions", "model_runs"):
        assert con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    _priced_event(con, now, "E0")                                           # control: active league, same prices
    s = pipeline.analyse(con, now)
    assert s["analysed_events"] == 1 and s["published"] == 1 and loaded == ["E0"]
    assert [r[0] for r in con.execute("SELECT league FROM recommendations")] == ["E0"]
    assert con.execute("SELECT COUNT(*) FROM predictions p JOIN events e USING(event_id) WHERE e.league='E2'").fetchone()[0] == 0


def test_empty_window_and_unlisted_division_do_not_break_analysis(con, monkeypatch):
    now = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
    assert pipeline.analyse(con, now)["analysed_events"] == 0               # international break: nothing stored
    monkeypatch.setattr(pipeline, "load_league", lambda div, seasons: (_ for _ in ()).throw(AssertionError("must not load")))
    _priced_event(con, now, "D2")                                           # stored by mistake: still never analysed
    s = pipeline.analyse(con, now)
    assert s["analysed_events"] == 0 and s["monitoring_only_events"] == {"D2": 1}


def test_newly_promoted_team_gets_a_warning_not_a_pick(con, monkeypatch):
    now = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(pipeline, "load_league", lambda div, seasons: (_history(now, div), None))
    eid = _priced_event(con, now, "E0", home="T0", away="Promoted FC")      # no match history in this division
    s = pipeline.analyse(con, now)
    assert s["published"] == 0 and s["analysed_events"] == 0
    assert any(eid in w and "not in training data" in w for w in s["warnings"])


def test_research_brief_leaves_out_monitoring_leagues(con):
    from sbi import research
    now = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
    _priced_event(con, now, "E2")
    _priced_event(con, now, "E0")
    assert [u["league"] for u in research.brief(con, now)["upcoming_events"]] == ["E0"]


def test_backtest_loader_keeps_odds_aligned_when_a_row_is_dropped(monkeypatch):
    from sbi import backtest
    hdr = "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,B365H,B365D,B365A"
    s1 = f"{hdr}\nE2,01/11/2025,15:00,A,B,1,0,1.5,4,6\nE2,garbage,15:00,C,D,0,0,9,9,9\nE2,02/11/2025,15:00,C,D,2,2,2.5,3,3\n"
    s2 = f"{hdr}\nE2,07/11/2026,15:00,B,A,0,3,3.1,3.2,2.3\n"
    monkeypatch.setattr(fd, "load_season_frame", lambda div, s, max_age_hours=0: fd.read_csv({"2526": s1, "2627": s2}[s].encode()))
    m, o = backtest.load_league("E2", ["2526", "2627"])
    assert len(m) == 3 and m.index.is_unique
    home_price = {m.at[r.idx, "home"]: r.price for r in o[(o.market == "1X2") & (o.selection == "H")].itertuples()}
    assert home_price == {"A": 1.5, "C": 2.5, "B": 3.1}                     # no price slid onto another match


# ---------------------------------------------------------------- coverage per league

def _ev(con, eid, league, hours, status="scheduled"):
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (eid, "football", league, (NOW + timedelta(hours=hours)).isoformat(), "H", "A", status, "t", "t"))


def _q(con, eid, book, sels, market="1X2", line=None, age_h=1, source="football-data.co.uk"):
    for s in sels:
        con.execute("""INSERT INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,retrieved_at)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (eid, book, market, s, line, 2.0, "pre", source, (NOW - timedelta(hours=age_h)).isoformat()))


@pytest.fixture
def cov(tmp_path):
    p = tmp_path / "c.sqlite"
    con = db.connect(p)
    _ev(con, "a", "E2", 20)                              # usable 1X2: three known operators, all selections
    for b in ("Bet365", "Bwin", "Paddy Power", "Sky Bet", "Betfred", "Betfair Exchange"):
        _q(con, "a", b, "HDA")
    _q(con, "a", "Avg", "HDA")                           # aggregate: not a bookmaker
    for b in ("Bet365", "Betfair Exchange"):             # O/U from two operators only: priced, not usable
        _q(con, "a", b, ("over", "under"), market="OU", line=2.5)
    _ev(con, "b", "E2", 21)                              # three names, but Betfred/BetVictor ownership is unknown
    for b in ("Bet365", "Betfred", "BetVictor"):
        _q(con, "b", b, "HDA")
    _ev(con, "c", "E2", 22)                              # three operators, one missing the draw price
    _q(con, "c", "Bet365", "HDA")
    _q(con, "c", "Bwin", "HDA")
    _q(con, "c", "Paddy Power", "HA")
    _ev(con, "d", "E2", 23)                              # complete but stale
    for b in ("Bet365", "Bwin", "Paddy Power"):
        _q(con, "d", b, "HDA", age_h=40)
    _ev(con, "e", "E2", 24)                              # no quotes at all
    _ev(con, "f", "E0", 20)                              # active league, bookmaker-timed quotes
    for b in ("Pinnacle", "Bet365", "Bwin"):
        _q(con, "f", b, "HDA", source="the-odds-api.com")
    for i in range(3):
        _ev(con, f"h{i}", "SC3", -200 - i, status="finished")     # results only, no upcoming fixture
    _ev(con, "g", "INT:uefa.nations", 30)
    con.commit()
    con.close()
    return p


def test_league_coverage_counts_events_markets_and_operators_separately(cov):
    sl = coverage.soccer_leagues(coverage.connect_ro(cov), NOW)
    e2 = sl["E2"]
    assert e2["tier"] == "monitoring" and e2["scheduled_events"] == 5 and e2["events_priced"] == 4
    assert e2["markets_priced"] == 5                       # a: 1X2 + OU; b, c, d: 1X2
    assert e2["usable_markets"] == 1 and e2["events_with_usable_market"] == 1     # only a's 1X2
    assert e2["known_operators"] == 4 and e2["unknown_bookmakers"] == 2    # Bet365, Entain, Flutter, Betfair | Betfred, BetVictor
    # football-data timestamps are a file's publication time: observed, never bookmaker-timed
    assert e2["events_fresh_bookmaker_timed"] == 0 and e2["events_fresh_observed_only"] == 3
    assert e2["events_with_sharp_reference"] == 1 and e2["timestamp_basis"] == ["file_published"]
    e0 = sl["E0"]
    assert e0["tier"] == "active" and e0["events_fresh_bookmaker_timed"] == 1 and e0["events_fresh_observed_only"] == 0
    assert e0["usable_markets"] == 1
    assert list(sl)[: len(leagues.active())] == sorted(leagues.active())    # active first, then monitoring
    assert sl["INT:uefa.nations"]["tier"] == "international"


def test_historical_only_competition_is_flagged_not_counted_as_coverage(cov):
    sc3 = coverage.soccer_leagues(coverage.connect_ro(cov), NOW)["SC3"]
    assert sc3["historical_only"] is True and sc3["finished_events_stored"] == 3
    assert sc3["scheduled_events"] == 0 and sc3["usable_markets"] == 0 and sc3["known_operators"] == 0
    assert sc3["first_result"] <= sc3["last_result"]


def test_league_delta_against_a_baseline_without_the_league_block(cov):
    rep = {"soccer_leagues": coverage.soccer_leagues(coverage.connect_ro(cov), NOW)}
    old = {"matrix": [{"sport": "soccer", "competition": "INT:uefa.nations", "scheduled_events": 44, "events_priced": 26},
                      {"sport": "soccer", "competition": "INT:uefa.nations", "scheduled_events": 44, "events_priced": 22},
                      {"sport": "nba", "competition": "NBA", "scheduled_events": 52, "events_priced": 9}]}
    d = coverage.league_delta(rep, old)
    assert d["E2"]["scheduled_events"] == {"baseline": 0, "now": 5, "change": 5}
    assert d["E2"]["events_priced"] == {"baseline": 0, "now": 4, "change": 4}
    assert d["E2"]["usable_markets"] == {"baseline": None, "now": 1, "change": None}    # not recorded then: no claim
    assert d["INT:uefa.nations"]["events_priced"] == {"baseline": 26, "now": 0, "change": -26}
    assert "NBA" not in d
    new = coverage.league_delta(rep, {"soccer_leagues": {"E2": {**rep["soccer_leagues"]["E2"], "usable_markets": 0}}})
    assert new["E2"]["usable_markets"] == {"baseline": 0, "now": 1, "change": 1}


def test_report_keeps_the_frozen_baseline_and_explains_monitoring(cov, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path / "reports")
    base_dir = tmp_path / "data" / "coverage"
    base_dir.mkdir(parents=True)
    frozen = json.dumps({"as_of": "2026-11-13T12:17:00+00:00", "summary": {}, "matrix": []})
    (base_dir / "baseline_2026-11-13.json").write_text(frozen)
    rep = coverage.write(NOW, db_path=cov)
    assert (base_dir / "baseline_2026-11-13.json").read_text() == frozen      # never rewritten
    assert rep["baseline"]["soccer_league_delta"]["E2"]["scheduled_events"]["change"] == 5
    md = (tmp_path / "reports" / "source_coverage.md").read_text()
    assert "## Soccer by league" in md and "| E2 England League One | monitoring |" in md
    assert "never priced" in md and "5 events in monitoring leagues" in md
    assert "(n/r)" in md and "not a bettable price" in md


# ---------------------------------------------------------------- validation verdict

GOOD_TEST = {"n_matches": 1500, "base_rate": {"logloss": 1.07}, "dixon_coles": {"logloss": 1.00},
             "market_pre": {"logloss": 1.01}, "blend": {"logloss": 0.99}}
GOOD_BETS = {"n_bets": 300, "roi_ci95": [0.01, 0.2], "clv_ci95": [0.01, 0.05]}
GOOD_LIVE = {"known_operators": 4, "events_fresh_bookmaker_timed": 5}


def test_verdict_needs_every_check_and_never_promotes():
    v = league_eval.verdict(GOOD_TEST, GOOD_BETS, 0.3, GOOD_LIVE)
    assert v["status"] == "candidate_for_owner_review" and v["blockers"] == [] and "never automatic" in v["promotion"]
    for change in ({"test": {**GOOD_TEST, "n_matches": 300}}, {"w": 0.0}, {"bets": {**GOOD_BETS, "n_bets": 20}},
                   {"bets": {**GOOD_BETS, "clv_ci95": [-0.01, 0.05]}}, {"bets": {**GOOD_BETS, "roi_ci95": [-0.2, 0.3]}},
                   {"live": {"known_operators": 2, "events_fresh_bookmaker_timed": 5}},
                   {"live": {"known_operators": 4, "events_fresh_bookmaker_timed": 0}}, {"live": None},
                   {"test": {**GOOD_TEST, "blend": {"logloss": 1.02}}}):
        v = league_eval.verdict(change.get("test", GOOD_TEST), change.get("bets", GOOD_BETS), change.get("w", 0.3),
                                change.get("live", GOOD_LIVE))
        assert v["status"] == "monitoring" and v["blockers"], change
    assert league_eval.verdict({}, {}, 0.0)["status"] == "monitoring"       # no evidence is never a pass


def test_verdict_does_not_change_the_allowlist():
    before = (leagues.active(), leagues.monitoring())
    league_eval.verdict(GOOD_TEST, GOOD_BETS, 0.3, GOOD_LIVE)
    assert (leagues.active(), leagues.monitoring()) == before


def test_history_audit_counts_promoted_teams_xg_and_depth():
    def season(code, date, pairs):
        return [("E2", d, h, a) for d, (h, a) in zip(pd.date_range(date, periods=len(pairs), freq="7D", tz="UTC"), pairs)]
    rows = season("2526", "2025-08-09 14:00", [("A", "B"), ("C", "D")]) + season("2627", "2026-08-08 14:00", [("A", "C"), ("E", "B")])
    m = pd.DataFrame(rows, columns=["div", "kickoff_utc", "home", "away"])
    m["season"] = ["2526", "2526", "2627", "2627"]
    m["hxg"] = [np.nan, np.nan, 1.2, 0.8]
    m["event_id"] = [f"e{i}" for i in range(4)]
    o = pd.DataFrame([(0, "Bet365", "1X2", "H", None, 2.0, "pre"), (0, "Pinnacle", "1X2", "H", None, 2.1, "pre"),
                      (0, "Avg", "1X2", "H", None, 2.0, "pre"), (2, "Betfair Exchange", "1X2", "H", None, 2.2, "pre"),
                      (2, "Bet365", "1X2", "H", None, 2.0, "closing")],
                     columns=["idx", "bookmaker", "market", "selection", "line", "price", "kind"])
    a = {r["season"]: r for r in league_eval.audit(m, o)}
    assert a["2526"]["teams_new_to_division"] is None and a["2627"]["teams_new_to_division"] == 1     # E came up
    assert a["2526"]["xg_rows"] == 0 and a["2627"]["xg_rows"] == 2
    assert a["2526"]["median_bookmakers_pre"]["1X2"] == 2.0 and a["2526"]["sharp_references_pre"] == ["Pinnacle"]
    assert a["2627"]["sharp_references_pre"] == ["Betfair Exchange"] and a["2627"]["median_bookmakers_closing_1x2"] == 1.0
    assert a["2627"]["matches_with_pre_1x2"] == 1 and a["2627"]["kickoff_not_1500"] == 0


def test_validation_report_says_it_changes_nothing():
    rep = {"generated": "2026-11-13T17:00:00+00:00", "seasons": {"tune": ["2021"], "validate": ["2223"], "test": ["2425"]},
           "leagues": {"E2": {"name": "England League One", "audit": [], "blend_weight_1x2": 0.0,
                              "hyperparameters": {"xi": 0.0019, "ridge": 2.0},
                              "test_1x2": {"n_matches": 0}, "verdict": league_eval.verdict({}, {}, 0.0)}}}
    md = league_eval.to_markdown(rep)
    assert "Nothing here changes what Doyen analyses or publishes" in md
    assert "| E2 England League One | monitoring |" in md and "not a recommendation" in md
