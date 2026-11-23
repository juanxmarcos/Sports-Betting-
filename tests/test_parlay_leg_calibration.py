"""Issue #106: overconfident parlay legs. Shrunk and capped leg probabilities for NEW parlays, an
append-only ledger, and the per-market `parlay-calibration` report.

Every game, price, probability and bookmaker below is test data built for these tests, never a real
quote or result. Database tests use a temporary database."""
import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sbi import config, db
from sbi import parlay_estimated as pe
from sbi import parlay_leg_calibration as plc

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "parlay_calibration" / "expected.json"
NOW = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)          # 10:00 in New York
DAY = "2026-11-13"


# ---------- the rule ----------
def test_soccer_ou_leg_at_062_against_a_050_market_uses_at_most_055():
    p = pe.used_prob("OU", 0.62, 0.50)
    assert p <= 0.55
    assert p == pytest.approx(0.25 * 0.62 + 0.75 * 0.50)          # the blend (0.53) is below the cap here


@pytest.mark.parametrize("market", ["OU", "BTTS", "DC", "DNB"])
def test_score_matrix_markets_are_shrunk_toward_the_market(market):
    assert pe.used_prob(market, 0.70, 0.60) == pytest.approx(0.625)
    assert pe.used_prob(market, 0.50, 0.60) == pytest.approx(0.575)   # shrinking works both ways


@pytest.mark.parametrize("market", ["1X2", "ML", "SPREAD", "TOTAL"])
def test_every_other_market_is_capped_at_market_plus_005(market):
    assert pe.used_prob(market, 0.62, 0.50) == pytest.approx(0.55)
    assert pe.used_prob(market, 0.52, 0.50) == pytest.approx(0.52)    # inside the cap: unchanged
    assert pe.used_prob(market, 0.40, 0.50) == pytest.approx(0.40)    # never raised


def _soccer_event(i):
    return {"event_id": f"football:E0:{i}", "site_sport": "soccer", "league": "E0", "competition": "E0",
            "home": f"H{i}", "away": f"A{i}", "kickoff_utc": (NOW + timedelta(hours=4 + i)).isoformat()}


def _ou_books(over=1.85):
    # two bookmakers at 1.95/1.95 make the de-vigged consensus exactly 0.50; Bet365 prices the leg
    return {("OU", 2.5): {"Pinnacle": {"over": 1.95, "under": 1.95}, "DraftKings": {"over": 1.95, "under": 1.95},
                          "Bet365": {"over": over, "under": 1.95}}}


def test_a_leg_cannot_qualify_on_model_optimism_alone():
    # 0.61 (not 0.62): the de-vigged 0.50 carries float noise and 0.12 is the kept disagreement screen
    model = {("OU", 2.5, "over"): 0.61, ("OU", 2.5, "under"): 0.39}
    pool = []
    for i in (1, 2):
        legs, _ = pe.extra_market_legs(_soccer_event(i), _ou_books(), model)
        [leg] = [x for x in legs if x["selection"] == "over"]
        b = leg["books"][pe.CONSENSUS]                              # issue #112: the typical price
        assert b["raw_prob"] == pytest.approx(0.61) and b["prob"] <= 0.55
        assert b["price"] == pytest.approx(1.95)                   # median of 1.95 / 1.95 / 1.85
        assert b["raw_prob"] * b["price"] > 1.0                    # the raw model would call it value ...
        assert b["value"] < 0.08                                   # ... the probability actually used is shrunk
        pool.append(leg)
    # Ranking uses the probability USED: the raw model's 0.61 never reaches a parlay's joint probability.
    cands = pe.search(pool)
    assert cands and all(c["joint_prob"] <= 0.55 ** 2 + 1e-9 for c in cands)


def test_moneyline_is_capped_too():
    ev = {"event_id": "nba:1", "site_sport": "nba", "league": "NBA", "home": "H", "away": "A",
          "kickoff_utc": (NOW + timedelta(hours=5)).isoformat()}
    books = {("ML", None): {"Pinnacle": {"home": 1.95, "away": 1.95}, "Bet365": {"home": 1.90, "away": 1.95}}}
    legs, why = pe.screen_event(ev, books, {("ML", "home"): 0.61, ("ML", "away"): 0.39})
    [home] = [x for x in legs if x["selection"] == "home"]
    assert why is None and home["books"][pe.CONSENSUS]["prob"] == pytest.approx(0.55)
    assert home["books"][pe.CONSENSUS]["raw_prob"] == pytest.approx(0.61)
    # adjust=False keeps the raw probability (no caller uses it since issue #112).
    legs, _ = pe.screen_event(ev, books, {("ML", "home"): 0.61, ("ML", "away"): 0.39}, adjust=False)
    [home] = [x for x in legs if x["selection"] == "home"]
    assert home["books"][pe.CONSENSUS]["prob"] == pytest.approx(0.61) == home["books"][pe.CONSENSUS]["raw_prob"]


