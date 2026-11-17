"""Walk-forward validation of multi-leg joint probabilities (issue #38, PR B of #35). SHADOW ONLY.

Question: are the joint probabilities Doyen would attach to 2-6-leg parlays (the product of
de-vigged leg probabilities, i.e. the independence assumption) calibrated out of sample?

Method
1. Point-in-time replay. For every recorded scheduled run (`job_runs`, job `publish`) the stored
   database is rebuilt as it was at that moment: only events of that New York day that had not yet
   started, only `pre` quotes retrieved at or before the decision time, only model predictions and
   research notes created by then, scores removed and status reset to scheduled. The live engine
   (`parlay_engine.build_pool`, `search`, `shortlist`) runs on that snapshot UNCHANGED. Nothing
   later than the decision time can reach a leg, a price or a screen.
2. Settlement from final scores in the real database (read-only). Void/postponed legs are dropped
   from leg scoring and make a combination void.
3. Samples (defined before scoring):
   - Legs: each event's first sighting as a screened candidate leg (the selection the engine picks).
   - Synthetic k-leg combinations (k = 2..6): per day, screened legs grouped greedily in kick-off order
     into DISJOINT combinations that pass the live link screens (each leg used once per k).
   - Engine shortlist: every shortlisted candidate's first sighting, event-disjoint per day.
   - Straight-pick backtest (`data/backtest/bets_test.csv`): the same disjoint k-leg grouping, a second,
     older sample (six club soccer leagues).
4. Scoring: log loss, Brier score, reliability by probability bucket, observed versus expected joint
   wins (Poisson-binomial z), per leg count. Predictors compared: the independence product of
   de-vigged market probabilities, the product of stored model probabilities where every leg has one,
   and (shortlist) the product of the slip bookmaker's own implied probabilities.
5. Correlation: residual covariance E[(y_i - p_i)(y_j - p_j)] for same-day leg pairs, split by
   same competition / different competition. Zero is what calibrated independent legs give.
6. Diagnostics for zero-candidate days, including two labelled COUNTERFACTUALS (all quotes treated as
   fresh; the same-competition screen removed). They explain the result; they are never used live
   and no threshold changes.

Pre-registered criteria (`CRITERIA`) are fixed in code before any scoring and are not tuned to the
result. Nothing here publishes, changes a pick, a price, a threshold or the homepage.
"""
from __future__ import annotations

import csv
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from math import prod
from zoneinfo import ZoneInfo

from . import config, db, parlay_calibration, parlays
from . import parlay_engine as pe

METHOD = "parlay-walkforward-v1"
NY = ZoneInfo("America/New_York")
LEG_COUNTS = tuple(range(parlays.MIN_LEGS, parlays.MAX_LEGS + 1))

# Pre-registered: written before the first scoring run and not to be loosened to make a result pass.
# A change needs new out-of-sample evidence and owner review (docs/PARLAYS.md section 9).
CRITERIA = {
    "min_combinations_per_leg_count": 200,   # disjoint settled combinations at that leg count
    "max_abs_joint_z": 1.96,                 # observed joint wins inside the 95% band of the product
    "min_legs": 500,                         # settled screened legs behind the estimates
    "max_abs_leg_z": 1.96,                   # leg probabilities calibrated in the large
    "min_pairs_correlation": 200,            # same-day, different-competition leg pairs
    # residual covariance 95% interval must include 0 for different-competition pairs
}
JOINT_BUCKETS = (0.0, 0.02, 0.05, 0.10, 0.20, 0.35, 0.50, 1.0)
LEG_BUCKETS = (0.30, 0.40, 0.50, 0.60, 0.70, 0.85)
EPS = 1e-6
BOOT = 1000


# ---------- point-in-time snapshot ----------
def decision_times(con, since: str | None = None, until: str | None = None) -> list[datetime]:
    """The moments the scheduled job actually ran (publish job start), in order."""
    rows = con.execute("SELECT DISTINCT started_at FROM job_runs WHERE job='publish' ORDER BY started_at").fetchall()
    out = []
    for (ts,) in rows:
        t = datetime.fromisoformat(ts)
        if (since and t < datetime.fromisoformat(since)) or (until and t > datetime.fromisoformat(until)):
            continue
        out.append(t)
    return out


