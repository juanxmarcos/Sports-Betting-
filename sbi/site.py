"""Builds the Sports Betting Doyen site data (docs/data/doyen.json).

The front end (docs/index.html + docs/assets/*) is static and reads this one file.
Contents: picks (with plain-language explanations and live status), Doyen's Pick of the Day,
watched/upcoming events for all five sports, pick history, sport operational status.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from . import config, db
from .explain import ev_plain, explain, market_label, selection_label

SPORTS = {
    "soccer": {"name": "Soccer", "analysis": ["soccer_club", "soccer_intl"]},
    "nfl": {"name": "NFL", "analysis": ["nfl"]},
    "nba": {"name": "NBA", "analysis": ["nba"]},
    "tennis": {"name": "Tennis", "analysis": ["tennis"]},
    "golf": {"name": "Golf", "analysis": ["golf"]},
}


def sport_of(league: str) -> str:
    for k in ("nfl", "nba", "tennis", "golf"):
        if league.lower().startswith(k):
            return k
    return "soccer"


def _load_analysis(name: str) -> dict | None:
    p = config.DATA_DIR / "analysis" / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def _status(con, r) -> dict:
    if r["status"] not in ("open",):
        res = {"won": "Won", "half_won": "Half won", "push": "Push", "half_lost": "Half lost",
               "lost": "Lost", "void": "Void"}[r["status"]]
        return {"state": "settled", "label": res, "result": r["status"], "pnl": r["pnl_units"]}
    u = con.execute("SELECT * FROM rec_updates WHERE rec_id=? ORDER BY id DESC LIMIT 1", (r["rec_id"],)).fetchone()
    if not u:
        return {"state": "active", "label": "Active"}
    lab = {"active": "Active", "updated": "Updated", "withdrawn": "Withdrawn", "expired": "In play / awaiting result"}
    return {"state": u["status"], "label": lab[u["status"]], "note": u["note"], "checked_at": u["checked_at"],
            "best_odds": u["best_odds"], "best_bookmaker": u["best_bookmaker"], "ev_now": u["ev_now"]}


def _pick(con, r, now) -> dict:
    r = dict(r)
    e = json.loads(r.get("evidence_json") or "{}")
    r["sport"] = sport_of(r["league"])
    x = explain(r, e)
    ts = r.get("odds_retrieved_at")
    age_h = (now - datetime.fromisoformat(ts)).total_seconds() / 3600 if ts else None
    comp = e.get("competition") or config.FOOTBALL_LEAGUES.get(r["league"], r["league"])
    return {
        "id": r["rec_id"], "event_id": r["event_id"], "sport": r["sport"], "competition": comp,
        "title": f"{r['home']} v {r['away']}" if r["sport"] != "golf" else r["home"],
        "start_utc": r["kickoff_utc"], "published_at": r["published_at"],
        "market": market_label(r["market"]), "selection": selection_label(r),
        "odds": r["odds"], "bookmaker": r["bookmaker"], "net_odds": e.get("net_odds", r["odds"]),
        "prob": r["final_prob"], "fair_odds": r["fair_odds"], "ev": r["ev"], "ev_plain": ev_plain(r["ev"]),
        "model_prob": r["model_prob"], "market_prob": r["market_prob"],
        "why": x["why"], "risk": x["risk"], "risks": x["risks"],
        "odds_updated": ts, "stale": age_h is not None and age_h > 24,
        "status": _status(con, r), "model_version": r["model_version"],
        "detail": {"consensus_source": e.get("consensus_source"), "n_bookmakers": e.get("n_bookmakers"),
                   "prices": e.get("all_prices"), "expected_goals": e.get("expected_goals"),
                   "form": e.get("form"), "model_markets": e.get("model_markets"),
                   "sources": json.loads(r.get("source_urls") or "[]")},
        "notes": [dict(n) for n in con.execute(
            "SELECT category,claim,evidence_type,direction,source_url,retrieved_at FROM research_notes WHERE event_id=?",
            (r["event_id"],))],
    }


def _watch_reason(row: dict) -> str:
    """Why the matchup is interesting - computed, never invented."""
    c = row.get("closest") or {}
    mv, bv = row.get("model_view") or {}, row.get("book_view") or {}
    bits = []
    if c and c.get("ev") is not None and c["ev"] > -0.01:
        bits.append(f"Closest to value: {c['market_label']} — {c['selection_text']} at {c['odds']:.2f} "
                    f"({c['ev'] * 100:+.1f}% vs fair)")
    if mv and bv:
        gaps = {k: mv[k] - bv[k] for k in bv if k in mv}
        if gaps:
            k = max(gaps, key=lambda z: abs(gaps[z]))
            if abs(gaps[k]) >= 0.05:
                lab = k.lower() if k in ("Home", "Away", "Draw") else k
                txt = f"Doyen's model and the bookmakers differ on {lab} ({mv[k] * 100:.0f}% vs {bv[k] * 100:.0f}%)"
                if abs(gaps[k]) >= 0.10:
                    txt += ", a gap this size usually means news the model can't see (injuries, rest, lineups)"
                bits.append(txt)
    if row.get("extra_text") and (not bits or row["sport"] != "soccer"):
        bits.append(row["extra_text"].split(". ")[0].rstrip("."))
    for n in row.get("notes") or []:
        bits.append(n)
    out = ". ".join(bits) + ("." if bits else "")
    return out[:1].upper() + out[1:]


def _sel_text(row: dict, c: dict) -> str:
    p = row.get("participants") or ["Home", "Away"]
    s, ln = c["selection"], c.get("line")
    if c["market"] == "1X2":
        return {"H": f"{p[0]}", "D": "Draw", "A": f"{p[1]}"}[s]
    if c["market"] in ("OU", "TOTAL"):
        return f"{'Over' if s == 'over' else 'Under'} {ln:g}"
    if c["market"] in ("AH", "SPREAD"):
        return f"{p[0]} {ln:+g}" if s == "home" else f"{p[1]} {-ln:+g}"
    if c["market"] == "ML":
        return p[0] if s in ("home", "H") else p[1]
    return str(s)


def build(con, now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    config.load_tuned()
    picks_all = [_pick(con, r, now) for r in con.execute(
        "SELECT * FROM recommendations ORDER BY published_at DESC, rank")]
    current = [p for p in picks_all if p["status"]["state"] in ("active", "updated")
               and datetime.fromisoformat(p["start_utc"]) > now]
    current.sort(key=lambda p: (p["status"]["state"] != "active", -(p["ev"] or 0)))
    potd = current[0]["id"] if current and current[0]["status"]["state"] == "active" else None

    events, sports = [], {}
    for key, s in SPORTS.items():
        rows, gen = [], None
        for name in s["analysis"]:
            a = _load_analysis(name)
            if a:
                rows += a["rows"]
                gen = max(gen or a["generated"], a["generated"])
        fresh = gen is not None and (now - datetime.fromisoformat(gen)) < timedelta(days=3)
        meta = {}
        for name in s["analysis"]:
            a = _load_analysis(name)
            if a:
                meta.update(a.get("meta") or {})
        sports[key] = {"name": s["name"], "operational": bool(meta.get("operational", fresh or key == "soccer")),
                       "analysis_updated": gen, "events": len(rows),
                       "markets": meta.get("markets"), "note": meta.get("note"),
                       "picks_possible": meta.get("picks_possible", key == "soccer")}
        for row in rows:
            if datetime.fromisoformat(row.get("end_utc") or row["start_utc"]) < now - timedelta(hours=3):
                continue
            c = row.get("closest")
            if c:
                c["selection_text"] = _sel_text(row, c)
            row["why_interesting"] = _watch_reason(row)
            row["has_pick"] = any(p["event_id"] == row["event_id"] for p in current)
            events.append(row)
    events.sort(key=lambda r: r["start_utc"])
    # Matches Doyen is watching: closest-to-value and largest disagreements, no picks, next 72h
    def interest(r):
        """Score only on computed signals: closeness to value and model-market disagreement."""
        c = r.get("closest") or {}
        mv, bv = r.get("model_view") or {}, r.get("book_view") or {}
        gap = max((abs(mv[k] - bv[k]) for k in bv if k in mv), default=0.0)
        near = c.get("ev", -1) if c else -1
        return max(near + 0.03, gap - 0.02) if (near > -0.015 or gap >= 0.05) else None

    cand = []
    for r in events:
        if r["has_pick"] or datetime.fromisoformat(r["start_utc"]) >= now + timedelta(hours=72):
            continue
        if any("known model bias" in n.lower() for n in r.get("notes", [])):
            continue
        sc = interest(r)
        if sc is not None:
            cand.append((sc, r))
    cand.sort(key=lambda x: -x[0])
    watching, per = [], {}
    for sc, r in cand:                       # at most 3 per sport so every sport gets a look-in
        if per.get(r["sport"], 0) < 3:
            watching.append(r["event_id"])
            per[r["sport"]] = per.get(r["sport"], 0) + 1
    golf_now = [r["event_id"] for r in events if r["sport"] == "golf"]
    watching = (watching + golf_now)[:12]

    settled = [p for p in picks_all if p["status"]["state"] == "settled"]
    rec = {"won": sum(p["status"]["result"] in ("won", "half_won") for p in settled),
           "lost": sum(p["status"]["result"] in ("lost", "half_lost") for p in settled),
           "push": sum(p["status"]["result"] in ("push", "void") for p in settled),
           "profit_units": round(sum(p["status"].get("pnl") or 0 for p in settled), 2),
           "open": len(picks_all) - len(settled)}
    last_jobs = {r["job"]: r["finished_at"] for r in con.execute(
        "SELECT job, MAX(finished_at) finished_at FROM job_runs WHERE status IN ('ok','partial') GROUP BY job")}
    providers = {r["provider"]: r["last_success"] for r in con.execute("SELECT provider,last_success FROM provider_status")}
    data = {"brand": "Sports Betting Doyen", "generated": now.isoformat(), "default_timezone": config.TIMEZONE,
            "pick_of_the_day": potd, "picks": current, "history": picks_all, "record": rec,
            "events": events, "watching": watching, "sports": sports,
            "rules": {"min_ev": config.RULES.min_ev, "min_odds": config.RULES.min_odds,
                      "max_odds": config.RULES.max_odds, "min_bookmakers": config.RULES.min_bookmakers},
            "updated": {"pipeline": last_jobs.get("publish"), "providers": providers}}
    out = config.ROOT / "docs" / "data"
    out.mkdir(parents=True, exist_ok=True)
    (out / "doyen.json").write_text(json.dumps(data, default=str))
    return out / "doyen.json"
