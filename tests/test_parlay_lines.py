"""Issue #83: NBA and NFL point spreads and game totals as estimated-parlay legs.

Every price, game and team below is test data built for these tests, never a real quote. The
database tests use a temporary database; the browser tests run the real docs/assets/doyen.js."""
import csv
import json
from datetime import timedelta

import pytest
from scipy.stats import norm

from sbi import db, parlay_engine, parlay_lines as pl
from sbi import parlay_estimated as pe
from tests.test_parlay_estimated import DAY, NOW, _event, _store, con, eblock, needs_node, render  # noqa: F401
from tests import test_parlay_history as ph


# ---------- Normal model ----------
def test_cover_probability_half_point_line_matches_the_normal_cdf():
    # Home -4.5 with an expected margin of +7 and sd 12: P(margin > 4.5) = 1 - Phi((4.5 - 7) / 12).
    w, p, l = pl.cover_probs(7.0, 12.0, -4.5, "home")
    assert p == 0.0 and w == pytest.approx(1 - norm.cdf((4.5 - 7) / 12)) and w + l == pytest.approx(1)
    # The away side at the same row (away +4.5) is the complement.
    assert pl.cover_probs(7.0, 12.0, -4.5, "away")[0] == pytest.approx(l)
    # Expected margin equal to the line: a coin flip.
    assert pl.cover_probs(4.5, 13.5, -4.5, "home")[0] == pytest.approx(0.5)


def test_whole_number_line_has_a_push_and_the_leg_probability_excludes_it():
    w, p, l = pl.cover_probs(3.0, 13.5, -3.0, "home")          # home -3, expected margin exactly 3
    assert p == pytest.approx(norm.cdf(0.5 / 13.5) - norm.cdf(-0.5 / 13.5)) and w == pytest.approx(l)
    assert w + p + l == pytest.approx(1)
    assert pl.no_push((w, p, l)) == pytest.approx(0.5)
    assert pl.leg_prob("SPREAD", "home", -3.0, 3.0, 13.5) == pytest.approx(0.5)


def test_total_probability_over_and_under():
    w, p, l = pl.total_probs(230.0, 18.0, 228.5, "over")
    assert p == 0.0 and w == pytest.approx(1 - norm.cdf((228.5 - 230) / 18))
    assert pl.total_probs(230.0, 18.0, 228.5, "under")[0] == pytest.approx(l)
    w, p, l = pl.total_probs(44.0, 13.5, 44.0, "under")          # whole line: push possible
    assert p > 0 and w == pytest.approx(l)
    with pytest.raises(ValueError):
        pl.total_probs(44.0, 0.0, 44.0, "over")


def test_moneyline_implied_margin_round_trips():
    mu = pl.ml_implied_margin(0.70, 12.0)
    assert mu > 0 and 1 - norm.cdf(-mu / 12.0) == pytest.approx(0.70)
    assert pl.ml_implied_margin(0.5, 13.5) == pytest.approx(0.0)


def test_selection_text():
    assert pl.selection_text("SPREAD", "home", -4.5, "Lakers", "Celtics") == "Lakers −4.5"
    assert pl.selection_text("SPREAD", "away", -4.5, "Lakers", "Celtics") == "Celtics +4.5"
    assert pl.selection_text("SPREAD", "home", 3.0, "Jets", "Bills") == "Jets +3"
    assert pl.selection_text("SPREAD", "home", 0.0, "Jets", "Bills") == "Jets PK"
    assert pl.selection_text("TOTAL", "over", 228.5, "Lakers", "Celtics") == "Over 228.5 points"
    assert pl.selection_text("TOTAL", "under", 44.0, "Jets", "Bills") == "Under 44 points"
    assert pl.selection_text("TOTAL", "over", None, "Jets", "Bills") is None


def test_use_model_only_when_the_backtest_says_so(tmp_path):
    win = {"decision": {"nba": {"SPREAD": {"use_model": True}}, "nfl": {"SPREAD": {"use_model": False}}}}
    assert pl.use_model("nba", "SPREAD", win) and not pl.use_model("nfl", "SPREAD", win)
    assert not pl.use_model("nba", "TOTAL", win) and not pl.use_model("nba", "TOTAL", {})


def test_decision_needs_a_confident_improvement():
    lose = {"n": 900, "m": {"log_loss": 0.70, "ci95": [-0.001, 0.01]}}
    assert pl._decide(lose, ["m"])["use_model"] is False
    win = {"n": 900, "m": {"log_loss": 0.68, "ci95": [-0.02, -0.004]}}
    assert pl._decide(win, ["m"]) == {"use_model": True, "model": "m", "reason": "m beats the de-vigged market out of sample"}
    assert pl._decide({**win, "n": 40}, ["m"])["use_model"] is False      # too few games


