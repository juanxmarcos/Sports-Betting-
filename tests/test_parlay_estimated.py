"""Issue #47: estimated parlays of the day (owner-approved, labelled estimates).

Every price, game and team below is test data built for these tests, never a real quote. The
database tests use a temporary database; the browser tests run the real docs/assets/doyen.js."""
import copy
import csv
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from math import prod
from pathlib import Path

import pytest

from sbi import config, db, parlay_engine, parlays, site
from sbi import parlay_estimated as pe

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tests" / "js" / "render_home.js"
NOW = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)          # 10:00 in New York
DAY = "2026-11-13"
needs_node = pytest.mark.skipif(not shutil.which("node") and not os.environ.get("CI"), reason="node is not installed")


def _iso(dt):
    return dt.isoformat()


def _event(i, sport="nba", league="NBA", hours=5, home=None, away=None):
    return {"event_id": f"{sport}:{i}", "sport": sport, "site_sport": parlay_engine.SPORTS.get(sport), "league": league,
            "kickoff_utc": _iso(NOW + timedelta(hours=hours)), "home": home or f"H{i}", "away": away or f"A{i}",
            "competition": None}


def _two_way(soft_home=2.10, soft_away=1.80, soft="Bet365"):
    """Three independent books near 1.95/1.95 plus one soft book with its own prices."""
    return {("ML", None): {"Pinnacle": {"home": 1.95, "away": 1.95}, "DraftKings": {"home": 1.93, "away": 1.93},
                           "Unibet": {"home": 1.94, "away": 1.94}, soft: {"home": soft_home, "away": soft_away}}}


def _pool_leg(i, books, *, hours=5, sport="nba", league="NBA", home=None, away=None):
    """A ready pool leg: books = {bookmaker: (price, prob)}."""
    return {"event_id": f"{sport}:{i}", "sport": sport, "league": league, "competition": league,
            "participants": [home or f"H{i}", away or f"A{i}"], "start_utc": _iso(NOW + timedelta(hours=hours)),
            "title": f"{home or f'H{i}'} v {away or f'A{i}'}", "market": "ML", "selection": "home", "model_prob": None,
            "consensus_prob": 0.5, "prob_source": "model",
            "books": {bk: {"price": p, "prob": q, "value": p * q - 1} for bk, (p, q) in books.items()},
            "best_value": max(p * q - 1 for p, q in books.values()),
            "price_ts": {bk: _iso(NOW - timedelta(minutes=30)) for bk in books}}


# ---------- legs (issue #51: estimated mode only) ----------
def test_one_leg_per_game_and_model_probability_preferred():
    leg, why = pe.legs_for_event(_event(1), _two_way(), None)
    assert why is None and leg["selection"] == "home" and leg["prob_source"] == "market_consensus_ex_book"
    # #51: every pricing bookmaker is kept, value or not; the parlay-level check decides later.
    assert set(leg["books"]) == {"Bet365", "DraftKings", "Unibet", "Pinnacle"}   # a sportsbook, not an exchange
    assert leg["books"]["Bet365"]["prob"] == pytest.approx(0.5, abs=0.003)
    assert leg["books"]["DraftKings"]["value"] < 0 < leg["books"]["Bet365"]["value"]
    leg, _ = pe.legs_for_event(_event(1), _two_way(), {("ML", "home"): 0.53, ("ML", "away"): 0.47})
    assert leg["prob_source"] == "model" and leg["books"]["Bet365"]["prob"] == 0.53
    assert leg["books"]["Bet365"]["value"] == pytest.approx(0.53 * 2.10 - 1)
    assert isinstance(leg, dict)                                   # one leg, never both sides of a game


def test_pinnacle_prices_a_leg_and_exchanges_never_do():
    books = {("ML", None): {"Pinnacle": {"home": 1.95, "away": 1.95}, "Betfair Exchange": {"home": 2.3, "away": 1.75},
                            "Bet365": {"home": 2.0, "away": 1.85}}}
    legs, why = pe.screen_event(_event(1), books, None)
    assert why is None and all("Betfair Exchange" not in x["books"] for x in legs)
    only_exchange = {("ML", None): {"Betfair Exchange": {"home": 2.0, "away": 1.95}}}
    assert pe.screen_event(_event(1), only_exchange, {("ML", "home"): 0.5})[1] == "no bookmaker that offers a parlay slip"


def test_a_leg_below_doyens_probability_is_still_a_candidate():
    flat = {("ML", None): {b: {"home": 1.9, "away": 1.9} for b in ("Pinnacle", "DraftKings", "Unibet", "Bet365")}}
    leg, why = pe.legs_for_event(_event(1), flat, None)
    assert why is None and all(v["value"] < 0 for v in leg["books"].values())


def test_one_bookmaker_is_enough_when_doyen_has_a_model():
    one = {("ML", None): {"Bet365": {"home": 2.0, "away": 1.85}}}
    leg, why = pe.legs_for_event(_event(1), one, {("ML", "home"): 0.52, ("ML", "away"): 0.48})
    assert why is None and set(leg["books"]) == {"Bet365"} and leg["prob_source"] == "model"
    # No model (tennis): one bookmaker alone gives no consensus, so the leg is skipped.
    assert pe.legs_for_event(_event(1, "tennis", "TENNIS:ATP"), one, None) == (
        None, "no model probability and no 2-bookmaker consensus")


