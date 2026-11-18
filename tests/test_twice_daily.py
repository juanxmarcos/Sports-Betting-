"""Issue #63: the site updates twice a day (about 6 AM and 6 PM New York time).

* Backup crons are gated per slot: a morning success never skips an evening backup.
* The free Odds API allowance is split between the two runs; the day's total does not grow.
* The evening run keeps every parlay recorded that morning exactly as recorded and may append new
  ones, built only from games that have not started and are not in a recorded parlay.
* History shows Parlays before single picks.

Every game, price and bookmaker below is test data built for these tests, never a real quote."""
import csv
import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from sbi import config, db, run_marker, site
from sbi import parlay_estimated as pe
from sbi.sources import odds_api as oa

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tests" / "js" / "render_home.js"
NY = ZoneInfo("America/New_York")
DAY = "2026-11-13"
MORNING = datetime(2026, 11, 13, 5, 47, tzinfo=NY)            # 10:47 UTC primary
EVENING = datetime(2026, 11, 13, 17, 47, tzinfo=NY)           # 22:47 UTC primary
needs_node = pytest.mark.skipif(not shutil.which("node") and not os.environ.get("CI"), reason="node is not installed")


# ---------- per-slot backup gate (sbi/run_marker.py) ----------
def test_slots_split_the_new_york_day_at_2pm():
    assert run_marker.slot(datetime(2026, 11, 13, 0, 5, tzinfo=NY)) == "morning"
    assert run_marker.slot(datetime(2026, 11, 13, 13, 59, tzinfo=NY)) == "morning"
    assert run_marker.slot(datetime(2026, 11, 13, 14, 0, tzinfo=NY)) == "evening"
    assert run_marker.slot(datetime(2026, 11, 14, 1, 13, tzinfo=timezone.utc)) == "evening"   # 8:13 PM EST
    assert oa.run_slot(MORNING) == "morning" and oa.run_slot(EVENING) == "evening"


def test_morning_success_does_not_skip_the_evening_backup(tmp_path):
    p = tmp_path / "last_daily_run.json"
    run_marker.mark(MORNING, p)
    assert run_marker.ran_this_slot(MORNING.replace(hour=9, minute=13), p)                  # morning backup: skip
    assert not run_marker.ran_this_slot(EVENING.replace(hour=18, minute=29), p)             # evening backup: run
    assert not run_marker.ran_this_slot(EVENING.replace(hour=20, minute=13), p)


def test_second_evening_backup_skips_after_the_evening_run_succeeded(tmp_path):
    p = tmp_path / "last_daily_run.json"
    run_marker.mark(MORNING, p)
    run_marker.mark(EVENING.replace(hour=18, minute=29), p)          # primary missed, first evening backup ran
    assert run_marker.ran_this_slot(EVENING.replace(hour=20, minute=13), p)                 # second backup: skip
    assert run_marker.ran_this_slot(MORNING.replace(hour=9, minute=13), p)                  # morning still recorded
    data = json.loads(p.read_text())
    assert data["slot"] == "evening" and data["ny_date"] == DAY and set(data["runs"]) == {"morning", "evening"}
    # The next New York day starts fresh in both slots, and yesterday's runs are dropped from the marker.
    tomorrow = MORNING + timedelta(days=1)
    assert not run_marker.ran_this_slot(tomorrow, p)
    run_marker.mark(tomorrow, p)
    assert json.loads(p.read_text())["runs"] == {"morning": tomorrow.isoformat()}
    assert not run_marker.ran_this_slot(EVENING + timedelta(days=1), p)


def test_a_marker_from_before_issue_63_counts_for_its_own_slot_only(tmp_path):
    p = tmp_path / "last_daily_run.json"
    at = datetime(2026, 11, 13, 9, 47, tzinfo=NY)
    p.write_text(json.dumps({"completed_at": at.isoformat(), "ny_date": DAY}))
    assert run_marker.ran_this_slot(at + timedelta(hours=2), p)
    assert not run_marker.ran_this_slot(EVENING, p)


@pytest.mark.parametrize("content", ['{"runs": {"evening": "2026-11-13T17:47:00"}}',          # naive
                                     '{"runs": {"evening": "2026-11-13T23:00:00-05:00"}}',    # future
                                     '{"runs": {"evening": 5}}', '{"runs": []}', "[]"])
def test_bad_slot_entries_never_skip(tmp_path, content):
    p = tmp_path / "last_daily_run.json"
    p.write_text(content)
    assert not run_marker.ran_this_slot(EVENING.replace(hour=18, minute=29), p)


