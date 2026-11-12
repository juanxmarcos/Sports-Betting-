"""Regression tests: missing data must exclude, never crash or invent; time zones convert correctly."""
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from sbi import config, db


def test_football_data_uk_time_to_utc_across_dst():
    from sbi.sources.football_data import _kickoff_utc
    summer = _kickoff_utc({"Date": "25/10/2025", "Time": "15:00"})   # BST (UTC+1)
    winter = _kickoff_utc({"Date": "01/11/2025", "Time": "15:00"})   # GMT
    assert summer == datetime(2025, 10, 25, 14, 0, tzinfo=timezone.utc)
    assert winter == datetime(2025, 11, 1, 15, 0, tzinfo=timezone.utc)
    assert _kickoff_utc({"Date": "01/11/2025", "Time": None}).hour == 15   # missing time -> default, no crash


def test_international_analysis_single_book_and_no_odds(tmp_path, monkeypatch):
    """Historic failure: round(None) when the only bookmaker gave no consensus."""
    from sbi import intl
    from sbi.sources import international as src
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    con = db.connect(tmp_path / "t.sqlite")
    now = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)
    rng = np.random.default_rng(0)
    teams = [f"N{i}" for i in range(10)]
    rows = []
    for k in range(900):
        h, a = rng.choice(teams, 2, replace=False)
        rows.append({"home": h, "away": a, "hg": rng.poisson(1.4), "ag": rng.poisson(1.1), "tournament": "Qualifier",
                     "neutral": False, "kickoff_utc": pd.Timestamp(now - timedelta(days=int(k * 2 + 1))), "src": "t"})
    monkeypatch.setattr(src, "training_frame", lambda now, recent: pd.DataFrame(rows))
    con.execute("CREATE TABLE IF NOT EXISTS event_meta (event_id TEXT PRIMARY KEY, neutral INTEGER, competition TEXT)")
    for eid, h, a in (("football:INT:x:1", "N0", "N1"), ("football:INT:x:2", "N2", "N3")):
        con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,source_url,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""", (eid, "football", "INT:x", (now + timedelta(hours=20)).isoformat(),
                                                       h, a, "scheduled", "t", "u", "t"))
        con.execute("INSERT INTO event_meta VALUES (?,?,?)", (eid, 0, "Qualifier"))
    for s_, p in zip("HDA", (1.9, 3.4, 4.2)):   # single bookmaker on event 1, nothing on event 2
        con.execute("INSERT INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,retrieved_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    ("football:INT:x:1", "DraftKings", "1X2", s_, None, p, "pre", "t", now.isoformat()))
    con.commit()
    out = intl.analyse(con, now, [])
    assert out["analysed"] == 2 and out["published"] == 0          # single book can never qualify
    rows_by = {r["event_id"]: r for r in out["rows"]}
    assert "book_1x2" in rows_by["football:INT:x:1"] and "book_1x2" not in rows_by["football:INT:x:2"]


def test_stale_odds_are_not_actionable(tmp_path):
    from sbi.pipeline import _latest_books
    con = db.connect(tmp_path / "t.sqlite")
    now = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,updated_at)
                   VALUES ('e','football','E0',?,'A','B','scheduled','t','t')""", ((now + timedelta(days=3)).isoformat(),))
    old = (now - timedelta(hours=config.RULES.max_odds_age_hours + 1)).isoformat()
    for s_, p in zip("HDA", (2.0, 3.4, 3.8)):
        con.execute("INSERT INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,retrieved_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    ("e", "Bet365", "1X2", s_, None, p, "pre", "t", old))
    books, newest, _ = _latest_books(con, "e", config.RULES.max_odds_age_hours, now)
    assert books == {} and newest == old                            # stale -> excluded, but recorded as stale
    assert config.RULES.max_odds_age_hours <= 24 and config.RULES.publish_window_hours == 168


def test_bookmaker_aliases_count_once_and_latest_wins(tmp_path):
    from sbi.pipeline import _latest_books
    con = db.connect(tmp_path / "t.sqlite")
    now = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,updated_at)
                   VALUES ('e','football','INT:x',?,'A','B','scheduled','t','t')""", ((now + timedelta(days=1)).isoformat(),))
    for bk, ts, px in (("Unibet (SE)", now - timedelta(hours=6), 6.0), ("Unibet", now - timedelta(hours=1), 5.6)):
        for s_, p in zip("HDA", (px, 4.0, 1.6)):
            con.execute("INSERT INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,retrieved_at) VALUES (?,?,?,?,?,?,?,?,?)",
                        ("e", bk, "1X2", s_, None, p, "pre", "t", ts.isoformat()))
    books, _, _ = _latest_books(con, "e", 24, now)
    assert list(books[("1X2", None)]) == ["Unibet"] and books[("1X2", None)]["Unibet"]["H"] == 5.6


def test_source_specific_freshness():
    from sbi.odds_policy import max_age_hours
    assert max_age_hours("espn.com (public scoreboard)", 48) == 6
    assert max_age_hours("the-odds-api.com", 5) == 6 and max_age_hours("the-odds-api.com", 20) == 12
    assert max_age_hours("the-odds-api.com", 100) == 24
    assert max_age_hours("football-data.co.uk", 4) == 12


def test_espn_quote_older_than_6h_not_actionable(tmp_path):
    from sbi.pipeline import _latest_books
    con = db.connect(tmp_path / "t.sqlite")
    now = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,updated_at)
                   VALUES ('e','nba','NBA',?,'A','B','scheduled','t','t')""", ((now + timedelta(days=2)).isoformat(),))
    for src, bk, age in (("espn.com (public scoreboard)", "DraftKings", 8), ("the-odds-api.com", "Pinnacle", 8)):
        for s_, p in (("home", 1.8), ("away", 2.1)):
            con.execute("INSERT INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,retrieved_at) VALUES (?,?,?,?,?,?,?,?,?)",
                        ("e", bk, "ML", s_, None, p, "pre", src, (now - timedelta(hours=age)).isoformat()))
    books, _, _ = _latest_books(con, "e", 24, now)
    assert list(books[("ML", None)]) == ["Pinnacle"]          # 8h-old ESPN quote dropped, Odds API (48h out) kept


