"""Expected-value engine: de-vigging, consensus, best price, blended probability.

EV per unit stake (decimal odds o, probability p): EV = p*o - 1
(generalised to push/half outcomes in markets.Outcome).
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq

from .sources.football_data import AGGREGATES, EXCHANGES

CONSENSUS_PRIORITY = ("Betfair Exchange", "Pinnacle", "Avg")


def implied(prices) -> np.ndarray:
    return 1.0 / np.asarray(prices, float)


def devig_multiplicative(prices) -> np.ndarray:
    p = implied(prices)
    return p / p.sum()


def devig_power(prices) -> np.ndarray:
    """Power method: p_i = (1/o_i)^k with k s.t. sum p_i = 1. Accounts for the
    favourite-longshot bias better than proportional normalisation."""
    p = implied(prices)
    if p.sum() <= 1.0:
        return p / p.sum()
    f = lambda k: (p ** k).sum() - 1.0  # noqa: E731
    if f(200.0) > 0:  # degenerate quotes (e.g. a price near 1.0): fall back
        return p / p.sum()
    k = brentq(f, 1.0, 200.0)
    return p ** k


def sane(quotes: dict | None, selections: list[str], lo: float = 0.97, hi: float = 1.20) -> bool:
    """A bookmaker's market is usable only if complete and its overround is plausible.
    Rejects stale/illiquid quotes such as exchange prices of 1.02 / 1.12 on a 2-way market."""
    if not quotes or not all(s in quotes for s in selections):
        return False
    ov = sum(1.0 / quotes[s] for s in selections)
    return lo <= ov <= hi


def clean(book: dict, selections: list[str]) -> dict:
    return {bk: q for bk, q in book.items() if sane(q, selections)}


def net_price(bookmaker: str, price: float, commission: float) -> float:
    if bookmaker in EXCHANGES:
        return 1 + (price - 1) * (1 - commission)
    return price


def consensus(book: dict[str, dict[str, float]], selections: list[str],
              priority=CONSENSUS_PRIORITY) -> tuple[dict[str, float] | None, str | None]:
    """book: bookmaker -> {selection: price}. Returns de-vigged fair probs and the source."""
    book = clean(book, selections)
    for bk in priority:
        q = book.get(bk)
        if q:
            fair = devig_power([q[s] for s in selections])
            return dict(zip(selections, fair)), bk
    # fallback: median of de-vigged individual books
    fairs = [devig_power([q[s] for s in selections]) for b, q in book.items()
             if b not in AGGREGATES and all(s in q for s in selections)]
    if len(fairs) >= 2:
        med = np.median(np.array(fairs), axis=0)
        med = med / med.sum()
        return dict(zip(selections, med)), "median"
    singles = [b for b in book if b not in AGGREGATES]
    if len(fairs) == 1 and len(singles) == 1:
        # one bookmaker only: de-vig it, but label it so callers (and n_books rules) know
        return dict(zip(selections, fairs[0])), f"single:{singles[0]}"
    return None, None


def best_price(book: dict[str, dict[str, float]], selection: str, commission: float):
    best = (None, 0.0, 0.0)  # bookmaker, quoted, net
    for bk, q in book.items():
        if bk in AGGREGATES or selection not in q:
            continue
        net = net_price(bk, q[selection], commission)
        if net > best[2]:
            best = (bk, q[selection], net)
    return best


def n_books(book, selections) -> int:
    """Rule v1 ("legacy") count: same-owner / same-platform brands in the best-effort map count
    once, and a bookmaker that is NOT in the map counts as its own independent operator."""
    from .sources.books import group_of
    return len({group_of(b) for b, q in book.items() if b not in AGGREGATES and all(s in q for s in selections)})


def consensus_excluding(book, selections, exclude_bookmaker, priority=CONSENSUS_PRIORITY):
    """Consensus that never uses the bookmaker (or its group) whose price is being tested,
    so a price can't establish fair value and then 'beat' it (no circularity)."""
    from .sources.books import group_of
    g = group_of(exclude_bookmaker)
    return consensus({b: q for b, q in book.items() if group_of(b) != g}, selections, priority)


# ---------- rule v2 ("verified"): only verified operators are independent evidence ----------
SHARP_REFERENCES = ("Betfair Exchange", "Pinnacle")     # no aggregate: "Avg" contains the tested price
MEDIAN_VERIFIED = "median (verified operators)"


def _quoting(book, selections) -> list[str]:
    return [b for b, q in book.items() if b not in AGGREGATES and all(s in q for s in selections)]


def verified_operators(book, selections) -> set[str]:
    """Verified operator groups quoting this market. A bookmaker whose owner and price origin
    are not verified in sources/books.py REGISTRY is never counted here."""
    from .sources.books import verified_group
    return {g for g in map(verified_group, _quoting(book, selections)) if g}


def n_books_verified(book, selections) -> int:
    return len(verified_operators(book, selections))


def unverified_books(book, selections) -> list[str]:
    from .sources.books import verified_group
    return sorted(b for b in _quoting(book, selections) if not verified_group(b))


def consensus_verified_excluding(book, selections, exclude_bookmaker):
    """Leave-one-out fair value from VERIFIED operators only, one vote per operator.

    * The tested bookmaker is removed together with every brand of its verified operator AND of
      its legacy group, so neither map can leak its price into the reference.
    * Unverified bookmakers and aggregates ("Avg" includes the tested price) are not used.
    * A sharp reference (Betfair Exchange, Pinnacle) is used alone if present, as before.
    * Otherwise the median is taken over operators, not brands: three skins of one operator are
      one vote (their de-vigged prices are averaged first), so syndicated prices cannot outvote
      independent ones."""
    from .sources.books import group_of, verified_group
    book = clean(book, selections)
    ex_legacy, ex_verified = group_of(exclude_bookmaker), verified_group(exclude_bookmaker)
    votes: dict[str, list] = {}
    for b in _quoting(book, selections):
        g = verified_group(b)
        if not g or g == ex_verified or group_of(b) == ex_legacy or b == exclude_bookmaker:
            continue
        votes.setdefault(g, []).append(b)
    for bk in SHARP_REFERENCES:
        if any(bk in members for members in votes.values()):
            fair = devig_power([book[bk][s] for s in selections])
            return dict(zip(selections, fair)), bk
    fairs = {g: np.mean([devig_power([book[b][s] for s in selections]) for b in members], axis=0)
             for g, members in votes.items()}
    if len(fairs) >= 2:
        med = np.median(np.array(list(fairs.values())), axis=0)
        return dict(zip(selections, med / med.sum())), MEDIAN_VERIFIED
    if len(fairs) == 1:
        g, f = next(iter(fairs.items()))
        return dict(zip(selections, f / f.sum())), f"single:{g}"
    return None, None


def blend(model_q: float, market_q: float | None, w: float) -> float:
    """Linear opinion pool. w (weight on model) is fitted out-of-sample in the backtest;
    w=0 means 'trust the market', w=1 'trust the model'."""
    if market_q is None:
        return model_q
    return w * model_q + (1 - w) * market_q


def ev(prob: float, odds: float) -> float:
    return prob * odds - 1.0
