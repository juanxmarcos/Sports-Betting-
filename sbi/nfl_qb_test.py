import io, json, numpy as np, pandas as pd
from sbi.sources.http import fetch
from sbi.us import nfl_history
from sbi.models import ratings
from sbi.sources.international import american_to_decimal
from sbi.ev import devig_power
from sbi.backtest import bootstrap_ci
from sbi import config
g = pd.read_csv(io.BytesIO(fetch("https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv", 12)[0]))
g = g.sort_values(["season", "week"])
hist = nfl_history(); hist = hist[hist.hs.notna()].copy()
hist = hist.merge(g[["espn", "home_qb_name", "away_qb_name"]], on="espn", how="left")
# QB change flag: starter differs from the team's most frequent starter in its previous 4 games (pre-game info)
last = {}
hq, aq = [], []
for r in hist.itertuples():
    for team, qb, lst in ((r.home, r.home_qb_name, hq), (r.away, r.away_qb_name, aq)):
        prev = last.get(team, [])[-4:]
        usual = max(set(prev), key=prev.count) if prev else None
        lst.append(1.0 if usual and qb and qb != usual else 0.0)
    last.setdefault(r.home, []).append(r.home_qb_name); last.setdefault(r.away, []).append(r.away_qb_name)
hist["hq"], hist["aq"] = hq, aq
hist = hist[hist.season >= 2015]
def walk(lo, hi, use):
    out = []
    for (s, w), grp in hist[(hist.season >= lo) & (hist.season <= hi)].groupby(["season", "week"]):
        cut = grp.kickoff_utc.min() - pd.Timedelta(hours=1)
        tr = hist[(hist.kickoff_utc < cut) & (hist.kickoff_utc >= cut - pd.Timedelta(days=1095))]
        days = (cut - tr.kickoff_utc).dt.total_seconds().values / 86400
        kw = dict(f_home=tr[["hq"]].values, f_away=tr[["aq"]].values, feature_names=["qb_change"]) if use else {}
        m = ratings.fit(tr.home.values, tr.away.values, tr.hs.values, tr["as"].values, days, 0.004, 4.0, neutral=tr.neutral.values, **kw)
        for r in grp.itertuples():
            if not (m.has(r.home) and m.has(r.away)) or r.hs == r[4]:
                continue
            ph, pa = m.expected(r.home, r.away, bool(r.neutral), [r.hq] if use else None, [r.aq] if use else None)
            out.append({"y": float(r.hs > r[4]), "p": ratings.outcome(m, ph, pa, "ML", "home", None).pw, "beta": float(m.beta[0]) if use else 0})
    return pd.DataFrame(out)
li = lambda d: -(d.y * np.log(d.p.clip(1e-9)) + (1 - d.y) * np.log((1 - d.p).clip(1e-9)))
res = {}
for name, rng in (("tune", (2018, 2020)), ("test", (2023, 2026))):
    a, b = walk(*rng, False), walk(*rng, True)
    res[name] = {"n": len(a), "base": round(float(li(a).mean()), 5), "with_qb_change": round(float(li(b).mean()), 5), "qb_change_points_coef": round(float(b.beta.iloc[-1]), 2)}
d = li(walk(2023, 2026, True)).values - li(walk(2023, 2026, False)).values
res["test"]["diff_ci95"] = [round(x, 5) for x in bootstrap_ci(d)]
res["adopt"] = bool(res["tune"]["with_qb_change"] < res["tune"]["base"] and res["test"]["diff_ci95"][1] < 0)
(config.DATA_DIR / "backtest" / "nfl_qb.json").write_text(json.dumps(res, indent=2))
print(json.dumps(res, indent=1))
