"""Estimated parlays of the day (issue #47). Owner-approved, clearly labelled ESTIMATES.

Doyen is a small personal, non-commercial, paper-trading project. The owner approved an
estimated-parlay mode that runs alongside the strict path (`sbi.parlays`, issues #27/#33/#34),
which is unchanged. Strict mode wins: a parlay with a verified bookmaker combined quote is shown
as such, and an estimate never reuses one of its games.

What an estimated parlay is (rules loosened by the owner in issue #51, estimated mode only)
- 2-6 legs searched (cards show 2-5 since #54) from today's (America/New_York) games in Soccer, NFL, NBA or Tennis that have not
  started, at most one leg per game. Different games in one competition are allowed in this mode;
  same-game combinations are not, and neither are legs that share a team or player.
- ONE bookmaker that has priced every leg. Each leg uses that bookmaker's latest stored price,
  retrieved on the same New York day and before the game starts (#51 replaced the 150-minute
  limit). A leg drops out as soon as its game starts. Exchanges are excluded (no accumulator slip).
- Estimated price = the product of that bookmaker's own single-leg prices. It is NOT a bet-slip
  quote and is never labelled `bookmaker_combined` (`ESTIMATE_KIND` below); the slip may pay less.
- Leg probability = Doyen's stored model probability where one exists (Soccer, NFL, NBA). Where
  there is none (Tennis) it is a de-vigged market consensus: the other bookmakers' consensus when
  one exists, otherwise the consensus of at least 2 independent bookmakers including the pricing
  one. A leg with neither is skipped. One bookmaker is enough to price a leg (#51).
- Value is checked for the WHOLE parlay (#51): joint probability x estimated price > 1. A single
  leg may sit below Doyen's probability only as part of a positive-value pair; every further leg
  must not lower the parlay's estimated value (probability x price >= 1). Legs are never forced.
- Kept screens: consensus probability inside the research band of `sbi.parlay_engine`
  (0.30-0.85), the stored model within 0.12 of the market (data sanity). No single-pick threshold
  is read or changed here.
- Open injury/lineup research notes (owner decision, issue #68): no longer a screen. A leg whose
  game has an open `injury` or `lineup` note is kept, and the card shows a small muted line on that
  leg ("Injury/lineup note open", plus the note's short text) so the owner can judge. Shown, never
  used to filter. The strict/shadow screen `parlay_engine.screen_event` is unchanged.
- At most ONE leg per parlay may be "weak", i.e. below its own probability bar (probability x
  price < 1 at the pricing bookmaker); the parlay as a whole must still have positive value (#54).
- Ranking: score = estimated joint probability (product of leg probabilities, independence
  assumed, unvalidated) x estimated value (joint x estimated price - 1). Cards are picked per size
  (#54): the best 4-5 leg, 3-leg and 2-leg parlay, then a second of each, each game used at most
  once across cards, at most `parlays.CARD_MAX_CARDS`. A size with nothing qualifying is skipped.

Every shown estimate is appended to `ledger/estimated_parlays.csv` (never edited) and settled
read-only from final scores, so a hit rate and paper P/L at the $10 display stake build up.
No network request is made and no API credit is spent.

Previews (issue #58): each run also builds parlays for each of the next `PREVIEW_DAYS` New York
dates with the same rules, except the price rule: the bookmaker's latest stored price at the time
of the run, retrieved before the game starts (the same-day rule applies to today only). Previews
carry `preview: true` and `PREVIEW_BADGE`, are replaced on every run, and are never written to the
ledger or counted in the record; on its own day a date is rebuilt and recorded as today's parlays.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from itertools import permutations
from math import prod

from zoneinfo import ZoneInfo

from . import config, parlay_engine, parlays
from . import ev as evm
from .sources.books import normalize_book
from .sources.football_data import AGGREGATES, EXCHANGES

METHOD = "parlay-estimated-v2"
ESTIMATE_KIND = "estimated_product"          # never parlays.QUOTE_KIND ("bookmaker_combined")
BADGE = "Estimate"
VERIFIED_BADGE = "Verified bookmaker quote"
PRICE_RULE = "latest price from that bookmaker, retrieved on the same New York day and before the game starts"
MIN_PRICING_BOOKS = 1                        # the bookmaker pricing the parlay (#51)
MIN_CONSENSUS_BOOKS = 2                      # independent bookmakers, pricing one included, when no model (#51)
NY = ZoneInfo(parlays.CARD_TIMEZONE)
MIN_LEGS, MAX_LEGS = parlays.MIN_LEGS, parlays.MAX_LEGS
MAX_CARDS = parlays.CARD_MAX_CARDS
SIZE_BUCKETS = ((2, 2), (3, 3), (4, 5))      # cards are picked per size (issue #54)
PER_SIZE = 2                                 # at most this many cards of one size, within MAX_CARDS
MAX_WEAK_LEGS = 1                            # legs below their own probability bar per parlay (issue #54)
WEAK_TOLERANCE = 0.0005                      # card contract: rounding slack on the stored leg probability
DEFAULT_STAKE = parlays.DEFAULT_STAKE
BEAM = 120                                   # combinations kept per size per bookmaker
MAX_EVALUATIONS = 200_000                    # hard stop for the whole search
EMPTY_TEXT = "No parlays today: no verified quotes, and no games later today meet the estimate rules."
PREVIEW_DAYS = 3                             # next New York dates previewed (issue #58)
PREVIEW_BADGE = "Preview: may change at the next daily update"
PREVIEW_EMPTY_TEXT = "No preview yet for this day"
PREVIEW_PRICE_RULE = "latest stored price from that bookmaker at the time of the run, retrieved before the game starts"
RISK_NOTE_LABEL = "Injury/lineup note open"
RISK_NOTE_MAX_CHARS = 120                    # short text of one note shown on the leg (issue #68)
DISCLOSURE = ("Estimates for paper trading in a personal research project, never a guarantee. Parlays win less "
              "often than single picks, and every leg has to win.")


def price_label(bookmaker: str) -> str:
    return (f"Estimated price: product of {bookmaker}'s single-game odds, not a bet-slip quote. "
            "Your slip may pay less.")


# ---------- inputs (read-only) ----------
def _ny_day(t: datetime) -> str:
    return t.astimezone(NY).date().isoformat()


def fresh_books(con, event_id: str, now: datetime, start: datetime | None = None, same_day: bool = True) -> dict:
    """Latest pre-match quote per (bookmaker, market, selection, line) retrieved at or before `now`,
    kept only if it was retrieved before the game's start and, unless `same_day` is False (issue
    #58 previews), on the same New York day as `now`."""
    from .engine import books_from_rows
    rows = con.execute("""SELECT market, line, bookmaker, selection, price, retrieved_at FROM odds
                          WHERE event_id=? AND kind='pre'""", (event_id,)).fetchall()
    day, latest = _ny_day(now), {}
    for r in rows:
        bk = normalize_book(r["bookmaker"])
        t = parlays._ts(r["retrieved_at"])
        if not bk or t is None or t > now or (same_day and _ny_day(t) != day) or (start is not None and t >= start):
            continue
        key = (bk, r["market"], r["selection"], -999 if r["line"] is None else r["line"])
        if key not in latest or t > latest[key]["t"]:
            latest[key] = {"bk": bk, "t": t, **dict(r)}
    return books_from_rows([(v["market"], v["line"], v["bk"], v["selection"], v["price"]) for v in latest.values()])


