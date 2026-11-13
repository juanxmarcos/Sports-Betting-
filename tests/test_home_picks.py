"""Homepage contract (issue #6): Picks of the Day are plural peers, headings match the period,
and inactive picks are never presented as currently qualifying.

Renders the real docs/assets/doyen.js in Node against small fixtures with a fixed clock."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tests" / "js" / "render_home.js"
NOW = "2026-11-13T15:00:00+00:00"          # 10:00 in New York (the default timezone)

if not shutil.which("node"):
    if os.environ.get("CI"):
        raise RuntimeError("node is required for the homepage tests")
    pytestmark = pytest.mark.skip(reason="node is not installed")


def _pick(pid, start, state="active", title=None, ev=0.05):
    return {"id": pid, "event_id": "ev-" + pid, "sport": "soccer", "competition": "Test League",
            "title": title or f"Home {pid} v Away {pid}", "start_utc": start, "published_at": "2026-11-12T12:00:00+00:00",
            "market": "Match result", "selection": f"Home {pid} to win", "odds": 2.1, "bookmaker": "Book",
            "prob": 0.5, "fair_odds": 2.0, "ev": ev, "why_short": "Price beats the sharp consensus.",
            "stale": False, "status": {"state": state, "label": state.capitalize(), "note": f"note for {pid}"}}


def _data(picks, potd=None):
    return {"generated": NOW, "default_timezone": "America/New_York", "pick_of_the_day": potd, "picks": picks,
            "history": picks, "events": [], "watching": [], "close_to_value": [], "briefing": {}, "funnel_7d": {},
            "sports": {}, "record": {"won": 0, "lost": 0, "push": 0, "profit_units": 0, "open": len(picks)}}


def render(picks, range_="today", potd=None):
    out = subprocess.run(["node", str(HARNESS)], input=json.dumps({"data": _data(picks, potd), "now": NOW, "range": range_}),
                         capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout


def section(html, sid):
    m = re.search(rf'<section class="section[^"]*" id="{sid}">(.*?)</section>', html, re.S)
    return m.group(1) if m else None


def cards(html):
    return re.findall(r'<article class="([^"]*)" data-go="#/pick/([^"]+)"', html or "")


TODAY_1 = "2026-11-13T20:00:00+00:00"       # 15:00 New York, today
TODAY_2 = "2026-11-13T23:30:00+00:00"       # 18:30 New York, today
TOMORROW = "2026-11-14T20:00:00+00:00"
IN_4_DAYS = "2026-11-17T20:00:00+00:00"
STARTED = "2026-11-13T14:00:00+00:00"       # kicked off an hour ago


def test_zero_picks_is_an_honest_empty_state():
    html = render([])
    assert "<h1" in html and "Picks of the Day</h1>" in html
    assert "No picks qualify today yet." in html
    assert cards(html) == []
    assert "Pick of the Day" not in html                     # the singular concept is gone
    assert "<b>No</b> picks qualify yet" in html


def test_one_pick_is_shown_without_special_treatment():
    html = render([_pick("a", TODAY_1)], potd="a")
    assert cards(section(html, "picks")) == [("card cc pick", "a")]
    assert "No picks qualify" not in html
    assert "<b>1</b> pick qualifies" in html
    assert "Pick of the Day" not in html and "crown" not in html and "feat" not in html


def test_multiple_picks_are_equal_peers_regardless_of_pick_of_the_day():
    picks = [_pick("late", TODAY_2, ev=0.20), _pick("early", TODAY_1, ev=0.04)]
    html = render(picks, potd="late")                        # the legacy scalar must not drive highlighting
    got = cards(section(html, "picks"))
    assert got == [("card cc pick", "early"), ("card cc pick", "late")]   # start-time order, identical classes
    assert "More picks" not in html
    assert html.count("Expected value") == 2                 # every card keeps EV, chance and odds
    assert html.count("Estimated chance") == 2
    assert "<b>2</b> picks qualify" in html


def test_today_excludes_other_days_and_started_events():
    html = render([_pick("t", TODAY_1), _pick("tm", TOMORROW), _pick("gone", STARTED)])
    assert [c[1] for c in cards(html)] == ["t"]


@pytest.mark.parametrize("state", ["withdrawn", "expired", "settled"])
def test_inactive_picks_are_not_presented_as_daily_picks(state):
    # Even if such a record reached the picks list, the homepage must not list it or count it.
    html = render([_pick("x", TODAY_1, state=state)], potd="x")
    assert cards(html) == []
    assert "No picks qualify today yet." in html


def test_changed_pick_is_listed_separately_and_not_counted_as_qualifying():
    html = render([_pick("ok", TODAY_1), _pick("chg", TODAY_2, state="updated")])
    assert [c[1] for c in cards(section(html, "picks"))] == ["ok"]
    assert [c[1] for c in cards(section(html, "changed"))] == ["chg"]
    assert "note for chg" in section(html, "changed")
    assert "<b>1</b> pick qualifies" in html


def test_only_changed_picks_does_not_claim_there_are_no_picks_at_all():
    html = render([_pick("chg", TODAY_1, state="updated")])
    assert "No picks qualify today right now." in html
    assert "1 published pick has changed since publication" in html
    assert "none clears the bar" not in html
    assert [c[1] for c in cards(section(html, "changed"))] == ["chg"]


def test_tomorrow_heading_and_context_match_the_selection():
    html = render([_pick("t", TODAY_1), _pick("tm", TOMORROW)], "tomorrow")
    assert "Tomorrow&#39;s Picks</h1>" in html and "Picks of the Day" not in html
    assert "Saturday, November 14" in html and "Friday, November 13" not in html
    assert [c[1] for c in cards(html)] == ["tm"]
    assert "No picks qualify for tomorrow yet." in render([_pick("t", TODAY_1)], "tomorrow")


def test_week_heading_and_context_match_the_selection():
    html = render([_pick("w", IN_4_DAYS), _pick("t", TODAY_1)], "week")
    assert "This Week&#39;s Picks</h1>" in html and "Picks of the Day" not in html
    assert "Next 7 days · Nov 13 – Nov 20" in html
    assert [c[1] for c in cards(html)] == ["t", "w"]
    assert "No picks qualify this week yet." in render([], "week")


def test_parlay_section_is_reserved_below_picks_without_any_suggestions():
    html = render([_pick("a", TODAY_1)])
    par = section(html, "parlays")
    assert par and "Recommended Parlays of the Day" in par and "Not available yet" in par
    assert "<article" not in par and not re.search(r"\d\.\d\d", par)     # no cards, no odds
    assert html.index('id="picks"') < html.index('id="parlays"') < html.index("Close to Value")
    assert section(render([], "tomorrow"), "parlays") is None            # today only
