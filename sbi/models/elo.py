"""Elo baseline with goal-difference K multiplier and an ordered-logit map to 1X2.

Used only as a benchmark: the DC model must beat it out of sample to be worth using.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit


def run_elo(home, away, hg, ag, k: float = 20.0, hfa: float = 60.0, init: float = 1500.0):
    """Return pre-match rating difference (home - away + hfa) per match, sequentially."""
    r: dict[str, float] = {}
    diffs = np.zeros(len(home))
    for i, (h, a, x, y) in enumerate(zip(home, away, hg, ag)):
        rh, ra = r.get(h, init), r.get(a, init)
        d = rh - ra + hfa
        diffs[i] = d
        if np.isnan(x) or np.isnan(y):
            continue
        e = 1 / (1 + 10 ** (-d / 400))
        s = 1.0 if x > y else (0.5 if x == y else 0.0)
        gd = abs(x - y)
        mult = 1.0 if gd <= 1 else (1.5 if gd == 2 else (11 + gd) / 8)
        delta = k * mult * (s - e)
        r[h], r[a] = rh + delta, ra - delta
    return diffs


def fit_ordered_logit(diffs, outcome):
    """outcome: 0 away, 1 draw, 2 home. Returns (beta, c1, c2)."""
    diffs = np.asarray(diffs, float) / 100.0
    y = np.asarray(outcome)

    def nll(p):
        b, c1, gap = p
        c2 = c1 + np.exp(gap)
        z = b * diffs
        pa = expit(c1 - z)
        ph = 1 - expit(c2 - z)
        pd = 1 - pa - ph
        pr = np.where(y == 0, pa, np.where(y == 1, pd, ph))
        return -np.log(np.clip(pr, 1e-12, 1)).sum()

    res = minimize(nll, [0.4, -0.6, np.log(1.2)], method="Nelder-Mead", options={"maxiter": 2000})
    b, c1, gap = res.x
    return b, c1, c1 + np.exp(gap)


def ordered_logit_probs(diffs, params):
    b, c1, c2 = params
    z = b * np.asarray(diffs, float) / 100.0
    pa = expit(c1 - z)
    ph = 1 - expit(c2 - z)
    return np.column_stack([ph, 1 - pa - ph, pa])  # H, D, A


def final_ratings(home, away, hg, ag, k: float = 20.0, hfa: float = 60.0, init: float = 1500.0) -> dict:
    """Ratings after processing all (pre-cutoff) matches, for pricing upcoming fixtures."""
    r: dict[str, float] = {}
    for h, a, x, y in zip(home, away, hg, ag):
        rh, ra = r.get(h, init), r.get(a, init)
        e = 1 / (1 + 10 ** (-(rh - ra + hfa) / 400))
        s = 1.0 if x > y else (0.5 if x == y else 0.0)
        gd = abs(x - y)
        mult = 1.0 if gd <= 1 else (1.5 if gd == 2 else (11 + gd) / 8)
        d = k * mult * (s - e)
        r[h], r[a] = rh + d, ra - d
    return r
