"""Daily parlay homepage (issue #27): the card data contract, the payout arithmetic and the
rendered homepage.

Every recommendation below is MOCK data built for these tests. None of it is a real price, game
or pick. The browser only renders mock cards when the test harness sets __DOYEN_ALLOW_MOCK, and
the Python contract rejects them outright, so a mock fixture can never reach the live site."""
import copy
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from sbi import parlays

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tests" / "js" / "render_home.js"
NOW = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)          # 10:00 in New York, Friday 13 Nov
DAY = "2026-11-13"
needs_node = pytest.mark.skipif(not shutil.which("node") and not os.environ.get("CI"), reason="node is not installed")


def _iso(dt):
    return dt.isoformat()


def leg(i, *, hours=4, sport="soccer", status="active", event_id=None, minute=0):
    return {"event_id": event_id or f"mock-ev-{i}", "sport": sport, "title": f"Mock Home {i} v Mock Away {i}",
            "market": "Match result", "selection": f"Mock Home {i} to win",
            "start_utc": _iso(NOW + timedelta(hours=hours, minutes=minute)), "status": status}


def rec(pid="mock-1", n_legs=3, odds=6.5, quote_age_min=5, mock=False, **over):
    r = {"parlay_id": pid, "date": DAY, "status": "active", "bookmaker": "MockBook",
         "legs": [leg(f"{pid}-{i}", minute=i) for i in range(n_legs)],
         "quote": {"kind": "bookmaker_combined", "bookmaker": "MockBook", "decimal_odds": odds,
                   "quoted_at": _iso(NOW - timedelta(minutes=quote_age_min)), "source": "mock-fixture"}}
    if mock:
        r["mock"] = True
    r.update(over)
    return r


def block(recs, **over):
    b = {"date": DAY, "timezone": "America/New_York", "generated": _iso(NOW), "status": "published", "blockers": [],
         "recommendations": recs}
    b.update(over)
    return b


# Each case: (name, mutate(rec) -> None, expected problem or None)
def _set(path, value):
    def f(r):
        obj = r
        for k in path[:-1]:
            obj = obj[k]
        obj[path[-1]] = value
    return f


CASES = [
    ("valid", lambda r: None, None),
    ("two legs", lambda r: r.update(legs=r["legs"][:2]), None),
    ("six legs", lambda r: r.update(legs=[leg(f"x{i}") for i in range(6)]), None),
    ("one leg", lambda r: r.update(legs=r["legs"][:1]), "needs 2-6 legs"),
    ("seven legs", lambda r: r.update(legs=[leg(f"x{i}") for i in range(7)]), "needs 2-6 legs"),
    ("stale quote", _set(["quote", "quoted_at"], _iso(NOW - timedelta(hours=11))), "quote is stale"),  # yesterday in New York
    ("quote from the future", _set(["quote", "quoted_at"], _iso(NOW + timedelta(minutes=1))), "quote has no valid time"),
    ("quote without timezone", _set(["quote", "quoted_at"], "2026-11-13T14:55:00"), "quote has no valid time"),
    ("leg tomorrow", lambda r: r["legs"].__setitem__(1, leg("t", hours=20)), "leg is not on today's date"),
    ("leg started", lambda r: r["legs"].__setitem__(0, leg("s", hours=-1)), "leg has started"),
    ("leg withdrawn", lambda r: r["legs"].__setitem__(2, leg("w", status="withdrawn")), "leg is not active"),
    ("leg changed", lambda r: r["legs"].__setitem__(2, leg("c", status="updated")), "leg is not active"),
    ("same event twice", lambda r: r["legs"].__setitem__(1, dict(r["legs"][0])), "two legs on the same event"),
    ("unsupported sport", lambda r: r["legs"].__setitem__(0, leg("h", sport="hockey")), "unsupported sport"),
    ("leg without selection", _set(["legs", 0, "selection"], ""), None),          # problem text differs by side
    ("parlay withdrawn", _set(["status"], "withdrawn"), "parlay is not active"),
    ("yesterday's parlay", _set(["date"], "2026-11-12"), "not today's parlay"),
    ("no parlay_id", _set(["parlay_id"], ""), "missing parlay_id"),
    ("no bookmaker", _set(["bookmaker"], ""), "missing bookmaker"),
    ("quote from another book", _set(["quote", "bookmaker"], "OtherBook"), "quote is from a different bookmaker"),
    ("product of leg prices", _set(["quote", "kind"], "product_of_leg_prices"), "no single-bookmaker combined quote"),
    ("no quote", lambda r: r.pop("quote"), "no single-bookmaker combined quote"),
    ("no provenance", _set(["quote", "source"], ""), "quote has no provenance"),
    ("odds not above 1", _set(["quote", "decimal_odds"], 1.0), "invalid combined odds"),
    ("odds as text", _set(["quote", "decimal_odds"], "6.5"), "invalid combined odds"),
    ("mock flag", _set(["mock"], True), "mock or test data"),
]


