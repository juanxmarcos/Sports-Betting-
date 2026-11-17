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


# ---------- legs ----------
def test_one_leg_per_game_and_model_probability_preferred():
    leg, why = pe.legs_for_event(_event(1), _two_way(), None)
    assert why is None and leg["selection"] == "home" and leg["prob_source"] == "market_consensus_ex_book"
    assert set(leg["books"]) == {"Bet365"}                         # only a price above the probability is kept
    assert leg["books"]["Bet365"]["prob"] == pytest.approx(0.5, abs=0.003)
    leg, _ = pe.legs_for_event(_event(1), _two_way(), {("ML", "home"): 0.53, ("ML", "away"): 0.47})
    assert leg["prob_source"] == "model" and leg["books"]["Bet365"]["prob"] == 0.53
    assert leg["books"]["Bet365"]["value"] == pytest.approx(0.53 * 2.10 - 1)
    assert isinstance(leg, dict)                                   # one leg, never both sides of a game


def test_no_leg_when_no_bookmaker_beats_the_probability():
    flat = {("ML", None): {b: {"home": 1.9, "away": 1.9} for b in ("Pinnacle", "DraftKings", "Unibet", "Bet365")}}
    assert pe.legs_for_event(_event(1), flat, None) == (None, "no bookmaker price above Doyen's probability")
    assert pe.legs_for_event(_event(1), _two_way(), None, n_risk_notes=1)[1] == "open injury/lineup research note"


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
    pool = [_pool_leg(i, {"B": (1.9, 0.56)}, hours=1 + i * 0.5) for i in range(14)]
    chosen = pe.select(pe.search(pool))
    assert len(chosen) == 5
    evs = [x["event_id"] for c in chosen for x in c["legs"]]
    assert len(evs) == len(set(evs))
    firsts = [min(x["start_utc"] for x in c["legs"]) for c in chosen]
    assert firsts == sorted(firsts)
    assert all(c["n_legs"] == 2 for c in chosen)                   # equal legs: fewer legs ranks first


def test_fewer_cards_when_fewer_qualify_and_none_is_normal():
    assert pe.select(pe.search([_pool_leg(1, {"B": (2.1, 0.5)})])) == []
    assert len(pe.select(pe.search([_pool_leg(i, {"B": (2.1, 0.5)}) for i in range(4)]))) == 2


def test_verified_games_are_skipped():
    pool = [_pool_leg(i, {"B": (1.9, 0.56)}) for i in range(4)]
    chosen = pe.select(pe.search(pool), blocked_events={"nba:0", "nba:1"})
    assert chosen and all({x["event_id"] for x in c["legs"]}.isdisjoint({"nba:0", "nba:1"}) for c in chosen)


