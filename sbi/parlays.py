"""Recommended Parlays of the Day: staged, audit-only (issue #7).

Stage 0 (this module): Doyen publishes NO parlays. Every run screens the day's straight picks,
counts what was checked and why it was excluded, and exports that audit with an empty
recommendation list so the site can say "No verified parlays today" from data, not from a
hard-coded card.

A parlay may only ever be published when ALL prerequisites below are met. Two of them are
capabilities Doyen does not have (see docs/PARLAYS.md), so `recommendations` is always empty:

1. combined_quote: a price for the parlay itself, quoted by one bookmaker. Doyen's feeds return
   single-market prices only. Multiplying leg prices is how a bookmaker *usually* prices
   unrelated legs, but it is not evidence that this bookmaker accepts this combination at
   that price (market rules, limits, related-event restrictions).
2. joint_calibration: evidence that Doyen's leg probabilities, multiplied, give calibrated joint
   probabilities. There is no settled multi-leg record, and leg-level errors compound.

The arithmetic and the leg screens are implemented and tested here so the later stages build
on verified parts. Nothing in this module changes a pick, a threshold or the ledger.
"""
from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from itertools import combinations
from math import prod
from zoneinfo import ZoneInfo

from . import config, odds_policy
from .sources.books import normalize_book
from .sources.football_data import AGGREGATES

METHOD = "parlay-stage0-audit"
# 2-6 legs (issue #27; was 2-3). A leg limit is not a reason to add legs: never force more legs for payout.
MIN_LEGS, MAX_LEGS = 2, 6

# Capabilities a published parlay needs. None = not available. Do not set these to make cards
# appear: each needs its own data source or evidence, reviewed by the owner (docs/PARLAYS.md).
PREREQUISITES = {"combined_quote": None, "joint_calibration": None}

BLOCKERS = {
    "combined_quote": "No bookmaker-quoted parlay price. Doyen's odds feeds return single-market prices only, "
                      "so it cannot verify that any bookmaker offers a given combination, or at what price.",
    "joint_calibration": "No validated joint-probability estimate. Multiplying leg probabilities assumes the legs "
                         "are independent and each leg is well calibrated; Doyen has no settled multi-leg record "
                         "to support that.",
}

HEADLINE = "No verified parlays today"
DISCLOSURE = ("Parlays are higher-variance and win less often than single picks. Any parlay shown here would be "
              "paper-traded research, never a guarantee.")


# ---------- arithmetic (valid only for independent legs) ----------
def combined_odds(leg_odds) -> float:
    """Decimal odds of a parlay whose legs are priced independently: the product of the leg odds."""
    leg_odds = [float(o) for o in leg_odds]
    if len(leg_odds) < 2 or any(o <= 1.0 for o in leg_odds):
        raise ValueError("a parlay needs at least two legs with decimal odds above 1.0")
    return prod(leg_odds)


def joint_prob_independent(leg_probs) -> float:
    """P(all legs win) = product of leg probabilities. ONLY valid if the legs are independent."""
    leg_probs = [float(p) for p in leg_probs]
    if len(leg_probs) < 2 or any(not 0.0 < p < 1.0 for p in leg_probs):
        raise ValueError("a parlay needs at least two legs with probabilities strictly between 0 and 1")
    return prod(leg_probs)


def parlay_ev(joint_prob: float, parlay_odds: float) -> float:
    """EV per unit stake = P(all win) x parlay odds - 1. Leg EVs are never multiplied or added."""
    return joint_prob * parlay_odds - 1.0


# ---------- leg screens ----------
def _norm(name) -> str:
    return " ".join(str(name or "").lower().split())


def correlation_reasons(a: dict, b: dict) -> list[str]:
    """Why two legs may NOT be treated as independent. Empty list = no known link (which is
    weaker than proof of independence)."""
    out = []
    if a["event_id"] == b["event_id"]:
        out.append("same game")
    if {_norm(x) for x in a["participants"]} & {_norm(x) for x in b["participants"]}:
        out.append("shared team or player")
    if a["sport"] == b["sport"] and _norm(a["competition"]) == _norm(b["competition"]):
        out.append("same competition")
    return out


def leg_problem(leg: dict, now: datetime, day: str, tz: str) -> str | None:
    """Why a straight pick cannot be a parlay leg today. None = usable as a leg."""
    start = datetime.fromisoformat(leg["start_utc"])
    if leg["state"] != "active":
        return "pick is not active"
    if start <= now:
        return "event has started"
    if start.astimezone(ZoneInfo(tz)).date().isoformat() != day:
        return "not scheduled today"
    ts = leg.get("odds_updated")
    if not ts:
        return "no price timestamp"
    age_h = (now - datetime.fromisoformat(ts)).total_seconds() / 3600
    if age_h > odds_policy.max_age_hours(leg.get("source"), (start - now).total_seconds() / 3600):
        return "price is stale"
    return None


