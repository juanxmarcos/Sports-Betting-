"""Market probabilities and settlement from a score matrix.

Every market is reduced to outcome shares over a stake:
  pw  full win, phw half win, pp push, phl half loss, pl full loss
EV(o) = pw(o-1) + phw(o-1)/2 - phl/2 - pl = (A+B)(q*o - 1)
where A = pw + phw/2, B = pl + phl/2, q = A/(A+B) ("push-adjusted win probability").
For 1X2 and half-goal lines A+B = 1 and q is the plain win probability.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np


@dataclass(frozen=True)
class Outcome:
    pw: float = 0.0
    phw: float = 0.0
    pp: float = 0.0
    phl: float = 0.0
    pl: float = 0.0

    @property
    def a(self) -> float:
        return self.pw + self.phw / 2

    @property
    def b(self) -> float:
        return self.pl + self.phl / 2

    @property
    def q(self) -> float:
        s = self.a + self.b
        return self.a / s if s > 0 else 0.0

    @property
    def active(self) -> float:
        return self.a + self.b

    def ev(self, odds: float, q: float | None = None) -> float:
        q = self.q if q is None else q
        return self.active * (q * odds - 1)

    def fair_odds(self, q: float | None = None) -> float:
        q = self.q if q is None else q
        return 1 / q if q > 0 else float("inf")


def _split(line: float) -> list[float]:
    """Quarter lines split into two half-stakes: -0.75 -> [-0.5, -1.0]."""
    if abs((line * 4) % 2 - 1) < 1e-9:  # x.25 / x.75
        return [line - 0.25, line + 0.25]
    return [line]


def _settle_margin(margin: float) -> float:
    """Return per-unit result share for a single (non-split) line: 1 win, 0 push, -1 loss."""
    if margin > 1e-9:
        return 1.0
    if margin < -1e-9:
        return -1.0
    return 0.0


def settle_value(market: str, selection: str, line: float | None, hg: int, ag: int) -> float:
    """Return result r in {-1,-0.5,0,0.5,1}: fraction of stake won (+) or lost (-)."""
    if market == "1X2":
        res = "H" if hg > ag else ("A" if hg < ag else "D")
        return 1.0 if res == selection else -1.0
    if market == "DC":
        res = "H" if hg > ag else ("A" if hg < ag else "D")
        return 1.0 if res in selection else -1.0
    if market == "BTTS":
        yes = hg > 0 and ag > 0
        return 1.0 if (yes == (selection == "yes")) else -1.0
    parts = _split(line)
    vals = []
    for ln in parts:
        if market == "OU":
            margin = (hg + ag - ln) if selection == "over" else (ln - hg - ag)
        elif market == "AH":
            margin = (hg - ag + ln) if selection == "home" else (ag - hg - ln)
        else:
            raise ValueError(market)
        vals.append(_settle_margin(margin))
    return float(np.mean(vals))


def pnl(result: float, odds: float, stake: float = 1.0) -> float:
    return stake * (result * (odds - 1) if result > 0 else result)


@lru_cache(maxsize=512)
def result_grid(g: int, market: str, selection: str, line: float | None) -> np.ndarray:
    """(g x g) array of settlement values r in {-1,-.5,0,.5,1} for each scoreline."""
    hg, ag = np.meshgrid(np.arange(g), np.arange(g), indexing="ij")
    if market in ("1X2", "DC", "BTTS"):
        if market == "1X2":
            mask = {"H": hg > ag, "D": hg == ag, "A": hg < ag}[selection]
        elif market == "DC":
            mask = np.zeros_like(hg, bool)
            for s in selection:
                mask |= {"H": hg > ag, "D": hg == ag, "A": hg < ag}[s]
        else:
            yes = (hg > 0) & (ag > 0)
            mask = yes if selection == "yes" else ~yes
        return np.where(mask, 1.0, -1.0)
    parts = _split(line)
    vals = np.zeros((g, g))
    for ln in parts:
        if market == "OU":
            margin = (hg + ag - ln) if selection == "over" else (ln - hg - ag)
        else:
            margin = (hg - ag + ln) if selection == "home" else (ag - hg - ln)
        vals += np.sign(np.where(np.abs(margin) < 1e-9, 0, margin))
    vals /= len(parts)
    return vals


_LEVELS = (1.0, 0.5, 0.0, -0.5, -1.0)


def outcome(m: np.ndarray, market: str, selection: str, line: float | None = None) -> Outcome:
    vals = result_grid(m.shape[0], market, selection, None if line is None else float(line))
    acc = [float(m[np.isclose(vals, v)].sum()) for v in _LEVELS]
    return Outcome(*acc)


def q_many(mats: np.ndarray, market: str, selection: str, line: float | None = None) -> np.ndarray:
    """Push-adjusted win probability q for a stack of score matrices (n, g, g)."""
    vals = result_grid(mats.shape[1], market, selection, None if line is None else float(line))
    a = (mats * (vals == 1.0)).sum((1, 2)) + 0.5 * (mats * np.isclose(vals, 0.5)).sum((1, 2))
    b = (mats * (vals == -1.0)).sum((1, 2)) + 0.5 * (mats * np.isclose(vals, -0.5)).sum((1, 2))
    return a / np.maximum(a + b, 1e-12)


def standard_markets(m: np.ndarray) -> dict:
    """Headline probabilities for display."""
    out = {f"1X2:{s}": outcome(m, "1X2", s).pw for s in "HDA"}
    for s in ("HD", "HA", "DA"):
        out[f"DC:{s}"] = outcome(m, "DC", s).pw
    for ln in (1.5, 2.5, 3.5):
        out[f"OU:over:{ln}"] = outcome(m, "OU", "over", ln).pw
    out["BTTS:yes"] = outcome(m, "BTTS", "yes").pw
    g = np.arange(m.shape[0])
    out["exp_home_goals"] = float((m.sum(axis=1) * g).sum())
    out["exp_away_goals"] = float((m.sum(axis=0) * g).sum())
    return out
