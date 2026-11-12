"""Historical sensitivity of the qualification rules (club soccer, market-only strategy).

Each rule variant is evaluated on the VALIDATION seasons (used to judge) and confirmed on
the TEST seasons (never used to choose). Metrics: bets, ROI with bootstrap CI, average CLV
with CI and the share of bets beating the close. A rule change is only recommended when a
variant beats the baseline on CLV in validation AND test, with non-overlapping CLV evidence.
"""
from __future__ import annotations

import json
from dataclasses import replace

import pandas as pd

from . import config, db
from .backtest import evaluate_bets, load_league, walk_forward

VARIANTS = {
    "baseline (EV>=3%, 3 books, odds<=6)": {},
    "EV>=1%": {"min_ev": 0.01}, "EV>=2%": {"min_ev": 0.02}, "EV>=5%": {"min_ev": 0.05},
    "2 bookmakers": {"min_bookmakers": 2}, "5 bookmakers": {"min_bookmakers": 5},
    "odds<=10": {"max_odds": 10.0}, "odds<=3.5": {"max_odds": 3.5},
}


def run(leagues=("E0", "E1", "SP1", "D1", "I1", "F1"),
        seasons=("1920", "2021", "2122", "2223", "2324", "2425", "2526", "2627")) -> dict:
    config.load_tuned()
    data = {d: load_league(d, list(seasons)) for d in leagues}
    zero = {"1X2": 0.0, "OU": 0.0, "AH": 0.0}
    out = {}
    for name, kw in VARIANTS.items():
        rules = replace(config.RULES, **kw)
        res = {}
        for split, start, stop in (("validation", "2223", "2324"), ("test", "2425", "2627")):
            bets = []
            for div, (m, o) in data.items():
                _, b = walk_forward(div, m[m.season <= stop], o, start, config.MODEL.xi, config.MODEL.ridge,
                                    blend_w=zero, rules=rules, n_draws=0)
                bets += b
            ev = evaluate_bets(pd.DataFrame(bets))
            res[split] = {k: ev.get(k) for k in ("n_bets", "roi", "roi_ci95", "avg_clv", "clv_ci95", "clv_positive_share")}
        out[name] = res
        print(name, json.dumps(res))
    base = out["baseline (EV>=3%, 3 books, odds<=6)"]
    rec = []
    for name, r in out.items():
        if name.startswith("baseline"):
            continue
        better = all((r[s]["avg_clv"] or -1) > (base[s]["avg_clv"] or -1) and r[s]["n_bets"] >= 30 for s in ("validation", "test"))
        rec.append({"variant": name, "beats_baseline_clv_in_both": better})
    rep = {"variants": out, "assessment": rec,
           "note": "Market-only strategy (price vs sharp consensus). CLV is the primary criterion; ROI CIs are wide."}
    (config.DATA_DIR / "backtest").mkdir(parents=True, exist_ok=True)
    (config.DATA_DIR / "backtest" / "rule_sensitivity.json").write_text(json.dumps(rep, indent=2, default=str))
    con = db.connect()
    con.execute("INSERT INTO backtest_results(model_version,label,config_json,metrics_json,created_at) VALUES (?,?,?,?,?)",
                ("rules", "rule-sensitivity", "{}", json.dumps(rep, default=str), db.utcnow()))
    con.commit()
    return rep