# ---------- Odds API allowance split between the two runs ----------
def test_budget_morning_spends_about_half_and_evening_the_rest():
    morning, evening = datetime(2026, 11, 12, 11, tzinfo=timezone.utc), datetime(2026, 11, 12, 23, tzinfo=timezone.utc)
    # 19 days left; daily allowance (420 - 20) / 19 = 21.05
    assert oa.budget(420, morning) == 10                                    # half of 21.05
    assert oa.budget(420 - 10, evening, spent_today=10) == 11               # the rest of the same allowance
    assert oa.budget(420, morning) + oa.budget(410, evening, spent_today=10) <= oa.budget(420, evening)
    assert oa.budget(420, morning, spent_today=12) == 0                     # a second morning run gets nothing new
    # Large quota: the day's cap is shared, never doubled.
    m = oa.budget(10_000, morning)
    assert m == oa.MAX_CREDITS_PER_DAY // 2
    assert m + oa.budget(10_000 - m, evening, spent_today=m) == oa.MAX_CREDITS_PER_DAY
    # Remaining unknown: the old cap applies to the whole day.
    assert oa.budget(None, morning) == 6 and oa.budget(None, evening, spent_today=6) == 6
    assert oa.budget(None, evening, spent_today=12) == 0


def test_spent_today_counts_both_runs_of_the_new_york_day(tmp_path):
    con = db.connect(tmp_path / "t.sqlite")
    rows = [("2026-11-13T10:50:00+00:00", 8),    # 5:50 AM NY, morning of the 13th
            ("2026-11-14T01:15:00+00:00", 5),    # 8:15 PM NY on the 13th (next UTC day)
            ("2026-11-13T04:00:00+00:00", 7)]    # 11 PM NY on the 12th: a different New York day
    for at, n in rows:
        con.execute("INSERT INTO job_runs(job, started_at, status, details) VALUES ('ingest-odds-api', ?, 'ok', ?)",
                    (at, json.dumps({"credits_spent": n})))
    con.commit()
    assert oa.spent_today(con, datetime(2026, 11, 14, 1, 30, tzinfo=timezone.utc)) == 13
    assert oa.spent_today(con, datetime(2026, 11, 13, 22, 47, tzinfo=timezone.utc)) == 13


# ---------- evening build keeps the morning's parlays and only appends ----------
@pytest.fixture
def con(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(config, "SITE_DIR", tmp_path / "site")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    return db.connect(tmp_path / "t.sqlite")


def _books(soft_home=2.10):
    return {"Pinnacle": {"home": 1.95, "away": 1.95}, "DraftKings": {"home": 1.93, "away": 1.93},
            "Unibet": {"home": 1.94, "away": 1.94}, "Bet365": {"home": soft_home, "away": 1.80}}


def _game(con, i, ko):
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (f"nba:{i}", "nba", "NBA", ko.astimezone(timezone.utc).isoformat(), f"H{i}", f"A{i}", "scheduled",
                 "test", db.utcnow()))


def _price(con, i, retrieved, soft_home=2.10):
    for bk, q in _books(soft_home).items():
        for sel, price in q.items():
            con.execute("""INSERT INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,retrieved_at)
                           VALUES (?,?,?,?,?,?,?,?,?)""", (f"nba:{i}", bk, "ML", sel, None, price, "pre",
                                                           "https://api.the-odds-api.com/v4/x",
                                                           retrieved.astimezone(timezone.utc).isoformat()))


def _ledger():
    with pe.ledger_path().open(newline="") as f:
        return list(csv.DictReader(f))


def test_evening_build_keeps_morning_parlays_exactly_and_appends_new_ones(con):
    # Morning: four games tonight, priced at 5:40 AM.
    for i in range(1, 5):
        _game(con, i, datetime(2026, 11, 13, 19, 0, tzinfo=NY) + timedelta(minutes=10 * i))
        _price(con, i, MORNING - timedelta(minutes=7))
    con.commit()
    d = json.loads(site.build(con, MORNING, write_shadow=True).read_text())
    added = d["estimated_parlays"]["ledger_rows_added"]
    assert added >= 1
    ledger_bytes = pe.ledger_path().read_bytes()
    morning_rows = _ledger()
    morning_ids = {r["parlay_id"] for r in morning_rows}
    morning_events = {x["event_id"] for r in morning_rows for x in json.loads(r["legs"])}

    # Evening: the morning games get new (better) prices; two later games appear with fresh prices.
    for i in range(1, 5):
        _price(con, i, EVENING - timedelta(minutes=7), soft_home=2.40)
    for i in (5, 6):
        _game(con, i, datetime(2026, 11, 13, 21, 0, tzinfo=NY) + timedelta(minutes=10 * i))
        _price(con, i, EVENING - timedelta(minutes=7))
    con.commit()
    d = json.loads(site.build(con, EVENING, write_shadow=True).read_text())
    e = d["estimated_parlays"]

    # The morning rows are byte-for-byte unchanged; anything new is appended after them.
    assert pe.ledger_path().read_bytes().startswith(ledger_bytes)
    rows = _ledger()
    assert rows[:len(morning_rows)] == morning_rows
    new = rows[len(morning_rows):]
    assert e["ledger_rows_added"] == len(new) >= 1
    assert e["recorded_earlier_today"] == len(morning_rows)
    # New cards use only games that are not in a morning parlay, and never a morning parlay_id.
    for r in new:
        assert r["parlay_id"] not in morning_ids and r["date"] == DAY
        assert not {x["event_id"] for x in json.loads(r["legs"])} & morning_events
        assert r["first_seen"] == EVENING.isoformat()
    assert not {r["parlay_id"] for r in e["recommendations"]} & morning_ids
    # The homepage's recorded list still carries the morning cards at their morning prices.
    today = {r["parlay_id"]: r for r in e["ledger_today"]}
    for r in morning_rows:
        assert today[r["parlay_id"]]["estimated_odds"] == float(r["estimated_odds"])
    # The daily cap is shared by both runs.
    assert len(rows) <= pe.MAX_CARDS


