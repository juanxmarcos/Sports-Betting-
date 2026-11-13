"""Recommended Parlays of the Day (issue #7, stage 0): the arithmetic is right, the leg screens
exclude what they must, and NOTHING is ever published while the prerequisites are missing."""
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sbi import config, db, parlays, site

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tests" / "js" / "render_route.js"
NOW = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)          # 10:00 in New York
TZ = "America/New_York"


def _leg(i, *, hours=5, comp=None, sport="soccer", state="active", prob=0.5, odds_age_h=1.0, prices=None, teams=None,
         event_id=None, sel="H"):
    return {"id": f"p{i}", "event_id": event_id or f"e{i}", "sport": sport, "competition": comp or f"League {i}",
            "participants": teams or [f"Home {i}", f"Away {i}"], "start_utc": (NOW + timedelta(hours=hours)).isoformat(),
            "state": state, "prob": prob, "odds_updated": (NOW - timedelta(hours=odds_age_h)).isoformat(),
            "source": "https://api.the-odds-api.com/v4/x", "selection_key": sel,
            "prices": prices if prices is not None else {"BookA": {"H": 2.2, "A": 1.7}, "BookB": {"H": 2.1, "A": 1.75}}}


# ---------- arithmetic ----------
def test_combined_odds_and_joint_probability_multiply():
    assert parlays.combined_odds([2.0, 1.5]) == pytest.approx(3.0)
    assert parlays.combined_odds([2.0, 1.5, 1.8]) == pytest.approx(5.4)
    assert parlays.joint_prob_independent([0.5, 0.6]) == pytest.approx(0.30)


def test_parlay_ev_is_joint_times_odds_minus_one_never_a_product_of_leg_evs():
    probs, odds = [0.55, 0.60], [2.0, 1.8]
    ev = parlays.parlay_ev(parlays.joint_prob_independent(probs), parlays.combined_odds(odds))
    assert ev == pytest.approx(0.55 * 0.60 * 2.0 * 1.8 - 1)              # +18.8%
    leg_evs = [p * o - 1 for p, o in zip(probs, odds)]                   # +10%, +8%
    assert ev != pytest.approx(leg_evs[0] * leg_evs[1])                  # multiplying EVs gives 0.8%: wrong
    assert ev != pytest.approx(sum(leg_evs))
    assert parlays.parlay_ev(0.25, 4.0) == pytest.approx(0.0)            # fair price -> zero EV


def test_two_negative_ev_legs_never_make_a_positive_parlay():
    probs, odds = [0.45, 0.45], [2.0, 2.0]
    assert parlays.parlay_ev(parlays.joint_prob_independent(probs), parlays.combined_odds(odds)) < 0


@pytest.mark.parametrize("bad", [[2.0], [], [2.0, 1.0], [2.0, 0.5]])
def test_combined_odds_rejects_invalid_input(bad):
    with pytest.raises(ValueError):
        parlays.combined_odds(bad)


@pytest.mark.parametrize("bad", [[0.5], [0.5, 0.0], [0.5, 1.0], [0.5, 1.2]])
def test_joint_probability_rejects_invalid_input(bad):
    with pytest.raises(ValueError):
        parlays.joint_prob_independent(bad)


# ---------- correlation ----------
def test_same_game_and_shared_team_and_same_competition_are_not_independent():
    a = _leg(1)
    assert "same game" in parlays.correlation_reasons(a, _leg(2, event_id="e1"))
    assert "shared team or player" in parlays.correlation_reasons(a, _leg(2, teams=["home 1", "Other"]))
    assert "same competition" in parlays.correlation_reasons(a, _leg(2, comp="league 1"))
    assert parlays.correlation_reasons(a, _leg(2)) == []
    assert parlays.correlation_reasons(a, _leg(2, comp="League 1", sport="nba")) == []   # same name, other sport


