"""Issue #82: more bet types in parlays, step 1 (soccer Over/Under, BTTS, Double Chance, Draw No Bet).

Every game, price, probability and bookmaker below is test data built for these tests, never a real
quote. Database tests use a temporary database; browser tests run the real docs/assets/doyen.js with node
(always run, never skipped)."""
import csv
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from sbi import config, db, markets, parlay_engine
from sbi import parlay_estimated as pe
from sbi.sources import espn_extra

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tests" / "js" / "render_home.js"
NOW = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)          # 10:00 in New York
DAY = "2026-11-13"

# A known 3x3 score matrix (home goals = row, away goals = column), sums to 1.
M = np.array([[0.10, 0.08, 0.02],
              [0.15, 0.12, 0.05],
              [0.20, 0.18, 0.10]])


# ---------- probabilities from a known score matrix ----------
def test_market_probabilities_from_a_known_score_matrix():
    p = markets.parlay_market_probs(M, ou_lines=(1.5, 2.5))
    ph = 0.15 + 0.20 + 0.18                                      # home goals > away goals
    pd = 0.10 + 0.12 + 0.10
    pa = 0.08 + 0.02 + 0.05
    assert p[("1X2", None, "H")] == pytest.approx(ph) and p[("1X2", None, "D")] == pytest.approx(pd)
    assert p[("1X2", None, "A")] == pytest.approx(pa)
    # Double Chance = sum of the covered outcomes
    assert p[("DC", None, "HD")] == pytest.approx(ph + pd)
    assert p[("DC", None, "DA")] == pytest.approx(pd + pa)
    assert p[("DC", None, "HA")] == pytest.approx(ph + pa)
    # Draw No Bet = P(win) / (1 - P(draw))
    assert p[("DNB", None, "home")] == pytest.approx(ph / (1 - pd))
    assert p[("DNB", None, "away")] == pytest.approx(pa / (1 - pd))
    # BTTS = P(home >= 1 and away >= 1)
    btts = 0.12 + 0.05 + 0.18 + 0.10
    assert p[("BTTS", None, "yes")] == pytest.approx(btts) and p[("BTTS", None, "no")] == pytest.approx(1 - btts)
    # Over/Under from the total-goals distribution
    over15 = 0.02 + 0.12 + 0.05 + 0.20 + 0.18 + 0.10          # totals 2, 3, 4
    over25 = 0.05 + 0.18 + 0.10                                # totals 3, 4
    assert p[("OU", 1.5, "over")] == pytest.approx(over15) and p[("OU", 1.5, "under")] == pytest.approx(1 - over15)
    assert p[("OU", 2.5, "over")] == pytest.approx(over25) and p[("OU", 2.5, "under")] == pytest.approx(1 - over25)
    # The DNB probability is the push-adjusted win chance of the score-matrix outcome
    assert markets.outcome(M, "DNB", "home").q == pytest.approx(ph / (1 - pd))
    assert markets.outcome(M, "DNB", "home").pp == pytest.approx(pd)


def test_dc_and_dnb_from_stored_1x2():
    d = markets.dc_dnb_from_1x2(0.5, 0.3, 0.2)
    assert d[("DC", None, "HD")] == pytest.approx(0.8) and d[("DC", None, "HA")] == pytest.approx(0.7)
    assert d[("DNB", None, "home")] == pytest.approx(0.5 / 0.7) and d[("DNB", None, "away")] == pytest.approx(0.2 / 0.7)


