"""Single picks under the loosened rules (owner decision, issue #99, 2026-11-19).

The owner approved loosening the single-pick rules the same way estimated parlays were loosened
(#51, #68), because the Single picks page was almost always empty. The new rules apply to NEW
picks only and are recorded on each one as `rules_version` (`RULES_VERSION`) in its immutable
`evidence_json`. Picks published before keep their old rules (`LEGACY_RULES_VERSION`), odds and
results; nothing already published is edited or deleted (the database triggers forbid it).

Rules (`singles-v2`), mirroring the estimated-parlay leg screens in `sbi.parlay_estimated`:
- Games: Soccer, NFL, NBA or Tennis, later today (America/New_York date) and not started.
- Price: one bookmaker's latest stored price, retrieved on the same New York day and before the
  game starts. One bookmaker is enough. Exchanges and aggregate columns are never the pricing book.
- Probability: Doyen's stored model probability where one exists; otherwise the de-vigged
  consensus of the OTHER bookmakers, and, only when there is none, the consensus of at least two
  independent bookmakers including the pricing one (as parlays do since #51).
- Value: Doyen probability x price > 1 (positive estimated value), no extra margin.
- Kept screens: market probability inside the research band 0.30-0.85; the stored model within
  0.12 of the market (data sanity).
- Injury/lineup notes: never a reason to exclude; the open note is stored on the pick and shown on
  its card (#68).
- Volume: per run, the best picks by estimated value, at most one per game and at most
  `MAX_PER_DAY` picks for games on one New York day (picks already published for that day count).
  A game that already has a published pick (any rules) gets no second one. Zero is a normal result.
- Markets: those the leg pool offers AND the settlement code grades with a market reference
  (`engine.SELECTIONS`): match result / moneyline, soccer over/under and both-teams-to-score, NBA and
  NFL point spreads and game totals. Double chance and draw no bet are not used for singles.

Previews (Tomorrow, +2, +3) use the same rules with the preview price rule of #58 (latest stored
price at the time of the run, before the game starts). They are never published or recorded.

No network request is made and no API credit is spent: the module reads prices the twice-daily run
already stored. The old single-pick rules in `sbi.config.SelectionRules` are not changed; the
existing pipeline keeps running with them alongside this one.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime

from . import config, parlay_engine
from . import parlay_estimated as pe
from .engine import SELECTIONS

RULES_VERSION = "singles-v2"            # issue #99: loosened rules, new picks only
LEGACY_RULES_VERSION = "singles-v1"     # every pick published before #99 (no rules_version stored)
METHOD = "singles-loose-v1"
MAX_PER_DAY = 5                         # a cap, never a target
MIN_VALUE = 0.0                         # probability x price - 1 must be strictly above this
MARKETS = frozenset(SELECTIONS)         # settleable with a market reference (no DC / DNB)
PREVIEW_BADGE = pe.PREVIEW_BADGE
EMPTY_TEXT = "No single picks today."
PREVIEW_EMPTY_TEXT = "No single picks for this day yet."
RULES_TEXT = ("Loosened rules (issue #99): one bookmaker's price from today, Doyen probability x price > 1, "
              "probability 30-85%, model within 12 points of the market, injury notes shown not filtered, "
              "best 5 a day by value, one per game.")


def rules_version(evidence: dict | str | None) -> str:
    """The rules a published pick was selected under (old picks carry none: legacy)."""
    if isinstance(evidence, str):
        try:
            evidence = json.loads(evidence or "{}")
        except ValueError:
            evidence = {}
    return (evidence or {}).get("rules_version") or LEGACY_RULES_VERSION


def is_loose(row) -> bool:
    """True when a recommendations row was published under the loosened rules."""
    try:
        ev = row["evidence_json"]
    except (KeyError, IndexError, TypeError):
        ev = None
    return rules_version(ev) == RULES_VERSION


def rec_id(event_id: str, market: str, selection: str, line) -> str:
    """Same id scheme as `pipeline.publish_pick`, so one (game, market, selection, line) is one row."""
    return hashlib.sha1(f"{event_id}|{market}|{selection}|{line}".encode()).hexdigest()[:16]


# ---------- selection (pure) ----------
def best_price(leg: dict) -> tuple[str, dict] | None:
    """The pricing bookmaker with the highest positive estimated value for this leg, or None."""
    ok = [(bk, b) for bk, b in (leg.get("books") or {}).items()
          if b["prob"] * b["price"] - 1.0 > MIN_VALUE]
    if not ok:
        return None
    return max(ok, key=lambda kv: (kv[1]["prob"] * kv[1]["price"] - 1.0, kv[1]["price"], kv[0]))


def candidates(pool: list[dict]) -> tuple[list[dict], Counter]:
    """One candidate per game: its best positive-value selection at its best bookmaker."""
    best, why = {}, Counter()
    for leg in pool:
        if leg["market"] not in MARKETS:
            why["market not used for singles"] += 1
            continue
        got = best_price(leg)
        if not got:
            why["no positive estimated value"] += 1
            continue
        bk, b = got
        c = {**leg, "bookmaker": bk, "price": float(b["price"]), "prob": float(b["prob"]),
             "value": float(b["prob"]) * float(b["price"]) - 1.0, "prob_source_used": b["prob_source"]}
        k = leg["event_id"]
        rank = lambda x: (x["value"], x["price"], x["market"], x["selection"])
        if k not in best or rank(c) > rank(best[k]):
            best[k] = c
    out = sorted(best.values(), key=lambda x: (-x["value"], x["start_utc"], x["event_id"]))
    return out, why


def select(cands: list[dict], blocked_events: set | None = None, already_today: int = 0,
           limit: int = MAX_PER_DAY) -> list[dict]:
    """The best candidates by value, skipping games that already have a pick, up to the day's cap."""
    room = max(0, limit - already_today)
    blocked = set(blocked_events or ())
    out = []
    for c in cands:
        if len(out) >= room:
            break
        if c["event_id"] in blocked:
            continue
        blocked.add(c["event_id"])
        out.append(c)
    return out


