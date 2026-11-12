"""National-team model: neutral-venue-aware Dixon-Coles, walk-forward validation, and
live MONITORING (model vs. the single available bookmaker).

Why monitoring and not recommendations: free international odds come from a single
bookmaker (DraftKings via ESPN), and no free historical international odds exist to
validate how much weight the model deserves against the market. Publishing picks would
violate the "no unvalidated edges" rule. Every prediction is stored with the bookmaker's
de-vigged probability, so the model-vs-market comparison accumulates out of sample and
can earn the model a validated blend weight later.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from . import config, db
from types import SimpleNamespace

from . import ev as evm
from .backtest import bootstrap_ci, calibration, logloss
from .engine import price_event
from .pipeline import publish_pick
from .markets import standard_markets
from .models import dixon_coles as dc
from .models.elo import fit_ordered_logit, ordered_logit_probs
from .sources import international as src

DEFAULTS = {"xi": 0.0010, "ridge": 2.0, "friendly_weight": 0.5, "years": 8, "min_matches": 15,
            "calib_power": 1.0}


def calibrate(P: np.ndarray, a: float) -> np.ndarray:
    """Power calibration of 1X2 probabilities: p_i^a / sum_j p_j^a. a > 1 sharpens
    (fixes underconfidence). `a` is fitted on the tune period only."""
    Q = np.power(np.clip(P, 1e-12, 1), a)
    return Q / Q.sum(axis=-1, keepdims=True)


def fit_calibration(P: np.ndarray, y: np.ndarray) -> float:
    from scipy.optimize import minimize_scalar
    r = minimize_scalar(lambda a: logloss(calibrate(P, a), y), bounds=(0.5, 3.0), method="bounded")
    return float(r.x)


def params() -> dict:
    p = dict(DEFAULTS)
    f = config.DATA_DIR / "tuned_international.json"
    if f.exists():
        p.update({k: v for k, v in json.loads(f.read_text()).items() if k in DEFAULTS})
    return p


def fit(train: pd.DataFrame, cutoff, xi, ridge, friendly_weight, years=8, with_cov=True, init=None):
    t = train[(train.kickoff_utc < cutoff) & (train.kickoff_utc >= cutoff - pd.Timedelta(days=365 * years))]
    days = (cutoff - t.kickoff_utc).dt.total_seconds().values / 86400
    mw = np.where(t.tournament.map(src.is_friendly), friendly_weight, 1.0)
    return dc.fit(t.home.values, t.away.values, t.hg.values, t.ag.values, days, xi=xi, ridge=ridge,
                  with_cov=with_cov, init=init, neutral=t.neutral.values, match_weight=mw)


def _elo(df: pd.DataFrame, k=30.0, hfa=80.0):
    r, out = {}, np.zeros(len(df))
    for i, row in enumerate(df.itertuples()):
        rh, ra = r.get(row.home, 1500.0), r.get(row.away, 1500.0)
        d = rh - ra + (0 if row.neutral else hfa)
        out[i] = d
        e = 1 / (1 + 10 ** (-d / 400))
        s = 1.0 if row.hg > row.ag else (0.5 if row.hg == row.ag else 0.0)
        gd = abs(row.hg - row.ag)
        mult = 1.0 if gd <= 1 else (1.5 if gd == 2 else (11 + gd) / 8)
        kk = k * (0.5 if src.is_friendly(row.tournament) else 1.0) * mult
        r[row.home], r[row.away] = rh + kk * (s - e), ra - kk * (s - e)
    return out


def walk_forward(df: pd.DataFrame, start, end, xi, ridge, fw, years=8, min_matches=15) -> pd.DataFrame:
    """Monthly refits; predictions for matches in the following month (pre-match info only)."""
    df = df.sort_values("kickoff_utc").reset_index(drop=True)
    df["elo_d"] = _elo(df)
    df["res"] = np.where(df.hg > df.ag, 2, np.where(df.hg == df.ag, 1, 0))
    rows, prev = [], None
    cut = pd.Timestamp(start, tz="UTC")
    while cut < pd.Timestamp(end, tz="UTC"):
        nxt = cut + pd.DateOffset(months=1)
        m = fit(df, cut, xi, ridge, fw, years, with_cov=False, init=prev)
        prev = m
        tr = df[(df.kickoff_utc < cut)].tail(8000)
        ol = fit_ordered_logit(tr.elo_d.values, tr.res.values)
        wk = df[(df.kickoff_utc >= cut) & (df.kickoff_utc < nxt)]
        if len(wk):
            ep = ordered_logit_probs(wk.elo_d.values, ol)
            for k, r in enumerate(wk.itertuples()):
                if not (m.has(r.home) and m.has(r.away)):
                    continue
                if min(m.n_matches[r.home], m.n_matches[r.away]) < min_matches:
                    continue
                mat = m.score_matrix(r.home, r.away, neutral=bool(r.neutral))
                ph, pd_ = float(np.tril(mat, -1).sum()), float(np.trace(mat))
                rows.append(dict(date=r.kickoff_utc, home=r.home, away=r.away, tournament=r.tournament,
                                 friendly=src.is_friendly(r.tournament), res=r.res,
                                 dc_H=ph, dc_D=pd_, dc_A=1 - ph - pd_,
                                 elo_H=ep[k, 0], elo_D=ep[k, 1], elo_A=ep[k, 2]))
        cut = nxt
    return pd.DataFrame(rows)


def _y(d):
    return np.where(d.res == 2, 0, np.where(d.res == 1, 1, 2))


def backtest(tune=("2023-01-01", "2025-01-01"), test=("2025-01-01", "2026-11-01"),
             grid_xi=(0.0007, 0.0015), grid_ridge=(1.0, 4.0), grid_fw=(0.5, 1.0)) -> dict:
    df = src.training_frame(datetime.now(timezone.utc), [])
    scores = {}
    for xi in grid_xi:
        for rg in grid_ridge:
            for fw in grid_fw:
                p = walk_forward(df, tune[0], tune[1], xi, rg, fw)
                scores[(xi, rg, fw)] = logloss(p[["dc_H", "dc_D", "dc_A"]].values, _y(p))
                print(f"  intl tune xi={xi} ridge={rg} fw={fw}: {scores[(xi, rg, fw)]:.5f} n={len(p)}")
    xi, rg, fw = min(scores, key=scores.get)
    tp = walk_forward(df, tune[0], tune[1], xi, rg, fw)
    a = fit_calibration(tp[["dc_H", "dc_D", "dc_A"]].values, _y(tp))
    print(f"  calibration power (tune period): {a:.3f}")
    t = walk_forward(df, test[0], test[1], xi, rg, fw)
    y = _y(t)
    P_raw, P_elo = t[["dc_H", "dc_D", "dc_A"]].values, t[["elo_H", "elo_D", "elo_A"]].values
    P_dc = calibrate(P_raw, a)
    base = np.tile(np.bincount(y, minlength=3) / len(y), (len(y), 1))
    li = lambda P: -np.log(np.clip(P[np.arange(len(y)), y], 1e-12, 1))  # noqa: E731
    comp = {}
    for name, mask in (("all", np.ones(len(t), bool)), ("competitive", ~t.friendly.values), ("friendly", t.friendly.values)):
        if mask.sum() < 50:
            continue
        comp[name] = {"n": int(mask.sum()), "dc": round(float(li(P_dc)[mask].mean()), 5),
                      "dc_uncalibrated": round(float(li(P_raw)[mask].mean()), 5),
                      "elo": round(float(li(P_elo)[mask].mean()), 5), "base_rate": round(float(li(base)[mask].mean()), 5)}
    rep = {"model": "dc-intl-0.1", "tune": tune, "test": test,
           "hyperparameters": {"xi": xi, "ridge": rg, "friendly_weight": fw, "calib_power": round(a, 4)},
           "tune_grid": {f"{k[0]}|{k[1]}|{k[2]}": round(v, 5) for k, v in scores.items()},
           "test_logloss": comp,
           "dc_minus_elo_ci95": [round(v, 5) for v in bootstrap_ci(li(P_dc) - li(P_elo))],
           "calibration_dc_home": calibration(P_dc[:, 0], (y == 0).astype(int)),
           "calibration_dc_home_uncalibrated": calibration(P_raw[:, 0], (y == 0).astype(int)),
           "note": "No free historical international odds exist, so model-vs-market cannot be backtested; it is tracked live."}
    (config.DATA_DIR / "tuned_international.json").write_text(json.dumps(
        {"xi": xi, "ridge": rg, "friendly_weight": fw, "calib_power": a, "created_at": db.utcnow()}, indent=2))
    (config.DATA_DIR / "backtest").mkdir(parents=True, exist_ok=True)
    (config.DATA_DIR / "backtest" / "international.json").write_text(json.dumps(rep, indent=2, default=str))
    con = db.connect()
    con.execute("INSERT INTO backtest_results(model_version,label,config_json,metrics_json,created_at) VALUES (?,?,?,?,?)",
                ("dc-intl-0.1", "international-walkforward", json.dumps(rep["hyperparameters"]),
                 json.dumps(rep, default=str), db.utcnow()))
    con.commit()
    return rep


# ---------------------------------------------------------------- live

def _form(train: pd.DataFrame, team: str, n: int = 6) -> dict:
    g = train[(train.home == team) | (train.away == team)].tail(n)
    res, gf, ga = [], 0, 0
    for r in g.itertuples():
        f, a = (r.hg, r.ag) if r.home == team else (r.ag, r.hg)
        gf, ga = gf + f, ga + a
        res.append("W" if f > a else ("D" if f == a else "L"))
    return {"last": "".join(res), "gf": int(gf), "ga": int(ga), "n": len(g)}


def _publishable(con, now, cands_by_event, hist_ok, rules):
    """Same selection rules as club football, blend weight 0, shared daily exposure cap, no re-publishing."""
    from .engine import select
    already = {r[0] for r in con.execute("SELECT event_id FROM recommendations")}
    pool = {k: v for k, v in cands_by_event.items() if k not in already}
    picks = select(pool, rules, hist_ok)
    today = con.execute("SELECT COUNT(*) FROM recommendations WHERE substr(published_at,1,10)=?",
                        (now.strftime("%Y-%m-%d"),)).fetchone()[0]
    room = max(0, int(rules.max_daily_units // rules.stake_units) - today)
    return picks[:room]


def ingest(con, now: datetime, ahead_days: int = 2) -> tuple[dict, list[dict]]:
    hist_last = src.load_history().kickoff_utc.max().date()
    start = max(hist_last, now.date() - timedelta(days=60))
    events, errors = src.collect(start, now.date() + timedelta(days=ahead_days), now)
    out = src.store(con, events)
    out["errors"] = errors[:10]
    out["gap_fill_from"] = str(start)
    con.commit()
    return out, events


def analyse(con, now: datetime, recent: list[dict], horizon_h: float = 48) -> dict:
    p = params()
    rules = config.RULES
    train = src.training_frame(now, recent)
    model = fit(train, pd.Timestamp(now).tz_convert("UTC"), p["xi"], p["ridge"], p["friendly_weight"], p["years"], with_cov=True)
    run_id = f"dc-intl-0.1:INT:{now.strftime('%Y%m%dT%H%M')}"
    con.execute("INSERT OR IGNORE INTO model_runs VALUES (?,?,?,?,?,?,?)",
                (run_id, "dc-intl-0.1", "INT", now.isoformat(), int(len(train)),
                 json.dumps({**p, "home": model.home, "rho": model.rho}), db.utcnow()))
    evs = con.execute("""SELECT e.*, COALESCE(m.neutral,0) neutral, m.competition FROM events e
                         LEFT JOIN event_meta m USING(event_id)
                         WHERE e.league LIKE 'INT:%' AND e.status='scheduled' AND e.kickoff_utc > ? AND e.kickoff_utc <= ?
                         ORDER BY e.kickoff_utc""", (now.isoformat(), (now + timedelta(hours=horizon_h)).isoformat())).fetchall()
    rng = np.random.default_rng(int(now.timestamp()) // 86400)
    rows, skipped = [], []
    cands_by_event, hist_ok, meta = {}, {}, {}
    for e in evs:
        if not (model.has(e["home"]) and model.has(e["away"])):
            skipped.append(f"{e['home']} v {e['away']}: team not in history (name mismatch?)")
            continue
        nmin = min(model.n_matches[e["home"]], model.n_matches[e["away"]])
        neutral = bool(e["neutral"])
        mat = model.score_matrix(e["home"], e["away"], neutral=neutral)
        mk = standard_markets(mat)
        p1 = calibrate(np.array([mk["1X2:H"], mk["1X2:D"], mk["1X2:A"]]), p["calib_power"])
        mk["1X2:H"], mk["1X2:D"], mk["1X2:A"] = (float(x) for x in p1)
        from .pipeline import _latest_books
        books, odds_ts, urls = _latest_books(con, e["event_id"], rules.max_odds_age_hours, now)
        cands = price_event(model, e["home"], e["away"], books, {}, rules.exchange_commission,
                            n_draws=200, rng=rng, neutral=neutral, markets=("1X2", "OU", "AH"))
        cal = {"H": mk["1X2:H"], "D": mk["1X2:D"], "A": mk["1X2:A"]}
        for c in cands:
            if c.market == "1X2":
                c.model_q = cal[c.selection]
            con.execute("""INSERT OR IGNORE INTO predictions(run_id,event_id,market,selection,line,model_prob,prob_sd,
                           market_prob,final_prob,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (run_id, e["event_id"], c.market, c.selection, c.line, c.model_q, c.prob_sd,
                         c.market_q, c.market_q, db.utcnow()))
        if not cands:
            for s, k in (("H", "1X2:H"), ("D", "1X2:D"), ("A", "1X2:A")):
                con.execute("""INSERT OR IGNORE INTO predictions(run_id,event_id,market,selection,line,model_prob,
                               created_at) VALUES (?,?,?,?,?,?,?)""", (run_id, e["event_id"], "1X2", s, None, mk[k], db.utcnow()))
        best = None
        for c in [c for c in cands if c.market == "1X2"]:  # OU/AH not yet calibrated -> not shown
            model_ev = c.active * (c.model_q * c.net_odds - 1)
            if best is None or model_ev > best[0]:
                best = (model_ev, c)
        row = {"event_id": e["event_id"], "competition": e["competition"], "kickoff_utc": e["kickoff_utc"],
               "home": e["home"], "away": e["away"], "neutral": neutral, "min_matches": nmin,
               "model_1x2": [round(mk["1X2:H"], 4), round(mk["1X2:D"], 4), round(mk["1X2:A"], 4)],
               "xg": [round(mk["exp_home_goals"], 2), round(mk["exp_away_goals"], 2)],
               "source_url": e["source_url"]}
        c1 = [c for c in cands if c.market == "1X2"]
        if len(c1) == 3:
            if all(c.market_q is not None for c in c1):
                row["book_1x2"] = [round(float(next(c.market_q for c in c1 if c.selection == s)), 4) for s in "HDA"]
            row["bookmaker"] = c1[0].bookmaker
        if best:
            ev_, c = best
            row["largest_gap"] = {"market": c.market, "selection": c.selection, "line": c.line, "odds": c.odds,
                                  "model_q": round(float(c.model_q), 4),
                                  "book_q": round(float(c.market_q), 4) if c.market_q else None,
                                  "model_ev": round(float(ev_), 4), "prob_sd": round(float(c.prob_sd), 4)}
        g = row.get("largest_gap")
        if g and row.get("book_1x2"):
            fav = int(np.argmax(row["book_1x2"]))
            if max(row["book_1x2"]) > 0.70 and "HDA"[fav] != g["selection"]:
                g["flag"] = ("known model bias: underconfident on heavy favourites out of sample "
                             "(predicted 85% -> observed 94%); this gap is likely an artifact")
        rows.append(row)
        # Multi-bookmaker events can yield real (paper) recommendations: price vs. sharp consensus,
        # model weight 0 (the international model is not validated against the market).
        cands_by_event[e["event_id"]] = cands
        hist_ok[e["event_id"]] = nmin >= p["min_matches"]
        meta[e["event_id"]] = (e, books, urls, odds_ts, mk, row)
    picks = _publishable(con, now, cands_by_event, hist_ok, rules)
    published = 0
    for rank, (eid, c) in enumerate(picks, 1):
        e, books, urls, odds_ts, mk, row = meta[eid]
        ev = SimpleNamespace(league=e["league"], kickoff_utc=e["kickoff_utc"], home=e["home"], away=e["away"],
                             source_url=e["source_url"])
        risks = ["International selection: the model has weight 0. The edge is the price versus the sharp "
                 "de-vigged consensus (validated on club data: +4.5% CLV), not a model opinion.",
                 "Team news (call-ups, withdrawals, rotation) moves international prices sharply and is not modelled."]
        if c.market_q is not None and abs(c.model_q - c.market_q) > 0.05:
            risks.append(f"Model and market disagree by {c.model_q - c.market_q:+.1%}.")
        g = row.get("largest_gap") or {}
        if g.get("flag") and g.get("selection") == c.selection and c.market == "1X2":
            risks.append(g["flag"])
        evidence = {"expected_goals": {"home": row["xg"][0], "away": row["xg"][1]},
                    "model_markets": {k: round(v, 4) for k, v in mk.items()},
                    "form": {e["home"]: _form(train, e["home"]), e["away"]: _form(train, e["away"])},
                    "neutral_venue": row["neutral"], "competition": row["competition"],
                    "train_matches": {e["home"]: model.n_matches[e["home"]], e["away"]: model.n_matches[e["away"]]}}
        published += publish_pick(con, now, eid, c, ev, evidence, books, urls, odds_ts, rank, "dc-intl-0.1+mkt", risks)
    con.commit()
    rows.sort(key=lambda r: r.get("largest_gap", {}).get("model_ev", -9), reverse=True)
    return {"run_id": run_id, "events_in_window": len(evs), "analysed": len(rows), "rows": rows,
            "published": published, "multi_book_events": sum(1 for cs in cands_by_event.values()
                                                              if any(c.n_books >= rules.min_bookmakers for c in cs)),
            "skipped": skipped, "train_matches": int(len(train)), "params": p}
