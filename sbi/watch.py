"""Per-event analysis rows shared by every sport.

Each sport's analysis writes data/analysis/<name>.json: one row per upcoming event with
the model view, the market view, the closest candidate and - when nothing qualifies -
*why*, and what Doyen is waiting for. The site builder turns these into "Upcoming" and
"Matches Doyen Is Watching". Rows never contain invented information: every field is
computed from stored odds, model output or rule outcomes.
"""
from __future__ import annotations

import json
from datetime import datetime

from . import config, db

MARKET_LABEL = {"1X2": "Match result", "OU": "Total goals", "AH": "Asian handicap",
                "ML": "Moneyline", "SPREAD": "Point spread", "TOTAL": "Total points",
                "WIN": "Outright winner", "TOP5": "Top 5 finish", "TOP10": "Top 10 finish",
                "TOP20": "Top 20 finish", "CUT": "Make the cut", "H2H": "Head-to-head"}


def qualifying_odds(c, min_ev: float) -> float | None:
    """Price at which this selection would meet the EV threshold (same probability)."""
    if not c.final_q or c.active <= 0:
        return None
    return (min_ev / c.active + 1) / c.final_q


def waiting_for(reason: str | None, c, hours_to_start: float, sport: str, n_books: int) -> str:
    rules = config.RULES
    if c is None:
        return "bookmaker prices for this event"
    if reason == "too few bookmakers":
        return (f"prices from more bookmakers (only {c.n_books} quoting this market) to form a reliable consensus")
    if reason == "EV below threshold":
        q = qualifying_odds(c, rules.min_ev)
        return (f"a better price: {c.odds:.2f} is available, about {q:.2f} would qualify" if q
                else "price movement")
    if reason == "odds outside range":
        return (f"a price inside Doyen's range — the only edge is at {c.odds:.2f}, outside the "
                f"{rules.min_odds:.2f}–{rules.max_odds:.2f} limits used to avoid long-shot noise")
    if reason == "insufficient team history":
        return "more match history for one of the teams before modelling it"
    if reason == "no market consensus":
        return "a sharp reference price (Pinnacle or Betfair Exchange)"
    if reason in ("model uncertainty too high", "pessimistic EV not positive"):
        return "firmer evidence: the edge does not survive the model's uncertainty"
    if hours_to_start < 24 and sport in ("soccer", "nfl", "nba"):
        return "confirmed lineups and the final pre-game price"
    return "updated prices closer to the start"


def best_candidate(cands, rejections: dict):
    if not cands:
        return None, None
    c = max(cands, key=lambda x: x.ev)
    return c, rejections.get(f"{c.market}:{c.selection}:{c.line}")


def analysis_row(*, sport: str, event_id: str, competition: str, title: str, start_utc: str,
                 now: datetime, cands=None, rejections=None, model_view: dict | None = None,
                 book_view: dict | None = None, end_utc: str | None = None, notes: list | None = None,
                 participants: list | None = None, neutral: bool = False, odds_ts: str | None = None,
                 extra: dict | None = None) -> dict:
    cands = cands or []
    c, reason = best_candidate(cands, rejections or {})
    start = datetime.fromisoformat(start_utc)
    hours = (start - now).total_seconds() / 3600
    n_books = max((x.n_books for x in cands), default=0)
    row = {"event_id": event_id, "sport": sport, "competition": competition, "title": title,
           "participants": participants, "start_utc": start_utc, "end_utc": end_utc, "neutral": neutral,
           "model_view": model_view or {}, "book_view": book_view or {}, "n_books": n_books,
           "odds_updated": odds_ts, "notes": notes or [], **(extra or {})}
    if c is not None:
        row["closest"] = {"market": c.market, "market_label": MARKET_LABEL.get(c.market, c.market),
                          "selection": c.selection, "line": c.line, "odds": round(c.odds, 3),
                          "bookmaker": c.bookmaker, "prob": round(float(c.final_q), 4),
                          "model_prob": round(float(c.model_q), 4),
                          "market_prob": None if c.market_q is None else round(float(c.market_q), 4),
                          "ev": round(float(c.ev), 4), "reason": reason, "active": round(float(c.active), 4),
                          "n_books": c.n_books}
    row["waiting_for"] = waiting_for(reason, c, hours, sport, n_books)
    # opportunity-funnel facts for diagnostics (computed from rule outcomes only)
    from collections import Counter
    reasons = Counter((rejections or {}).values())
    row["funnel"] = {"n_markets": len(cands), "reasons": dict(reasons), "max_books": n_books,
                     "has_odds": bool(cands), "stale_odds": bool(odds_ts) and not cands,
                     "history_ok": "insufficient team history" not in reasons,
                     "qualified": reasons.get("ok", 0)}
    return row


def write(name: str, rows: list[dict], meta: dict | None = None) -> None:
    d = config.DATA_DIR / "analysis"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.json").write_text(json.dumps({"generated": db.utcnow(), "meta": meta or {}, "rows": rows},
                                               default=str))
