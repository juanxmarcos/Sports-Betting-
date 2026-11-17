"""Quote-source audit (issue #24): hand-built fixture rows only, no network, database opened read-only."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from sbi import config, coverage, db, quote_sources as qs
from sbi.sources import odds_api as oa

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)


def _ev(con, eid, hours=5, status="scheduled"):
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (eid, "nba", "NBA", (NOW + timedelta(hours=hours)).isoformat(), "H", "A", status, "t", "t"))


def _odds(con, eid, book, age_h=1, market="ML", source="the-odds-api.com"):
    con.execute("""INSERT INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,retrieved_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (eid, book, market, "home", None, 1.9, "pre", source, (NOW - timedelta(hours=age_h)).isoformat()))


def _run(con, started, fetched, coverage_, rows=0):
    con.execute("INSERT INTO job_runs(job,started_at,status,details) VALUES ('ingest-odds-api',?,'ok',?)",
                (started, json.dumps({"fetched": fetched, "coverage": coverage_, "odds_rows": rows,
                                      "credits_spent": 0, "credits_remaining_after": "400"})))


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "t.sqlite"
    con = db.connect(p)
    _ev(con, "a")      # 3 known operators (Pinnacle, Kambi twice, evoke) + 2 of unknown ownership
    for b in ("Pinnacle", "Unibet (SE)", "LeoVegas", "William Hill", "1xBet", "Tipico"):
        _odds(con, "a", b)
    _ev(con, "b")      # Kambi only through LeoVegas here, evoke only through 888sport
    for b in ("Pinnacle", "LeoVegas", "888sport", "1xBet"):
        _odds(con, "b", b)
    _ev(con, "c")      # two known operators only; a DraftKings quote from ESPN must not count as The Odds API's
    for b in ("Pinnacle", "Unibet"):
        _odds(con, "c", b)
    _odds(con, "c", "DraftKings", source="espn.com (public scoreboard)")
    _ev(con, "d")      # stale quotes only
    for b in ("Pinnacle", "Unibet", "William Hill"):
        _odds(con, "d", b, age_h=40)
    con.execute("CREATE TABLE IF NOT EXISTS odds_api_fetches (sport_key TEXT, fetched_at TEXT, credits INTEGER)")
    for sk, c in (("basketball_nba", 3), ("soccer_epl", 2), ("tennis_atp_finals", 1)):
        con.execute("INSERT INTO odds_api_fetches VALUES (?,?,?)", (sk, NOW.isoformat(), c))
    _run(con, "2026-11-12T20:00:00+00:00", ["basketball_nba", "soccer_epl"],
         {"basketball_nba": {"returned": 8, "in_window": 8, "matched": 8},
          "soccer_epl": {"returned": 20, "in_window": 9, "matched": 0}}, rows=100)
    _run(con, "2026-11-13T02:00:00+00:00", ["soccer_epl", "tennis_atp_finals"],
         {"soccer_epl": {"returned": 20, "in_window": 0, "matched": 0},
          "tennis_atp_finals": {"returned": 4, "in_window": 4, "matched": 4}}, rows=10)
    _run(con, "2026-11-13T04:00:00+00:00", ["basketball_nba"], {})                 # older log format: no outcome recorded
    con.execute("INSERT INTO job_runs(job,started_at,status,details) VALUES ('ingest-odds-api',?,'ok',?)",
                ("2026-11-13T06:00:00+00:00", json.dumps({"skipped": "ODDS_API_KEY not set"})))
    con.commit()
    con.close()
    return p


def test_credits_that_bought_nothing_are_counted_not_guessed(path):
    con = coverage.connect_ro(path)
    ce = qs.credit_economics(con)
    assert ce["runs_that_fetched"] == 3 and ce["new_quote_rows_stored"] == 110
    assert ce["by_sport_key"]["soccer_epl"] == {"fetches": 2, "credits": 4, "events_matched": 0,
                                                "fetches_matching_nothing": 2, "credits_matching_nothing": 4}
    assert ce["by_sport_key"]["basketball_nba"]["credits_matching_nothing"] == 0
    assert ce["total"]["credits"] == 3 + 2 + 2 + 1 and ce["total"]["credits_matching_nothing"] == 4
    assert ce["total"]["share_matching_nothing"] == 0.5
    assert ce["fetches_without_detail"] == 1           # the run with no per-competition outcome is not attributed


def test_credit_economics_on_an_empty_database(tmp_path):
    p = tmp_path / "e.sqlite"
    db.connect(p).close()
    ce = qs.credit_economics(coverage.connect_ro(p))
    assert ce["total"]["credits"] == 0 and ce["total"]["share_matching_nothing"] is None and ce["by_sport_key"] == {}
    oy = qs.operator_yield(coverage.connect_ro(p), NOW)
    assert oy["events_priced"] == 0 and oy["minimal_bookmakers_keeping_known_coverage"] == []


def test_operator_yield_counts_operators_not_names(path):
    oy = qs.operator_yield(coverage.connect_ro(path), NOW)
    assert oy["events_priced"] == 3                                    # d is stale; ESPN rows are not this source
    assert oy["bookmakers"] == 7 and oy["known_operators"] == 3        # Unibet (SE) and Unibet are one bookmaker
    assert oy["unknown_ownership"] == ["1xBet", "Tipico"]
    assert oy["operators_with_several_brands"] == {"Kambi": ["LeoVegas", "Unibet"], "evoke": ["888sport", "William Hill"]}
    assert oy["events_with_3plus_known_operators"] == 2 and oy["events_with_sharp_reference"] == 3
    assert "DraftKings" not in {r["bookmaker"] for r in oy["per_bookmaker"]}


