"""Internal diagnostics: provider health, odds freshness and the opportunity funnel.

Answers "why are there no picks?" with counts, not opinions. Written to
data/diagnostics.json and reports/diagnostics.md (not shown on the public site;
ask Doyen / read the file for the full breakdown).
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import median

from . import config, db, leagues

SPORT_FILES = {"soccer": ["soccer_club", "soccer_intl"], "nfl": ["nfl"], "nba": ["nba"], "tennis": ["tennis"]}
BLOCKER_TEXT = {
    "EV below threshold": "prices are in line with the sharp market",
    "too few bookmakers": "too few bookmakers price these markets",
    "no odds": "no bookmaker prices yet",
    "stale odds": "only stale prices available",
    "insufficient team history": "not enough history on one side",
    "odds outside range": "value only at long odds outside the allowed range",
    "no market consensus": "no sharp reference price",
    "model uncertainty too high": "edges too uncertain",
    "pessimistic EV not positive": "edges do not survive uncertainty",
}


def _rows(name):
    p = config.DATA_DIR / "analysis" / f"{name}.json"
    return json.loads(p.read_text())["rows"] if p.exists() else []


def funnel(now: datetime, horizon_h: float = 168, con=None) -> dict:
    """Per sport: every stage from discovery to final recommendation, plus rejection reasons."""
    out = {}
    recs = {}
    if con is not None:
        for r in con.execute("SELECT event_id FROM recommendations WHERE kickoff_utc > ? AND kickoff_utc <= ?",
                             (now.isoformat(), (now + timedelta(hours=horizon_h)).isoformat())):
            recs[r[0]] = 1
    for sport, files in SPORT_FILES.items():
        rows = [r for f in files for r in _rows(f)
                if now < datetime.fromisoformat(r["start_utc"]) <= now + timedelta(hours=horizon_h)]
        f = Counter()
        reasons, primary = Counter(), Counter()
        for r in rows:
            fu = r.get("funnel") or {}
            f["1_events_discovered"] += 1
            f["2_complete_history"] += int(fu.get("history_ok", True))
            f["3_valid_forecast"] += int(fu.get("model_ok", bool(r.get("model_view"))))
            f["4_fresh_odds_available"] += int(fu.get("has_odds", False))
            f["4b_stale_odds_only"] += int(fu.get("stale_odds", False))
            three = (fu.get("max_books") or 0) >= config.RULES.min_bookmakers
            f["5_three_plus_bookmakers"] += int(three)
            f["5b_fully_evaluated"] += int(three and fu.get("history_ok", True) and fu.get("model_ok", True))
            f["6_markets_evaluated"] += fu.get("n_markets", 0)
            f["7_markets_positive_ev"] += fu.get("positive_ev", 0)
            f["8_events_positive_ev"] += int(fu.get("positive_ev", 0) > 0)
            f["9_events_passing_all_rules"] += int(fu.get("qualified", 0) > 0)
            f["10_final_recommendations"] += int(r["event_id"] in recs)
            for k, v in (fu.get("reasons") or {}).items():
                if k != "ok":
                    reasons[k] += v
            if fu.get("qualified"):
                primary["qualified"] += 1
            elif fu.get("stale_odds"):
                primary["stale odds"] += 1
            elif not fu.get("has_odds"):
                primary["no odds"] += 1
            else:
                primary[(r.get("closest") or {}).get("reason") or "other"] += 1
        out[sport] = {"funnel": dict(sorted(f.items(), key=lambda kv: int(float(kv[0].split("_")[0].replace("b", ".5"))))),
                      "market_rejections": dict(reasons.most_common()),
                      "primary_blocker_by_event": dict(primary.most_common())}
    return out


def providers(con, now: datetime) -> dict:
    prov = {r["provider"]: {"last_success": r["last_success"], "last_error": r["last_error"], "rows": r["rows_last"]}
            for r in con.execute("SELECT * FROM provider_status")}
    fresh = {}
    for sport, like in (("soccer", "football"), ("nfl", "nfl"), ("nba", "nba"), ("tennis", "tennis")):
        ages, books = [], []
        for ev in con.execute("SELECT event_id, league FROM events WHERE sport=? AND status='scheduled' AND kickoff_utc BETWEEN ? AND ?",
                              (like, now.isoformat(), (now + timedelta(hours=168)).isoformat())):
            if like == "football" and leagues.status(ev[1]) == leagues.MONITORING:
                continue        # stored for measurement only; reported per league by `sbi coverage`
            r = con.execute("SELECT MAX(retrieved_at) m, COUNT(DISTINCT bookmaker) n FROM odds WHERE event_id=? AND kind='pre'",
                            (ev[0],)).fetchone()
            if r["m"]:
                ages.append((now - datetime.fromisoformat(r["m"])).total_seconds() / 3600)
                books.append(r["n"])
        fresh[sport] = {"events_with_odds": len(ages), "median_odds_age_h": round(abs(median(ages)), 1) if ages else None,
                        "median_bookmakers": median(books) if books else None,
                        "share_3plus_books": round(sum(b >= 3 for b in books) / len(books), 2) if books else None}
    oa = con.execute("SELECT details FROM job_runs WHERE job='ingest-odds-api' ORDER BY id DESC LIMIT 1").fetchone()
    oad = json.loads(oa["details"]) if oa and oa["details"] else {}
    errs = [dict(r) for r in con.execute(
        "SELECT job, started_at, details FROM job_runs WHERE status IN ('error','partial') ORDER BY id DESC LIMIT 10")]
    return {"providers": prov, "odds_freshness": fresh,
            "odds_api": {k: oad.get(k) for k in ("skipped", "credits_remaining_after", "credits_spent", "fetched",
                                                   "matched", "unmatched")},
            "recent_job_problems": errs}


def briefing(fun: dict) -> str:
    """One short sentence from the dominant blockers (computed)."""
    tot = Counter()
    for s in fun.values():
        for k, v in s["primary_blocker_by_event"].items():
            if k != "qualified":
                tot[k] += v
    if not tot:
        return "No events in the next 48 hours."
    waiting = tot["too few bookmakers"] + tot["no odds"] + tot["stale odds"]
    priced = tot["EV below threshold"] + tot["odds outside range"]
    if waiting >= priced:
        s = "Waiting for more bookmakers to price most games"
        return s + ("; where priced, odds match the sharp market." if priced else ".")
    return "Where priced, odds match the sharp market; watching for movement and team news."


def build(con, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    fun = funnel(now, 168, con)
    fun48 = funnel(now, 48, con)
    rep = {"generated": now.isoformat(), "funnel_7d": fun, "funnel_48h": fun48, **providers(con, now),
           "briefing": briefing(fun)}
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    (config.DATA_DIR / "diagnostics.json").write_text(json.dumps(rep, indent=2, default=str))
    lines = [f"# Sports Betting Doyen — diagnostics ({now:%Y-%m-%d %H:%M} UTC)", "", "## Opportunity funnel (next 7 days)", ""]
    for sport, d in fun.items():
        f = d["funnel"]
        lines.append(f"**{sport.upper()}**: " + " → ".join(f"{k.split('_', 1)[1].replace('_', ' ')} {v}" for k, v in f.items()))
        if d["market_rejections"]:
            lines.append("  - market rejections: " + ", ".join(f"{k} ({v})" for k, v in d["market_rejections"].items()))
        if d["primary_blocker_by_event"]:
            lines.append("  - primary blocker per event: " + ", ".join(f"{BLOCKER_TEXT.get(k, k)} ({v})" for k, v in d["primary_blocker_by_event"].items()))
        lines.append("")
    lines += ["## Odds freshness (events in next 48h)", ""]
    for s, v in rep["odds_freshness"].items():
        lines.append(f"- {s}: {v}")
    lines += ["", f"## The Odds API\n\n{rep['odds_api']}", "", "## Providers", ""]
    for k, v in rep["providers"].items():
        lines.append(f"- {k}: last success {v['last_success']}{' · last error ' + v['last_error'] if v['last_error'] else ''}")
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (config.REPORTS_DIR / "diagnostics.md").write_text("\n".join(lines) + "\n")
    return rep