def risk_note_texts(con, event_id: str) -> list[str]:
    """Claims of the event's open `injury`/`lineup` research notes (issue #68), oldest first.
    Information only: shown on the leg, never used to exclude it."""
    cats = parlay_engine.RISK_CATEGORIES
    q = ",".join("?" * len(cats))
    return [str(r[0] or "").strip() for r in con.execute(
        f"SELECT claim FROM research_notes WHERE event_id=? AND category IN ({q}) ORDER BY created_at, id",
        (event_id, *cats))]


def risk_note_line(notes: list[str] | None) -> str | None:
    """The muted leg line for open injury/lineup notes, or None when there are none."""
    if not notes:
        return None
    text = next((n for n in notes if n), "")
    if len(text) > RISK_NOTE_MAX_CHARS:
        text = text[:RISK_NOTE_MAX_CHARS - 1].rstrip() + "…"
    more = f" (+{len(notes) - 1} more)" if len(notes) > 1 else ""
    return f"{RISK_NOTE_LABEL}: {text}{more}" if text else f"{RISK_NOTE_LABEL}{more}"


def screen_event(event: dict, books: dict, model: dict | None = None,
                 notes: list[str] | None = None) -> tuple[list[dict], str | None]:
    """Estimated-mode leg screen (#51). The strict/shadow screen `parlay_engine.screen_event` is
    unchanged. Per selection and per pricing bookmaker: price, probability used and its source.
    `notes` are the game's open injury/lineup note texts: carried on the leg, never a reason to
    exclude it (owner decision, issue #68)."""
    sport = event.get("site_sport")
    if sport not in parlay_engine.RESULT_MARKET:
        return [], "unsupported sport"
    market = parlay_engine.RESULT_MARKET[sport]
    sels = parlay_engine.SELECTIONS[market]
    book = evm.clean(books.get((market, None)) or {}, sels)
    book = {bk: q for bk, q in book.items() if bk not in AGGREGATES or bk == "Avg"}
    if not book:
        return [], "no fresh result-market prices"
    pricing = sorted(bk for bk in book if bk not in AGGREGATES and bk not in EXCHANGES)
    if len(pricing) < MIN_PRICING_BOOKS:
        return [], "no bookmaker that offers a parlay slip"
    ref, ref_src = evm.consensus(book, sels)          # market reference for the band and sanity screens
    if not ref:
        return [], "no market reference"
    consensus_ok = evm.n_books(book, sels) >= MIN_CONSENSUS_BOOKS and not str(ref_src).startswith("single:")
    legs, reasons = [], Counter()
    for s in sels:
        q = float(ref[s])
        if not parlay_engine.MIN_LEG_PROB <= q <= parlay_engine.MAX_LEG_PROB:
            reasons["probability outside research band"] += 1
            continue
        mp = (model or {}).get((market, s))
        if mp is not None and abs(float(mp) - q) > parlay_engine.MAX_MODEL_DISAGREEMENT:
            reasons["model and market disagree strongly"] += 1
            continue
        per = {}
        for bk in pricing:
            if mp is not None:
                p, src = float(mp), "model"
            else:
                ex, ex_src = evm.consensus_excluding(book, sels, bk)
                if ex and not str(ex_src or "").startswith("single:"):
                    p, src = float(ex[s]), "market_consensus_ex_book"
                elif consensus_ok:
                    p, src = q, "market_consensus_incl_book"
                else:
                    continue
            price = float(book[bk][s])
            per[bk] = {"price": price, "prob": p, "value": p * price - 1.0, "prob_source": src}
        if not per:
            reasons["no model probability and no 2-bookmaker consensus"] += 1
            continue
        legs.append({"event_id": event["event_id"], "sport": sport, "league": event["league"],
                     "competition": event.get("competition") or event["league"],
                     "participants": [event["home"], event["away"]], "start_utc": event["kickoff_utc"],
                     "title": f"{event['home']} v {event['away']}", "market": market, "selection": s,
                     "consensus_prob": round(q, 6), "model_prob": None if mp is None else round(float(mp), 6),
                     "prob_source": "model" if mp is not None else next(iter(per.values()))["prob_source"],
                     "books": per, "best_value": max(v["value"] for v in per.values()),
                     "risk_note": risk_note_line(notes)})
    if not legs:
        return [], (reasons.most_common(1)[0][0] if reasons else "no selection passed")
    return legs, None