# ---------- settlement rules ----------
@pytest.mark.parametrize("market,sel,line,hg,ag,want", [
    ("OU", "over", 2.5, 2, 1, 1.0), ("OU", "over", 2.5, 1, 1, -1.0), ("OU", "under", 2.5, 1, 1, 1.0),
    ("OU", "under", 1.5, 1, 1, -1.0), ("BTTS", "yes", None, 1, 1, 1.0), ("BTTS", "yes", None, 2, 0, -1.0),
    ("BTTS", "no", None, 0, 0, 1.0), ("DC", "HD", None, 1, 1, 1.0), ("DC", "HD", None, 0, 1, -1.0),
    ("DC", "DA", None, 0, 2, 1.0), ("DC", "HA", None, 2, 2, -1.0), ("DC", "HA", None, 0, 1, 1.0),
    ("DNB", "home", None, 2, 1, 1.0), ("DNB", "home", None, 1, 1, 0.0), ("DNB", "away", None, 2, 1, -1.0),
    ("DNB", "away", None, 0, 0, 0.0),
])
def test_settlement_rules(market, sel, line, hg, ag, want):
    assert markets.settle_value(market, sel, line, hg, ag) == want


@pytest.fixture
def con(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(config, "SITE_DIR", tmp_path / "site")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    return db.connect(tmp_path / "t.sqlite")


def _event(con, eid, home, away, ko, status="scheduled", hg=None, ag=None):
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,home_score,away_score,source,
                   updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (eid, "football", "E0", ko.isoformat(), home, away, status, hg, ag, "test", db.utcnow()))


def _odds(con, eid, books, retrieved):
    for (market, line), bks in books.items():
        for bk, q in bks.items():
            for sel, price in q.items():
                con.execute("""INSERT INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,retrieved_at)
                               VALUES (?,?,?,?,?,?,?,?,?)""", (eid, bk, market, sel, line, price, "pre", "test",
                                                               retrieved.isoformat()))


def _predict(con, eid, probs, created):
    run = f"test:{eid}"
    con.execute("INSERT OR IGNORE INTO model_runs VALUES (?,?,?,?,?,?,?)",
                (run, "test", "E0", created.isoformat(), 100, "{}", created.isoformat()))
    for (market, line, sel), p in probs.items():
        con.execute("""INSERT INTO predictions(run_id,event_id,market,selection,line,model_prob,created_at)
                       VALUES (?,?,?,?,?,?,?)""", (run, eid, market, sel, line, p, created.isoformat()))


ONE_X_TWO = {b: {"H": 2.0, "D": 3.6, "A": 3.9} for b in ("Pinnacle", "Bet365", "DraftKings")}
# +100 over 2.5 goals at DraftKings. Issue #106: the model (0.58) is shrunk toward the de-vigged
# market (about 0.478) before value is checked, so the price must beat the SHRUNK probability.
OU25 = {"DraftKings": {"over": 2.00, "under": 1.83}, "Bet365": {"over": 2.00, "under": 1.83}}   # 2 books (#112)
MODEL = {("1X2", None, "H"): 0.47, ("1X2", None, "D"): 0.27, ("1X2", None, "A"): 0.26,
         ("OU", 2.5, "over"): 0.58, ("OU", 2.5, "under"): 0.42}


def _two_games(con, ou=True):
    fresh = NOW - timedelta(minutes=30)
    for i, (h, a) in enumerate((("Arsenal", "Chelsea"), ("Leeds", "Fulham")), 1):
        eid = f"football:E0:{i}"
        _event(con, eid, h, a, NOW + timedelta(hours=4 + i))
        books = {("1X2", None): ONE_X_TWO}
        if ou:
            books[("OU", 2.5)] = OU25
        _odds(con, eid, books, fresh)
        _predict(con, eid, MODEL, NOW - timedelta(hours=1))
    con.commit()


def test_model_probs_full_reads_lines_and_derives_dc_dnb(con):
    _two_games(con)
    p = pe.model_probs_full(con, "football:E0:1", NOW)
    assert p[("OU", 2.5, "over")] == 0.58 and p[("1X2", None, "H")] == 0.47
    assert p[("DC", None, "HD")] == pytest.approx(0.74) and p[("DNB", None, "home")] == pytest.approx(0.47 / 0.73)
    assert pe.model_probs_full(con, "football:E0:1", NOW + timedelta(hours=40)) == {}     # stale run: none


