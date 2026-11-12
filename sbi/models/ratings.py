"""Points-based team ratings for NFL and NBA (separate fits per sport).

points_home = mu + hfa*(not neutral) + off[home] - def[away] + b·features_home
points_away = mu              + off[away] - def[home] + b·features_away
Weighted (time-decay) ridge least squares; closed form. Margin and total are then modelled
as discrete normals with residual standard deviations estimated from the training fit.
Ties are removed and renormalised (overtime decides NFL/NBA games).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.stats import norm

from ..markets import Outcome


@dataclass
class PointsModel:
    teams: list[str]
    mu: float
    hfa: float
    off: np.ndarray
    dfn: np.ndarray
    beta: np.ndarray            # extra feature coefficients
    feature_names: list[str]
    sd_margin: float
    sd_total: float
    n_games: dict = field(default_factory=dict)

    @property
    def index(self):
        return {t: i for i, t in enumerate(self.teams)}

    def has(self, t):
        return t in self.index

    def expected(self, home, away, neutral=False, f_home=None, f_away=None):
        ix = self.index
        fh = np.zeros(len(self.beta)) if f_home is None else np.asarray(f_home, float)
        fa = np.zeros(len(self.beta)) if f_away is None else np.asarray(f_away, float)
        ph = self.mu + (0 if neutral else self.hfa) + self.off[ix[home]] - self.dfn[ix[away]] + fh @ self.beta
        pa = self.mu + self.off[ix[away]] - self.dfn[ix[home]] + fa @ self.beta
        return float(ph), float(pa)

    def rating(self, t):
        i = self.index[t]
        return float(self.off[i] + self.dfn[i])


def fit(home, away, hs, as_, days_ago, xi=0.004, ridge=5.0, neutral=None, f_home=None, f_away=None,
        feature_names=()) -> PointsModel:
    teams = sorted(set(home) | set(away))
    ix = {t: i for i, t in enumerate(teams)}
    n, g = len(teams), len(home)
    k = len(feature_names)
    p = 2 + 2 * n + k
    neutral = np.zeros(g) if neutral is None else np.asarray(neutral, float)
    fh = np.zeros((g, k)) if f_home is None else np.asarray(f_home, float).reshape(g, k)
    fa = np.zeros((g, k)) if f_away is None else np.asarray(f_away, float).reshape(g, k)
    X = np.zeros((2 * g, p))
    y = np.concatenate([np.asarray(hs, float), np.asarray(as_, float)])
    w = np.tile(np.exp(-xi * np.asarray(days_ago, float)), 2)
    hi = np.array([ix[t] for t in home])
    ai = np.array([ix[t] for t in away])
    r = np.arange(g)
    X[:, 0] = 1
    X[r, 1] = 1 - neutral
    X[r, 2 + hi] = 1
    X[r, 2 + n + ai] = -1
    X[g + r, 2 + ai] = 1
    X[g + r, 2 + n + hi] = -1
    if k:
        X[r, 2 + 2 * n:] = fh
        X[g + r, 2 + 2 * n:] = fa
    pen = np.zeros(p)
    pen[2:2 + 2 * n] = ridge
    A = (X * w[:, None]).T @ X + np.diag(pen)
    b = (X * w[:, None]).T @ y
    beta = np.linalg.solve(A, b)
    pred = X @ beta
    res = y - pred
    rm = res[:g] - res[g:]
    rt = res[:g] + res[g:]
    wg = w[:g] / w[:g].sum()
    counts = np.bincount(hi, minlength=n) + np.bincount(ai, minlength=n)
    return PointsModel(teams, float(beta[0]), float(beta[1]), beta[2:2 + n].copy(), beta[2 + n:2 + 2 * n].copy(),
                       beta[2 + 2 * n:].copy(), list(feature_names), float(np.sqrt((wg * rm ** 2).sum())),
                       float(np.sqrt((wg * rt ** 2).sum())), {t: int(counts[i]) for t, i in ix.items()})


def _discrete(mean: float, sd: float, drop_zero: bool) -> tuple[np.ndarray, np.ndarray]:
    lo, hi = int(np.floor(mean - 7 * sd)), int(np.ceil(mean + 7 * sd))
    k = np.arange(lo, hi + 1)
    pk = norm.cdf((k + 0.5 - mean) / sd) - norm.cdf((k - 0.5 - mean) / sd)
    if drop_zero:
        pk = np.where(k == 0, 0.0, pk)
    return k, pk / pk.sum()


def outcome(model: PointsModel, ph: float, pa: float, market: str, selection: str, line: float | None) -> Outcome:
    if market in ("ML", "SPREAD"):
        k, pk = _discrete(ph - pa, model.sd_margin, drop_zero=True)
        if market == "ML":
            win = k > 0 if selection == "home" else k < 0
            p = float(pk[win].sum())
            return Outcome(pw=p, pl=1 - p)
        m = (k + line) if selection == "home" else (-k - line)
    elif market == "TOTAL":
        k, pk = _discrete(ph + pa, model.sd_total, drop_zero=False)
        m = (k - line) if selection == "over" else (line - k)
    else:
        raise ValueError(market)
    return Outcome(pw=float(pk[m > 1e-9].sum()), pp=float(pk[np.abs(m) <= 1e-9].sum()), pl=float(pk[m < -1e-9].sum()))