def test_no_model_leg_uses_a_two_bookmaker_consensus_including_the_pricing_one():
    two = {("ML", None): {"Bet365": {"home": 2.0, "away": 1.85}, "DraftKings": {"home": 1.95, "away": 1.9}}}
    leg, why = pe.legs_for_event(_event(1, "tennis", "TENNIS:ATP"), two, None)
    assert why is None and set(leg["books"]) == {"Bet365", "DraftKings"}
    v = leg["books"]["Bet365"]
    assert v["prob_source"] == "market_consensus_incl_book"
    # de-vigged median of the two books (both included), never a single book on its own
    from sbi import ev as evm
    i = ["home", "away"].index(leg["selection"])
    fair = [evm.devig_power([q["home"], q["away"]])[i] for q in two[("ML", None)].values()]
    assert v["prob"] == pytest.approx(sum(fair) / 2, abs=1e-6)
    # Where the other bookmakers already give a consensus, it is still preferred (no circularity).
    leg, _ = pe.legs_for_event(_event(1, "tennis", "TENNIS:ATP"), _two_way(), None)
    assert leg["books"]["Bet365"]["prob_source"] == "market_consensus_ex_book"


def test_kept_screens_disagreement_and_band():
    assert pe.legs_for_event(_event(1), _two_way(), {("ML", "home"): 0.70, ("ML", "away"): 0.30})[1] == \
        "model and market disagree strongly"
    longshot = {("ML", None): {b: {"home": 1.10, "away": 7.0} for b in ("Pinnacle", "Bet365")}}
    assert pe.legs_for_event(_event(1), longshot, None)[1] == "probability outside research band"
    assert pe.legs_for_event(_event(1), {}, None)[1] == "no fresh result-market prices"


def test_open_injury_note_is_shown_not_a_screen():
    """Issue #68 (owner decision): an open injury/lineup note no longer excludes the leg; the leg
    carries a short muted line instead."""
    leg, why = pe.legs_for_event(_event(1), _two_way(), None, notes=["Star guard questionable (ankle)"])
    assert why is None and leg["selection"] == "home"
    assert leg["risk_note"] == "Injury/lineup note open: Star guard questionable (ankle)"
    assert pe.legs_for_event(_event(1), _two_way(), None)[0]["risk_note"] is None
    assert pe.risk_note_line([""]) == "Injury/lineup note open"
    assert pe.risk_note_line(["a", "b"]) == "Injury/lineup note open: a (+1 more)"
    long = pe.risk_note_line(["x" * 300])
    assert long.endswith("…") and len(long) <= len("Injury/lineup note open: ") + pe.RISK_NOTE_MAX_CHARS


# ---------- search ----------
def test_same_bookmaker_only_and_price_is_the_product_of_that_books_prices():
    pool = [_pool_leg(1, {"Bet365": (2.1, 0.5)}), _pool_leg(2, {"DraftKings": (2.2, 0.5)}),
            _pool_leg(3, {"Bet365": (1.8, 0.6), "DraftKings": (1.85, 0.6)})]
    cands = pe.search(pool)
    assert cands
    for c in cands:
        bk = c["bookmaker"]
        assert all(bk in x["books"] for x in c["legs"])           # that bookmaker priced every leg
        assert c["estimated_odds"] == pytest.approx(prod(x["books"][bk]["price"] for x in c["legs"]))
        assert c["joint_prob"] == pytest.approx(prod(x["books"][bk]["prob"] for x in c["legs"]))
    sets = {(c["bookmaker"], frozenset(x["event_id"] for x in c["legs"])) for c in cands}
    assert ("Bet365", frozenset({"nba:1", "nba:2"})) not in sets and ("DraftKings", frozenset({"nba:1", "nba:2"})) not in sets


def test_same_game_and_shared_team_blocked_same_competition_allowed():
    a = _pool_leg(1, {"B": (2.1, 0.5)}, home="Lakers", away="Suns")
    b = _pool_leg(2, {"B": (2.1, 0.5)}, home="Lakers", away="Kings")
    c = _pool_leg(3, {"B": (2.1, 0.5)}, home="Bulls", away="Heat")
    same = dict(a, selection="away")
    assert pe.linked(a, b) == ["shared team or player"] and "same game" in pe.linked(a, same)
    assert pe.linked(a, c) == []                                   # both NBA: allowed in estimated mode
    legsets = [frozenset(x["event_id"] for x in k["legs"]) for k in pe.search([a, b, c])]
    assert frozenset({"nba:1", "nba:2"}) not in legsets and frozenset({"nba:1", "nba:3"}) in legsets


def test_two_to_six_legs_only():
    pool = [_pool_leg(i, {"B": (1.9, 0.56)}) for i in range(9)]
    sizes = {c["n_legs"] for c in pe.search(pool)}
    assert min(sizes) == 2 and max(sizes) == 6


def test_five_card_cap_each_game_once_and_earliest_first():
    legs = iter([_pool_leg(i, {"B": (1.9, 0.56)}, hours=1 + i * 0.5) for i in range(40)])
    cands = [pe.combo([next(legs) for _ in range(n)], "B") for n in (2, 2, 2, 3, 3, 3, 4, 5, 4)]
    chosen = pe.select(cands)
    assert len(chosen) == 5
    evs = [x["event_id"] for c in chosen for x in c["legs"]]
    assert len(evs) == len(set(evs))
    firsts = [min(x["start_utc"] for x in c["legs"]) for c in chosen]
    assert firsts == sorted(firsts)
    # #54: per size, at most two of each; bigger sizes pick first, so the fifth card is 4-5 legs or 3.
    sizes = sorted(pe.size_bucket(c["n_legs"]) for c in chosen)
    assert sizes == ["2", "3", "3", "4-5", "4-5"]


