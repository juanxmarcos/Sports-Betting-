"""NFL and NBA: data, points-rating model, backtest and live analysis.

Data (free):
- ESPN public scoreboard JSON: fixtures, results, DraftKings odds (moneyline/spread/total).
- NFL history: nflverse games.csv (1999-present) incl. closing moneylines/spreads/totals.
- NBA history: ESPN daily scoreboards (backfilled once, cached).
- Multi-bookmaker odds: The Odds API (americanfootball_nfl, basketball_nba) when the key is set.

Picks use the standard selection rules. The model's blend weight comes from the backtest
(NFL: fitted against closing lines; NBA: 0 until validated, because no free NBA odds
history exists), so picks never rest on an unvalidated model opinion.
"""
from __future__ import annotations

import io
import json
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pandas as pd

from . import config, db
from . import ev as evm
from .engine import passes, price_generic, select
from .models import ratings
from .sources.http import fetch

ESPN = "https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={d}"
NFLVERSE = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
SOURCE = "espn.com (public scoreboard)"

CFG = {
    "nfl": {"path": "football/nfl", "league": "NFL", "name": "NFL", "min_games": 6, "lookback": 3 * 365,
            "competition": "NFL", "defaults": {"xi": 0.003, "ridge": 8.0}},
    "nba": {"path": "basketball/nba", "league": "NBA", "name": "NBA", "min_games": 10, "lookback": 420,
            "competition": "NBA", "defaults": {"xi": 0.006, "ridge": 10.0}},
}
NBA_SEASONS = [("2024-10-22", "2025-06-22"), ("2025-10-21", "2026-06-21"), ("2026-10-20", None)]


def params(sport: str) -> dict:
    p = dict(CFG[sport]["defaults"])
    p["blend_weight"] = {"ML": 0.0, "SPREAD": 0.0, "TOTAL": 0.0}
    f = config.DATA_DIR / f"tuned_{sport}.json"
    if f.exists():
        t = json.loads(f.read_text())
        p.update({k: t[k] for k in ("xi", "ridge", "blend_weight") if k in t})
    return p


# ---------------------------------------------------------------- ESPN parsing

def _am(s):
    from .sources.international import american_to_decimal
    return american_to_decimal(s)


def parse_espn(e: dict, sport: str) -> dict | None:
    c = (e.get("competitions") or [None])[0]
    if not c:
        return None
    t = {x.get("homeAway"): x for x in c.get("competitors", [])}
    if "home" not in t or "away" not in t:
        return None
    st = (e.get("status") or {}).get("type") or {}
    ev = {"espn_id": e["id"], "sport": sport, "league": CFG[sport]["league"],
          "kickoff_utc": datetime.fromisoformat(e["date"].replace("Z", "+00:00")),
          "home": t["home"]["team"]["displayName"], "away": t["away"]["team"]["displayName"],
          "home_abbr": t["home"]["team"].get("abbreviation"), "away_abbr": t["away"]["team"].get("abbreviation"),
          "neutral": bool(c.get("neutralSite")), "completed": bool(st.get("completed")),
          "hs": None, "as": None, "odds": [],
          "season_type": (e.get("season") or {}).get("type")}
    if ev["completed"]:
        try:
            ev["hs"], ev["as"] = int(float(t["home"]["score"])), int(float(t["away"]["score"]))
        except (TypeError, ValueError, KeyError):
            ev["completed"] = False
    for o in c.get("odds") or []:
        if not isinstance(o, dict):
            continue
        from .sources.books import normalize_book as _nb
        bk = _nb((o.get("provider") or {}).get("name", "ESPN odds"))
        if not bk:
            continue
        ml = o.get("moneyline") or {}
        for side in ("home", "away"):
            px = _am(((ml.get(side) or {}).get("close") or {}).get("odds"))
            if px:
                ev["odds"].append((bk, "ML", side, None, px))
        sp = o.get("pointSpread") or {}
        for side in ("home", "away"):
            rec = (sp.get(side) or {}).get("close") or {}
            px = _am(rec.get("odds"))
            try:
                ln = float(rec.get("line"))
            except (TypeError, ValueError):
                ln = None
            if px and ln is not None:
                ev["odds"].append((bk, "SPREAD", side, ln if side == "home" else -ln, px))
        tot = o.get("total") or {}
        for side in ("over", "under"):
            rec = (tot.get(side) or {}).get("close") or {}
            px = _am(rec.get("odds"))
            try:
                ln = float(str(rec.get("line"))[1:]) if rec.get("line") else None
            except ValueError:
                ln = None
            if px and ln is not None:
                ev["odds"].append((bk, "TOTAL", side, ln, px))
    return ev


