"""Full-slate parlay candidate research engine (issue #35, PR A). SHADOW ONLY.

The stage-1 parlay builder (`sbi.parlays.build`) only combines already-published straight picks,
which are scarce (often 0-2 a day, usually in one competition). This module looks at EVERY
scheduled, accurately priced, same-day event in the supported sports (Soccer, NFL, NBA, Tennis),
using only what is already stored in the database. It makes no network request and spends no
API credit.

What it does
1. Leg pool. For each of today's (America/New_York) upcoming events, the result market (1X2 for
   soccer, moneyline for NFL/NBA/Tennis) is read from fresh stored quotes (`pipeline._latest_books`,
   source-specific freshness from `odds_policy`). A selection becomes a candidate leg only if:
   enough independent bookmakers price the market (the existing `RULES.min_bookmakers`, not
   lowered), a de-vigged consensus exists, the consensus probability is inside a research band
   (no blind heavy favourites, no long shots), the stored model probability (where Doyen stores
   one) does not disagree strongly with the market, and there is no open injury/lineup research
   note on the event.
2. Per-bookmaker leg value. A parlay is one bet slip at one bookmaker (exchanges excluded: they
   price single markets, not accumulators), so each leg is valued at each bookmaker B against a leave-one-out consensus that EXCLUDES B (and its owner group).
   A leg enters a combination at B only if B's price is at or above that fair value.
3. Bounded combination search. Per bookmaker, a beam search builds 2-6-leg combinations from a
   capped pool, with the existing screens (`parlays.correlation_reasons`: no same game, no shared
   team/player, no two legs from one competition). Independence is NOT assumed from different
   names; the competition screen is kept and every candidate is labelled shadow.
4. Output. Every combination is SHADOW: its price is a computed product of single-market prices,
   labelled `computed_product_not_a_quote`, never a bookmaker's combined quote. The homepage is
   not touched; production cards still need the stage-1 gates in `sbi.parlays.build` (verified
   combined quote + joint calibration). Results go to developer-only files:
   `data/analysis/parlay_candidates.json`, `reports/parlay_candidates.md`, and the append-only
   `ledger/parlay_candidates_shadow.csv`, which is settled read-only from final scores.

The research screens below are NOT betting thresholds and change no straight pick.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from itertools import combinations
from math import prod
from zoneinfo import ZoneInfo

from . import config, parlay_calibration, parlay_quotes, parlays
from . import ev as evm
from .sources.football_data import AGGREGATES, EXCHANGES

METHOD = "parlay-fullslate-shadow-v1"
NY = ZoneInfo("America/New_York")
PRICE_KIND = "computed_product_not_a_quote"

# Supported sports only (issue #35). events.sport -> site sport.
SPORTS = {"football": "soccer", "nfl": "nfl", "nba": "nba", "tennis": "tennis"}
# Result markets only: their consensus probabilities are what the straight-pick models are validated
# on. Totals/handicaps are out of scope here until their calibration is measured.
RESULT_MARKET = {"soccer": "1X2", "nfl": "ML", "nba": "ML", "tennis": "ML"}
SELECTIONS = {"1X2": ["H", "D", "A"], "ML": ["home", "away"]}

# Research screens (shadow only; documented in docs/PARLAYS.md section 8).
MIN_LEG_PROB = 0.30          # no long shots (decimal fair odds above ~3.3)
MAX_LEG_PROB = 0.85          # no blind heavy favourites (fair odds below ~1.18 add risk, not value)
MAX_MODEL_DISAGREEMENT = 0.12  # |stored model prob - market consensus| above this = suspect data/news
MAX_PREDICTION_AGE_H = 36    # a stored model probability older than this is ignored (not used to screen)
RISK_CATEGORIES = ("injury", "lineup")

# Combinatorial bounds.
POOL_MAX = 30                # best legs kept (one selection per event)
BEAM = 150                   # combinations kept per size per bookmaker
MAX_EVALUATIONS = 250_000    # hard stop for the whole search
SHORTLIST_MAX = parlays.CARD_MAX_CARDS   # 5 is a cap, never a target
MIN_LEGS, MAX_LEGS = parlays.MIN_LEGS, parlays.MAX_LEGS


# ---------- inputs ----------
def _day(now: datetime) -> str:
    return now.astimezone(NY).date().isoformat()


def todays_events(con, now: datetime, day: str | None = None) -> list[dict]:
    """Scheduled events in supported sports that start later today (New York calendar day), or on
    the New York date `day` (issue #58 previews) and after `now`."""
    day = day or _day(now)
    start = datetime.fromisoformat(day).replace(tzinfo=NY)
    end = start + timedelta(days=1)
    has_meta = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_meta'").fetchone()
    meta_col, meta_join = ("m.competition", "LEFT JOIN event_meta m USING(event_id)") if has_meta else ("NULL AS competition", "")
    rows = con.execute(
        f"""SELECT e.event_id, e.sport, e.league, e.kickoff_utc, e.home, e.away, e.status, {meta_col}
           FROM events e {meta_join}
           WHERE e.status='scheduled' AND e.kickoff_utc > ? AND e.kickoff_utc < ?
           ORDER BY e.kickoff_utc, e.event_id""",
        (now.astimezone(timezone.utc).isoformat(), end.astimezone(timezone.utc).isoformat())).fetchall()
    out = []
    for r in rows:
        r = dict(r)
        ko = datetime.fromisoformat(r["kickoff_utc"])
        if ko <= now or ko.astimezone(NY).date().isoformat() != day:
            continue
        r["site_sport"] = SPORTS.get(r["sport"])
        out.append(r)
    return out


def model_probs(con, event_id: str, now: datetime) -> dict:
    """Latest stored model probability per (market, selection) for the event's most recent run,
    if that run is recent. Empty when Doyen stores none (e.g. tennis)."""
    row = con.execute("""SELECT run_id, MAX(created_at) c FROM predictions WHERE event_id=? AND line IS NULL
                         GROUP BY run_id ORDER BY c DESC LIMIT 1""", (event_id,)).fetchone()
    if not row or not row["c"]:
        return {}
    if (now - datetime.fromisoformat(row["c"])).total_seconds() / 3600 > MAX_PREDICTION_AGE_H:
        return {}
    return {(r["market"], r["selection"]): r["model_prob"] for r in con.execute(
        "SELECT market, selection, model_prob FROM predictions WHERE run_id=? AND event_id=? AND line IS NULL",
        (row["run_id"], event_id))}


def risk_notes(con, event_id: str) -> int:
    q = ",".join("?" * len(RISK_CATEGORIES))
    return con.execute(f"SELECT COUNT(*) FROM research_notes WHERE event_id=? AND category IN ({q})",
                       (event_id, *RISK_CATEGORIES)).fetchone()[0]


# ---------- leg screen (pure) ----------
def screen_event(event: dict, books: dict, model: dict | None = None, n_risk_notes: int = 0,
                 min_books: int | None = None) -> tuple[list[dict], str | None]:
    """Candidate legs for one event from its fresh books {(market, line): {bk: {sel: price}}}.
    Returns (legs, None) or ([], reason). Each leg carries per-bookmaker prices and the
    leave-one-out fair probability for each bookmaker."""
    sport = event.get("site_sport")
    if sport not in RESULT_MARKET:
        return [], "unsupported sport"
    market = RESULT_MARKET[sport]
    sels = SELECTIONS[market]
    book = evm.clean(books.get((market, None)) or {}, sels)
    book = {bk: q for bk, q in book.items() if bk not in AGGREGATES or bk == "Avg"}
    if not book:
        return [], "no fresh result-market prices"
    need = config.RULES.min_bookmakers if min_books is None else min_books
    if evm.n_books(book, sels) < need:
        return [], "too few independent bookmakers"
    cons, _src = evm.consensus(book, sels)
    if not cons or str(_src or "").startswith("single:"):
        return [], "no market consensus"
    if n_risk_notes:
        return [], "open injury/lineup research note"
    legs, reasons = [], Counter()
    for s in sels:
        q = float(cons[s])
        if not MIN_LEG_PROB <= q <= MAX_LEG_PROB:
            reasons["probability outside research band"] += 1
            continue
        mp = (model or {}).get((market, s))
        if mp is not None and abs(float(mp) - q) > MAX_MODEL_DISAGREEMENT:
            reasons["model and market disagree strongly"] += 1
            continue
        per_book = {}
        for bk, quotes in book.items():
            if bk in AGGREGATES or bk in EXCHANGES:   # exchanges stay in the consensus but offer no parlay slip
                continue
            ex, _ = evm.consensus_excluding(book, sels, bk)
            if not ex or str(_ or "").startswith("single:"):
                continue
            price = float(quotes[s])
            per_book[bk] = {"price": price, "fair_prob": float(ex[s]), "value": float(ex[s]) * price - 1.0}
        if not per_book:
            reasons["no leave-one-out reference"] += 1
            continue
        legs.append({"event_id": event["event_id"], "sport": sport, "league": event["league"],
                     "competition": event.get("competition") or event["league"],
                     "participants": [event["home"], event["away"]], "start_utc": event["kickoff_utc"],
                     "title": f"{event['home']} v {event['away']}", "market": market, "selection": s,
                     "consensus_prob": round(q, 6), "model_prob": None if mp is None else round(float(mp), 6),
                     "books": per_book, "best_value": max(v["value"] for v in per_book.values())})
    if not legs:
        return [], (reasons.most_common(1)[0][0] if reasons else "no selection passed")
    return legs, None


# ---------- combination search (pure) ----------
def _linked(a: dict, b: dict) -> list[str]:
    return parlays.correlation_reasons(a, b)


def combo_value(legs: list[dict], bk: str) -> tuple[float, float, float]:
    """(computed product odds, joint prob if independent, computed EV) at bookmaker bk."""
    odds = prod(leg["books"][bk]["price"] for leg in legs)
    joint = prod(leg["books"][bk]["fair_prob"] for leg in legs)
    return odds, joint, joint * odds - 1.0


def search(pool: list[dict], beam: int = BEAM, max_evals: int = MAX_EVALUATIONS,
           linked=None) -> tuple[list[dict], dict]:
    """Bounded beam search over single-bookmaker combinations of 2..6 legs.
    Only legs priced at or above leave-one-out fair value at that bookmaker are used, so every
    leg adds value at that slip. Returns (candidates, stats).
    `linked` defaults to the live link screen; the walk-forward report (issue #38) passes a
    different one ONLY for a labelled counterfactual diagnostic, never for a live run."""
    linked = linked or _linked
    stats = {"evaluated": 0, "by_size": {n: 0 for n in range(MIN_LEGS, MAX_LEGS + 1)},
             "passing_by_size": {n: 0 for n in range(MIN_LEGS, MAX_LEGS + 1)},
             "rejected_linked": 0, "truncated": False, "bookmakers": 0}
    by_book = defaultdict(list)
    for i, leg in enumerate(pool):
        for bk, v in leg["books"].items():
            if v["value"] >= 0:
                by_book[bk].append(i)
    out = []
    for bk in sorted(by_book):
        idx = by_book[bk]
        if len(idx) < MIN_LEGS:
            continue
        stats["bookmakers"] += 1
        frontier = [(i,) for i in idx]
        for n in range(MIN_LEGS, MAX_LEGS + 1):
            nxt = {}
            for combo in frontier:
                for j in idx:
                    if j <= combo[-1]:
                        continue
                    if stats["evaluated"] >= max_evals:
                        stats["truncated"] = True
                        break
                    stats["evaluated"] += 1
                    stats["by_size"][n] += 1
                    if any(linked(pool[j], pool[k]) for k in combo):
                        stats["rejected_linked"] += 1
                        continue
                    new = combo + (j,)
                    odds, joint, ev = combo_value([pool[k] for k in new], bk)
                    if ev > 0:
                        nxt[new] = (ev, odds, joint)
            ranked = sorted(nxt.items(), key=lambda kv: (-kv[1][0], kv[0]))[:beam]
            for combo, (ev, odds, joint) in ranked:
                stats["passing_by_size"][n] += 1
                out.append({"bookmaker": bk, "legs": [pool[k] for k in combo], "n_legs": n,
                            "computed_product_odds": round(odds, 4), "joint_prob_independent": round(joint, 6),
                            "computed_ev": round(ev, 6)})
            frontier = [c for c, _ in ranked]
            if not frontier:
                break
    return out, stats


def candidate_id(c: dict, day: str) -> str:
    key = json.dumps([day, c["bookmaker"], sorted(f"{x['event_id']}|{x['market']}|{x['selection']}" for x in c["legs"])])
    return "pc-" + hashlib.sha1(key.encode()).hexdigest()[:12]


def shortlist(cands: list[dict], limit: int = SHORTLIST_MAX) -> list[dict]:
    """Best computed EV first; an event appears in at most one shortlisted combination; identical
    leg sets at different bookmakers are deduplicated (best kept). 0 is a normal result."""
    seen_sets, used, out = set(), set(), []
    for c in sorted(cands, key=lambda c: (-c["computed_ev"], c["n_legs"], c["bookmaker"])):
        legset = frozenset((x["event_id"], x["selection"]) for x in c["legs"])
        if legset in seen_sets:
            continue
        seen_sets.add(legset)
        evs = {x["event_id"] for x in c["legs"]}
        if evs & used:
            continue
        used |= evs
        out.append(c)
        if len(out) >= limit:
            break
    return out


def production_blockers(c: dict, calibration: dict | None, verified_quote_ids: set) -> list[str]:
    """Why this candidate may not be a production card. Never empty today unless both stage-1 gates pass."""
    out = []
    if c.get("id") not in verified_quote_ids:
        out.append("no verified bookmaker combined quote (price shown is a computed product)")
    cov = parlay_calibration.coverage_problem(calibration, c["legs"])
    if cov:
        out.append(cov)
    return out


# ---------- orchestration ----------
def build_pool(con, now: datetime) -> dict:
    """Today's events, screened candidate legs and the capped pool (one selection per event).
    Shared by `run` and the walk-forward replay (issue #38) so both use identical screens."""
    from .pipeline import _latest_books
    events = todays_events(con, now)
    excluded = Counter()
    by_sport = defaultdict(lambda: Counter())
    pool_all = []
    event_reason = {}
    for e in events:
        sp = e["site_sport"] or e["sport"]
        by_sport[sp]["events"] += 1
        if e["site_sport"] is None:
            excluded["event: unsupported sport"] += 1
            continue
        books, odds_ts, _ = _latest_books(con, e["event_id"], config.RULES.max_odds_age_hours, now)
        if books:
            by_sport[sp]["fresh_prices"] += 1
        model = model_probs(con, e["event_id"], now)
        if model:
            by_sport[sp]["stored_model"] += 1
        legs, why = screen_event(e, books, model, risk_notes(con, e["event_id"]))
        if why:
            excluded["event: " + why] += 1
            event_reason[e["event_id"]] = why
            continue
        by_sport[sp]["events_with_candidate_legs"] += 1
        for leg in legs:
            leg["odds_updated"] = odds_ts
        pool_all += legs
    # One selection per event (its best value), then cap the pool.
    best = {}
    for leg in pool_all:
        if leg["event_id"] not in best or leg["best_value"] > best[leg["event_id"]]["best_value"]:
            best[leg["event_id"]] = leg
    ranked = sorted(best.values(), key=lambda x: (-x["best_value"], x["event_id"]))
    pool = [x for x in ranked if x["best_value"] >= 0][:POOL_MAX]
    excluded["leg: no bookmaker at or above fair value"] += sum(1 for x in ranked if x["best_value"] < 0)
    return {"events": events, "excluded": excluded, "by_sport": by_sport, "pool_all": pool_all,
            "best": best, "pool": pool, "event_reason": event_reason}


def run(con, now: datetime, calibration: dict | None = None) -> dict:
    day = _day(now)
    bp = build_pool(con, now)
    events, excluded, by_sport, pool_all, best, pool = (bp[k] for k in ("events", "excluded", "by_sport",
                                                                          "pool_all", "best", "pool"))
    cands, stats = search(pool)
    for c in cands:
        c["id"] = candidate_id(c, day)
    short = shortlist(cands)
    verified = {q.get("quote_id") for q in parlay_quotes.load()}
    for c in short:
        c["production_blockers"] = production_blockers(c, calibration, verified)
    return {"generated": now.isoformat(), "date": day, "timezone": "America/New_York", "method": METHOD,
            "price_kind": PRICE_KIND, "publication": "shadow_only",
            "screens": {"min_leg_prob": MIN_LEG_PROB, "max_leg_prob": MAX_LEG_PROB,
                        "max_model_disagreement": MAX_MODEL_DISAGREEMENT,
                        "min_independent_bookmakers": config.RULES.min_bookmakers,
                        "pool_max": POOL_MAX, "beam": BEAM, "max_evaluations": MAX_EVALUATIONS},
            "coverage": {"events_today": len(events), "by_sport": {k: dict(v) for k, v in sorted(by_sport.items())},
                         "candidate_legs": len(pool_all), "events_with_candidate_legs": len(best),
                         "pool_legs": len(pool), "excluded": dict(sorted(excluded.items()))},
            "search": stats, "candidates_found": len(cands), "shortlist": [_public(c) for c in short]}


def _public(c: dict) -> dict:
    return {"id": c["id"], "bookmaker": c["bookmaker"], "n_legs": c["n_legs"], "price_kind": PRICE_KIND,
            "computed_product_odds": c["computed_product_odds"], "joint_prob_independent": c["joint_prob_independent"],
            "computed_ev": c["computed_ev"], "production_blockers": c.get("production_blockers", []),
            "legs": [{"event_id": x["event_id"], "sport": x["sport"], "league": x["league"], "title": x["title"],
                      "market": x["market"], "selection": x["selection"], "start_utc": x["start_utc"],
                      "price": x["books"][c["bookmaker"]]["price"],
                      "fair_prob_ex_book": round(x["books"][c["bookmaker"]]["fair_prob"], 6),
                      "model_prob": x["model_prob"], "odds_updated": x.get("odds_updated")}
                     for x in sorted(c["legs"], key=lambda x: (x["start_utc"], x["event_id"]))]}


# ---------- shadow ledger (append-only) and read-only settlement ----------
LEDGER_FIELDS = ("first_seen", "date", "candidate_id", "bookmaker", "n_legs", "legs", "price_kind",
                 "computed_product_odds", "joint_prob_independent", "computed_ev")


def ledger_path():
    return config.ROOT / "ledger" / "parlay_candidates_shadow.csv"


def record(result: dict, now: datetime, path=None) -> int:
    """Append unseen shortlisted candidates. Existing rows are never edited or removed."""
    path = path or ledger_path()
    seen = set()
    if path.exists():
        with path.open(newline="") as f:
            seen = {r["candidate_id"] for r in csv.DictReader(f)}
    new = []
    for c in result["shortlist"]:
        if c["id"] in seen:
            continue
        seen.add(c["id"])
        legs = [{k: x[k] for k in ("event_id", "market", "selection", "price")} for x in c["legs"]]
        new.append({"first_seen": now.isoformat(), "date": result["date"], "candidate_id": c["id"],
                    "bookmaker": c["bookmaker"], "n_legs": c["n_legs"], "legs": json.dumps(legs), "price_kind": PRICE_KIND,
                    "computed_product_odds": c["computed_product_odds"],
                    "joint_prob_independent": c["joint_prob_independent"], "computed_ev": c["computed_ev"]})
    if new:
        path.parent.mkdir(parents=True, exist_ok=True)
        header = not path.exists()
        with path.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=LEDGER_FIELDS)
            if header:
                w.writeheader()
            w.writerows(new)
    return len(new)


