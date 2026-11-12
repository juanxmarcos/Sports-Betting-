"""Golf (PGA Tour + DP World Tour): strokes-versus-field ratings and tournament simulation.

Data: ESPN public golf scoreboards (leaderboards with round-by-round strokes; season
calendars). Skill = time-weighted average of (round field average - player strokes), a
"strokes gained vs field" proxy, shrunk toward a below-average prior for thin histories.
Simulation: remaining rounds ~ Normal(-skill, sd) per player, actual scores for rounds
already played, 36-hole cut (top 65 and ties) when the field has a cut, 10,000 runs.
Outputs: win, top 5/10/20 and make-cut probabilities. Ties are counted as finishing
inside the position (dead-heat rules are not modelled, so this slightly overstates them).
Odds: no free golf odds outside the four majors (The Odds API outrights), so golf is
model-only monitoring unless such odds exist.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import numpy as np

from . import config, db
from .sources.http import fetch

BASE = "https://site.api.espn.com/apis/site/v2/sports/golf/{tour}/scoreboard"
TOURS = {"pga": "PGA Tour", "eur": "DP World Tour"}
HALF_LIFE_DAYS = 365
PRIOR, PRIOR_ROUNDS, ROUND_SD = -1.0, 8.0, 2.9


def _get(url: str, max_age: float) -> dict:
    content, _ = fetch(url, max_age_hours=max_age)
    return json.loads(content)


def calendar(tour: str, year: int) -> list[dict]:
    j = _get(BASE.format(tour=tour) + f"?dates={year}0601", 24 * 7)
    cal = (j.get("leagues") or [{}])[0].get("calendar") or []
    return [c for c in cal if isinstance(c, dict) and c.get("id")]


def leaderboard(tour: str, event_id: str, ended: bool, start: str | None = None) -> dict | None:
    """ESPN ignores ?event=, so past events are fetched by their start date and checked by id."""
    q = f"?dates={start[:10].replace('-', '')}" if start else ""
    j = _get(BASE.format(tour=tour) + q, 24 * 365 if ended else 0.9)
    ev = next((e for e in j.get("events") or [] if str(e.get("id")) == str(event_id)), None)
    if not ev:
        return None
    comp = ev["competitions"][0]
    players = []
    for p in comp.get("competitors", []):
        name = (p.get("athlete") or {}).get("displayName")
        rounds = []
        for ls in (p.get("linescores") or [])[:4]:
            v = ls.get("value")
            holes = ls.get("linescores")
            complete = (holes is None and ended) or (isinstance(holes, list) and len(holes) >= 18)
            rounds.append(float(v) if complete and isinstance(v, (int, float)) and 55 <= v <= 95 else None)
        players.append({"name": name, "rounds": rounds, "score": p.get("score")})
    return {"id": ev["id"], "name": ev["name"], "tour": tour, "start": ev["date"], "end": ev.get("endDate"),
            "state": (ev.get("status") or {}).get("type", {}).get("name"), "players": players}


def history(now: datetime) -> list[dict]:
    evs = []
    for tour in TOURS:
        for year in (now.year - 1, now.year):
            for c in calendar(tour, year):
                end = datetime.fromisoformat(c["endDate"].replace("Z", "+00:00")) if c.get("endDate") else None
                if end and end < now - timedelta(days=1):
                    try:
                        lb = leaderboard(tour, c["id"], ended=True, start=c.get("startDate"))
                    except Exception as ex:  # noqa: BLE001
                        print(f"warning: golf {tour} {c['id']}: {ex}")
                        continue
                    if lb and lb["players"]:
                        evs.append(lb)
    return sorted(evs, key=lambda e: e["start"])


def round_rel(ev: dict) -> list[tuple[str, int, float]]:
    """(player, round index, field mean - strokes) for every played round."""
    out = []
    for k in range(4):
        sc = [(p["name"], p["rounds"][k]) for p in ev["players"] if len(p["rounds"]) > k and p["rounds"][k]]
        if len(sc) < 20:
            continue
        mean = float(np.mean([s for _, s in sc]))
        out += [(n, k, mean - s) for n, s in sc]
    return out


def skills(events: list[dict], asof: datetime) -> tuple[dict, dict]:
    num, den, cnt = {}, {}, {}
    for ev in events:
        t = datetime.fromisoformat(ev["start"].replace("Z", "+00:00"))
        if t >= asof:
            continue
        w = 0.5 ** ((asof - t).days / HALF_LIFE_DAYS)
        for n, _, rel in round_rel(ev):
            num[n] = num.get(n, 0) + w * rel
            den[n] = den.get(n, 0) + w
            cnt[n] = cnt.get(n, 0) + 1
    sk = {n: (num[n] + PRIOR_ROUNDS * PRIOR) / (den[n] + PRIOR_ROUNDS) for n in num}
    return sk, cnt


def simulate(ev: dict, sk: dict, n_sims: int = 10000, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    names = [p["name"] for p in ev["players"]]
    m = len(names)
    mu = np.array([sk.get(n, PRIOR) for n in names])
    # field means of played rounds to convert actual strokes into relative scores
    # a round counts as played only when >= 90% of players who completed the previous round
    # (or the whole field, for round 1) have a complete score; otherwise it is simulated for everyone
    means = {}
    prev = m
    for k in range(4):
        sc = [p["rounds"][k] for p in ev["players"] if len(p["rounds"]) > k and p["rounds"][k]]
        if len(sc) >= 20 and len(sc) >= 0.9 * min(prev, 65 if k >= 2 and m > 80 else prev):
            means[k] = float(np.mean(sc))
            prev = len(sc)
        else:
            break
    total = np.zeros((n_sims, m))
    for k in range(4):
        if k in means:
            rel = np.array([means[k] - p["rounds"][k] if len(p["rounds"]) > k and p["rounds"][k] else np.nan for p in ev["players"]])
            # players without a score in a played round (missed cut / WD) get a large penalty
            rel = np.where(np.isnan(rel), -50.0, rel)
            total += rel
        else:
            total += mu + rng.normal(0, ROUND_SD, (n_sims, m))
        if k == 1 and m > 80:  # 36-hole cut, top 65 and ties
            thresh = np.sort(total, axis=1)[:, ::-1][:, 64:65]
            cut = total < thresh
            total = np.where(cut, total - 1000.0, total)
    rank = (-total).argsort(axis=1).argsort(axis=1) + 1
    best = total.max(axis=1, keepdims=True)
    winners = (total == best)
    res = {}
    for i, n in enumerate(names):
        res[n] = {"win": float((winners[:, i] / winners.sum(axis=1)).mean()),
                  "top5": float((rank[:, i] <= 5).mean()), "top10": float((rank[:, i] <= 10).mean()),
                  "top20": float((rank[:, i] <= 20).mean()), "cut": float((total[:, i] > -500).mean()),
                  "skill": float(mu[i])}
    return res


def backtest(now: datetime | None = None, min_events_before: int = 12) -> dict:
    from .backtest import bootstrap_ci
    now = now or datetime.now(timezone.utc)
    evs = history(now)
    rows = []
    for i, ev in enumerate(evs):
        if i < min_events_before:
            continue
        t = datetime.fromisoformat(ev["start"].replace("Z", "+00:00"))
        sk, cnt = skills(evs[:i], t)
        pre = dict(ev, players=[dict(p, rounds=[]) for p in ev["players"]])  # pre-tournament: no rounds known
        sim = simulate(pre, sk, n_sims=3000, seed=i)
        totals = {p["name"]: sum(r for r in p["rounds"] if r) for p in ev["players"] if len([r for r in p["rounds"] if r]) == 4}
        if len(totals) < 20:
            continue
        order = sorted(totals, key=totals.get)
        cutoff20 = totals[order[min(19, len(order) - 1)]]
        n = len(ev["players"])
        for p in ev["players"]:
            y20 = 1.0 if p["name"] in totals and totals[p["name"]] <= cutoff20 else 0.0
            q = min(max(sim[p["name"]]["top20"], 1e-4), 1 - 1e-4)
            b = min(20 / n, 0.999)
            rows.append((q, b, y20))
    if not rows:
        return {"sport": "golf", "n_test": 0}
    Q, B, Y = (np.array(x) for x in zip(*rows))
    ll = lambda p: -(Y * np.log(p) + (1 - Y) * np.log(1 - p))  # noqa: E731
    rep = {"sport": "golf", "model": "sg-field-sim-0.1", "events": len(evs), "n_test": len(rows),
           "test_logloss_top20": {"model": round(float(ll(Q).mean()), 5), "field_share_baseline": round(float(ll(B).mean()), 5)},
           "model_minus_baseline_ci95": [round(x, 5) for x in bootstrap_ci(ll(Q) - ll(B))],
           "note": "Pre-tournament top-20 probabilities vs the naive 20/field-size baseline. No free golf odds history."}
    (config.DATA_DIR / "backtest").mkdir(parents=True, exist_ok=True)
    (config.DATA_DIR / "backtest" / "golf.json").write_text(json.dumps(rep, indent=2, default=str))
    return rep


def analyse(con, now: datetime) -> dict:
    from . import watch
    evs = history(now)
    rows = []
    con.execute("CREATE TABLE IF NOT EXISTS event_meta (event_id TEXT PRIMARY KEY, neutral INTEGER, competition TEXT)")
    for tour, tname in TOURS.items():
        j = _get(BASE.format(tour=tour), 0.9)
        for e in j.get("events", []):
            state = (e.get("status") or {}).get("type", {}).get("name")
            if state == "STATUS_FINAL":
                continue
            lb = leaderboard(tour, e["id"], ended=False)
            if not lb or len(lb["players"]) < 20:
                continue
            sk, cnt = skills(evs, now)
            sim = simulate(lb, sk, 10000, seed=int(now.timestamp()) // 3600)
            top = sorted(sim.items(), key=lambda kv: -kv[1]["win"])[:10]
            eid = f"golf:{tour.upper()}:{lb['start'][:10].replace('-', '')}:{lb['id']}"
            start = datetime.fromisoformat(lb["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(lb["end"].replace("Z", "+00:00")) if lb.get("end") else start + timedelta(days=3)
            played = 0
            for k in range(4):
                if sum(1 for p in lb["players"] if len(p["rounds"]) > k and p["rounds"][k]) >= 0.9 * (len(lb["players"]) if k < 2 else min(65, len(lb["players"]))):
                    played = k + 1
                else:
                    break
            url = f"https://www.espn.com/golf/leaderboard/_/tournamentId/{lb['id']}"
            con.execute("""INSERT INTO events(event_id,sport,league,season,kickoff_utc,home,away,status,source,source_url,updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(event_id) DO UPDATE SET updated_at=excluded.updated_at""",
                        (eid, "golf", f"GOLF:{tour.upper()}", str(start.year), start.isoformat(), lb["name"], "", "scheduled",
                         "espn.com (public scoreboard)", url, db.utcnow()))
            con.execute("INSERT OR REPLACE INTO event_meta VALUES (?,?,?)", (eid, 1, tname))
            lines = "; ".join(f"{n} {v['win'] * 100:.1f}% win / {v['top10'] * 100:.0f}% top 10" for n, v in top[:6])
            thin = [n for n, _ in top[:10] if cnt.get(n, 0) < 12]
            in_prog = state == "STATUS_IN_PROGRESS"
            lead = (f"After {played} completed round{'s' if played != 1 else ''}, " if played else "")
            if in_prog:
                lead += f"with round {played + 1} in progress (partial rounds are not used), "
            elif not played:
                lead = "Before the first round, "
            lead = lead[:1].upper() + lead[1:]
            ctx = (f"{lead}"
                   f"Doyen's 10,000-run simulation favours: {lines}.")
            if thin:
                ctx += f" Thin history (under 12 rounds) for {', '.join(thin[:3])}, so treat their numbers cautiously."
            rows.append(watch.analysis_row(
                sport="golf", event_id=eid, competition=tname, title=lb["name"], participants=None,
                start_utc=start.isoformat(), end_utc=end.isoformat(), now=now, cands=[], rejections={},
                model_view={n: v["win"] for n, v in top[:5]},
                extra={"extra_text": ctx, "model_weight": 0, "rounds_played": played,
                       "golf_table": [{"player": n, **{k: round(v[k], 4) for k in ("win", "top5", "top10", "top20", "cut")}}
                                      for n, v in sorted(sim.items(), key=lambda kv: -kv[1]["win"])[:25]]}))
            rows[-1]["waiting_for"] = "multi-bookmaker golf odds (free odds exist only for the four majors' winner markets)"
    con.commit()
    bt = config.DATA_DIR / "backtest" / "golf.json"
    note = "Winner, top 5/10/20 and make-cut probabilities from simulation. No free golf odds outside the majors, so no picks yet."
    if bt.exists():
        b = json.loads(bt.read_text())
        t = b.get("test_logloss_top20", {})
        note += f" Top-20 log loss {t.get('model')} vs naive {t.get('field_share_baseline')} on {b.get('n_test')} player-events."
    watch.write("golf", rows, {"operational": True, "picks_possible": False,
                               "markets": ["Outright winner", "Top 5", "Top 10", "Top 20", "Make the cut"], "note": note})
    return {"events": len(rows), "history_events": len(evs)}