def _case(mutate):
    r = rec()
    mutate(r)
    return r


# ---------- Python contract ----------
@pytest.mark.parametrize("name,mutate,want", CASES, ids=[c[0] for c in CASES])
def test_card_contract(name, mutate, want):
    got = parlays.card_problem(_case(mutate), NOW)
    if name == "leg without selection":
        assert got == "leg missing selection"
    else:
        assert got == want


@pytest.mark.parametrize("n", [0, 1, 3, 5])
def test_shown_cards_counts(n):
    assert len(parlays.shown_cards(block([rec(f"p{i}") for i in range(n)]), NOW)) == n


def test_more_than_five_valid_is_capped_and_ordered_by_first_start():
    recs = [rec(f"p{i}") for i in range(7)]
    for i, r in enumerate(recs):
        for j, lg in enumerate(r["legs"]):
            lg["start_utc"] = _iso(NOW + timedelta(hours=8 - i, minutes=j))
    shown = parlays.shown_cards(block(recs), NOW)
    assert [r["parlay_id"] for r in shown] == ["p6", "p5", "p4", "p3", "p2"]


@pytest.mark.parametrize("over", [{"blockers": [{"key": "combined_quote", "text": "x"}]}, {"status": "not_published"},
                                  {"date": "2026-11-12"}, {"blockers": None}])
def test_nothing_is_shown_while_the_block_is_not_cleared(over):
    assert parlays.shown_cards(block([rec()], **over), NOW) == []


def test_invalid_cards_are_dropped_and_valid_ones_kept():
    shown = parlays.shown_cards(block([rec("good"), _case(CASES[5][1]) | {"parlay_id": "stale"}]), NOW)
    assert [r["parlay_id"] for r in shown] == ["good"]


@pytest.mark.parametrize("stake,odds,payout,profit", [
    (10, 6.5, "65.00", "55.00"), (10, 1.005, "10.05", "0.05"), (25, 3.333, "83.33", "58.33"),
    (10, 2.5, "25.00", "15.00"), (0, 4.0, "0.00", "0.00"), (12.5, 12.345, "154.31", "141.81")])
def test_gross_payout_includes_stake_and_net_profit_is_separate(stake, odds, payout, profit):
    assert parlays.gross_payout(stake, odds) == Decimal(payout)
    assert parlays.net_profit(stake, odds) == Decimal(profit)


@pytest.mark.parametrize("stake,odds", [(-1, 2.0), (10, 1.0), ("x", 2.0), (10, float("nan"))])
def test_gross_payout_rejects_bad_input(stake, odds):
    with pytest.raises(ValueError):
        parlays.gross_payout(stake, odds)


def test_card_view_uses_default_ten_dollar_stake():
    v = parlays.card_view(rec(odds=6.5))
    assert v["stake"] == 10 and v["gross_payout"] == "65.00" and v["net_profit"] == "55.00" and v["bookmaker"] == "MockBook"


def test_stage0_build_still_publishes_nothing_with_two_to_six_leg_limits():
    b = parlays.build([], NOW, "America/New_York")
    assert b["recommendations"] == [] and b["status"] == "not_published" and b["leg_limits"] == [2, 6]
    assert {x["key"] for x in b["blockers"]} == {"combined_quote", "joint_calibration"}
    assert parlays.shown_cards(b, NOW) == []
    assert parlays.PREREQUISITES == ("combined_quote", "joint_calibration")


def test_committed_parlay_file_has_the_homepage_shape_and_shows_nothing():
    # The scheduled job rewrites both data files together (site.build); equality is tested there.
    lite = json.loads((ROOT / "docs" / "data" / "parlays.json").read_text())
    assert {"generated", "default_timezone", "parlays"} <= set(lite) <= {"generated", "default_timezone", "parlays",
                                                                         "estimated_parlays"}   # issue #47
    assert lite["parlays"]["recommendations"] == [] and parlays.shown_cards(lite["parlays"], NOW) == []