# ---------- settlement ----------
def _game(con, eid, hs, as_, status="finished"):
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,home_score,away_score,source,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (eid, "nba", "NBA", NOW.isoformat(), "H", "A", status, hs, as_, "t", db.utcnow()))


@pytest.mark.parametrize("market,sel,line,hs,as_,want", [
    ("SPREAD", "home", -4.5, 110, 100, "won"),
    ("SPREAD", "home", -10.5, 110, 100, "lost"),
    ("SPREAD", "away", -10.5, 110, 100, "won"),        # away +10.5, lost by 10
    ("SPREAD", "home", -10.0, 110, 100, "void"),       # push on a whole-number line
    ("SPREAD", "away", -10.0, 110, 100, "void"),
    ("TOTAL", "over", 209.5, 110, 100, "won"),
    ("TOTAL", "under", 209.5, 110, 100, "lost"),
    ("TOTAL", "over", 210.0, 110, 100, "void"),        # push
    ("TOTAL", "under", 210.0, 110, 100, "void"),
    ("SPREAD", "home", None, 110, 100, "open"),        # unknown line: never guessed
])
def test_leg_settlement_from_final_scores(con, market, sel, line, hs, as_, want):  # noqa: F811
    _game(con, "g1", hs, as_)
    leg = {"event_id": "g1", "market": market, "selection": sel}
    if line is not None:
        leg["line"] = line
    assert parlay_engine._leg_result(con, leg) == want


def test_unfinished_game_stays_open(con):  # noqa: F811
    _game(con, "g2", None, None, status="scheduled")
    assert parlay_engine._leg_result(con, {"event_id": "g2", "market": "TOTAL", "selection": "over", "line": 200.5}) == "open"


# ---------- fixture day: a parlay with spread and total legs ----------
SHARP = ("Pinnacle", "DraftKings", "Unibet")


def _line_books(line, soft_home, soft_away, market="SPREAD", sels=("home", "away"), sharp=(1.91, 1.91)):
    b = {bk: {sels[0]: sharp[0], sels[1]: sharp[1]} for bk in SHARP}
    b["Bet365"] = {sels[0]: soft_home, sels[1]: soft_away}
    return {(market, line): b}


def _flat_ml():
    return {("ML", None): {bk: {"home": 1.91, "away": 1.91} for bk in SHARP + ("Bet365",)}}


def _seed_day(con):
    t = NOW - timedelta(minutes=40)
    _store(con, "nba:1", "nba", "NBA", NOW + timedelta(hours=8), "Lakers", "Celtics",
           {**_flat_ml(), **_line_books(-4.5, 1.85, 1.95, sharp=(1.80, 2.02))}, t)
    _store(con, "nba:2", "nba", "NBA", NOW + timedelta(hours=9), "Knicks", "Heat",
           {**_flat_ml(), **_line_books(228.5, 1.84, 1.96, "TOTAL", ("over", "under"), sharp=(1.80, 2.02))}, t)
    con.commit()


def test_fixture_day_builds_a_parlay_with_spread_and_total_legs(con):  # noqa: F811
    _seed_day(con)
    b = pe.build(con, NOW)
    assert b["coverage"]["legs"] >= 2
    [r] = b["recommendations"]
    assert r["price_basis"] == "consensus" and "bookmaker" not in r and r["n_legs"] == 2
    legs = {x["event_id"]: x for x in r["legs"]}
    s, t = legs["nba:1"], legs["nba:2"]
    assert (s["market"], s["selection"], s["line"], s["selection_text"]) == ("SPREAD", "home", -4.5, "Lakers −4.5")
    assert (t["market"], t["selection"], t["line"], t["selection_text"]) == ("TOTAL", "over", 228.5, "Over 228.5 points")
    # Issue #112: the typical price (median of 1.80 / 1.80 / 1.80 / Bet365's 1.85 or 1.84).
    assert s["price"] == 1.80 and t["price"] == 1.80 and r["estimated_odds"] == pytest.approx(1.80 * 1.80)
    assert s["price_books"] == t["price_books"] == 4
    # Probability is the de-vigged market consensus (the more likely side beats the 50% moneyline), and the card says so.
    assert s["prob_source"] == "market_consensus" and s["prob"] == pytest.approx(0.529, abs=0.003)
    assert s["prob_note"] == t["prob_note"] == "Probability: market consensus"
    assert s["market_label"] == "Point spread" and t["market_label"] == "Game total"
    assert pe.card_problem(r, NOW) is None
    # A spread leg without its line is rejected by the card contract.
    bad = json.loads(json.dumps(r))
    del bad["legs"][0]["line"]
    assert pe.card_problem(bad, NOW) == "leg has no valid line"


