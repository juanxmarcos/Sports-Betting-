"""Time-weighted Dixon-Coles (1997) bivariate-Poisson-style goal model.

log(lambda_home) = home + att[h] + def[a]
log(mu_away)     =        att[a] + def[h]
plus the Dixon-Coles low-score dependence correction tau(x, y; rho).

Fitted by penalised weighted maximum likelihood (L-BFGS with analytic gradient).
- weights: exp(-xi * days_before_cutoff)  (Dixon & Coles time decay)
- ridge:   L2 penalty on att/def -> identifiability + shrinkage for thin data
Parameter uncertainty: Gaussian approximation from the observed Fisher information
of the Poisson part (rho treated as fixed), used for Monte-Carlo probability bands.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize


@dataclass
class DCModel:
    teams: list[str]
    home: float
    att: np.ndarray
    dfn: np.ndarray
    rho: float
    cov: np.ndarray | None = None
    n_matches: dict = field(default_factory=dict)  # team -> matches in window
    xi: float = 0.0
    ridge: float = 0.0

    @property
    def index(self) -> dict:
        return {t: i for i, t in enumerate(self.teams)}

    def has(self, team: str) -> bool:
        return team in self.index

    def rates(self, home: str, away: str, theta: np.ndarray | None = None) -> tuple[float, float]:
        ix = self.index
        i, j = ix[home], ix[away]
        if theta is None:
            return (float(np.exp(self.home + self.att[i] + self.dfn[j])),
                    float(np.exp(self.att[j] + self.dfn[i])))
        n = len(self.teams)
        h, att, dfn = theta[0], theta[1:1 + n], theta[1 + n:1 + 2 * n]
        return float(np.exp(h + att[i] + dfn[j])), float(np.exp(att[j] + dfn[i]))

    def theta(self) -> np.ndarray:
        return np.concatenate([[self.home], self.att, self.dfn])

    def score_matrix(self, home: str, away: str, max_goals: int = 10, theta=None) -> np.ndarray:
        lam, mu = self.rates(home, away, theta)
        return score_matrix(lam, mu, self.rho, max_goals)

    def sample_matrices(self, home: str, away: str, n: int, max_goals: int = 10,
                        rng: np.random.Generator | None = None) -> list[np.ndarray]:
        if self.cov is None:
            return [self.score_matrix(home, away, max_goals)]
        rng = rng or np.random.default_rng(0)
        draws = rng.multivariate_normal(self.theta(), self.cov, size=n, method="cholesky")
        return [self.score_matrix(home, away, max_goals, th) for th in draws]


_LOGFACT = np.cumsum(np.log(np.maximum(np.arange(64), 1)))


def _pmf(g: np.ndarray, lam: float) -> np.ndarray:
    return np.exp(g * np.log(lam) - lam - _LOGFACT[g])


def score_matrix(lam: float, mu: float, rho: float, max_goals: int = 10) -> np.ndarray:
    g = np.arange(max_goals + 1)
    m = np.outer(_pmf(g, lam), _pmf(g, mu))
    m[0, 0] *= max(1 - lam * mu * rho, 1e-10)
    m[0, 1] *= max(1 + lam * rho, 1e-10)
    m[1, 0] *= max(1 + mu * rho, 1e-10)
    m[1, 1] *= max(1 - rho, 1e-10)
    return m / m.sum()


def _nll_grad(params, hi, ai, hg, ag, w, n, ridge):
    h = params[0]
    att = params[1:1 + n]
    dfn = params[1 + n:1 + 2 * n]
    rho = params[-1]
    ll_lam = h + att[hi] + dfn[ai]
    ll_mu = att[ai] + dfn[hi]
    lam, mu = np.exp(ll_lam), np.exp(ll_mu)

    # Poisson part (constant log-factorials dropped)
    ll = hg * ll_lam - lam + ag * ll_mu - mu
    g_lam = hg - lam          # d ll / d log(lam)
    g_mu = ag - mu
    g_rho = np.zeros_like(lam)

    tau = np.ones_like(lam)
    m00 = (hg == 0) & (ag == 0)
    m01 = (hg == 0) & (ag == 1)
    m10 = (hg == 1) & (ag == 0)
    m11 = (hg == 1) & (ag == 1)
    tau[m00] = 1 - lam[m00] * mu[m00] * rho
    tau[m01] = 1 + lam[m01] * rho
    tau[m10] = 1 + mu[m10] * rho
    tau[m11] = 1 - rho
    tau = np.maximum(tau, 1e-10)
    ll = ll + np.log(tau)
    t = tau
    g_lam[m00] += -lam[m00] * mu[m00] * rho / t[m00]
    g_mu[m00] += -lam[m00] * mu[m00] * rho / t[m00]
    g_rho[m00] = -lam[m00] * mu[m00] / t[m00]
    g_lam[m01] += lam[m01] * rho / t[m01]
    g_rho[m01] = lam[m01] / t[m01]
    g_mu[m10] += mu[m10] * rho / t[m10]
    g_rho[m10] = mu[m10] / t[m10]
    g_rho[m11] = -1 / t[m11]

    nll = -(w * ll).sum() + ridge * (att @ att + dfn @ dfn)
    wl, wm = w * g_lam, w * g_mu
    grad = np.zeros_like(params)
    grad[0] = -wl.sum()
    g_att = -(np.bincount(hi, wl, n) + np.bincount(ai, wm, n))
    g_def = -(np.bincount(ai, wl, n) + np.bincount(hi, wm, n))
    grad[1:1 + n] = g_att + 2 * ridge * att
    grad[1 + n:1 + 2 * n] = g_def + 2 * ridge * dfn
    grad[-1] = -(w * g_rho).sum()
    return nll, grad


def fit(home: np.ndarray, away: np.ndarray, hg: np.ndarray, ag: np.ndarray,
        days_ago: np.ndarray, xi: float = 0.0019, ridge: float = 2.0,
        with_cov: bool = True, init: DCModel | None = None) -> DCModel:
    """Fit on matches strictly before the cutoff (caller guarantees no leakage)."""
    teams = sorted(set(home) | set(away))
    ix = {t: i for i, t in enumerate(teams)}
    hi = np.array([ix[t] for t in home])
    ai = np.array([ix[t] for t in away])
    hg = np.asarray(hg, float)
    ag = np.asarray(ag, float)
    w = np.exp(-xi * np.asarray(days_ago, float))
    n = len(teams)
    x0 = np.zeros(2 * n + 2)
    x0[0] = 0.25
    x0[-1] = -0.05
    if init is not None:
        for t, i in ix.items():
            if init.has(t):
                k = init.index[t]
                x0[1 + i], x0[1 + n + i] = init.att[k], init.dfn[k]
        x0[0], x0[-1] = init.home, init.rho
    bounds = [(None, None)] * (2 * n + 1) + [(-0.25, 0.25)]
    res = minimize(_nll_grad, x0, args=(hi, ai, hg, ag, w, n, ridge), jac=True,
                   method="L-BFGS-B", bounds=bounds, options={"maxiter": 500})
    p = res.x
    model = DCModel(teams=teams, home=float(p[0]), att=p[1:1 + n].copy(),
                    dfn=p[1 + n:1 + 2 * n].copy(), rho=float(p[-1]), xi=xi, ridge=ridge)
    counts = np.bincount(hi, minlength=n) + np.bincount(ai, minlength=n)
    model.n_matches = {t: int(counts[i]) for t, i in ix.items()}
    if with_cov:
        model.cov = _covariance(model, hi, ai, w, ridge)
    return model


def _covariance(model: DCModel, hi, ai, w, ridge) -> np.ndarray | None:
    """Inverse observed Fisher information of the (penalised) Poisson log-likelihood."""
    n = len(model.teams)
    k = 1 + 2 * n
    lam = np.exp(model.home + model.att[hi] + model.dfn[ai])
    mu = np.exp(model.att[ai] + model.dfn[hi])
    m = len(hi)
    X_l = np.zeros((m, k))
    X_m = np.zeros((m, k))
    r = np.arange(m)
    X_l[:, 0] = 1
    X_l[r, 1 + hi] = 1
    X_l[r, 1 + n + ai] = 1
    X_m[r, 1 + ai] = 1
    X_m[r, 1 + n + hi] = 1
    info = (X_l * (w * lam)[:, None]).T @ X_l + (X_m * (w * mu)[:, None]).T @ X_m
    info[1:, 1:] += 2 * ridge * np.eye(2 * n)
    try:
        cov = np.linalg.inv(info)
        cov = (cov + cov.T) / 2
        np.linalg.cholesky(cov)
        return cov
    except np.linalg.LinAlgError:
        return None
