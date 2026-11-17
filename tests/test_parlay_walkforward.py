"""Issue #38 (PR B of #35): walk-forward validation of multi-leg joint probabilities. Shadow only:
point-in-time replay of the live engine, network-free, pre-registered criteria, append-only ledger."""
import csv
import json
from datetime import datetime, timedelta, timezone

import pytest

from sbi import config, db, parlay_engine as pe, parlay_walkforward as wf

T = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)          # 10:00 New York


def _two_way(soft_home=2.10, soft_away=1.80, soft="Bet365"):
    return {("ML", None): {"Pinnacle": {"home": 1.95, "away": 1.95}, "DraftKings": {"home": 1.93, "away": 1.93},
                           "Unibet": {"home": 1.94, "away": 1.94}, soft: {"home": soft_home, "away": soft_away}}}


@pytest.fixture
def con(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(config, "SITE_DIR", tmp_path / "site")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    return db.connect(tmp_path / "t.sqlite")


def _store(con, eid, sport, league, ko, home, away, books, retrieved, status="finished", score=(110, 100)):
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,home_score,away_score,source,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (eid, sport, league, ko.isoformat(), home, away, status,
                                                       *(score if status == "finished" else (None, None)), "test", db.utcnow()))
    _odds(con, eid, books, retrieved)


def _odds(con, eid, books, retrieved):
    for (market, line), bks in books.items():
        for bk, q in bks.items():
            for sel, price in q.items():
                con.execute("""INSERT INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,retrieved_at)
                               VALUES (?,?,?,?,?,?,?,?,?)""", (eid, bk, market, sel, line, price, "pre",
                                                               "https://api.the-odds-api.com/v4/x", retrieved.isoformat()))


def _job(con, t):
    con.execute("INSERT INTO job_runs(job, started_at, status) VALUES ('publish', ?, 'ok')", (t.isoformat(),))


def _slate(con):
    """An NBA and an NFL game that evening, both finished now with the home side winning."""
    _store(con, "nba:1", "nba", "NBA", T + timedelta(hours=8), "H1", "A1", _two_way(), T - timedelta(hours=1))
    _store(con, "nfl:2", "nfl", "NFL", T + timedelta(hours=9), "H2", "A2", _two_way(), T - timedelta(hours=1),
           score=(20, 17))
    _job(con, T)
    con.commit()


# ---------- point-in-time snapshot ----------
def test_snapshot_hides_the_future(con):
    _slate(con)
    _odds(con, "nba:1", {("ML", None): {"Bet365": {"home": 9.0, "away": 1.01}}}, T + timedelta(hours=2))  # later quote
    con.execute("""INSERT INTO research_notes(event_id,category,claim,evidence_type,created_at)
                   VALUES ('nfl:2','injury','x','verified_fact',?)""", ((T + timedelta(hours=1)).isoformat(),))
    con.commit()
    snap = wf.snapshot(con, T)
    ev = {r["event_id"]: dict(r) for r in snap.execute("SELECT * FROM events")}
    assert set(ev) == {"nba:1", "nfl:2"}
    assert all(e["status"] == "scheduled" and e["home_score"] is None for e in ev.values())   # no results leak
    assert snap.execute("SELECT MAX(retrieved_at) FROM odds").fetchone()[0] <= T.isoformat()
    assert snap.execute("SELECT COUNT(*) FROM odds WHERE price=9.0").fetchone()[0] == 0
    assert snap.execute("SELECT COUNT(*) FROM research_notes").fetchone()[0] == 0              # note written later
    # The live engine on the snapshot sees exactly the pre-decision world.
    bp = pe.build_pool(snap, T)
    assert {x["event_id"] for x in bp["pool"]} == {"nba:1", "nfl:2"}
    assert bp["pool"][0]["books"]["Bet365"]["price"] in (2.10, 1.80)


def test_snapshot_excludes_started_and_other_day_events(con):
    _store(con, "nba:0", "nba", "NBA", T - timedelta(hours=1), "H0", "A0", _two_way(), T - timedelta(hours=3))
    _store(con, "nba:9", "nba", "NBA", T + timedelta(hours=30), "H9", "A9", _two_way(), T - timedelta(hours=1))
    con.commit()
    assert wf.snapshot(con, T).execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0