def snapshot(src, now: datetime, all_fresh: bool = False):
    """In-memory database holding only what was known at `now` for events later that New York day.
    `all_fresh=True` is a COUNTERFACTUAL (diagnostic only): each bookmaker's latest pre-`now` quote is
    re-stamped at `now`, so the freshness screen cannot exclude it."""
    day = pe._day(now)
    end = datetime.fromisoformat(day).replace(tzinfo=NY) + timedelta(days=1)
    lo, hi = now.astimezone(timezone.utc).isoformat(), end.astimezone(timezone.utc).isoformat()
    snap = db.connect(":memory:")
    evs = src.execute("""SELECT event_id, sport, league, season, kickoff_utc, home, away, source
                         FROM events WHERE kickoff_utc > ? AND kickoff_utc < ?""", (lo, hi)).fetchall()
    ids = [e["event_id"] for e in evs]
    for e in evs:
        snap.execute("""INSERT INTO events(event_id,sport,league,season,kickoff_utc,home,away,status,source,updated_at)
                        VALUES (?,?,?,?,?,?,?,'scheduled',?,?)""", (*tuple(e), lo))
    if not ids:
        return snap
    q = ",".join("?" * len(ids))
    has_meta = src.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_meta'").fetchone()
    if has_meta:
        snap.execute("CREATE TABLE IF NOT EXISTS event_meta (event_id TEXT PRIMARY KEY, neutral INTEGER, competition TEXT)")
        snap.executemany("INSERT INTO event_meta(event_id, neutral, competition) VALUES (?,?,?)",
                         [tuple(r) for r in src.execute(
                             f"SELECT event_id, neutral, competition FROM event_meta WHERE event_id IN ({q})", ids)])
    odds = src.execute(f"""SELECT event_id, bookmaker, market, selection, line, price, kind, source, source_url, retrieved_at
                           FROM odds WHERE kind='pre' AND retrieved_at <= ? AND event_id IN ({q})""", (lo, *ids)).fetchall()
    if all_fresh:
        latest = {}
        for r in odds:
            k = (r["event_id"], r["bookmaker"], r["market"], r["selection"], r["line"])
            if k not in latest or r["retrieved_at"] > latest[k]["retrieved_at"]:
                latest[k] = r
        odds = [{**dict(r), "retrieved_at": lo} for r in latest.values()]
    snap.executemany("""INSERT OR IGNORE INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,source_url,retrieved_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?)""",
                     [(r["event_id"], r["bookmaker"], r["market"], r["selection"], r["line"], r["price"], r["kind"],
                       r["source"], r["source_url"], r["retrieved_at"]) for r in odds])
    preds = src.execute(f"""SELECT run_id, event_id, market, selection, line, model_prob, created_at FROM predictions
                            WHERE created_at <= ? AND event_id IN ({q})""", (lo, *ids)).fetchall()
    snap.executemany("""INSERT INTO model_runs(run_id, model_version, league, trained_through, created_at)
                        VALUES (?,?,?,?,?)""", [(r, "replay", "replay", lo, lo) for r in sorted({p["run_id"] for p in preds})])
    snap.executemany("""INSERT INTO predictions(run_id,event_id,market,selection,line,model_prob,created_at)
                        VALUES (?,?,?,?,?,?,?)""", [tuple(p) for p in preds])
    snap.executemany("""INSERT INTO research_notes(event_id,category,claim,evidence_type,created_at) VALUES (?,?,?,?,?)""",
                     [tuple(r) for r in src.execute(
                         f"""SELECT event_id, category, claim, evidence_type, created_at FROM research_notes
                             WHERE created_at <= ? AND event_id IN ({q})""", (lo, *ids))])
    return snap


def _bookmakers_seen(snap, event_id: str, market: str) -> int:
    """Independent owner groups with ANY pre-decision quote on the result market (stale or not)."""
    from .sources.books import group_of, normalize_book
    from .sources.football_data import AGGREGATES
    names = {normalize_book(r[0]) for r in snap.execute(
        "SELECT DISTINCT bookmaker FROM odds WHERE event_id=? AND market=?", (event_id, market))}
    return len({group_of(n) for n in names if n and n not in AGGREGATES})


# ---------- replay ----------
def replay(src, times: list[datetime]) -> dict:
    """Run the live engine at each decision time on its point-in-time snapshot."""
    runs, legs_first, short_first = [], {}, {}
    for t in times:
        snap = snapshot(src, t)
        bp = pe.build_pool(snap, t)
        cands, stats = pe.search(bp["pool"])
        day = pe._day(t)
        for c in cands:
            c["id"] = pe.candidate_id(c, day)
        short = pe.shortlist(cands)
        for leg in bp["best"].values():
            legs_first.setdefault(leg["event_id"], {**leg, "decision_time": t.isoformat(), "date": day,
                                                    "in_pool": leg["best_value"] >= 0})
        for c in short:
            short_first.setdefault(c["id"], {**c, "decision_time": t.isoformat(), "date": day})
        diag = _diagnose(snap, t, bp, stats, cands, short)
        runs.append(diag)
        snap.close()
    return {"runs": runs, "legs": list(legs_first.values()), "shortlist": list(short_first.values())}


def _value_legs_per_book(pool: list[dict]) -> dict:
    c = Counter()
    for leg in pool:
        for bk, v in leg["books"].items():
            if v["value"] >= 0:
                c[bk] += 1
    return dict(c)


def _diagnose(snap, t: datetime, bp: dict, stats: dict, cands: list, short: list) -> dict:
    """Funnel for one decision time, plus structural attribution of the 'too few bookmakers' exclusions."""
    price_reasons = ("too few independent bookmakers", "no fresh result-market prices")
    stale_but_covered = 0
    for e in bp["events"]:
        sp = e["site_sport"]
        if not sp or bp["event_reason"].get(e["event_id"]) not in price_reasons:
            continue
        n_seen = _bookmakers_seen(snap, e["event_id"], pe.RESULT_MARKET[sp])
        if n_seen >= config.RULES.min_bookmakers:
            stale_but_covered += 1
    few = bp["excluded"].get("event: too few independent bookmakers", 0) + \
        bp["excluded"].get("event: no fresh result-market prices", 0)
    vlb = _value_legs_per_book(bp["pool"])
    return {"at": t.isoformat(), "date": pe._day(t), "events": len(bp["events"]),
            "events_by_sport": dict(Counter(e["site_sport"] or e["sport"] for e in bp["events"])),
            "events_with_3plus_groups_any_age": stale_but_covered, "excluded_for_prices": few,
            "excluded": dict(sorted(bp["excluded"].items())), "candidate_legs": len(bp["pool_all"]),
            "pool_legs": len(bp["pool"]), "pool_by_sport": dict(Counter(x["sport"] for x in bp["pool"])),
            "pool_competitions": len({(x["sport"], x["competition"]) for x in bp["pool"]}),
            "books_with_2plus_value_legs": sum(1 for v in vlb.values() if v >= 2),
            "evaluated": stats["evaluated"], "rejected_linked": stats["rejected_linked"],
            "candidates": len(cands), "shortlist": len(short)}


