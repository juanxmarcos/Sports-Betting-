"""Tennis model audit: Elo variants and a fatigue feature, chronological out-of-sample.

tune: 2025-01-01 .. 2025-07-01 (choose), test: 2025-07-01 .. now (confirm).
Variants: surface-Elo weight, K-factor scale. Fatigue: matches played in the previous
7 days (difference), applied as a logit shift fitted on the tune period only.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import expit, logit

from . import config
from .tennis import SLAM, Elo, bo5, matches


def VElo(w_surface=0.5, k_scale=1.0):
    return Elo(w_surface, k_scale)


def _run(hist, w, ks, start, stop):
    elo, recent, rows = VElo(w, ks), {}, []
    for m in hist:
        if start <= m["date"] < stop and min(elo.matches_played(m["p1"]), elo.matches_played(m["p2"])) >= 10:
            p = elo.prob(m["p1"], m["p2"], m["surface"])
            if m["slam"] and m["tour"] == "atp":
                p = bo5(p)
            f = lambda pl: sum(1 for d in recent.get(pl, []) if 0 < (m["date"] - d).days <= 7)  # noqa: E731
            rows.append((p, 1.0 if m["winner"] == m["p1"] else 0.0, f(m["p1"]) - f(m["p2"])))
        loser = m["p2"] if m["winner"] == m["p1"] else m["p1"]
        elo.update(m["winner"], loser, m["surface"])
        for pl in (m["p1"], m["p2"]):
            recent.setdefault(pl, []).append(m["date"])
    return np.array(rows)


def ll(p, y):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def run():
    now = datetime.now(timezone.utc)
    hist = sorted([m for m in matches(date(2024, 1, 1), now.date(), now) if m["completed"] and m["winner"]
                   and not m.get("walkover")], key=lambda x: x["date"])
    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc); t1 = datetime(2025, 7, 1, tzinfo=timezone.utc)
    grid = {}
    for w in (0.15, 0.3, 0.5):
        for ks in (0.6, 0.8, 1.0):
            a = _run(hist, w, ks, t0, t1)
            grid[(w, ks)] = ll(a[:, 0], a[:, 1])
    w, ks = min(grid, key=grid.get)
    tune = _run(hist, w, ks, t0, t1)
    b = float(minimize_scalar(lambda b: ll(expit(logit(np.clip(tune[:, 0], 1e-6, 1 - 1e-6)) + b * tune[:, 2]), tune[:, 1]),
                              bounds=(-1, 1), method="bounded").x)
    test_base = _run(hist, 0.5, 1.0, t1, now)
    test_best = _run(hist, w, ks, t1, now)
    fat = expit(logit(np.clip(test_best[:, 0], 1e-6, 1 - 1e-6)) + b * test_best[:, 2])
    rep = {"tune_grid_logloss": {f"w={k[0]},k={k[1]}": round(v, 5) for k, v in grid.items()},
           "chosen": {"w_surface": w, "k_scale": ks, "fatigue_coef": round(b, 4)},
           "test": {"n": len(test_best), "current_model": round(ll(test_base[:, 0], test_base[:, 1]), 5),
                    "tuned_elo": round(ll(test_best[:, 0], test_best[:, 1]), 5),
                    "tuned_elo_plus_fatigue": round(ll(fat, test_best[:, 1]), 5)}}
    t = rep["test"]
    rep["adopt_tuned_elo"] = t["tuned_elo"] < t["current_model"] - 0.001
    rep["adopt_fatigue"] = t["tuned_elo_plus_fatigue"] < t["tuned_elo"] - 0.001
    (config.DATA_DIR / "backtest" / "tennis_tuning.json").write_text(json.dumps(rep, indent=2))
    return rep
