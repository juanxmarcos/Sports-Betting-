"""Estimated parlays of the day (issue #47). Owner-approved, clearly labelled ESTIMATES.

Doyen is a small personal, non-commercial, paper-trading project. The owner approved an
estimated-parlay mode that runs alongside the strict path (`sbi.parlays`, issues #27/#33/#34),
which is unchanged. Strict mode wins: a parlay with a verified bookmaker combined quote is shown
as such, and an estimate never reuses one of its games.

What an estimated parlay is
- 2-6 legs from today's (America/New_York) games in Soccer, NFL, NBA or Tennis that have not
  started, at most one leg per game. Different games in one competition are allowed in this mode;
  same-game combinations are not, and neither are legs that share a team or player.
- ONE bookmaker that has priced every leg, with each of its prices retrieved in the last
  `parlays.MAX_QUOTE_AGE_MINUTES` (150) minutes. Exchanges are excluded (no accumulator slip).
- Estimated price = the product of that bookmaker's own single-leg prices. It is NOT a bet-slip
  quote and is never labelled `bookmaker_combined` (`ESTIMATE_KIND` below); the slip may pay less.
- Leg probability = Doyen's stored model probability where one exists (Soccer, NFL, NBA), else the
  de-vigged consensus of the OTHER bookmakers (Tennis has no stored model probability). Each leg
  must add value at that bookmaker (probability x price > 1); legs are never added for payout.
- Candidate legs pass the existing research screens of `sbi.parlay_engine.screen_event` (enough
  independent bookmakers, a market consensus, a probability band, model/market agreement, no open
  injury/lineup note). No single-pick threshold is read or changed here.
- Ranking: score = estimated joint probability (product of leg probabilities, independence
  assumed, unvalidated) x estimated value (joint x estimated price - 1). The best cards are kept,
  each game used at most once across cards, at most `parlays.CARD_MAX_CARDS`; fewer is normal.

Every shown estimate is appended to `ledger/estimated_parlays.csv` (never edited) and settled
read-only from final scores, so a hit rate and paper P/L at the $10 display stake build up.
No network request is made and no API credit is spent.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from math import prod

from . import config, parlay_engine, parlays
from .sources.books import normalize_book

METHOD = "parlay-estimated-v1"
ESTIMATE_KIND = "estimated_product"          # never parlays.QUOTE_KIND ("bookmaker_combined")
BADGE = "Estimate"
VERIFIED_BADGE = "Verified bookmaker quote"
MAX_PRICE_AGE_MINUTES = parlays.MAX_QUOTE_AGE_MINUTES       # the 150-minute rule
MIN_LEGS, MAX_LEGS = parlays.MIN_LEGS, parlays.MAX_LEGS
MAX_CARDS = parlays.CARD_MAX_CARDS
DEFAULT_STAKE = parlays.DEFAULT_STAKE
BEAM = 120                                   # combinations kept per size per bookmaker
MAX_EVALUATIONS = 200_000                    # hard stop for the whole search
EMPTY_TEXT = "No parlays today: no verified quotes, and no games later today meet the estimate rules."
DISCLOSURE = ("Estimates for paper trading in a personal research project, never a guarantee. Parlays win less "
              "often than single picks, and every leg has to win.")


def price_label(bookmaker: str) -> str:
    return (f"Estimated price: product of {bookmaker}'s single-game odds, not a bet-slip quote. "
            "Your slip may pay less.")


# ---------- inputs (read-only) ----------
def fresh_books(con, event_id: str, now: datetime, max_age_minutes: int = MAX_PRICE_AGE_MINUTES) -> dict:
    """Latest pre-match quote per (bookmaker, market, selection, line), keeping only quotes whose own
    retrieval time is within `max_age_minutes` of `now` (and not in the future)."""
    from .engine import books_from_rows
    rows = con.execute("""SELECT market, line, bookmaker, selection, price, retrieved_at FROM odds
                          WHERE event_id=? AND kind='pre'""", (event_id,)).fetchall()
    latest: dict = {}
    for r in rows:
        bk = normalize_book(r["bookmaker"])
        if not bk:
            continue
        key = (bk, r["market"], r["selection"], -999 if r["line"] is None else r["line"])
        if key not in latest or r["retrieved_at"] > latest[key]["retrieved_at"]:
            latest[key] = {"bk": bk, **dict(r)}
    lo = now - timedelta(minutes=max_age_minutes)
    keep = []
    for v in latest.values():
        t = parlays._ts(v["retrieved_at"])
        if t is not None and lo <= t <= now:
            keep.append((v["market"], v["line"], v["bk"], v["selection"], v["price"]))
    return books_from_rows(keep)


def legs_for_event(event: dict, books: dict, model: dict | None, n_risk_notes: int = 0) -> tuple[dict | None, str | None]:
    """The single best leg for one game (or None, reason). Per bookmaker the leg carries its price,
    the probability used and the value at that bookmaker."""
    legs, why = parlay_engine.screen_event(event, books, model, n_risk_notes)
    if why:
        return None, why
    best = None
    for leg in legs:
        per = {}
        for bk, v in leg["books"].items():
            p = leg["model_prob"] if leg["model_prob"] is not None else v["fair_prob"]
            value = p * v["price"] - 1.0
            if value > 0:
                per[bk] = {"price": v["price"], "prob": float(p), "value": value}
        if not per:
            continue
        cand = {**{k: leg[k] for k in ("event_id", "sport", "league", "competition", "participants", "start_utc",
                                       "title", "market", "selection", "model_prob", "consensus_prob")},
                "prob_source": "model" if leg["model_prob"] is not None else "market_consensus_ex_book",
                "books": per, "best_value": max(x["value"] for x in per.values())}
        if best is None or cand["best_value"] > best["best_value"]:
            best = cand
    if best is None:
        return None, "no bookmaker price above Doyen's probability"
    return best, None


def build_pool(con, now: datetime) -> tuple[list[dict], dict]:
    events = parlay_engine.todays_events(con, now)
    excluded, pool = Counter(), []
    for e in events:
        if e["site_sport"] is None:
            excluded["unsupported sport"] += 1
            continue
        books = fresh_books(con, e["event_id"], now)
        leg, why = legs_for_event(e, books, parlay_engine.model_probs(con, e["event_id"], now),
                                  parlay_engine.risk_notes(con, e["event_id"]))
        if why:
            excluded[why] += 1
            continue
        leg["price_ts"] = _price_times(con, e["event_id"], leg, now)
        pool.append(leg)
    pool.sort(key=lambda x: (-x["best_value"], x["event_id"]))
    return pool, {"events_today": len(events), "legs": len(pool), "excluded": dict(sorted(excluded.items()))}


def _price_times(con, event_id: str, leg: dict, now: datetime) -> dict:
    """Retrieval time of each bookmaker's price used for the leg (latest at or before now)."""
    out = {}
    for r in con.execute("""SELECT bookmaker, retrieved_at FROM odds WHERE event_id=? AND kind='pre' AND market=?
                            AND selection=? AND line IS NULL""", (event_id, leg["market"], leg["selection"])):
        bk = normalize_book(r["bookmaker"])
        t = parlays._ts(r["retrieved_at"])
        if bk in leg["books"] and t is not None and t <= now and (bk not in out or r["retrieved_at"] > out[bk]):
            out[bk] = r["retrieved_at"]
    return out


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