# ---------- issue #54: the best parlay of each size ----------
def _sizes(chosen):
    return sorted(pe.size_bucket(c["n_legs"]) for c in chosen)


def test_one_card_of_each_size_when_2_3_and_4_leg_combos_qualify():
    pool = [_pool_leg(i, {"B": (1.9, 0.56)}, hours=1 + i * 0.5) for i in range(9)]   # exactly 4 + 3 + 2 games
    chosen = pe.select(pe.search(pool))
    assert _sizes(chosen) == ["2", "3", "4-5"]
    assert {c["n_legs"] for c in chosen} == {2, 3, 4}
    evs = [x["event_id"] for c in chosen for x in c["legs"]]
    assert len(evs) == len(set(evs)) == 9


def test_thin_day_covers_the_most_sizes_not_the_biggest_card():
    # Five games: a 4-leg card alone would use four of them and leave no 2-leg card. Trying every
    # order of sizes shows a 3-leg and a 2-leg card instead (two sizes beat one).
    pool = [_pool_leg(i, {"B": (1.9, 0.56)}, hours=1 + i * 0.5) for i in range(5)]
    chosen = pe.select(pe.search(pool))
    assert _sizes(chosen) == ["2", "3"]
    # With only four games, two sizes cannot both fit; the bigger size wins the tie.
    assert _sizes(pe.select(pe.search(pool[:4]))) == ["4-5"]


def test_only_2_leg_cards_when_only_2_leg_combos_qualify():
    # Two positive legs and one weak leg in each pair: {strong, weak} pairs qualify, nothing bigger
    # can (a bigger parlay would need a second weak leg or a pair without a positive value).
    pool = [_pool_leg(1, {"B": (2.2, 0.5)}), _pool_leg(2, {"B": (2.0, 0.48)}),
            _pool_leg(3, {"B": (2.2, 0.5)}), _pool_leg(4, {"B": (2.0, 0.48)})]
    cands = pe.search(pool)
    assert cands and {c["n_legs"] for c in cands} >= {2}
    chosen = pe.select([c for c in cands if c["n_legs"] == 2])
    assert chosen and _sizes(chosen) == ["2"] * len(chosen)
    # A size with nothing qualifying is skipped, never padded.
    assert pe.select([]) == []
    two_only = [_pool_leg(1, {"B": (2.2, 0.5)}), _pool_leg(2, {"B": (2.0, 0.48)})]
    assert _sizes(pe.select(pe.search(two_only))) == ["2"]


def test_no_card_ever_has_more_than_one_weak_leg():
    strong = [_pool_leg(i, {"B": (2.6, 0.5)}) for i in range(4)]
    weak = [_pool_leg(10 + i, {"B": (1.9, 0.5)}) for i in range(4)]   # value -0.05 each
    cands = pe.search(strong + weak)
    assert any(pe.weak_legs(c) == 1 for c in cands)
    assert all(pe.weak_legs(c) <= 1 and c["estimated_ev"] > 0 for c in cands)
    # Even a hand-made candidate with two weak legs and a positive value is never selected.
    two_weak = pe.combo([strong[0], strong[1], weak[0], weak[1]], "B")
    assert pe.weak_legs(two_weak) == 2 and two_weak["estimated_ev"] > 0
    assert pe.select([two_weak]) == []
    chosen = pe.select(cands + [two_weak])
    assert chosen and all(pe.weak_legs(c) <= 1 for c in chosen)
    # ... and the card contract rejects such a card on the page too.
    c = pe.card(two_weak, DAY)
    assert c["weak_legs"] == 2 and pe.card_problem(c, NOW) == "more than one leg below its probability"
    assert pe.card_problem(pe.card(pe.combo([strong[0], strong[1], weak[0]], "B"), DAY), NOW) is None


def test_cards_carry_size_and_ten_dollar_payout():
    c = pe.card(pe.combo([_pool_leg(i, {"B": (2.0, 0.55)}) for i in range(4)], "B"), DAY)
    assert c["n_legs"] == 4 and c["size"] == "4-5" and c["stake"] == 10
    assert c["gross_payout"] == "160.00" and c["estimated_odds"] == 16.0 and c["est_hit_chance"] == round(0.55 ** 4, 4)


def test_whole_parlay_value_replaces_the_per_leg_rule():
    # One leg below Doyen's probability (0.48 x 2.0 = 0.96) completes a pair with positive value.
    strong, weak = _pool_leg(1, {"B": (2.2, 0.5)}), _pool_leg(2, {"B": (2.0, 0.48)})
    [c] = pe.search([strong, weak])
    assert c["n_legs"] == 2 and c["estimated_ev"] == pytest.approx(0.5 * 0.48 * 2.2 * 2.0 - 1) and c["estimated_ev"] > 0
    # A pair whose joint value is not positive is never shown.
    assert pe.search([_pool_leg(1, {"B": (2.02, 0.5)}), _pool_leg(2, {"B": (2.0, 0.48)})]) == []
    # Two legs below the probability can never make a positive parlay.
    assert pe.search([_pool_leg(1, {"B": (1.9, 0.5)}), _pool_leg(2, {"B": (1.9, 0.5)})]) == []