# ---------- database ----------
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
    run = f"test:{eid}:{created.isoformat()}"
    con.execute("INSERT OR IGNORE INTO model_runs VALUES (?,?,?,?,?,?,?)",
                (run, "test", "E0", created.isoformat(), 100, "{}", created.isoformat()))
    for (market, line, sel), p in probs.items():
        con.execute("""INSERT INTO predictions(run_id,event_id,market,selection,line,model_prob,created_at)
                       VALUES (?,?,?,?,?,?,?)""", (run, eid, market, sel, line, p, created.isoformat()))


ONE_X_TWO = {b: {"H": 2.0, "D": 3.6, "A": 3.9} for b in ("Pinnacle", "Bet365", "DraftKings")}
OU25 = {"DraftKings": {"over": 2.00, "under": 1.83}, "Bet365": {"over": 2.00, "under": 1.83}}   # 2 books (#112)
MODEL = {("1X2", None, "H"): 0.47, ("1X2", None, "D"): 0.27, ("1X2", None, "A"): 0.26,
         ("OU", 2.5, "over"): 0.58, ("OU", 2.5, "under"): 0.42}

OLD_ROW = ('2026-11-12T15:00:00+00:00,2026-11-12,pe-old000000001,DraftKings,2,"[{""event_id"": ""football:E0:9"", '
           '""market"": ""OU"", ""selection"": ""over"", ""price"": 1.83, ""prob"": 0.61, ""title"": ""X v Y"", '
           '""start_utc"": ""2026-11-12T20:00:00+00:00"", ""line"": 2.5}]",estimated_product,3.3489,0.3721,0.2461,10')


def test_new_ledger_rows_record_used_and_raw_probability_and_old_rows_are_untouched(con):
    for i, (h, a) in enumerate((("Arsenal", "Chelsea"), ("Leeds", "Fulham")), 1):
        eid = f"football:E0:{i}"
        _event(con, eid, h, a, NOW + timedelta(hours=4 + i))
        _odds(con, eid, {("1X2", None): ONE_X_TWO, ("OU", 2.5): OU25}, NOW - timedelta(minutes=30))
        _predict(con, eid, MODEL, NOW - timedelta(hours=1))
    con.commit()
    path = pe.ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    header = ",".join(pe.LEDGER_FIELDS)
    path.write_text(header + "\n" + OLD_ROW + "\n")
    before = path.read_text()
    b = pe.build(con, NOW)
    [card] = b["recommendations"]
    assert all(x["prob"] < x["raw_prob"] == 0.58 for x in card["legs"])
    assert pe.record(b, NOW) == 1
    after = path.read_text()
    assert after.startswith(before)                                # append-only: the old row is byte-identical
    with path.open(newline="") as f:
        old, new = list(csv.DictReader(f))
    assert "raw_prob" not in old["legs"] and json.loads(old["legs"])[0]["prob"] == 0.61
    legs = json.loads(new["legs"])
    for x in legs:
        assert x["raw_prob"] == 0.58 and x["prob"] == pytest.approx(0.25 * 0.58 + 0.75 * x["market_prob"], abs=1e-4)
    # the card's hit chance is the product of the probabilities USED
    assert float(new["est_hit_chance"]) == pytest.approx(legs[0]["prob"] * legs[1]["prob"], abs=1e-3)


# ---------- calibration report ----------
def _leg(eid, market, sel, price, prob, raw=None, mkt=None, line=None):
    x = {"event_id": eid, "market": market, "selection": sel, "price": price, "prob": prob, "title": "H v A",
         "start_utc": "2026-11-12T20:00:00+00:00"}
    if line is not None:
        x["line"] = line
    if raw is not None:
        x["raw_prob"] = raw
    if mkt is not None:
        x["market_prob"] = mkt
    return x


