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

More bet types (issue #82, soccer step 1): besides the match result a soccer game can offer
Over/Under goals (x.5 lines in `OU_LINES`), Both Teams To Score, Double Chance and Draw No Bet legs,
each only where a stored bookmaker price exists (a price is never invented) and Doyen has a model
probability for it from the same Dixon-Coles score matrix: OU and BTTS as stored by the model run,
DC = sum of the covered 1X2 outcomes, DNB = P(win) / (1 - P(draw)). The best selection per market
and line is a candidate leg; still at most ONE leg per game, so markets never stack within a game.
A push leg (Draw No Bet on a draw) settles at odds 1.00 (removed from the parlay, the rest stands).

Typical price and likelihood ranking (owner decision, issue #112, 2026-11-23; supersedes the
single-bookmaker price, value check and weak-leg rule above for NEW parlays, `parlay-estimated-v4`):
- The owner bets at sportsbooks that are not in the free odds data, so a leg is priced at the TYPICAL
  market price: the median of the latest stored pre-match prices across bookmakers (exchanges and
  aggregate columns excluded; same freshness rules). At least 2 bookmakers must price the leg.
  Combined odds = the product of the typical leg prices. No bookmaker is named on a card.
- Leg probability = the #106 shrunk and capped probability (or the de-vigged consensus without a
  model). A leg is kept when the probability is in the research band (0.30-0.85), the model is not
  below the market by more than 0.02 (`MAX_MODEL_BELOW_MARKET`) and not 0.12 away from it.
- Parlays are ranked by joint probability, subject to minimum typical combined odds per size
  (`MIN_COMBINED_ODDS`: 2 legs 2.2, 3 legs 3.5, 4-5 legs 6.0). There is no value requirement: the
  typical price includes the bookmakers' margin, so estimated value is usually slightly negative.
  The goal is the win-loss record at typical odds, not value hunting.
- Legacy rows (`LEGACY_METHODS`) keep their bookmaker, price and probabilities; nothing is edited.

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

from . import config, parlay_engine, parlay_lines, parlays
from . import ev as evm
from .sources.books import normalize_book
from .sources.football_data import AGGREGATES, EXCHANGES

METHOD = "parlay-estimated-v5"            # v5: sensible parlays (owner, 2026-11-26): strong legs only, 2-3 legs, max 3
LEGACY_METHODS = ("parlay-estimated-v4", "parlay-estimated-v3")   # v4: typical price, joint probability (#112); v3: one bookmaker (#106)
ESTIMATE_KIND = "estimated_product"          # never parlays.QUOTE_KIND ("bookmaker_combined")
BADGE = "Estimate"
VERIFIED_BADGE = "Verified bookmaker quote"
PRICE_RULE = ("typical odds: the median of the bookmakers' latest prices (exchanges and aggregates excluded), "
              "each retrieved on the same New York day and before the game starts")
MIN_PRICING_BOOKS = 1                        # kept for the market-level screen message
MIN_CONSENSUS_BOOKS = 2                      # independent bookmakers for a de-vigged consensus (#51)
# Issue #112 (owner, 2026-11-23): "We don't want to compare sportsbooks since I will not be using any of
# those. I use Betano and Solcasino." Neither is in the free odds data, so a leg is priced at the TYPICAL
# market price (median across bookmakers), never at one bookmaker, and parlays are ranked by likelihood.
CONSENSUS = "consensus"                      # pseudo-bookmaker key of the typical price (never a sportsbook)
PRICE_BASIS = "consensus"
MIN_PRICE_BOOKS = 2                          # bookmakers that must price a leg for its typical price
MAX_MODEL_BELOW_MARKET = 0.02                # model must be >= de-vigged market - 0.02 where a model exists
# Owner decision 2026-11-26 ("good, sensible parlays, professionally studied; not the ones that pay the
# most"): every leg must be clearly likely by the whole market (de-vigged consensus >= 65%), Doyen's model
# must agree where it has one (not below the market by more than MAX_MODEL_BELOW_MARKET), and a leg must
# still pay something (typical price >= 1.15). Two or three legs, at most three parlays a day. The low
# minimum combined odds only stop a parlay of near-certainties that pays almost nothing.
MIN_LEG_MARKET_PROB = 0.65
MIN_LEG_PRICE = 1.15
MIN_COMBINED_ODDS = {"2": 1.6, "3": 1.9}      # minimum typical combined odds per size (v4: 2.2 / 3.5 / 6.0)
TYPICAL_ODDS_LABEL = "Typical odds"
TYPICAL_ODDS_NOTE = "Typical odds across sportsbooks; your sportsbook's price may differ slightly."
NY = ZoneInfo(parlays.CARD_TIMEZONE)
MIN_LEGS, MAX_LEGS = parlays.MIN_LEGS, parlays.MAX_LEGS
MAX_CARDS = 3                                # owner decision 2026-11-26 (was parlays.CARD_MAX_CARDS = 5)
SIZE_BUCKETS = ((2, 2), (3, 3))              # cards are picked per size (issue #54); 4-5 legs dropped 2026-11-26
PER_SIZE = 2                                 # at most this many cards of one size, within MAX_CARDS
MAX_WEAK_LEGS = 1                            # legs below their own probability bar per parlay (issue #54)
WEAK_TOLERANCE = 0.0005                      # card contract: rounding slack on the stored leg probability
DEFAULT_STAKE = parlays.DEFAULT_STAKE
BEAM = 120                                   # combinations kept per size (per ranking)
MAX_EVALUATIONS = 400_000                    # hard stop for the whole search
EMPTY_TEXT = "No parlays today: no verified quotes, and no games later today meet the estimate rules."
PREVIEW_DAYS = 3                             # next New York dates previewed (issue #58)
PREVIEW_BADGE = "Preview: may change at the next daily update"
PREVIEW_EMPTY_TEXT = "No preview yet for this day"
PREVIEW_PRICE_RULE = ("typical odds: the median of the bookmakers' latest stored prices at the time of the run, "
                      "each retrieved before the game starts")
RISK_NOTE_LABEL = "Injury/lineup note open"
RISK_NOTE_MAX_CHARS = 120                    # short text of one note shown on the leg (issue #68)
OU_LINES = (1.5, 2.5, 3.5)                   # soccer goal lines offered as legs (issue #82; half lines, no push)
EXTRA_MARKETS = {"OU": ["over", "under"], "BTTS": ["yes", "no"], "DC": ["HD", "DA", "HA"],
                 "DNB": ["home", "away"]}    # soccer markets beyond the match result (issue #82)