def test_all_fresh_counterfactual_only_restamps_quotes_known_before_the_decision(con):
    _store(con, "nba:1", "nba", "NBA", T + timedelta(hours=8), "H1", "A1", _two_way(), T - timedelta(hours=20))
    _odds(con, "nba:1", {("ML", None): {"Bet365": {"home": 9.0, "away": 1.01}}}, T + timedelta(hours=2))
    con.commit()
    live = pe.build_pool(wf.snapshot(con, T), T)
    assert live["excluded"]["event: no fresh result-market prices"] == 1 and not live["pool"]   # 20 h old, game in 8 h
    snap = wf.snapshot(con, T, all_fresh=True)
    assert snap.execute("SELECT COUNT(*) FROM odds WHERE price=9.0").fetchone()[0] == 0
    assert len(pe.build_pool(snap, T)["pool"]) == 1


# ---------- replay, settlement, ledger ----------
def test_end_to_end_replay_scores_and_records(con):
    _slate(con)
    out = wf.write(con, record_ledger=True, focus_day="2026-11-13")
    r = out["result"]
    assert r["publication"] == "shadow_only" and r["price_kind"] == "computed_product_not_a_quote"
    assert r["decision_times"] == 1 and r["legs_settled"] == 2
    assert r["replay_combinations"]["2"]["combinations"] == 1
    # The engine shortlists Bet365 home+home (value at the slip); both home sides won.
    assert r["shortlist"]["settled"] == 1 and r["shortlist"]["by_legs"][2]["leave_one_out_fair"]["observed_wins"] == 1
    assert r["verdict_replay"]["fit_to_back_recommendation"] is False      # tiny sample never passes
    assert r["ledger_rows_added"] == 1
    assert (config.REPORTS_DIR / "parlay_walkforward.md").exists()
    assert (config.DATA_DIR / "analysis" / "parlay_walkforward.json").exists()
    assert not config.SITE_DIR.exists()                                     # homepage data never written
    text = (config.REPORTS_DIR / "parlay_walkforward.md").read_text()
    assert "fit to back a recommendation: NO" in text and "Why 2026-11-13 gave 0 candidates" in text
    # Append-only: a second run adds nothing and keeps the first row.
    assert wf.write(con, record_ledger=True)["result"]["ledger_rows_added"] == 0
    with wf.ledger_path().open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1 and rows[0]["origin"] == "walk_forward_replay"
    assert rows[0]["price_kind"] == "computed_product_not_a_quote"
    assert not pe.ledger_path().exists()                                    # the live ledger is untouched


def test_unsettled_and_void_legs_are_not_scored(con):
    _store(con, "nba:1", "nba", "NBA", T + timedelta(hours=8), "H1", "A1", _two_way(), T - timedelta(hours=1),
           status="scheduled")
    _store(con, "nfl:2", "nfl", "NFL", T + timedelta(hours=9), "H2", "A2", _two_way(), T - timedelta(hours=1),
           status="postponed")
    _job(con, T)
    con.commit()
    r = wf.evaluate(con, wf.decision_times(con), with_counterfactuals=False)
    assert r["legs_seen"] == 2 and r["legs_settled"] == 0 and r["shortlist"]["settled"] == 0


def test_replay_makes_no_network_request(con, monkeypatch):
    import requests

    def boom(*a, **k):
        raise AssertionError("network request attempted")
    monkeypatch.setattr(requests.Session, "request", boom)
    _slate(con)
    wf.write(con)


def test_replay_never_writes_to_the_source_database(con):
    _slate(con)
    before = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("events", "odds", "predictions")}
    wf.evaluate(con, wf.decision_times(con))
    after = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("events", "odds", "predictions")}
    assert before == after
    assert con.execute("SELECT status FROM events WHERE event_id='nba:1'").fetchone()[0] == "finished"


# ---------- grouping and scoring (pure) ----------
def _leg(i, comp, y=1, p=0.5, day="2026-11-13", teams=None):
    return {"event_id": f"e{i}", "date": day, "sport": comp.split("|")[0], "competition": comp,
            "start": f"2026-11-13T{10 + i:02d}:00:00+00:00", "participants": teams or [f"h{i}", f"a{i}"],
            "league": comp, "p_market": p, "p_model": None, "in_pool": True, "y": y}


