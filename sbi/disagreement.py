"""Extreme model-vs-market disagreement screening.

Historical finding (club soccer, 9,920 test matches): the larger the gap between Doyen's
model and the de-vigged sharp market, the more decisively the MARKET is right
(log loss at gap >= 0.20: model 1.029 vs market 0.837). Large gaps therefore signal model
error or a data fault, never a reason to bet. Picks rest on price-vs-consensus, so a large
gap is screened for TECHNICAL faults (wrong match, conflicting sources) and for known
explanations; unexplained or technically suspect extreme gaps are held for review and
not published.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from . import db
from . import ev as evm
from .engine import SELECTIONS
from .sources.books import normalize_book

EXTREME_GAP = 0.15
SOURCE_CONFLICT = 0.08

SCHEMA = """
CREATE TABLE IF NOT EXISTS disagreement_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT, market TEXT, selection TEXT, line REAL,
    model_prob REAL, market_prob REAL, gap REAL, category TEXT, flags TEXT, held INTEGER, created_at TEXT);
CREATE TABLE IF NOT EXISTS odds_match_audit (
    event_id TEXT, source TEXT, provider_home TEXT, provider_away TEXT, score REAL, kickoff_diff_min REAL,
    swapped INTEGER, retrieved_at TEXT, PRIMARY KEY (event_id, source));
"""


def ensure(con):
    con.executescript(SCHEMA)


def _source_consensus(con, event_id, market, line, selection, now, max_age_h=24):
    """De-vigged probability for one selection, separately per odds SOURCE (feed)."""
    sels = SELECTIONS.get(market, [])
    rows = con.execute("""SELECT source, bookmaker, selection, price, retrieved_at FROM odds WHERE event_id=? AND kind='pre'
                          AND market=? AND IFNULL(line,-999)=IFNULL(?,-999)""", (event_id, market, line)).fetchall()
    by_src: dict = {}
    for r in rows:
        if (now - datetime.fromisoformat(r["retrieved_at"])).total_seconds() / 3600 > max_age_h:
            continue
        src = "espn" if "espn" in (r["source"] or "") else r["source"]
        bk = normalize_book(r["bookmaker"])
        cur = by_src.setdefault(src, {}).setdefault(bk, {})
        old = cur.get(r["selection"])
        if not old or r["retrieved_at"] > old[1]:
            cur[r["selection"]] = (r["price"], r["retrieved_at"])
    out = {}
    for src, book in by_src.items():
        clean = {bk: {s: p for s, (p, _) in q.items()} for bk, q in book.items()}
        cons, ref = evm.consensus(clean, sels)
        if cons and selection in cons:
            out[src] = (cons[selection], ref)
    return out


def _movement(con, event_id, market, line, selection, ref_book, now, hours=48):
    """Change in the reference bookmaker's implied probability over the last `hours`."""
    if not ref_book or ref_book.startswith(("median", "single")):
        return None
    rows = con.execute("""SELECT price, retrieved_at FROM odds WHERE event_id=? AND kind='pre' AND market=? AND selection=?
                          AND IFNULL(line,-999)=IFNULL(?,-999) ORDER BY retrieved_at""",
                       (event_id, market, selection, line)).fetchall()
    rows = [r for r in rows if (now - datetime.fromisoformat(r["retrieved_at"])) <= timedelta(hours=hours)]
    if len(rows) < 2:
        return None
    return 1 / rows[-1]["price"] - 1 / rows[0]["price"]


def screen(con, now, event_id: str, c, *, n_min: int, min_history: int, injuries: dict | None = None,
           known_bias: bool = False) -> dict:
    """Return {'gap','category','flags','held'} for one candidate."""
    ensure(con)
    res = {"gap": None, "category": "none", "flags": [], "held": False}
    if c.market_q is None or c.model_q is None:
        return res
    gap = abs(c.model_q - c.market_q)
    res["gap"] = round(gap, 4)
    if gap < EXTREME_GAP:
        return res
    tech, expl = [], []
    # 1) feeds disagree on the same selection -> possible mismatch / stale feed
    per_src = _source_consensus(con, event_id, c.market, c.line, c.selection, now)
    if len(per_src) >= 2:
        vals = [v for v, _ in per_src.values()]
        if max(vals) - min(vals) >= SOURCE_CONFLICT:
            tech.append("odds feeds disagree: " + ", ".join(f"{k} {v * 100:.0f}%" for k, (v, _) in per_src.items()))
    # 2) weak event match recorded by the odds connector
    for a in con.execute("SELECT * FROM odds_match_audit WHERE event_id=?", (event_id,)):
        if a["score"] is not None and a["score"] < 0.8:
            tech.append(f"weak team-name match with {a['source']} ({a['score']:.2f}: {a['provider_home']} v {a['provider_away']})")
        if a["kickoff_diff_min"] is not None and abs(a["kickoff_diff_min"]) > 90:
            tech.append(f"kick-off times differ by {a['kickoff_diff_min']:.0f} min between feeds")
    # 3) known explanations (model-side or news)
    if n_min < 2 * min_history:
        expl.append(f"thin model history (a side has {n_min} matches)")
    if known_bias:
        expl.append("documented model calibration bias for this competition/price range")
    for team, lst in (injuries or {}).items():
        key_out = [i["player"] for i in lst if i.get("key") and i.get("status") in ("Out", "Doubtful")]
        if key_out:
            expl.append(f"key absences for {team}: {', '.join(key_out)}")
    ref = next((r for _, r in per_src.values()), None)
    mv = _movement(con, event_id, c.market, c.line, c.selection, ref, now)
    if mv is not None and abs(mv) >= 0.04:
        expl.append(f"sharp price moved {mv * 100:+.0f} pts in 48h")
    res["flags"] = tech + expl
    res["category"] = "technical_suspect" if tech else ("explained" if expl else "unexplained")
    res["held"] = res["category"] in ("technical_suspect", "unexplained")
    con.execute("""INSERT INTO disagreement_reviews(event_id,market,selection,line,model_prob,market_prob,gap,category,flags,held,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (event_id, c.market, c.selection, c.line, c.model_q, c.market_q, gap,
                                                       res["category"], json.dumps(res["flags"]), int(res["held"]), db.utcnow()))
    return res


def filter_candidates(con, now, cands_by_event: dict, rejections_by_event: dict | None, info: dict) -> dict:
    """Remove held candidates before selection. info[eid] = dict(n_min, min_history, injuries, known_bias).
    Returns {eid: [screen results]} and updates rejection reasons in place."""
    out = {}
    for eid, cands in cands_by_event.items():
        keep = []
        for c in cands:
            # only candidates that would otherwise be eligible need screening
            if c.ev < 0:
                keep.append(c)
                continue
            r = screen(con, now, eid, c, **info.get(eid, {"n_min": 999, "min_history": 0}))
            out.setdefault(eid, []).append((c, r))
            if r["held"]:
                if rejections_by_event is not None:
                    rejections_by_event.setdefault(eid, {})[f"{c.market}:{c.selection}:{c.line}"] = "extreme disagreement (review)"
                continue
            keep.append(c)
        cands_by_event[eid] = keep
    con.commit()
    return out
