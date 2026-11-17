"""Issue #35 (PR A): the full-slate parlay candidate engine. Shadow only: it reads stored data, never
makes a network request, never labels a computed product as a bookmaker quote and never feeds the
homepage."""
import csv
import json
from datetime import datetime, timedelta, timezone

import pytest

from sbi import config, db, parlay_engine as pe, parlays

NOW = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)          # 10:00 in New York


def _event(i, sport="nba", league=None, hours=5, home=None, away=None):
    return {"event_id": f"{sport}:{i}", "sport": sport, "site_sport": pe.SPORTS.get(sport),
            "league": league or {"nba": "NBA", "nfl": "NFL", "tennis": "TENNIS:ATP", "football": "INT:uefa.nations"}.get(sport, sport),
            "kickoff_utc": (NOW + timedelta(hours=hours)).isoformat(), "home": home or f"H{i}", "away": away or f"A{i}",
            "competition": None}


def _two_way(soft_home=2.10, soft_away=1.80, soft="Bet365"):
    """Three independent bookmakers near 1.95/1.95 plus one soft book `soft` with its own prices."""
    return {("ML", None): {"Pinnacle": {"home": 1.95, "away": 1.95}, "DraftKings": {"home": 1.93, "away": 1.93},
                           "Unibet": {"home": 1.94, "away": 1.94}, soft: {"home": soft_home, "away": soft_away}}}


def _three_way(soft_h=2.6, soft="Bet365"):
    return {("1X2", None): {"Pinnacle": {"H": 2.4, "D": 3.4, "A": 3.1}, "DraftKings": {"H": 2.35, "D": 3.35, "A": 3.05},
                            "Unibet": {"H": 2.38, "D": 3.3, "A": 3.1}, soft: {"H": soft_h, "D": 3.2, "A": 2.9}}}


def _legs(event, books, **kw):
    legs, why = pe.screen_event(event, books, **kw)
    assert why is None, why
    return legs


# ---------- leg screen ----------
def test_leg_value_uses_leave_one_out_fair_probability():
    legs = _legs(_event(1), _two_way())
    home = next(x for x in legs if x["selection"] == "home")
    b = home["books"]["Bet365"]
    assert b["price"] == 2.10
    assert b["fair_prob"] == pytest.approx(0.5, abs=0.003)            # from the other three books only
    assert b["value"] == pytest.approx(b["fair_prob"] * 2.10 - 1)
    assert b["value"] > 0 and home["books"]["DraftKings"]["value"] < 0


def test_same_owner_brands_count_once_for_the_independence_gate():
    books = {("ML", None): {"Unibet": {"home": 1.95, "away": 1.95}, "LeoVegas": {"home": 1.94, "away": 1.96},
                            "William Hill": {"home": 1.93, "away": 1.97}, "888sport": {"home": 1.92, "away": 1.98}}}
    assert pe.screen_event(_event(1), books) == ([], "too few independent bookmakers")   # Kambi x2 + evoke x2 = 2


def test_unsupported_sport_and_missing_prices_and_risk_notes():
    assert pe.screen_event(_event(1, sport="hockey"), _two_way())[1] == "unsupported sport"
    assert pe.screen_event(_event(1), {})[1] == "no fresh result-market prices"
    assert pe.screen_event(_event(1), _two_way(), n_risk_notes=1)[1] == "open injury/lineup research note"


def test_probability_band_excludes_heavy_favourites_and_long_shots():
    books = {("ML", None): {b: {"home": 1.08, "away": 9.0} for b in ("Pinnacle", "DraftKings", "Unibet", "Bet365")}}
    assert pe.screen_event(_event(1), books) == ([], "probability outside research band")


def test_strong_model_market_disagreement_excludes_the_leg():
    legs, why = pe.screen_event(_event(1), _two_way(), model={("ML", "home"): 0.75, ("ML", "away"): 0.25})
    assert legs == [] and why == "model and market disagree strongly"
    ok = _legs(_event(1), _two_way(), model={("ML", "home"): 0.52, ("ML", "away"): 0.48})
    assert {x["model_prob"] for x in ok} == {0.52, 0.48}


