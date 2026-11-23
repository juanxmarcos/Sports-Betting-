"""Leg calibration of the estimated parlays, per market (issue #106).

After 25 settled estimated parlays the record was 3-22 against about 7.3 expected wins: the leg
probabilities were too optimistic, above all soccer Over/Under and Double Chance. This module
measures that, read-only, and is the evidence behind the leg-probability shrinking in
`sbi.parlay_estimated.used_prob`.

Two parts, both written to `data/backtest/parlay_calibration.json` by
`python -m sbi parlay-calibration`:

1. `ledger_calibration`: per market, over every SETTLED leg in `ledger/estimated_parlays.csv`
   (won or lost; push and void legs are excluded, open legs counted apart), the mean probability
   the parlay used, the mean raw model probability, the actual hit rate with a Wilson 95% interval,
   and the de-vigged market probability. The market probability is the one stored on the leg
   (`market_prob`, recorded since #106); for older rows it is reconstructed from the stored odds
   exactly as the card saw them (same bookmakers, retrieved on the same New York day before
   `first_seen` and before the start), and labelled as reconstructed.
2. `weight_backtest`: on every finished soccer game in the database with a model run stored before
   kick-off and pre-match prices, the log loss and Brier score of
   `w x model + (1 - w) x market` for w = 0, 0.05, ..., 1, per market (Over/Under at the leg lines,
   Double Chance, Draw No Bet), over all selections and over the "optimistic" subset where the model
   sits above the market (the legs a value search prefers). BTTS has no stored model run, so it is
   not tested. Nothing here changes a pick, a price or the ledger.
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta

from . import config, parlay_engine, parlay_lines
from . import ev as evm
from . import parlay_estimated as pe
from .sources.football_data import AGGREGATES

METHOD = "parlay-leg-calibration-v1"
Z95 = 1.959964
WEIGHTS = [round(i * 0.05, 2) for i in range(21)]
OPTIMISTIC_GAP = 0.0          # model above market by more than this = the "optimistic" subset
EPS = 1e-6


def out_path():
    return config.DATA_DIR / "backtest" / "parlay_calibration.json"


def wilson(k: int, n: int, z: float = Z95) -> list[float] | None:
    """Wilson score interval for k successes in n trials."""
    if n <= 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


# ---------- market reference (mirrors the screens in parlay_estimated) ----------
def _clean(raw: dict, sels: list[str]) -> dict:
    book = evm.clean(raw or {}, sels)
    return {bk: q for bk, q in book.items() if bk not in AGGREGATES or bk == "Avg"}


def market_reference(books: dict, market: str, line, selection: str) -> float | None:
    """De-vigged market consensus for one selection from stored books {(market, line): {bk: {sel: price}}},
    as the estimated-parlay screens compute it: the market's own consensus; Double Chance from the
    1X2 consensus; Draw No Bet falls back to the 1X2 consensus without the draw."""
    line = None if line is None else float(line)
    one = _clean(books.get(("1X2", None)), ["H", "D", "A"])
    ref1 = evm.consensus(one, ["H", "D", "A"])[0] if one else None
    if market == "DC":
        if not ref1:
            return None
        return {"HD": ref1["H"] + ref1["D"], "DA": ref1["D"] + ref1["A"], "HA": ref1["H"] + ref1["A"]}.get(selection)
    sels = (pe.EXTRA_MARKETS.get(market) or parlay_engine.SELECTIONS.get(market)
            or parlay_lines.SELECTIONS.get(market))
    if not sels:
        return None
    raw = books.get((market, line))
    if raw is None and line is not None:
        raw = next((v for (m, ln), v in books.items() if m == market and ln is not None and abs(ln - line) < 1e-9), None)
    book = _clean(raw, sels)
    ref = evm.consensus(book, sels)[0] if book else None
    if not ref and market == "DNB" and ref1 and ref1["H"] + ref1["A"] > 0:
        ref = {"home": ref1["H"] / (ref1["H"] + ref1["A"]), "away": ref1["A"] / (ref1["H"] + ref1["A"])}
    return None if not ref or selection not in ref else float(ref[selection])


def _reconstructed_market_prob(con, leg: dict, first_seen: datetime) -> float | None:
    e = con.execute("SELECT kickoff_utc FROM events WHERE event_id=?", (leg.get("event_id"),)).fetchone()
    start = pe.parlays._ts(e["kickoff_utc"]) if e else pe.parlays._ts(leg.get("start_utc"))
    books = pe.fresh_books(con, leg["event_id"], first_seen, start, same_day=True)
    return market_reference(books, leg.get("market"), leg.get("line"), leg.get("selection"))


# ---------- part 1: settled ledger legs ----------
def _empty() -> dict:
    return {"won": 0, "lost": 0, "excluded_push_void": 0, "open": 0, "_p": [], "_raw": [], "_mkt": [],
            "_mkt_src": defaultdict(int)}


def ledger_calibration(con, path=None) -> dict:
    """Per-market calibration of every settled ledger leg (read-only)."""
    path = path or pe.ledger_path()
    acc = defaultdict(_empty)
    rows = 0
    if path.exists():
        with path.open(newline="") as f:
            for r in csv.DictReader(f):
                rows += 1
                first_seen = pe.parlays._ts(r.get("first_seen"))
                for leg in json.loads(r["legs"]):
                    m = str(leg.get("market") or "?")
                    res = pe.leg_result(con, leg)
                    a = acc[m]
                    if res in ("push", "void"):
                        a["excluded_push_void"] += 1
                        continue
                    if res == "open":
                        a["open"] += 1
                        continue
                    a[res] += 1
                    p = float(leg["prob"])
                    a["_p"].append((p, res == "won"))
                    a["_raw"].append(float(leg["raw_prob"]) if leg.get("raw_prob") is not None else p)
                    mp, src = leg.get("market_prob"), "stored"
                    if mp is None and first_seen is not None:
                        mp, src = _reconstructed_market_prob(con, leg, first_seen), "reconstructed"
                    if mp is not None:
                        a["_mkt"].append(float(mp))
                        a["_mkt_src"][src] += 1
    order = lambda m: (pe.MARKET_ORDER.index(m) if m in pe.MARKET_ORDER else len(pe.MARKET_ORDER), m)
    by_market = {m: _summary(acc[m], m) for m in sorted(acc, key=order)}
    total = _empty()
    for a in acc.values():
        for k in ("won", "lost", "excluded_push_void", "open"):
            total[k] += a[k]
        for k in ("_p", "_raw", "_mkt"):
            total[k] += a[k]
        for s, n in a["_mkt_src"].items():
            total["_mkt_src"][s] += n
    return {"ledger_rows": rows, "by_market": by_market, "overall": _summary(total, None)}


def _summary(a: dict, market: str | None) -> dict:
    n = a["won"] + a["lost"]
    mean = lambda xs: round(sum(xs) / len(xs), 4) if xs else None
    used = mean([p for p, _ in a["_p"]])
    hit = round(a["won"] / n, 4) if n else None
    out = {"label": pe.MARKET_LABELS.get(market, market) if market else "All markets",
           "legs_settled": n, "won": a["won"], "lost": a["lost"],
           "excluded_push_void": a["excluded_push_void"], "open": a["open"],
           "mean_prob_used": used, "mean_raw_prob": mean(a["_raw"]),
           "expected_wins": round(sum(p for p, _ in a["_p"]), 3),
           "hit_rate": hit, "hit_rate_ci95": wilson(a["won"], n),
           "mean_market_prob": mean(a["_mkt"]), "market_prob_n": len(a["_mkt"]),
           "market_prob_source": dict(sorted(a["_mkt_src"].items())),
           "gap_used_minus_hit": None if used is None or hit is None else round(used - hit, 4)}
    return out


# ---------- part 2: weight backtest on stored odds and results ----------
def _loss(p: float, y: int) -> tuple[float, float]:
    p = min(max(p, EPS), 1 - EPS)
    return -(y * math.log(p) + (1 - y) * math.log(1 - p)), (p - y) ** 2


def backtest_samples(con) -> list[dict]:
    """(market, model, market_prob, outcome) for every finished soccer game with a model run stored
    before kick-off and pre-match prices retrieved before kick-off. One side per two-way market (the
    other side is its complement, so it would only double-count): OU over, DNB home (draws excluded,
    a push); all three Double Chance selections."""
    out = []
    events = con.execute("""SELECT event_id, kickoff_utc, home_score, away_score FROM events
                            WHERE sport='football' AND status='finished' AND home_score IS NOT NULL
                            AND away_score IS NOT NULL ORDER BY kickoff_utc, event_id""").fetchall()
    for e in events:
        start = pe.parlays._ts(e["kickoff_utc"])
        if start is None:
            continue
        row = con.execute("""SELECT run_id, MAX(created_at) c FROM predictions WHERE event_id=? AND market='1X2'
                             AND created_at < ? GROUP BY run_id ORDER BY c DESC LIMIT 1""",
                          (e["event_id"], start.isoformat())).fetchone()
        if not row or not row["run_id"]:
            continue
        model = {(r["market"], None if r["line"] is None else float(r["line"]), r["selection"]): float(r["model_prob"])
                 for r in con.execute("SELECT market, selection, line, model_prob FROM predictions WHERE run_id=? "
                                      "AND event_id=?", (row["run_id"], e["event_id"]))}
        one = [model.get(("1X2", None, s)) for s in "HDA"]
        if all(x is not None for x in one):
            from .markets import dc_dnb_from_1x2
            for k, v in dc_dnb_from_1x2(*one).items():
                model.setdefault(k, v)
        books = pe.fresh_books(con, e["event_id"], start - timedelta(seconds=1), start, same_day=False)
        if not books:
            continue
        hg, ag = int(e["home_score"]), int(e["away_score"])
        picks = [("OU", ln, "over") for ln in pe.OU_LINES] + [("DC", None, s) for s in ("HD", "DA", "HA")]
        if hg != ag:
            picks.append(("DNB", None, "home"))
        for mk, ln, s in picks:
            mp = model.get((mk, ln, s))
            q = market_reference(books, mk, ln, s)
            if mp is None or q is None:
                continue
            from .markets import settle_value
            y = 1 if settle_value(mk, s, ln, hg, ag) > 0 else 0
            out.append({"market": mk, "model": mp, "market_prob": q, "y": y, "event_id": e["event_id"]})
    return out


def _grid(samples: list[dict]) -> dict:
    n = len(samples)
    if not n:
        return {"n": 0}
    rows = []
    for w in WEIGHTS:
        ll = br = 0.0
        for s in samples:
            a, b = _loss(w * s["model"] + (1 - w) * s["market_prob"], s["y"])
            ll, br = ll + a, br + b
        rows.append({"w_model": w, "log_loss": round(ll / n, 5), "brier": round(br / n, 5)})
    best = min(rows, key=lambda r: (r["log_loss"], r["w_model"]))
    return {"n": n, "events": len({s["event_id"] for s in samples}),
            "hit_rate": round(sum(s["y"] for s in samples) / n, 4),
            "mean_model": round(sum(s["model"] for s in samples) / n, 4),
            "mean_market": round(sum(s["market_prob"] for s in samples) / n, 4),
            "best_w_model_by_log_loss": best["w_model"],
            "at": {str(r["w_model"]): {"log_loss": r["log_loss"], "brier": r["brier"]}
                   for r in rows if r["w_model"] in (0.0, 0.25, 0.5, 0.75, 1.0) or r is best}}


def weight_backtest(con) -> dict:
    samples = backtest_samples(con)
    by = defaultdict(list)
    for s in samples:
        by[s["market"]].append(s)
    res = {}
    for mk in ("OU", "DC", "DNB"):
        allx = by.get(mk, [])
        opt = [s for s in allx if s["model"] - s["market_prob"] > OPTIMISTIC_GAP]
        res[mk] = {"all": _grid(allx), "model_above_market": _grid(opt)}
    pooled = [s for mk in ("OU", "DC", "DNB") for s in by.get(mk, [])]
    res["pooled"] = {"all": _grid(pooled),
                     "model_above_market": _grid([s for s in pooled if s["model"] - s["market_prob"] > OPTIMISTIC_GAP])}
    res["note"] = ("Finished soccer games in the database with a model run stored before kick-off and pre-match "
                   "prices retrieved before kick-off. BTTS has no stored model run and is not tested.")
    return res


def build(con, now: datetime, path=None) -> dict:
    return {"method": METHOD, "generated": now.isoformat(),
            "leg_rule": {"method": pe.PROB_RULE, "shrink_markets": list(pe.SHRINK_MARKETS),
                         "shrink_model_weight": pe.SHRINK_MODEL_WEIGHT, "max_over_market": pe.MAX_OVER_MARKET},
            "ledger": ledger_calibration(con, path),
            "weight_backtest": weight_backtest(con)}


def write(con, now: datetime, path=None) -> dict:
    rep = build(con, now, path)
    p = out_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rep, indent=1) + "\n")
    return rep