def counterfactuals(src, times: list[datetime]) -> list[dict]:
    """DIAGNOSTIC ONLY (labelled; never used live): how many shortlisted candidates each decision time
    would give if (a) every pre-decision quote counted as fresh, (b) the same-competition screen were
    removed, (c) both. Answers 'structural or rules?'. No live screen or threshold is changed."""
    def no_comp(a, b):
        return [r for r in parlays.correlation_reasons(a, b) if r != "same competition"]
    out = []
    for t in times:
        row = {"at": t.isoformat(), "date": pe._day(t)}
        for fresh in (False, True):
            snap = snapshot(src, t, all_fresh=fresh)
            bp = pe.build_pool(snap, t)
            for label, linked in (("live", None), ("no_same_competition", no_comp)):
                cands, _ = pe.search(bp["pool"], linked=linked)
                for c in cands:
                    c["id"] = pe.candidate_id(c, row["date"])
                key = ("all_fresh+" if fresh else "") + label
                row[key] = len(pe.shortlist(cands))
                if label == "live":
                    row[("all_fresh_" if fresh else "") + "pool_legs"] = len(bp["pool"])
            snap.close()
        out.append(row)
    return out


# ---------- settlement (read-only) ----------
def _outcome(src, event_id: str, market: str, selection: str) -> int | None:
    r = pe._leg_result(src, {"event_id": event_id, "market": market, "selection": selection})
    return {"won": 1, "lost": 0}.get(r)


def settle_legs(src, legs: list[dict]) -> list[dict]:
    out = []
    for leg in legs:
        y = _outcome(src, leg["event_id"], leg["market"], leg["selection"])
        if y is None:
            continue
        out.append({"event_id": leg["event_id"], "date": leg["date"], "sport": leg["sport"],
                    "competition": f"{leg['sport']}|{leg['competition']}", "start": leg["start_utc"],
                    "participants": leg["participants"], "league": leg["league"],
                    "p_market": float(leg["consensus_prob"]),
                    "p_model": None if leg.get("model_prob") is None else float(leg["model_prob"]),
                    "in_pool": leg["in_pool"], "y": y})
    return out


# ---------- grouping ----------
def _link(a: dict, b: dict) -> bool:
    return (a["event_id"] == b["event_id"] or a["competition"] == b["competition"]
            or bool({x.lower() for x in a["participants"]} & {x.lower() for x in b["participants"]}))


def disjoint_groups(legs: list[dict], k: int) -> list[list[dict]]:
    """Per day, greedy in kick-off order: each leg in at most one k-leg group; legs in a group pass the
    live link screens (different games, competitions, no shared team). Deterministic."""
    by_day = defaultdict(list)
    for leg in legs:
        by_day[leg["date"]].append(leg)
    out = []
    for day in sorted(by_day):
        pool = sorted(by_day[day], key=lambda x: (x["start"], x["competition"], x["event_id"]))
        used = [False] * len(pool)
        for i in range(len(pool)):
            if used[i]:
                continue
            grp = [i]
            for j in range(i + 1, len(pool)):
                if not used[j] and all(not _link(pool[j], pool[g]) for g in grp):
                    grp.append(j)
                    if len(grp) == k:
                        break
            if len(grp) == k:
                for g in grp:
                    used[g] = True
                out.append([pool[g] for g in grp])
    return out


def backtest_legs(path=None) -> list[dict]:
    """Straight-pick walk-forward selections (club soccer) in the same leg shape."""
    out = []
    for s in parlay_calibration.load_selections(path):
        out.append({"event_id": s["event"], "date": s["start"].astimezone(NY).date().isoformat(),
                    "sport": "soccer", "competition": f"soccer|{s['league']}", "start": s["start"].isoformat(),
                    "participants": sorted(s["teams"]), "league": s["league"], "p_market": s["prob"],
                    "p_model": None, "in_pool": True, "y": s["won"]})
    return out


# ---------- scoring ----------
def _ll(p: float, y: int) -> float:
    p = min(max(p, EPS), 1 - EPS)
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n == 0:
        return None
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (round(max(0.0, c - h), 4), round(min(1.0, c + h), 4))


def _boot_ci(vals: list[float], seed: int = 0) -> tuple[float, float] | None:
    if len(vals) < 2:
        return None
    rng = random.Random(seed)
    n = len(vals)
    means = sorted(sum(vals[rng.randrange(n)] for _ in range(n)) / n for _ in range(BOOT))
    return (round(means[int(0.025 * BOOT)], 4), round(means[int(0.975 * BOOT) - 1], 4))