def test_two_same_day_ou_quotes_build_an_over_under_parlay(con):
    _two_games(con)
    b = pe.build(con, NOW)
    [r] = b["recommendations"]
    assert r["price_basis"] == "consensus" and r["n_legs"] == 2 and all(x["price_books"] == 2 for x in r["legs"])
    assert [x["market"] for x in r["legs"]] == ["OU", "OU"]
    assert {x["selection_text"] for x in r["legs"]} == {"Over 2.5 goals"}
    assert all(x["line"] == 2.5 and x["price"] == 2.00 and x["market_label"] == "Over/Under" for x in r["legs"])
    assert r["estimated_odds"] == pytest.approx(2.00 * 2.00, abs=1e-4)
    assert pe.card_problem(r, NOW) is None
    # The pool offers several legs per game (match result and O/U), yet no parlay holds two of one game.
    pool, _ = pe.build_pool(con, NOW)
    assert len({x["event_id"] for x in pool}) == 2 and len(pool) > 2
    for c in pe.search(pool):
        evs = [x["event_id"] for x in c["legs"]]
        assert len(evs) == len(set(evs))
    # Never an invented price: DC, DNB and BTTS have model probabilities here but no stored quote, so no leg.
    assert {x["market"] for x in pool} <= {"1X2", "OU"}


def test_no_stored_price_no_leg_for_extra_markets(con):
    _two_games(con, ou=False)
    pool, _ = pe.build_pool(con, NOW)
    assert {x["market"] for x in pool} <= {"1X2"}


def test_extra_market_leg_needs_a_model_probability_and_a_half_line():
    ev = {"event_id": "football:E0:9", "site_sport": "soccer", "league": "E0", "competition": None,
          "home": "Arsenal", "away": "Chelsea", "kickoff_utc": (NOW + timedelta(hours=3)).isoformat()}
    books = {("1X2", None): ONE_X_TWO, ("OU", 2.5): OU25, ("OU", 2.25): OU25,
             ("DC", None): {bk: {"HD": 1.33, "DA": 1.95, "HA": 1.30} for bk in ("Bet365", "DraftKings")},
             ("DNB", None): {bk: {"home": 1.50, "away": 2.60} for bk in ("Bet365", "DraftKings")}}
    legs, _ = pe.extra_market_legs(ev, books, {})
    assert legs == []                                                   # no model probability, no leg
    full = {(m, ln, s): v for (m, ln, s), v in MODEL.items()}
    full.update(markets.dc_dnb_from_1x2(0.47, 0.27, 0.26))
    legs, _ = pe.extra_market_legs(ev, books, full)
    got = {(x["market"], x["line"], x["selection"]) for x in legs}
    assert ("OU", 2.5, "over") in got and not any(x["line"] == 2.25 for x in legs)   # quarter lines skipped
    assert ("DC", None, "HD") in got and ("DNB", None, "home") in got
    texts = {pe.selection_text(x) for x in legs}
    assert {"Over 2.5 goals", "Arsenal or draw", "Arsenal (draw no bet)"} <= texts
    cands, why = pe.candidate_legs(ev, books, full)
    assert why is None and len({(x["market"], x.get("line")) for x in cands}) == len(cands)   # best per market/line
    # Issue #112: a leg priced by one bookmaker only gets no typical price, so no leg.
    one = {**books, ("DC", None): {"Bet365": {"HD": 1.33, "DA": 1.95, "HA": 1.30}}}
    assert not any(x["market"] == "DC" for x in pe.extra_market_legs(ev, one, full)[0])