def test_exchanges_inform_consensus_but_are_never_parlay_bookmakers():
    books = _two_way()
    books[("ML", None)]["Betfair Exchange"] = {"home": 2.2, "away": 1.9}
    legs = _legs(_event(1), books)
    assert all("Betfair Exchange" not in x["books"] for x in legs)


# ---------- combinations ----------
def test_cross_sport_combination_at_one_bookmaker():
    pool = [_legs(_event(1, "nba"), _two_way())[0], _legs(_event(2, "nfl"), _two_way())[0],
            _legs(_event(3, "football"), _three_way())[0], _legs(_event(4, "tennis"), _two_way())[0]]
    cands, stats = pe.search(pool)
    assert cands and all(c["bookmaker"] == "Bet365" for c in cands)
    best = max(cands, key=lambda c: c["n_legs"])
    assert best["n_legs"] == 4 and {x["sport"] for x in best["legs"]} == {"nba", "nfl", "soccer", "tennis"}
    odds, joint, ev = pe.combo_value(best["legs"], "Bet365")
    assert best["computed_product_odds"] == pytest.approx(odds, abs=1e-4) and ev > 0
    assert stats["passing_by_size"][2] == 6 and not stats["truncated"]


def test_same_competition_same_game_and_shared_team_are_never_combined():
    same_comp = [_legs(_event(1, "nba"), _two_way())[0], _legs(_event(2, "nba"), _two_way())[0]]
    assert pe.search(same_comp)[0] == []
    shared = [_legs(_event(1, "nba", home="Lakers"), _two_way())[0],
              _legs(_event(2, "nfl", away="Lakers"), _two_way())[0]]
    assert pe.search(shared)[0] == []
    both_sides = _legs(_event(1, "nba"), _two_way(2.10, 2.10))     # home and away of one game
    assert len(both_sides) == 2 and pe.search(both_sides)[0] == []


def test_legs_priced_at_different_bookmakers_never_combine():
    a = _legs(_event(1, "nba"), _two_way(soft="Bet365"))[0]
    b = _legs(_event(2, "nfl"), _two_way(soft="BookX"))[0]
    assert pe.search([a, b])[0] == []                               # no single slip has value on both


def test_negative_value_legs_are_not_used_at_that_bookmaker():
    a = _legs(_event(1, "nba"), _two_way())[0]
    b = _legs(_event(2, "nfl"), _two_way(1.85, 1.85))[0]            # Bet365 below fair on both sides
    assert pe.search([a, b])[0] == []


def test_search_is_bounded():
    pool = []
    for i in range(40):
        sport = ("nba", "nfl", "tennis", "football")[i % 4]
        leg = _legs(_event(i, sport, league=f"L{i}"), _three_way() if sport == "football" else _two_way())[0]
        pool.append(leg)
    cands, stats = pe.search(pool, beam=20, max_evals=500)
    assert stats["evaluated"] <= 500 and stats["truncated"]
    assert all(v <= 20 for v in stats["passing_by_size"].values())
    assert max(c["n_legs"] for c in cands) <= pe.MAX_LEGS


def test_shortlist_caps_exposure_dedupes_and_allows_zero():
    pool = [_legs(_event(i, ("nba", "nfl", "tennis")[i % 3], league=f"L{i}"), _two_way())[0] for i in range(9)]
    cands, _ = pe.search(pool)
    short = pe.shortlist(cands)
    used = [x["event_id"] for c in short for x in c["legs"]]
    assert len(used) == len(set(used)) and len(short) <= pe.SHORTLIST_MAX
    assert pe.shortlist([]) == []


def test_every_candidate_is_blocked_from_production_today():
    pool = [_legs(_event(1, "nba"), _two_way())[0], _legs(_event(2, "nfl"), _two_way())[0]]
    c = pe.search(pool)[0][0]
    c["id"] = pe.candidate_id(c, "2026-11-13")
    blockers = pe.production_blockers(c, {"passed": False}, set())
    assert any("computed product" in b for b in blockers) and "joint calibration criteria not met" in blockers


# ---------- against a database ----------
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


