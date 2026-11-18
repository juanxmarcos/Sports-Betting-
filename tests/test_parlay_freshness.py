"""Twice-a-day refresh with backups, and same-day price freshness (issue #53, two slots since #63;
replaces #37's 150 minutes).

The static site is rebuilt by a morning and an evening run (New York time) at unusual minutes, plus
backup crons that exit early when their own slot's run already succeeded. A card built from today's run stays shown until its
first leg starts and says when the price was taken; a price from a previous New York day never counts.
"""
import json
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from sbi import parlay_quotes as pq
from sbi import parlays, run_marker

ROOT = Path(__file__).resolve().parents[1]
NY = ZoneInfo("America/New_York")
BUILT = datetime(2026, 11, 17, 9, 47, tzinfo=NY)            # the 9:47 AM EST primary run
GAME = datetime(2026, 11, 17, 19, 30, tzinfo=NY)            # 7:30 PM EST start
PRIMARIES = ("47 10 * * *", "47 22 * * *")    # issue #63: morning and evening


def _crons() -> list[str]:
    return re.findall(r'cron:\s*"([^"]+)"', (ROOT / ".github" / "workflows" / "daily.yml").read_text())


# ---------- schedule ----------
def test_two_daily_primary_crons_at_odd_minutes_plus_backups():
    crons = _crons()
    assert tuple(crons[:2]) == PRIMARIES
    for c in crons:
        minute, hour, dom, month, dow = c.split()
        assert minute.isdigit() and hour.isdigit(), f"each run is once a day at a fixed time: {c!r}"
        assert int(minute) % 5 != 0, f"avoid round minutes, GitHub drops those most: {c!r}"
        assert (dom, month, dow) == ("*", "*", "*")
    assert len(set(crons)) == len(crons) and 2 <= len(crons) - 2 <= 4, "one or two backups per slot"
    # Every morning cron is a New York morning (before 2 PM) and every evening cron is after 2 PM, in
    # both EST and EDT, so each backup is gated by its own slot.
    for c in crons:
        h, m = int(c.split()[1]), int(c.split()[0])
        slots = {run_marker.slot(datetime(2026, month, 15, h, m, tzinfo=timezone.utc)) for month in (1, 7)}
        assert len(slots) == 1, f"{c!r} changes slot with daylight saving time"
    morning = [c for c in crons if run_marker.slot(datetime(2026, 1, 15, int(c.split()[1]), 0, tzinfo=timezone.utc)) == "morning"]
    assert morning[0] == PRIMARIES[0] and 1 <= len(morning) - 1 <= 2
    assert 1 <= len(crons) - len(morning) - 1 <= 2
    # The primaries land around 6 AM / 6 PM New York time (5:47 in EST, 6:47 in EDT).
    for c, target in zip(PRIMARIES, (6, 18)):
        for month in (1, 7):
            local = datetime(2026, month, 15, int(c.split()[1]), 47, tzinfo=timezone.utc).astimezone(NY)
            assert target - 1 <= local.hour <= target


def test_backup_crons_are_gated_and_the_primary_and_manual_runs_are_not():
    wf = (ROOT / ".github" / "workflows" / "daily.yml").read_text()
    assert "workflow_dispatch" in wf
    assert ("github.event_name == 'schedule' && github.event.schedule != '47 10 * * *'"
            " && github.event.schedule != '47 22 * * *'") in wf
    assert "python -m sbi.run_marker >> \"$GITHUB_OUTPUT\"" in wf
    assert "daylight saving" in wf
    for step in ("pip install -r requirements.txt", "python -m pytest -q", "python -m sbi daily", "git push"):
        before = wf[:wf.index(step)]
        assert before.rstrip().rfind("if: steps.gate.outputs.skip != 'true'") > before.rfind("- "), step


# ---------- skip logic (sbi.run_marker) ----------
def test_backup_skips_only_after_a_successful_run_in_the_same_slot_and_new_york_day(tmp_path):
    p = tmp_path / "last_daily_run.json"
    assert not run_marker.ran_this_slot(BUILT, p)                               # no marker yet: run
    run_marker.mark(BUILT, p)
    assert json.loads(p.read_text()) == {"completed_at": BUILT.isoformat(), "ny_date": "2026-11-17",
                                         "slot": "morning", "runs": {"morning": BUILT.isoformat()}}
    assert run_marker.ran_this_slot(BUILT + timedelta(hours=2), p)              # 11:47 morning backup: skip
    assert not run_marker.ran_this_slot(datetime(2026, 11, 17, 18, 29, tzinfo=NY), p)  # evening: run
    assert not run_marker.ran_this_slot(datetime(2026, 11, 18, 7, 29, tzinfo=NY), p)   # next New York day: run
    # 9:47 PM EST is already the next day in UTC; it is still the same New York day (evening slot).
    run_marker.mark(datetime(2026, 11, 17, 21, 47, tzinfo=NY), p)
    assert run_marker.ran_this_slot(datetime(2026, 11, 17, 23, 0, tzinfo=NY), p)
    assert run_marker.ran_this_slot(datetime(2026, 11, 17, 12, 0, tzinfo=NY), p)    # morning kept
    assert set(json.loads(p.read_text())["runs"]) == {"morning", "evening"}