# ---------- card contract ----------
def ecard(pid="pe-1", n_legs=2, prices=None, price_age_min=30, **over):
    prices = prices or [1.9, 2.1, 1.8, 1.7, 2.0, 1.6, 1.5][:n_legs]
    legs = [{"event_id": f"ev-{pid}-{i}", "sport": "nba", "league": "NBA", "title": f"Home {i} v Away {i}",
             "market": "ML", "selection": "home", "selection_text": f"Home {i} to win",
             "start_utc": _iso(NOW + timedelta(hours=3, minutes=i)), "status": "active", "price": p, "prob": 0.55,
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
    ("stale leg price", _leg_set(1, "price_at", _iso(NOW - timedelta(minutes=151))), "leg price is stale"),
    ("price 150 min old", _leg_set(1, "price_at", _iso(NOW - timedelta(minutes=150))), None),
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
    legs = [_pool_leg(i, {"BookA": (p, 0.6)}) for i, p in enumerate(prices)]
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


def test_fresh_books_keep_only_prices_from_the_last_150_minutes(con):
    _store(con, "nba:1", "nba", "NBA", NOW + timedelta(hours=5), "H1", "A1", _two_way(), NOW - timedelta(minutes=149))
    _store(con, "nba:2", "nba", "NBA", NOW + timedelta(hours=5), "H2", "A2", _two_way(), NOW - timedelta(minutes=151))
    _store(con, "nba:3", "nba", "NBA", NOW + timedelta(hours=5), "H3", "A3", _two_way(), NOW + timedelta(minutes=5))
    assert pe.fresh_books(con, "nba:1", NOW) and pe.fresh_books(con, "nba:2", NOW) == {}
    assert pe.fresh_books(con, "nba:3", NOW) == {}


def test_build_end_to_end_no_started_stale_or_tomorrow_legs(con):
    fresh, stale = NOW - timedelta(minutes=40), NOW - timedelta(minutes=200)
    _store(con, "nba:1", "nba", "NBA", NOW + timedelta(hours=8), "H1", "A1", _two_way(), fresh)
    _store(con, "nba:2", "nba", "NBA", NOW + timedelta(hours=9), "H2", "A2", _two_way(), fresh)   # same competition
    _store(con, "tennis:3", "tennis", "TENNIS:ATP", NOW + timedelta(hours=6), "P1", "P2", _two_way(), stale)
    _store(con, "nba:4", "nba", "NBA", NOW - timedelta(minutes=5), "H4", "A4", _two_way(), fresh)    # started
    _store(con, "nfl:5", "nfl", "NFL", NOW + timedelta(hours=30), "H5", "A5", _two_way(), fresh)     # tomorrow
    con.commit()
    b = pe.build(con, NOW)
    assert b["status"] == "estimated" and b["kind"] == "estimated_product" and b["date"] == DAY
    assert b["coverage"]["events_today"] == 3 and b["coverage"]["excluded"] == {"no fresh result-market prices": 1}
    [r] = b["recommendations"]
    assert {x["event_id"] for x in r["legs"]} == {"nba:1", "nba:2"} and r["bookmaker"] == "Bet365"
    assert r["estimated_odds"] == pytest.approx(2.10 * 2.10) and r["gross_payout"] == "44.10"
    assert all(x["price_at"] == fresh.isoformat() for x in r["legs"])
    # Strict mode wins: a verified card on one of those games removes the estimate.
    assert pe.build(con, NOW, verified_cards=[{"legs": [{"event_id": "nba:1"}]}])["recommendations"] == []


def test_build_with_nothing_today_is_an_honest_empty_block(con):
    b = pe.build(con, NOW)
    assert b["recommendations"] == [] and b["empty_text"] == pe.EMPTY_TEXT


# ---------- ledger: append-only, settled read-only ----------
def _settle_event(con, eid, home, away, status="finished"):
    con.execute("UPDATE events SET status=?, home_score=?, away_score=? WHERE event_id=?", (status, home, away, eid))


def test_ledger_is_append_only_and_settles_wins_losses_voids_and_open(con):
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
    assert pe.ledger_path().read_text() == before                  # settlement never edits the ledger
    assert pe.record_line({"won": 0, "lost": 2, "paper_pl": "-20.00"}) == "Estimated parlays record: 0–2, paper P/L −$20.00"


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
    assert "Estimated parlays of the day" in html and '<span class="pill estimate">Estimate</span>' in card
    assert ("Estimated price: product of BookA's single-game odds, not a bet-slip quote. Your slip may pay less."
            in card)
    assert ">Estimated odds<" in card and ">3.99<" in card and ">$39.90<" in card and 'value="10"' in card
    assert "Home 0 to win" in card and card.count("<li>") == 2
    assert "Estimated hit chance 30% (model estimate, unvalidated)" in card
    assert "Combined odds" not in card and "Verified bookmaker quote" not in card
    assert "No verified parlays today" not in html and pe.EMPTY_TEXT not in html


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
    assert "Estimated parlays record: 1–2, paper P/L −$2.10" in html