def score(preds: list[float], ys: list[int], buckets=JOINT_BUCKETS) -> dict:
    """Log loss, Brier, calibration in the large (z) and reliability buckets, with 95% intervals."""
    n = len(preds)
    if n == 0:
        return {"n": 0}
    ll = [_ll(p, y) for p, y in zip(preds, ys)]
    br = [(p - y) ** 2 for p, y in zip(preds, ys)]
    exp, obs = sum(preds), sum(ys)
    var = sum(p * (1 - p) for p in preds)
    rel = []
    for lo, hi in zip(buckets, buckets[1:]):
        idx = [i for i, p in enumerate(preds) if lo <= p < hi or (hi == buckets[-1] and p == hi)]
        if idx:
            k = sum(ys[i] for i in idx)
            rel.append({"bucket": f"{lo:.2f}-{hi:.2f}", "n": len(idx),
                        "mean_pred": round(sum(preds[i] for i in idx) / len(idx), 4),
                        "observed": round(k / len(idx), 4), "observed_95": wilson(k, len(idx))})
    return {"n": n, "observed_wins": obs, "expected_wins": round(exp, 2),
            "z": None if var <= 0 else round((obs - exp) / math.sqrt(var), 2),
            "log_loss": round(sum(ll) / n, 4), "log_loss_95": _boot_ci(ll, 1),
            "brier": round(sum(br) / n, 4), "brier_95": _boot_ci(br, 2), "reliability": rel}


def score_groups(groups: list[list[dict]]) -> dict:
    """Joint scoring of disjoint combinations: independence product of market probs, and of model probs
    where every leg has one (a smaller subset, scored on the same rows for a fair comparison)."""
    ys = [int(all(x["y"] for x in g)) for g in groups]
    mkt = [prod(x["p_market"] for x in g) for g in groups]
    out = {"combinations": len(groups), "independence_market": score(mkt, ys)}
    sub = [i for i, g in enumerate(groups) if all(x["p_model"] is not None for x in g)]
    if sub:
        out["model_subset"] = {"n": len(sub),
                               "independence_model": score([prod(x["p_model"] for x in groups[i]) for i in sub],
                                                           [ys[i] for i in sub]),
                               "independence_market": score([mkt[i] for i in sub], [ys[i] for i in sub])}
    legs = [x for g in groups for x in g]
    out["legs"] = score([x["p_market"] for x in legs], [x["y"] for x in legs], LEG_BUCKETS)
    out["sports"] = dict(Counter(x["sport"] for x in legs))
    return out


def correlation(legs: list[dict]) -> dict:
    """Residual covariance of same-day leg pairs, by relation. Calibrated independent legs give ~0."""
    by_day = defaultdict(list)
    for leg in legs:
        by_day[leg["date"]].append(leg)
    groups = defaultdict(list)
    for day_legs in by_day.values():
        for i in range(len(day_legs)):
            for j in range(i + 1, len(day_legs)):
                a, b = day_legs[i], day_legs[j]
                if a["event_id"] == b["event_id"]:
                    continue
                shared = {x.lower() for x in a["participants"]} & {x.lower() for x in b["participants"]}
                rel = "shared team" if shared else ("same competition" if a["competition"] == b["competition"]
                                                    else "different competition")
                groups[rel].append((a["y"] - a["p_market"]) * (b["y"] - b["p_market"]))
    out = {}
    for rel in ("same competition", "different competition", "shared team"):
        v = groups.get(rel, [])
        out[rel] = {"pairs": len(v), "mean_residual_cov": round(sum(v) / len(v), 5) if v else None,
                    "cov_95": _boot_ci(v, 3)}
    out["note"] = ("Pairs within a day share legs, so they are not independent: the intervals are optimistic. "
                   "The same-competition pairs are what the live screen excludes.")
    return out


def exclusion_reading(corr: dict) -> str:
    """Plain verdict on the same-competition exclusion, from the measured pairs."""
    sc = corr.get("same competition", {})
    if sc.get("pairs", 0) < CRITERIA["min_pairs_correlation"] or not sc.get("cov_95"):
        return (f"only {sc.get('pairs', 0)} same-competition pairs; the data neither justify nor refute the "
                "same-competition exclusion, so it stays.")
    lo, hi = sc["cov_95"]
    if lo > 0:
        return "same-competition outcomes move together on this sample: the exclusion is supported by the data."
    return (f"no same-competition dependence detected ({sc['pairs']} overlapping pairs, interval {lo:+.4f} to {hi:+.4f}), "
            "but the pairs come from few days and share legs, so this is not evidence of independence; "
            "the exclusion stays until a larger, pre-registered test says otherwise.")