def legs_for_event(event: dict, books: dict, model: dict | None,
                   notes: list[str] | None = None) -> tuple[dict | None, str | None]:
    """The single best leg for one game (or None, reason): the selection with the highest value at
    any pricing bookmaker. The value may be negative here; the parlay-level check is in `search`."""
    legs, why = screen_event(event, books, model, notes)
    if why:
        return None, why
    return max(legs, key=lambda x: (x["best_value"], x["selection"])), None


def build_pool(con, now: datetime, day: str | None = None) -> tuple[list[dict], dict]:
    """Leg pool for today, or for the later New York date `day` (a preview, issue #58)."""
    preview = day is not None and day != parlay_engine._day(now)
    events = parlay_engine.todays_events(con, now, day)
    excluded, pool, fresh = Counter(), [], 0
    by_sport: dict[str, dict[str, int]] = {}
    for e in events:
        if e["site_sport"] is None:
            excluded["unsupported sport"] += 1
            continue
        books = fresh_books(con, e["event_id"], now, parlays._ts(e["kickoff_utc"]), same_day=not preview)
        sp = by_sport.setdefault(e["site_sport"], {"events": 0, "with_prices": 0})
        sp["events"] += 1
        if books:
            fresh += 1
            sp["with_prices"] += 1
        leg, why = legs_for_event(e, books, parlay_engine.model_probs(con, e["event_id"], now),
                                  risk_note_texts(con, e["event_id"]))
        if why:
            excluded[why] += 1
            continue
        leg["price_ts"] = _price_times(con, e["event_id"], leg, now)
        pool.append(leg)
    pool.sort(key=lambda x: (-x["best_value"], x["event_id"]))
    cov = {"events_today": len(events), "events_with_fresh_prices": fresh, "legs": len(pool),
           "excluded": dict(sorted(excluded.items()))}
    if preview:                       # issue #61: which sports on a preview day have prices
        cov["by_sport"] = dict(sorted(by_sport.items()))
    return pool, cov