def test_no_leg_that_lowers_the_parlay_value_is_added():
    a, b = _pool_leg(1, {"B": (2.2, 0.5)}), _pool_leg(2, {"B": (2.2, 0.5)})
    weak = _pool_leg(3, {"B": (2.0, 0.48)})                        # value -0.04
    sets = {frozenset(x["event_id"] for x in c["legs"]) for c in pe.search([a, b, weak])}
    assert frozenset({"nba:1", "nba:2"}) in sets and frozenset({"nba:1", "nba:3"}) in sets
    # {1, 3} is a positive pair and leg 2 does not lower it, so {1, 2, 3} is allowed ...
    assert frozenset({"nba:1", "nba:2", "nba:3"}) in sets
    # ... but a weak leg that pairs positively with no leg is never added to a bigger parlay.
    weaker = _pool_leg(6, {"B": (1.8, 0.5)})                       # value -0.10: 1.1 x 0.90 < 1
    sets = {frozenset(x["event_id"] for x in c["legs"]) for c in pe.search([a, b, weaker])}
    assert sets == {frozenset({"nba:1", "nba:2"})}
    even = _pool_leg(4, {"B": (2.0, 0.5)})                         # value exactly 0: does not lower it
    sets = {frozenset(x["event_id"] for x in c["legs"]) for c in pe.search([a, b, even])}
    assert frozenset({"nba:1", "nba:2", "nba:4"}) in sets
    for c in pe.search([a, b, weak, even, _pool_leg(5, {"B": (2.1, 0.5)})]):
        assert c["estimated_ev"] > 0 and sum(x["books"]["B"]["value"] < 0 for x in c["legs"]) <= 1


def test_loosened_rules_allow_longer_parlays_from_more_legs():
    pool = [_pool_leg(i, {"B": (2.05, 0.5)}) for i in range(6)] + [_pool_leg(9, {"B": (1.98, 0.5)})]
    cands = pe.search(pool)
    six = [c for c in cands if c["n_legs"] == 6]
    assert six and all(c["estimated_ev"] > 0 for c in cands)
    assert any("nba:9" in {x["event_id"] for x in c["legs"]} for c in six)   # the below-probability leg, last


def test_fewer_cards_when_fewer_qualify_and_none_is_normal():
    assert pe.select(pe.search([_pool_leg(1, {"B": (2.1, 0.5)})])) == []
    # #54: four games make one 4-leg card (bigger sizes pick first); the rest are not padded.
    chosen = pe.select(pe.search([_pool_leg(i, {"B": (2.1, 0.5)}) for i in range(4)]))
    assert [c["n_legs"] for c in chosen] == [4]


def test_verified_games_are_skipped():
    pool = [_pool_leg(i, {"B": (1.9, 0.56)}) for i in range(4)]
    chosen = pe.select(pe.search(pool), blocked_events={"nba:0", "nba:1"})
    assert chosen and all({x["event_id"] for x in c["legs"]}.isdisjoint({"nba:0", "nba:1"}) for c in chosen)


# ---------- card contract ----------
def ecard(pid="pe-1", n_legs=2, prices=None, price_age_min=30, **over):
    prices = prices or [1.9, 2.1, 1.8, 1.7, 2.0, 1.6, 1.5][:n_legs]
    legs = [{"event_id": f"ev-{pid}-{i}", "sport": "nba", "league": "NBA", "title": f"Home {i} v Away {i}",
             "market": "ML", "selection": "home", "selection_text": f"Home {i} to win",
             "start_utc": _iso(NOW + timedelta(hours=3, minutes=i)), "status": "active", "price": p,
             "prob": round(1 / p + 0.01, 4),
             "prob_source": "model", "price_at": _iso(NOW - timedelta(minutes=price_age_min))} for i, p in enumerate(prices)]
    r = {"parlay_id": pid, "date": DAY, "status": "active", "kind": pe.ESTIMATE_KIND, "badge": "Estimate",
         "bookmaker": "BookA", "n_legs": len(legs), "estimated_odds": round(prod(prices), 4),
         "stake": 10, "est_hit_chance": round(0.55 ** len(legs), 4), "legs": legs}
    r.update(over)
    return r


def eblock(recs, **over):
    b = {"status": "estimated", "kind": pe.ESTIMATE_KIND, "date": DAY, "recommendations": recs,
         "record": {"rows": 3, "won": 1, "lost": 2, "void": 0, "open": 0, "paper_pl": "-2.10", "staked": "30.00"}}
    b.update(over)
    return b


def _leg_set(i, k, v):
    return lambda r: r["legs"][i].__setitem__(k, v)