def verdict(groups_by_k: dict, leg_score: dict, corr: dict) -> dict:
    """Apply the pre-registered CRITERIA. 'calibrated' per leg count only if every criterion passes."""
    C, per_k = CRITERIA, {}
    leg_reasons = []
    if leg_score.get("n", 0) < C["min_legs"]:
        leg_reasons.append(f"{leg_score.get('n', 0)} settled legs; {C['min_legs']} required")
    if leg_score.get("z") is None or abs(leg_score["z"]) > C["max_abs_leg_z"]:
        leg_reasons.append("leg probabilities outside the 95% band" if leg_score.get("z") is not None
                           else "no leg outcomes")
    d = corr.get("different competition", {})
    corr_reasons = []
    if d.get("pairs", 0) < C["min_pairs_correlation"]:
        corr_reasons.append(f"{d.get('pairs', 0)} different-competition pairs; {C['min_pairs_correlation']} required")
    elif d.get("cov_95") and not d["cov_95"][0] <= 0 <= d["cov_95"][1]:
        corr_reasons.append("different-competition residual covariance excludes 0")
    for k, g in groups_by_k.items():
        s = g["independence_market"]
        r = []
        if g["combinations"] < C["min_combinations_per_leg_count"]:
            r.append(f"{g['combinations']} combinations; {C['min_combinations_per_leg_count']} required")
        if s.get("z") is None or abs(s["z"]) > C["max_abs_joint_z"]:
            r.append("joint wins outside the 95% band" if s.get("z") is not None else "no joint outcomes")
        per_k[k] = {"calibrated": not (r or leg_reasons or corr_reasons), "reasons": r}
    fit = bool(per_k) and all(v["calibrated"] for v in per_k.values())
    return {"criteria": C, "per_leg_count": per_k, "leg_reasons": leg_reasons, "correlation_reasons": corr_reasons,
            "fit_to_back_recommendation": fit}


def days_needed(groups_by_k: dict, n_days: int) -> dict:
    """At the observed rate, extra replay days needed to reach the combination minimum per leg count."""
    need = CRITERIA["min_combinations_per_leg_count"]
    out = {}
    for k, g in groups_by_k.items():
        per_day = g["combinations"] / n_days if n_days else 0
        out[k] = None if per_day == 0 else max(0, math.ceil((need - g["combinations"]) / per_day))
    return out


# ---------- shortlist scoring ----------
def shortlist_sample(src, short: list[dict]) -> dict:
    """First sighting of each shortlisted candidate, event-disjoint per day (first seen kept)."""
    rows, used = [], defaultdict(set)
    for c in sorted(short, key=lambda c: (c["decision_time"], c["id"])):
        evs = {x["event_id"] for x in c["legs"]}
        if evs & used[c["date"]]:
            continue
        res = [_outcome(src, x["event_id"], x["market"], x["selection"]) for x in c["legs"]]
        if any(r is None for r in res):
            continue
        used[c["date"]] |= evs
        bk = c["bookmaker"]
        rows.append({"n_legs": c["n_legs"], "y": int(all(res)), "p_fair": c["joint_prob_independent"],
                     "p_implied": 1.0 / c["computed_product_odds"], "odds": c["computed_product_odds"],
                     "bookmaker": bk})
    by_k = {}
    for k in LEG_COUNTS:
        rk = [r for r in rows if r["n_legs"] == k]
        if rk:
            by_k[k] = {"leave_one_out_fair": score([r["p_fair"] for r in rk], [r["y"] for r in rk]),
                       "slip_implied": score([r["p_implied"] for r in rk], [r["y"] for r in rk]),
                       "shadow_return_per_unit": round(sum(r["y"] * r["odds"] - 1 for r in rk) / len(rk), 4)}
    return {"settled": len(rows), "by_legs": by_k}


# ---------- shadow ledger (append-only; replay rows kept apart from live sightings) ----------
WF_FIELDS = ("origin", "decision_time", "date", "candidate_id", "bookmaker", "n_legs", "legs", "price_kind",
             "computed_product_odds", "joint_prob_independent", "computed_ev", "method")


def ledger_path():
    return config.ROOT / "ledger" / "parlay_walkforward_shadow.csv"


def record(short: list[dict], path=None) -> int:
    """Append unseen replayed shortlist candidates. Never edits or removes a row. Rows are labelled
    `origin=walk_forward_replay` with the historical decision time; they are not live sightings."""
    path = path or ledger_path()
    seen = set()
    if path.exists():
        with path.open(newline="") as f:
            seen = {r["candidate_id"] for r in csv.DictReader(f)}
    new = []
    for c in sorted(short, key=lambda c: (c["decision_time"], c["id"])):
        if c["id"] in seen:
            continue
        seen.add(c["id"])
        legs = [{"event_id": x["event_id"], "market": x["market"], "selection": x["selection"],
                 "price": x["books"][c["bookmaker"]]["price"]} for x in c["legs"]]
        new.append({"origin": "walk_forward_replay", "decision_time": c["decision_time"], "date": c["date"],
                    "candidate_id": c["id"], "bookmaker": c["bookmaker"], "n_legs": c["n_legs"],
                    "legs": json.dumps(legs), "price_kind": pe.PRICE_KIND,
                    "computed_product_odds": c["computed_product_odds"],
                    "joint_prob_independent": c["joint_prob_independent"], "computed_ev": c["computed_ev"],
                    "method": METHOD})
    if new:
        path.parent.mkdir(parents=True, exist_ok=True)
        header = not path.exists()
        with path.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=WF_FIELDS)
            if header:
                w.writeheader()
            w.writerows(new)
    return len(new)