def scoreboard(sport: str, d: date, max_age_hours: float) -> list[dict]:
    content, _ = fetch(ESPN.format(path=CFG[sport]["path"], d=d.strftime("%Y%m%d")), max_age_hours=max_age_hours)
    out = []
    for e in json.loads(content).get("events", []):
        try:
            x = parse_espn(e, sport)
        except (KeyError, TypeError, ValueError, AttributeError) as ex:
            print(f"warning: skipped malformed ESPN {sport} event {e.get('id')}: {ex}")
            continue
        if x:
            out.append(x)
    return out


def event_id(ev: dict) -> str:
    return f"{ev['sport']}:{ev['league']}:{ev['kickoff_utc'].strftime('%Y%m%d')}:{ev['espn_id']}"


def store(con, events: list[dict]) -> dict:
    now = db.utcnow()
    n = k = 0
    con.execute("CREATE TABLE IF NOT EXISTS event_meta (event_id TEXT PRIMARY KEY, neutral INTEGER, competition TEXT)")
    for ev in events:
        eid = event_id(ev)
        url = f"https://www.espn.com/{CFG[ev['sport']]['path'].split('/')[0]}/game/_/gameId/{ev['espn_id']}"
        con.execute("""
            INSERT INTO events(event_id,sport,league,season,kickoff_utc,home,away,status,home_score,away_score,
                               source,source_url,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(event_id) DO UPDATE SET kickoff_utc=excluded.kickoff_utc,
              status=CASE WHEN excluded.status='finished' THEN 'finished' ELSE events.status END,
              home_score=COALESCE(excluded.home_score, events.home_score),
              away_score=COALESCE(excluded.away_score, events.away_score), updated_at=excluded.updated_at""",
                    (eid, ev["sport"], ev["league"], str(ev["kickoff_utc"].year), ev["kickoff_utc"].isoformat(),
                     ev["home"], ev["away"], "finished" if ev["completed"] else "scheduled", ev["hs"], ev["as"],
                     SOURCE, url, now))
        comp = CFG[ev["sport"]]["competition"] + (" Playoffs" if ev.get("season_type") == 3 else "")
        con.execute("INSERT OR REPLACE INTO event_meta VALUES (?,?,?)", (eid, int(ev["neutral"]), comp))
        n += 1
        if not ev["completed"]:
            for bk, market, sel, line, px in ev["odds"]:
                cur = con.execute("""INSERT OR IGNORE INTO odds(event_id,bookmaker,market,selection,line,price,kind,
                                     source,source_url,retrieved_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                                  (eid, bk, market, sel, line, px, "pre", SOURCE, url, now))
                k += cur.rowcount
    con.commit()
    return {"events": n, "odds": k}


# ---------------------------------------------------------------- history

NFL_ABBR = {"LAR": "LA", "WSH": "WAS"}


def nfl_history(max_age_hours: float = 12) -> pd.DataFrame:
    content, _ = fetch(NFLVERSE, max_age_hours=max_age_hours)
    df = pd.read_csv(io.BytesIO(content))
    df["kickoff_utc"] = pd.to_datetime(df.gameday + " " + df.gametime.fillna("13:00"), errors="coerce") \
        .dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
    df = df.dropna(subset=["kickoff_utc"])
    out = pd.DataFrame({"home": df.home_team, "away": df.away_team, "hs": df.home_score, "as": df.away_score,
                        "kickoff_utc": df.kickoff_utc, "neutral": (df.location == "Neutral").astype(int),
                        "season": df.season, "week": df.week, "espn": df.espn,
                        "home_ml": df.home_moneyline, "away_ml": df.away_moneyline,
                        "spread_line": df.spread_line, "total_line": df.total_line,
                        "home_rest": df.home_rest, "away_rest": df.away_rest})
    return out.sort_values("kickoff_utc").reset_index(drop=True)


def nba_history(now: datetime) -> pd.DataFrame:
    rows = []
    for start, end in NBA_SEASONS:
        d = date.fromisoformat(start)
        stop = min(date.fromisoformat(end) if end else now.date(), now.date() - timedelta(days=1))
        while d <= stop:
            past = d < now.date() - timedelta(days=2)
            for ev in scoreboard("nba", d, 24 * 365 if past else 1):
                if ev["completed"] and ev["season_type"] in (2, 3, 5, None):
                    rows.append({"home": ev["home"], "away": ev["away"], "hs": ev["hs"], "as": ev["as"],
                                 "kickoff_utc": pd.Timestamp(ev["kickoff_utc"]), "neutral": int(ev["neutral"]),
                                 "espn": ev["espn_id"]})
            d += timedelta(days=1)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.drop_duplicates("espn").sort_values("kickoff_utc").reset_index(drop=True)


def add_rest(df: pd.DataFrame) -> pd.DataFrame:
    """Back-to-back flags (NBA) computed from the schedule itself (pre-game information)."""
    last: dict = {}
    hb, ab = [], []
    for r in df.itertuples():
        for team, lst in ((r.home, hb), (r.away, ab)):
            prev = last.get(team)
            lst.append(1.0 if prev is not None and (r.kickoff_utc - prev).total_seconds() < 36 * 3600 else 0.0)
        last[r.home] = last[r.away] = r.kickoff_utc
    df = df.copy()
    df["home_b2b"], df["away_b2b"] = hb, ab
    return df


USE_REST = False  # backtest: the back-to-back feature did not improve out-of-sample log loss -> simpler model


def _fit(sport, train: pd.DataFrame, cutoff, xi, ridge):
    days = (cutoff - train.kickoff_utc).dt.total_seconds().values / 86400
    if sport == "nba" and USE_REST:
        return ratings.fit(train.home.values, train.away.values, train.hs.values, train["as"].values, days, xi, ridge,
                           neutral=train.neutral.values, f_home=train[["home_b2b"]].values,
                           f_away=train[["away_b2b"]].values, feature_names=["b2b"])
    return ratings.fit(train.home.values, train.away.values, train.hs.values, train["as"].values, days, xi, ridge,
                       neutral=train.neutral.values)


# ---------------------------------------------------------------- backtest

def _p_home(m, ph, pa):
    return ratings.outcome(m, ph, pa, "ML", "home", None).pw


def backtest_nfl(tune=(2018, 2020), validate=(2021, 2022), test=(2023, 2026),
                 grid=((0.002, 4.0), (0.002, 10.0), (0.004, 4.0), (0.004, 10.0), (0.007, 10.0))) -> dict:
    from scipy.optimize import minimize_scalar
    from .backtest import bootstrap_ci, calibration
    df = nfl_history()
    df = df[df.hs.notna()].reset_index(drop=True)

    def walk(lo, hi, xi, ridge):
        out = []
        for (season, week), g in df[(df.season >= lo) & (df.season <= hi)].groupby(["season", "week"], sort=True):
            cut = g.kickoff_utc.min() - pd.Timedelta(hours=1)
            tr = df[(df.kickoff_utc < cut) & (df.kickoff_utc >= cut - pd.Timedelta(days=CFG["nfl"]["lookback"]))]
            m = _fit("nfl", tr, cut, xi, ridge)
            for r in g.itertuples():
                if not (m.has(r.home) and m.has(r.away)):
                    continue
                ph, pa = m.expected(r.home, r.away, bool(r.neutral))
                rec = {"season": season, "y": 1.0 if r.hs > r.as_ else (0.0 if r.hs < r.as_ else np.nan),
                       "p_model": _p_home(m, ph, pa)}
                if pd.notna(r.home_ml) and pd.notna(r.away_ml):
                    from .sources.international import american_to_decimal as a2d
                    oh, oa = a2d(r.home_ml), a2d(r.away_ml)
                    if oh and oa:
                        rec["p_market"] = float(evm.devig_power([oh, oa])[0])
                out.append(rec)
        return pd.DataFrame(out).dropna(subset=["y"])

    df = df.rename(columns={"as": "as_"}).assign(**{"as": lambda d: d["as_"]})
    ll = lambda p, y: float(-(y * np.log(np.clip(p, 1e-9, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-9, 1))).mean())  # noqa: E731
    scores = {}
    for xi, rg in grid:
        t = walk(*tune, xi, rg)
        scores[(xi, rg)] = ll(t.p_model, t.y)
        print(f"  nfl tune xi={xi} ridge={rg}: {scores[(xi, rg)]:.5f} n={len(t)}")
    xi, rg = min(scores, key=scores.get)
    v = walk(*validate, xi, rg).dropna(subset=["p_market"])
    w = float(minimize_scalar(lambda w: ll(w * v.p_model + (1 - w) * v.p_market, v.y), bounds=(0, 1), method="bounded").x)
    t = walk(*test, xi, rg).dropna(subset=["p_market"])
    li = lambda p: -(t.y * np.log(np.clip(p, 1e-9, 1)) + (1 - t.y) * np.log(np.clip(1 - p, 1e-9, 1)))  # noqa: E731
    rep = {"sport": "nfl", "model": "points-ridge-0.1", "tune": tune, "validate": validate, "test": test,
           "hyperparameters": {"xi": xi, "ridge": rg}, "tune_grid": {f"{k[0]}|{k[1]}": round(s, 5) for k, s in scores.items()},
           "blend_weight_ml": round(w, 4), "n_test": int(len(t)),
           "test_logloss": {"model": round(float(li(t.p_model).mean()), 5), "market_closing": round(float(li(t.p_market).mean()), 5),
                            "blend": round(float(li(w * t.p_model + (1 - w) * t.p_market).mean()), 5),
                            "home_rate": round(ll(np.full(len(t), t.y.mean()), t.y), 5)},
           "model_minus_market_ci95": [round(x, 5) for x in bootstrap_ci((li(t.p_model) - li(t.p_market)).values)],
           "calibration_model": calibration(t.p_model.values, t.y.values.astype(int)),
           "note": "Market = de-vigged closing moneyline (nflverse). Closing lines are the hardest benchmark."}
    _save(sport="nfl", rep=rep, tuned={"xi": xi, "ridge": rg,
                                       "blend_weight": {"ML": round(w, 4), "SPREAD": round(w, 4), "TOTAL": 0.0}})
    return rep


def backtest_nba(tune=("2025-01-01", "2025-06-22"), test=("2025-10-21", None),
                 grid=((0.003, 5.0), (0.006, 5.0), (0.006, 15.0), (0.012, 10.0))) -> dict:
    from .backtest import bootstrap_ci, calibration
    now = datetime.now(timezone.utc)
    df = add_rest(nba_history(now))

    def walk(lo, hi, xi, rg, use_rest=True):
        lo, hi = pd.Timestamp(lo, tz="UTC"), pd.Timestamp(hi or now, tz="UTC") if hi else pd.Timestamp(now)
        out, cut = [], lo
        while cut < hi:
            nxt = cut + pd.Timedelta(days=7)
            tr = df[(df.kickoff_utc < cut) & (df.kickoff_utc >= cut - pd.Timedelta(days=CFG["nba"]["lookback"]))]
            g = df[(df.kickoff_utc >= cut) & (df.kickoff_utc < nxt)]
            if len(g) and len(tr) > 300:
                m = _fit("nba", tr, cut, xi, rg)
                for r in g.itertuples():
                    if not (m.has(r.home) and m.has(r.away)):
                        continue
                    fh, fa = ([r.home_b2b], [r.away_b2b]) if use_rest else ([0.0], [0.0])
                    ph, pa = m.expected(r.home, r.away, bool(r.neutral), fh, fa)
                    out.append({"y": 1.0 if r.hs > r.as_ else 0.0, "p_model": _p_home(m, ph, pa)})
            cut = nxt
        return pd.DataFrame(out)

    df = df.rename(columns={"as": "as_"}).assign(**{"as": lambda d: d["as_"]})
    ll = lambda p, y: float(-(y * np.log(np.clip(p, 1e-9, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-9, 1))).mean())  # noqa: E731
    scores = {}
    for xi, rg in grid:
        t = walk(*tune, xi, rg)
        scores[(xi, rg)] = ll(t.p_model, t.y)
        print(f"  nba tune xi={xi} ridge={rg}: {scores[(xi, rg)]:.5f} n={len(t)}")
    xi, rg = min(scores, key=scores.get)
    t = walk(*test, xi, rg)
    t0 = walk(*test, xi, rg, use_rest=False)
    rep = {"sport": "nba", "model": "points-ridge-0.1", "tune": tune, "test": test,
           "hyperparameters": {"xi": xi, "ridge": rg}, "tune_grid": {f"{k[0]}|{k[1]}": round(s, 5) for k, s in scores.items()},
           "n_test": int(len(t)),
           "test_logloss": {"model": round(ll(t.p_model, t.y), 5), "model_without_rest": round(ll(t0.p_model, t0.y), 5),
                            "home_rate": round(ll(np.full(len(t), t.y.mean()), t.y), 5)},
           "calibration_model": calibration(t.p_model.values, t.y.values.astype(int)),
           "note": "No free historical NBA odds: the model cannot be validated against the market, so its blend weight is 0 "
                   "and live picks rest on price versus multi-bookmaker consensus only."}
    _save(sport="nba", rep=rep, tuned={"xi": xi, "ridge": rg, "blend_weight": {"ML": 0.0, "SPREAD": 0.0, "TOTAL": 0.0}})
    return rep


def _save(sport, rep, tuned):
    (config.DATA_DIR / "backtest").mkdir(parents=True, exist_ok=True)
    (config.DATA_DIR / "backtest" / f"{sport}.json").write_text(json.dumps(rep, indent=2, default=str))
    (config.DATA_DIR / f"tuned_{sport}.json").write_text(json.dumps({**tuned, "created_at": db.utcnow()}, indent=2))
    con = db.connect()
    con.execute("INSERT INTO backtest_results(model_version,label,config_json,metrics_json,created_at) VALUES (?,?,?,?,?)",
                (f"{sport}-points-0.1", f"{sport}-walkforward", json.dumps(tuned), json.dumps(rep, default=str), db.utcnow()))
    con.commit()


# ---------------------------------------------------------------- live

def ingest(con, now: datetime, sport: str, ahead_days: int = 7) -> dict:
    events, errors = [], []
    for k in range(-2, ahead_days + 1):
        d = now.date() + timedelta(days=k)
        try:
            events += scoreboard(sport, d, 0.9)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{d}: {e}")
    out = store(con, events)
    out["errors"] = errors[:5]
    return out


def _team_key(sport, name, abbr):
    return name


def analyse(con, now: datetime, sport: str, horizon_h: float = 168, publish_h: float = 48) -> dict:
    from . import watch
    from .pipeline import _latest_books, publish_pick
    cfg, p, rules = CFG[sport], params(sport), config.RULES
    if sport == "nfl":
        hist = nfl_history()
        hist = hist[hist.hs.notna()]
        # nflverse uses abbreviations; map them to ESPN display names
        abbr_name = _nfl_abbr_names(con)
        hist = hist.assign(home=hist.home.map(lambda a: abbr_name.get(a, a)), away=hist.away.map(lambda a: abbr_name.get(a, a)))
    else:
        hist = add_rest(nba_history(now))
    train = hist[(hist.kickoff_utc < pd.Timestamp(now)) &
                 (hist.kickoff_utc >= pd.Timestamp(now) - pd.Timedelta(days=cfg["lookback"]))]
    if len(train) < 100:
        watch.write(sport, [], {"operational": False, "note": f"Only {len(train)} training games available."})
        return {"error": "insufficient history", "train": len(train)}
    model = _fit(sport, train, pd.Timestamp(now), p["xi"], p["ridge"])
    run_id = f"{sport}-points-0.1:{cfg['league']}:{now.strftime('%Y%m%dT%H%M')}"
    con.execute("INSERT OR IGNORE INTO model_runs VALUES (?,?,?,?,?,?,?)",
                (run_id, f"{sport}-points-0.1", cfg["league"], now.isoformat(), int(len(train)),
                 json.dumps({**p, "hfa": model.hfa, "sd_margin": model.sd_margin, "sd_total": model.sd_total}), db.utcnow()))
    evs = con.execute("""SELECT e.*, COALESCE(m.neutral,0) neutral, m.competition FROM events e LEFT JOIN event_meta m USING(event_id)
                         WHERE e.league=? AND e.status='scheduled' AND e.kickoff_utc > ? AND e.kickoff_utc <= ?
                         ORDER BY e.kickoff_utc""", (cfg["league"], now.isoformat(),
                                                      (now + timedelta(hours=horizon_h)).isoformat())).fetchall()
    last_game = {}
    for r in train.itertuples():
        last_game[r.home] = last_game[r.away] = r.kickoff_utc
    rows, cands_by_event, hist_ok, meta = [], {}, {}, {}
    ranks = sorted(model.teams, key=model.rating, reverse=True)
    for e in evs:
        h, a = e["home"], e["away"]
        if not (model.has(h) and model.has(a)):
            continue
        ko = pd.Timestamp(e["kickoff_utc"])
        fh = fa = None
        if sport == "nba" and USE_REST:
            fh = [1.0 if h in last_game and (ko - last_game[h]).total_seconds() < 36 * 3600 else 0.0]
            fa = [1.0 if a in last_game and (ko - last_game[a]).total_seconds() < 36 * 3600 else 0.0]
        ph, pa = model.expected(h, a, bool(e["neutral"]), fh, fa)
        books, odds_ts, urls = _latest_books(con, e["event_id"], rules.max_odds_age_hours, now)
        fn = lambda mk, s, ln, ph=ph, pa=pa: ratings.outcome(model, ph, pa, mk, s, ln)  # noqa: E731
        cands = price_generic(fn, books, p["blend_weight"], rules.exchange_commission)
        for c in cands:
            con.execute("""INSERT OR IGNORE INTO predictions(run_id,event_id,market,selection,line,model_prob,market_prob,
                           final_prob,created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
                        (run_id, e["event_id"], c.market, c.selection, c.line, c.model_q, c.market_q, c.final_q, db.utcnow()))
        p_home = ratings.outcome(model, ph, pa, "ML", "home", None).pw
        if not cands:
            con.execute("""INSERT OR IGNORE INTO predictions(run_id,event_id,market,selection,line,model_prob,created_at)
                           VALUES (?,?,?,?,?,?,?)""", (run_id, e["event_id"], "ML", "home", None, p_home, db.utcnow()))
        nmin = min(model.n_games.get(h, 0), model.n_games.get(a, 0))
        hist_ok[e["event_id"]] = nmin >= cfg["min_games"]
        rej = {f"{c.market}:{c.selection}:{c.line}": passes(c, rules, hist_ok[e["event_id"]])[1] for c in cands}
        mlc = {c.selection: c.market_q for c in cands if c.market == "ML" and c.market_q is not None}
        unit = "pts"
        context = (f"Doyen's ratings project {h} {ph:.1f} – {a} {pa:.1f} {unit} "
                   f"(margin {ph - pa:+.1f}, total {ph + pa:.1f}); power ranks {ranks.index(h) + 1} and {ranks.index(a) + 1} "
                   f"of {len(ranks)}.")
        b2b = [t for t in (h, a) if t in last_game and (ko - last_game[t]).total_seconds() < 36 * 3600] if sport == "nba" else []
        if b2b:
            context += " " + " and ".join(b2b) + " on the second night of a back-to-back (not a model input: it did not improve out-of-sample accuracy)."
        rows.append(watch.analysis_row(
            sport=sport, event_id=e["event_id"], competition=e["competition"] or cfg["competition"], title=f"{a} at {h}",
            participants=[h, a], start_utc=e["kickoff_utc"], now=now, cands=cands, rejections=rej, odds_ts=odds_ts,
            neutral=bool(e["neutral"]),
            model_view={f"{h} win": p_home, f"{a} win": 1 - p_home},
            book_view=({f"{h} win": mlc["home"], f"{a} win": mlc["away"]} if len(mlc) == 2 else {}),
            extra={"extra_text": context, "model_weight": p["blend_weight"].get("ML", 0)}))
        cands_by_event[e["event_id"]] = cands
        meta[e["event_id"]] = (e, books, urls, odds_ts, context, ph, pa)
    # publish (standard rules, shared daily cap, no re-publishing)
    from .intl import _publishable
    soon = {k for k, v in meta.items() if datetime.fromisoformat(v[0]["kickoff_utc"]) <= now + timedelta(hours=publish_h)}
    picks = _publishable(con, now, {k: v for k, v in cands_by_event.items() if k in soon}, hist_ok, rules)
    published = 0
    for rank, (eid, c) in enumerate(picks, 1):
        e, books, urls, odds_ts, context, ph, pa = meta[eid]
        ev = SimpleNamespace(league=cfg["league"], kickoff_utc=e["kickoff_utc"], home=e["home"], away=e["away"],
                             source_url=e["source_url"])
        risks = [f"Model weight {c.blend_w:.2f}: " + ("the edge is the price versus the multi-bookmaker consensus, "
                 "not a model opinion." if c.blend_w < 0.05 else "the probability blends the model with the market.")]
        if c.market_q is not None and abs(c.model_q - c.market_q) > 0.05:
            risks.append(f"Model and market disagree by {c.model_q - c.market_q:+.1%}.")
        evidence = {"context": context, "competition": e["competition"] or cfg["competition"],
                    "projection": {"home": round(ph, 1), "away": round(pa, 1)}}
        published += publish_pick(con, now, eid, c, ev, evidence, books, urls, odds_ts, rank, f"{sport}-points-0.1", risks)
    con.commit()
    bt = config.DATA_DIR / "backtest" / f"{sport}.json"
    note = None
    if bt.exists():
        b = json.loads(bt.read_text())
        tl = b.get("test_logloss", {})
        note = (f"Model validated out of sample on {b.get('n_test')} games (log loss {tl.get('model')}"
                + (f" vs closing market {tl.get('market_closing')}" if tl.get("market_closing") else "") + ").")
    watch.write(sport, rows, {"operational": True, "markets": ["Moneyline", "Point spread", "Total points"],
                              "picks_possible": True, "note": note})
    return {"events_in_window": len(evs), "analysed": len(rows), "published": published, "train": int(len(train))}


def _nfl_abbr_names(con) -> dict:
    """nflverse abbreviation -> ESPN display name, learned from current ESPN events (plus fixed aliases)."""
    out = {}
    base = {"ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens", "BUF": "Buffalo Bills",
            "CAR": "Carolina Panthers", "CHI": "Chicago Bears", "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns",
            "DAL": "Dallas Cowboys", "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
            "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars", "KC": "Kansas City Chiefs",
            "LA": "Los Angeles Rams", "LAC": "Los Angeles Chargers", "LV": "Las Vegas Raiders", "MIA": "Miami Dolphins",
            "MIN": "Minnesota Vikings", "NE": "New England Patriots", "NO": "New Orleans Saints", "NYG": "New York Giants",
            "NYJ": "New York Jets", "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers", "SEA": "Seattle Seahawks",
            "SF": "San Francisco 49ers", "TB": "Tampa Bay Buccaneers", "TEN": "Tennessee Titans", "WAS": "Washington Commanders",
            "OAK": "Las Vegas Raiders", "SD": "Los Angeles Chargers", "STL": "Los Angeles Rams"}
    out.update(base)
    return out