def test_build_fills_only_what_is_left_of_the_daily_cap(con):
    for i in range(1, 3):
        _game(con, i, datetime(2026, 11, 13, 21, 0, tzinfo=NY) + timedelta(minutes=10 * i))
        _price(con, i, EVENING - timedelta(minutes=7))
    con.commit()
    assert len(pe.build(con, EVENING)["recommendations"]) == 1
    full = [{"parlay_id": f"pe-m{k}", "date": DAY, "legs": [{"event_id": f"nba:m{k}"}]} for k in range(pe.MAX_CARDS)]
    assert pe.build(con, EVENING, recorded_today=full)["recommendations"] == []
    # Rows from another day neither block games nor use up today's cap.
    old = [dict(r, date="2026-11-12", legs=[{"event_id": "nba:1"}]) for r in full]
    assert len(pe.build(con, EVENING, recorded_today=old)["recommendations"]) == 1


# ---------- History: Parlays first, single picks after ----------
@needs_node
def test_history_renders_parlays_before_single_picks():
    now = datetime(2026, 11, 13, 23, 0, tzinfo=timezone.utc)
    ko = now - timedelta(days=1)
    parlay = {"parlay_id": "pe-h1", "date": "2026-11-12", "first_seen": (ko - timedelta(hours=5)).isoformat(),
              "kind": pe.ESTIMATE_KIND, "bookmaker": "BookA", "n_legs": 2, "estimated_odds": 4.0, "stake": "10.00",
              "gross_payout": "40.00", "result": "won", "paper_pl": "30.00",
              "legs": [{"event_id": f"ev{i}", "title": f"H{i} v A{i}", "selection": "home", "selection_text": f"H{i} to win",
                        "start_utc": ko.isoformat(), "result": "won"} for i in (1, 2)]}
    pick = {"id": "r1", "event_id": "ev9", "sport": "nba", "title": "H9 v A9", "selection": "H9 to win", "odds": 2.1,
            "published_at": (now - timedelta(days=1)).isoformat(), "status": {"state": "settled", "result": "won"}}
    est = {"status": "estimated", "kind": pe.ESTIMATE_KIND, "date": DAY, "recommendations": [], "ledger_today": [],
           "record": {"rows": 1, "won": 1, "lost": 0, "void": 0, "open": 0, "paper_pl": "30.00", "staked": "10.00",
                      "by_legs": {"2": {"rows": 1, "won": 1, "lost": 0, "void": 0, "open": 0, "paper_pl": "30.00"}}}}
    data = {"generated": now.isoformat(), "default_timezone": "America/New_York",
            "parlays": {"date": DAY, "status": "not_published", "blockers": [], "recommendations": []},
            "estimated_parlays": est, "parlay_history": [parlay], "picks": [], "history": [pick], "events": [],
            "watching": [], "close_to_value": [], "briefing": {}, "funnel_7d": {}, "sports": {},
            "record": {"won": 1, "lost": 0, "push": 0, "profit_units": 1.1, "open": 0}}
    out = subprocess.run(["node", str(HARNESS)], input=json.dumps({"data": data, "now": now.isoformat(), "hash": "#/history"}),
                         capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    html = out.stdout
    for marker in ('id="parlay-history"', 'data-ph="pe-h1"', 'data-ph-by-legs', 'id="pick-history"',
                   "<h2>Single picks</h2>", 'data-go="#/pick/r1"'):
        assert marker in html, marker
    assert html.index("<h1>Pick History</h1>") < html.index('id="parlay-history"') < html.index('data-ph="pe-h1"') \
        < html.index('id="pick-history"') < html.index('data-go="#/pick/r1"')
    # With no single picks in the period, Parlays still come first and the empty state follows.
    data["history"] = []
    html = subprocess.run(["node", str(HARNESS)], input=json.dumps({"data": data, "now": now.isoformat(), "hash": "#/history"}),
                          capture_output=True, text=True, timeout=30).stdout
    assert html.index('data-ph="pe-h1"') < html.index("No picks in this period")