def _price_times(con, event_id: str, leg: dict, now: datetime) -> dict:
    """Retrieval time of each bookmaker's price used for the leg (latest at or before now)."""
    out = {}
    for r in con.execute("""SELECT bookmaker, retrieved_at FROM odds WHERE event_id=? AND kind='pre' AND market=?
                            AND selection=? AND line IS NULL""", (event_id, leg["market"], leg["selection"])):
        bk = normalize_book(r["bookmaker"])
        t = parlays._ts(r["retrieved_at"])
        if bk in leg["books"] and t is not None and t <= now and (bk not in out or t > out[bk][0]):
            out[bk] = (t, r["retrieved_at"])
    return {bk: v for bk, (t, v) in out.items()}


# ---------- search and selection (pure) ----------
def linked(a: dict, b: dict) -> list[str]:
    """Estimated mode: same game or a shared team/player blocks a pair; same competition does not."""
    return [r for r in parlays.correlation_reasons(a, b) if r != "same competition"]


def score(joint: float, ev: float) -> float:
    return joint * ev


def combo(legs: list[dict], bk: str) -> dict:
    odds = prod(x["books"][bk]["price"] for x in legs)
    joint = prod(x["books"][bk]["prob"] for x in legs)
    ev = joint * odds - 1.0
    return {"bookmaker": bk, "legs": legs, "n_legs": len(legs), "estimated_odds": odds, "joint_prob": joint,
            "estimated_ev": ev, "score": score(joint, ev)}


def adds_no_loss(leg: dict, bk: str) -> bool:
    """A leg does not lower a parlay's estimated value at `bk` when probability x price >= 1."""
    return leg["books"][bk]["prob"] * leg["books"][bk]["price"] >= 1.0


def search(pool: list[dict], beam: int = BEAM, max_evals: int = MAX_EVALUATIONS) -> list[dict]:
    """Per bookmaker, 2..6-leg combinations with positive estimated value (beam search on score).
    A parlay starts from a pair with joint probability x estimated price > 1, and every further leg
    must not lower that value (probability x price >= 1). So at most one leg sits below Doyen's
    probability, and only if it forms a positive-value pair with the parlay's strongest leg. Legs
    are tried in order of value at the bookmaker, which makes that weak leg the last one tried."""
    by_book = defaultdict(list)
    for i, leg in enumerate(pool):
        for bk in leg["books"]:
            by_book[bk].append(i)
    out, evals = [], 0
    for bk in sorted(by_book):
        idx = sorted(by_book[bk], key=lambda i: (-pool[i]["books"][bk]["value"], i))
        pos = {i: n for n, i in enumerate(idx)}
        frontier = [(i,) for i in idx]
        for n in range(MIN_LEGS, MAX_LEGS + 1):
            nxt = {}
            for c in frontier:
                for j in idx[pos[c[-1]] + 1:]:
                    if evals >= max_evals:
                        break
                    evals += 1
                    if any(linked(pool[j], pool[k]) for k in c):
                        continue
                    if n > MIN_LEGS and not adds_no_loss(pool[j], bk) and (
                            not all(adds_no_loss(pool[k], bk) for k in c)
                            or combo([pool[c[0]], pool[j]], bk)["estimated_ev"] <= 0):
                        continue
                    new = c + (j,)
                    cand = combo([pool[k] for k in new], bk)
                    if cand["estimated_ev"] > 0:
                        nxt[new] = cand
            ranked = sorted(nxt.items(), key=lambda kv: (-kv[1]["score"], sorted(kv[0])))[:beam]
            out += [c for _, c in ranked]
            frontier = [k for k, _ in ranked]
            if not frontier:
                break
    return out


def parlay_id(c: dict, day: str) -> str:
    key = json.dumps([day, c["bookmaker"], sorted(f"{x['event_id']}|{x['market']}|{x['selection']}" for x in c["legs"])])
    return "pe-" + hashlib.sha1(key.encode()).hexdigest()[:12]


def weak_legs(c: dict) -> int:
    """Legs priced below their own probability bar at the card's bookmaker (probability x price < 1)."""
    bk = c["bookmaker"]
    return sum(1 for x in c["legs"] if x["books"][bk]["prob"] * x["books"][bk]["price"] < 1.0)


def size_bucket(n_legs: int) -> str | None:
    """The size bucket a parlay belongs to (issue #54): "2", "3" or "4-5"; 6 legs is in none."""
    for lo, hi in SIZE_BUCKETS:
        if lo <= n_legs <= hi:
            return str(lo) if lo == hi else f"{lo}-{hi}"
    return None