def search(pool: list[dict], beam: int = BEAM, max_evals: int = MAX_EVALUATIONS) -> list[dict]:
    """Per bookmaker, 2..6-leg combinations of legs that each add value there (beam search on score)."""
    by_book = defaultdict(list)
    for i, leg in enumerate(pool):
        for bk in leg["books"]:
            by_book[bk].append(i)
    out, evals = [], 0
    for bk in sorted(by_book):
        idx = by_book[bk]
        frontier = [(i,) for i in idx]
        for _n in range(MIN_LEGS, MAX_LEGS + 1):
            nxt = {}
            for c in frontier:
                for j in idx:
                    if j <= c[-1] or evals >= max_evals:
                        continue
                    evals += 1
                    if any(linked(pool[j], pool[k]) for k in c):
                        continue
                    new = c + (j,)
                    cand = combo([pool[k] for k in new], bk)
                    if cand["estimated_ev"] > 0:
                        nxt[new] = cand
            ranked = sorted(nxt.items(), key=lambda kv: (-kv[1]["score"], kv[0]))[:beam]
            out += [c for _, c in ranked]
            frontier = [k for k, _ in ranked]
            if not frontier:
                break
    return out


def parlay_id(c: dict, day: str) -> str:
    key = json.dumps([day, c["bookmaker"], sorted(f"{x['event_id']}|{x['market']}|{x['selection']}" for x in c["legs"])])
    return "pe-" + hashlib.sha1(key.encode()).hexdigest()[:12]


def select(cands: list[dict], limit: int = MAX_CARDS, blocked_events: set | None = None) -> list[dict]:
    """Best score first (ties: fewer legs); a game appears in at most one card; games already in a
    verified-quote card are skipped (strict mode wins). Returned earliest kickoff first."""
    used, out = set(blocked_events or ()), []
    for c in sorted(cands, key=lambda c: (-c["score"], c["n_legs"], c["bookmaker"],
                                          sorted(x["event_id"] for x in c["legs"]))):
        evs = {x["event_id"] for x in c["legs"]}
        if evs & used:
            continue
        used |= evs
        out.append(c)
        if len(out) >= limit:
            break
    out.sort(key=lambda c: (min(x["start_utc"] for x in c["legs"]), c["bookmaker"]))
    return out


