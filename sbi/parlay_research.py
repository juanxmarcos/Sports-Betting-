"""Parlay research report (issue #33): what stops a real daily parlay, measured from stored data.

Writes reports/parlay_research.md and data/analysis/parlay_calibration.json. Read-only with
respect to picks, odds and the ledgers; it makes no network request.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
from itertools import combinations
from zoneinfo import ZoneInfo

from . import config, parlay_calibration, parlay_quotes, parlays

NY = ZoneInfo("America/New_York")

# Combined-quote source audit. Pages read 2026-11-16 (automated fetch; short fragments, not legal advice).
SOURCES = [
    ("The Odds API (in use, free 500 credits/month)", "no combined price",
     "Endpoints return single-market outcomes only (sports, odds, scores, events, event odds, markets, "
     "participants; historical on paid plans). No parlay or bet-builder endpoint.",
     "https://the-odds-api.com/liveapi/guides/v4/"),
    ("ESPN public JSON (in use)", "no combined price", "One moneyline/spread/total per event from one provider.", None),
    ("football-data.co.uk (in use)", "no combined price", "Historical single-market closing/opening odds files.", None),
    ("OpticOdds Parlay API (POST /parlay/odds)", "paid, not enabled",
     "Prices parlays across sportsbooks, but needs a licence key obtained by contacting sales; no public price "
     "or free tier found.", "https://developer.opticodds.com/reference/post_parlay-odds"),
    ("OddsBlaze same-game-parlay endpoint", "paid, not enabled",
     "Sportsbook-specific SGP prices (DraftKings, FanDuel, Fanatics ...). Third-party review: Plan 1 $299/month, "
     "'does not offer a free tier'.", "https://sportsapis.dev/apis/oddsblaze"),
    ("SportsGameOdds", "no combined price", "Leg odds as building blocks; the combined price is computed by the client, "
     "which is exactly the product Doyen may not present as a quote.",
     "https://sportsgameodds.com/use-cases/parlay-builder-api"),
    ("Bookmaker bet slips (websites/apps)", "owner manual entry only",
     "The only no-cost source of a real combined price. Automated reading of bet slips (scraping) is not "
     "acceptable; the owner can record a slip price with `python -m sbi parlay-quote`.", None),
]


def _days_scarcity(con) -> dict:
    rows = [dict(r) for r in con.execute(
        "SELECT rec_id, event_id, league, home, away, kickoff_utc, bookmaker FROM recommendations")]
    by_day = defaultdict(list)
    for r in rows:
        by_day[datetime.fromisoformat(r["kickoff_utc"]).astimezone(NY).date().isoformat()].append(r)
    days = []
    for d in sorted(by_day):
        rs = by_day[d]
        pairs = list(combinations(rs, 2))
        strict = [p for p in pairs if p[0]["event_id"] != p[1]["event_id"] and p[0]["league"] != p[1]["league"]
                  and not ({p[0]["home"], p[0]["away"]} & {p[1]["home"], p[1]["away"]})]
        loose = [p for p in pairs if p[0]["event_id"] != p[1]["event_id"]
                 and not ({p[0]["home"], p[0]["away"]} & {p[1]["home"], p[1]["away"]})]
        days.append({"date": d, "picks": len(rs), "competitions": len({r["league"] for r in rs}),
                     "bookmakers": len({r["bookmaker"] for r in rs}),
                     "pairs_current_screens": len(strict), "pairs_if_same_competition_allowed": len(loose)})
    return {"total_picks": len(rows), "days": days}


def _shadow_summary(con) -> dict:
    path = config.ROOT / "ledger" / "parlay_shadow.csv"
    if not path.exists():
        return {"rows": 0, "won": 0, "lost": 0, "open": 0}
    status = {r["rec_id"]: r["status"] for r in con.execute("SELECT rec_id, status FROM recommendations")}
    out = {"rows": 0, "won": 0, "lost": 0, "open": 0}
    with path.open(newline="") as f:
        for r in csv.DictReader(f):
            out["rows"] += 1
            st = [status.get(i) for i in json.loads(r["legs"])]
            if any(s in ("lost", "half_lost") for s in st):
                out["lost"] += 1
            elif st and all(s == "won" for s in st):
                out["won"] += 1
            else:
                out["open"] += 1
    return out


def build(con, now: datetime) -> dict:
    from . import site
    legs = site.parlay_legs(con, now)
    cal = parlay_calibration.evaluate()
    block = parlays.build(legs, now, quotes=parlay_quotes.load(), calibration=cal)
    return {"generated": now.isoformat(), "calibration": cal, "today": block["audit"], "status": block["status"],
            "blockers": [b["key"] for b in block["blockers"]], "scarcity": _days_scarcity(con),
            "shadow": _shadow_summary(con), "quotes_recorded": len(parlay_quotes.load()),
            "usable_legs": [{"id": leg["id"], "title": leg.get("title"), "selection": leg.get("selection_label"),
                             "start_utc": leg["start_utc"]} for leg in legs]}


def write(con, now: datetime):
    r = build(con, now)
    (config.DATA_DIR / "analysis").mkdir(parents=True, exist_ok=True)
    (config.DATA_DIR / "analysis" / "parlay_calibration.json").write_text(json.dumps(r["calibration"], indent=1))
    c, t, s = r["calibration"], r["today"], r["scarcity"]
    L = [f"# Parlay research — {now.astimezone(NY):%Y-%m-%d %H:%M} New York", "",
         f"Status: **{r['status']}**. Open gates: {', '.join(r['blockers']) or 'none'}.", "",
         "## 1. Combined-quote sources (pages read 2026-11-16)", "",
         "| Source | Status | Finding | Link |", "|---|---|---|---|"]
    L += [f"| {a} | {b} | {x} | {u or '—'} |" for a, b, x, u in SOURCES]
    L += ["", "No legally usable, no-cost source returns a bookmaker's own combined price. Paid sources are "
          "listed for the owner's information only; none is enabled.", "",
          "## 2. Today's screen", "",
          f"- Straight picks seen: {t['straight_picks_seen']}; usable as legs today: {t['usable_legs_today']}",
          f"- Combinations checked: {t['combinations_checked']}; passed leg screens: {t['passed_leg_screens']}",
          f"- Verified owner quotes: {t['verified_quotes']} (recorded in total: {r['quotes_recorded']})",
          f"- Excluded: {json.dumps(t['excluded'])}", "",
          "## 3. Joint calibration (pre-registered criteria)", "",
          f"- Source: {c['source']}; settled selections: {c['selections_settled']}",
          f"- Disjoint two-leg combinations (same New York day; different competitions, events and teams): **{c['combinations']}** "
          f"(required: {c['criteria']['min_combinations']})",
          f"- Both legs won: observed {c['joint_wins_observed']}, multiplied probabilities predict "
          f"{c['joint_wins_expected']} (z = {c['joint_z']})",
          f"- Legs won: observed {c['leg_wins_observed']}, predicted {c['leg_wins_expected']} (z = {c['leg_z']})",
          f"- Outcome correlation between paired legs (phi): {c['outcome_correlation_phi']}",
          f"- Leagues covered: {', '.join(c['leagues']) or 'none'}; legs per combination: {c['legs_per_combination']}",
          f"- Verdict: **{'passed' if c['passed'] else 'not passed'}**"
          + ("" if c["passed"] else f" — {'; '.join(c['reasons'])}"), "",
          "The sample is consistent with independence but far too small to rely on, and it covers only six club "
          "leagues and two legs. Live picks so far are UEFA Nations League, which the evidence does not cover.", "",
          "## 4. Scarcity of eligible legs (all published straight picks, by New York day)", "",
          "| Day | Picks | Competitions | Bookmakers | Pairs under current screens | Pairs if same competition were allowed |",
          "|---|---|---|---|---|---|"]
    L += [f"| {d['date']} | {d['picks']} | {d['competitions']} | {d['bookmakers']} | {d['pairs_current_screens']} | "
          f"{d['pairs_if_same_competition_allowed']} |" for d in s["days"]]
    L += ["", f"Total published straight picks: {s['total_picks']}. Whenever every pick is in one competition, the "
          "same-competition screen leaves zero pairs. The last column is a counterfactual only; the screen is "
          "unchanged and relaxing it is an owner decision that needs its own evidence.", "",
          "## 5. Shadow ledger (`ledger/parlay_shadow.csv`, unpublished, computed prices)", "",
          f"- Rows: {r['shadow']['rows']}; both/all legs won: {r['shadow']['won']}; lost: {r['shadow']['lost']}; "
          f"open: {r['shadow']['open']}", "",
          "## 6. Open straight picks (leg candidates; ids for `parlay-quote`)", ""]
    L += [f"- `{x['id']}` {x['title']} — {x['selection']} ({x['start_utc']})" for x in r["usable_legs"]] or ["- none"]
    out = config.REPORTS_DIR / "parlay_research.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n")
    return out
