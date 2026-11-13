"""Bookmaker-independence audit: what the staged rule v2 ("verified") would change, measured.

`python -m sbi independence` reads the database READ-ONLY and writes
  data/independence/latest.json and reports/independence_audit.md
(developer reports; nothing here is shown on the public site, and nothing is published,
edited or settled by this module).

It answers, with the stored data and nothing invented:
  * which bookmakers are verified operators, which are not, and on what evidence (the registry);
  * how many upcoming markets clear the 3-bookmaker gate under rule v1 (legacy: an unmapped
    bookmaker counts as its own operator) and under rule v2 (verified operators only);
  * how many price-rule candidates that v1 would let through v2 would block, with 95% limits;
  * what v2 would have said about each pick already published (they are NOT changed);
  * which bookmaker pairs quote identical prices, as empirical evidence of shared pricing.

`python -m sbi independence --history` additionally replays the walk-forward backtest's test
seasons under both rules (downloads football-data.co.uk files; several minutes) and stores
data/independence/history.json, which later reports include.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timedelta
from itertools import combinations

from . import config
from . import ev as evm
from .coverage import SPORT_NAMES, connect_ro
from .engine import SELECTIONS, UNVERIFIED_REASON, books_from_rows, passes_under, price_generic
from .markets import Outcome
from .sources import books as bk
from .sources.football_data import AGGREGATES

OUT_DIR = "independence"
HISTORY_FILE = "history.json"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """95% Wilson score interval for a proportion k/n (None when there is nothing to estimate)."""
    if n <= 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(0.0, c - h), 4), round(min(1.0, c + h), 4))


def _share(k: int, n: int) -> dict:
    return {"blocked": k, "of": n, "share": round(k / n, 4) if n else None, "ci95": wilson(k, n)}


def registry() -> list[dict]:
    return [{"bookmaker": name, "operator": b.group, "verified": b.verified, "owner": b.owner,
             "price_origin": b.pricing, "source": b.source, "owner_source": b.owner_source,
             "evidence": b.evidence, "source_opened": b.opened, "checked": b.checked, "note": b.note}
            for name, b in sorted(bk.REGISTRY.items())]


def _no_push(market: str, line) -> bool:
    """Markets where the whole stake is always won or lost, so EV needs no model for the push share."""
    return market in ("1X2", "ML", "BTTS") or (line is not None and abs((float(line) * 2) % 2 - 1) < 1e-9)


def _upcoming(con, now: datetime, horizon_h: float):
    return con.execute("""SELECT event_id, sport, league FROM events WHERE status='scheduled'
                          AND kickoff_utc > ? AND kickoff_utc <= ? ORDER BY kickoff_utc""",
                       (now.isoformat(), (now + timedelta(hours=horizon_h)).isoformat())).fetchall()


def upcoming_impact(con, now: datetime, horizon_h: float = 168) -> dict:
    """Gate counts and a price-rule replay on the fresh quotes of every upcoming event.

    The replay prices each market at blend weight 0 (value = best price versus the leave-one-out
    market reference), which is what is deployed while every fitted blend weight is ~0. It assumes
    team history is sufficient and applies no disagreement review or daily cap, so it is an UPPER
    bound on what rule v1 would publish; the comparison between the rules is like for like."""
    from .pipeline import _latest_books            # the same freshness filter the live pipeline uses
    rules = config.RULES
    flat = Outcome(pw=0.5, pl=0.5)                 # active = 1; with weight 0 the model share is unused
    per: dict = defaultdict(lambda: {"markets": 0, "markets_v1_3plus": 0, "markets_v2_3plus": 0,
                                     "events_priced": 0, "events_v1_3plus": 0, "events_v2_3plus": 0,
                                     "cand_v1": 0, "cand_v2": 0, "cand_v1_no_push": 0, "cand_v2_no_push": 0,
                                     "events_v1": 0, "events_v2": 0})
    blocked, reasons = [], defaultdict(int)
    for e in _upcoming(con, now, horizon_h):
        books, _ts, _urls = _latest_books(con, e["event_id"], rules.max_odds_age_hours, now)
        s = per[SPORT_NAMES.get(e["sport"], e["sport"])]
        n1 = n2 = 0
        for (market, line), book in books.items():
            if market not in SELECTIONS:
                continue
            book = evm.clean(book, SELECTIONS[market])
            if not book:
                continue
            s["markets"] += 1
            a, b = evm.n_books(book, SELECTIONS[market]), evm.n_books_verified(book, SELECTIONS[market])
            n1, n2 = max(n1, a), max(n2, b)
            s["markets_v1_3plus"] += a >= rules.min_bookmakers
            s["markets_v2_3plus"] += a >= rules.min_bookmakers and b >= rules.min_bookmakers
        if books:
            s["events_priced"] += 1
            s["events_v1_3plus"] += n1 >= rules.min_bookmakers
            s["events_v2_3plus"] += n2 >= rules.min_bookmakers
        ev1 = ev2 = False
        for c in price_generic(lambda m, sel, ln: flat, books, {}, rules.exchange_commission, policy="legacy"):
            if not passes_under(c, "legacy", rules, True)[0]:
                continue
            ok2, why = passes_under(c, "verified", rules, True)
            exact = _no_push(c.market, c.line)
            s["cand_v1"] += 1
            s["cand_v2"] += ok2
            s["cand_v1_no_push"] += exact
            s["cand_v2_no_push"] += exact and ok2
            ev1, ev2 = True, ev2 or ok2
            if not ok2:
                reasons[why] += 1
                v2 = c.views["verified"]
                blocked.append({"event_id": e["event_id"], "sport": SPORT_NAMES.get(e["sport"], e["sport"]),
                                "market": c.market, "selection": c.selection, "line": c.line,
                                "bookmaker": c.bookmaker, "odds": c.odds, "ev_v1": round(c.ev, 4),
                                "ev_v2": None if v2["market_q"] is None else round(v2["ev"], 4),
                                "books_v1": c.n_books, "operators_v2": v2["n_books"],
                                "reference_v1": c.consensus_src, "reference_v2": v2["consensus_src"],
                                "price_book_verified": bk.verified_group(c.bookmaker) is not None,
                                "unverified_books": list(c.unverified_books), "blocked_because": why})
        s["events_v1"] += ev1
        s["events_v2"] += ev2
    tot = defaultdict(int)
    for s in per.values():
        for k, v in s.items():
            tot[k] += v
    out = {"by_sport": {k: dict(v) for k, v in sorted(per.items())}, "total": dict(tot)}
    out["blocked_share"] = {
        "markets_at_gate": _share(tot["markets_v1_3plus"] - tot["markets_v2_3plus"], tot["markets_v1_3plus"]),
        "events_at_gate": _share(tot["events_v1_3plus"] - tot["events_v2_3plus"], tot["events_v1_3plus"]),
        "price_rule_candidates": _share(tot["cand_v1"] - tot["cand_v2"], tot["cand_v1"]),
        "price_rule_candidates_no_push": _share(tot["cand_v1_no_push"] - tot["cand_v2_no_push"], tot["cand_v1_no_push"]),
        "price_rule_events": _share(tot["events_v1"] - tot["events_v2"], tot["events_v1"]),
    }
    out["blocked_reasons"] = dict(reasons)
    out["blocked_candidates"] = blocked
    return out


def published_review(con) -> list[dict]:
    """What rule v2 says about each pick already published, from the prices stored WITH the pick.
    Read-only: the recommendation, its odds and its status are never touched."""
    rules, out = config.RULES, []
    for r in con.execute("""SELECT rec_id, event_id, published_at, sport, home, away, market, selection, line,
                                   bookmaker, odds, ev, model_version, evidence_json
                            FROM recommendations ORDER BY published_at, rec_id"""):
        ev_ = json.loads(r["evidence_json"] or "{}")
        raw = ev_.get("all_prices") or {}
        if r["market"] not in SELECTIONS or not raw:
            out.append({"rec_id": r["rec_id"], "reviewable": False})
            continue
        rows = [(r["market"], r["line"], bk.normalize_book(name), sel, px)
                for name, q in raw.items() for sel, px in q.items() if bk.normalize_book(name)]
        book = evm.clean(books_from_rows(rows).get((r["market"], r["line"]), {}), SELECTIONS[r["market"]])
        sels = SELECTIONS[r["market"]]
        price_book = bk.normalize_book(r["bookmaker"])
        ref, src = evm.consensus_verified_excluding(book, sels, price_book)
        active = float(ev_.get("stake_share_active", 1.0))
        net = float(ev_.get("net_odds", r["odds"]))
        market_only = float(ev_.get("blend_weight") or 0.0) < 0.01
        ev2 = active * (ref[r["selection"]] * net - 1) if ref and market_only else None
        n2 = evm.n_books_verified(book, sels)
        if n2 < rules.min_bookmakers:
            verdict = UNVERIFIED_REASON
        elif ref is None:
            verdict = "no market consensus"
        elif ev2 is None:
            verdict = "not recomputable (model-weighted pick)"
        else:
            verdict = "ok" if ev2 >= rules.min_ev else "EV below threshold"
        out.append({"rec_id": r["rec_id"], "reviewable": True, "published_at": r["published_at"],
                    "event": f"{r['home']} v {r['away']}", "market": r["market"], "selection": r["selection"],
                    "bookmaker": r["bookmaker"], "odds": r["odds"], "model_version": r["model_version"],
                    "price_book_verified": bk.verified_group(price_book) is not None,
                    "names_stored": len(raw), "books_v1": evm.n_books(book, sels), "operators_v2": n2,
                    "bookmakers_recorded_at_publication": ev_.get("n_bookmakers"),
                    "unverified_books": evm.unverified_books(book, sels),
                    "reference_v2": src, "ev_published": round(r["ev"], 4),
                    "ev_v2": None if ev2 is None else round(ev2, 4), "v2_verdict": verdict})
    return out


def price_identity(con, min_shared: int = 20) -> list[dict]:
    """How often two bookmakers' latest stored quotes for the same market are IDENTICAL.

    Measured on three-way 1X2 markets only (three prices must all match, so a coincidence is
    unlikely; two-way lines at standard prices coincide by convention). A high share is evidence
    of a shared price feed; a low share is NOT proof of independence."""
    latest: dict = {}
    for r in con.execute("""SELECT event_id, bookmaker, selection, price, retrieved_at FROM odds
                            WHERE kind='pre' AND market='1X2'"""):
        b = bk.normalize_book(r["bookmaker"])
        if not b or b in AGGREGATES:
            continue
        k = (r["event_id"], b, r["selection"])
        if k not in latest or r["retrieved_at"] > latest[k][1]:
            latest[k] = (round(float(r["price"]), 3), r["retrieved_at"])
    quotes: dict = defaultdict(dict)
    for (eid, b, sel), (px, _) in latest.items():
        quotes[(eid, b)][sel] = px
    by_event: dict = defaultdict(dict)
    for (eid, b), q in quotes.items():
        if all(s in q for s in SELECTIONS["1X2"]):
            by_event[eid][b] = tuple(q[s] for s in SELECTIONS["1X2"])
    shared, same = defaultdict(int), defaultdict(int)
    for q in by_event.values():
        for a, b in combinations(sorted(q), 2):
            shared[(a, b)] += 1
            same[(a, b)] += q[a] == q[b]
    out = []
    for (a, b), n in shared.items():
        if n < min_shared:
            continue
        ga, gb = bk.verified_group(a), bk.verified_group(b)
        out.append({"a": a, "b": b, "shared_markets": n, "identical": same[(a, b)],
                    "identical_share": round(same[(a, b)] / n, 4), "ci95": wilson(same[(a, b)], n),
                    "same_verified_operator": bool(ga and ga == gb),
                    "both_verified": bool(ga and gb)})
    return sorted(out, key=lambda r: (-r["identical_share"], -r["shared_markets"], r["a"], r["b"]))


def history(leagues=("E0", "E1", "SP1", "D1", "I1", "F1"), test=("2425", "2526", "2627"),
            seasons=("2122", "2223", "2324", "2425", "2526", "2627")) -> dict:
    """Walk-forward replay of the backtest's TEST seasons under both rules (market-only strategy,
    the deployed one while blend weights are ~0). Same models, prices and thresholds; only the
    independence policy differs. Network: football-data.co.uk season files."""
    import pandas as pd

    from . import backtest
    config.load_tuned()
    out, frames = {"leagues": list(leagues), "test_seasons": list(test), "xi": config.MODEL.xi,
                   "ridge": config.MODEL.ridge, "strategy": "market_only (blend weight 0)"}, {}
    data = {div: backtest.load_league(div, list(seasons)) for div in leagues}
    for policy in config.INDEPENDENCE_POLICIES:
        bets = []
        for div, (m, o) in data.items():
            _, b = backtest.walk_forward(div, m, o, test[0], config.MODEL.xi, config.MODEL.ridge,
                                         blend_w={"1X2": 0.0, "OU": 0.0, "AH": 0.0}, rules=config.RULES,
                                         n_draws=0, policy=policy)
            bets += b
        frames[policy] = pd.DataFrame(bets)
        out[policy] = backtest.evaluate_bets(frames[policy])
    key = ["event", "div", "market", "selection", "line", "bookmaker"]
    v1, v2 = frames["legacy"], frames["verified"]
    if v1.empty:
        out["comparison"] = {"bets_v1": 0}
        return out
    kept = set(map(tuple, v2[key].astype(str).values)) if not v2.empty else set()
    is_kept = [tuple(x) in kept for x in v1[key].astype(str).values]
    gone = v1[[not k for k in is_kept]]
    events_v2 = set(zip(v2["div"], v2["event"])) if not v2.empty else set()
    lost_events = {(d, e) for d, e in zip(v1["div"], v1["event"])} - events_v2
    out["comparison"] = {
        "bets_v1": int(len(v1)), "bets_v2": int(len(v2)),
        "identical_bets": int(sum(is_kept)),
        "v1_bets_not_made_under_v2": _share(int(len(gone)), int(len(v1))),
        "v1_events_with_no_bet_under_v2": _share(len(lost_events), len(set(zip(v1["div"], v1["event"])))),
        "v2_bets_not_in_v1": int(len(v2) - sum(is_kept)),
        "removed_bets": backtest.evaluate_bets(gone) if len(gone) else {"n_bets": 0},
        "removed_by_price_bookmaker": {k: int(v) for k, v in gone["bookmaker"].value_counts().items()} if len(gone) else {},
    }
    return out


def build(con, now: datetime, horizon_h: float = 168) -> dict:
    reg = registry()
    hist_path = config.DATA_DIR / OUT_DIR / HISTORY_FILE
    return {
        "generated_at": now.isoformat(), "horizon_hours": horizon_h,
        "deployed_policy": config.RULES.independence_policy,
        "rule_versions": config.INDEPENDENCE_RULE_VERSION, "min_bookmakers": config.RULES.min_bookmakers,
        "registry": reg,
        "registry_summary": {"bookmakers": len(reg), "verified": sum(r["verified"] for r in reg),
                             "unverified": sum(not r["verified"] for r in reg),
                             "verified_operators": len({r["operator"] for r in reg if r["verified"]})},
        "upcoming": upcoming_impact(con, now, horizon_h),
        "published": published_review(con),
        "price_identity": price_identity(con),
        "history": json.loads(hist_path.read_text()) if hist_path.exists() else None,
    }


def _pct(x) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def _ci(s: dict) -> str:
    if not s["of"]:
        return "0 of 0 (nothing to measure)"
    return f"**{s['blocked']} of {s['of']}** ({_pct(s['share'])}; 95% limits {_pct(s['ci95'][0])} to {_pct(s['ci95'][1])})"


def render(rep: dict) -> str:
    live = rep["deployed_policy"]
    up, rs = rep["upcoming"], rep["registry_summary"]
    L = [f"# Bookmaker independence audit ({rep['generated_at'][:16].replace('T', ' ')} UTC)", "",
         "Generated by `python -m sbi independence` from the stored database (read-only). "
         "Developer report; see docs/METHODOLOGY.md, section *Bookmaker independence*.", "",
         f"**Deployed rule: {rep['rule_versions'][live]} (`{live}`).** "
         + ("Rule v2 is **staged**: it is computed for every candidate and reported here, but it does not "
            "decide what is published." if live == "legacy" else
            "Rule v2 decides what is published. Picks published before the switch are unchanged."), "",
         "- **Rule v1 (legacy):** a bookmaker missing from the ownership map counts as its own operator.",
         f"- **Rule v2 (verified):** only operators verified in `sbi/sources/books.py` count toward the "
         f"{rep['min_bookmakers']}-bookmaker gate, the leave-one-out reference uses only them (one vote per "
         "operator), and every v1 check must still pass. It can block a v1 pick and can never add one.",
         "- Unverified bookmakers stay in monitoring, the watchlist and the best-price search under both rules.", "",
         "## Impact on upcoming markets", "",
         f"Fresh stored quotes for events starting in the next {rep['horizon_hours']:.0f} hours.", "",
         "| Sport | Events priced | Events with 3+ (v1) | Events with 3+ (v2) | Markets | Markets 3+ (v1) | Markets 3+ (v2) | "
         "Price-rule candidates (v1) | Still eligible (v2) |", "|---|---|---|---|---|---|---|---|---|"]
    for sport, s in up["by_sport"].items():
        L.append(f"| {sport} | {s['events_priced']} | {s['events_v1_3plus']} | {s['events_v2_3plus']} | {s['markets']} | "
                 f"{s['markets_v1_3plus']} | {s['markets_v2_3plus']} | {s['cand_v1']} | {s['cand_v2']} |")
    b = up["blocked_share"]
    L += ["",
          f"- Markets that clear the bookmaker-count gate under v1 but not under v2: {_ci(b['markets_at_gate'])}.",
          f"- Events with at least one such market under v1 but none under v2: {_ci(b['events_at_gate'])}.",
          f"- Price-rule candidates v1 would let through that v2 blocks: {_ci(b['price_rule_candidates'])}.",
          f"- The same, counting only markets that cannot push (exact without a model): {_ci(b['price_rule_candidates_no_push'])}.",
          f"- Events with a v1 candidate and no v2 candidate: {_ci(b['price_rule_events'])}.",
          "- *Price-rule candidates* are prices that pass the bookmaker count, market reference, odds range and "
          "EV threshold at blend weight 0. Team-history checks, the disagreement review and the daily cap are not "
          "applied, so the v1 figure is an upper bound on published picks, not a forecast of them.",
          "- The limits are 95% Wilson intervals for this one snapshot. Candidates from the same event or the same "
          "bookmaker are correlated, so the true uncertainty is wider than the interval shows.", ""]
    if up["blocked_reasons"]:
        L += ["Why v2 blocks them: " + "; ".join(f"{k}: {v}" for k, v in sorted(up["blocked_reasons"].items())) + ".", ""]
    if up["blocked_candidates"]:
        L += ["| Event | Market | Price at | Odds | EV v1 | EV v2 | Books v1 | Operators v2 | Blocked because |",
              "|---|---|---|---|---|---|---|---|---|"]
        for c in up["blocked_candidates"][:40]:
            mk = f"{c['market']} {c['selection']}" + ("" if c["line"] is None else f" {c['line']:+g}")
            L.append(f"| {c['event_id']} | {mk} | {c['bookmaker']}{'' if c['price_book_verified'] else ' (unverified)'} | "
                     f"{c['odds']:.2f} | {_pct(c['ev_v1'])} | {_pct(c['ev_v2'])} | {c['books_v1']} | {c['operators_v2']} | "
                     f"{c['blocked_because']} |")
        if len(up["blocked_candidates"]) > 40:
            L.append(f"\n({len(up['blocked_candidates']) - 40} more in data/independence/latest.json.)")
        L.append("")
    L += ["## Picks already published (not changed)", "",
          "Recomputed from the prices stored with each pick. This is a review only: published picks, their odds "
          "and their status are never edited.", ""]
    pub = [p for p in rep["published"] if p.get("reviewable")]
    if pub:
        n_block = sum(p["v2_verdict"] != "ok" for p in pub)
        L += ["| Published | Event | Pick | Price at | Books v1 | Operators v2 | EV published | EV v2 | Under v2 |",
              "|---|---|---|---|---|---|---|---|---|"]
        for p in pub:
            L.append(f"| {p['published_at'][:16].replace('T', ' ')} | {p['event']} | {p['market']} {p['selection']} @ {p['odds']:.2f} | "
                     f"{p['bookmaker']}{'' if p['price_book_verified'] else ' (unverified)'} | {p['books_v1']} | "
                     f"{p['operators_v2']} | {_pct(p['ev_published'])} | {_pct(p['ev_v2'])} | {p['v2_verdict']} |")
        L += ["", f"Rule v2 would not have published {_ci(_share(n_block, len(pub)))} of these. "
                  "With so few picks the interval is very wide; treat it as a description, not an estimate.", ""]
    else:
        L += ["No published pick has stored prices to review.", ""]
    h = rep.get("history")
    L += ["## Historical replay (walk-forward test seasons)", ""]
    if h and h.get("comparison", {}).get("bets_v1"):
        c = h["comparison"]
        L += [f"Leagues {', '.join(h['leagues'])}; test seasons {', '.join(h['test_seasons'])}; {h['strategy']}; "
              f"run {h.get('generated_at', '')[:10]}. Same models, prices and thresholds under both rules.", "",
              "| Rule | Bets | ROI | ROI 95% limits | Average CLV | CLV 95% limits |", "|---|---|---|---|---|---|"]
        for name, key in (("v1 (legacy)", "legacy"), ("v2 (verified)", "verified"), ("Bets v2 removes", None)):
            m = h[key] if key else c["removed_bets"]
            if not m.get("n_bets"):
                L.append(f"| {name} | 0 | n/a | n/a | n/a | n/a |")
                continue
            L.append(f"| {name} | {m['n_bets']} | {_pct(m['roi'])} | {_pct(m['roi_ci95'][0])} to {_pct(m['roi_ci95'][1])} | "
                     f"{_pct(m.get('avg_clv'))} | " + (f"{_pct(m['clv_ci95'][0])} to {_pct(m['clv_ci95'][1])} |"
                                                       if "clv_ci95" in m else "n/a |"))
        L += ["", f"- v1 bets that v2 would not make: {_ci(c['v1_bets_not_made_under_v2'])}.",
              f"- v1 events left with no bet under v2: {_ci(c['v1_events_with_no_bet_under_v2'])}.",
              f"- Bets under v2 that v1 did not make: **{c['v2_bets_not_in_v1']}** (v2 can only pick a different "
              "market of an event v1 already bet; it cannot add an event).",
              "- This history is football-data.co.uk club football, whose bookmakers are mostly large verified "
              "operators. It says little about The Odds API markets, where most unverified bookmakers appear.",
              "- It is a fresh replay on the season files as downloaded on the run date, so its bet count differs "
              "from the older run stored in data/backtest/report.json. The two rules are compared within this one run.", ""]
        if c["removed_by_price_bookmaker"]:
            L += ["Removed bets by the bookmaker whose price was taken: "
                  + ", ".join(f"{k} {v}" for k, v in c["removed_by_price_bookmaker"].items()) + ".", ""]
    else:
        L += ["Not run for this report. Run `python -m sbi independence --history` (needs network access to "
              "football-data.co.uk).", ""]
    L += ["## Identical prices between bookmakers (measured)", "",
          "Share of three-way 1X2 markets where two bookmakers' latest stored quotes are identical on all three "
          "prices (pairs with at least 20 shared markets). A high share is evidence of a shared price feed. "
          "A low share is not proof of independence.", "",
          "| Bookmaker A | Bookmaker B | Shared markets | Identical | Share | 95% limits | Same verified operator |",
          "|---|---|---|---|---|---|---|"]
    top = [p for p in rep["price_identity"] if p["identical_share"] >= 0.10 or p["same_verified_operator"]][:30]
    for p in top:
        L.append(f"| {p['a']} | {p['b']} | {p['shared_markets']} | {p['identical']} | {_pct(p['identical_share'])} | "
                 f"{_pct(p['ci95'][0])} to {_pct(p['ci95'][1])} | {'yes' if p['same_verified_operator'] else 'no'} |")
    if not top:
        L.append("| (no pair reaches a 10% identical share) | | | | | | |")
    L += ["", f"## Bookmaker registry ({rs['bookmakers']} names: {rs['verified']} verified in "
              f"{rs['verified_operators']} operators, {rs['unverified']} unverified)", "",
          "*Operator* is the unit that counts once under rule v2: brands sharing an owner or a price origin are "
          "merged. A bookmaker that is not listed here at all is treated as unverified.", "",
          "*Evidence* is the best grade among the citations. *Read* says whether the cited page was opened "
          "and read, or blocked automated reading and was seen only as a search-result summary: those rows are "
          "the weakest and should be re-checked by a person before rule v2 goes live.", "",
          "| Bookmaker | Verified | Operator (counts once) | Owner | Price origin | Evidence | Read | Checked | Source |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in rep["registry"]:
        L.append(f"| {r['bookmaker']} | {'yes' if r['verified'] else 'NO'} | {r['operator'] if r['verified'] else '(not counted)'} | "
                 f"{r['owner']} | {r['price_origin']} | {r['evidence']} | {'opened' if r['source_opened'] else 'summary only'} | "
                 f"{r['checked']} | {r['source'] or r['owner_source'] or 'none found'} |")
    notes = [r for r in rep["registry"] if r["note"]]
    if notes:
        L += ["", "Notes:"] + [f"- **{r['bookmaker']}:** {r['note']}" for r in notes]
    return "\n".join(L) + "\n"


def write(now: datetime, db_path=None, horizon_h: float = 168, with_history: bool = False) -> dict:
    out = config.DATA_DIR / OUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    if with_history:
        h = history()
        h["generated_at"] = now.isoformat()
        (out / HISTORY_FILE).write_text(json.dumps(h, indent=1, default=str) + "\n")
    con = connect_ro(db_path)
    try:
        rep = build(con, now, horizon_h)
    finally:
        con.close()
    (out / "latest.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (config.REPORTS_DIR / "independence_audit.md").write_text(render(rep))
    return rep
