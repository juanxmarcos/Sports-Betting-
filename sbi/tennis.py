"""Tennis (ATP + WTA): surface-aware Elo from ESPN results; match-winner market only.

Data: ESPN public tennis scoreboards (each date returns active tournaments with every
match and set score). History is backfilled weekly and cached.
Model: overall Elo + surface Elo (hard/clay/grass), averaged, with a dynamic K factor
(FiveThirtyEight-style). Best-of-five Grand Slam men's matches are converted from the
best-of-three probability via the implied per-set win probability.
Markets: match winner only. Set handicaps and total games are excluded because they
are not modelled reliably here.
Odds: The Odds API tennis tournament keys when active (multi-book); otherwise
model-only monitoring.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone

import numpy as np
from scipy.optimize import brentq

from . import config, db
from .sources.http import fetch

ESPN = "https://site.api.espn.com/apis/site/v2/sports/tennis/{tour}/scoreboard?dates={d}"
TOURS = ("atp", "wta")
CLAY = re.compile(r"roland|french open|monte|madrid|internazionali|rome|barcelona|hamburg|rio |buenos aires|estoril|"
                  r"munich|geneva|lyon|bastad|båstad|gstaad|kitzb|umag|houston|marrakech|bucharest|santiago|cordoba|"
                  r"córdoba|charleston|rabat|strasbourg|palermo|parma|bogota|prague|iasi|lausanne|budapest|portoroz|"
                  r"warsaw|hamburg|rouen|saint-malo|clay", re.I)
GRASS = re.compile(r"wimbledon|queen|hsbc championships|halle|terra wortmann|hertogenbosch|libéma|libema|eastbourne|"
                   r"mallorca|boss open|berlin|bad homburg|nottingham|birmingham|grass", re.I)
SLAM = re.compile(r"australian open|roland|french open|wimbledon|us open", re.I)


def surface(name: str, d: date) -> str:
    if GRASS.search(name) or ("stuttgart" in name.lower() and d.month == 6):
        return "grass"
    if CLAY.search(name) or ("stuttgart" in name.lower() and d.month == 4):
        return "clay"
    return "hard"


def _sets(c: dict) -> tuple[int, int]:
    a, b = (c.get("competitors") or [{}, {}])[:2]
    wa = sum(1 for ls in a.get("linescores") or [] if ls.get("winner"))
    wb = sum(1 for ls in b.get("linescores") or [] if ls.get("winner"))
    return wa, wb


def _parse(j: dict, tour: str) -> list[dict]:
    out = []
    for e in j.get("events", []):
        tname = e.get("name", "")
        for g in e.get("groupings", []):
            gname = (g.get("grouping") or {}).get("displayName", "")
            if "Singles" not in gname:
                continue
            for c in g.get("competitions", []):
                comp = c.get("competitors") or []
                if len(comp) != 2 or any(x.get("type") != "athlete" for x in comp):
                    continue
                st = (c.get("status") or {}).get("type") or {}
                a, b = comp
                d = datetime.fromisoformat((c.get("date") or e["date"]).replace("Z", "+00:00"))
                rnd = (c.get("round") or {}).get("displayName", "")
                rec = {"id": c["id"], "tour": tour, "tournament": tname, "event_id_espn": e["id"], "date": d,
                       "round": rnd, "p1": a["athlete"]["displayName"], "p2": b["athlete"]["displayName"],
                       "completed": bool(st.get("completed")), "state": st.get("name"),
                       "winner": None, "slam": bool(SLAM.search(tname)), "major": bool(e.get("major")),
                       "surface": surface(tname, d.date())}
                rec["sets"] = _sets(c)
                if rec["completed"]:
                    if a.get("winner"):
                        rec["winner"] = rec["p1"]
                    elif b.get("winner"):
                        rec["winner"] = rec["p2"]
                    # walkovers/retirements without a winner flag are skipped
                    detail = str(st.get("description", "")) + str(st.get("detail", ""))
                    rec["walkover"] = "walkover" in detail.lower() or "w/o" in detail.lower()
                out.append(rec)
    return out


def matches(start: date, end: date, now: datetime) -> list[dict]:
    rows, seen = [], set()
    d = start
    while d <= end:
        past = d < now.date() - timedelta(days=3)
        for tour in TOURS:
            try:
                content, _ = fetch(ESPN.format(tour=tour, d=d.strftime("%Y%m%d")), max_age_hours=24 * 365 if past else 0.9)
                for m in _parse(json.loads(content), tour):
                    if m["id"] not in seen:
                        seen.add(m["id"])
                        rows.append(m)
            except Exception as ex:  # noqa: BLE001
                print(f"warning: tennis {tour} {d}: {ex}")
        d += timedelta(days=7 if past else 1)
    return rows


# ---------------------------------------------------------------- Elo

def _tuned() -> tuple[float, float]:
    """Surface weight and K scale adopted from the chronological tuning (data/backtest/tennis_tuning.json)."""
    try:
        t = json.loads((config.DATA_DIR / "backtest" / "tennis_tuning.json").read_text())
        if t.get("adopt_tuned_elo"):
            return float(t["chosen"]["w_surface"]), float(t["chosen"]["k_scale"])
    except (OSError, ValueError, KeyError):
        pass
    return 0.5, 1.0


class Elo:
    def __init__(self, w_surface: float | None = None, k_scale: float | None = None):
        self.r, self.rs, self.n, self.ns = {}, {}, {}, {}
        tw, tk = _tuned()
        self.w = tw if w_surface is None else w_surface
        self.ks = tk if k_scale is None else k_scale

    def _k(self, n):
        return self.ks * 250 / (n + 5) ** 0.4

    def prob(self, a, b, surf):
        ra = (1 - self.w) * self.r.get(a, 1500) + self.w * self.rs.get((a, surf), 1500)
        rb = (1 - self.w) * self.r.get(b, 1500) + self.w * self.rs.get((b, surf), 1500)
        return 1 / (1 + 10 ** ((rb - ra) / 400))

    def update(self, w, l, surf):
        for tab, cnt, kw, kl in ((self.r, self.n, w, l), (self.rs, self.ns, (w, surf), (l, surf))):
            rw, rl = tab.get(kw, 1500), tab.get(kl, 1500)
            e = 1 / (1 + 10 ** ((rl - rw) / 400))
            tab[kw] = rw + self._k(cnt.get(kw, 0)) * (1 - e)
            tab[kl] = rl - self._k(cnt.get(kl, 0)) * (1 - e)
            cnt[kw] = cnt.get(kw, 0) + 1
            cnt[kl] = cnt.get(kl, 0) + 1

    def matches_played(self, p):
        return self.n.get(p, 0)


def bo5(p3: float) -> float:
    """Best-of-3 match prob -> per-set prob s -> best-of-5 prob."""
    p3 = min(max(p3, 1e-4), 1 - 1e-4)
    s = brentq(lambda s: s * s * (3 - 2 * s) - p3, 1e-6, 1 - 1e-6)
    return s ** 3 * (10 - 15 * s + 6 * s * s)


def match_prob(elo: Elo, m: dict) -> float:
    p = elo.prob(m["p1"], m["p2"], m["surface"])
    return bo5(p) if (m["slam"] and m["tour"] == "atp") else p


def run_elo(hist: list[dict]) -> Elo:
    elo = Elo()
    for m in sorted(hist, key=lambda x: x["date"]):
        if m["completed"] and m["winner"] and not m.get("walkover"):
            loser = m["p2"] if m["winner"] == m["p1"] else m["p1"]
            elo.update(m["winner"], loser, m["surface"])
    return elo


def backtest(now: datetime | None = None, test_from: str = "2025-07-01") -> dict:
    from .backtest import bootstrap_ci, calibration
    now = now or datetime.now(timezone.utc)
    hist = sorted([m for m in matches(date(2024, 1, 1), now.date(), now) if m["completed"] and m["winner"]
                   and not m.get("walkover")], key=lambda x: x["date"])
    elo, rows = Elo(), []
    cut = datetime.fromisoformat(test_from).replace(tzinfo=timezone.utc)
    for m in hist:
        if m["date"] >= cut and min(elo.matches_played(m["p1"]), elo.matches_played(m["p2"])) >= 10:
            p = match_prob(elo, m)
            fav_won = (p >= 0.5) == (m["winner"] == m["p1"])
            rows.append((p, 1.0 if m["winner"] == m["p1"] else 0.0, fav_won, m["tour"], m["surface"]))
        loser = m["p2"] if m["winner"] == m["p1"] else m["p1"]
        elo.update(m["winner"], loser, m["surface"])
    P = np.array([r[0] for r in rows]); Y = np.array([r[1] for r in rows])
    li = -(Y * np.log(np.clip(P, 1e-9, 1)) + (1 - Y) * np.log(np.clip(1 - P, 1e-9, 1)))
    rep = {"sport": "tennis", "model": "surface-elo-0.1", "history_matches": len(hist), "n_test": len(rows),
           "test_from": test_from, "test_logloss": {"model": round(float(li.mean()), 5), "coin_flip": round(float(np.log(2)), 5)},
           "test_logloss_ci95": [round(x, 5) for x in bootstrap_ci(li)],
           "favourite_win_rate": round(float(np.mean([r[2] for r in rows])), 4),
           "calibration_model": calibration(np.maximum(P, 1 - P), np.where(P >= 0.5, Y, 1 - Y).astype(int)),
           "note": "No free historical tennis odds: model weight vs market is 0; picks need multi-bookmaker odds."}
    (config.DATA_DIR / "backtest").mkdir(parents=True, exist_ok=True)
    (config.DATA_DIR / "backtest" / "tennis.json").write_text(json.dumps(rep, indent=2, default=str))
    return rep


# ---------------------------------------------------------------- live

def _eid(m):
    return f"tennis:{m['tour'].upper()}:{m['date'].strftime('%Y%m%d')}:{m['id']}"


def register(con, now: datetime, allm: list[dict] | None = None) -> dict:
    """Store upcoming matches (so odds can be matched) and recent results (so picks settle)."""
    allm = allm if allm is not None else matches(now.date() - timedelta(days=3), (now + timedelta(days=7)).date(), now)
    con.execute("CREATE TABLE IF NOT EXISTS event_meta (event_id TEXT PRIMARY KEY, neutral INTEGER, competition TEXT)")
    n = 0
    for m in allm:
        if m["date"] < now - timedelta(days=3) or m["date"] > now + timedelta(days=7):
            continue
        eid, league = _eid(m), f"TENNIS:{m['tour'].upper()}"
        url = f"https://www.espn.com/tennis/scoreboard/tournament/_/eventId/{m['event_id_espn']}"
        done = m["completed"] and m["winner"] and not m.get("walkover")
        hs, as_ = (m["sets"] if done else (None, None))
        if done and hs == as_:   # retirement mid-set: score by winner
            hs, as_ = (1, 0) if m["winner"] == m["p1"] else (0, 1)
        con.execute("""INSERT INTO events(event_id,sport,league,season,kickoff_utc,home,away,status,home_score,away_score,
                       source,source_url,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(event_id) DO UPDATE SET kickoff_utc=excluded.kickoff_utc,
                       status=CASE WHEN excluded.status='finished' THEN 'finished' ELSE events.status END,
                       home_score=COALESCE(excluded.home_score, events.home_score),
                       away_score=COALESCE(excluded.away_score, events.away_score), updated_at=excluded.updated_at""",
                    (eid, "tennis", league, str(m["date"].year), m["date"].isoformat(), m["p1"], m["p2"],
                     "finished" if done else ("void" if m["completed"] else "scheduled"), hs, as_,
                     "espn.com (public scoreboard)", url, db.utcnow()))
        comp = f"{m['tour'].upper()} · {m['tournament']}" + (f" · {m['round']}" if m["round"] else "")
        con.execute("INSERT OR REPLACE INTO event_meta VALUES (?,?,?)", (eid, 1, comp))
        n += 1
    con.commit()
    return {"events": n}

def analyse(con, now: datetime, horizon_h: float = 168, publish_h: float | None = None) -> dict:
    from types import SimpleNamespace

    from . import watch
    from .engine import passes, price_generic
    from .intl import _publishable
    from .markets import Outcome
    from .pipeline import _latest_books, publish_pick
    rules = config.RULES
    allm = matches(date(2024, 1, 1), (now + timedelta(days=7)).date(), now)
    hist = [m for m in allm if m["date"] < now and m["completed"] and m["winner"] and not m.get("walkover")]
    elo = run_elo(hist)
    upcoming = [m for m in allm if not m["completed"] and now < m["date"] <= now + timedelta(hours=horizon_h)
                and m["state"] in ("STATUS_SCHEDULED", None)]
    rows, cands_by_event, hist_ok, meta, dinfo = [], {}, {}, {}, {}
    register(con, now, allm)
    for m in upcoming:
        eid, league = _eid(m), f"TENNIS:{m['tour'].upper()}"
        url = f"https://www.espn.com/tennis/scoreboard/tournament/_/eventId/{m['event_id_espn']}"
        comp = f"{m['tour'].upper()} · {m['tournament']}" + (f" · {m['round']}" if m["round"] else "")
        p1 = match_prob(elo, m)
        books, odds_ts, urls = _latest_books(con, eid, rules.max_odds_age_hours, now)
        fn = lambda mk, s, ln, p1=p1: Outcome(pw=p1 if s == "home" else 1 - p1, pl=1 - p1 if s == "home" else p1)  # noqa: E731
        cands = price_generic(fn, books, {"ML": 0.0}, rules.exchange_commission, markets=("ML",))
        n1, n2 = elo.matches_played(m["p1"]), elo.matches_played(m["p2"])
        hist_ok[eid] = min(n1, n2) >= 15
        rej = {f"{c.market}:{c.selection}:{c.line}": passes(c, rules, hist_ok[eid])[1] for c in cands}
        r1 = (1 - elo.w) * elo.r.get(m["p1"], 1500) + elo.w * elo.rs.get((m["p1"], m["surface"]), 1500)
        r2 = (1 - elo.w) * elo.r.get(m["p2"], 1500) + elo.w * elo.rs.get((m["p2"], m["surface"]), 1500)
        ctx = (f"Surface-adjusted Elo ({m['surface']}): {m['p1']} {r1:.0f} vs {m['p2']} {r2:.0f}; "
               f"{n1} and {n2} matches in Doyen's history" + ("; best of five sets." if m["slam"] and m["tour"] == "atp" else "."))
        if min(n1, n2) < 15:
            ctx += " Thin history for at least one player, so the rating is uncertain."
        mlc = {c.selection: c.market_q for c in cands if c.market_q is not None}
        rows.append(watch.analysis_row(sport="tennis", event_id=eid, competition=comp, title=f"{m['p1']} v {m['p2']}",
                                       participants=[m["p1"], m["p2"]], start_utc=m["date"].isoformat(), now=now,
                                       cands=cands, rejections=rej, odds_ts=odds_ts, history_ok=hist_ok[eid],
                                       model_view={m["p1"]: p1, m["p2"]: 1 - p1},
                                       book_view=({m["p1"]: mlc["home"], m["p2"]: mlc["away"]} if len(mlc) == 2 else {}),
                                       extra={"extra_text": ctx, "model_weight": 0}))
        cands_by_event[eid] = cands
        meta[eid] = (m, books, urls, odds_ts, ctx, url, league, comp)
        dinfo[eid] = {"n_min": min(n1, n2), "min_history": 15}
    soon = {k for k, v in meta.items() if v[0]["date"] <= now + timedelta(hours=publish_h or config.RULES.publish_window_hours)}
    from . import disagreement
    pool = {k: list(v) for k, v in cands_by_event.items() if k in soon}
    disagreement.filter_candidates(con, now, pool, None, dinfo)
    picks = _publishable(con, now, pool, hist_ok, rules)
    published = 0
    for rank, (eid, c) in enumerate(picks, 1):
        m, books, urls, odds_ts, ctx, url, league, comp = meta[eid]
        ev = SimpleNamespace(league=league, kickoff_utc=m["date"].isoformat(), home=m["p1"], away=m["p2"], source_url=url)
        published += publish_pick(con, now, eid, c, ev, {"context": ctx, "competition": comp}, books, urls, odds_ts, rank,
                                  "tennis-elo-0.1", ["Model weight 0: the edge is the price versus the multi-bookmaker consensus."])
    con.commit()
    bt = config.DATA_DIR / "backtest" / "tennis.json"
    note = "Match-winner market only. Picks need multi-bookmaker odds (The Odds API, when the tournament is listed)."
    if bt.exists():
        b = json.loads(bt.read_text())
        note += f" Model test log loss {b['test_logloss']['model']} on {b['n_test']} matches (coin flip {b['test_logloss']['coin_flip']})."
    watch.write("tennis", rows, {"operational": True, "markets": ["Match winner"], "picks_possible": True, "note": note})
    return {"upcoming": len(upcoming), "analysed": len(rows), "published": published, "history": len(hist)}