def test_leg_texts():
    t = pe.market_selection_text
    assert t("OU", "over", 2.5, "Arsenal", "Chelsea") == "Over 2.5 goals"
    assert t("OU", "under", 1.5, "Arsenal", "Chelsea") == "Under 1.5 goals"
    assert t("BTTS", "yes", None, "Arsenal", "Chelsea") == "Both teams to score: Yes"
    assert t("BTTS", "no", None, "Arsenal", "Chelsea") == "Both teams to score: No"
    assert t("DC", "HD", None, "Arsenal", "Chelsea") == "Arsenal or draw"
    assert t("DC", "DA", None, "Arsenal", "Chelsea") == "Chelsea or draw"
    assert t("DC", "HA", None, "Arsenal", "Chelsea") == "Arsenal or Chelsea"
    assert t("DNB", "home", None, "Arsenal", "Chelsea") == "Arsenal (draw no bet)"
    assert t("1X2", "H", None, "Arsenal", "Chelsea") == "Arsenal to win" and t("1X2", "D", None, "A", "B") == "Draw"
    assert t("ML", "away", None, "Lakers", "Celtics") == "Celtics to win"


def test_parlay_id_unchanged_for_match_result_and_line_aware_for_ou():
    leg = {"event_id": "e1", "market": "1X2", "selection": "H"}
    old = pe.parlay_id({"bookmaker": "B", "legs": [leg, {"event_id": "e2", "market": "1X2", "selection": "A"}]}, DAY)
    assert old == pe.parlay_id({"bookmaker": "B", "legs": [dict(leg, line=None),
                                                           {"event_id": "e2", "market": "1X2", "selection": "A"}]}, DAY)
    a = pe.parlay_id({"bookmaker": "B", "legs": [{"event_id": "e1", "market": "OU", "selection": "over", "line": 2.5}]}, DAY)
    b = pe.parlay_id({"bookmaker": "B", "legs": [{"event_id": "e1", "market": "OU", "selection": "over", "line": 3.5}]}, DAY)
    assert a != b


# ---------- ledger, settlement with pushes, record by market ----------
def _write_ledger(rows):
    path = pe.ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=pe.LEDGER_FIELDS)
        w.writeheader()
        for pid, legs, odds in rows:
            w.writerow({"first_seen": NOW.isoformat(), "date": DAY, "parlay_id": pid, "bookmaker": "BookA",
                        "n_legs": len(legs), "legs": json.dumps(legs), "kind": pe.ESTIMATE_KIND,
                        "estimated_odds": odds, "est_hit_chance": 0.3, "estimated_ev": 0.1, "stake": "10.00"})


def _leg(eid, market, sel, price, line=None, title="Arsenal v Chelsea"):
    x = {"event_id": eid, "market": market, "selection": sel, "price": price, "prob": 0.6, "title": title,
         "start_utc": (NOW + timedelta(hours=2)).isoformat()}
    if line is not None:
        x["line"] = line
    return x