# ---------- orchestration ----------
def evaluate(src, times: list[datetime], with_counterfactuals: bool = True, bets_path=None) -> dict:
    rep = replay(src, times)
    legs = settle_legs(src, rep["legs"])
    days = sorted({r["date"] for r in rep["runs"]})
    live_by_k = {k: score_groups(disjoint_groups(legs, k)) for k in LEG_COUNTS}
    bt = backtest_legs(bets_path)
    bt_by_k = {k: score_groups(disjoint_groups(bt, k)) for k in LEG_COUNTS}
    leg_score = score([x["p_market"] for x in legs], [x["y"] for x in legs], LEG_BUCKETS)
    corr = correlation(legs)
    per_day = defaultdict(lambda: {"runs": 0, "max_shortlist": 0, "unique_shortlisted": 0, "max_pool": 0})
    for r in rep["runs"]:
        d = per_day[r["date"]]
        d["runs"] += 1
        d["max_shortlist"] = max(d["max_shortlist"], r["shortlist"])
        d["max_pool"] = max(d["max_pool"], r["pool_legs"])
    for c in rep["shortlist"]:
        per_day[c["date"]]["unique_shortlisted"] += 1
    out = {"method": METHOD, "publication": "shadow_only", "price_kind": pe.PRICE_KIND,
           "decision_times": len(times), "days": days,
           "first": times[0].isoformat() if times else None, "last": times[-1].isoformat() if times else None,
           "legs_seen": len(rep["legs"]), "legs_settled": len(legs),
           "legs_settled_by_sport": dict(Counter(x["sport"] for x in legs)),
           "leg_calibration_market": leg_score,
           "leg_calibration_model_subset": _model_leg_subset(legs),
           "leg_calibration_by_sport": {sp: score([x["p_market"] for x in legs if x["sport"] == sp],
                                                  [x["y"] for x in legs if x["sport"] == sp], LEG_BUCKETS)
                                        for sp in sorted({x["sport"] for x in legs})},
           "replay_combinations": {str(k): v for k, v in live_by_k.items()},
           "backtest_combinations": {str(k): v for k, v in bt_by_k.items()},
           "backtest_source": "data/backtest/bets_test.csv (walk-forward test seasons, six club soccer leagues)",
           "correlation": corr, "shortlist": shortlist_sample(src, rep["shortlist"]),
           "shortlisted_unique": len(rep["shortlist"]), "per_day": dict(sorted(per_day.items())),
           "runs": rep["runs"]}
    out["verdict_replay"] = verdict(live_by_k, leg_score, corr)
    out["verdict_backtest"] = verdict(bt_by_k, score([x["p_market"] for x in bt], [x["y"] for x in bt], LEG_BUCKETS),
                                      correlation(bt))
    out["days_needed_replay"] = {str(k): v for k, v in days_needed(live_by_k, len(days)).items()}
    if with_counterfactuals:
        out["counterfactuals"] = counterfactuals(src, times)
    out["_shortlist_rows"] = rep["shortlist"]
    return out


def _model_leg_subset(legs: list[dict]) -> dict:
    sub = [x for x in legs if x["p_model"] is not None]
    return {"n": len(sub), "model": score([x["p_model"] for x in sub], [x["y"] for x in sub], LEG_BUCKETS),
            "market": score([x["p_market"] for x in sub], [x["y"] for x in sub], LEG_BUCKETS)}


def write(src, times: list[datetime] | None = None, record_ledger: bool = False, focus_day: str = "2026-11-16") -> dict:
    times = decision_times(src) if times is None else times
    r = evaluate(src, times)
    short_rows = r.pop("_shortlist_rows")
    if record_ledger:
        r["ledger_rows_added"] = record(short_rows)
    r["focus_day"] = focus_day
    (config.DATA_DIR / "analysis").mkdir(parents=True, exist_ok=True)
    (config.DATA_DIR / "analysis" / "parlay_walkforward.json").write_text(json.dumps(r, indent=1, default=str))
    return {"result": r, "report": _report(r)}


# ---------- report ----------
def _f(x, fmt="{:.4f}"):
    return "n/a" if x is None else fmt.format(x)


def _ci(x):
    return "n/a" if not x else f"{x[0]:.4f} to {x[1]:.4f}"


def _combo_table(by_k: dict) -> list[str]:
    L = ["| Legs | Combinations | Joint wins obs / exp | z | Log loss (95%) | Brier (95%) | Legs z |",
         "|---|---|---|---|---|---|---|"]
    for k in LEG_COUNTS:
        g = by_k[str(k)]
        s, lg = g["independence_market"], g["legs"]
        if not s.get("n"):
            L.append(f"| {k} | 0 | – | – | – | – | – |")
            continue
        L.append(f"| {k} | {g['combinations']} | {s['observed_wins']} / {s['expected_wins']} | {_f(s['z'], '{:+.2f}')} | "
                 f"{s['log_loss']} ({_ci(s['log_loss_95'])}) | {s['brier']} ({_ci(s['brier_95'])}) | {_f(lg.get('z'), '{:+.2f}')} |")
    return L