def _leg_result(con, leg: dict) -> str:
    from .markets import settle_value
    e = con.execute("SELECT status, home_score, away_score FROM events WHERE event_id=?", (leg["event_id"],)).fetchone()
    if not e:
        return "open"
    if e["status"] == "void" or e["status"] == "postponed":
        return "void"
    if e["status"] != "finished" or e["home_score"] is None:
        return "open"
    line = leg.get("line")                       # spread/total legs (issue #83); None for result markets
    if leg["market"] in ("SPREAD", "TOTAL") and line is None:
        return "open"                              # unknown line: never guess a result
    r = settle_value(leg["market"], leg["selection"], None if line is None else float(line),
                     e["home_score"], e["away_score"])
    return "won" if r > 0 else ("void" if r == 0 else "lost")


def settle_summary(con, path=None) -> dict:
    """Read-only shadow settlement of the ledger from final scores (the ledger itself is not edited).
    A void leg makes the row void here (bookmaker rules on void legs differ; not modelled)."""
    path = path or ledger_path()
    out = {"rows": 0, "won": 0, "lost": 0, "void": 0, "open": 0, "expected_wins_settled": 0.0,
           "by_legs": {}}
    if not path.exists():
        return out
    with path.open(newline="") as f:
        for r in csv.DictReader(f):
            out["rows"] += 1
            res = [_leg_result(con, x) for x in json.loads(r["legs"])]
            st = "lost" if "lost" in res else ("void" if "void" in res else ("open" if "open" in res else "won"))
            out[st] += 1
            b = out["by_legs"].setdefault(r["n_legs"], {"won": 0, "lost": 0, "void": 0, "open": 0})
            b[st] += 1
            if st in ("won", "lost"):
                out["expected_wins_settled"] += float(r["joint_prob_independent"])
    out["expected_wins_settled"] = round(out["expected_wins_settled"], 3)
    return out