MARKET_LABELS = {"1X2": "Match result", "ML": "Moneyline", "OU": "Over/Under", "BTTS": "Both teams to score",
                 "DC": "Double chance", "DNB": "Draw no bet",
                 **{m: parlay_lines.market_label(m) for m in parlay_lines.MARKETS}}   # issue #83
# Issue #106 (owner, 2026-11-23): after 25 settled estimated parlays the record was 3-22 against about
# 7.3 expected wins; legs were too optimistic (Over/Under 5-11, Double Chance 1-3). The probability a
# NEW parlay uses for value and ranking is therefore shrunk toward the de-vigged market and capped.
# Evidence: `python -m sbi parlay-calibration` (data/backtest/parlay_calibration.json), docs/PARLAYS.md.
PROB_RULE = "parlay-leg-shrink-v1"
SHRINK_MARKETS = ("OU", "BTTS", "DC", "DNB")  # soccer score-matrix markets: blended with the market
SHRINK_MODEL_WEIGHT = 0.25                    # used = 0.25 x model + 0.75 x market consensus
MAX_OVER_MARKET = 0.05                        # every market: used probability <= market consensus + 0.05


def used_prob(market: str, raw: float, market_prob: float | None) -> float:
    """Issue #106: the leg probability a new parlay uses for value and ranking. Soccer Over/Under,
    BTTS, Double Chance and Draw No Bet blend the raw (model) probability with the de-vigged market
    consensus (`SHRINK_MODEL_WEIGHT` model). Every market is then capped at the consensus plus
    `MAX_OVER_MARKET`. A blended model below the market moves up toward it (that is shrinking, not
    optimism); no leg can sit more than `MAX_OVER_MARKET` above the market. Without a market
    reference the raw probability is returned (the screens never build a leg without one)."""
    p = float(raw)
    if market_prob is None:
        return p
    q = float(market_prob)
    if market in SHRINK_MARKETS:
        p = SHRINK_MODEL_WEIGHT * p + (1.0 - SHRINK_MODEL_WEIGHT) * q
    return min(p, q + MAX_OVER_MARKET)


DISCLOSURE = ("Estimates for paper trading in a personal research project, never a guarantee. Parlays win less "
              "often than single picks, and every leg has to win.")


def price_label(bookmaker: str | None = None) -> str:
    """Card price label. Issue #112: no bookmaker is named; the price is the typical market price."""
    return ("Typical combined odds: the product of each leg's typical odds (median across sportsbooks), "
            "not a bet-slip quote. " + TYPICAL_ODDS_NOTE)


def consensus_price(prices) -> float | None:
    """Issue #112: the typical price of one selection = the median of the bookmakers' prices."""
    xs = sorted(float(x) for x in prices if x is not None and float(x) > 1.0)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def consensus_entry(book: dict, pricing: list[str], s: str, prob: float, raw: float, src: str) -> dict | None:
    """The leg's single price entry {price, prob, ...} at the typical price, or None when fewer than
    `MIN_PRICE_BOOKS` bookmakers price the selection (issue #112)."""
    prices = {bk: float(book[bk][s]) for bk in pricing if book.get(bk, {}).get(s) and float(book[bk][s]) > 1.0}
    if len(prices) < MIN_PRICE_BOOKS:
        return None
    price = round(consensus_price(prices.values()), 4)
    return {"price": price, "prob": prob, "raw_prob": raw, "value": prob * price - 1.0, "prob_source": src,
            "n_books": len(prices), "book_prices": prices}


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


def model_probs_full(con, event_id: str, now: datetime) -> dict:
    """Issue #82: the event's latest recent model run as {(market, line, selection): probability},
    every stored market and line (1X2, OU by line, BTTS when priced), plus Double Chance and Draw No
    Bet derived from that run's 1X2 (exact sums of the same score matrix). The run is the one
    `parlay_engine.model_probs` uses; empty when Doyen stores none."""
    base = parlay_engine.model_probs(con, event_id, now)
    if not base:
        return {}
    row = con.execute("""SELECT run_id, MAX(created_at) c FROM predictions WHERE event_id=? AND line IS NULL
                         GROUP BY run_id ORDER BY c DESC LIMIT 1""", (event_id,)).fetchone()
    out = {(r["market"], None if r["line"] is None else float(r["line"]), r["selection"]): float(r["model_prob"])
           for r in con.execute("SELECT market, selection, line, model_prob FROM predictions WHERE run_id=? AND event_id=?",
                                (row["run_id"], event_id))}
    one = [out.get(("1X2", None, s)) for s in "HDA"]
    if all(x is not None for x in one):
        from .markets import dc_dnb_from_1x2
        for k, v in dc_dnb_from_1x2(*one).items():
            out.setdefault(k, v)
    return out


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
                 notes: list[str] | None = None, line_model: dict | None = None,
                 adjust: bool = True) -> tuple[list[dict], str | None]:
    """Estimated-mode leg screen (#51). The strict/shadow screen `parlay_engine.screen_event` is
    unchanged. Per selection and per pricing bookmaker: price, probability used and its source.
    `notes` are the game's open injury/lineup note texts: carried on the leg, never a reason to
    exclude it (owner decision, issue #68).
    Issue #83: NBA and NFL games also offer point-spread and game-total legs, one candidate per
    (market, line, selection) priced by the bookmaker. Their probability is the de-vigged market
    consensus unless the stored backtest shows the model beating the market (`parlay_lines.use_model`),
    in which case `line_model` {(market, selection, line): probability} supplies it.
    Issue #106: with `adjust` (parlays) the probability used is `used_prob`; `adjust=False` keeps the
    raw probability (the single picks, `singles-v2`, are unchanged)."""
    sport = event.get("site_sport")
    if sport not in parlay_engine.RESULT_MARKET:
        return [], "unsupported sport"
    market = parlay_engine.RESULT_MARKET[sport]
    groups = [(market, None, parlay_engine.SELECTIONS[market], model or {})]
    if sport in parlay_lines.SPORTS:
        lm = line_model or {}
        for mk in parlay_lines.MARKETS:
            use = parlay_lines.use_model(sport, mk)
            for ln in sorted(l for (m, l) in books if m == mk and l is not None):
                groups.append((mk, ln, parlay_lines.SELECTIONS[mk],
                               {(mk, s): lm.get((mk, s, ln)) for s in parlay_lines.SELECTIONS[mk]} if use else {}))
    legs, reasons, first_why = [], Counter(), None
    for mk, ln, sels, mp in groups:
        got, why = _screen_market(event, sport, books.get((mk, ln)) or {}, mk, ln, sels, mp, notes, adjust)
        legs += got
        if why and mk == market:
            first_why = why
        if isinstance(why, Counter):
            reasons.update(why)
    if not legs:
        if isinstance(first_why, str):
            return [], first_why
        return [], (reasons.most_common(1)[0][0] if reasons else "no selection passed")
    return legs, None


