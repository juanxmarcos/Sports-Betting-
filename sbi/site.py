"""Builds the Sports Betting Doyen site data (docs/data/doyen.json).

The front end (docs/index.html + docs/assets/*) is static and reads this one file.
Contents: picks (with plain-language explanations and live status), Doyen's Pick of the Day,
watched/upcoming events for all five sports, pick history, sport operational status.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from . import config, db
from types import SimpleNamespace

from .explain import ev_plain, explain, market_label, selection_label

SPORTS = {
    "soccer": {"name": "Soccer", "analysis": ["soccer_club", "soccer_intl"]},
    "nfl": {"name": "NFL", "analysis": ["nfl"]},
    "nba": {"name": "NBA", "analysis": ["nba"]},
    "tennis": {"name": "Tennis", "analysis": ["tennis"]},
}


def sport_of(league: str) -> str:
    for k in ("nfl", "nba", "tennis"):
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
    if r["sport"] in ("nba", "nfl", "soccer") and not e.get("injuries"):
        from .sources.espn_extra import context_for
        e = {**e, **context_for(con, r["event_id"], r["sport"], r["home"], r["away"])}
    x = explain(r, e)
    ts = r.get("odds_retrieved_at")
    age_h = (now - datetime.fromisoformat(ts)).total_seconds() / 3600 if ts else None
    comp = e.get("competition") or config.FOOTBALL_LEAGUES.get(r["league"], r["league"])
    return {
        "id": r["rec_id"], "event_id": r["event_id"], "sport": r["sport"], "competition": comp,
        "title": f"{r['home']} v {r['away']}",
        "start_utc": r["kickoff_utc"], "published_at": r["published_at"],
        "market": market_label(r["market"]), "selection": selection_label(r),
        "odds": r["odds"], "bookmaker": r["bookmaker"], "net_odds": e.get("net_odds", r["odds"]),
        "prob": r["final_prob"], "fair_odds": r["fair_odds"], "ev": r["ev"], "ev_plain": ev_plain(r["ev"]),
        "model_prob": r["model_prob"], "market_prob": r["market_prob"],
        "why": x["why"], "why_short": x["why_short"], "risk": x["risk"], "risks": x["risks"],
        "odds_updated": ts, "stale": age_h is not None and age_h > 24,
        "status": _status(con, r), "model_version": r["model_version"],
        "updates": [dict(u) for u in con.execute(
            "SELECT checked_at,status,best_odds,best_bookmaker,ev_now,note FROM rec_updates WHERE rec_id=? ORDER BY id", (r["rec_id"],))],
        "detail": {"consensus_source": e.get("consensus_source"), "n_bookmakers": e.get("n_bookmakers"),
                   "context": e.get("context"), "injuries": e.get("injuries"), "external_forecast": e.get("external_forecast"),
                   "weather": e.get("weather"), "blend_weight": e.get("blend_weight", 0),
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


def _attach_context(con, row: dict) -> None:
    """Injuries, ESPN Analytics forecast, lineup status and source discrepancies (flagged, never resolved
    by picking a side)."""
    from .sources.espn_extra import context_for
    p = row.get("participants") or [None, None]
    if not p[0]:
        return
    ctx = context_for(con, row["event_id"], row["sport"], p[0], p[1])
    row.update(ctx)
    disc = []
    f, bv = ctx.get("external_forecast"), row.get("book_view") or {}
    mv = row.get("model_view") or {}
    if f:
        keymap = {p[0]: ["Home", f"{p[0]} win", p[0]], p[1]: ["Away", f"{p[1]} win", p[1]], "Draw": ["Draw"]}
        for team, prob in f["probs"].items():
            for k in keymap.get(team, []):
                if k in bv and abs(prob - bv[k]) >= 0.10:
                    disc.append(f"{f['source']} gives {team} {prob * 100:.0f}% vs bookmakers {bv[k] * 100:.0f}%.")
                if k in mv and abs(prob - mv[k]) >= 0.10:
                    disc.append(f"{f['source']} gives {team} {prob * 100:.0f}% vs Doyen's model {mv[k] * 100:.0f}%.")
    row["discrepancies"] = sorted(set(disc))
    c = row.get("closest")
    if c:
        from .disagreement import ensure
        ensure(con)
        h = con.execute("""SELECT category, flags, gap FROM disagreement_reviews WHERE event_id=? AND market=? AND selection=?
                           AND IFNULL(line,-999)=IFNULL(?,-999) ORDER BY id DESC LIMIT 1""",
                        (row["event_id"], c["market"], c["selection"], c.get("line"))).fetchone()
        if h:
            row["disagreement"] = {"category": h["category"], "flags": json.loads(h["flags"] or "[]"), "gap": h["gap"]}
            if h["category"] in ("technical_suspect", "unexplained") and (c.get("ev") or -1) >= config.RULES.min_ev:
                c["reason"] = "extreme disagreement (review)"


def _watch_short(row: dict) -> str:
    """One short sentence: why Doyen is watching / what it is waiting for. Computed, never invented."""
    c = row.get("closest") or {}
    reason = c.get("reason")
    rules = config.RULES
    hours = (datetime.fromisoformat(row["start_utc"]) - datetime.now(timezone.utc)).total_seconds() / 3600
    if not c:
        return "Waiting for bookmaker prices."
    if reason == "EV below threshold":
        from .watch import qualifying_odds
        q = qualifying_odds(SimpleNamespace(final_q=c["prob"], active=c.get("active", 1.0)), rules.min_ev)
        return f"Waiting for better odds ({q:.2f}+)." if q else "Waiting for a better price."
    if reason == "too few bookmakers":
        return "Waiting for more bookmakers to price it."
    if reason == "odds outside range":
        return "Value only at long odds, outside Doyen's range."
    if reason == "no market consensus":
        return "Waiting for a sharp reference price."
    if reason == "insufficient team history":
        return "Not enough history on one side yet."
    if reason in ("model uncertainty too high", "pessimistic EV not positive"):
        return "Edge too uncertain to publish."
    if reason == "extreme disagreement (review)":
        return "Held for review: model and market disagree sharply."
    if hours < 24 and row["sport"] == "soccer" and not row.get("lineups_confirmed"):
        return "Waiting for confirmed lineups and final prices."
    if hours < 24 and row["sport"] in ("nfl", "nba"):
        return "Waiting for final injury report and prices."
    return "Monitoring price movement."


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
    if c["market"] == "BTTS":
        return "Yes" if s == "yes" else "No"
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
            if row.get("sport") not in SPORTS or \
                    datetime.fromisoformat(row.get("end_utc") or row["start_utc"]) < now - timedelta(hours=3):
                continue
            c = row.get("closest")
            if c:
                c["selection_text"] = _sel_text(row, c)
            _attach_context(con, row)
            row["why_interesting"] = _watch_reason(row)
            row["short"] = _watch_short(row)
            if c:
                row["watch_label"] = f"{c['market_label']}: {c['selection_text']}"
            row["has_pick"] = any(p["event_id"] == row["event_id"] for p in current)
            events.append(row)
    events.sort(key=lambda r: r["start_utc"])
    # Matches Doyen is watching: closest-to-value and largest disagreements, no picks, next 72h
    min_ev = config.RULES.min_ev

    def fresh(r):
        ts = r.get("odds_updated")
        return ts is not None and (now - datetime.fromisoformat(ts)) < timedelta(hours=config.RULES.max_odds_age_hours)

    upcoming7 = [r for r in events if now < datetime.fromisoformat(r["start_utc"]) <= now + timedelta(days=7)
                 and not any("known model bias" in n.lower() for n in r.get("notes", []))]

    # CLOSE TO VALUE: a real, fresh price within 4 points of the EV threshold, blocked by a fixable rule.
    fixable = ("EV below threshold", "too few bookmakers", "no market consensus", "extreme disagreement (review)",
               "model uncertainty too high", "pessimistic EV not positive")
    close = [r for r in upcoming7 if not r["has_pick"] and r.get("closest") and fresh(r)
             and r["closest"].get("reason") in fixable and (r["closest"].get("ev") or -1) >= min_ev - 0.04]
    close.sort(key=lambda r: (max(0.0, min_ev - (r["closest"].get("ev") or -1)), r["start_utc"]))
    close_ids = [r["event_id"] for r in close][:20]
    for r in close:
        r["rank_basis"] = (f"Fresh price; {max(0.0, min_ev - (r['closest'].get('ev') or -1)) * 100:.1f} pts short of the "
                           f"{min_ev * 100:.0f}% value threshold.")

    # WATCHING: completeness, price quality/freshness, pending information, proximity, start time.
    def watch_key(r):
        fu = r.get("funnel") or {}
        complete = int(bool(fu.get("history_ok", True)) and bool(fu.get("model_ok", True)))
        quality = int(fresh(r)) + int((fu.get("max_books") or 0) >= config.RULES.min_bookmakers)
        hours = (datetime.fromisoformat(r["start_utc"]) - now).total_seconds() / 3600
        pending = int(hours <= 36 and (r["sport"] in ("soccer", "nfl", "nba") or not fu.get("has_odds")))
        gap = max(0.0, min_ev - ((r.get("closest") or {}).get("ev") or -1.0))
        return (-complete, -quality, -pending, round(gap, 3), r["start_utc"])

    pool = [r for r in upcoming7 if not r["has_pick"] and r["event_id"] not in close_ids
            and (r.get("closest") or {}).get("reason") not in ("odds outside range", "insufficient team history")]
    pool.sort(key=watch_key)
    watching, per = [], {}
    for r in pool:                            # at most 3 per sport so every sport gets a look-in
        if per.get(r["sport"], 0) < 3:
            watching.append(r["event_id"])
            per[r["sport"]] = per.get(r["sport"], 0) + 1
            k = watch_key(r)
            r["rank_basis"] = ("Complete data" if k[0] == -1 else "Incomplete data") + \
                (", fresh multi-bookmaker prices" if k[1] == -2 else (", partial prices" if k[1] == -1 else ", no current prices")) + \
                (", key information pending before the start" if k[2] == -1 else "") + "."
    watching = watching[:12]

    settled = [p for p in picks_all if p["status"]["state"] == "settled"]
    rec = {"won": sum(p["status"]["result"] in ("won", "half_won") for p in settled),
           "lost": sum(p["status"]["result"] in ("lost", "half_lost") for p in settled),
           "push": sum(p["status"]["result"] in ("push", "void") for p in settled),
           "profit_units": round(sum(p["status"].get("pnl") or 0 for p in settled), 2),
           "open": len(picks_all) - len(settled)}
    last_jobs = {r["job"]: r["finished_at"] for r in con.execute(
        "SELECT job, MAX(finished_at) finished_at FROM job_runs WHERE status IN ('ok','partial') GROUP BY job")}
    providers = {r["provider"]: r["last_success"] for r in con.execute("SELECT provider,last_success FROM provider_status")}
    from . import diagnostics
    diag = diagnostics.build(con, now)
    data = {"brand": "Sports Betting Doyen", "briefing": {"sentence": diag["briefing"]}, "generated": now.isoformat(), "default_timezone": config.TIMEZONE,
            "pick_of_the_day": potd, "picks": current, "history": picks_all, "record": rec,
            "events": events, "watching": watching, "close_to_value": close_ids, "sports": sports,
            "funnel_7d": {k: v["funnel"] for k, v in diag["funnel_7d"].items()},
            "rules": {"min_ev": config.RULES.min_ev, "min_odds": config.RULES.min_odds,
                      "max_odds": config.RULES.max_odds, "min_bookmakers": config.RULES.min_bookmakers},
            "updated": {"pipeline": last_jobs.get("publish"), "providers": providers}}
    out = config.ROOT / "docs" / "data"
    out.mkdir(parents=True, exist_ok=True)
    (out / "doyen.json").write_text(json.dumps(data, default=str))
    return out / "doyen.json"