def single_book_quotes(legs: list[dict]) -> dict[str, list[float]]:
    """Bookmakers that quote EVERY leg's exact selection, with their price for each leg.
    The same bookmaker is required (not just the same owner group): a parlay is one bet slip."""
    per_leg = []
    for leg in legs:
        q = {}
        for bk, prices in (leg.get("prices") or {}).items():
            name = normalize_book(bk)
            price = (prices or {}).get(leg["selection_key"])
            if name and name not in AGGREGATES and price and price > 1.0:
                q[name] = max(price, q.get(name, 0.0))
        per_leg.append(q)
    common = set(per_leg[0]).intersection(*per_leg[1:]) if per_leg else set()
    return {bk: [q[bk] for q in per_leg] for bk in sorted(common)}


def leg_from_pick(pick: dict, row: dict) -> dict:
    """The fields the screens need, from an exported pick and its recommendations row."""
    sources = (pick.get("detail") or {}).get("sources") or []
    return {"id": pick["id"], "event_id": pick["event_id"], "sport": pick["sport"], "competition": pick["competition"],
            "participants": [row["home"], row["away"]], "start_utc": pick["start_utc"],
            "state": pick["status"]["state"], "prob": pick["prob"], "odds_updated": pick.get("odds_updated"),
            "source": " ".join(sources), "selection_key": row["selection"],
            "prices": (pick.get("detail") or {}).get("prices") or {}}


def build(legs: list[dict], now: datetime, tz: str | None = None) -> dict:
    """The `parlays` block of docs/data/doyen.json. `recommendations` stays empty until every
    prerequisite is met; the audit says what was checked."""
    tz = tz or config.TIMEZONE
    day = now.astimezone(ZoneInfo(tz)).date().isoformat()
    excluded: dict[str, int] = {}

    def count(reason: str) -> None:
        excluded[reason] = excluded.get(reason, 0) + 1

    usable = []
    for leg in legs:
        why = leg_problem(leg, now, day, tz)
        if why:
            count("leg: " + why)
        else:
            usable.append(leg)

    checked = passing = 0
    for n in range(MIN_LEGS, MAX_LEGS + 1):
        for combo in combinations(usable, n):
            checked += 1
            links = sorted({r for a, b in combinations(combo, 2) for r in correlation_reasons(a, b)})
            if links:
                count("combination: " + links[0])
                continue
            quotes = single_book_quotes(list(combo))
            if not quotes:
                count("combination: no single bookmaker prices every leg")
                continue
            joint = joint_prob_independent([leg["prob"] for leg in combo])
            if not any(parlay_ev(joint, combined_odds(q)) > 0 for q in quotes.values()):
                count("combination: no positive value at any single bookmaker")
                continue
            passing += 1

    missing = [k for k, v in PREREQUISITES.items() if not v]
    return {
        "date": day, "timezone": tz, "generated": now.isoformat(), "method": METHOD,
        "status": "not_published",
        "headline": HEADLINE,
        "recommendations": [],          # stage 0: never populated, whatever the screens find
        "blockers": [{"key": k, "text": BLOCKERS[k]} for k in missing],
        "audit": {"straight_picks_seen": len(legs), "usable_legs_today": len(usable),
                  "combinations_checked": checked, "passed_leg_screens": passing,
                  "excluded": dict(sorted(excluded.items()))},
        "leg_limits": [MIN_LEGS, MAX_LEGS],
        "disclosure": DISCLOSURE,
    }


# ---------- card contract (issue #27): what a homepage parlay card may show ----------
# The homepage renders a parlay card ONLY for a recommendation that passes every check below.
# docs/assets/doyen.js applies the same rules again in the browser. In stage 0 `build()` never
# produces a recommendation, so these checks guard the future backend and reject injected data.
CARD_SPORTS = ("soccer", "nfl", "nba", "tennis")
CARD_TIMEZONE = "America/New_York"      # the site's authoritative publishing day
CARD_MAX_CARDS = 5                      # a cap, not a target: 0 is a normal result
DEFAULT_STAKE = 10                      # illustrative display amount, in dollars; never a request to bet
MAX_QUOTE_AGE_MINUTES = 30              # a combined quote older than this is not shown as current
QUOTE_KIND = "bookmaker_combined"       # one bookmaker's own price for the whole combination


