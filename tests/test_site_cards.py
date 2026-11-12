"""Compact-card contract: short fields exist, are short, and never invent odds."""
import json
from datetime import datetime, timedelta, timezone

from sbi import config, db, site, watch
from sbi.engine import Candidate
from sbi.markets import Outcome


def _cand(ev, odds=1.9, n_books=5, mq=0.5):
    return Candidate("1X2", "H", None, 0.5, 0.0, 0.5, mq, "Pinnacle", mq, mq, "Bet365", odds, odds, ev, ev, 0.0, 1.0,
                     n_books, Outcome(pw=mq, pl=1 - mq))


def test_watch_short_and_funnel(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path / "r")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    con = db.connect(tmp_path / "t.sqlite")
    now = datetime.now(timezone.utc)
    rows = []
    for i, (ev, reason, books) in enumerate([(0.01, "EV below threshold", 6), (-0.02, "too few bookmakers", 1)]):
        c = _cand(ev, n_books=books)
        rows.append(watch.analysis_row(sport="soccer", event_id=f"e{i}", competition="X", title=f"A{i} v B{i}",
                                       participants=[f"A{i}", f"B{i}"], start_utc=(now + timedelta(hours=30)).isoformat(),
                                       now=now, cands=[c], rejections={"1X2:H:None": reason}, odds_ts=now.isoformat()))
    rows.append(watch.analysis_row(sport="soccer", event_id="e9", competition="X", title="C v D", participants=["C", "D"],
                                   start_utc=(now + timedelta(hours=30)).isoformat(), now=now))
    watch.write("soccer_club", rows)
    d = json.loads(site.build(con, now).read_text())
    ev = {e["event_id"]: e for e in d["events"]}
    assert ev["e0"]["short"].startswith("Waiting for better odds (") and len(ev["e0"]["short"].split()) <= 12
    assert ev["e1"]["short"] == "Waiting for more bookmakers to price it."
    assert ev["e9"]["short"] == "Waiting for bookmaker prices." and "closest" not in ev["e9"]   # no invented odds
    assert d["watching"][0] == "e0"                          # closest to threshold ranks first
    assert d["briefing"]["sentence"]
    diag = json.loads((tmp_path / "diagnostics.json").read_text())
    f = diag["funnel_48h"]["soccer"]["funnel"]
    assert f["events_discovered"] == 3 and f["with_odds"] == 2 and f["with_3plus_bookmakers"] == 1


def test_short_reason_is_short():
    from sbi.explain import short_reason
    r = {"odds": 4.8, "market_prob": 0.24, "model_prob": 0.25}
    s = short_reason(r, {})
    assert len(s.split()) <= 12 and "4.80" in s and "4.17" in s
