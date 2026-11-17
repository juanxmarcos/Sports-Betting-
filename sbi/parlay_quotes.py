"""Owner-supplied bookmaker parlay quotes, with verification (issue #33, fallback path).

No legally usable, no-cost data source returns a bookmaker's own price for a combination
(docs/PARLAYS.md section 1). The only zero-cost route to a REAL combined quote is the owner
reading it off a bookmaker's bet slip and recording it here. Doyen never fetches or scrapes
bet slips, never places a bet, and never treats a product of leg prices as a quote.

Records live in `data/parlay_quotes.json` (append-only: a correction is a new record).
A record only counts when `quote_problem` returns None:
- 2-6 legs, each a current published straight pick, on distinct events;
- the bookmaker quotes every leg's exact selection in Doyen's own stored prices;
- the combined odds are consistent with that bookmaker's leg prices (a large gap means the
  wrong legs, a different market, a boost, or correlation pricing: all need a human look);
- a timezone-aware `quoted_at`, not in the future, on the same New York day as now (issue #53:
  the site is rebuilt once a day, so a price from today's slip stays usable until the first leg
  starts, and the card says when it was quoted). A price from a previous New York day never counts.
An old quote is never relabelled as fresh: it simply stops counting.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from math import prod
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config
from .sources.books import normalize_book

KIND = "bookmaker_combined"
ORIGIN = "owner_bet_slip"
# Consistency band for combined odds / product of the SAME bookmaker's stored leg prices.
# Unrelated legs at one bookmaker are normally priced at (close to) the product. Outside this
# band the record is rejected for review instead of guessed at.
MIN_RATIO, MAX_RATIO = 0.85, 1.02
NY = ZoneInfo("America/New_York")   # the site's publishing day: a quote counts only on its own day


def path() -> Path:
    return config.DATA_DIR / "parlay_quotes.json"


def load(p: Path | None = None) -> list[dict]:
    p = p or path()
    if not p.exists():
        return []
    data = json.loads(p.read_text() or "[]")
    return data if isinstance(data, list) else []


def quote_id(rec: dict) -> str:
    key = json.dumps([rec["bookmaker"], sorted(rec["legs"]), rec["decimal_odds"], rec["quoted_at"]])
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def make(bookmaker: str, decimal_odds: float, legs: list[str], quoted_at: datetime, source: str,
         recorded_at: datetime) -> dict:
    rec = {"bookmaker": bookmaker.strip(), "decimal_odds": float(decimal_odds), "legs": sorted(set(legs)),
           "quoted_at": quoted_at.isoformat(), "source": source.strip(), "origin": ORIGIN,
           "kind": KIND, "recorded_at": recorded_at.isoformat()}
    rec["quote_id"] = quote_id(rec)
    return rec


def append(rec: dict, p: Path | None = None) -> bool:
    """Append one record. Existing records are never edited or removed. False = duplicate."""
    p = p or path()
    data = load(p)
    if any(r.get("quote_id") == rec["quote_id"] for r in data):
        return False
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data + [rec], indent=1) + "\n")
    return True


def _ts(x) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else None


def book_leg_prices(bookmaker: str, legs: list[dict]) -> list[float] | None:
    """This bookmaker's own stored price for every leg's exact selection, or None."""
    want = normalize_book(bookmaker)
    out = []
    for leg in legs:
        best = None
        for bk, prices in (leg.get("prices") or {}).items():
            if normalize_book(bk) == want:
                p = (prices or {}).get(leg["selection_key"])
                if p and p > 1.0:
                    best = max(best or 0.0, float(p))
        if best is None:
            return None
        out.append(best)
    return out


def same_ny_day(at: datetime, now: datetime) -> bool:
    return at.astimezone(NY).date() == now.astimezone(NY).date()


def quote_problem(rec, legs_by_id: dict, now: datetime, max_age_minutes: int | None = None) -> str | None:
    """Why this owner-recorded quote cannot be used now. None = verified for use.
    A quote counts only on its own New York day; `max_age_minutes` is an optional extra cap."""
    if not isinstance(rec, dict) or rec.get("kind") != KIND or rec.get("origin") != ORIGIN:
        return "not an owner-recorded bookmaker quote"
    if not isinstance(rec.get("bookmaker"), str) or not rec["bookmaker"].strip():
        return "missing bookmaker"
    if not isinstance(rec.get("source"), str) or not rec["source"].strip():
        return "missing provenance"
    ids = rec.get("legs")
    if not isinstance(ids, list) or not 2 <= len(set(ids)) <= 6 or len(set(ids)) != len(ids):
        return "needs 2-6 distinct legs"
    if any(i not in legs_by_id for i in ids):
        return "a leg is not a current usable pick"
    legs = [legs_by_id[i] for i in ids]
    if len({leg["event_id"] for leg in legs}) != len(legs):
        return "two legs on the same event"
    odds = rec.get("decimal_odds")
    if isinstance(odds, bool) or not isinstance(odds, (int, float)) or not odds > 1.0:
        return "invalid combined odds"
    at = _ts(rec.get("quoted_at"))
    if at is None or at > now:
        return "quote has no valid time"
    if not same_ny_day(at, now):
        return "quote is stale"
    if max_age_minutes is not None and (now - at).total_seconds() > max_age_minutes * 60:
        return "quote is stale"
    prices = book_leg_prices(rec["bookmaker"], legs)
    if prices is None:
        return "bookmaker does not price every leg in Doyen's data"
    ratio = float(odds) / prod(prices)
    if not MIN_RATIO <= ratio <= MAX_RATIO:
        return "combined odds inconsistent with the bookmaker's leg prices (review)"
    return None