def select(cands: list[dict], limit: int = MAX_CARDS, blocked_events: set | None = None,
           per_size: int | None = None) -> list[dict]:
    """Cards per size (issue #54): the best 4-5 leg, the best 3-leg and the best 2-leg parlay, then a
    second of each while `per_size` and `limit` allow. In the first round the sizes pick games in
    the order that covers the most sizes (bigger sizes first on a tie). Within a size, best score first (ties: fewer legs). A size with no qualifying combo is
    skipped, never padded. Every card has positive estimated value and at most one weak leg; a game
    appears in at most one card; games in a verified-quote card are skipped (strict mode wins).
    Returned earliest kickoff first."""
    per_size = PER_SIZE if per_size is None else per_size
    order = lambda c: (-c["score"], c["n_legs"], c["bookmaker"], sorted(x["event_id"] for x in c["legs"]))
    buckets = defaultdict(list)
    for c in cands:
        b = size_bucket(c["n_legs"])
        if b is not None and c["estimated_ev"] > 0 and weak_legs(c) <= MAX_WEAK_LEGS:
            buckets[b].append(c)
    for b in buckets:
        buckets[b].sort(key=order)
    names = [size_bucket(lo) for lo, _ in reversed(SIZE_BUCKETS)]     # bigger sizes first

    def take(order: list[str], used: set, out: list, taken: set) -> None:
        for b in order:
            if len(out) >= limit:
                return
            for c in buckets.get(b, []):
                evs = {x["event_id"] for x in c["legs"]}
                if id(c) in taken or evs & used:
                    continue
                used |= evs
                out.append(c)
                taken.add(id(c))
                break

    # Round 1: one card per size. A game can be in one card only, so the order in which sizes pick
    # matters on a thin day; every order is tried and the one covering the most sizes wins (ties:
    # bigger sizes covered, then the higher total score, then bigger sizes picking first).
    best = None
    for order in permutations(names):
        used, out, taken = set(blocked_events or ()), [], set()
        take(list(order), used, out, taken)
        got = {size_bucket(c["n_legs"]) for c in out}
        key = (len(got), tuple(b in got for b in names), sum(c["score"] for c in out),
               tuple(-names.index(b) for b in order))
        if best is None or key > best[0]:
            best = (key, used, out, taken)
    _, used, out, taken = best
    for _ in range(per_size - 1):                                      # later rounds: bigger first
        take(names, used, out, taken)
    out.sort(key=lambda c: (min(x["start_utc"] for x in c["legs"]), c["bookmaker"]))
    return out


def card(c: dict, day: str, preview: bool = False) -> dict:
    bk = c["bookmaker"]
    legs = sorted(c["legs"], key=lambda x: (x["start_utc"], x["event_id"]))
    odds = round(prod(x["books"][bk]["price"] for x in legs), 4)
    times = [x["price_ts"][bk] for x in legs if bk in x.get("price_ts", {})]
    out = {"parlay_id": parlay_id(c, day), "date": day, "status": "active", "kind": ESTIMATE_KIND, "badge": BADGE,
            "bookmaker": bk, "n_legs": len(legs), "estimated_odds": odds,
            "price_label": price_label(bk), "prices_at": min(times) if len(times) == len(legs) else None,
            "stake": DEFAULT_STAKE, "gross_payout": str(parlays.gross_payout(DEFAULT_STAKE, odds)),
            "est_hit_chance": round(c["joint_prob"], 4), "est_hit_chance_label": "Model estimate, unvalidated",
            "estimated_ev": round(c["estimated_ev"], 4), "size": size_bucket(len(legs)),
            "weak_legs": weak_legs(c),
            "legs": [{"event_id": x["event_id"], "sport": x["sport"], "league": x["league"], "title": x["title"],
                      "market": x["market"], "selection": x["selection"], "selection_text": selection_text(x),
                      "start_utc": x["start_utc"], "status": "active", "price": x["books"][bk]["price"],
                      "prob": round(x["books"][bk]["prob"], 4),
                      "prob_source": x["books"][bk].get("prob_source", x["prob_source"]),
                      "price_at": x.get("price_ts", {}).get(bk),
                      "risk_note": x.get("risk_note")} for x in legs]}
    if preview:
        out.update(preview=True, preview_badge=PREVIEW_BADGE)
    return out


def selection_text(leg: dict) -> str:
    home, away = leg["participants"]
    return {"H": f"{home} to win", "A": f"{away} to win", "D": "Draw",
            "home": f"{home} to win", "away": f"{away} to win"}.get(leg["selection"], str(leg["selection"]))


