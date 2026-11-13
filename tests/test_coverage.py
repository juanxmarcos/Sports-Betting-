"""Source coverage audit: recorded fixture rows only, no network, database opened read-only."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from sbi import config, coverage, db

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)


def _ev(con, eid, sport, league, hours, status="scheduled"):
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (eid, sport, league, (NOW + timedelta(hours=hours)).isoformat(), "H", "A", status, "t", "t"))


def _odds(con, eid, book, age_h, market="ML", source="the-odds-api.com", kind="pre", price=1.9):
    con.execute("""INSERT INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,retrieved_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (eid, book, market, "home", None, price, kind, source, (NOW - timedelta(hours=age_h)).isoformat()))


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "t.sqlite"
    con = db.connect(p)
    _ev(con, "a", "nba", "NBA", 5)       # three names, one operator (Flutter) + one alias variant
    for b in ("Paddy Power", "Sky Bet", "FanDuel"):
        _odds(con, "a", b, 1)
    _ev(con, "b", "nba", "NBA", 6)       # three independent operators incl. a sharp reference
    for b in ("Pinnacle", "DraftKings", "Unibet (SE)", "Unibet"):
        _odds(con, "b", b, 2)
    _odds(con, "b", "Avg", 2)            # aggregate: never a bookmaker
    _odds(con, "b", "Bet365 Live", 2)    # in-play feed: excluded
    _ev(con, "c", "nba", "NBA", 7)       # stale quotes only
    for b in ("Pinnacle", "DraftKings", "Bet365"):
        _odds(con, "c", b, 30)
    _ev(con, "d", "nba", "NBA", 8)       # no quotes
    _ev(con, "e", "nba", "NBA", 400)     # beyond the 7-day horizon
    _odds(con, "e", "Pinnacle", 1)
    _ev(con, "f", "tennis", "TENNIS:ATP", -30)   # still 'scheduled' long after its start
    _ev(con, "g", "nba", "NBA", -48, status="finished")
    _odds(con, "g", "Pinnacle", 50)
    db.provider_ok(con, "espn:nba", 5)
    db.provider_err(con, "the-odds-api", "boom apiKey=SECRETVALUE")
    for day, spent, rem in (("2026-11-12T20:00:00+00:00", 7, "493"), ("2026-11-13T02:00:00+00:00", 3, "490")):
        con.execute("INSERT INTO job_runs(job,started_at,status,details) VALUES ('ingest-odds-api',?,'ok',?)",
                    (day, json.dumps({"credits_spent": spent, "credits_remaining_after": rem})))
    con.execute("INSERT INTO job_runs(job,started_at,status,details) VALUES ('ingest-odds-api',?,'ok',?)",
                ("2026-11-13T03:00:00+00:00", json.dumps({"skipped": "ODDS_API_KEY not set"})))
    con.commit()
    con.close()
    return p


def test_summary_counts_operators_not_names(path):
    s = coverage.summary(coverage.connect_ro(path), NOW)["nba"]
    assert s["scheduled_events"] == 4                 # e is beyond the horizon, g is finished
    assert s["with_any_quote"] == 3 and s["with_fresh_quote"] == 2      # c only has stale quotes
    assert s["with_3plus_operators"] == 1             # a: three Flutter brands are ONE operator
    assert s["with_sharp_reference"] == 1             # c's Pinnacle quote is stale
    assert s["bookmaker_names"] == 8 and s["independent_operators"] == 5


def test_matrix_row(path):
    rows = coverage.matrix(coverage.connect_ro(path), NOW)
    assert len(rows) == 1
    r = rows[0]
    assert (r["sport"], r["competition"], r["market"], r["source"]) == ("nba", "NBA", "ML", "the-odds-api.com")
    assert r["scheduled_events"] == 4 and r["events_priced"] == 3 and r["events_priced_fresh"] == 2
    assert r["sharp_references"] == ["Pinnacle"]
    assert r["median_quote_age_h"] == 2.0             # newest quote per event: 1h, 2h, 30h


def test_book_audit(path):
    b = coverage.book_audit(coverage.connect_ro(path))
    assert b["name_variants_merged"] == {"Unibet (SE)": "Unibet"}
    assert b["multi_brand_operators"]["Flutter"] == ["FanDuel", "Paddy Power", "Sky Bet"]
    assert "DraftKings" in b["no_operator_mapping_treated_as_independent"]
    assert set(b["excluded_not_bookmakers"]) == {"Avg", "Bet365 Live"}


def test_sources_usage_and_credentials(path, monkeypatch):
    con = coverage.connect_ro(path)
    now = datetime.now(timezone.utc)
    src = coverage.sources(con, now)["providers"]
    assert src["espn:nba"]["working"] is True
    assert src["the-odds-api"]["working"] is False and "SECRETVALUE" not in json.dumps(src)
    u = coverage.odds_api_usage(con)
    assert u["credits_by_day"] == {"2026-11-12": {"credits": 7, "runs_that_spent": 1},
                                   "2026-11-13": {"credits": 3, "runs_that_spent": 1}}
    assert u["credits_remaining_after_last_run"] == 490
    monkeypatch.setenv("ODDS_API_KEY", "SECRETVALUE")
    c = coverage.credentials(con)
    assert c["ODDS_API_KEY"]["set_in_this_environment"] is True
    assert c["ODDS_API_KEY"]["last_run_that_used_a_working_key"] == "2026-11-13T02:00:00+00:00"
    assert "SECRETVALUE" not in json.dumps(c)          # presence only, never the value


def test_write_is_read_only_and_reports_delta(path, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path / "reports")
    before = path.read_bytes()
    base = coverage.write(NOW, baseline=True, db_path=path)
    assert "baseline" not in base and (tmp_path / "data" / "coverage" / "baseline_2026-11-13.json").exists()
    rep = coverage.write(NOW - timedelta(hours=10), db_path=path)     # 10h earlier c's 30h-old quotes were still fresh
    assert path.read_bytes() == before                 # the audit never writes to the database
    d = rep["baseline"]["delta"]["nba"]
    assert d["with_fresh_quote"] == {"baseline": 2, "now": 3, "change": 1}
    md = (tmp_path / "reports" / "source_coverage.md").read_text()
    assert "Change since baseline" in md and "| nba | NBA | ML |" in md
    assert rep["context"]["scheduled_events_past_start"] == {"tennis": 1}


def test_read_only_connection_rejects_writes(path):
    import sqlite3
    with pytest.raises(sqlite3.OperationalError):
        coverage.connect_ro(path).execute("DELETE FROM odds")


def test_stale_scheduled_events_flagged(path):
    assert coverage.context(coverage.connect_ro(path), NOW)["scheduled_events_past_start"] == {"tennis": 1}