# ---------- leg screens ----------
@pytest.mark.parametrize("kw,reason", [
    ({"state": "updated"}, "pick is not active"),
    ({"state": "withdrawn"}, "pick is not active"),
    ({"hours": -1}, "event has started"),
    ({"hours": 30}, "not scheduled today"),
    ({"odds_age_h": 30}, "price is stale"),
    ({"hours": 5, "odds_age_h": 7}, "price is stale"),          # within 10h of the start the limit is 6h
])
def test_inactive_started_other_day_and_stale_legs_are_unusable(kw, reason):
    assert parlays.leg_problem(_leg(1, **kw), NOW, "2026-11-13", TZ) == reason


def test_a_fresh_active_pick_today_is_a_usable_leg():
    assert parlays.leg_problem(_leg(1), NOW, "2026-11-13", TZ) is None


def test_leg_without_a_price_timestamp_is_unusable():
    leg = _leg(1)
    leg["odds_updated"] = None
    assert parlays.leg_problem(leg, NOW, "2026-11-13", TZ) == "no price timestamp"


# ---------- bookmaker executability ----------
def test_single_book_must_price_every_leg_itself():
    a = _leg(1, prices={"BookA": {"H": 2.2}, "BookB": {"H": 2.0}})
    b = _leg(2, prices={"BookB": {"H": 1.9}, "BookC": {"H": 2.5}})
    assert parlays.single_book_quotes([a, b]) == {"BookB": [2.0, 1.9]}      # never BookA x BookC
    c = _leg(3, prices={"BookC": {"H": 2.5}})
    assert parlays.single_book_quotes([a, c]) == {}


def test_single_book_ignores_aggregates_live_feeds_and_other_selections():
    a = _leg(1, prices={"Avg": {"H": 2.2}, "Bet365 Live": {"H": 2.3}, "BookA": {"A": 3.0}})
    b = _leg(2, prices={"Avg": {"H": 2.0}, "Bet365 Live": {"H": 2.1}, "BookA": {"H": 2.0}})
    assert parlays.single_book_quotes([a, b]) == {}


# ---------- the block: nothing is ever published in stage 0 ----------
def test_no_picks_gives_an_honest_empty_block():
    b = parlays.build([], NOW, TZ)
    assert b["recommendations"] == [] and b["status"] == "not_published" and b["headline"] == "No verified parlays today"
    assert b["date"] == "2026-11-13" and b["audit"]["combinations_checked"] == 0
    assert {x["key"] for x in b["blockers"]} == {"combined_quote", "joint_calibration"}


def test_even_perfect_legs_are_not_published_without_the_prerequisites():
    """Two unrelated, fresh, active picks today, both priced by one bookmaker at positive value:
    the screens pass, and the parlay is still NOT published."""
    legs = [_leg(1, prob=0.55), _leg(2, prob=0.55)]
    b = parlays.build(legs, NOW, TZ)
    assert b["audit"]["usable_legs_today"] == 2 and b["audit"]["combinations_checked"] == 1
    assert b["audit"]["passed_leg_screens"] == 1
    assert b["recommendations"] == [] and b["status"] == "not_published" and len(b["blockers"]) == 2
    text = json.dumps(b)
    assert "Home 1" not in text and "p1" not in text and "BookA" not in text        # no legs, ids or books leak out


def test_prerequisites_are_not_met():
    """Guard: enabling either capability is a deliberate, reviewed change (docs/PARLAYS.md)."""
    assert parlays.PREREQUISITES == {"combined_quote": None, "joint_calibration": None}


def test_audit_counts_exclusions_and_each_combination_once():
    legs = [_leg(1), _leg(2, comp="League 1"),                              # same competition as leg 1
            _leg(3, prices={"BookZ": {"H": 2.0}}),                          # no common bookmaker with the others
            _leg(4, state="withdrawn"), _leg(5, hours=40)]
    a = parlays.build(legs, NOW, TZ)["audit"]
    assert a["straight_picks_seen"] == 5 and a["usable_legs_today"] == 3
    assert a["combinations_checked"] == 4                                   # 3 pairs + 1 triple
    assert a["passed_leg_screens"] == 0
    assert a["excluded"] == {"combination: no single bookmaker prices every leg": 2, "combination: same competition": 2,
                             "leg: not scheduled today": 1, "leg: pick is not active": 1}