def test_dnb_push_counts_at_odds_one_and_the_rest_stands(con):
    _event(con, "g1", "Arsenal", "Chelsea", NOW - timedelta(hours=3), "finished", 1, 1)     # draw: DNB push
    _event(con, "g2", "Leeds", "Fulham", NOW - timedelta(hours=3), "finished", 2, 1)        # 3 goals: over 2.5
    _event(con, "g3", "Spurs", "Wolves", NOW - timedelta(hours=3), "finished", 0, 0)        # draw, BTTS no
    _event(con, "g4", "Everton", "Brentford", NOW - timedelta(hours=3), "postponed")
    con.commit()
    _write_ledger([
        ("pe-push", [_leg("g1", "DNB", "home", 1.5), _leg("g2", "OU", "over", 1.8, 2.5, "Leeds v Fulham")], 2.7),
        ("pe-allpush", [_leg("g1", "DNB", "home", 1.5), _leg("g3", "DNB", "away", 2.2, title="Spurs v Wolves")], 3.3),
        ("pe-lost", [_leg("g2", "OU", "under", 2.0, 2.5, "Leeds v Fulham"), _leg("g3", "BTTS", "no", 1.9, title="Spurs v Wolves")], 3.8),
        ("pe-dc", [_leg("g1", "DC", "HD", 1.3), _leg("g3", "DC", "HA", 1.25, title="Spurs v Wolves")], 1.625),
        ("pe-void", [_leg("g2", "OU", "over", 1.8, 2.5, "Leeds v Fulham"), _leg("g4", "DNB", "home", 1.6, title="Everton v Brentford")], 2.88),
    ])
    rows = {r["parlay_id"]: r for r in pe.ledger_rows(con)}
    assert rows["pe-push"]["result"] == "won" and rows["pe-push"]["settled_odds"] == pytest.approx(1.8)
    assert [x["result"] for x in rows["pe-push"]["legs"]] == ["push", "won"]
    assert rows["pe-push"]["paper_pl"] == "8.00"                       # $10 x (1.80 - 1), the push at 1.00
    assert rows["pe-push"]["gross_payout"] == "18.00"
    assert rows["pe-push"]["estimated_odds"] == 2.7                    # the recorded price is never edited
    assert rows["pe-allpush"]["result"] == "void" and rows["pe-allpush"]["paper_pl"] == "0.00"
    assert rows["pe-lost"]["result"] == "lost" and [x["result"] for x in rows["pe-lost"]["legs"]] == ["lost", "won"]
    assert rows["pe-dc"]["result"] == "lost"
    assert rows["pe-void"]["result"] == "void"
    texts = [x["selection_text"] for x in rows["pe-push"]["legs"]]
    assert texts == ["Arsenal (draw no bet)", "Over 2.5 goals"]
    assert rows["pe-push"]["legs"][1]["line"] == 2.5
    s = pe.settle(con)
    assert (s["won"], s["lost"], s["void"]) == (1, 2, 2) and s["paper_pl"] == "-12.00"
    bm = s["by_market"]
    assert list(bm) == ["OU", "BTTS", "DC", "DNB"]
    assert bm["DNB"] == {"won": 0, "lost": 0, "push": 3, "void": 1, "open": 0, "label": "Draw no bet",
                         "expected_wins_settled": 0.0}                # issue #107: pushes add nothing
    assert bm["OU"]["expected_wins_settled"] == pytest.approx(1.8)     # 3 settled legs x prob 0.6
    assert bm["OU"]["won"] == 2 and bm["OU"]["lost"] == 1 and bm["BTTS"]["won"] == 1
    assert bm["DC"]["won"] == 1 and bm["DC"]["lost"] == 1 and bm["DC"]["label"] == "Double chance"


def test_match_result_settlement_is_unchanged(con):
    _event(con, "g1", "Arsenal", "Chelsea", NOW - timedelta(hours=3), "finished", 1, 1)
    con.commit()
    leg = _leg("g1", "1X2", "D", 3.4)
    assert pe.leg_result(con, leg) == parlay_engine._leg_result(con, leg) == "won"
    assert pe.leg_result(con, _leg("g1", "1X2", "H", 2.0)) == "lost"


def test_recorded_ledger_legs_carry_the_line(con):
    _two_games(con)
    b = pe.build(con, NOW)
    assert pe.record(b, NOW) == 1
    with pe.ledger_path().open() as f:
        [row] = list(csv.DictReader(f))
    legs = json.loads(row["legs"])
    assert all(x["market"] == "OU" and x["selection"] == "over" and x["line"] == 2.5 for x in legs)


# ---------- free ESPN Double Chance prices ----------
def test_espn_summary_double_chance_is_parsed_from_fractional_odds():
    s = {"odds": [{"provider": {"name": "Bet 365"}, "bettingOdds": {"teamOdds": {
        "preMatchDoubleChanceHomeOrDraw": {"value": "1/9"}, "preMatchDoubleChanceDrawOrAway": {"value": "7/4"},
        "preMatchDoubleChanceHomeOrAway": {"value": "EVS"}}}}]}
    [(name, market, prices)] = espn_extra.summary_quotes(s, "soccer")
    assert market == "DC" and prices == {"HD": 1.1111, "DA": 2.75, "HA": 2.0}
    assert espn_extra.fractional_to_decimal("4/1") == 5.0 and espn_extra.fractional_to_decimal("x") is None
    s["odds"][0]["bettingOdds"]["teamOdds"].pop("preMatchDoubleChanceHomeOrAway")
    assert espn_extra.summary_quotes(s, "soccer") == []                # incomplete: nothing stored