def _screen_market(event: dict, sport: str, raw_book: dict, market: str, line, sels: list[str],
                   model: dict, notes: list[str] | None, adjust: bool = True):
    """Legs for one (market, line) of one game: ([legs], None), ([], reason) for a market-level
    failure, or ([], Counter of per-selection reasons)."""
    book = evm.clean(raw_book, sels)
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
        if mp is not None and float(mp) < q - MAX_MODEL_BELOW_MARKET:      # issue #112
            reasons["model below the market"] += 1
            continue
        if mp is not None:
            p, src = float(mp), "model"
        elif consensus_ok:
            p, src = q, "market_consensus"
        else:
            reasons["no model probability and no 2-bookmaker consensus"] += 1
            continue
        used = used_prob(market, p, q) if adjust else p      # issue #106: capped at the market consensus + 0.05
        entry = consensus_entry(book, pricing, s, used, p, src)
        if entry is None:
            reasons["fewer than 2 bookmakers price this leg"] += 1
            continue
        per = {CONSENSUS: entry}
        leg = {"event_id": event["event_id"], "sport": sport, "league": event["league"],
               "competition": event.get("competition") or event["league"],
               "participants": [event["home"], event["away"]], "start_utc": event["kickoff_utc"],
               "title": f"{event['home']} v {event['away']}", "market": market, "line": None, "selection": s,
               "consensus_prob": round(q, 6), "model_prob": None if mp is None else round(float(mp), 6),
               "prob_source": src, "books": per, "best_value": entry["value"], "best_prob": used,
               "risk_note": risk_note_line(notes)}
        if line is not None:                          # issue #83: spread / total legs
            leg["line"] = float(line)
            leg["prob_note"] = None if mp is not None else parlay_lines.PROB_NOTE_MARKET
        legs.append(leg)
    if not legs:
        return [], reasons
    return legs, None


def _is_half_line(line) -> bool:
    return line is not None and abs((float(line) * 2) % 2 - 1) < 1e-9


def extra_market_legs(event: dict, books: dict, model: dict | None,
                      notes: list[str] | None = None, adjust: bool = True) -> tuple[list[dict], Counter]:
    """Issue #82: soccer Over/Under, BTTS, Double Chance and Draw No Bet legs. Each needs a stored
    price from a bookmaker that offers a parlay slip AND a Doyen model probability for the same
    market, line and selection (`model_probs_full`); no model, no leg. The kept screens are the same
    as for the match result: the market reference inside the research band and the model within
    `MAX_MODEL_DISAGREEMENT` of it. Market reference: de-vigged consensus of the market's own
    two-way prices (OU, BTTS, DNB); for Double Chance (three overlapping outcomes) the sum of the
    1X2 consensus probabilities. DNB falls back to P(H) / (P(H) + P(A)) of the 1X2 consensus."""
    reasons = Counter()
    if event.get("site_sport") != "soccer":
        return [], reasons
    one = evm.clean(books.get(("1X2", None)) or {}, parlay_engine.SELECTIONS["1X2"])
    one = {bk: q for bk, q in one.items() if bk not in AGGREGATES or bk == "Avg"}
    ref1, _ = evm.consensus(one, ["H", "D", "A"]) if one else (None, None)
    legs = []
    for (market, line), raw in sorted(books.items(), key=lambda kv: (kv[0][0], -999 if kv[0][1] is None else kv[0][1])):
        sels = EXTRA_MARKETS.get(market)
        if not sels:
            continue
        if market == "OU" and not (_is_half_line(line) and float(line) in OU_LINES):
            continue
        if market != "OU" and line is not None:
            continue
        if market == "DC":
            book = {bk: q for bk, q in raw.items() if all(float(q.get(s) or 0) > 1.0 for s in sels)}
            ref = ({"HD": ref1["H"] + ref1["D"], "DA": ref1["D"] + ref1["A"], "HA": ref1["H"] + ref1["A"]}
                   if ref1 else None)
        else:
            book = evm.clean(raw, sels)
            ref = evm.consensus(book, sels)[0] if book else None
            if not ref and market == "DNB" and ref1 and ref1["H"] + ref1["A"] > 0:
                ref = {"home": ref1["H"] / (ref1["H"] + ref1["A"]), "away": ref1["A"] / (ref1["H"] + ref1["A"])}
        pricing = sorted(bk for bk in book if bk not in AGGREGATES and bk not in EXCHANGES)
        if not pricing:
            reasons[f"{market}: no bookmaker price"] += 1
            continue
        if not ref:
            reasons[f"{market}: no market reference"] += 1
            continue
        key_line = None if line is None else float(line)
        for s in sels:
            q = float(ref[s])
            if not parlay_engine.MIN_LEG_PROB <= q <= parlay_engine.MAX_LEG_PROB:
                reasons["probability outside research band"] += 1
                continue
            mp = (model or {}).get((market, key_line, s))
            if mp is None:
                reasons[f"{market}: no model probability"] += 1
                continue
            if abs(float(mp) - q) > parlay_engine.MAX_MODEL_DISAGREEMENT:
                reasons["model and market disagree strongly"] += 1
                continue
            if float(mp) < q - MAX_MODEL_BELOW_MARKET:                       # issue #112
                reasons["model below the market"] += 1
                continue
            used = used_prob(market, float(mp), q) if adjust else float(mp)   # issue #106: shrunk, then capped
            entry = consensus_entry(book, pricing, s, used, float(mp), "model")
            if entry is None:
                reasons["fewer than 2 bookmakers price this leg"] += 1
                continue
            per = {CONSENSUS: entry}
            legs.append({"event_id": event["event_id"], "sport": "soccer", "league": event["league"],
                         "competition": event.get("competition") or event["league"],
                         "participants": [event["home"], event["away"]], "start_utc": event["kickoff_utc"],
                         "title": f"{event['home']} v {event['away']}", "market": market, "line": key_line,
                         "selection": s, "consensus_prob": round(q, 6), "model_prob": round(float(mp), 6),
                         "prob_source": "model", "books": per, "best_value": entry["value"], "best_prob": used,
                         "risk_note": risk_note_line(notes)})
    return legs, reasons