def test_parlay_calibration_per_market_matches_the_fixture(con, tmp_path):
    ko = datetime(2026, 11, 12, 20, 0, tzinfo=timezone.utc)
    _event(con, "football:E0:1", "H1", "A1", ko, "finished", 2, 1)      # 3 goals, home win
    _event(con, "football:E0:2", "H2", "A2", ko, "finished", 0, 0)      # 0 goals, draw
    _event(con, "football:E0:3", "H3", "A3", ko, "finished", 1, 1)      # 2 goals, draw
    _event(con, "football:E0:4", "H4", "A4", ko, "scheduled")            # still open
    con.commit()
    rows = [
        # an old row: no raw_prob, no market_prob stored and no stored odds to reconstruct one
        ("2026-11-12T15:00:00+00:00", [_leg("football:E0:1", "OU", "over", 1.9, 0.61, line=2.5),
                                       _leg("football:E0:2", "OU", "over", 1.9, 0.60, line=2.5)]),
        # new rows (issue #106) with the used, raw and market probabilities
        ("2026-11-12T16:00:00+00:00", [_leg("football:E0:1", "DC", "HD", 1.4, 0.70, 0.76, 0.68),
                                       _leg("football:E0:2", "DC", "HA", 1.6, 0.62, 0.70, 0.60)]),
        ("2026-11-12T16:00:00+00:00", [_leg("football:E0:3", "DNB", "home", 1.9, 0.52, 0.56, 0.51),
                                       _leg("football:E0:2", "1X2", "D", 3.5, 0.30, 0.30, 0.28),
                                       _leg("football:E0:4", "OU", "under", 1.9, 0.50, 0.55, 0.48, line=2.5)]),
    ]
    path = tmp_path / "ledger.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=pe.LEDGER_FIELDS)
        w.writeheader()
        for i, (seen, legs) in enumerate(rows):
            w.writerow({"first_seen": seen, "date": "2026-11-12", "parlay_id": f"pe-t{i}", "bookmaker": "Bet365",
                        "n_legs": len(legs), "legs": json.dumps(legs), "kind": pe.ESTIMATE_KIND,
                        "estimated_odds": 2.0, "est_hit_chance": 0.3, "estimated_ev": 0.1, "stake": 10})
    got = plc.ledger_calibration(con, path)
    assert got == json.loads(FIXTURE.read_text())
    assert got["by_market"]["OU"]["hit_rate"] == 0.5 and got["by_market"]["DC"]["won"] == 1
    assert got["overall"]["excluded_push_void"] == 1 and got["overall"]["open"] == 1


def test_wilson_interval():
    assert plc.wilson(0, 0) is None
    lo, hi = plc.wilson(3, 25)
    assert lo < 0.12 < hi and lo == pytest.approx(0.0417, abs=1e-3) and hi == pytest.approx(0.3, abs=2e-3)


def test_weight_backtest_reads_only_runs_and_prices_before_kickoff(con):
    ko = NOW - timedelta(days=1)
    _event(con, "football:E0:1", "H1", "A1", ko, "finished", 2, 1)
    books = {("1X2", None): ONE_X_TWO, ("OU", 2.5): {"Pinnacle": {"over": 1.95, "under": 1.95}}}
    _odds(con, "football:E0:1", books, ko - timedelta(hours=2))
    _odds(con, "football:E0:1", {("OU", 2.5): {"Pinnacle": {"over": 9.0, "under": 1.05}}}, ko + timedelta(minutes=5))
    _predict(con, "football:E0:1", MODEL, ko - timedelta(hours=3))
    _predict(con, "football:E0:1", {("1X2", None, "H"): 0.9, ("1X2", None, "D"): 0.05, ("1X2", None, "A"): 0.05,
                                    ("OU", 2.5, "over"): 0.99}, ko + timedelta(minutes=1))     # after kick-off: ignored
    con.commit()
    s = plc.backtest_samples(con)
    ou = [x for x in s if x["market"] == "OU"]
    assert len(ou) == 1 and ou[0]["model"] == 0.58 and ou[0]["market_prob"] == pytest.approx(0.5) and ou[0]["y"] == 1
    assert {x["market"] for x in s} == {"OU", "DC", "DNB"} and len(s) == 5
    rep = plc.weight_backtest(con)
    assert rep["OU"]["all"]["n"] == 1 and set(rep["OU"]["all"]["at"]) >= {"0.0", "0.25", "1.0"}
