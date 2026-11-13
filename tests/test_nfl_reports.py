"""NFL availability report: missing teams, stale data, QB flags, ESPN disagreements, reschedules, opt-in."""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sbi import db, nfl_reports as nr
from sbi.sources import espn_extra, nflverse_injuries as nv

FX = Path(__file__).parent / "fixtures" / "nflverse"
NOW = datetime(2026, 11, 13, 16, tzinfo=timezone.utc)
GAMES = nr.load_games((FX / "games.csv").read_bytes())


def _event(con, espn, home, away, ko, status="scheduled"):
    con.execute("""INSERT OR REPLACE INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,updated_at)
                   VALUES (?,?,?,?,?,?,?,'t','t')""", (f"nfl:NFL:{ko[:10].replace('-', '')}:{espn}", "nfl", "NFL", ko, home, away, status))


def _load(con, name, published):
    return nv.ingest(con, 2026, lambda url: {"outcome": "fetched", "http_status": 200, "content": (FX / name).read_bytes(),
                                             "etag": None, "last_modified": published})


@pytest.fixture
def con(tmp_path, monkeypatch):
    c = db.connect(tmp_path / "t.sqlite")
    monkeypatch.setattr(db, "utcnow", lambda: (NOW - timedelta(hours=1)).isoformat())
    _event(c, "401000003", "Atlanta Falcons", "Kansas City Chiefs", "2026-11-15T18:00:00+00:00")
    _event(c, "401000004", "Las Vegas Raiders", "Seattle Seahawks", "2026-11-15T21:05:00+00:00")
    _event(c, "401999999", "Dallas Cowboys", "San Francisco 49ers", "2026-11-15T21:25:00+00:00")     # not in the schedule file
    _event(c, "401000001", "Seattle Seahawks", "Kansas City Chiefs", "2026-11-08T18:00:00+00:00", "finished")
    return c


def _teams(rep):
    return {t["team"]: t for g in rep["games"] for t in (g["home"], g["away"])}


def test_practice_only_then_designated_and_missing_team(con):
    _load(con, "week10_wed.csv", "2026-11-12T07:00:00+00:00")
    rep = nr.build(con, NOW, GAMES)
    t = _teams(rep)
    assert rep["summary"]["mapped_games"] == 2 and rep["summary"]["unmapped_events"] == 1      # unknown game: no guess
    assert t["KC"]["state"] == "practice_only" and t["KC"]["practice"] == {"DNP": 1, "Limited": 1, "Full": 0}
    assert t["KC"]["designations"] == {"Out": 0, "Doubtful": 0, "Questionable": 0}
    assert t["LV"]["state"] == "missing" and t["LV"]["listed_players"] == 0
    assert rep["summary"]["teams_missing"] == 1 and rep["summary"]["teams_with_designations"] == 0

    _load(con, "week10_fri.csv", "2026-11-13T07:00:00+00:00")
    t = _teams(nr.build(con, NOW, GAMES))
    assert t["KC"]["state"] == "designated" and t["KC"]["designations"]["Questionable"] == 1
    assert t["KC"]["listed_players"] == 1                                # the retracted receiver is not counted
    assert t["ATL"]["designations"] == {"Out": 1, "Doubtful": 1, "Questionable": 0}


def test_qb_flags_never_confirm_a_starter(con):
    _load(con, "week10_wed.csv", "2026-11-12T07:00:00+00:00")
    t = _teams(nr.build(con, NOW, GAMES))
    assert t["KC"]["qb"]["last_starter"]["gsis_id"] == "00-0000001"
    assert t["KC"]["qb"]["flags"] == ["last game's starter Fixture Quarterback One practice: DNP; no designation published"]
    assert t["ATL"]["qb"]["flags"] == ["schedule file lists Fixture Quarterback Nine instead of last game's starter "
                                       "Fixture Quarterback Three (unconfirmed)"]     # Full practice alone raises no flag
    assert t["LV"]["qb"]["last_starter"] is None and t["LV"]["qb"]["flags"] == []
    _load(con, "week10_fri.csv", "2026-11-13T07:00:00+00:00")
    t = _teams(nr.build(con, NOW, GAMES))
    assert t["SEA"]["qb"]["flags"] == ["last game's starter Fixture Quarterback Five is designated Out"]
    assert all(x["qb"]["confirmed_starter"] is None for x in t.values())


def test_stale_and_never_fetched(con):
    rep = nr.build(con, NOW, GAMES)                                      # nothing fetched yet
    assert rep["source"]["stale"] and rep["source"]["last_success"] is None and rep["summary"]["teams_missing"] == 4
    _load(con, "week10_wed.csv", "2026-11-13T07:00:00+00:00")
    assert nr.build(con, NOW, GAMES)["source"]["stale"] is False
    late = nr.build(con, NOW + timedelta(hours=40), GAMES)
    assert late["source"]["stale"] and late["source"]["published_age_h"] == 49.0
    assert "**Stale: YES**" in nr.to_markdown(late)


def test_failed_fetch_shows_in_source_health(con):
    _load(con, "week10_wed.csv", "2026-11-13T07:00:00+00:00")

    def blocked(url):
        raise nv.SourceBlocked("HTTP 429")
    nv.ingest(con, 2026, blocked)
    src = nr.build(con, NOW, GAMES)["source"]
    assert src["last_outcome"] == "blocked" and "429" in src["last_error"] and src["last_success"]
    assert src["outcomes"] == {"fetched": 1, "blocked": 1}