def legs_for_event(event: dict, books: dict, model: dict | None,
                   notes: list[str] | None = None, line_model: dict | None = None) -> tuple[dict | None, str | None]:
    """The single best candidate leg for one game (or None, reason): the most likely leg across
    `candidate_legs` (issue #112). Kept for callers that want one leg per game."""
    legs, why = candidate_legs(event, books, model, notes, line_model)
    if why:
        return None, why
    return max(legs, key=lambda x: (x["best_prob"], x["selection"])), None


def candidate_legs(event: dict, books: dict, model: dict | None, notes: list[str] | None = None,
                   line_model: dict | None = None, adjust: bool = True,
                   every: bool = False) -> tuple[list[dict], str | None]:
    """Candidate legs for one game (or [], reason): the most likely selection (highest probability
    used, issue #112; before #112 the highest value at one bookmaker) per market and line, so a soccer game can offer a match-result leg and, where priced,
    Over/Under, BTTS, Double Chance and Draw No Bet legs (issue #82), and an NBA/NFL game the best
point-spread and the best game-total selection over all lines (issue #83). A parlay still takes at most
    one leg per game (`linked`). Values may be negative here; the parlay-level check is in `search`.
    `model` is keyed (market, selection) as in `parlay_engine.model_probs`, or (market, line,
    selection) as in `model_probs_full`; the match-result screen reads line-less entries.
    `line_model` is `line_model_probs` for the spread/total legs. `every` returns every screened
    leg instead of one per market (the single picks filter on a minimum price first)."""
    full = {(k if len(k) == 3 else (k[0], None, k[1])): v for k, v in (model or {}).items()}
    flat = {(m, s): v for (m, ln, s), v in full.items() if ln is None}
    legs, why = screen_event(event, books, flat, notes, line_model, adjust)
    extra, reasons = extra_market_legs(event, books, full, notes, adjust)
    legs = list(legs) + extra
    if not legs:
        return [], why or (reasons.most_common(1)[0][0] if reasons else "no selection passed")
    order = lambda x: (-x["best_prob"], x["market"], x.get("line") or 0, x["selection"])
    if every:
        return sorted(legs, key=order), None
    best = {}
    for x in legs:
        k = (x["market"],) if x["market"] in parlay_lines.MARKETS else (x["market"], x.get("line"))
        rank = lambda y: (y["best_prob"], y["selection"], -abs(y.get("line") or 0.0))
        if k not in best or rank(x) > rank(best[k]):
            best[k] = x
    return sorted(best.values(), key=order), None


def build_pool(con, now: datetime, day: str | None = None, adjust: bool = True,
               every: bool = False) -> tuple[list[dict], dict]:
    """Leg pool for today, or for the later New York date `day` (a preview, issue #58). `adjust=False`
    keeps raw leg probabilities (issue #106). `every` keeps every screened selection (single picks)."""
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
        legs, why = candidate_legs(e, books, model_probs_full(con, e["event_id"], now),
                                   risk_note_texts(con, e["event_id"]), line_model_probs(con, e["event_id"], now),
                                   adjust, every)
        if why:
            excluded[why] += 1
            continue
        for leg in legs:
            leg["price_ts"] = _price_times(con, e["event_id"], leg, now)
            pool.append(leg)
    pool.sort(key=lambda x: (-x["best_prob"], x["event_id"], x["market"], x.get("line") or 0, x["selection"]))
    cov = {"events_today": len(events), "events_with_fresh_prices": fresh, "legs": len(pool),
           "excluded": dict(sorted(excluded.items()))}
    if preview:                       # issue #61: which sports on a preview day have prices
        cov["by_sport"] = dict(sorted(by_sport.items()))
    return pool, cov


def line_model_probs(con, event_id: str, now: datetime) -> dict:
    """{(market, selection, line): stored model probability} for the event's latest recent run
    (issue #83, SPREAD/TOTAL). Only read by `screen_event` when the backtest favours the model."""
    row = con.execute("""SELECT run_id, MAX(created_at) c FROM predictions WHERE event_id=? AND market IN ('SPREAD','TOTAL')
                         GROUP BY run_id ORDER BY c DESC LIMIT 1""", (event_id,)).fetchone()
    if not row or not row["c"]:
        return {}
    if (now - datetime.fromisoformat(row["c"])).total_seconds() / 3600 > parlay_engine.MAX_PREDICTION_AGE_H:
        return {}
    return {(r["market"], r["selection"], float(r["line"])): r["model_prob"] for r in con.execute(
        """SELECT market, selection, line, model_prob FROM predictions WHERE run_id=? AND event_id=?
           AND market IN ('SPREAD','TOTAL') AND line IS NOT NULL""", (row["run_id"], event_id))}


def _price_times(con, event_id: str, leg: dict, now: datetime) -> dict:
    """Retrieval time of the prices used for the leg (latest at or before now). Issue #112: the typical
    price (`CONSENSUS`) is timed at the latest of the bookmaker prices it was taken from."""
    out = {}
    line = leg.get("line")
    rows = (con.execute("""SELECT bookmaker, retrieved_at FROM odds WHERE event_id=? AND kind='pre' AND market=?
                           AND selection=? AND line IS NULL""", (event_id, leg["market"], leg["selection"]))
            if line is None else
            con.execute("""SELECT bookmaker, retrieved_at FROM odds WHERE event_id=? AND kind='pre' AND market=?
                           AND selection=? AND abs(line - ?) < 1e-9""", (event_id, leg["market"], leg["selection"], line)))
    used = set(leg["books"])
    for b in leg["books"].values():
        used |= set(b.get("book_prices") or {})
    for r in rows:
        bk = normalize_book(r["bookmaker"])
        t = parlays._ts(r["retrieved_at"])
        if bk in used and t is not None and t <= now and (bk not in out or t > out[bk][0]):
            out[bk] = (t, r["retrieved_at"])
    res = {bk: v for bk, (t, v) in out.items()}
    for key, b in leg["books"].items():
        ts = [out[bk] for bk in (b.get("book_prices") or {}) if bk in out]
        if ts and len(ts) == len(b.get("book_prices") or {}):
            res[key] = max(ts)[1]
    return res


# ---------- search and selection (pure) ----------
def linked(a: dict, b: dict) -> list[str]:
    """Estimated mode: same game or a shared team/player blocks a pair; same competition does not."""
    return [r for r in parlays.correlation_reasons(a, b) if r != "same competition"]