# ---------- rendered homepage (real docs/assets/doyen.js in Node) ----------
def _run(payload):
    out = subprocess.run(["node", str(HARNESS)], input=json.dumps(payload), capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout


def render(parlay_block, *, allow_mock=True, **extra):
    data = {"generated": _iso(NOW), "default_timezone": "America/New_York", "parlays": parlay_block, "picks": [],
            "history": [], "events": [], "watching": [], "close_to_value": [], "briefing": {}, "funnel_7d": {}, "sports": {},
            "record": {"won": 0, "lost": 0, "push": 0, "profit_units": 0, "open": 0}}
    return _run({"data": data, "now": _iso(NOW), "allowMock": allow_mock, **extra})


def articles(html):
    return re.findall(r'<article class="card parlay" data-parlay="([^"]+)"', html)


@needs_node
@pytest.mark.parametrize("n", [0, 1, 3, 5])
def test_home_renders_zero_one_three_five_cards(n):
    html = render(block([rec(f"p{i}", mock=True) for i in range(n)]))
    assert len(articles(html)) == n
    assert ("No verified parlays today." in html) == (n == 0)
    assert "Recommended Parlays of the Day</h1>" in html and "Friday, November 13" in html


@needs_node
def test_card_shows_legs_bookmaker_combined_odds_ten_dollar_stake_and_gross_payout():
    html = render(block([rec("p1", n_legs=3, odds=6.5, mock=True)]))
    card = html[html.index("<article"):html.index("</article>")]
    assert card.count("<li>") == 3 and "Mock Home p1-0 vs. Mock Away p1-0" in card and "Mock Home p1-2 to win" in card
    assert ">MockBook<" in card and ">6.50<" in card
    assert 'value="10"' in card and "data-stake" in card and ">$65.00<" in card
    assert "Potential payout" in card and "includes the stake" in card and "only if every leg wins" in card
    assert "illustrative" in card and "Mock data · testing only" in card
    for banned in ("Expected value", "Estimated chance", "guarantee", "%"):
        assert banned not in card


@needs_node
@pytest.mark.parametrize("n,shown", [(2, 1), (6, 1), (7, 0)])
def test_home_leg_limits(n, shown):
    html = render(block([rec("p", mock=True, legs=[leg(f"x{i}") for i in range(n)])]))
    assert len(articles(html)) == shown
    if shown:
        assert html.count("<li>") == n


@needs_node
@pytest.mark.parametrize("name,mutate,want", CASES, ids=[c[0] for c in CASES])
def test_browser_and_python_agree_on_every_contract_case(name, mutate, want):
    r = _case(mutate)
    html = render(block([r]), allow_mock=(name != "mock flag"))
    py_ok = parlays.card_problem(r, NOW) is None
    assert (len(articles(html)) == 1) == py_ok, name


@needs_node
def test_mock_cards_never_render_without_the_test_flag():
    html = render(block([rec("p1", mock=True), rec("p2", mock=True)]), allow_mock=False)
    assert articles(html) == [] and "No verified parlays today." in html and "MockBook" not in html


@needs_node
@pytest.mark.parametrize("over", [{"blockers": [{"key": "combined_quote", "text": "x"}]}, {"status": "not_published"},
                                  {"date": "2026-11-12"}])
def test_home_shows_nothing_while_the_block_is_not_cleared(over):
    html = render(block([rec(mock=True)], **over))
    assert articles(html) == [] and "No verified parlays today." in html


@needs_node
def test_current_production_data_renders_the_empty_state():
    data = json.loads((ROOT / "docs" / "data" / "doyen.json").read_text())
    when = datetime.fromisoformat(data["parlays"]["generated"])
    html = _run({"data": data, "now": _iso(when), "allowMock": True})
    # No verified (strict) card. Since #47 the same section may hold labelled estimates instead, and
    # since #57 today's recorded estimates stay on the page after their games start.
    assert articles(html) == []
    assert ("No verified parlays today." in html or "No parlays today:" in html
            or 'data-kind="estimate"' in html or 'data-kind="recorded"' in html)


@needs_node
@pytest.mark.parametrize("value,odds,want", [("10", 6.5, "$65.00"), ("25", 6.5, "$162.50"), ("", 6.5, "—"),
                                             ("-5", 6.5, "—"), ("abc", 6.5, "—"), ("10", 1.005, "$10.05"),
                                             ("12.5", 12.345, "$154.31"), ("1000", 12.345, "$12,345.00"), ("0", 3.0, "—"),
                                             ("10001", 3.0, "—")])
def test_editing_the_stake_recalculates_gross_payout_to_the_cent(value, odds, want):
    assert render(block([]), stake={"value": value, "odds": odds}) == want
    if want != "—":
        assert want.replace(",", "") == "$" + str(parlays.gross_payout(Decimal(value), odds))


@needs_node
def test_home_loads_only_the_small_parlay_file():
    assert json.loads(render(block([]), fetched=True)) == ["data/parlays.json"]


@needs_node
def test_home_falls_back_to_the_full_file_if_the_parlay_file_is_missing():
    html = render(block([rec(mock=True)]), noLite=True)
    assert len(articles(html)) == 1
    assert json.loads(render(block([]), noLite=True, fetched=True)) == ["data/parlays.json", "data/doyen.json"]


@needs_node
def test_secondary_routes_still_load_the_full_research_file():
    data_html = render(block([]), hash="#/history")
    assert "Pick History" in data_html or "history" in data_html.lower()
    assert json.loads(render(block([]), hash="#/picks", fetched=True)) == ["data/doyen.json"]
