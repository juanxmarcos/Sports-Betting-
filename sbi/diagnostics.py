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

from . import config, db

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


def funnel(now: datetime, horizon_h: float = 48) -> dict:
    out = {}
    for sport, files in SPORT_FILES.items():
        rows = [r for f in files for r in _rows(f)
                if now < datetime.fromisoformat(r["start_utc"]) <= now + timedelta(hours=horizon_h)]
        f = Counter()
        reasons = Counter()
        primary = Counter()
        for r in rows:
            fu = r.get("funnel") or {}
            f["events_discovered"] += 1
            f["with_sufficient_stats"] += int(fu.get("history_ok", True))
            f["with_odds"] += int(fu.get("has_odds", False))
            f["stale_odds_only"] += int(fu.get("stale_odds", False))
            f["with_3plus_bookmakers"] += int((fu.get("max_books") or 0) >= config.RULES.min_bookmakers)
            f["markets_evaluated"] += fu.get("n_markets", 0)
            f["qualifying_markets"] += fu.get("qualified", 0)
            for k, v in (fu.get("reasons") or {}).items():
                if k != "ok":
                    reasons[k] += v
            # primary blocker per event
            if fu.get("qualified"):
                primary["qualified"] += 1
            elif fu.get("stale_odds"):
                primary["stale odds"] += 1
            elif not fu.get("has_odds"):
                primary["no odds"] += 1
            else:
                c = (r.get("closest") or {}).get("reason")
                primary[c or "other"] += 1
        out[sport] = {"funnel": dict(f), "market_rejections": dict(reasons.most_common()),
                      "primary_blocker_by_event": dict(primary.most_common())}
    return out


def providers(con, now: datetime) -> dict:
    prov = {r["provider"]: {"last_success": r["last_success"], "last_error": r["last_error"], "rows": r["rows_last"]}
            for r in con.execute("SELECT * FROM provider_status")}
    fresh = {}
    for sport, like in (("soccer", "football"), ("nfl", "nfl"), ("nba", "nba"), ("tennis", "tennis")):
        ages, books = [], []
        for ev in con.execute("SELECT event_id FROM events WHERE sport=? AND status='scheduled' AND kickoff_utc BETWEEN ? AND ?",
                              (like, now.isoformat(), (now + timedelta(hours=48)).isoformat())):
            r = con.execute("SELECT MAX(retrieved_at) m, COUNT(DISTINCT bookmaker) n FROM odds WHERE event_id=? AND kind='pre'",
                            (ev[0],)).fetchone()
            if r["m"]:
                ages.append((now - datetime.fromisoformat(r["m"])).total_seconds() / 3600)
                books.append(r["n"])
        fresh[sport] = {"events_with_odds": len(ages), "median_odds_age_h": round(median(ages), 1) if ages else None,
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
    fun = funnel(now)
    rep = {"generated": now.isoformat(), "funnel_48h": fun, **providers(con, now), "briefing": briefing(fun)}
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    (config.DATA_DIR / "diagnostics.json").write_text(json.dumps(rep, indent=2, default=str))
    lines = [f"# Sports Betting Doyen — diagnostics ({now:%Y-%m-%d %H:%M} UTC)", "", "## Opportunity funnel (next 48h)", ""]
    for sport, d in fun.items():
        f = d["funnel"]
        lines.append(f"**{sport.upper()}**: " + " → ".join(f"{k.replace('_', ' ')} {v}" for k, v in f.items()))
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