def score(joint: float, ev: float | None = None) -> float:
    """Issue #112: parlays are ranked by joint probability alone (the estimated value is not used)."""
    return joint


def min_odds(n_legs: int) -> float | None:
    """Minimum typical combined odds for a parlay of `n_legs` (issue #112), None outside the sizes."""
    b = size_bucket(n_legs)
    return None if b is None else MIN_COMBINED_ODDS[b]


def combo(legs: list[dict], bk: str = CONSENSUS) -> dict:
    odds = prod(x["books"][bk]["price"] for x in legs)
    joint = prod(x["books"][bk]["prob"] for x in legs)
    ev = joint * odds - 1.0
    return {"bookmaker": bk, "legs": legs, "n_legs": len(legs), "estimated_odds": odds, "joint_prob": joint,
            "estimated_ev": ev, "score": score(joint, ev)}


def qualifies(c: dict) -> bool:
    """A parlay may be shown (issue #112): a card size and typical combined odds at or above that size's
    minimum. No value check: the typical price includes the bookmakers' margin (owner decision)."""
    m = min_odds(c["n_legs"])
    return m is not None and c["estimated_odds"] >= m - 1e-9


def adds_no_loss(leg: dict, bk: str = CONSENSUS) -> bool:
    """Kept for reference: probability x price >= 1 at `bk`. Not a selection rule since issue #112."""
    return leg["books"][bk]["prob"] * leg["books"][bk]["price"] >= 1.0


def sensible(leg: dict, bk: str = CONSENSUS) -> bool:
    """Owner decision 2026-11-26: a leg may join a parlay only if the whole market rates it clearly likely
    (de-vigged consensus >= MIN_LEG_MARKET_PROB), it pays something (typical price >= MIN_LEG_PRICE), and
    Doyen's model, where it has one, is not below the market by more than MAX_MODEL_BELOW_MARKET."""
    q, b = leg.get("consensus_prob"), leg.get("books", {}).get(bk)
    if q is None or b is None or q < MIN_LEG_MARKET_PROB or b["price"] < MIN_LEG_PRICE - 1e-9:
        return False
    mp = leg.get("model_prob")
    return mp is None or mp >= q - MAX_MODEL_BELOW_MARKET - 1e-9


def search(pool: list[dict], beam: int = BEAM, max_evals: int = MAX_EVALUATIONS) -> list[dict]:
    """2..5-leg combinations at the typical price (issue #112), at most one leg per game and no linked
    legs, whose typical combined odds reach the size's minimum (`MIN_COMBINED_ODDS`). Beam search: at
    each size the frontier keeps the `beam` most likely combinations overall, the `beam` most likely that
    already reach the minimum odds, and the `beam` with the highest odds-weighted likelihood
    (joint x odds), so likely-but-short legs can still be extended to a worthwhile payout. Returned
    candidates all qualify; ranking by joint probability happens in `select`."""
    bk = CONSENSUS
    idx = sorted((i for i, leg in enumerate(pool) if bk in leg["books"] and sensible(leg, bk)),
                 key=lambda i: (-pool[i]["books"][bk]["prob"], i))
    pos = {i: n for n, i in enumerate(idx)}
    frontier, out, evals = [(i,) for i in idx], [], 0
    top_size = max(hi for _, hi in SIZE_BUCKETS)
    for n in range(MIN_LEGS, min(MAX_LEGS, top_size) + 1):
        nxt = {}
        for c in frontier:
            for j in idx[pos[c[-1]] + 1:]:
                if evals >= max_evals:
                    break
                evals += 1
                if any(linked(pool[j], pool[k]) for k in c):
                    continue
                new = c + (j,)
                nxt[new] = combo([pool[k] for k in new], bk)
        tie = lambda kv: sorted(kv[0])
        by_joint = sorted(nxt.items(), key=lambda kv: (-kv[1]["joint_prob"], tie(kv)))
        ok = [kv for kv in by_joint if qualifies(kv[1])]
        by_pay = sorted(nxt.items(), key=lambda kv: (-kv[1]["joint_prob"] * kv[1]["estimated_odds"], tie(kv)))
        out += [c for _, c in ok[:beam]]
        keep = dict(by_joint[:beam])
        keep.update(ok[:beam])
        keep.update(by_pay[:beam])
        frontier = sorted(keep, key=lambda k: sorted(k))
        if not frontier:
            break
    return out


def _leg_key(x: dict) -> str:
    """Leg identity in the parlay_id; the line is added only when there is one, so match-result
    parlay ids are exactly as before issue #82."""
    base = f"{x['event_id']}|{x['market']}|{x['selection']}"
    return base if x.get("line") is None else f"{base}|{float(x['line']):g}"


def parlay_id(c: dict, day: str) -> str:
    key = json.dumps([day, c["bookmaker"], sorted(_leg_key(x) for x in c["legs"])])
    return "pe-" + hashlib.sha1(key.encode()).hexdigest()[:12]


def weak_legs(c: dict) -> int:
    """Legs below their own probability bar at the card's price (probability x price < 1). Information
    only since issue #112: at the typical price (margin included) most legs are below it."""
    bk = c["bookmaker"]
    return sum(1 for x in c["legs"] if x["books"][bk]["prob"] * x["books"][bk]["price"] < 1.0)


def size_bucket(n_legs: int) -> str | None:
    """The size bucket a parlay belongs to (issue #54): "2", "3" or "4-5"; 6 legs is in none."""
    for lo, hi in SIZE_BUCKETS:
        if lo <= n_legs <= hi:
            return str(lo) if lo == hi else f"{lo}-{hi}"
    return None


def select(cands: list[dict], limit: int | None = None, blocked_events: set | None = None,
           per_size: int | None = None) -> list[dict]:
    """Cards per size (issue #54): the best 4-5 leg, the best 3-leg and the best 2-leg parlay, then a
    second of each while `per_size` and `limit` allow. In the first round the sizes pick games in
    the order that covers the most sizes (bigger sizes first on a tie). Within a size, the highest
    joint probability first (issue #112; ties: fewer legs). A size with no qualifying combo is skipped,
    never padded. Every card reaches its size's minimum typical combined odds (`qualifies`); a game
    appears in at most one card; games in a verified-quote card are skipped (strict mode wins).
    Returned earliest kickoff first."""
    per_size = PER_SIZE if per_size is None else per_size
    limit = MAX_CARDS if limit is None else limit
    order = lambda c: (-c["joint_prob"], c["n_legs"], c["bookmaker"], sorted(x["event_id"] for x in c["legs"]))
    buckets = defaultdict(list)
    for c in cands:
        b = size_bucket(c["n_legs"])
        if b is not None and qualifies(c):
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
        key = (len(got), tuple(b in got for b in names), sum(c["joint_prob"] for c in out),
               tuple(-names.index(b) for b in order))
        if best is None or key > best[0]:
            best = (key, used, out, taken)
    _, used, out, taken = best
    for _ in range(per_size - 1):                                      # later rounds: bigger first
        take(names, used, out, taken)
    out.sort(key=lambda c: (min(x["start_utc"] for x in c["legs"]), c["bookmaker"]))
    return out


