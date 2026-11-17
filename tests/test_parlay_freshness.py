"""Combined-quote freshness matches the site refresh cadence (issue #37).

The static site is rebuilt by the scheduled job; a verified bookmaker quote must stay usable for
at least one full refresh interval (plus build time), and the Python and browser limits must agree.
"""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sbi import parlay_quotes as pq
from sbi import parlays

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)


def _cron_interval_minutes() -> int:
    text = (ROOT / ".github" / "workflows" / "daily.yml").read_text()
    crons = re.findall(r'cron:\s*"([^"]+)"', text)
    assert len(crons) == 1, crons
    minute, hour = crons[0].split()[:2]
    assert minute.isdigit(), "the refresh must run at a fixed minute"
    m = re.fullmatch(r"\*/(\d+)", hour)
    assert m, f"expected an every-N-hours schedule, got {hour!r}"
    return int(m.group(1)) * 60


def test_refresh_constant_matches_the_scheduled_job():
    assert parlays.SITE_REFRESH_MINUTES == _cron_interval_minutes() == 120


def test_quote_limit_covers_one_full_refresh_plus_build_time():
    assert parlays.MAX_QUOTE_AGE_MINUTES == parlays.SITE_REFRESH_MINUTES + parlays.QUOTE_BUILD_ALLOWANCE_MINUTES
    assert parlays.MAX_QUOTE_AGE_MINUTES > _cron_interval_minutes()
    assert parlays.MAX_QUOTE_AGE_MINUTES == 150


def test_browser_limit_equals_python_limit():
    js = (ROOT / "docs" / "assets" / "doyen.js").read_text()
    m = re.search(r"maxQuoteMin:\s*(\d+)", js)
    assert m and int(m.group(1)) == parlays.MAX_QUOTE_AGE_MINUTES


def test_blocker_text_states_the_same_limit():
    assert f"last {parlays.MAX_QUOTE_AGE_MINUTES} minutes" in parlays.BLOCKERS["combined_quote"]


def _legs():
    def leg(i, league):
        return {"id": f"p{i}", "event_id": f"e{i}", "selection_key": "H", "league": league,
                "prices": {"BookA": {"H": 2.2}, "BookB": {"H": 2.1}, "BookC": {"H": 2.15}}}
    return {x["id"]: x for x in (leg(1, "E0"), leg(2, "SP1"))}


@pytest.mark.parametrize("age, ok", [(5, True), (119, True), (149, True), (150, True), (151, False), (240, False)])
def test_owner_quote_counts_only_inside_the_limit(age, ok):
    q = pq.make("BookA", 4.8, ["p1", "p2"], NOW - timedelta(minutes=age), "BookA bet slip", NOW)
    why = pq.quote_problem(q, _legs(), NOW, parlays.MAX_QUOTE_AGE_MINUTES)
    assert (why is None) == ok, why
    if not ok:
        assert why == "quote is stale"