def _money(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def gross_payout(stake, decimal_odds) -> Decimal:
    """Gross potential payout INCLUDING the stake = stake x quoted combined decimal odds, to the cent.
    This is what the slip returns if every leg wins. It is not expected value."""
    try:
        s, o = Decimal(str(stake)), Decimal(str(decimal_odds))
    except InvalidOperation as e:
        raise ValueError("stake and odds must be numbers") from e
    if not s.is_finite() or not o.is_finite() or s < 0 or o <= 1:
        raise ValueError("stake must be >= 0 and decimal odds > 1")
    return _money(s * o)


def net_profit(stake, decimal_odds) -> Decimal:
    """Net profit if every leg wins = stake x (odds - 1). Always labelled separately from payout."""
    return gross_payout(stake, decimal_odds) - _money(stake)


def _ts(x) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else None


def _num(x) -> float | None:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    x = float(x)
    return x if x == x and x not in (float("inf"), float("-inf")) else None


def card_problem(rec, now: datetime, day: str | None = None) -> str | None:
    """Why `rec` must NOT be shown as a recommended parlay card. None = it may be shown.
    Unknown or missing data is always a rejection."""
    tz = ZoneInfo(CARD_TIMEZONE)
    day = day or now.astimezone(tz).date().isoformat()
    if not isinstance(rec, dict):
        return "not an object"
    if rec.get("mock") or rec.get("test"):
        return "mock or test data"
    if not isinstance(rec.get("parlay_id"), str) or not rec["parlay_id"].strip():
        return "missing parlay_id"
    if rec.get("date") != day:
        return "not today's parlay"
    if rec.get("status") != "active":
        return "parlay is not active"
    if not isinstance(rec.get("bookmaker"), str) or not rec["bookmaker"].strip():
        return "missing bookmaker"
    legs = rec.get("legs")
    if not isinstance(legs, list) or not MIN_LEGS <= len(legs) <= MAX_LEGS:
        return f"needs {MIN_LEGS}-{MAX_LEGS} legs"
    seen = set()
    for leg in legs:
        if not isinstance(leg, dict):
            return "leg is not an object"
        for k in ("event_id", "title", "selection"):
            if not isinstance(leg.get(k), str) or not leg[k].strip():
                return f"leg missing {k}"
        if leg["event_id"] in seen:
            return "two legs on the same event"
        seen.add(leg["event_id"])
        if leg.get("sport") not in CARD_SPORTS:
            return "unsupported sport"
        if leg.get("status") != "active":
            return "leg is not active"
        start = _ts(leg.get("start_utc"))
        if start is None:
            return "leg has no valid start time"
        if start.astimezone(tz).date().isoformat() != day:
            return "leg is not on today's date"
        if start <= now:
            return "leg has started"
    q = rec.get("quote")
    if not isinstance(q, dict) or q.get("kind") != QUOTE_KIND:
        return "no single-bookmaker combined quote"
    if q.get("bookmaker") != rec["bookmaker"]:
        return "quote is from a different bookmaker"
    if not isinstance(q.get("source"), str) or not q["source"].strip():
        return "quote has no provenance"
    odds = _num(q.get("decimal_odds"))
    if odds is None or odds <= 1.0:
        return "invalid combined odds"
    at = _ts(q.get("quoted_at"))
    if at is None or at > now:
        return "quote has no valid time"
    if (now - at).total_seconds() > MAX_QUOTE_AGE_MINUTES * 60:
        return "quote is stale"
    return None


def card_view(rec: dict, stake=DEFAULT_STAKE) -> dict:
    """Display values for a card that passed `card_problem`: odds and gross payout at the stake."""
    odds = rec["quote"]["decimal_odds"]
    return {"parlay_id": rec["parlay_id"], "bookmaker": rec["bookmaker"], "decimal_odds": odds, "stake": stake,
            "gross_payout": str(gross_payout(stake, odds)), "net_profit": str(net_profit(stake, odds)),
            "legs": [{"title": leg["title"], "selection": leg["selection"], "start_utc": leg["start_utc"]}
                     for leg in rec["legs"]]}


def shown_cards(block: dict | None, now: datetime) -> list[dict]:
    """The recommendations the homepage may show: nothing while any blocker is open or the block is
    not published, otherwise every valid card for today, earliest first, at most CARD_MAX_CARDS."""
    if not isinstance(block, dict) or block.get("status") != "published" or block.get("blockers") != []:
        return []
    day = now.astimezone(ZoneInfo(CARD_TIMEZONE)).date().isoformat()
    if block.get("date") != day:
        return []
    ok = [r for r in block.get("recommendations") or [] if card_problem(r, now, day) is None]
    ok.sort(key=lambda r: (min(_ts(leg["start_utc"]) for leg in r["legs"]), r["parlay_id"]))
    return ok[:CARD_MAX_CARDS]
