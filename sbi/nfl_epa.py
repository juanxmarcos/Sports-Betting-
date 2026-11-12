"""NFL EPA features from nflverse play-by-play (open data, programmatic download intended).

For every game, each team's offensive EPA/play and defensive EPA/play allowed are computed
from PRIOR games only (exponentially weighted, half-life in games), so there is no leakage.
These enter the points model as features and are kept only if they improve out-of-sample
log loss (see backtest_epa).
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd

from .sources.http import fetch

PBP = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{y}.csv.gz"
COLS = ["game_id", "season", "week", "posteam", "defteam", "epa", "success", "play_type", "game_date"]


def pbp_games(season: int, current: bool) -> pd.DataFrame:
    content, _ = fetch(PBP.format(y=season), max_age_hours=12 if current else 24 * 365)
    df = pd.read_csv(io.BytesIO(content), compression="gzip", usecols=COLS, low_memory=False)
    df = df[df.play_type.isin(["pass", "run"]) & df.epa.notna() & df.posteam.notna()]
    g = df.groupby(["game_id", "posteam", "defteam"]).agg(epa=("epa", "mean"), succ=("success", "mean"),
                                                          plays=("epa", "size"), date=("game_date", "first")).reset_index()
    return g


def team_features(seasons: list[int], current_season: int, half_life_games: float = 8.0) -> pd.DataFrame:
    games = pd.concat([pbp_games(s, s == current_season) for s in seasons], ignore_index=True)
    games["date"] = pd.to_datetime(games.date)
    games = games.sort_values("date")
    alpha = 1 - 0.5 ** (1 / half_life_games)
    off, dfn, rows = {}, {}, []
    for gid, grp in games.groupby("game_id", sort=False):
        for r in grp.itertuples():
            rows.append({"game_id": gid, "team": r.posteam,
                         "off_epa_pre": off.get(r.posteam, 0.0), "def_epa_pre": dfn.get(r.posteam, 0.0)})
        for r in grp.itertuples():  # update AFTER recording pre-game values
            off[r.posteam] = (1 - alpha) * off.get(r.posteam, 0.0) + alpha * r.epa
            dfn[r.defteam] = (1 - alpha) * dfn.get(r.defteam, 0.0) + alpha * r.epa
    return pd.DataFrame(rows), off, dfn


def backtest_epa(train_from=2016, tune=(2018, 2020), test=(2023, 2026), xi=0.004, ridge=4.0) -> dict:
    from . import config
    from .backtest import bootstrap_ci
    from .models import ratings
    from .sources import international
    from .us import nfl_history
    import json
    hist = nfl_history()
    hist = hist[hist.hs.notna()].copy()
    feats, _, _ = team_features(list(range(train_from, test[1] + 1)), test[1])
    gid = pd.read_csv(io.BytesIO(fetch("https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv", 12)[0]))
    hist = hist.merge(gid[["espn", "game_id"]], on="espn", how="left")
    fh = feats.rename(columns={"team": "home", "off_epa_pre": "h_off", "def_epa_pre": "h_def"})
    fa = feats.rename(columns={"team": "away", "off_epa_pre": "a_off", "def_epa_pre": "a_def"})
    hist = hist.merge(fh, on=["game_id", "home"], how="left").merge(fa, on=["game_id", "away"], how="left")
    hist = hist[hist.season >= train_from].fillna({"h_off": 0, "h_def": 0, "a_off": 0, "a_def": 0})

    def walk(lo, hi, use):
        out = []
        for (season, week), g in hist[(hist.season >= lo) & (hist.season <= hi)].groupby(["season", "week"]):
            cut = g.kickoff_utc.min() - pd.Timedelta(hours=1)
            tr = hist[(hist.kickoff_utc < cut) & (hist.kickoff_utc >= cut - pd.Timedelta(days=3 * 365))]
            if len(tr) < 200:
                continue
            days = (cut - tr.kickoff_utc).dt.total_seconds().values / 86400
            kw = {}
            if use:
                kw = dict(f_home=tr[["h_off", "a_def"]].values, f_away=tr[["a_off", "h_def"]].values,
                          feature_names=["off_epa", "opp_def_epa"])
            m = ratings.fit(tr.home.values, tr.away.values, tr.hs.values, tr["as"].values, days, xi, ridge,
                            neutral=tr.neutral.values, **kw)
            for r in g.itertuples():
                if not (m.has(r.home) and m.has(r.away)) or r.hs == r[4]:
                    continue
                f1 = [r.h_off, r.a_def] if use else None
                f2 = [r.a_off, r.h_def] if use else None
                ph, pa = m.expected(r.home, r.away, bool(r.neutral), f1, f2)
                p = ratings.outcome(m, ph, pa, "ML", "home", None).pw
                rec = {"y": float(r.hs > r[4]), "p": p}
                if pd.notna(r.home_ml) and pd.notna(r.away_ml):
                    oh, oa = international.american_to_decimal(r.home_ml), international.american_to_decimal(r.away_ml)
                    if oh and oa:
                        from .ev import devig_power
                        rec["m"] = float(devig_power([oh, oa])[0])
                out.append(rec)
        return pd.DataFrame(out)

    li = lambda p, y: -(y * np.log(np.clip(p, 1e-9, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-9, 1)))  # noqa: E731
    res = {}
    for name, rng in (("tune", tune), ("test", test)):
        a, b = walk(*rng, False), walk(*rng, True)
        res[name] = {"n": len(a), "base_model": round(float(li(a.p, a.y).mean()), 5), "with_epa": round(float(li(b.p, b.y).mean()), 5)}
        if name == "test":
            d = li(b.p, b.y).values - li(a.p, a.y).values
            res[name]["epa_minus_base_ci95"] = [round(x, 5) for x in bootstrap_ci(d)]
            bm = b.dropna(subset=["m"])
            res[name]["market_closing"] = round(float(li(bm.m, bm.y).mean()), 5)
            res[name]["with_epa_on_market_games"] = round(float(li(bm.p, bm.y).mean()), 5)
    res["adopt"] = bool(res["tune"]["with_epa"] < res["tune"]["base_model"] and res["test"]["epa_minus_base_ci95"][1] < 0)
    (config.DATA_DIR / "backtest").mkdir(parents=True, exist_ok=True)
    (config.DATA_DIR / "backtest" / "nfl_epa.json").write_text(json.dumps(res, indent=2))
    return res