def card(c: dict, day: str, preview: bool = False) -> dict:
    """A card at the typical price (issue #112): no bookmaker is named. Each leg carries its typical
    price, the number of bookmakers it was taken from (`price_books`) and the probability used."""
    bk = c["bookmaker"]
    legs = sorted(c["legs"], key=lambda x: (x["start_utc"], x["event_id"]))
    odds = round(prod(x["books"][bk]["price"] for x in legs), 4)
    times = [x["price_ts"][bk] for x in legs if bk in x.get("price_ts", {})]
    out = {"parlay_id": parlay_id(c, day), "date": day, "status": "active", "kind": ESTIMATE_KIND, "badge": BADGE,
            "method": METHOD, "price_basis": PRICE_BASIS, "odds_label": TYPICAL_ODDS_LABEL,
            "odds_note": TYPICAL_ODDS_NOTE, "n_legs": len(legs), "estimated_odds": odds,
            "price_label": price_label(), "prices_at": min(times) if len(times) == len(legs) else None,
            "stake": DEFAULT_STAKE, "gross_payout": str(parlays.gross_payout(DEFAULT_STAKE, odds)),
            "est_hit_chance": round(c["joint_prob"], 4), "est_hit_chance_label": "Model estimate, unvalidated",
            "estimated_ev": round(c["estimated_ev"], 4), "size": size_bucket(len(legs)),
            "min_odds": min_odds(len(legs)),
            "legs": [{"event_id": x["event_id"], "sport": x["sport"], "league": x["league"], "title": x["title"],
                      "market": x["market"], "market_label": MARKET_LABELS.get(x["market"], x["market"]),
                      "line": x.get("line"), "selection": x["selection"], "selection_text": selection_text(x),
                      "start_utc": x["start_utc"], "status": "active", "price": x["books"][bk]["price"],
                      "price_books": x["books"][bk].get("n_books"),
                      "prob": round(x["books"][bk]["prob"], 4),
                      **({"raw_prob": round(x["books"][bk]["raw_prob"], 4)}
                         if x["books"][bk].get("raw_prob") is not None else {}),
                      **({"market_prob": round(x["consensus_prob"], 4)}
                         if x.get("consensus_prob") is not None else {}),
                      "prob_source": x["books"][bk].get("prob_source", x["prob_source"]),
                      "price_at": x.get("price_ts", {}).get(bk),
                      "risk_note": x.get("risk_note"),
                      **({"prob_note": x.get("prob_note")} if x["market"] in parlay_lines.MARKETS else {})} for x in legs]}
    if preview:
        out.update(preview=True, preview_badge=PREVIEW_BADGE)
    return out


def market_selection_text(market: str | None, selection: str, line, home: str, away: str) -> str:
    """Plain leg text (issue #82), e.g. "Arsenal to win", "Over 2.5 goals", "Both teams to score: Yes",
    "Arsenal or draw", "Arsenal (draw no bet)", "Lakers −4.5", "Over 228.5 points"."""
    sel = str(selection or "")
    if market in parlay_lines.MARKETS and line is not None:      # issue #83: spread / total legs
        t = parlay_lines.selection_text(market, sel, line, home, away)
        if t:
            return t
    if market == "OU" and line is not None and sel in ("over", "under"):
        return f"{sel.capitalize()} {float(line):g} goals"
    if market == "BTTS" and sel in ("yes", "no"):
        return f"Both teams to score: {sel.capitalize()}"
    if market == "DC" and sel in ("HD", "DA", "HA") and home and away:
        return {"HD": f"{home} or draw", "DA": f"{away} or draw", "HA": f"{home} or {away}"}[sel]
    if market == "DNB" and sel in ("home", "away") and home and away:
        return f"{home if sel == 'home' else away} (draw no bet)"
    if sel in ("H", "home") and home:
        return f"{home} to win"
    if sel in ("A", "away") and away:
        return f"{away} to win"
    return "Draw" if sel == "D" else sel



def selection_text(leg: dict) -> str:
    home, away = leg["participants"]
    return market_selection_text(leg.get("market"), leg["selection"], leg.get("line"), home, away)


# ---------- card contract (mirrored in docs/assets/doyen.js estProblem) ----------
def team_form(con, team: str, sport: str, before: str, n: int = 5) -> str | None:
    """The team's last `n` finished results before `before`, newest first, as e.g. "W W L D W"
    (from stored final scores only). None when fewer than 3 results are stored."""
    rows = con.execute("""SELECT home, away, home_score, away_score FROM events WHERE sport=? AND status='finished'
                          AND (home=? OR away=?) AND kickoff_utc < ? AND home_score IS NOT NULL AND away_score IS NOT NULL
                          ORDER BY kickoff_utc DESC LIMIT ?""", (sport, team, team, before, n)).fetchall()
    if len(rows) < 3:
        return None
    out = []
    for r in rows:
        mine, theirs = (r["home_score"], r["away_score"]) if r["home"] == team else (r["away_score"], r["home_score"])
        out.append("W" if mine > theirs else ("L" if mine < theirs else "D"))
    return " ".join(out)