ECASES = [
    ("valid", lambda r: None, None),
    ("six legs", lambda r: r.update(**ecard(n_legs=6)), None),
    ("one leg", lambda r: r.update(**ecard(n_legs=1)), "needs 2-6 legs"),
    ("seven legs", lambda r: r.update(**ecard(n_legs=7)), "needs 2-6 legs"),
    ("leg started", _leg_set(0, "start_utc", _iso(NOW - timedelta(minutes=1))), "leg has started"),
    ("leg tomorrow", _leg_set(1, "start_utc", _iso(NOW + timedelta(hours=20))), "leg is not on today's date"),
    # #51: any price read earlier today (New York) counts; yesterday's price does not.
    ("price from yesterday", _leg_set(1, "price_at", _iso(NOW - timedelta(hours=10, minutes=1))), "leg price is stale"),
    ("price read just after midnight", _leg_set(1, "price_at", _iso(NOW - timedelta(hours=9, minutes=59))), None),
    ("price 151 min old", _leg_set(1, "price_at", _iso(NOW - timedelta(minutes=151))), None),
    ("future price time", _leg_set(0, "price_at", _iso(NOW + timedelta(minutes=1))), "leg price has no valid time"),
    ("no price time", _leg_set(0, "price_at", None), "leg price has no valid time"),
    ("same game twice", lambda r: r["legs"].__setitem__(1, dict(r["legs"][0])), "two legs on the same event"),
    ("unsupported sport", _leg_set(0, "sport", "hockey"), "unsupported sport"),
    ("leg withdrawn", _leg_set(0, "status", "withdrawn"), "leg is not active"),
    ("odds not the product", lambda r: r.update(estimated_odds=r["estimated_odds"] * 1.2),
     "estimated odds are not the product of the leg prices"),
    ("leg price missing", _leg_set(0, "price", None), "leg has no valid price"),
    ("labelled as a bookmaker quote", lambda r: r.update(kind="bookmaker_combined"), "not an estimate"),
    ("yesterday", lambda r: r.update(date="2026-11-12"), "not today's parlay"),
    ("no bookmaker", lambda r: r.update(bookmaker=""), "missing bookmaker"),
    ("mock flag", lambda r: r.update(mock=True), "mock or test data"),
    # #54: at most one leg below its own probability bar (probability x price < 1).
    ("one weak leg", _leg_set(0, "prob", 0.5), None),
    ("two weak legs", lambda r: [r["legs"][i].__setitem__("prob", 0.4) for i in (0, 1)],
     "more than one leg below its probability"),
]


@pytest.mark.parametrize("name,mutate,want", ECASES, ids=[c[0] for c in ECASES])
def test_estimated_card_contract(name, mutate, want):
    r = ecard()
    mutate(r)
    assert pe.card_problem(r, NOW) == want


def test_shown_caps_at_five_and_skips_verified_games():
    recs = [ecard(f"p{i}") for i in range(7)]
    assert len(pe.shown(eblock(recs), NOW)) == 5
    assert [r["parlay_id"] for r in pe.shown(eblock(recs), NOW, blocked_events={"ev-p0-1"})][0] == "p1"
    assert pe.shown(eblock(recs, date="2026-11-12"), NOW) == [] and pe.shown(eblock(recs, status="x"), NOW) == []


@pytest.mark.parametrize("prices,payout", [([1.9, 2.1], "39.90"), ([1.333, 1.5], "20.00"), ([2.05, 1.87, 1.62], "62.10")])
def test_card_payout_to_the_cent_and_labels(prices, payout):
    legs = [_pool_leg(i, {"BookA": (p, 0.8)}) for i, p in enumerate(prices)]
    c = pe.card(pe.combo(legs, "BookA"), DAY)
    assert c["gross_payout"] == payout and c["stake"] == 10
    assert Decimal(c["gross_payout"]) == parlays.gross_payout(10, c["estimated_odds"])
    assert c["kind"] == "estimated_product" != parlays.QUOTE_KIND and c["badge"] == "Estimate"
    assert c["price_label"] == ("Estimated price: product of BookA's single-game odds, not a bet-slip quote. "
                                "Your slip may pay less.")
    assert c["est_hit_chance_label"] == "Model estimate, unvalidated"
    assert pe.card_problem(c, NOW) is None


