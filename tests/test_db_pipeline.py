import json
import sqlite3
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from sbi import config, db


@pytest.fixture
def con(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(config, "SITE_DIR", tmp_path / "site")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    return db.connect(tmp_path / "t.sqlite")


def _history(now):
    from tests.test_ev_model import synthetic
    teams, att, dfn, H, A, HG, AG, days = synthetic(3, seed=3)
    ko = [now - timedelta(days=float(d) + 1) for d in days]
    return pd.DataFrame({"div": "E0", "home": H, "away": A, "kickoff_utc": pd.to_datetime(ko, utc=True),
                         "hg": HG, "ag": AG, "hxg": np.nan, "axg": np.nan, "season": "2627",
                         "event_id": [f"h{i}" for i in range(len(H))]})


def test_end_to_end_publish_settle_immutable(con, monkeypatch):
    from sbi import pipeline, settle, report, dashboard
    now = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
    hist = _history(now)
    monkeypatch.setattr(pipeline, "load_league", lambda div, seasons: (hist, None))
    ko = (now + timedelta(hours=10)).isoformat()
    eid = "football:E0:20261120:t0:t1"
    con.execute("""INSERT INTO events(event_id,sport,league,season,kickoff_utc,home,away,status,source,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""", (eid, "football", "E0", "2627", ko, "T0", "T1", "scheduled", "test", db.utcnow()))
    ts = (now - timedelta(hours=2)).isoformat()
    for bk, (h, d, a) in {"Pinnacle": (2.0, 3.6, 4.0), "Bet365": (2.05, 3.5, 3.9), "Bwin": (1.95, 3.6, 4.8),
                          "Betfred": (2.0, 3.4, 3.9)}.items():
        for s, p in zip("HDA", (h, d, a)):
            con.execute("INSERT INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,retrieved_at) VALUES (?,?,?,?,?,?,?,?,?)",
                        (eid, bk, "1X2", s, None, p, "pre", "test", ts))
    con.commit()
    monkeypatch.setattr(config.RULES, "max_prob_sd", 1.0)
    s = pipeline.analyse(con, now)
    assert s["analysed_events"] == 1
    recs = con.execute("SELECT * FROM recommendations").fetchall()
    assert len(recs) == 1 and recs[0]["selection"] == "A" and recs[0]["bookmaker"] == "Bwin"
    # re-running does not duplicate
    pipeline.analyse(con, now)
    assert con.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0] == 1
    # immutability
    with pytest.raises(sqlite3.DatabaseError):
        con.execute("UPDATE recommendations SET odds=10")
    with pytest.raises(sqlite3.DatabaseError):
        con.execute("DELETE FROM recommendations")
    # settle: away win 0-2
    con.execute("UPDATE events SET status='finished', home_score=0, away_score=2 WHERE event_id=?", (eid,))
    for s_, p in zip("HDA", (2.1, 3.5, 3.7)):
        con.execute("INSERT INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,retrieved_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (eid, "Pinnacle", "1X2", s_, None, p, "closing", "test", now.isoformat()))
    n = settle.settle_all(con, now + timedelta(days=1))
    r = con.execute("SELECT * FROM recommendations").fetchone()
    assert n["settled"] == 1 and r["status"] == "won" and r["pnl_units"] == pytest.approx(3.8)
    assert r["clv"] is not None and r["clv"] > 0
    p = report.write_daily(con, now, s)
    assert "Ranked selections" in p.read_text()
    out = dashboard.build(con)
    data = json.loads((out.parent / "data.json").read_text())
    assert data["performance"]["settled"] == 1


def test_no_opportunities_report(con):
    from sbi import report
    now = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
    p = report.write_daily(con, now, {"events_in_window": 0, "analysed_events": 0, "leagues": {}})
    assert "No qualifying opportunities today" in p.read_text()


def test_research_note_rules(con):
    from sbi.research import add_note
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,source,updated_at)
                   VALUES ('e','football','E0','2026-11-20T15:00:00+00:00','A','B','t','now')""")
    with pytest.raises(ValueError):
        add_note(con, "e", "injury", "X out", "verified_fact")  # needs URL
    assert add_note(con, "e", "injury", "X out", "verified_fact", "against", "https://example.org") > 0