@pytest.mark.parametrize("content", ["", "not json", "{}", '{"completed_at": "2026-11-17T09:47:00"}',
                                     '{"completed_at": "2026-11-17T23:00:00-05:00"}'])
def test_unreadable_naive_or_future_marker_never_skips(tmp_path, content):
    p = tmp_path / "last_daily_run.json"
    p.write_text(content)
    assert not run_marker.ran_this_slot(BUILT, p)


def test_cli_prints_a_github_output_line(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SBI_DATA_DIR", str(tmp_path))
    assert run_marker.main() == 0 and capsys.readouterr().out == "skip=false\n"
    run_marker.mark(datetime.now(timezone.utc))
    assert run_marker.main() == 0 and capsys.readouterr().out == "skip=true\n"


# ---------- strict (verified quote) cards ----------
def _card(quoted_at=BUILT, start=GAME):
    legs = [{"event_id": f"e{i}", "title": f"Home {i} v Away {i}", "selection": f"Home {i}", "sport": "soccer",
             "status": "active", "start_utc": (start + timedelta(minutes=30 * i)).astimezone(timezone.utc).isoformat()}
            for i in range(2)]
    return {"parlay_id": "q1", "date": "2026-11-17", "status": "active", "bookmaker": "BookA", "legs": legs,
            "quote": {"kind": parlays.QUOTE_KIND, "bookmaker": "BookA", "source": "BookA bet slip",
                      "decimal_odds": 4.8, "quoted_at": quoted_at.astimezone(timezone.utc).isoformat()}}


def test_card_built_in_the_morning_is_shown_at_6pm_and_hidden_once_the_first_leg_starts():
    six_pm = datetime(2026, 11, 17, 18, 0, tzinfo=NY)
    assert parlays.card_problem(_card(), six_pm) is None
    assert parlays.card_problem(_card(), GAME) == "leg has started"
    assert parlays.card_problem(_card(), GAME + timedelta(minutes=1)) == "leg has started"


def test_card_from_yesterdays_run_is_hidden():
    yesterday = BUILT - timedelta(days=1)
    rec = _card(quoted_at=yesterday)
    assert parlays.card_problem(rec, datetime(2026, 11, 17, 8, 0, tzinfo=NY)) == "quote is stale"
    rec["date"] = "2026-11-16"
    assert parlays.card_problem(rec, datetime(2026, 11, 17, 8, 0, tzinfo=NY)) == "not today's parlay"


def test_blocker_text_states_the_same_day_rule():
    assert parlays.QUOTE_RULE == "same_ny_day"
    assert "earlier today (New York time)" in parlays.BLOCKERS["combined_quote"]
    assert "150" not in parlays.BLOCKERS["combined_quote"]


def test_browser_applies_the_same_rule():
    js = (ROOT / "docs" / "assets" / "doyen.js").read_text()
    assert 'quoteRule: "same_ny_day"' in js and "maxQuoteMin" not in js
    assert 'if (nyKey(new Date(at)) !== day) return "quote is stale";' in js


def _legs():
    def leg(i, league):
        return {"id": f"p{i}", "event_id": f"e{i}", "selection_key": "H", "league": league,
                "prices": {"BookA": {"H": 2.2}, "BookB": {"H": 2.1}, "BookC": {"H": 2.15}}}
    return {x["id"]: x for x in (leg(1, "E0"), leg(2, "SP1"))}


@pytest.mark.parametrize("quoted, ok", [
    (BUILT, True),
    (datetime(2026, 11, 17, 0, 5, tzinfo=NY), True),           # early today: still today's price
    (datetime(2026, 11, 16, 23, 55, tzinfo=NY), False),        # 18 h old but yesterday in New York
    (BUILT - timedelta(days=1), False),
])
def test_owner_quote_counts_only_on_its_own_new_york_day(quoted, ok):
    now = datetime(2026, 11, 17, 18, 0, tzinfo=NY)
    q = pq.make("BookA", 4.8, ["p1", "p2"], quoted, "BookA bet slip", now)
    why = pq.quote_problem(q, _legs(), now)
    assert (why is None) == ok, why
    if not ok:
        assert why == "quote is stale"


# ---------- the real front end ----------
def test_front_end_card_shows_price_as_of_time_until_the_first_leg_starts():
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    harness = ROOT / "tests" / "js" / "render_home.js"
    block = {"date": "2026-11-17", "status": "published", "blockers": [], "recommendations": [_card()]}

    def render(now):
        data = {"generated": BUILT.isoformat(), "default_timezone": "America/New_York", "parlays": block,
                "picks": [], "history": [], "events": [], "watching": [], "close_to_value": [], "briefing": {},
                "funnel_7d": {}, "sports": {}, "record": {"won": 0, "lost": 0, "push": 0, "profit_units": 0, "open": 0}}
        out = subprocess.run(["node", str(harness)], input=json.dumps({"data": data, "now": now.isoformat(), "hash": ""}),
                             capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        return out.stdout

    at_six = render(datetime(2026, 11, 17, 18, 0, tzinfo=NY))
    assert 'data-parlay="q1"' in at_six
    assert "Price as of 9:47 AM EST — check your book." in at_six
    assert 'data-parlay="q1"' not in render(GAME + timedelta(minutes=1))
    assert 'data-parlay="q1"' not in render(datetime(2026, 11, 18, 9, 0, tzinfo=NY))