# ---------- browser ----------
def _run(payload):
    out = subprocess.run(["node", str(HARNESS)], input=json.dumps(payload), capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout


def _data(est, history=None):
    strict = {"date": DAY, "status": "not_published", "blockers": [{"key": "combined_quote", "text": "x"}],
              "recommendations": []}
    return {"generated": NOW.isoformat(), "default_timezone": "America/New_York", "parlays": strict,
            "estimated_parlays": est, "parlay_history": history or [], "picks": [], "history": [], "events": [],
            "watching": [], "close_to_value": [], "briefing": {}, "funnel_7d": {}, "sports": {},
            "record": {"won": 0, "lost": 0, "push": 0, "profit_units": 0, "open": 0}}


def test_home_card_shows_the_market_and_leg_odds(con):
    _two_games(con)
    b = pe.build(con, NOW)
    html = _run({"data": _data(b), "now": NOW.isoformat()})
    card = html[html.index("<article"):html.index("</article>")]
    assert card.count('<div class="lg-s">Over 2.5 goals</div>') == 2
    assert card.count('data-leg-price="2">+100 (2.00)<') == 2


def test_history_shows_record_by_market_type():
    rec = {"rows": 2, "won": 1, "lost": 1, "void": 0, "open": 0, "paper_pl": "-2.00", "staked": "20.00",
           "by_legs": {"2": {"rows": 2, "won": 1, "lost": 1, "void": 0, "open": 0, "paper_pl": "-2.00"}},
           "by_market": {"1X2": {"won": 1, "lost": 1, "push": 0, "void": 0, "open": 0, "label": "Match result"},
                         "OU": {"won": 1, "lost": 0, "push": 0, "void": 0, "open": 0, "label": "Over/Under"},
                         "DNB": {"won": 0, "lost": 0, "push": 1, "void": 0, "open": 0, "label": "Draw no bet"}}}
    est = {"status": "estimated", "kind": pe.ESTIMATE_KIND, "date": DAY, "recommendations": [], "record": rec}
    hist = [{"parlay_id": "pe-h", "date": DAY, "first_seen": NOW.isoformat(), "kind": pe.ESTIMATE_KIND,
             "bookmaker": "BookA", "n_legs": 2, "estimated_odds": 2.7, "settled_odds": 1.8, "stake": "10.00",
             "gross_payout": "18.00", "est_hit_chance": 0.3, "result": "won", "paper_pl": "8.00",
             "legs": [{"event_id": "g1", "title": "Arsenal v Chelsea", "market": "DNB", "selection": "home",
                       "selection_text": "Arsenal (draw no bet)", "price": 1.5, "start_utc": NOW.isoformat(), "result": "push"},
                      {"event_id": "g2", "title": "Leeds v Fulham", "market": "OU", "line": 2.5, "selection": "over",
                       "selection_text": "Over 2.5 goals", "price": 1.8, "start_utc": NOW.isoformat(), "result": "won"}]}]
    html = _run({"data": _data(est, hist), "now": NOW.isoformat(), "hash": "#/history"})
    assert "data-ph-by-market" not in html          # owner removed the by-market table (2026-11-18)
    assert "Arsenal (draw no bet) (push)" in html and "Over 2.5 goals ✓" in html
    assert "(settled at 1.80 after a push)" in html


def test_home_card_shows_the_why_line(con):  # owner request 2026-11-26
    _two_games(con)
    b = pe.build(con, NOW)
    assert all(isinstance(leg.get("why"), list) for r in b["recommendations"] for leg in r["legs"])
    b["recommendations"][0]["legs"][0]["why"] = ["18 sportsbooks: 70% likely", "Last 5: A W W L · B L L D"]
    html = _run({"data": _data(b), "now": NOW.isoformat()})
    card = html[html.index("<article"):html.index("</article>")]
    assert "Why: 18 sportsbooks: 70% likely · Last 5: A W W L · B L L D" in card