def test_run_end_to_end_time_window_stale_odds_and_no_publication(con, monkeypatch):
    fresh, stale = NOW - timedelta(hours=1), NOW - timedelta(hours=30)
    _store(con, "nba:1", "nba", "NBA", NOW + timedelta(hours=8), "H1", "A1", _two_way(), fresh)
    _store(con, "nfl:2", "nfl", "NFL", NOW + timedelta(hours=9), "H2", "A2", _two_way(), fresh)
    _store(con, "tennis:3", "tennis", "TENNIS:ATP", NOW + timedelta(hours=6), "P1", "P2", _two_way(), stale)
    _store(con, "nba:4", "nba", "NBA", NOW - timedelta(hours=1), "H4", "A4", _two_way(), fresh)       # started
    _store(con, "nfl:5", "nfl", "NFL", NOW + timedelta(hours=30), "H5", "A5", _two_way(), fresh)      # tomorrow
    _store(con, "hockey:6", "hockey", "NHL", NOW + timedelta(hours=7), "H6", "A6", _two_way(), fresh)
    con.commit()
    r = pe.write(con, NOW, record_ledger=True)
    cov = r["coverage"]
    assert cov["events_today"] == 4                                       # started and tomorrow excluded
    assert cov["excluded"]["event: no fresh result-market prices"] == 1   # stale tennis quotes
    assert cov["excluded"]["event: unsupported sport"] == 1
    assert r["publication"] == "shadow_only" and r["price_kind"] == "computed_product_not_a_quote"
    assert len(r["shortlist"]) == 1 and r["shortlist"][0]["bookmaker"] == "Bet365"
    assert r["shortlist"][0]["production_blockers"]
    assert r["ledger_rows_added"] == 1
    assert (config.REPORTS_DIR / "parlay_candidates.md").exists()
    assert (config.DATA_DIR / "analysis" / "parlay_candidates.json").exists()
    assert not config.SITE_DIR.exists()                                   # the homepage data is never written
    # The stage-1 homepage builder still publishes nothing: no straight picks, gates closed.
    assert parlays.build([], NOW)["status"] == "not_published"
    # Append-only: the same shortlist is not recorded twice; earlier rows survive.
    assert pe.record(r, NOW + timedelta(minutes=5)) == 0
    with pe.ledger_path().open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1 and rows[0]["price_kind"] == "computed_product_not_a_quote"


def test_zero_candidates_is_reported_honestly(con):
    r = pe.write(con, NOW)
    assert r["shortlist"] == [] and r["candidates_found"] == 0
    assert any("0 candidates is the honest result" in w for w in r["why_not_3_to_5"])


def test_shadow_settlement_from_final_scores(con):
    _store(con, "nba:1", "nba", "NBA", NOW + timedelta(hours=8), "H1", "A1", _two_way(), NOW - timedelta(hours=1))
    _store(con, "nfl:2", "nfl", "NFL", NOW + timedelta(hours=9), "H2", "A2", _two_way(), NOW - timedelta(hours=1))
    con.commit()
    r = pe.write(con, NOW, record_ledger=True)
    assert pe.settle_summary(con)["open"] == 1
    con.execute("UPDATE events SET status='finished', home_score=110, away_score=100 WHERE event_id='nba:1'")
    con.execute("UPDATE events SET status='finished', home_score=20, away_score=17 WHERE event_id='nfl:2'")
    s = pe.settle_summary(con)
    assert (s["won"], s["lost"], s["open"]) == (1, 0, 0)
    assert s["expected_wins_settled"] == pytest.approx(r["shortlist"][0]["joint_prob_independent"], abs=1e-3)
    con.execute("UPDATE events SET away_score=30 WHERE event_id='nfl:2'")
    assert pe.settle_summary(con)["lost"] == 1


def test_engine_makes_no_network_request(con, monkeypatch):
    import requests

    def boom(*a, **k):
        raise AssertionError("network request attempted")
    monkeypatch.setattr(requests.Session, "request", boom)
    _store(con, "nba:1", "nba", "NBA", NOW + timedelta(hours=8), "H1", "A1", _two_way(), NOW - timedelta(hours=1))
    con.commit()
    pe.write(con, NOW)


def test_daily_pipeline_runs_the_engine_as_a_research_job():
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "sbi" / "pipeline.py").read_text()
    i, j = src.index('"parlay-candidates"'), src.index('db.job(con, "publish")')
    assert i < j and "record_ledger=True" in src[i:j] and "except Exception" in src[i:j]
