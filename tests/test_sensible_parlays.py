"""Owner decision 2026-11-26 (parlay-estimated-v5): good, sensible parlays. Strong legs only (whole
market >= 60%, Doyen's model agrees, price >= 1.15), two or three legs, up to five parlays a day,
and the homework behind each leg. Every game, price and probability here is test data."""
from datetime import timedelta

import pytest

from sbi import db
from sbi import parlay_estimated as pe
from tests.test_parlay_estimated import NOW, _pool_leg

pytestmark = pytest.mark.sensible_rules


def _leg(i, price, q, model=None, **kw):
    leg = _pool_leg(i, {"B": (price, q)}, **kw)
    leg["consensus_prob"], leg["model_prob"] = q, model
    return leg


def test_production_rules():
    assert pe.METHOD == "parlay-estimated-v5" and "parlay-estimated-v4" in pe.LEGACY_METHODS
    assert (pe.MIN_LEG_MARKET_PROB, pe.MIN_LEG_PRICE, pe.MAX_CARDS, pe.PER_SIZE) == (0.60, 1.15, 5, 3)
    assert pe.MIN_COMBINED_ODDS == {"2": 1.6, "3": 1.9} and pe.SIZE_BUCKETS == ((2, 2), (3, 3))
    assert [pe.min_odds(n) for n in (1, 2, 3, 4)] == [None, 1.6, 1.9, None]


def test_only_strong_legs_the_model_agrees_with():
    assert pe.sensible(_leg(1, 1.35, 0.70))
    assert not pe.sensible(_leg(2, 1.70, 0.55))                    # coin-flip-ish: market below 60%
    assert not pe.sensible(_leg(3, 1.10, 0.88))                    # pays almost nothing
    assert not pe.sensible(_leg(4, 1.35, 0.70, model=0.66))        # Doyen's model disagrees
    assert pe.sensible(_leg(5, 1.35, 0.70, model=0.69))            # within 2 points: agrees
    no_market = _leg(6, 1.35, 0.70)
    no_market["consensus_prob"] = None
    assert not pe.sensible(no_market)


def test_search_never_uses_a_weak_leg_and_cards_pay_something():
    strong = [_leg(i, 1.35, 0.70) for i in range(4)]
    weak = [_leg(10 + i, 2.10, 0.48) for i in range(4)]
    cands = pe.search(strong + weak)
    assert cands and all(x["event_id"] in {s["event_id"] for s in strong} for c in cands for x in c["legs"])
    assert all(c["n_legs"] in (2, 3) for c in cands)
    picked = pe.select(cands)
    assert 1 <= len(picked) <= 5 and all(pe.qualifies(c) for c in picked)
    short = pe.combo([_leg(20, 1.2, 0.8), _leg(21, 1.2, 0.8)])     # 1.44 combined: below 1.6
    assert not pe.qualifies(short)


def test_up_to_five_parlays_a_day():
    legs = [_leg(i, 1.40, 0.68) for i in range(16)]
    assert len(pe.select(pe.search(legs))) == 5


def test_why_lines_come_only_from_stored_data(tmp_path, monkeypatch):
    con = db.connect(tmp_path / "t.sqlite")
    ko = NOW + timedelta(hours=5)
    con.execute("INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,updated_at) "
                "VALUES ('e1','football','E0',?,'Arsenal','Chelsea','scheduled','t',?)", (ko.isoformat(), NOW.isoformat()))
    for k, (h, a, hs, as_) in enumerate([("Arsenal", "X", 2, 0), ("Y", "Arsenal", 1, 1), ("Arsenal", "Z", 0, 1),
                                          ("Chelsea", "X", 1, 0), ("Y", "Chelsea", 0, 3), ("Chelsea", "Z", 2, 2)]):
        t = (NOW - timedelta(days=k + 1)).isoformat()
        con.execute("INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,home_score,away_score,source,updated_at) "
                    "VALUES (?,?,?,?,?,?,'finished',?,?,'t',?)", (f"p{k}", "football", "E0", t, h, a, hs, as_, t))
    con.commit()
    leg = {"event_id": "e1", "sport": "soccer", "market_prob": 0.7, "price_books": 18, "raw_prob": 0.72, "prob_source": "model"}
    assert pe.leg_why(con, leg) == ["18 sportsbooks: 70% likely", "Doyen's model: 72%",
                                    "Last 5: Arsenal W D L · Chelsea W W D"]
    # No model, no stored results: those lines are left out, never filled in.
    bare = {"event_id": "nope", "sport": "tennis", "market_prob": 0.8, "price_books": 5, "prob_source": "market"}
    assert pe.leg_why(con, bare) == ["5 sportsbooks: 80% likely"]

