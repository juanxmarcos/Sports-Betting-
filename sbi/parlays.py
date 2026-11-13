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
from itertools import combinations
from math import prod
from zoneinfo import ZoneInfo

from . import config, odds_policy
from .sources.books import normalize_book
from .sources.football_data import AGGREGATES

METHOD = "parlay-stage0-audit"
MIN_LEGS, MAX_LEGS = 2, 3

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