def test_combination_without_positive_value_at_one_bookmaker_is_excluded():
    legs = [_leg(1, prob=0.40), _leg(2, prob=0.40)]                         # 0.16 x 2.2 x 2.2 < 1
    a = parlays.build(legs, NOW, TZ)["audit"]
    assert a["passed_leg_screens"] == 0
    assert a["excluded"] == {"combination: no positive value at any single bookmaker": 1}


def test_thresholds_are_untouched():
    r = config.SelectionRules()
    assert (r.min_ev, r.min_odds, r.max_odds, r.min_bookmakers, r.max_per_event) == (0.03, 1.30, 6.00, 3, 1)


# ---------- site export ----------
def _insert_pick(con, i, start, now):
    con.execute("INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,source,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (f"e{i}", "football", "E0", start, f"Home {i}", f"Away {i}", "test", now.isoformat()))
    cols = {"rec_id": f"r{i}", "event_id": f"e{i}", "published_at": now.isoformat(), "sport": "football", "league": "E0",
            "kickoff_utc": start, "home": f"Home {i}", "away": f"Away {i}", "market": "1X2", "selection": "H", "bookmaker": "BookA",
            "odds": 2.2, "odds_retrieved_at": now.isoformat(), "model_prob": 0.5, "market_prob": 0.5, "final_prob": 0.5,
            "fair_odds": 2.0, "ev": 0.1, "ev_lower": 0.1, "stake_units": 1.0, "model_version": "t", "status": "open",
            "evidence_json": json.dumps({"all_prices": {"BookA": {"H": 2.2}}, "injuries": {"x": 1}, "competition": f"Comp {i}"}),
            "source_urls": "[]"}
    have = {r[1] for r in con.execute("PRAGMA table_info(recommendations)")}
    cols = {k: v for k, v in cols.items() if k in have}
    con.execute(f"INSERT INTO recommendations({','.join(cols)}) VALUES({','.join('?' * len(cols))})", list(cols.values()))
    con.commit()


def test_site_export_carries_the_parlay_block_and_leaves_picks_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path / "r")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    con = db.connect(tmp_path / "t.sqlite")
    now = datetime.now(timezone.utc)
    for i in (1, 2):
        _insert_pick(con, i, (now + timedelta(hours=2 + i)).isoformat(), now)
    before = [tuple(r) for r in con.execute("SELECT * FROM recommendations ORDER BY rec_id")]
    d = json.loads(site.build(con, now).read_text())
    assert [tuple(r) for r in con.execute("SELECT * FROM recommendations ORDER BY rec_id")] == before
    assert len(d["picks"]) == 2 and d["pick_of_the_day"] in ("r1", "r2")           # straight picks unaffected
    p = d["parlays"]
    assert p["recommendations"] == [] and p["status"] == "not_published"
    assert p["audit"]["straight_picks_seen"] == 2
    assert not [t for t in con.execute("SELECT name FROM sqlite_master WHERE name LIKE '%parlay%'")]


# ---------- front end ----------
needs_node = pytest.mark.skipif(not shutil.which("node") and not os.environ.get("CI"), reason="node is not installed")
ISO = "2026-11-13T15:00:00+00:00"


def _pick(pid, start):
    return {"id": pid, "event_id": "ev-" + pid, "sport": "soccer", "competition": "Test League", "title": f"Home {pid} v Away {pid}",
            "start_utc": start, "published_at": "2026-11-12T12:00:00+00:00", "market": "Match result",
            "selection": f"Home {pid} to win", "odds": 2.1, "bookmaker": "Book", "prob": 0.5, "fair_odds": 2.0, "ev": 0.05,
            "why_short": "Price beats the sharp consensus.", "stale": False, "status": {"state": "active", "label": "Active"}}


