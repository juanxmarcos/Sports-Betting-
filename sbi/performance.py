"""Performance accounting for published (paper) recommendations and all predictions."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import bootstrap_ci, calibration

ODDS_BANDS = [(1.0, 1.8), (1.8, 2.5), (2.5, 3.5), (3.5, 100)]


def _group(df: pd.DataFrame, col: str) -> list[dict]:
    out = []
    for k, g in df.groupby(col):
        out.append({"key": str(k), "n": int(len(g)), "profit": round(float(g.pnl_units.sum()), 2),
                    "roi": round(float(g.pnl_units.mean()), 4),
                    "avg_clv": None if g.clv.isna().all() else round(float(g.clv.mean()), 4)})
    return out


def rec_metrics(con) -> dict:
    df = pd.read_sql_query("SELECT * FROM recommendations ORDER BY kickoff_utc", con)
    out = {"total": int(len(df)), "open": int((df.status == "open").sum()) if len(df) else 0}
    s = df[~df.status.isin(["open", "void"])].copy() if len(df) else df
    if s.empty:
        out["settled"] = 0
        out["sample_warning"] = "No settled selections yet. Nothing can be concluded."
        return out
    pnl = s.pnl_units.values
    cum = np.cumsum(pnl)
    peak = np.maximum.accumulate(np.concatenate([[0], cum]))[1:]
    stake = s.stake_units.sum()
    out.update({
        "settled": int(len(s)),
        "won": int(s.status.isin(["won", "half_won"]).sum()), "lost": int(s.status.isin(["lost", "half_lost"]).sum()),
        "push": int((s.status == "push").sum()),
        "hit_rate": round(float((pnl > 0).mean()), 4),
        "profit_units": round(float(pnl.sum()), 2), "staked_units": float(stake),
        "yield": round(float(pnl.sum() / stake), 4),
        "yield_ci95": [round(v, 4) for v in bootstrap_ci(pnl / s.stake_units.values)],
        "max_drawdown_units": round(float((peak - cum).max()), 2),
        "avg_odds": round(float(s.odds.mean()), 3), "avg_ev_claimed": round(float(s.ev.mean()), 4),
        "expected_profit_units": round(float((s.ev * s.stake_units).sum()), 2),
        "avg_clv": None if s.clv.isna().all() else round(float(s.clv.mean()), 4),
        "clv_n": int(s.clv.notna().sum()),
        "series": [{"date": d[:10], "cum": round(float(c), 3)} for d, c in zip(s.kickoff_utc, cum)],
        "by_league": _group(s, "league"), "by_market": _group(s, "market"),
    })
    s["band"] = pd.cut(s.odds, [b[0] for b in ODDS_BANDS] + [100], labels=[f"{a}-{b}" for a, b in ODDS_BANDS])
    out["by_odds"] = _group(s, "band")
    # Brier / log loss of the published (push-adjusted) win probability
    dec = s[s.status.isin(["won", "lost"])]
    if len(dec):
        y = (dec.status == "won").astype(int).values
        p = dec.final_prob.clip(1e-6, 1 - 1e-6).values
        out["brier"] = round(float(((p - y) ** 2).mean()), 4)
        out["logloss"] = round(float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()), 4)
    n = len(s)
    out["sample_warning"] = (
        f"Only {n} settled selections. Yield CIs are wide; at typical odds, several hundred to "
        "a few thousand bets are needed before ROI distinguishes skill from luck. CLV is the "
        "faster, more reliable early indicator." if n < 500 else
        "Sample is moderate; still treat ROI with caution and prefer CLV for inference.")
    return out


def prediction_metrics(con) -> dict:
    """Calibration of ALL 1X2 model predictions (bet or not) on finished events, latest run per event."""
    df = pd.read_sql_query("""
        SELECT p.event_id, p.selection, p.model_prob, p.market_prob, e.home_score, e.away_score
        FROM predictions p JOIN events e USING(event_id)
        WHERE p.market='1X2' AND e.status='finished'
          AND p.id IN (SELECT MAX(id) FROM predictions WHERE market='1X2' GROUP BY event_id, selection)""", con)
    if df.empty:
        return {"n_events": 0}
    res = np.where(df.home_score > df.away_score, "H", np.where(df.home_score == df.away_score, "D", "A"))
    df["y"] = (df.selection == res).astype(int)
    out = {"n_events": int(df.event_id.nunique())}
    piv = df.pivot_table(index="event_id", columns="selection", values=["model_prob", "y", "market_prob"])
    for name in ("model_prob", "market_prob"):
        if name not in piv or piv[name].isna().any().any():
            continue
        P = piv[name][["H", "D", "A"]].values
        Y = piv["y"][["H", "D", "A"]].values
        out[name] = {"brier": round(float(((P - Y) ** 2).sum(1).mean()), 4),
                     "logloss": round(float(-np.log(np.clip((P * Y).sum(1), 1e-9, 1)).mean()), 4)}
    out["calibration"] = calibration(df.model_prob.values, df.y.values)
    return out