def test_disjoint_groups_respect_link_screens_and_use_each_leg_once():
    legs = [_leg(0, "nba|NBA"), _leg(1, "nba|NBA"), _leg(2, "nfl|NFL"), _leg(3, "soccer|EPL"),
            _leg(4, "tennis|ATP", teams=["h0", "x"])]
    g2 = wf.disjoint_groups(legs, 2)
    ids = [x["event_id"] for g in g2 for x in g]
    assert len(ids) == len(set(ids))
    for g in g2:
        assert len({x["competition"] for x in g}) == 2
        assert not (set(g[0]["participants"]) & set(g[1]["participants"]))
    assert len(wf.disjoint_groups(legs, 6)) == 0
    other_day = [_leg(0, "nba|NBA"), _leg(1, "nfl|NFL", day="2026-11-14")]
    assert wf.disjoint_groups(other_day, 2) == []                           # never across days


def test_score_known_values():
    s = wf.score([0.5, 0.5], [1, 0])
    assert s["log_loss"] == pytest.approx(0.6931, abs=1e-4) and s["brier"] == 0.25
    assert s["z"] == 0.0 and s["observed_wins"] == 1 and s["expected_wins"] == 1.0
    assert wf.wilson(0, 10)[0] == 0.0 and wf.wilson(10, 10)[1] == 1.0


def test_joint_prediction_is_the_product_of_leg_probabilities():
    g = [[_leg(0, "nba|NBA", p=0.6), _leg(1, "nfl|NFL", p=0.5)]]
    s = wf.score_groups(g)
    assert s["independence_market"]["expected_wins"] == pytest.approx(0.3)
    assert s["independence_market"]["observed_wins"] == 1


def test_correlation_splits_pairs_by_relation():
    legs = [_leg(0, "nba|NBA"), _leg(1, "nba|NBA", y=0), _leg(2, "nfl|NFL")]
    c = wf.correlation(legs)
    assert c["same competition"]["pairs"] == 1 and c["different competition"]["pairs"] == 2
    assert c["same competition"]["mean_residual_cov"] == pytest.approx(-0.25)


# ---------- pre-registered criteria ----------
def test_criteria_are_fixed_and_not_loosened():
    assert wf.CRITERIA == {"min_combinations_per_leg_count": 200, "max_abs_joint_z": 1.96, "min_legs": 500,
                           "max_abs_leg_z": 1.96, "min_pairs_correlation": 200}
    assert wf.LEG_COUNTS == (2, 3, 4, 5, 6)


def test_verdict_passes_only_when_every_criterion_holds():
    good = {"combinations": 250, "independence_market": {"z": 0.5}}
    leg_ok = {"n": 600, "z": 0.1}
    corr_ok = {"different competition": {"pairs": 300, "cov_95": (-0.01, 0.01)}}
    assert wf.verdict({2: good}, leg_ok, corr_ok)["fit_to_back_recommendation"] is True
    assert wf.verdict({2: {**good, "combinations": 199}}, leg_ok, corr_ok)["fit_to_back_recommendation"] is False
    assert wf.verdict({2: {**good, "independence_market": {"z": 2.5}}}, leg_ok, corr_ok)["fit_to_back_recommendation"] is False
    assert wf.verdict({2: good}, {"n": 400, "z": 0.1}, corr_ok)["fit_to_back_recommendation"] is False
    bad_corr = {"different competition": {"pairs": 300, "cov_95": (0.01, 0.03)}}
    assert wf.verdict({2: good}, leg_ok, bad_corr)["fit_to_back_recommendation"] is False
    assert wf.verdict({2: good, 3: {"combinations": 0, "independence_market": {"n": 0}}}, leg_ok,
                      corr_ok)["fit_to_back_recommendation"] is False


def test_live_engine_defaults_are_unchanged_by_the_counterfactual_hook():
    """The counterfactual passes its own link screen; the live search still uses the full screen."""
    import inspect
    assert inspect.signature(pe.search).parameters["linked"].default is None
    a = {"event_id": "x", "participants": ["a", "b"], "sport": "nba", "competition": "NBA"}
    b = {"event_id": "y", "participants": ["c", "d"], "sport": "nba", "competition": "NBA"}
    assert pe._linked(a, b) == ["same competition"]
