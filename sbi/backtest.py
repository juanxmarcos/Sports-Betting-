"""Walk-forward backtest with strict chronology.

For each league, every 7 days the DC model is refitted on matches that kicked off
BEFORE the refit date only, then used to price the following 7 days. Elo ratings are
computed sequentially (pre-match). Market benchmarks use the pre-match odds that
football-data collected before the match ("pre"), and closing odds for CLV.

Splits (by season, chronological):
  tune     : hyperparameters (xi, ridge) chosen by 1X2 log loss
  validate : blend weights (model vs market) fitted by log loss
  test     : untouched; all headline numbers come from here
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import timedelta

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

from . import config, db
from . import ev as evm
from .engine import books_from_rows, price_event, select
from .markets import pnl, settle_value
from .models import dixon_coles as dc
from .models.elo import fit_ordered_logit, ordered_logit_probs, run_elo
from .sources import football_data as fd


def load_league(div: str, seasons: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames, odds = [], []
    offset = 0
    for s in seasons:
        try:
            raw = fd.load_season_frame(div, s, max_age_hours=24 * 30)
        except Exception as e:  # noqa: BLE001
            print(f"  skip {div} {s}: {e}")
            continue
        if raw.empty:
            continue
        m = fd.parse_matches(raw)
        o = fd.parse_odds(raw)
        m.index = m.index + offset
        o["idx"] = o["idx"] + offset
        offset += len(m)
        frames.append(m)
        odds.append(o)
    m = pd.concat(frames).sort_values("kickoff_utc")
    o = pd.concat(odds)
    m = m.dropna(subset=["hg", "ag"])
    return m, o[o["idx"].isin(m.index)]


def _books(o_idx: pd.DataFrame, kind: str) -> dict:
    sub = o_idx[o_idx["kind"] == kind]
    return books_from_rows(zip(sub["market"], sub["line"], sub["bookmaker"], sub["selection"], sub["price"]))


def walk_forward(div: str, m: pd.DataFrame, o: pd.DataFrame, start_season: str, xi: float,
                 ridge: float, blend_w: dict | None = None, rules=None, n_draws: int = 0,
                 lookback_days: int = 3 * 365) -> tuple[pd.DataFrame, list[dict]]:
    """Returns per-match 1X2 prediction rows and (if rules given) simulated bets."""
    m = m.copy()
    elo_d = run_elo(m["home"].values, m["away"].values, m["hg"].values.astype(float), m["ag"].values.astype(float))
    m["elo_diff"] = elo_d
    m["res"] = np.where(m.hg > m.ag, 2, np.where(m.hg == m.ag, 1, 0))
    o_by = dict(tuple(o.groupby("idx")))
    test = m[m["season"] >= start_season]
    if test.empty:
        return pd.DataFrame(), []
    t0 = test["kickoff_utc"].min().normalize()
    t_end = test["kickoff_utc"].max()
    rows, bets = [], []
    prev = None
    rng = np.random.default_rng(42)
    cut = t0
    while cut <= t_end:
        nxt = cut + timedelta(days=7)
        train = m[(m.kickoff_utc < cut) & (m.kickoff_utc >= cut - timedelta(days=lookback_days))]
        week = m[(m.kickoff_utc >= cut) & (m.kickoff_utc < nxt)]
        if len(week) and len(train) > 200:
            days = (cut - train.kickoff_utc).dt.total_seconds().values / 86400
            model = dc.fit(train.home.values, train.away.values, train.hg.values, train.ag.values,
                           days, xi=xi, ridge=ridge, with_cov=n_draws > 0, init=prev)
            prev = model
            ol = fit_ordered_logit(train["elo_diff"].values[-1500:], train["res"].values[-1500:])
            elo_p = ordered_logit_probs(week["elo_diff"].values, ol)
            recent = train[train.kickoff_utc >= cut - timedelta(days=365)]
            for k, (idx, r) in enumerate(week.iterrows()):
                if not (model.has(r.home) and model.has(r.away)):
                    continue
                mat = model.score_matrix(r.home, r.away)
                ph = float(np.tril(mat, -1).sum()); pd_ = float(np.trace(mat)); pa = 1 - ph - pd_
                oi = o_by.get(idx)
                pre = _books(oi, "pre") if oi is not None else {}
                clo = _books(oi, "closing") if oi is not None else {}
                mk = pre.get(("1X2", None), {})
                cons, src = evm.consensus(mk, ["H", "D", "A"])
                ccons, _ = evm.consensus(clo.get(("1X2", None), {}), ["H", "D", "A"])
                hist_ok = min(model.n_matches.get(r.home, 0), model.n_matches.get(r.away, 0))
                row = dict(event=idx, div=div, season=r.season, date=r.kickoff_utc, home=r.home, away=r.away,
                           res=r.res, hg=r.hg, ag=r.ag, dc_H=ph, dc_D=pd_, dc_A=pa,
                           elo_H=elo_p[k, 0], elo_D=elo_p[k, 1], elo_A=elo_p[k, 2],
                           min_team_n=hist_ok,
                           recent_n=int(((recent.home == r.home) | (recent.away == r.home)).sum()))
                if cons:
                    row.update(mkt_H=cons["H"], mkt_D=cons["D"], mkt_A=cons["A"], mkt_src=src)
                if ccons:
                    row.update(close_H=ccons["H"], close_D=ccons["D"], close_A=ccons["A"])
                # O/U 2.5 and AH model vs market (for blend fitting per market)
                for key, sels in ((("OU", 2.5), ["over", "under"]),):
                    b = pre.get(key)
                    if b:
                        c, _ = evm.consensus(b, sels)
                        if c:
                            from .markets import outcome
                            row["ou_model"] = outcome(mat, "OU", "over", 2.5).q
                            row["ou_mkt"] = c["over"]
                            row["ou_y"] = int(r.hg + r.ag > 2.5)
                ah = [k2 for k2 in pre if k2[0] == "AH"]
                if ah:
                    b = pre[ah[0]]
                    c, _ = evm.consensus(b, ["home", "away"])
                    if c:
                        from .markets import outcome
                        oc = outcome(mat, "AH", "home", ah[0][1])
                        res_v = settle_value("AH", "home", ah[0][1], int(r.hg), int(r.ag))
                        if res_v != 0:
                            row["ah_model"] = oc.q
                            row["ah_mkt"] = c["home"]
                            row["ah_y"] = 1 if res_v > 0 else 0  # half results counted by sign
                rows.append(row)
                if rules is not None and pre:
                    cands = price_event(model, r.home, r.away, pre, blend_w or {},
                                        rules.exchange_commission, n_draws=n_draws, rng=rng,
                                        markets=rules.markets)
                    ok = hist_ok >= rules.min_team_matches
                    for eid, c in select({idx: cands}, rules, {idx: ok}):
                        res_v = settle_value(c.market, c.selection, c.line, int(r.hg), int(r.ag))
                        cl_book = clo.get((c.market, c.line), {})
                        ccons2, _ = evm.consensus(cl_book, list({"1X2": "HDA", "OU": ["over", "under"],
                                                                  "AH": ["home", "away"]}[c.market]))
                        clv = (c.net_odds * ccons2[c.selection] - 1) if ccons2 else None
                        bets.append(dict(event=idx, div=div, season=r.season, date=r.kickoff_utc,
                                         home=r.home, away=r.away, market=c.market, selection=c.selection,
                                         line=c.line, bookmaker=c.bookmaker, odds=c.odds, net_odds=c.net_odds,
                                         model_q=c.model_q, market_q=c.market_q, final_q=c.final_q,
                                         ev=c.ev, ev_lower=c.ev_lower, result=res_v,
                                         pnl=pnl(res_v, c.net_odds), clv=clv))
        cut = nxt
    return pd.DataFrame(rows), bets


# ---------------------------------------------------------------- metrics

def logloss(P: np.ndarray, y: np.ndarray) -> float:
    return float(-np.log(np.clip(P[np.arange(len(y)), y], 1e-12, 1)).mean())


def brier(P: np.ndarray, y: np.ndarray) -> float:
    Y = np.zeros_like(P)
    Y[np.arange(len(y)), y] = 1
    return float(((P - Y) ** 2).sum(axis=1).mean())


def bin_logloss(p, y) -> float:
    p = np.clip(np.asarray(p, float), 1e-12, 1 - 1e-12)
    y = np.asarray(y)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def probs(df: pd.DataFrame, prefix: str) -> np.ndarray:
    return df[[f"{prefix}_H", f"{prefix}_D", f"{prefix}_A"]].values


def y1x2(df) -> np.ndarray:
    return np.where(df.res == 2, 0, np.where(df.res == 1, 1, 2))  # columns H, D, A


def fit_blend_1x2(df: pd.DataFrame) -> float:
    d = df.dropna(subset=["mkt_H"])
    y = y1x2(d)
    M, K = probs(d, "dc"), probs(d, "mkt")
    r = minimize_scalar(lambda w: logloss(w * M + (1 - w) * K, y), bounds=(0, 1), method="bounded")
    return float(r.x)


def fit_blend_bin(df, mcol, kcol, ycol) -> float | None:
    d = df.dropna(subset=[mcol, kcol, ycol])
    if len(d) < 200:
        return None
    r = minimize_scalar(lambda w: bin_logloss(w * d[mcol] + (1 - w) * d[kcol], d[ycol]),
                        bounds=(0, 1), method="bounded")
    return float(r.x)


def bootstrap_ci(x: np.ndarray, stat=np.mean, n: int = 2000, seed: int = 0) -> tuple[float, float]:
    if len(x) == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    s = [stat(rng.choice(x, len(x))) for _ in range(n)]
    return float(np.quantile(s, 0.025)), float(np.quantile(s, 0.975))


def evaluate_predictions(df: pd.DataFrame, w1x2: float) -> dict:
    d = df.dropna(subset=["mkt_H"]).copy()
    y = y1x2(d)
    base = np.tile(np.bincount(y, minlength=3) / len(y), (len(y), 1))  # in-sample base rate (optimistic)
    out = {"n_matches": int(len(d))}
    models = {"base_rate": base, "elo": probs(d, "elo"), "dixon_coles": probs(d, "dc"),
              "market_pre": probs(d, "mkt"),
              "blend": w1x2 * probs(d, "dc") + (1 - w1x2) * probs(d, "mkt")}
    if "close_H" in d and d["close_H"].notna().all():
        models["market_closing"] = probs(d, "close")
    for k, P in models.items():
        out[k] = {"logloss": round(logloss(P, y), 5), "brier": round(brier(P, y), 5)}
    # paired comparison DC vs market (per-match log loss difference, bootstrap CI)
    li = lambda P: -np.log(np.clip(P[np.arange(len(y)), y], 1e-12, 1))  # noqa: E731
    diff = li(models["dixon_coles"]) - li(models["market_pre"])
    out["dc_minus_market_logloss_ci95"] = [round(v, 5) for v in bootstrap_ci(diff)]
    # calibration of DC home-win probs (10 bins)
    out["calibration_dc_home"] = calibration(models["dixon_coles"][:, 0], (y == 0).astype(int))
    return out


def calibration(p, y, bins: int = 10) -> list[dict]:
    p, y = np.asarray(p), np.asarray(y)
    edges = np.linspace(0, 1, bins + 1)
    res = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mk = (p >= lo) & (p < hi)
        if mk.sum() >= 20:
            res.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": int(mk.sum()),
                        "pred": round(float(p[mk].mean()), 4), "obs": round(float(y[mk].mean()), 4)})
    return res


def evaluate_bets(bets: pd.DataFrame) -> dict:
    if bets.empty:
        return {"n_bets": 0}
    b = bets
    pnl_arr = b["pnl"].values
    cum = np.cumsum(pnl_arr)
    dd = float((np.maximum.accumulate(np.concatenate([[0], cum]))[1:] - cum).max())
    out = {"n_bets": int(len(b)), "staked": float(len(b)), "profit_units": round(float(pnl_arr.sum()), 2),
           "roi": round(float(pnl_arr.mean()), 4),
           "roi_ci95": [round(v, 4) for v in bootstrap_ci(pnl_arr)],
           "hit_rate": round(float((b["result"] > 0).mean()), 4),
           "avg_odds": round(float(b["odds"].mean()), 3), "avg_ev_claimed": round(float(b["ev"].mean()), 4),
           "max_drawdown_units": round(dd, 2)}
    c = b["clv"].dropna()
    if len(c):
        out["avg_clv"] = round(float(c.mean()), 4)
        out["clv_ci95"] = [round(v, 4) for v in bootstrap_ci(c.values)]
        out["clv_positive_share"] = round(float((c > 0).mean()), 4)
    out["by_market"] = {k: {"n": int(len(g)), "roi": round(float(g["pnl"].mean()), 4)}
                        for k, g in b.groupby("market")}
    out["by_league"] = {k: {"n": int(len(g)), "roi": round(float(g["pnl"].mean()), 4)}
                        for k, g in b.groupby("div")}
    return out


# ---------------------------------------------------------------- orchestration

def run(leagues: list[str], seasons: list[str], tune: list[str], validate: list[str], test: list[str],
        xi_grid=(0.0013, 0.0019, 0.0026), ridge_grid=(2.0, 4.0, 8.0), n_draws: int = 100, out_dir=None) -> dict:
    out_dir = out_dir or (config.DATA_DIR / "backtest")
    out_dir.mkdir(parents=True, exist_ok=True)
    data = {}
    for div in leagues:
        print(f"loading {div}")
        data[div] = load_league(div, seasons)

    # 1) tune xi, ridge on the tune seasons only
    scores = {}
    for xi in xi_grid:
        for rg in ridge_grid:
            frames = []
            for div, (m, o) in data.items():
                df, _ = walk_forward(div, m[m.season <= tune[-1]], o, tune[0], xi, rg)
                frames.append(df)
            df = pd.concat(frames).dropna(subset=["mkt_H"])
            scores[(xi, rg)] = logloss(probs(df, "dc"), y1x2(df))
            print(f"  tune xi={xi} ridge={rg}: logloss={scores[(xi, rg)]:.5f} n={len(df)}")
    xi, rg = min(scores, key=scores.get)

    # 2) predictions through validate+test with chosen hyperparameters
    frames = []
    for div, (m, o) in data.items():
        df, _ = walk_forward(div, m, o, validate[0], xi, rg)
        frames.append(df)
    pred = pd.concat(frames)
    val = pred[pred.season.isin(validate)]
    tst = pred[pred.season.isin(test)]
    w = {"1X2": fit_blend_1x2(val),
         "OU": fit_blend_bin(val, "ou_model", "ou_mkt", "ou_y") or 0.0,
         "AH": fit_blend_bin(val, "ah_model", "ah_mkt", "ah_y") or 0.0}
    print(f"  blend weights (validation): {w}")

    # 3) betting simulation on TEST seasons only, using the deployed selection rules
    rules = config.RULES
    bets = []
    for div, (m, o) in data.items():
        _, b = walk_forward(div, m, o, test[0], xi, rg, blend_w=w, rules=rules, n_draws=n_draws)
        bets += b
    bets = pd.DataFrame(bets)

    # 4) pure line-shopping benchmark: same rules with w=0 (model ignored) -> isolates model value
    bets0 = []
    for div, (m, o) in data.items():
        _, b = walk_forward(div, m, o, test[0], xi, rg, blend_w={"1X2": 0, "OU": 0, "AH": 0},
                            rules=rules, n_draws=0)
        bets0 += b
    bets0 = pd.DataFrame(bets0)

    report = {
        "model_version": config.MODEL.model_version,
        "leagues": leagues, "seasons": {"tune": tune, "validate": validate, "test": test},
        "hyperparameters": {"xi": xi, "ridge": rg, "tune_grid_logloss": {f"{k[0]}|{k[1]}": round(v, 5) for k, v in scores.items()}},
        "blend_weight": w,
        "validation_1x2": evaluate_predictions(val, w["1X2"]),
        "test_1x2": evaluate_predictions(tst, w["1X2"]),
        "test_ou25_logloss": {
            "model": round(bin_logloss(tst.dropna(subset=['ou_model'])['ou_model'], tst.dropna(subset=['ou_model'])['ou_y']), 5),
            "market": round(bin_logloss(tst.dropna(subset=['ou_model'])['ou_mkt'], tst.dropna(subset=['ou_model'])['ou_y']), 5)},
        "test_bets": evaluate_bets(bets),
        "test_bets_market_only_benchmark": evaluate_bets(bets0),
        "rules": asdict(rules),
    }
    pred.to_csv(out_dir / "predictions.csv", index=False)
    if not bets.empty:
        bets.to_csv(out_dir / "bets_test.csv", index=False)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, default=str))
    tuned = {"xi": xi, "ridge": rg, "blend_weight": w, "source": "backtest", "created_at": db.utcnow(),
             "test_seasons": test}
    (config.DATA_DIR / "tuned.json").write_text(json.dumps(tuned, indent=2))
    con = db.connect()
    con.execute("INSERT INTO backtest_results(model_version,label,config_json,metrics_json,created_at) VALUES (?,?,?,?,?)",
                (config.MODEL.model_version, f"walkforward:{','.join(leagues)}", json.dumps(tuned),
                 json.dumps(report, default=str), db.utcnow()))
    con.commit()
    return report
