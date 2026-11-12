"""Post-publication integrity audit (append-only).

For each open recommendation not yet audited:
 1. Was the published price the bookmaker's LATEST quote at publication (after name normalisation)?
 2. Recompute EV at that latest quote; must still clear the EV threshold.
 3. Extreme model-vs-market disagreement must be explained (same rule as pre-publication screening).
Failures append a 'withdrawn' rec_update with the reason. The original row is never modified.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from . import config, db
from .disagreement import EXTREME_GAP
from .sources.books import normalize_book

TAG = "Integrity audit"


def audit_open(con, now: datetime) -> dict:
    out = {"audited": 0, "withdrawn": 0, "passed": 0}
    for r in con.execute("SELECT * FROM recommendations WHERE status='open'").fetchall():
        if con.execute("SELECT 1 FROM rec_updates WHERE rec_id=? AND note LIKE ?", (r["rec_id"], TAG + "%")).fetchone():
            continue
        out["audited"] += 1
        pub = datetime.fromisoformat(r["published_at"])
        target = normalize_book(r["bookmaker"])
        latest = None
        for q in con.execute("""SELECT bookmaker, price, retrieved_at FROM odds WHERE event_id=? AND market=? AND selection=?
                                AND IFNULL(line,-999)=IFNULL(?,-999) AND kind='pre' AND retrieved_at <= ?""",
                             (r["event_id"], r["market"], r["selection"], r["line"], (pub + timedelta(minutes=5)).isoformat())):
            if normalize_book(q["bookmaker"]) == target and (latest is None or q["retrieved_at"] > latest["retrieved_at"]):
                latest = q
        reasons = []
        if latest is None:
            reasons.append("published price could not be traced to a stored quote")
        elif abs(latest["price"] - r["odds"]) > 1e-9:
            ev_latest = r["market_prob"] * latest["price"] - 1 if r["market_prob"] else None
            reasons.append(f"published {r['odds']:.2f} was a superseded quote; {target}'s latest was {latest['price']:.2f}"
                           + (f" (EV {ev_latest * 100:+.1f}%)" if ev_latest is not None else ""))
            if ev_latest is not None and ev_latest >= config.RULES.min_ev:
                reasons.pop()   # superseded but the latest quote still qualified -> not a failure
        if r["model_prob"] is not None and r["market_prob"] is not None and abs(r["model_prob"] - r["market_prob"]) >= EXTREME_GAP:
            ev_j = json.loads(r["evidence_json"] or "{}")
            explained = any(k in ev_j for k in ("injuries",)) and ev_j.get("injuries")
            if not explained:
                reasons.append(f"unexplained model–market gap ({r['model_prob'] * 100:.0f}% vs {r['market_prob'] * 100:.0f}%)")
        if reasons:
            con.execute("INSERT INTO rec_updates(rec_id,checked_at,status,note) VALUES (?,?,?,?)",
                        (r["rec_id"], now.isoformat(), "withdrawn", f"{TAG} (v0.5): fails — " + "; ".join(reasons) + "."))
            out["withdrawn"] += 1
        else:
            con.execute("INSERT INTO rec_updates(rec_id,checked_at,status,note) VALUES (?,?,?,?)",
                        (r["rec_id"], now.isoformat(), _last_status(con, r["rec_id"]), f"{TAG} (v0.5): passed."))
            out["passed"] += 1
    con.commit()
    return out


def _last_status(con, rec_id):
    u = con.execute("SELECT status FROM rec_updates WHERE rec_id=? ORDER BY id DESC LIMIT 1", (rec_id,)).fetchone()
    return u["status"] if u and u["status"] in ("active", "updated", "withdrawn") else "active"