# ---------- card contract (mirrored in docs/assets/doyen.js estProblem) ----------
def card_problem(rec, now: datetime, day: str | None = None, preview: bool = False) -> str | None:
    """Why an estimated card must NOT be shown. None = it may be shown. Unknown data is rejected.
    With `preview` (issue #58) `day` is a later New York date: the card must be marked as a preview
    and its prices need only be read before each game starts (not on the same New York day)."""
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(parlays.CARD_TIMEZONE)
    day = day or now.astimezone(tz).date().isoformat()
    if not isinstance(rec, dict):
        return "not an object"
    if rec.get("mock") or rec.get("test"):
        return "mock or test data"
    if rec.get("kind") != ESTIMATE_KIND:
        return "not an estimate"
    if not isinstance(rec.get("parlay_id"), str) or not rec["parlay_id"].strip():
        return "missing parlay_id"
    if bool(rec.get("preview")) != preview:
        return "preview flag does not match the day"
    if rec.get("date") != day:
        return "not today's parlay" if not preview else "not this day's preview"
    if rec.get("status") != "active":
        return "parlay is not active"
    bk = rec.get("bookmaker")
    if not isinstance(bk, str) or not bk.strip():
        return "missing bookmaker"
    legs = rec.get("legs")
    if not isinstance(legs, list) or not MIN_LEGS <= len(legs) <= MAX_LEGS:
        return f"needs {MIN_LEGS}-{MAX_LEGS} legs"
    seen, prices, weak = set(), [], 0
    for leg in legs:
        if not isinstance(leg, dict):
            return "leg is not an object"
        for k in ("event_id", "title", "selection"):
            if not isinstance(leg.get(k), str) or not leg[k].strip():
                return f"leg missing {k}"
        if leg["event_id"] in seen:
            return "two legs on the same event"
        seen.add(leg["event_id"])
        if leg.get("sport") not in parlays.CARD_SPORTS:
            return "unsupported sport"
        if leg.get("status") != "active":
            return "leg is not active"
        start = parlays._ts(leg.get("start_utc"))
        if start is None:
            return "leg has no valid start time"
        if start.astimezone(tz).date().isoformat() != day:
            return "leg is not on today's date" if not preview else "leg is not on the preview's date"
        if start <= now:
            return "leg has started"
        p = parlays._num(leg.get("price"))
        if p is None or p <= 1.0:
            return "leg has no valid price"
        at = parlays._ts(leg.get("price_at"))
        if at is None or at > now:
            return "leg price has no valid time"
        if not preview and at.astimezone(tz).date().isoformat() != day:
            return "leg price is stale"           # not retrieved today (New York); start > now >= at
        if at >= start:
            return "leg price read after the start"
        q = parlays._num(leg.get("prob"))
        if q is not None and q * p < 1.0 - WEAK_TOLERANCE * p:
            weak += 1
        prices.append(p)
    if weak > MAX_WEAK_LEGS:
        return "more than one leg below its probability"
    odds = parlays._num(rec.get("estimated_odds"))
    if odds is None or odds <= 1.0:
        return "invalid estimated odds"
    if abs(odds - prod(prices)) > 0.005 * odds:
        return "estimated odds are not the product of the leg prices"
    return None


def shown(block: dict | None, now: datetime, blocked_events: set | None = None, limit: int = MAX_CARDS) -> list[dict]:
    """Estimated cards the homepage may show, earliest first, skipping games in verified cards."""
    if not isinstance(block, dict) or block.get("status") != "estimated":
        return []
    from zoneinfo import ZoneInfo
    day = now.astimezone(ZoneInfo(parlays.CARD_TIMEZONE)).date().isoformat()
    if block.get("date") != day:
        return []
    used, out = set(blocked_events or ()), []
    ok = [r for r in block.get("recommendations") or [] if card_problem(r, now, day) is None]
    ok.sort(key=lambda r: (min(parlays._ts(x["start_utc"]) for x in r["legs"]), r["parlay_id"]))
    for r in ok:
        evs = {x["event_id"] for x in r["legs"]}
        if evs & used:
            continue
        used |= evs
        out.append(r)
    return out[:limit]


# ---------- orchestration ----------
def build(con, now: datetime, verified_cards: list[dict] | None = None,
          recorded_today: list[dict] | None = None) -> dict:
    """Today's estimated parlays. `recorded_today` (issue #63) are the ledger rows already recorded
    for today's New York date, e.g. by the morning run: they are never rebuilt or repriced here.
    New cards may only use games outside them (so a recorded card can't come back at a new price
    under the same parlay_id) and only fill what is left of the day's `MAX_CARDS` cap, so a second
    run a day adds parlays from games that have not started without raising the daily volume."""
    day = parlay_engine._day(now)
    blocked = {leg.get("event_id") for c in verified_cards or [] for leg in c.get("legs", [])}
    recorded = [r for r in recorded_today or [] if r.get("date") == day]
    blocked |= {leg.get("event_id") for r in recorded for leg in r.get("legs", [])}
    limit = max(0, MAX_CARDS - len(verified_cards or []) - len({r.get("parlay_id") for r in recorded}))
    pool, cov = build_pool(con, now)
    cands = search(pool)
    picked = [card(c, day) for c in select(cands, limit, blocked)] if limit else []
    recs = [r for r in picked if card_problem(r, now, day) is None]
    return {"status": "estimated", "method": METHOD, "kind": ESTIMATE_KIND, "date": day,
            "timezone": parlays.CARD_TIMEZONE, "generated": now.isoformat(), "badge": BADGE,
            "verified_badge": VERIFIED_BADGE, "empty_text": EMPTY_TEXT, "disclosure": DISCLOSURE,
            "price_rule": PRICE_RULE, "default_stake": DEFAULT_STAKE,
            "coverage": {**cov, "combinations_kept": len(cands)}, "recorded_earlier_today": len(recorded),
            "recommendations": recs}