# ---------- database ----------
def _picks_on_day(con, day: str) -> int:
    n = 0
    for r in con.execute("SELECT kickoff_utc FROM recommendations"):
        t = pe.parlays._ts(r[0])
        if t is not None and pe._ny_day(t) == day:
            n += 1
    return n


def _row(c: dict, now: datetime, rank: int) -> tuple:
    from .explain import selection_label
    home, away = c["participants"]
    sel = {"market": c["market"], "selection": c["selection"], "line": c.get("line"), "home": home, "away": away}
    others = {bk: {c["selection"]: b["price"]} for bk, b in (c.get("books") or {}).items()}
    evidence = {
        "rules_version": RULES_VERSION, "method": METHOD,
        "prob_source": c["prob_source_used"], "consensus_prob": c.get("consensus_prob"),
        "consensus_source": {"model": "Doyen model", "market_consensus_ex_book": "other bookmakers' consensus",
                             "market_consensus_incl_book": "consensus incl. the pricing bookmaker"}.get(c["prob_source_used"]),
        "n_bookmakers": len(others), "all_prices": others, "price_rule": pe.PRICE_RULE,
        "competition": c.get("competition"), "risk_note": c.get("risk_note"),
        "risks": ["Selected under the loosened single-pick rules (issue #99): one bookmaker's price is enough and the "
                  "only value check is probability x price > 1, so the estimated edge is smaller and less certain "
                  "than under the original rules."] + ([c["risk_note"]] if c.get("risk_note") else []),
        "selection_text": selection_label(sel),
    }
    if c.get("prob_note"):
        evidence["prob_note"] = c["prob_note"]
    ts = (c.get("price_ts") or {}).get(c["bookmaker"])
    model_p = c.get("model_prob")
    mv = "singles-v2:" + ("model" if c["prob_source_used"] == "model" else "market")
    return (rec_id(c["event_id"], c["market"], c["selection"], c.get("line")), c["event_id"], now.isoformat(),
            {"soccer": "football"}.get(c["sport"], c["sport"]), c["league"], c["start_utc"], home, away,
            c["market"], c["selection"], c.get("line"), c["bookmaker"], c["price"], ts,
            float(model_p) if model_p is not None else c["prob"], c.get("consensus_prob"), c["prob"],
            1.0 / c["prob"], c["value"], c["value"], None, config.RULES.stake_units, mv, rank,
            json.dumps(evidence, default=str), json.dumps([]))