def test_minimal_list_keeps_every_known_operator_and_never_needs_unknown_books(path):
    oy = qs.operator_yield(coverage.connect_ro(path), NOW)
    keep = oy["minimal_bookmakers_keeping_known_coverage"]
    assert keep[0] == "Pinnacle"                                       # sharp references are kept first
    assert set(keep) == {"Pinnacle", "LeoVegas", "Unibet", "William Hill", "888sport"}
    assert not set(keep) & {"1xBet", "Tipico"}
    assert oy["check_events_with_3plus_known_operators_after"] == oy["events_with_3plus_known_operators"]
    assert oy["check_events_with_sharp_reference_after"] == oy["events_with_sharp_reference"]
    assert oy["slots_left_for_other_operators"] == 5


def test_matrix_invariants():
    keys = [c.key for c in qs.CANDIDATES]
    assert len(keys) == len(set(keys))
    for c in qs.CANDIDATES:
        assert c.status in qs.STATUSES, c.key
        assert c.links and all(u.startswith("https://") for u in c.links), c.key
        assert c.checked == qs.CHECKED and c.finding and c.store and c.publish, c.key
    # the only source cleared for a connector is the one already in use
    assert [c.key for c in qs.CANDIDATES if c.status == "verified"] == ["the-odds-api"]
    # prediction markets are never cleared and never described as bookmakers
    for c in qs.CANDIDATES:
        if c.kind == "prediction market":
            assert c.status == "blocked" and "not bookmaker odds" in (c.independence + c.finding).lower(), c.key
    # the two similarly named vendors are separate rows
    assert "the-odds-api.com" in qs.CANDIDATES[0].name and "theoddsapi.com" in next(
        c for c in qs.CANDIDATES if c.key == "betting-data-api").name


def test_no_candidate_host_is_called_by_the_code():
    """A blocked or opt-in provider must not have slipped into the code as a connector."""
    import pathlib
    src = "\n".join(p.read_text() for p in pathlib.Path(qs.__file__).parent.rglob("*.py") if p.name != "quote_sources.py")
    for host in ("gamma-api.polymarket.com", "clob.polymarket.com", "bettingdataapi.com", "theoddsapi.com",
                 "kalshi.com", "api.betfair.com", "api.pinnacle.com", "smarkets.com"):
        assert host not in src, host


def test_write_is_read_only_and_wording_does_not_overstate(path, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path / "reports")
    before = path.read_bytes()
    rep = qs.write(NOW, db_path=path)
    assert path.read_bytes() == before
    assert rep["baseline"] is None                                     # no baseline file in this temp directory
    md = (tmp_path / "reports" / "quote_sources.md").read_text()
    assert "Prediction-market prices are not bookmaker odds" in md and "Nothing is a live or executable price" in md
    assert "| soccer_epl | 2 | 4 | 0 | 2 | 4 |" in md
    assert "owner decision" in md and "SECRET" not in md
    json.loads((tmp_path / "data" / "coverage" / "quote_sources_latest.json").read_text())


def test_report_compares_with_the_frozen_baseline(path, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path / "reports")
    coverage.write(NOW, baseline=True, db_path=path)
    rep = qs.write(NOW, db_path=path)
    assert rep["baseline"]["file"] == "baseline_2026-11-13.json"
    assert rep["baseline"]["bookmakers"]["known_operators"] == rep["now"]["bookmakers"]["known_operators"] == 3
    assert "| Known operators | 3 | 3 | +0 |" in (tmp_path / "reports" / "quote_sources.md").read_text()


def _probe_fake(monkeypatch, remaining="400", calls=None):
    def fake_get(path, params, api_key):
        if calls is not None:
            calls.append((path, dict(params)))
        if path == "/sports":
            return [], {"remaining": remaining, "used": "0", "last": "0"}
        return ([{"bookmakers": [{"key": "pinnacle"}, {"key": "draftkings"}]}, {"bookmakers": [{"key": "pinnacle"}]}],
                {"remaining": "399", "used": "1", "last": "1"})
    monkeypatch.setenv("ODDS_API_KEY", "dummy")
    monkeypatch.setattr(oa, "_get", fake_get)


def test_probe_is_one_h2h_call_and_reports_what_the_plan_returned(monkeypatch):
    calls = []
    _probe_fake(monkeypatch, calls=calls)
    out = qs.probe("pinnacle,draftkings,fanduel")
    paid = [(p, q) for p, q in calls if p.endswith("/odds")]
    assert len(paid) == 1 and paid[0][1]["markets"] == "h2h" and "regions" not in paid[0][1]
    assert out["events_per_bookmaker_returned"] == {"draftkings": 1, "pinnacle": 2}
    assert out["requested_but_not_returned"] == ["fanduel"]
    assert out["credits_expected"] == 1 and out["credits_charged"] == 1 and out["stored"] == "nothing"


def test_probe_refuses_without_spending(monkeypatch):
    calls = []
    _probe_fake(monkeypatch, remaining="20", calls=calls)              # at the reserve
    assert "reserve" in qs.probe("pinnacle")["refused"]
    assert "not bookmaker odds" in qs.probe("pinnacle,polymarket")["refused"]
    assert not [p for p, _ in calls if p.endswith("/odds")]
    _probe_fake(monkeypatch, remaining=None, calls=calls)              # remaining unknown: do not spend
    assert "refused" in qs.probe("pinnacle")
    monkeypatch.delenv("ODDS_API_KEY")
    assert qs.probe("pinnacle") == {"refused": "ODDS_API_KEY not set"}
    assert not [p for p, _ in calls if p.endswith("/odds")]