def preview_days(now: datetime, n: int = PREVIEW_DAYS) -> list[str]:
    """The next `n` New York dates after today."""
    today = date.fromisoformat(parlay_engine._day(now))
    return [(today + timedelta(days=k)).isoformat() for k in range(1, n + 1)]


def build_preview(con, now: datetime, day: str) -> dict:
    """Preview parlays for a later New York date (issue #58): same search and selection as today,
    prices from the latest stored quotes before each game starts. Never recorded in the ledger."""
    pool, cov = build_pool(con, now, day)
    cands = search(pool)
    picked = [card(c, day, preview=True) for c in select(cands, MAX_CARDS)]
    recs = [r for r in picked if card_problem(r, now, day, preview=True) is None]
    return {"status": "preview", "preview": True, "method": METHOD, "kind": ESTIMATE_KIND, "date": day,
            "timezone": parlays.CARD_TIMEZONE, "generated": now.isoformat(), "badge": BADGE,
            "preview_badge": PREVIEW_BADGE, "empty_text": PREVIEW_EMPTY_TEXT, "price_rule": PREVIEW_PRICE_RULE,
            "default_stake": DEFAULT_STAKE, "coverage": {**cov, "combinations_kept": len(cands)},
            "recommendations": recs}


def build_previews(con, now: datetime) -> list[dict]:
    out = []
    for day in preview_days(now):
        try:
            out.append(build_preview(con, now, day))
        except Exception as e:                # one bad day never hides the others; truthful empty state
            out.append({"status": "unavailable", "preview": True, "kind": ESTIMATE_KIND, "date": day,
                        "preview_badge": PREVIEW_BADGE, "empty_text": PREVIEW_EMPTY_TEXT,
                        "recommendations": [], "error": type(e).__name__})
    return out


# ---------- append-only ledger and read-only settlement ----------
LEDGER_FIELDS = ("first_seen", "date", "parlay_id", "bookmaker", "n_legs", "legs", "kind", "estimated_odds",
                 "est_hit_chance", "estimated_ev", "stake")


def ledger_path():
    return config.ROOT / "ledger" / "estimated_parlays.csv"


def record(block: dict, now: datetime, path=None) -> int:
    """Append every shown estimate not already recorded. Existing rows are never edited or removed;
    the first price shown for a parlay_id is the one that counts."""
    path = path or ledger_path()
    seen = set()
    if path.exists():
        with path.open(newline="") as f:
            seen = {r["parlay_id"] for r in csv.DictReader(f)}
    new = []
    for c in shown(block, now):
        if c["parlay_id"] in seen:
            continue
        seen.add(c["parlay_id"])
        legs = [{k: x[k] for k in ("event_id", "market", "selection", "price", "prob", "title", "start_utc")}
                for x in c["legs"]]
        new.append({"first_seen": now.isoformat(), "date": c["date"], "parlay_id": c["parlay_id"],
                    "bookmaker": c["bookmaker"], "n_legs": c["n_legs"], "legs": json.dumps(legs), "kind": ESTIMATE_KIND,
                    "estimated_odds": c["estimated_odds"], "est_hit_chance": c["est_hit_chance"],
                    "estimated_ev": c["estimated_ev"], "stake": c["stake"]})
    if new:
        path.parent.mkdir(parents=True, exist_ok=True)
        header = not path.exists()
        with path.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=LEDGER_FIELDS)
            if header:
                w.writeheader()
            w.writerows(new)
    return len(new)