def _render(parlay_block, hash_="", range_="today", picks=()):
    picks = list(picks)
    data = {"generated": ISO, "default_timezone": TZ, "pick_of_the_day": picks[0]["id"] if picks else None, "picks": picks,
            "history": picks, "events": [], "watching": [], "close_to_value": [], "briefing": {}, "funnel_7d": {}, "sports": {},
            "record": {"won": 0, "lost": 0, "push": 0, "profit_units": 0, "open": len(picks)}}
    if parlay_block is not None:
        data["parlays"] = parlay_block
    out = subprocess.run(["node", str(HARNESS)], input=json.dumps({"data": data, "now": ISO, "hash": hash_, "range": range_}),
                         capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout


def _section(html):
    m = re.search(r'<section class="section" id="parlays">(.*?)</section>', html, re.S)
    return m.group(1) if m else None


@needs_node
def test_home_shows_the_honest_empty_state_below_the_picks_today_only():
    picks = [_pick("a", "2026-11-13T20:00:00+00:00"), _pick("b", "2026-11-13T23:30:00+00:00")]
    html = _render(parlays.build([], NOW, TZ), picks=picks)
    par = _section(html)
    assert par and "<h2>Recommended Parlays of the Day</h2>" in par and "No verified parlays today" in par
    assert 'href="#/parlays"' in par
    assert "<article" not in par and not re.search(r"\d\.\d\d", par) and "%" not in par      # no cards, odds or chances
    assert html.index("#/pick/a") < html.index('id="parlays"') < html.index("Close to Value")
    assert html.count("#/pick/a") >= 1 and html.count("#/pick/b") >= 1                       # straight picks still shown
    assert _section(_render(parlays.build([], NOW, TZ), range_="tomorrow")) is None
    assert _section(_render(parlays.build([], NOW, TZ), range_="week")) is None


@needs_node
def test_home_shows_the_same_empty_state_when_the_data_file_has_no_parlay_block():
    par = _section(_render(None))
    assert par and "No verified parlays today" in par and "<article" not in par


@needs_node
def test_the_front_end_cannot_render_a_parlay_card_even_if_the_data_contains_one():
    block = parlays.build([], NOW, TZ)
    block["status"] = "published"
    block["recommendations"] = [{"legs": [{"title": "Injected FC v Fake United", "odds": 2.5}], "combined_odds": 6.25,
                                 "joint_prob": 0.2, "ev": 0.25, "bookmaker": "FakeBook"}]
    for h in ("", "#/parlays"):
        html = _render(block, h)
        assert "Injected FC" not in html and "FakeBook" not in html and "6.25" not in html
        assert "No verified parlays today" in html


@needs_node
def test_details_page_explains_the_check_the_blockers_and_the_risk():
    legs = [_leg(1), _leg(2, comp="League 1"), _leg(3, state="withdrawn")]
    html = _render(parlays.build(legs, NOW, TZ), "#/parlays")
    assert "Recommended Parlays of the Day</h1>" in html and "No verified parlays today" in html
    for title in ("Today's check", "Why none is published", "What a parlay would need", "How the numbers work", "Risk"):
        assert f"<summary>{title.replace(chr(39), '&#39;')}</summary>" in html
    assert "No bookmaker-quoted parlay price" in html and "No validated joint-probability estimate" in html
    assert "same competition" in html and "pick is not active" in html
    assert "higher-variance" in html and "never a guarantee" in html
    assert "Same-game parlays are out" in html and "never multiplied or added" in html
    assert "docs/PARLAYS.md" in html


@needs_node
def test_details_page_does_not_present_yesterdays_check_as_todays():
    old = parlays.build([_leg(1)], NOW - timedelta(days=1), TZ)
    html = _render(old, "#/parlays")
    assert "No parlay check has been recorded for" in html and "Usable as legs today" not in html
    assert "No bookmaker-quoted parlay price" in html
