"""Shared pricing + selection logic used by BOTH the live pipeline and the backtest,
so the backtest evaluates exactly the rules that are deployed."""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

from . import config
from . import ev as evm
from .markets import Outcome, outcome, q_many
from .models.dixon_coles import DCModel

NO_EV = -1.0   # sentinel: EV not computable (no independent market reference)
UNVERIFIED_REASON = "too few verified independent bookmakers"   # rule v2 only (see passes)

SELECTIONS = {"1X2": ["H", "D", "A"], "OU": ["over", "under"], "AH": ["home", "away"],
              "ML": ["home", "away"], "SPREAD": ["home", "away"], "TOTAL": ["over", "under"],
              "BTTS": ["yes", "no"]}


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
    n_books: int         # independent-bookmaker count under the ACTIVE policy
    outcome: Outcome = field(repr=False, default=None)
    policy: str = "legacy"                    # which independence policy the fields above reflect
    unverified_books: tuple = ()              # quoting this market, owner / price origin not verified
    # Both policies' numbers for this same price, so the staged rule can be compared with the live
    # one candidate by candidate: {policy: {market_q, consensus_src, final_q, final_q_lo, ev, ev_lower, n_books}}
    views: dict = field(repr=False, default=None)

    @property
    def fair_odds(self) -> float:
        return 1 / self.final_q if self.final_q > 0 else float("inf")

    def view(self, policy: str) -> "Candidate":
        """This candidate as the given independence policy sees it (same price, same model)."""
        if not self.views or policy == self.policy:
            return self
        return replace(self, policy=policy, **self.views[policy])


def _both_views(book, sels, s, bk, model_q, q_lo, w, net, active, legacy_ref, n_legacy) -> dict:
    """Value of one price under rule v1 (legacy) and rule v2 (verified). Only the market
    reference and the bookmaker count differ; the price, model and blend weight are the same."""
    out = {}
    for policy, (ref, src), nb in (("legacy", legacy_ref, n_legacy),
                                   ("verified", evm.consensus_verified_excluding(book, sels, bk),
                                    evm.n_books_verified(book, sels))):
        mq = ref[s] if ref else None
        fq, fq_lo = evm.blend(model_q, mq, w), evm.blend(q_lo, mq, w)
        if mq is None:   # no independent market reference -> no value claim (never fall back to the model alone)
            e = e_lo = NO_EV
        else:
            e, e_lo = active * (fq * net - 1), active * (fq_lo * net - 1)
        out[policy] = {"market_q": mq, "consensus_src": src, "final_q": fq, "final_q_lo": fq_lo,
                       "ev": e, "ev_lower": e_lo, "n_books": nb}
    return out


def _candidate(policy, book, sels, market, s, line, oc, sd, q_lo, bk, quoted, net, w, legacy_ref, n_legacy) -> Candidate:
    views = _both_views(book, sels, s, bk, oc.q, q_lo, w, net, oc.active, legacy_ref, n_legacy)
    v = views[policy]
    return Candidate(market, s, line, oc.q, sd, q_lo, v["market_q"], v["consensus_src"], v["final_q"], v["final_q_lo"],
                     bk, quoted, net, v["ev"], v["ev_lower"], w, oc.active, v["n_books"], oc, policy,
                     tuple(evm.unverified_books(book, sels)), views)


def price_event(model: DCModel, home: str, away: str, books: dict, blend_w: dict,
                commission: float, n_draws: int = 200, max_goals: int = 10,
                rng: np.random.Generator | None = None, markets=("1X2", "OU", "AH"),
                neutral: bool = False, policy: str | None = None) -> list[Candidate]:
    """books: {(market, line): {bookmaker: {selection: price}}}
    policy: independence policy (default: config.RULES.independence_policy)."""
    policy = policy or config.RULES.independence_policy
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
            bk, quoted, net = evm.best_price(book, s, commission)
            if bk is None:
                continue
            legacy_ref = evm.consensus_excluding(book, sels, bk)   # leave-one-out reference
            w = blend_w.get(market, 0.0)
            out.append(_candidate(policy, book, sels, market, s, line, oc, sd, q_lo, bk, quoted, net, w,
                                  legacy_ref, nb))
    return out


def _passes_core(c: Candidate, rules, min_team_matches_ok: bool) -> tuple[bool, str]:
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


def passes(c: Candidate, rules, min_team_matches_ok: bool) -> tuple[bool, str]:
    """Publication gate under the candidate's own independence policy.

    legacy (rule v1): the checks as they have always been.
    verified (rule v2): a pure tightening. The v1 checks must pass first (same reasons as before),
    then the market needs min_bookmakers VERIFIED operators and the value must also hold against
    the verified-only reference. It can block a v1 pick; it can never create one."""
    if c.policy != "verified":
        return _passes_core(c, rules, min_team_matches_ok)
    ok, why = _passes_core(c.view("legacy"), rules, min_team_matches_ok)
    if not ok:
        return ok, why
    if c.n_books < rules.min_bookmakers:
        return False, UNVERIFIED_REASON
    return _passes_core(c, rules, min_team_matches_ok)


def passes_under(c: Candidate, policy: str, rules, min_team_matches_ok: bool) -> tuple[bool, str]:
    """The gate's verdict under another policy, without changing what is deployed (staged comparison)."""
    return passes(c.view(policy), rules, min_team_matches_ok)


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


def price_generic(outcome_fn, books: dict, blend_w: dict, commission: float, markets=None,
                  policy: str | None = None) -> list[Candidate]:
    """Pricing for sports without a score-matrix model. outcome_fn(market, selection, line) -> Outcome.
    Parameter uncertainty is not estimated for these models, so prob_sd = 0 (the blend weight,
    fitted out of sample, is what limits trust in the model)."""
    policy = policy or config.RULES.independence_policy
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
            bk, quoted, net = evm.best_price(book, s, commission)
            if bk is None:
                continue
            legacy_ref = evm.consensus_excluding(book, sels, bk)   # leave-one-out reference
            w = blend_w.get(market, 0.0)
            out.append(_candidate(policy, book, sels, market, s, line, oc, 0.0, oc.q, bk, quoted, net, w,
                                  legacy_ref, nb))
    return out