def settle(con, path=None) -> dict:
    """Read-only settlement from final scores. Any lost leg loses the parlay; otherwise a void or
    postponed leg voids the whole row here (stake returned, 0 P/L: bookmaker void-leg rules differ
    and are not modelled); otherwise open until every leg is final. P/L at the recorded stake and
    the recorded estimated price, so a real slip may have paid less."""
    path = path or ledger_path()
    out = _tally()
    out["by_legs"] = {}
    if not path.exists():
        return out
    groups = defaultdict(_tally)
    with path.open(newline="") as f:
        for r in csv.DictReader(f):
            legs = json.loads(r["legs"])
            st, _ = _row_result(con, legs)
            n = str(r.get("n_legs") or "").strip() or str(len(legs))
            for t in (out, groups[n]):
                _add(t, st, r)
    for t in (out, *groups.values()):
        _finish(t)
    out["by_legs"] = {n: groups[n] for n in sorted(groups, key=lambda k: (not k.isdigit(), int(k) if k.isdigit() else 0, k))}
    return out


def _row_result(con, legs: list[dict]) -> tuple[str, list[str]]:
    """(parlay result, per-leg results) from final scores. Any lost leg loses; otherwise an open leg
    keeps it open; otherwise a void leg voids it; otherwise it won."""
    res = [parlay_engine._leg_result(con, x) for x in legs]
    st = "lost" if "lost" in res else ("open" if "open" in res else ("void" if "void" in res else "won"))
    return st, res


def _ledger_selection_text(leg: dict) -> str:
    parts = str(leg.get("title") or "").split(" v ", 1)
    home, away = (parts + [""])[:2] if len(parts) == 2 else ("", "")
    sel = str(leg.get("selection") or "")
    if sel in ("H", "home") and home:
        return f"{home} to win"
    if sel in ("A", "away") and away:
        return f"{away} to win"
    return "Draw" if sel == "D" else sel


def ledger_rows(con, path=None, day: str | None = None) -> list[dict]:
    """Every recorded estimate (issue #57), newest first, exactly as first published, with read-only
    results from final scores. `day` limits it to one New York date (the homepage's "today").
    Rows are never edited; result and paper P/L use the same rules and numbers as `settle`."""
    path = path or ledger_path()
    if not path.exists():
        return []
    out = []
    with path.open(newline="") as f:
        for i, r in enumerate(csv.DictReader(f)):
            if day is not None and r["date"] != day:
                continue
            legs = json.loads(r["legs"])
            st, res = _row_result(con, legs)
            stake = parlays._money(r["stake"])
            odds = r["estimated_odds"]
            pl = (parlays.net_profit(stake, r["estimated_odds"]) if st == "won"
                  else (-stake if st == "lost" else Decimal("0")))
            out.append({"parlay_id": r["parlay_id"], "date": r["date"], "first_seen": r["first_seen"],
                        "kind": r.get("kind") or ESTIMATE_KIND, "bookmaker": r["bookmaker"],
                        "n_legs": int(str(r.get("n_legs") or "").strip() or len(legs)),
                        "estimated_odds": float(odds), "stake": str(stake),
                        "gross_payout": str(parlays.gross_payout(stake, odds)),
                        "est_hit_chance": float(r["est_hit_chance"]) if r.get("est_hit_chance") else None,
                        "result": st, "paper_pl": str(parlays._money(pl)), "_order": i,
                        "legs": [{"event_id": x["event_id"], "title": x.get("title"), "market": x.get("market"),
                                  "selection": x.get("selection"), "selection_text": _ledger_selection_text(x),
                                  "price": x.get("price"), "start_utc": x.get("start_utc"), "result": lr}
                                 for x, lr in zip(legs, res)]})
    out.sort(key=lambda x: (x["date"], x["first_seen"], x["_order"]), reverse=True)
    for x in out:
        del x["_order"]
    return out


def _tally() -> dict:
    return {"rows": 0, "won": 0, "lost": 0, "void": 0, "open": 0, "paper_pl": Decimal("0"),
            "staked": Decimal("0"), "expected_wins_settled": 0.0}


def _add(t: dict, st: str, r: dict) -> None:
    t["rows"] += 1
    t[st] += 1
    stake = parlays._money(r["stake"])
    if st == "won":
        t["paper_pl"] += parlays.net_profit(stake, r["estimated_odds"])
        t["staked"] += stake
    elif st == "lost":
        t["paper_pl"] -= stake
        t["staked"] += stake
    if st in ("won", "lost"):
        t["expected_wins_settled"] += float(r["est_hit_chance"])


def _finish(t: dict) -> None:
    t["paper_pl"] = str(parlays._money(t["paper_pl"]))
    t["staked"] = str(parlays._money(t["staked"]))
    t["expected_wins_settled"] = round(t["expected_wins_settled"], 3)


def record_line(s: dict) -> str:
    pl = Decimal(s["paper_pl"])
    sign = "+" if pl > 0 else ("−" if pl < 0 else "")
    return f"Estimated parlays record: {s['won']}–{s['lost']}, paper P/L {sign}${abs(pl):.2f}"