def _report(r: dict) -> str:
    v, vb = r["verdict_replay"], r["verdict_backtest"]
    L = [f"# Parlay walk-forward validation (shadow) — {r['first'] or 'n/a'} to {r['last'] or 'n/a'}", "",
         f"Developer-only, issue #38 (PR B of #35). Method `{METHOD}`. **Nothing here is published.** Every price is a "
         f"computed product (`{pe.PRICE_KIND}`), never a bookmaker combined quote. No network request, no API credit. "
         "Reproduce with `python -m sbi parlay-walkforward`.", "",
         "## Verdict", ""]
    fit = v["fit_to_back_recommendation"] and vb["fit_to_back_recommendation"]
    L.append(f"- **Joint estimates fit to back a recommendation: {'YES' if fit else 'NO'}.**")
    L.append(f"- Replay ({r['decision_times']} recorded scheduled runs over {len(r['days'])} days, "
             f"{r['legs_settled']} settled screened legs): " +
             ("; ".join(f"{k} legs: {'calibrated' if x['calibrated'] else 'not shown (' + '; '.join(x['reasons'] or ['see leg/correlation reasons']) + ')'}"
                        for k, x in v["per_leg_count"].items())))
    if v["leg_reasons"]:
        L.append(f"- Leg evidence (replay): {'; '.join(v['leg_reasons'])}.")
    if v["correlation_reasons"]:
        L.append(f"- Correlation evidence (replay): {'; '.join(v['correlation_reasons'])}.")
    L.append("- Straight-pick backtest sample (club soccer only): " +
             "; ".join(f"{k} legs: {'calibrated' if x['calibrated'] else '; '.join(x['reasons'] or ['see leg/correlation reasons'])}"
                       for k, x in vb["per_leg_count"].items()))
    if vb["leg_reasons"] or vb["correlation_reasons"]:
        L.append(f"- Backtest leg/correlation evidence: {'; '.join(vb['leg_reasons'] + vb['correlation_reasons'])}.")
    dn = r["days_needed_replay"]
    L.append("- More data needed (replay, at the observed rate of disjoint combinations per day): " +
             ", ".join(f"{k} legs ≈ {'no combinations yet' if dn[str(k)] is None else str(dn[str(k)]) + ' more days'}"
                       for k in LEG_COUNTS) + ".")
    L += ["", "Pre-registered criteria (fixed in `sbi/parlay_walkforward.py` before scoring): " +
          json.dumps(CRITERIA) + ". A leg count is \"calibrated\" only if all hold.", "",
          "## 1. Leg calibration (replay; market de-vigged consensus)", ""]
    ls = r["leg_calibration_market"]
    if ls.get("n"):
        L += [f"- {ls['n']} settled legs ({json.dumps(r['legs_settled_by_sport'])}): wins {ls['observed_wins']} vs "
              f"expected {ls['expected_wins']} (z {_f(ls['z'], '{:+.2f}')}); log loss {ls['log_loss']} ({_ci(ls['log_loss_95'])}); "
              f"Brier {ls['brier']} ({_ci(ls['brier_95'])}).", "",
              "| Probability bucket | n | Mean predicted | Observed (95%) |", "|---|---|---|---|"]
        L += [f"| {b['bucket']} | {b['n']} | {b['mean_pred']} | {b['observed']} ({_ci(b['observed_95'])}) |" for b in ls["reliability"]]
    else:
        L.append("- No settled legs.")
    bs = r.get("leg_calibration_by_sport") or {}
    if bs:
        L += ["", "| Sport | Legs | Wins obs / exp | z | Log loss (95%) | Brier (95%) |", "|---|---|---|---|---|---|"]
        L += [f"| {sp} | {x['n']} | {x['observed_wins']} / {x['expected_wins']} | {_f(x['z'], '{:+.2f}')} | "
              f"{x['log_loss']} ({_ci(x['log_loss_95'])}) | {x['brier']} ({_ci(x['brier_95'])}) |" for sp, x in bs.items()]
    ms = r["leg_calibration_model_subset"]
    if ms["n"]:
        L += ["", f"- Legs with a stored model probability: {ms['n']}. Model log loss {ms['model'].get('log_loss')} vs market "
              f"{ms['market'].get('log_loss')} on the same legs; model Brier {ms['model'].get('brier')} vs market {ms['market'].get('brier')}."]
    L += ["", "## 2. Joint calibration by leg count — replay (independence product of market probabilities)", ""]
    L += _combo_table(r["replay_combinations"])
    sub_lines = []
    for k in LEG_COUNTS:
        m = r["replay_combinations"][str(k)].get("model_subset")
        if m and m["n"]:
            sub_lines.append(f"- {k} legs, {m['n']} combinations with a model probability on every leg: model log loss "
                             f"{m['independence_model'].get('log_loss')} vs market {m['independence_market'].get('log_loss')}.")
    L += [""] + (sub_lines or ["- No combination had a stored model probability on every leg (tennis stores none)."])
    rel2 = r["replay_combinations"]["2"]["independence_market"].get("reliability") or []
    if rel2:
        L += ["", "Reliability, 2-leg replay combinations:", "", "| Joint bucket | n | Mean predicted | Observed (95%) |", "|---|---|---|---|"]
        L += [f"| {b['bucket']} | {b['n']} | {b['mean_pred']} | {b['observed']} ({_ci(b['observed_95'])}) |" for b in rel2]
    L += ["", "## 3. Joint calibration by leg count — straight-pick backtest (club soccer, older sample)", ""]
    L += _combo_table(r["backtest_combinations"])
    L += ["", "## 4. Engine shortlist replay", "",
          f"- Unique shortlisted candidates across all replayed runs: {r['shortlisted_unique']}; settled and event-disjoint "
          f"per day: {r['shortlist']['settled']}."]
    for k, x in r["shortlist"]["by_legs"].items():
        a, b = x["leave_one_out_fair"], x["slip_implied"]
        L.append(f"- {k} legs: n {a['n']}, won {a['observed_wins']} vs expected {a['expected_wins']} (fair) / "
                 f"{b['expected_wins']} (slip implied); log loss fair {a['log_loss']} vs implied {b['log_loss']}; "
                 f"shadow return per unit {x['shadow_return_per_unit']:+.3f} (computed product, not a quote).")
    if r.get("ledger_rows_added") is not None:
        L.append(f"- Appended {r['ledger_rows_added']} new row(s) to `ledger/parlay_walkforward_shadow.csv` "
                 "(append-only, labelled `walk_forward_replay`).")
    c = r["correlation"]
    L += ["", "## 5. Correlation risk (same-day leg pairs; residual covariance, 0 = independent and calibrated)", "",
          "| Relation | Pairs | Mean residual covariance | 95% (optimistic) |", "|---|---|---|---|"]
    for rel in ("same competition", "different competition", "shared team"):
        x = c[rel]
        L.append(f"| {rel} | {x['pairs']} | {_f(x['mean_residual_cov'], '{:+.5f}')} | {_ci(x['cov_95'])} |")
    L += ["", f"{c['note']} Same-day shared-team pairs cannot occur except in back-to-back fixtures.", "",
          f"Reading: {exclusion_reading(c)}", "",
          "## 6. Daily candidates against the 3–5 target (replay; thresholds unchanged)", "",
          "| NY day | Runs | Max pool legs | Max shortlist in one run | Unique shortlisted |", "|---|---|---|---|---|"]
    for d, x in r["per_day"].items():
        L.append(f"| {d} | {x['runs']} | {x['max_pool']} | {x['max_shortlist']} | {x['unique_shortlisted']} |")
    fd = r["focus_day"]
    runs = [x for x in r["runs"] if x["date"] == fd]
    L += ["", f"## 7. Why {fd} gave 0 candidates", ""]
    if runs:
        L += ["| Run (UTC) | Events | By sport | Excluded for prices | Of those, ≥3 groups at any age | Candidate legs | Pool | "
              "Pool by sport | Books with ≥2 value legs | Evaluated | Linked rejects | Shortlist |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for x in runs:
            L.append(f"| {x['at'][11:16]} | {x['events']} | {json.dumps(x['events_by_sport'])} | {x['excluded_for_prices']} | "
                     f"{x['events_with_3plus_groups_any_age']} | {x['candidate_legs']} | {x['pool_legs']} | "
                     f"{json.dumps(x['pool_by_sport'])} | {x['books_with_2plus_value_legs']} | {x['evaluated']} | "
                     f"{x['rejected_linked']} | {x['shortlist']} |")
        ex = Counter()
        for x in runs:
            ex.update(x["excluded"])
        L += ["", f"Exclusion reasons summed over the day's runs: {json.dumps(dict(ex.most_common()))}"]
    else:
        L.append("- No recorded scheduled run on that day in the stored job log.")
    cf = [x for x in r.get("counterfactuals", []) if x["date"] == fd]
    if cf:
        L += ["", "**Counterfactual diagnostics (never used live; no threshold changes):**", "",
              "| Run (UTC) | Live shortlist | All quotes fresh | No same-competition screen | Both | Pool live / all fresh |",
              "|---|---|---|---|---|---|"]
        for x in cf:
            L.append(f"| {x['at'][11:16]} | {x['live']} | {x['all_fresh+live']} | {x['no_same_competition']} | "
                     f"{x['all_fresh+no_same_competition']} | {x['pool_legs']} / {x['all_fresh_pool_legs']} |")
    allcf = r.get("counterfactuals", [])
    if allcf:
        def tot(key):
            by = defaultdict(int)
            for x in allcf:
                by[x["date"]] = max(by[x["date"]], x[key])
            return by
        L += ["", "Best single run per day (all replayed days):", "",
              "| NY day | Live | All quotes fresh | No same-competition screen | Both |", "|---|---|---|---|---|"]
        a, b, cc, dd = tot("live"), tot("all_fresh+live"), tot("no_same_competition"), tot("all_fresh+no_same_competition")
        for d in sorted(a):
            L.append(f"| {d} | {a[d]} | {b[d]} | {cc[d]} | {dd[d]} |")
    L += ["", "Reading: \"all quotes fresh\" measures the timing/coverage share (structural: the multi-bookmaker refresh "
          "versus start times); \"no same-competition screen\" measures the rule share. Removing that screen is NOT "
          "supported unless section 5 shows same-competition outcomes are uncorrelated on an adequate sample.", "",
          "## Limits", "",
          "- The replay covers only the days the database holds multi-bookmaker quotes (the job log starts 2026-11-12). "
          "Samples are small; intervals are wide and, for pairs, optimistic.",
          "- Decision times are the recorded runs of the daily job (`job_runs`, job `publish`), including the extra "
          "runs made on 2026-11-12 while the job was being set up.",
          "- Decision times are the recorded scheduled runs. Event kick-off times are as stored now (a later reschedule "
          "would be visible to the replay). Kick-off-time changes are rare and do not touch prices or outcomes.",
          "- The backtest sample is straight-pick value selections in six club soccer leagues; it says nothing about "
          "NBA, NFL, tennis or international soccer, and its leg probabilities are blended model/market values.",
          "- Void/postponed legs are dropped from scoring; bookmaker void rules are not modelled."]
    out = config.REPORTS_DIR / "parlay_walkforward.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n")
    return str(out)