def test_same_group_brands_count_once_and_no_self_consensus():
    from sbi import ev as evm
    book = {"Betsson": {"H": 2.0, "A": 1.9}, "Nordic Bet": {"H": 2.0, "A": 1.9}, "Pinnacle": {"H": 1.95, "A": 1.95}}
    assert evm.n_books(book, ["H", "A"]) == 2
    c, src = evm.consensus_excluding(book, ["H", "A"], "Pinnacle")
    assert src != "Pinnacle"


def test_integrity_audit_withdraws_superseded_price_keeps_original(tmp_path):
    import json, sqlite3
    from sbi import integrity
    con = db.connect(tmp_path / "t.sqlite")
    now = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)
    pub = now - timedelta(hours=1)
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,updated_at)
                   VALUES ('e','football','INT:x',?,'Andorra','Gibraltar','scheduled','t','t')""", ((now + timedelta(hours=8)).isoformat(),))
    for bk, ts, px in (("LeoVegas (SE)", pub - timedelta(hours=2), 1.80), ("LeoVegas", pub - timedelta(minutes=1), 1.77)):
        con.execute("INSERT INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,retrieved_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    ("e", bk, "1X2", "H", None, px, "pre", "the-odds-api.com", ts.isoformat()))
    con.execute("""INSERT INTO recommendations(rec_id,event_id,published_at,sport,league,kickoff_utc,home,away,market,selection,
                   line,bookmaker,odds,model_prob,market_prob,final_prob,fair_odds,ev,ev_lower,stake_units,model_version,evidence_json)
                   VALUES ('r','e',?,'football','INT:x',?,'Andorra','Gibraltar','1X2','H',NULL,'LeoVegas (SE)',1.80,0.341,0.573,0.573,
                   1.745,0.031,0.031,1,'t','{}')""", (pub.isoformat(), (now + timedelta(hours=8)).isoformat()))
    out = integrity.audit_open(con, now)
    u = con.execute("SELECT status, note FROM rec_updates").fetchone()
    assert out == {"audited": 1, "withdrawn": 1, "passed": 0} and u["status"] == "withdrawn"
    assert "superseded" in u["note"] and "34% vs 57%" in u["note"]
    assert con.execute("SELECT odds FROM recommendations").fetchone()[0] == 1.80          # original untouched
    assert integrity.audit_open(con, now)["audited"] == 0                                 # audited once


def test_integrity_withdrawal_is_terminal(tmp_path):
    from sbi import settle
    con = db.connect(tmp_path / "t.sqlite")
    now = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,updated_at)
                   VALUES ('e','football','INT:x',?,'A','B','scheduled','t','t')""", ((now + timedelta(hours=8)).isoformat(),))
    con.execute("""INSERT INTO recommendations(rec_id,event_id,published_at,sport,league,kickoff_utc,home,away,market,selection,
                   line,bookmaker,odds,model_prob,market_prob,final_prob,fair_odds,ev,ev_lower,stake_units,model_version)
                   VALUES ('r','e',?,'football','INT:x',?,'A','B','1X2','H',NULL,'X',2.0,0.5,0.5,0.5,2.0,0.04,0.04,1,'t')""",
                (now.isoformat(), (now + timedelta(hours=8)).isoformat()))
    con.execute("INSERT INTO rec_updates(rec_id,checked_at,status,note) VALUES ('r',?,'withdrawn','Integrity audit (v0.5): fails — x.')",
                (now.isoformat(),))
    settle.reassess_open(con, now + timedelta(hours=1))
    assert con.execute("SELECT status FROM rec_updates ORDER BY id DESC LIMIT 1").fetchone()[0] == "withdrawn"