# ---------- database: freshness, time window, end to end ----------
@pytest.fixture
def con(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(config, "SITE_DIR", tmp_path / "site")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    return db.connect(tmp_path / "t.sqlite")


def _store(con, eid, sport, league, ko, home, away, books, retrieved, status="scheduled"):
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""", (eid, sport, league, ko.isoformat(), home, away, status, "test", db.utcnow()))
    for (market, line), bks in books.items():
        for bk, q in bks.items():
            for sel, price in q.items():
                con.execute("""INSERT INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,retrieved_at)
                               VALUES (?,?,?,?,?,?,?,?,?)""", (eid, bk, market, sel, line, price, "pre",
                                                               "https://api.the-odds-api.com/v4/x", retrieved.isoformat()))


def test_fresh_books_keep_todays_latest_price_before_the_start(con):
    ko = NOW + timedelta(hours=5)
    _store(con, "nba:1", "nba", "NBA", ko, "H1", "A1", _two_way(), NOW - timedelta(hours=9, minutes=50))   # 00:10 NY
    _store(con, "nba:2", "nba", "NBA", ko, "H2", "A2", _two_way(), NOW - timedelta(hours=10, minutes=10))  # yesterday
    _store(con, "nba:3", "nba", "NBA", ko, "H3", "A3", _two_way(), NOW + timedelta(minutes=5))             # future
    assert pe.fresh_books(con, "nba:1", NOW, ko) and pe.fresh_books(con, "nba:2", NOW, ko) == {}
    assert pe.fresh_books(con, "nba:3", NOW, ko) == {}
    # The LATEST price is used: a newer read replaces an older one, even if older reads were today.
    con.execute("""INSERT INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,retrieved_at)
                   VALUES ('nba:1','Bet365','ML','home',NULL,2.30,'pre','x',?)""", ((NOW - timedelta(minutes=5)).isoformat(),))
    assert pe.fresh_books(con, "nba:1", NOW, ko)[("ML", None)]["Bet365"]["home"] == 2.30
    # A price read after the game started is never used.
    assert pe.fresh_books(con, "nba:1", NOW, NOW - timedelta(minutes=10))[("ML", None)]["Bet365"]["home"] == 2.10


def test_build_end_to_end_no_started_yesterday_or_tomorrow_legs(con):
    fresh, morning, yesterday = NOW - timedelta(minutes=40), NOW - timedelta(hours=6), NOW - timedelta(hours=14)
    _store(con, "nba:1", "nba", "NBA", NOW + timedelta(hours=8), "H1", "A1", _two_way(), fresh)
    _store(con, "nba:2", "nba", "NBA", NOW + timedelta(hours=9), "H2", "A2", _two_way(), morning)  # #51: still today
    _store(con, "tennis:3", "tennis", "TENNIS:ATP", NOW + timedelta(hours=6), "P1", "P2", _two_way(), yesterday)
    _store(con, "nba:4", "nba", "NBA", NOW - timedelta(minutes=5), "H4", "A4", _two_way(), fresh)    # started
    _store(con, "nfl:5", "nfl", "NFL", NOW + timedelta(hours=30), "H5", "A5", _two_way(), fresh)     # tomorrow
    con.commit()
    b = pe.build(con, NOW)
    assert b["status"] == "estimated" and b["kind"] == "estimated_product" and b["date"] == DAY
    assert b["method"] == "parlay-estimated-v2" and "same New York day" in b["price_rule"]
    cov = b["coverage"]
    assert cov["events_today"] == 3 and cov["events_with_fresh_prices"] == 2
    assert cov["excluded"] == {"no fresh result-market prices": 1} and cov["legs"] == 2
    [r] = b["recommendations"]
    assert {x["event_id"] for x in r["legs"]} == {"nba:1", "nba:2"} and r["bookmaker"] == "Bet365"
    assert r["estimated_odds"] == pytest.approx(2.10 * 2.10) and r["gross_payout"] == "44.10"
    assert {x["price_at"] for x in r["legs"]} == {fresh.isoformat(), morning.isoformat()}
    assert r["prices_at"] == morning.isoformat()
    # Strict mode wins: a verified card on one of those games removes the estimate.
    assert pe.build(con, NOW, verified_cards=[{"legs": [{"event_id": "nba:1"}]}])["recommendations"] == []
    # A leg drops out as soon as its game starts.
    assert pe.build(con, NOW + timedelta(hours=8, minutes=1))["recommendations"] == []


def test_build_keeps_a_leg_with_an_open_injury_note_and_shows_it(con):
    """Issue #68: before, nba:1 was excluded ("open injury/lineup research note") and no card was
    possible; now it appears with the note line, and coverage no longer counts that exclusion."""
    fresh = NOW - timedelta(minutes=40)
    _store(con, "nba:1", "nba", "NBA", NOW + timedelta(hours=8), "H1", "A1", _two_way(), fresh)
    _store(con, "nba:2", "nba", "NBA", NOW + timedelta(hours=9), "H2", "A2", _two_way(), fresh)
    con.execute("""INSERT INTO research_notes(event_id,category,claim,evidence_type,created_at)
                   VALUES ('nba:1','injury','H1 starting centre listed out','verified_fact',?)""", (fresh.isoformat(),))
    con.commit()
    b = pe.build(con, NOW)
    assert "open injury/lineup research note" not in b["coverage"]["excluded"] and b["coverage"]["legs"] == 2
    [r] = b["recommendations"]
    notes = {x["event_id"]: x["risk_note"] for x in r["legs"]}
    assert notes == {"nba:1": "Injury/lineup note open: H1 starting centre listed out", "nba:2": None}
    # Previews follow the same rule (the note is shown, not used to filter).
    _store(con, "nba:3", "nba", "NBA", NOW + timedelta(days=1, hours=8), "H3", "A3", _two_way(), fresh)
    _store(con, "nba:4", "nba", "NBA", NOW + timedelta(days=1, hours=9), "H4", "A4", _two_way(), fresh)
    con.execute("""INSERT INTO research_notes(event_id,category,claim,evidence_type,created_at)
                   VALUES ('nba:3','lineup','H3 lineup unconfirmed','interpretation',?)""", (fresh.isoformat(),))
    con.commit()
    p = pe.build_preview(con, NOW, "2026-11-14")
    [r] = p["recommendations"]
    assert {x["event_id"]: x["risk_note"] for x in r["legs"]}["nba:3"] == "Injury/lineup note open: H3 lineup unconfirmed"


def test_build_with_nothing_today_is_an_honest_empty_block(con):
    b = pe.build(con, NOW)
    assert b["recommendations"] == [] and b["empty_text"] == pe.EMPTY_TEXT


# ---------- ledger: append-only, settled read-only ----------
def _settle_event(con, eid, home, away, status="finished"):
    con.execute("UPDATE events SET status=?, home_score=?, away_score=? WHERE event_id=?", (status, home, away, eid))


def test_ledger_is_append_only_and_settles_wins_losses_voids_and_open(con, monkeypatch):
    monkeypatch.setattr(pe, "SIZE_BUCKETS", ((2, 2),))             # 2-leg cards only, to settle 4 rows
    monkeypatch.setattr(pe, "PER_SIZE", 5)
    for i in range(1, 9):
        _store(con, f"nba:{i}", "nba", "NBA", NOW + timedelta(hours=2 + i * 0.1), f"H{i}", f"A{i}", _two_way(),
               NOW - timedelta(minutes=10))
    con.commit()
    b = pe.build(con, NOW)
    assert len(b["recommendations"]) == 4                          # 8 games, each used once, 2-leg cards
    assert pe.record(b, NOW) == 4 and pe.record(b, NOW + timedelta(minutes=5)) == 0
    with pe.ledger_path().open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 4 and {r["kind"] for r in rows} == {"estimated_product"}
    before = pe.ledger_path().read_text()
    cards = {frozenset(x["event_id"] for x in r["legs"]): r for r in b["recommendations"]}
    games = [sorted(k) for k in cards]
    w, l, v, o = games
    for e in w:
        _settle_event(con, e, 110, 100)                            # home wins: both legs won
    _settle_event(con, l[0], 110, 100)
    _settle_event(con, l[1], 90, 100)                              # one leg lost
    _settle_event(con, v[0], 110, 100)
    _settle_event(con, v[1], None, None, status="postponed")       # void leg voids the row here
    _settle_event(con, o[0], 110, 100)                             # other leg still open
    s = pe.settle(con)
    assert (s["rows"], s["won"], s["lost"], s["void"], s["open"]) == (4, 1, 1, 1, 1)
    assert s["paper_pl"] == "24.10" and s["staked"] == "20.00"     # +10 x (4.41 - 1) - 10
    assert pe.record_line(s) == "Estimated parlays record: 1–1, paper P/L +$24.10"
    assert list(s["by_legs"]) == ["2"] and s["by_legs"]["2"]["won"] == 1 and s["by_legs"]["2"]["paper_pl"] == "24.10"
    assert pe.ledger_path().read_text() == before                  # settlement never edits the ledger
    assert pe.record_line({"won": 0, "lost": 2, "paper_pl": "-20.00"}) == "Estimated parlays record: 0–2, paper P/L −$20.00"


def test_ledger_rows_record_leg_count_and_results_group_by_it(con):
    # Old rows stay byte-for-byte; new rows of each size are appended with n_legs.
    for i in range(1, 10):
        _store(con, f"nba:{i}", "nba", "NBA", NOW + timedelta(hours=2 + i * 0.1), f"H{i}", f"A{i}",
               _two_way(soft_home=2.3), NOW - timedelta(minutes=10))
    con.commit()
    path = pe.ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    old = ",".join(pe.LEDGER_FIELDS) + "\r\n" + ('2026-11-12T12:00:00+00:00,2026-11-12,pe-old,BookZ,2,'
           '"[{""event_id"": ""nba:old"", ""market"": ""ML"", ""selection"": ""home"", ""price"": 2.0, '
           '""prob"": 0.6, ""title"": ""Old v Game"", ""start_utc"": ""2026-11-12T23:00:00+00:00""}]",'
           'estimated_product,4.0,0.36,0.44,10\r\n')
    path.write_bytes(old.encode())
    b = pe.build(con, NOW)
    assert sorted(pe.size_bucket(r["n_legs"]) for r in b["recommendations"]) == ["2", "3", "4-5"]
    assert pe.record(b, NOW) == 3
    text = path.read_bytes()
    assert text.startswith(old.encode())
    with path.open() as f:
        rows = list(csv.DictReader(f))
    assert sorted(int(r["n_legs"]) for r in rows[1:]) == sorted(r["n_legs"] for r in b["recommendations"])
    assert all(int(r["n_legs"]) == len(json.loads(r["legs"])) for r in rows[1:])
    s = pe.settle(con)
    assert s["rows"] == 4 and sum(g["rows"] for g in s["by_legs"].values()) == 4
    assert list(s["by_legs"]) == sorted(s["by_legs"], key=int) and "2" in s["by_legs"] and "3" in s["by_legs"]
    assert path.read_bytes() == text


def test_site_build_exports_the_block_and_records_only_on_the_scheduled_run(con):
    for i in (1, 2):
        _store(con, f"nba:{i}", "nba", "NBA", NOW + timedelta(hours=3 + i), f"H{i}", f"A{i}", _two_way(),
               NOW - timedelta(minutes=10))
    con.commit()
    d = json.loads(site.build(con, NOW).read_text())
    e = d["estimated_parlays"]
    assert len(e["recommendations"]) == 1 and e["record"]["rows"] == 0 and not pe.ledger_path().exists()
    assert d["parlays"]["status"] == "not_published"               # the strict path is unchanged
    lite = json.loads((config.ROOT / "docs" / "data" / "parlays.json").read_text())
    assert lite["estimated_parlays"] == e
    d = json.loads(site.build(con, NOW, write_shadow=True).read_text())
    assert d["estimated_parlays"]["ledger_rows_added"] == 1 and d["estimated_parlays"]["record"]["open"] == 1


# ---------- rendered homepage (real docs/assets/doyen.js in Node) ----------
def _run(payload):
    out = subprocess.run(["node", str(HARNESS)], input=json.dumps(payload), capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout


def _verified(pid, events):
    legs = [{"event_id": e, "sport": "nba", "title": f"V{e} v W{e}", "selection": "V to win",
             "start_utc": _iso(NOW + timedelta(hours=2)), "status": "active"} for e in events]
    return {"parlay_id": pid, "date": DAY, "status": "active", "bookmaker": "BookV", "legs": legs, "mock": True,
            "quote": {"kind": "bookmaker_combined", "bookmaker": "BookV", "decimal_odds": 3.5,
                      "quoted_at": _iso(NOW - timedelta(minutes=5)), "source": "mock-fixture"}}


def render(est, strict=None, *, allow_mock=True, **extra):
    strict = strict or {"date": DAY, "status": "not_published", "blockers": [{"key": "combined_quote", "text": "x"}],
                        "recommendations": []}
    data = {"generated": _iso(NOW), "default_timezone": "America/New_York", "parlays": strict,
            "estimated_parlays": est, "picks": [], "history": [], "events": [], "watching": [], "close_to_value": [],
            "briefing": {}, "funnel_7d": {}, "sports": {}, "record": {"won": 0, "lost": 0, "push": 0, "profit_units": 0, "open": 0}}
    return _run({"data": data, "now": _iso(NOW), "allowMock": allow_mock, **extra})


def cards(html):
    return re.findall(r'<article class="card parlay( est)?" data-parlay="([^"]+)"', html)


@needs_node
def test_home_renders_estimated_cards_with_labels_and_payout():
    html = render(eblock([ecard("pe-a", prices=[1.9, 2.1])]))
    assert cards(html) == [(" est", "pe-a")]
    card = html[html.index("<article"):html.index("</article>")]
    assert "Estimated parlays of the day" not in html and '<span class="pill estimate">Estimate</span>' in card
    assert ("Estimated price: product of BookA's single-game odds, not a bet-slip quote. Your slip may pay less."
            in card)
    assert ">Estimated combined odds<" in card and ">3.99<" in card and ">$39.90<" in card and 'value="10"' in card
    assert "bet pays" not in card and "Recorded" not in card and "data-pays10" not in card     # issue #78
    assert "Parlay 1 · 2 legs" in card
    assert "Home 0 to win" in card and card.count("<li>") == 2
    assert "Estimated hit chance 30% (model estimate, unvalidated)" in card
    assert "Combined odds" not in card and "Verified bookmaker quote" not in card
    assert re.search(r"Prices? as of [^<]+ E[SD]T — check your book\.", card) and "data-prices-read" in card
    assert "No verified parlays today" not in html and pe.EMPTY_TEXT not in html


@needs_node
def test_home_shows_the_injury_note_line_on_the_leg():
    rec = ecard("pe-n", prices=[1.9, 2.1])
    rec["legs"][0]["risk_note"] = "Injury/lineup note open: <b>X</b> out"
    card = render(eblock([rec]))
    card = card[card.index("<article"):card.index("</article>")]
    assert card.count("data-risk-note") == 1
    assert '<div class="lg-n" data-risk-note>Injury/lineup note open: &lt;b&gt;X&lt;/b&gt; out</div>' in card


@needs_node
def test_home_empty_state_is_one_truthful_line():
    html = render(eblock([]))
    assert cards(html) == [] and f"{pe.EMPTY_TEXT} <a" in html


@needs_node
def test_browser_caps_at_five_and_a_verified_quote_wins():
    est = eblock([ecard(f"p{i}") for i in range(7)])
    assert len(cards(render(est))) == 5
    strict = {"date": DAY, "status": "published", "blockers": [], "recommendations": [_verified("v1", ["ev-p0-0", "ev-p0-1"])]}
    html = render(est, strict)
    got = cards(html)
    assert got[0] == ("", "v1") and ("est", "p0") not in [(a.strip(), b) for a, b in got] and len(got) == 5
    first = html[html.index("<article"):html.index("</article>")]
    assert "Verified bookmaker quote" in first and "Estimate<" not in first


@needs_node
@pytest.mark.parametrize("name,mutate,want", ECASES, ids=[c[0] for c in ECASES])
def test_browser_and_python_agree_on_estimated_contract(name, mutate, want):
    r = ecard()
    mutate(r)
    html = render(eblock([r]), allow_mock=(name != "mock flag"))
    assert (len(cards(html)) == 1) == (pe.card_problem(r, NOW) is None), name


@needs_node
def test_typed_stake_updates_estimated_payout_to_the_cent():
    assert _run({"data": {}, "now": _iso(NOW), "stake": {"value": "25", "odds": 3.99}}) == "$99.75"


@needs_node
def test_footer_shows_the_estimated_record_line():
    out = json.loads(render(eblock([]), footer=True))
    assert out == {"estrec": "Estimated parlays record: 1–2, paper P/L −$2.10", "hidden": False}
    out = json.loads(render(None, footer=True))
    assert out["hidden"] is True and out["estrec"] == ""


@needs_node
def test_parlay_rules_page_explains_estimated_mode():
    html = render(eblock([]), hash="#/parlays")
    assert "Estimated parlays" in html and "not a bet-slip quote" in html and "unvalidated" in html
    assert "150 minutes" not in html and "positive estimated value" in html
    assert "Estimated parlays record: 1–2, paper P/L −$2.10" in html
    assert "Picked per size" in html and "At most one leg may be priced below" in html


@needs_node
def test_parlay_rules_page_groups_results_by_leg_count():
    by = {"2": {"rows": 2, "won": 1, "lost": 1, "void": 0, "open": 0, "paper_pl": "8.20"},
          "4": {"rows": 1, "won": 0, "lost": 1, "void": 0, "open": 0, "paper_pl": "-10.00"}}
    html = render(eblock([], record={"rows": 3, "won": 1, "lost": 2, "void": 0, "open": 0, "paper_pl": "-1.80",
                                     "staked": "30.00", "by_legs": by}), hash="#/parlays")
    assert "data-by-legs" in html
    assert "<td>2 legs</td><td>1–1</td><td>0</td><td>0</td><td>+$8.20</td>" in html
    assert "<td>4 legs</td><td>0–1</td><td>0</td><td>0</td><td>−$10.00</td>" in html