# ---------- straight-pick baseline and report ----------
def baseline(con, now: datetime) -> dict:
    """The stage-1 builder's view today (published straight picks only), for before/after."""
    from . import site
    legs = site.parlay_legs(con, now)
    block = parlays.build(legs, now, quotes=parlay_quotes.load(), calibration=parlay_calibration.evaluate())
    a = block["audit"]
    return {"straight_picks_seen": a["straight_picks_seen"], "usable_legs_today": a["usable_legs_today"],
            "combinations_checked": a["combinations_checked"], "passed_leg_screens": a["passed_leg_screens"]}


def quota(con) -> dict:
    """Latest The Odds API job record (credits), read from the job log. This engine spends none."""
    row = con.execute("SELECT started_at, details FROM job_runs WHERE job='ingest-odds-api' ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return {}
    try:
        d = json.loads(row["details"] or "{}")
    except ValueError:
        return {}
    return {"at": row["started_at"], "credits_spent_last_run": d.get("credits_spent"),
            "credits_remaining": d.get("credits_remaining_after", d.get("credits_remaining_before"))}


def why_not(result: dict, calibration: dict | None) -> list[str]:
    cov, out = result["coverage"], []
    if not result["shortlist"]:
        out.append("No combination of today's legs is priced at or above leave-one-out fair value at one bookmaker "
                   "after the screens; 0 candidates is the honest result.")
    if cov["pool_legs"] < 2:
        out.append(f"Only {cov['pool_legs']} leg(s) are at or above fair value at any bookmaker.")
    comps = {leg["league"] for c in result["shortlist"] for leg in c["legs"]}
    if result["shortlist"] and len(comps) < 3:
        out.append("Legs cluster in few competitions, and two legs from one competition are never combined.")
    out.append("Every candidate is shadow: no free source returns a bookmaker's own combined price, so the shown "
               "price is a computed product of single-market prices, not a quote.")
    if not (calibration or {}).get("passed"):
        out.append(f"Joint calibration not passed ({(calibration or {}).get('combinations', 0)} disjoint settled "
                   f"pairs of {parlay_calibration.MIN_COMBINATIONS} required; 2-leg, six club leagues only).")
    return out


def write(con, now: datetime, record_ledger: bool = False) -> dict:
    cal = parlay_calibration.evaluate()
    r = run(con, now, cal)
    r["baseline_straight_picks"] = baseline(con, now)
    r["quota"] = quota(con)
    if record_ledger:
        r["ledger_rows_added"] = record(r, now)
    r["shadow_settlement"] = settle_summary(con)
    r["why_not_3_to_5"] = why_not(r, cal)
    (config.DATA_DIR / "analysis").mkdir(parents=True, exist_ok=True)
    (config.DATA_DIR / "analysis" / "parlay_candidates.json").write_text(json.dumps(r, indent=1))
    _report(r, now)
    return r


def _report(r: dict, now: datetime):
    c, s, b, ss = r["coverage"], r["search"], r["baseline_straight_picks"], r["shadow_settlement"]
    L = [f"# Parlay candidates (shadow) — {now.astimezone(NY):%Y-%m-%d %H:%M} New York", "",
         "Developer-only. **Nothing here is published.** Prices are computed products of single-market quotes "
         f"(`{PRICE_KIND}`), not bookmaker combined quotes. Method `{METHOD}`; no network request, no API credit.", "",
         "## 1. Coverage: before (straight picks only) and after (full slate)", "",
         "| Measure | Stage-1 (published picks) | Full-slate engine |", "|---|---|---|",
         f"| Legs considered today | {b['straight_picks_seen']} picks | {c['events_today']} events |",
         f"| Usable legs | {b['usable_legs_today']} | {c['pool_legs']} (candidate legs {c['candidate_legs']}, "
         f"events with a leg {c['events_with_candidate_legs']}) |",
         f"| Combinations checked | {b['combinations_checked']} | {s['evaluated']} (bounded; truncated: {s['truncated']}) |",
         f"| Passed leg/combination screens | {b['passed_leg_screens']} | {r['candidates_found']} |", "",
         "| Sport | Events today | Fresh prices | Stored model prob | Events with candidate legs |", "|---|---|---|---|---|"]
    for sp, v in c["by_sport"].items():
        L.append(f"| {sp} | {v.get('events', 0)} | {v.get('fresh_prices', 0)} | {v.get('stored_model', 0)} | "
                 f"{v.get('events_with_candidate_legs', 0)} |")
    L += ["", f"Excluded: {json.dumps(c['excluded'])}", "",
          "| Legs | Combinations evaluated | Kept (positive computed EV, beam-capped) |", "|---|---|---|"]
    L += [f"| {n} | {s['by_size'][n]} | {s['passing_by_size'][n]} |" for n in s["by_size"]]
    q = r.get("quota") or {}
    L += ["", f"The Odds API (read from job log, not called here): last run {q.get('at', 'n/a')}, spent "
          f"{q.get('credits_spent_last_run', 'n/a')}, remaining {q.get('credits_remaining', 'n/a')}.", "",
          "## 2. Shadow shortlist (not shown on the homepage)", ""]
    if not r["shortlist"]:
        L.append("- none")
    for x in r["shortlist"]:
        L.append(f"- `{x['id']}` {x['n_legs']} legs at **{x['bookmaker']}**: computed product {x['computed_product_odds']}, "
                 f"joint prob (if independent) {x['joint_prob_independent']:.3f}, computed EV {x['computed_ev']:+.1%}. "
                 f"Blocked: {'; '.join(x['production_blockers'])}")
        for leg in x["legs"]:
            L.append(f"  - {leg['title']} ({leg['league']}) — {leg['market']} {leg['selection']} @ {leg['price']} "
                     f"(fair ex-book {leg['fair_prob_ex_book']:.3f}; model {leg['model_prob']}; {leg['start_utc']})")
    L += ["", "## 3. Shadow settlement (`ledger/parlay_candidates_shadow.csv`, read-only from final scores)", "",
          f"- Rows: {ss['rows']}; won {ss['won']}, lost {ss['lost']}, void {ss['void']}, open {ss['open']}; "
          f"expected wins among settled (product of fair probs): {ss['expected_wins_settled']}",
          f"- By legs: {json.dumps(ss['by_legs'])}",
          "- Far too small for any conclusion; walk-forward multi-leg validation is follow-up work (issue #35, PR B).", "",
          "## 4. Why not 3–5 recommended parlays today", ""]
    L += [f"- {w}" for w in r["why_not_3_to_5"]]
    out = config.REPORTS_DIR / "parlay_candidates.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n")
    return out