def leg_why(con, leg: dict) -> list[str]:
    """Owner request 2026-11-26: the homework behind a leg, in short lines built only from stored data
    (market consensus, Doyen's model, recent results, NBA/NFL injury reports). Nothing is invented; a
    line whose data is missing is left out."""
    out = []
    q, nb = leg.get("market_prob"), leg.get("price_books")
    if isinstance(q, (int, float)):
        out.append(f"{nb} sportsbooks: {round(q * 100)}% likely" if nb else f"Market: {round(q * 100)}% likely")
    raw = leg.get("raw_prob")
    if leg.get("prob_source") == "model" and isinstance(raw, (int, float)):
        out.append(f"Doyen's model: {round(raw * 100)}%")
    try:
        ev = con.execute("SELECT sport, home, away, kickoff_utc FROM events WHERE event_id=?", (leg["event_id"],)).fetchone()
    except Exception:
        ev = None
    if ev:
        forms = [(t, team_form(con, t, ev["sport"], ev["kickoff_utc"])) for t in (ev["home"], ev["away"])]
        if all(f for _, f in forms):
            out.append("Last 5: " + " · ".join(f"{t} {f}" for t, f in forms))
        if leg.get("sport") in ("nba", "nfl"):
            try:
                from .sources import espn_extra
                inj = espn_extra.context_for(con, leg["event_id"], leg["sport"], ev["home"], ev["away"]).get("injuries") or {}
            except Exception:
                inj = {}
            key = {t: [x["player"] for x in v if x.get("key") and x.get("status") in ("Out", "Doubtful")] for t, v in inj.items()}
            miss = [f"{t}: {', '.join(p[:2])}" + (f" +{len(p) - 2}" if len(p) > 2 else "") for t, p in key.items() if p]
            if miss:
                out.append("Key players out: " + "; ".join(miss))
    return out


def annotate(con, recs: list[dict]) -> list[dict]:
    """Adds `why` lines to every leg of the given cards (display only; never a selection rule)."""
    for r in recs:
        for leg in r.get("legs", []):
            try:
                leg["why"] = leg_why(con, leg)
            except Exception:                 # explanations must never stop a build
                leg["why"] = []
    return recs


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
    if rec.get("price_basis") != PRICE_BASIS:
        return "not priced at the typical odds"      # issue #112: never one bookmaker's price
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
        if leg.get("market") in parlay_lines.MARKETS and parlays._num(leg.get("line")) is None:
            return "leg has no valid line"            # issue #83: a spread/total leg names its line
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
        nb = parlays._num(leg.get("price_books"))
        if nb is None or nb < MIN_PRICE_BOOKS:
            return "leg price from fewer than 2 bookmakers"
        prices.append(p)
    odds = parlays._num(rec.get("estimated_odds"))
    if odds is None or odds <= 1.0:
        return "invalid estimated odds"
    if abs(odds - prod(prices)) > 0.005 * odds:
        return "estimated odds are not the product of the leg prices"
    m = min_odds(len(legs))
    if m is None or odds < m - 0.005:
        return "combined odds below the minimum for its size"
    return None


def shown(block: dict | None, now: datetime, blocked_events: set | None = None, limit: int | None = None) -> list[dict]:
    """Estimated cards the homepage may show, earliest first, skipping games in verified cards."""
    limit = MAX_CARDS if limit is None else limit
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
    recs = annotate(con, [r for r in picked if card_problem(r, now, day) is None])
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
    recs = annotate(con, [r for r in picked if card_problem(r, now, day, preview=True) is None])
    return {"status": "preview", "preview": True, "method": METHOD, "kind": ESTIMATE_KIND, "date": day,
            "timezone": parlays.CARD_TIMEZONE, "generated": now.isoformat(), "badge": BADGE,
            "preview_badge": PREVIEW_BADGE, "empty_text": PREVIEW_EMPTY_TEXT, "price_rule": PREVIEW_PRICE_RULE,
            "default_stake": DEFAULT_STAKE, "coverage": {**cov, "combinations_kept": len(cands)},
            "recommendations": recs}


def preview_coverage(con, now: datetime) -> dict:
    """Issue #66: {day: {"events", "with_prices", "legs", "by_sport": {sport: {"events", "with_prices"}}}}
    for each preview day, from the same leg pool the previews use (stored data only)."""
    out = {}
    for day in preview_days(now):
        _, cov = build_pool(con, now, day)
        out[day] = {"events": cov["events_today"], "with_prices": cov["events_with_fresh_prices"],
                    "legs": cov["legs"], "by_sport": cov.get("by_sport", {})}
    return out


