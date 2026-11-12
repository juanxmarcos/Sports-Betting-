"""Shared pricing + selection logic used by BOTH the live pipeline and the backtest,
so the backtest evaluates exactly the rules that are deployed."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import ev as evm
from .markets import Outcome, outcome, q_many
from .models.dixon_coles import DCModel

SELECTIONS = {"1X2": ["H", "D", "A"], "OU": ["over", "under"], "AH": ["home", "away"],
              "ML": ["home", "away"], "SPREAD": ["home", "away"], "TOTAL": ["over", "under"]}


@dataclass
class Candidate:
    market: str
    selection: str
    line: float | None
    model_q: float
    prob_sd: float
    model_q_lo: float
    market_q: float | None
    consensus_src: str | None
    final_q: float
    final_q_lo: float
    bookmaker: str | None
    odds: float          # quoted
    net_odds: float      # after exchange commission
    ev: float
    ev_lower: float
    blend_w: float
    active: float        # share of stake not pushed
    n_books: int
    outcome: Outcome = field(repr=False, default=None)

    @property
    def fair_odds(self) -> float:
        return 1 / self.final_q if self.final_q > 0 else float("inf")


def price_event(model: DCModel, home: str, away: str, books: dict, blend_w: dict,
                commission: float, n_draws: int = 200, max_goals: int = 10,
                rng: np.random.Generator | None = None, markets=("1X2", "OU", "AH"),
                neutral: bool = False) -> list[Candidate]:
    """books: {(market, line): {bookmaker: {selection: price}}}"""
    m = model.score_matrix(home, away, max_goals, neutral=neutral)
    draws = (np.array(model.sample_matrices(home, away, n_draws, max_goals, rng, neutral))
             if n_draws else None)
    out: list[Candidate] = []
    for (market, line), book in books.items():
        if market not in markets:
            continue
        sels = SELECTIONS[market]
        book = evm.clean(book, sels)
        if not book:
            continue
        cons, src = evm.consensus(book, sels)
        nb = evm.n_books(book, sels)
        for s in sels:
            oc = outcome(m, market, s, line)
            if draws is not None:
                qs = q_many(draws, market, s, line)
                sd, q_lo = float(qs.std()), float(np.quantile(qs, 0.10))
            else:
                sd, q_lo = 0.0, oc.q
            mq = cons[s] if cons else None
            w = blend_w.get(market, 0.0)
            fq = evm.blend(oc.q, mq, w)
            fq_lo = evm.blend(q_lo, mq, w)
            bk, quoted, net = evm.best_price(book, s, commission)
            if bk is None:
                continue
            out.append(Candidate(market, s, line, oc.q, sd, q_lo, mq, src, fq, fq_lo, bk, quoted,
                                 net, oc.active * (fq * net - 1), oc.active * (fq_lo * net - 1),
                                 w, oc.active, nb, oc))
    return out


def passes(c: Candidate, rules, min_team_matches_ok: bool) -> tuple[bool, str]:
    if not min_team_matches_ok:
        return False, "insufficient team history"
    if c.n_books < rules.min_bookmakers:
        return False, "too few bookmakers"
    if c.market_q is None:
        return False, "no market consensus"
    if not (rules.min_odds <= c.odds <= rules.max_odds):
        return False, "odds outside range"
    if c.blend_w * c.prob_sd > rules.max_prob_sd:  # uncertainty of the FINAL probability
        return False, "model uncertainty too high"
    if c.ev < rules.min_ev:
        return False, "EV below threshold"
    if c.ev_lower <= rules.min_ev_lower:
        return False, "pessimistic EV not positive"
    return True, "ok"


def select(cands_by_event: dict, rules, history_ok: dict) -> list[tuple[str, Candidate]]:
    """Filter, keep the best (by pessimistic EV) per event, rank, cap daily exposure."""
    picks = []
    for eid, cands in cands_by_event.items():
        ok = [c for c in cands if passes(c, rules, history_ok.get(eid, False))[0]]
        ok.sort(key=lambda c: c.ev_lower, reverse=True)
        picks += [(eid, c) for c in ok[: rules.max_per_event]]
    picks.sort(key=lambda x: x[1].ev_lower, reverse=True)
    max_n = int(rules.max_daily_units // rules.stake_units)
    return picks[:max_n]


def books_from_rows(rows) -> dict:
    """rows: iterable of (market, line, bookmaker, selection, price) -> books dict."""
    books: dict = {}
    for market, line, bk, sel, price in rows:
        line = None if line is None or (isinstance(line, float) and np.isnan(line)) else float(line)
        key = (market, line)
        books.setdefault(key, {}).setdefault(bk, {})[sel] = float(price)
    return books


def price_generic(outcome_fn, books: dict, blend_w: dict, commission: float, markets=None) -> list[Candidate]:
    """Pricing for sports without a score-matrix model. outcome_fn(market, selection, line) -> Outcome.
    Parameter uncertainty is not estimated for these models, so prob_sd = 0 (the blend weight,
    fitted out of sample, is what limits trust in the model)."""
    out: list[Candidate] = []
    for (market, line), book in books.items():
        if market not in SELECTIONS or (markets and market not in markets):
            continue
        sels = SELECTIONS[market]
        book = evm.clean(book, sels)
        if not book:
            continue
        cons, src = evm.consensus(book, sels)
        nb = evm.n_books(book, sels)
        for s in sels:
            try:
                oc = outcome_fn(market, s, line)
            except (ValueError, KeyError):
                continue
            mq = cons[s] if cons else None
            w = blend_w.get(market, 0.0)
            fq = evm.blend(oc.q, mq, w)
            bk, quoted, net = evm.best_price(book, s, commission)
            if bk is None:
                continue
            e = oc.active * (fq * net - 1)
            out.append(Candidate(market, s, line, oc.q, 0.0, oc.q, mq, src, fq, fq, bk, quoted, net, e, e, w,
                                 oc.active, nb, oc))
    return out