def test_reschedule_keeps_the_game_week(con):
    _load(con, "week10_fri.csv", "2026-11-13T07:00:00+00:00")
    con.execute("UPDATE events SET kickoff_utc='2026-11-17T01:15:00+00:00' WHERE event_id LIKE '%401000003'")   # moved to Monday
    g = [x for x in nr.build(con, NOW, GAMES)["games"] if x["event_id"].endswith("401000003")][0]
    assert g["week"] == 10 and g["away"]["designations"]["Questionable"] == 1
    con.execute("UPDATE events SET status='postponed' WHERE event_id LIKE '%401000003'")
    assert nr.build(con, NOW, GAMES)["summary"]["mapped_games"] == 1


def test_team_mismatch_is_not_mapped(con):
    con.execute("UPDATE events SET home='Denver Broncos' WHERE event_id LIKE '%401000004'")
    rep = nr.build(con, NOW, GAMES)
    assert rep["summary"]["mapped_games"] == 1 and {u.get("reason") for u in rep["unmapped"]} == {None, "team mismatch"}


def test_espn_disagreements(con):
    _load(con, "week10_fri.csv", "2026-11-13T07:00:00+00:00")
    espn_extra._ensure(con)
    rows = [("Kansas City Chiefs", "Fixture Quarterback One", "Out"),            # nflverse: Questionable -> conflict
            ("Atlanta Falcons", "Fixture Tackle Four", "Out"),                   # suffix differs, same status -> agree
            ("Atlanta Falcons", "Fixture Corner Six", "Active"),                 # nflverse Doubtful -> nflverse only
            ("Atlanta Falcons", "Fixture Quarterback Three", "Questionable"),    # nflverse has no designation yet
            ("Atlanta Falcons", "Fixture Long Term", "Out"),                     # not on the weekly report -> ESPN only
            ("Atlanta Falcons", "Fixture Reserve", "Injured Reserve")]           # not a game designation: ignored
    con.executemany("INSERT INTO injuries_current VALUES ('nfl',?,?,?,'','2026-11-13T01:00Z','2026-11-13T12:00:00+00:00','u')", rows)
    t = _teams(nr.build(con, NOW, GAMES))
    assert t["KC"]["espn"]["status_conflicts"] == [{"player": "Fixture Quarterback One", "nflverse": "Questionable",
                                                    "espn": "Out", "espn_reported": "2026-11-13T01:00Z"}]
    a = t["ATL"]["espn"]
    assert a["status_conflicts"] == [] and a["espn_designated_nflverse_pending"] == 1
    assert [x["player"] for x in a["nflverse_only"]] == ["Fixture Corner Six"]
    assert [x["player"] for x in a["espn_only"]] == ["Fixture Long Term"]
    assert t["SEA"]["espn"]["available"] is False


def test_ambiguous_names_are_not_paired(con):
    _load(con, "week10_fri.csv", "2026-11-13T07:00:00+00:00")
    espn_extra._ensure(con)
    con.executemany("INSERT INTO injuries_current VALUES ('nfl','Kansas City Chiefs',?,'Out','','r','2026-11-13T12:00:00+00:00','u')",
                    [("Fixture Quarterback One",), ("Fixture Quarterback One Jr.",)])
    e = _teams(nr.build(con, NOW, GAMES))["KC"]["espn"]
    assert e["ambiguous_names"] == 1 and e["status_conflicts"] == [] and e["espn_only"] == []
    assert nr.name_key("José Núñez-Smith III") == "jose nunez smith"


def test_history_coverage_counts_team_games_without_rows():
    recs = nv.parse((FX / "week10_fri.csv").read_bytes())[0]
    h = nr.history_coverage(recs, GAMES, 2026)
    assert (h["team_games_scheduled"], h["team_games_with_rows"], h["team_games_no_rows"]) == (4, 3, 1)    # LV has no rows
    assert h["team_games_with_designation"] == 3 and h["rows_with_provider_time"] == 0 and h["qb_rows"] == 3


def test_report_is_written_and_states_its_limits(con, tmp_path, monkeypatch):
    from sbi import config
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path / "reports")
    _load(con, "week10_fri.csv", "2026-11-13T07:00:00+00:00")
    nr.write(con, NOW, GAMES, [nr.history_coverage(nv.parse((FX / "week10_fri.csv").read_bytes())[0], GAMES, 2026)])
    md = (tmp_path / "reports" / "nfl_availability.md").read_text()
    assert "Informational risk flags only" in md and "CC-BY-4.0" in md and "| Kansas City Chiefs |" in md
    assert "No source used here confirms a starting quarterback" in md
    assert (tmp_path / "data" / "coverage" / "nfl_reports_latest.json").exists()


def test_context_only_and_off_by_default():
    """The adapter must not reach into the model, and production must not run it unless the owner opts in."""
    root = Path(__file__).resolve().parent.parent
    for mod in ("sbi/sources/nflverse_injuries.py", "sbi/nfl_reports.py"):
        src = (root / mod).read_text()
        assert not re.search(r"^\s*(from|import)\s+.*\b(ev|engine|models|us|pipeline|settle|site|markets)\b", src, re.M), mod
        assert not re.search(r"\b(recommendations|predictions|rec_updates|odds)\b\s*(\(|SET|VALUES)", src), mod
    assert 'os.environ.get("SBI_NFL_REPORTS") == "1"' in (root / "sbi/pipeline.py").read_text()
    assert "SBI_NFL_REPORTS" not in (root / ".github/workflows/daily.yml").read_text()


def test_coverage_audit_lists_the_new_feed(con):
    from sbi import coverage
    _load(con, "week10_fri.csv", "2026-11-13T07:00:00+00:00")
    assert coverage.context(con, NOW)["nfl_reports"] == {"player_weeks": 5, "teams": 3, "weeks": 1, "with_designation": 4,
                                                         "with_practice_status": 5, "updates_logged": 5}