def coverage_line(day: str, c: dict) -> str:
    """One log line, e.g. '2026-11-21: 41 events, 30 with prices (soccer 30/38, nba 0/3)'."""
    sports = ", ".join(f"{sp} {v['with_prices']}/{v['events']}" for sp, v in sorted(c.get("by_sport", {}).items()))
    return f"{day}: {c['events']} events, {c['with_prices']} with prices" + (f" ({sports})" if sports else "")


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
        legs = [{**{k: x[k] for k in ("event_id", "market", "selection", "price", "prob", "title", "start_utc")},
                 **({"line": x["line"]} if x.get("line") is not None else {}),       # issue #83
                 **{k: x[k] for k in ("raw_prob", "market_prob") if x.get(k) is not None},   # issue #106
                 **({"price_basis": c["price_basis"], "price_books": x.get("price_books"),    # issue #112
                     "rules_version": c.get("method") or METHOD} if c.get("price_basis") else {})}
                for x in c["legs"]]
        for leg, x in zip(legs, c["legs"]):          # issue #82: the line, only where the market has one
            if x.get("line") is not None:
                leg["line"] = x["line"]
        new.append({"first_seen": now.isoformat(), "date": c["date"], "parlay_id": c["parlay_id"],
                    "bookmaker": c.get("bookmaker") or c.get("price_basis"), "n_legs": c["n_legs"],
                    "legs": json.dumps(legs), "kind": ESTIMATE_KIND,
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


MARKET_ORDER = ("1X2", "ML", "OU", "BTTS", "DC", "DNB", "SPREAD", "TOTAL")


def settle(con, path=None) -> dict:
    """Read-only settlement from final scores. Any lost leg loses the parlay; otherwise a void or
    postponed game voids the whole row here (stake returned, 0 P/L: bookmaker void-leg rules differ
    and are not modelled); otherwise open until every leg is final. A push leg (issue #82: Draw No
    Bet on a draw) is removed at odds 1.00 and the rest stands; all legs pushed = void. P/L at the
    recorded stake and the recorded estimated price (less any pushed legs), so a real slip may have
    paid less. `by_market` (issue #82) is a LEG record per market type: each leg won, lost, push or
    void, or open, from the same final scores. Issue #107: `expected_wins_settled` is the sum of the
    recorded per-leg probabilities (`prob`) over legs that settled won or lost, per size (from
    `est_hit_chance`) and per market; None for a market where a settled leg has no recorded prob."""
    path = path or ledger_path()
    out = _tally()
    out["by_legs"], out["by_market"] = {}, {}
    if not path.exists():
        return out
    groups, markets = defaultdict(_tally), defaultdict(_leg_tally)
    with path.open(newline="") as f:
        for r in csv.DictReader(f):
            legs = json.loads(r["legs"])
            st, res, odds = _row_result(con, legs, r["estimated_odds"])
            n = str(r.get("n_legs") or "").strip() or str(len(legs))
            for t in (out, groups[n]):
                _add(t, st, r, odds)
            for x, lr in zip(legs, res):
                m = markets[str(x.get("market") or "?")]
                m[lr] += 1
                if lr in ("won", "lost"):                    # issue #107: expected leg wins
                    try:
                        p = float(x.get("prob"))
                    except (TypeError, ValueError):
                        p = None
                    if p is None or not 0.0 <= p <= 1.0:
                        m["_missing_prob"] = True
                    else:
                        m["expected_wins_settled"] += p
    for t in (out, *groups.values()):
        _finish(t)
    for m in markets.values():
        # Never show a partial sum: a settled leg without a recorded probability blanks the market.
        m["expected_wins_settled"] = None if m.pop("_missing_prob", False) else round(m["expected_wins_settled"], 3)
    out["by_legs"] = {n: groups[n] for n in sorted(groups, key=lambda k: (not k.isdigit(), int(k) if k.isdigit() else 0, k))}
    order = lambda m: (MARKET_ORDER.index(m) if m in MARKET_ORDER else len(MARKET_ORDER), m)
    out["by_market"] = {m: {**markets[m], "label": MARKET_LABELS.get(m, m)} for m in sorted(markets, key=order)}
    return out


def _leg_tally() -> dict:
    return {"won": 0, "lost": 0, "push": 0, "void": 0, "open": 0, "expected_wins_settled": 0.0}


def leg_result(con, leg: dict) -> str:
    """One leg from final scores: won, lost, push, void (game void or postponed) or open. Match-result
    legs settle exactly as before (`parlay_engine._leg_result`); the issue #82 markets settle on
    their line with `markets.settle_value` (Over/Under on the goals line, BTTS from both scores,
    Double Chance on the covered outcomes, Draw No Bet a push on a draw)."""
    if leg.get("market") not in EXTRA_MARKETS:
        return parlay_engine._leg_result(con, leg)
    from .markets import settle_value
    e = con.execute("SELECT status, home_score, away_score FROM events WHERE event_id=?", (leg["event_id"],)).fetchone()
    if not e:
        return "open"
    if e["status"] in ("void", "postponed"):
        return "void"
    if e["status"] != "finished" or e["home_score"] is None or e["away_score"] is None:
        return "open"
    line = leg.get("line")
    if leg["market"] == "OU" and line is None:
        return "open"                             # never guess a missing line
    r = settle_value(leg["market"], leg["selection"], None if line is None else float(line),
                     int(e["home_score"]), int(e["away_score"]))
    return "won" if r > 0 else ("lost" if r < 0 else "push")


def _row_result(con, legs: list[dict], odds=None) -> tuple[str, list[str], float | None]:
    """(parlay result, per-leg results, settled odds) from final scores. Any lost leg loses;
    otherwise an open leg keeps it open; otherwise a void leg voids it; otherwise it won. Pushed legs
    count at odds 1.00: settled odds = recorded odds / the pushed legs' prices; every leg pushed =
    void. Without pushes the settled odds are the recorded odds."""
    res = [leg_result(con, x) for x in legs]
    if "lost" in res:
        return "lost", res, None
    if "open" in res:
        return "open", res, None
    if "void" in res:
        return "void", res, None
    if all(x == "push" for x in res):
        return "void", res, None
    rec = None if odds is None else float(odds)
    pushed = [float(x.get("price") or 0) for x, lr in zip(legs, res) if lr == "push"]
    if rec is not None and pushed:
        if all(p > 1.0 for p in pushed):
            rec = round(rec / prod(pushed), 4)
        else:
            rec = round(prod(float(x["price"]) for x, lr in zip(legs, res) if lr == "won"), 4)
    return "won", res, rec


def _ledger_selection_text(leg: dict) -> str:
    parts = str(leg.get("title") or "").split(" v ", 1)
    home, away = (parts + [""])[:2] if len(parts) == 2 else ("", "")
    return market_selection_text(leg.get("market"), leg.get("selection"), leg.get("line"), home, away)


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
            st, res, settled = _row_result(con, legs, r["estimated_odds"])
            stake = parlays._money(r["stake"])
            odds = r["estimated_odds"]
            pl = (parlays.net_profit(stake, settled) if st == "won"
                  else (-stake if st == "lost" else Decimal("0")))
            out.append({"parlay_id": r["parlay_id"], "date": r["date"], "first_seen": r["first_seen"],
                        "kind": r.get("kind") or ESTIMATE_KIND, "bookmaker": r["bookmaker"],
                        **({"price_basis": PRICE_BASIS} if r["bookmaker"] == PRICE_BASIS else {}),
                        "n_legs": int(str(r.get("n_legs") or "").strip() or len(legs)),
                        "estimated_odds": float(odds), "stake": str(stake),
                        "gross_payout": str(parlays.gross_payout(stake, settled if st == "won" and settled else odds)),
                        "est_hit_chance": float(r["est_hit_chance"]) if r.get("est_hit_chance") else None,
                        "result": st, "paper_pl": str(parlays._money(pl)), "_order": i,
                        **({"settled_odds": settled} if st == "won" and settled is not None
                           and abs(settled - float(odds)) > 1e-9 else {}),
                        "legs": [{"event_id": x["event_id"], "title": x.get("title"), "market": x.get("market"),
                                  "market_label": MARKET_LABELS.get(x.get("market"), x.get("market")),
                                  "line": x.get("line"),
                                  "selection": x.get("selection"), "selection_text": _ledger_selection_text(x),
                                  "price": x.get("price"), "start_utc": x.get("start_utc"), "result": lr,
                                  **({"price_books": x["price_books"]} if x.get("price_books") else {})}
                                 for x, lr in zip(legs, res)]})
    out.sort(key=lambda x: (x["date"], x["first_seen"], x["_order"]), reverse=True)
    for x in out:
        del x["_order"]
    return out


def _tally() -> dict:
    return {"rows": 0, "won": 0, "lost": 0, "void": 0, "open": 0, "paper_pl": Decimal("0"),
            "staked": Decimal("0"), "expected_wins_settled": 0.0}


def _add(t: dict, st: str, r: dict, odds=None) -> None:
    t["rows"] += 1
    t[st] += 1
    stake = parlays._money(r["stake"])
    if st == "won":
        t["paper_pl"] += parlays.net_profit(stake, r["estimated_odds"] if odds is None else odds)
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