def test_at_most_one_leg_per_game_even_with_several_markets(con):  # noqa: F811
    t = NOW - timedelta(minutes=40)
    for i in (1, 2, 3):   # every market at Bet365 is generous on every game
        _store(con, f"nba:{i}", "nba", "NBA", NOW + timedelta(hours=6 + i), f"H{i}", f"A{i}",
               {("ML", None): {**{bk: {"home": 1.91, "away": 1.91} for bk in SHARP}, "Bet365": {"home": 2.05, "away": 1.78}},
                **_line_books(-3.5, 2.10, 1.75), **_line_books(220.5, 2.06, 1.77, "TOTAL", ("over", "under"))}, t)
    con.commit()
    pool, _ = pe.build_pool(con, NOW)
    assert {x["market"] for x in pool} == {"ML", "SPREAD", "TOTAL"} and len(pool) == 9
    for c in pe.search(pool):
        evs = [x["event_id"] for x in c["legs"]]
        assert len(evs) == len(set(evs))
    b = pe.build(con, NOW)
    for r in b["recommendations"]:
        assert len({x["event_id"] for x in r["legs"]}) == len(r["legs"])


def test_parlay_id_is_unchanged_for_moneyline_legs_and_includes_the_line_otherwise():
    ml = {"event_id": "e1", "market": "ML", "selection": "home"}
    assert pe._leg_key(ml) == "e1|ML|home"
    assert pe._leg_key({**ml, "line": None}) == "e1|ML|home"
    assert pe._leg_key({"event_id": "e1", "market": "SPREAD", "selection": "home", "line": -4.5}) == "e1|SPREAD|home|-4.5"


def test_ledger_stores_market_selection_and_line_and_settles_by_market(con):  # noqa: F811
    _seed_day(con)
    b = pe.build(con, NOW)
    assert pe.record(b, NOW) == 1
    with pe.ledger_path().open() as f:
        [row] = list(csv.DictReader(f))
    legs = {x["event_id"]: x for x in json.loads(row["legs"])}
    assert (legs["nba:1"]["market"], legs["nba:1"]["selection"], legs["nba:1"]["line"]) == ("SPREAD", "home", -4.5)
    assert (legs["nba:2"]["market"], legs["nba:2"]["selection"], legs["nba:2"]["line"]) == ("TOTAL", "over", 228.5)
    [lr] = pe.ledger_rows(con, day=DAY)
    assert {x["selection_text"] for x in lr["legs"]} == {"Lakers −4.5", "Over 228.5 points"}
    # Lakers win by 5 (cover -4.5); the Knicks game lands exactly on... 228.5 can't push: 115-110 = 225, under.
    con.execute("UPDATE events SET status='finished', home_score=105, away_score=100 WHERE event_id='nba:1'")
    con.execute("UPDATE events SET status='finished', home_score=115, away_score=110 WHERE event_id='nba:2'")
    s = pe.settle(con)
    assert (s["won"], s["lost"]) == (0, 1)
    assert s["by_market"] == {
        "SPREAD": {"won": 1, "lost": 0, "push": 0, "void": 0, "open": 0, "label": "Point spread",
                   "expected_wins_settled": round(legs["nba:1"]["prob"], 3)},
        "TOTAL": {"won": 0, "lost": 1, "push": 0, "void": 0, "open": 0, "label": "Game total",
                  "expected_wins_settled": round(legs["nba:2"]["prob"], 3)}}


# ---------- browser ----------
@needs_node
def test_card_shows_the_line_odds_and_market_consensus_note(con):  # noqa: F811
    _seed_day(con)
    [r] = pe.build(con, NOW)["recommendations"]
    html = render(eblock([r]))
    i = html.index(f'data-parlay="{r["parlay_id"]}"')
    card = html[i:html.index("</article>", i)]
    assert "Lakers −4.5" in card and "Over 228.5 points" in card
    assert card.count('data-leg-price="1.8">-125 (1.80)<') == 2
    assert card.count("data-prob-note>Probability: market consensus<") == 2


@needs_node
def test_history_shows_no_record_by_market_table():
    # The owner removed the parlay by-market table from History (#95); by_market stays data only.
    rec = ph._data([])
    rec["estimated_parlays"]["record"]["by_market"] = {
        "ML": {"won": 2, "lost": 1, "push": 0, "void": 0, "open": 0, "label": "Moneyline"},
        "SPREAD": {"won": 1, "lost": 0, "push": 0, "void": 1, "open": 0, "label": "Point spread"}}
    html = ph._run({"data": rec, "now": ph.NOW.isoformat(), "hash": "#/history"})
    assert "data-ph-by-market" not in html and "Point spread</th>" not in html