def card(c: dict, day: str) -> dict:
    bk = c["bookmaker"]
    legs = sorted(c["legs"], key=lambda x: (x["start_utc"], x["event_id"]))
    odds = round(prod(x["books"][bk]["price"] for x in legs), 4)
    times = [x["price_ts"][bk] for x in legs if bk in x.get("price_ts", {})]
    return {"parlay_id": parlay_id(c, day), "date": day, "status": "active", "kind": ESTIMATE_KIND, "badge": BADGE,
            "bookmaker": bk, "n_legs": len(legs), "estimated_odds": odds,
            "price_label": price_label(bk), "prices_at": min(times) if len(times) == len(legs) else None,
            "stake": DEFAULT_STAKE, "gross_payout": str(parlays.gross_payout(DEFAULT_STAKE, odds)),
            "est_hit_chance": round(c["joint_prob"], 4), "est_hit_chance_label": "Model estimate, unvalidated",
            "estimated_ev": round(c["estimated_ev"], 4),
            "legs": [{"event_id": x["event_id"], "sport": x["sport"], "league": x["league"], "title": x["title"],
                      "market": x["market"], "selection": x["selection"], "selection_text": selection_text(x),
                      "start_utc": x["start_utc"], "status": "active", "price": x["books"][bk]["price"],
                      "prob": round(x["books"][bk]["prob"], 4), "prob_source": x["prob_source"],
                      "price_at": x.get("price_ts", {}).get(bk)} for x in legs]}


def selection_text(leg: dict) -> str:
    home, away = leg["participants"]
    return {"H": f"{home} to win", "A": f"{away} to win", "D": "Draw",
            "home": f"{home} to win", "away": f"{away} to win"}.get(leg["selection"], str(leg["selection"]))


# ---------- card contract (mirrored in docs/assets/doyen.js estProblem) ----------
def card_problem(rec, now: datetime, day: str | None = None) -> str | None:
    """Why an estimated card must NOT be shown. None = it may be shown. Unknown data is rejected."""
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
    if rec.get("date") != day:
        return "not today's parlay"
    if rec.get("status") != "active":
        return "parlay is not active"
    bk = rec.get("bookmaker")
    if not isinstance(bk, str) or not bk.strip():
        return "missing bookmaker"
    legs = rec.get("legs")
    if not isinstance(legs, list) or not MIN_LEGS <= len(legs) <= MAX_LEGS:
        return f"needs {MIN_LEGS}-{MAX_LEGS} legs"
    seen, prices = set(), []
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
            return "leg is not on today's date"
        if start <= now:
            return "leg has started"
        p = parlays._num(leg.get("price"))
        if p is None or p <= 1.0:
            return "leg has no valid price"
        at = parlays._ts(leg.get("price_at"))
        if at is None or at > now:
            return "leg price has no valid time"
        if (now - at).total_seconds() > MAX_PRICE_AGE_MINUTES * 60:
            return "leg price is stale"
        prices.append(p)
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
def build(con, now: datetime, verified_cards: list[dict] | None = None) -> dict:
    day = parlay_engine._day(now)
    blocked = {leg.get("event_id") for c in verified_cards or [] for leg in c.get("legs", [])}
    pool, cov = build_pool(con, now)
    cands = search(pool)
    picked = [card(c, day) for c in select(cands, MAX_CARDS - len(verified_cards or []), blocked)]
    recs = [r for r in picked if card_problem(r, now, day) is None]
    return {"status": "estimated", "method": METHOD, "kind": ESTIMATE_KIND, "date": day,
            "timezone": parlays.CARD_TIMEZONE, "generated": now.isoformat(), "badge": BADGE,
            "verified_badge": VERIFIED_BADGE, "empty_text": EMPTY_TEXT, "disclosure": DISCLOSURE,
            "max_price_age_minutes": MAX_PRICE_AGE_MINUTES, "default_stake": DEFAULT_STAKE,
            "coverage": {**cov, "combinations_kept": len(cands)}, "recommendations": recs}


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
    out = {"rows": 0, "won": 0, "lost": 0, "void": 0, "open": 0, "paper_pl": "0.00", "staked": "0.00",
           "expected_wins_settled": 0.0}
    if not path.exists():
        return out
    pl, staked = Decimal("0"), Decimal("0")
    with path.open(newline="") as f:
        for r in csv.DictReader(f):
            out["rows"] += 1
            res = [parlay_engine._leg_result(con, x) for x in json.loads(r["legs"])]
            st = "lost" if "lost" in res else ("open" if "open" in res else ("void" if "void" in res else "won"))
            out[st] += 1
            stake = parlays._money(r["stake"])
            if st == "won":
                pl += parlays.net_profit(stake, r["estimated_odds"])
                staked += stake
            elif st == "lost":
                pl -= stake
                staked += stake
            if st in ("won", "lost"):
                out["expected_wins_settled"] += float(r["est_hit_chance"])
    out["paper_pl"] = str(parlays._money(pl))
    out["staked"] = str(parlays._money(staked))
    out["expected_wins_settled"] = round(out["expected_wins_settled"], 3)
    return out


def record_line(s: dict) -> str:
    pl = Decimal(s["paper_pl"])
    sign = "+" if pl > 0 else ("−" if pl < 0 else "")
    return f"Estimated parlays record: {s['won']}–{s['lost']}, paper P/L {sign}${abs(pl):.2f}"