def publish(con, now: datetime) -> dict:
    """Publish today's single picks under the loosened rules. Append-only: `INSERT OR IGNORE`, so a
    pick already published (any rules) is never touched and never published twice."""
    day = parlay_engine._day(now)
    pool, cov = pe.build_pool(con, now, adjust=False)      # issue #106: singles-v2 keeps raw probabilities
    cands, why = candidates(pool)
    blocked = {r[0] for r in con.execute("SELECT event_id FROM recommendations")}
    already = _picks_on_day(con, day)
    picked = select(cands, blocked, already)
    published = 0
    for rank, c in enumerate(picked, 1):
        cur = con.execute("""INSERT OR IGNORE INTO recommendations(rec_id,event_id,published_at,sport,league,kickoff_utc,
                home,away,market,selection,line,bookmaker,odds,odds_retrieved_at,model_prob,market_prob,final_prob,
                fair_odds,ev,ev_lower,prob_sd,stake_units,model_version,rank,evidence_json,source_urls)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", _row(c, now, rank))
        published += cur.rowcount
    con.commit()
    return {"rules_version": RULES_VERSION, "date": day, "events_today": cov["events_today"],
            "pool_legs": cov["legs"], "candidates": len(cands), "already_published_today": already,
            "published": published, "excluded": dict(sorted(why.items()))}


def preview(con, now: datetime, day: str) -> dict:
    """Single picks the same rules would choose for a later New York date. Never published."""
    pool, cov = pe.build_pool(con, now, day, adjust=False)
    cands, _ = candidates(pool)
    blocked = {r[0] for r in con.execute("SELECT event_id FROM recommendations")}
    picked = select(cands, blocked, _picks_on_day(con, day))
    from .explain import market_label, selection_label
    recs = []
    for c in picked:
        home, away = c["participants"]
        recs.append({"id": "preview:" + rec_id(c["event_id"], c["market"], c["selection"], c.get("line")),
                     "preview": True, "event_id": c["event_id"], "sport": c["sport"],
                     "competition": c.get("competition"), "title": c["title"], "start_utc": c["start_utc"],
                     "market": market_label(c["market"]),
                     "selection": selection_label({"market": c["market"], "selection": c["selection"],
                                                   "line": c.get("line"), "home": home, "away": away}),
                     "odds": round(c["price"], 4), "bookmaker": c["bookmaker"],
                     "price_at": (c.get("price_ts") or {}).get(c["bookmaker"]), "risk_note": c.get("risk_note"),
                     "rules_version": RULES_VERSION, "status": {"state": "preview", "label": "Preview"}})
    return {"date": day, "badge": PREVIEW_BADGE, "price_rule": pe.PREVIEW_PRICE_RULE,
            "coverage": {"events": cov["events_today"], "legs": cov["legs"]}, "recommendations": recs}


def previews(con, now: datetime) -> list[dict]:
    out = []
    for day in pe.preview_days(now):
        try:
            out.append(preview(con, now, day))
        except Exception as e:  # noqa: BLE001 - a preview must never take the site down
            out.append({"date": day, "badge": PREVIEW_BADGE, "recommendations": [], "error": type(e).__name__})
    return out


# ---------- site block ----------
def compact(p: dict) -> dict:
    """The fields a Today-page single card needs, from an exported pick (`site._pick`)."""
    st = p.get("status") or {}
    return {"id": p["id"], "event_id": p["event_id"], "sport": p["sport"], "competition": p.get("competition"),
            "title": p["title"], "start_utc": p["start_utc"], "published_at": p.get("published_at"),
            "market": p["market"], "selection": p["selection"], "odds": p["odds"], "bookmaker": p.get("bookmaker"),
            "price_at": p.get("odds_updated"), "risk_note": p.get("risk_note"),
            "rules_version": p.get("rules_version") or LEGACY_RULES_VERSION,
            "status": {k: st.get(k) for k in ("state", "label", "result", "pnl", "note") if st.get(k) is not None}}


def record(picks: list[dict], version: str = RULES_VERSION) -> dict:
    """Won-lost and paper P/L (1-unit stakes) of exported picks under one rules version."""
    ps = [p for p in picks if (p.get("rules_version") or LEGACY_RULES_VERSION) == version]
    st = [p for p in ps if (p.get("status") or {}).get("state") == "settled"]
    won = sum(p["status"]["result"] in ("won", "half_won") for p in st)
    lost = sum(p["status"]["result"] in ("lost", "half_lost") for p in st)
    first = min((p["published_at"] for p in ps if p.get("published_at")), default=None)
    return {"rules_version": version, "picks": len(ps), "won": won, "lost": lost, "push": len(st) - won - lost,
            "open": len(ps) - len(st), "profit_units": round(sum(p["status"].get("pnl") or 0 for p in st), 2),
            "since": first}


def block(con, now: datetime, picks_all: list[dict]) -> dict:
    """`singles` block for the Today page: published picks by New York date (today and the preview
    days), previews of picks not yet published, and the record since the loosened rules started."""
    today = parlay_engine._day(now)
    days = [today] + pe.preview_days(now)
    by_day = {d: [] for d in days}
    for p in picks_all:
        t = pe.parlays._ts(p.get("start_utc"))
        d = pe._ny_day(t) if t is not None else None
        if d in by_day:
            by_day[d].append(compact(p))
    for d in by_day:
        by_day[d].sort(key=lambda x: (x["start_utc"], x["title"]))
    return {"method": METHOD, "rules_version": RULES_VERSION, "rules": RULES_TEXT, "date": today,
            "max_per_day": MAX_PER_DAY, "empty_text": EMPTY_TEXT, "preview_empty_text": PREVIEW_EMPTY_TEXT,
            "days": by_day, "previews": previews(con, now), "record": record(picks_all)}
