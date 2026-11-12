from datetime import datetime, timedelta, timezone

from sbi import db, disagreement
from sbi.engine import Candidate
from sbi.markets import Outcome


def _c(model_q, market_q, sel="H"):
    return Candidate("1X2", sel, None, model_q, 0.0, model_q, market_q, "Betfair Exchange", market_q, market_q, "Bet365",
                     1.8, 1.8, 0.04, 0.04, 0.0, 1.0, 5, Outcome(pw=market_q, pl=1 - market_q))


def _odds(con, eid, src, bk, prices, ts):
    for s, p in zip("HDA", prices):
        con.execute("INSERT INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,retrieved_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (eid, bk, "1X2", s, None, p, "pre", src, ts))


def test_small_gap_not_screened(tmp_path):
    con = db.connect(tmp_path / "t.sqlite")
    r = disagreement.screen(con, datetime.now(timezone.utc), "e", _c(0.50, 0.55), n_min=50, min_history=12)
    assert r["category"] == "none" and not r["held"]


def test_unexplained_extreme_gap_is_held(tmp_path):
    con = db.connect(tmp_path / "t.sqlite")
    r = disagreement.screen(con, datetime.now(timezone.utc), "e", _c(0.34, 0.57), n_min=80, min_history=12)
    assert r["category"] == "unexplained" and r["held"]


def test_explained_by_key_absence_not_held(tmp_path):
    con = db.connect(tmp_path / "t.sqlite")
    inj = {"Philadelphia 76ers": [{"player": "LeBron James", "status": "Out", "key": True}]}
    r = disagreement.screen(con, datetime.now(timezone.utc), "e", _c(0.49, 0.73), n_min=80, min_history=12, injuries=inj)
    assert r["category"] == "explained" and not r["held"] and "LeBron James" in r["flags"][0]


def test_feed_conflict_is_technical_even_if_explained(tmp_path):
    con = db.connect(tmp_path / "t.sqlite")
    now = datetime.now(timezone.utc)
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,updated_at)
                   VALUES ('e','football','INT:x',?,'A','B','scheduled','t','t')""", ((now + timedelta(days=1)).isoformat(),))
    ts = (now - timedelta(hours=1)).isoformat()
    _odds(con, "e", "the-odds-api.com", "Betfair Exchange", (1.75, 3.9, 5.2), ts)   # home ~ 0.56
    _odds(con, "e", "espn.com (public scoreboard)", "DraftKings", (2.6, 3.3, 2.8), ts)  # home ~ 0.37
    r = disagreement.screen(con, now, "e", _c(0.36, 0.56), n_min=5, min_history=12)
    assert r["category"] == "technical_suspect" and r["held"]
    assert any("feeds disagree" in f for f in r["flags"])


def test_filter_removes_held_and_records_reason(tmp_path):
    con = db.connect(tmp_path / "t.sqlite")
    pool = {"e": [_c(0.34, 0.57), _c(0.30, 0.31, "D")]}
    rej = {"e": {}}
    disagreement.filter_candidates(con, datetime.now(timezone.utc), pool, rej, {"e": {"n_min": 80, "min_history": 12}})
    assert [c.selection for c in pool["e"]] == ["D"]
    assert rej["e"]["1X2:H:None"] == "extreme disagreement (review)"
    assert con.execute("SELECT COUNT(*) FROM disagreement_reviews WHERE held=1").fetchone()[0] == 1
