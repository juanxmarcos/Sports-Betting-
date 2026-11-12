import numpy as np
import pytest

from sbi import ev
from sbi.engine import books_from_rows, price_event, select
from sbi.config import SelectionRules
from sbi.models import dixon_coles as dc


def test_devig():
    p = ev.devig_multiplicative([2.0, 3.4, 4.0])
    assert p.sum() == pytest.approx(1)
    q = ev.devig_power([1.5, 4.2, 7.0])
    assert q.sum() == pytest.approx(1)
    # power method shifts more margin onto the longshot than proportional normalisation
    assert q[2] < ev.devig_multiplicative([1.5, 4.2, 7.0])[2]
    assert ev.devig_power([1.01, 30.0]).sum() == pytest.approx(1)  # degenerate fallback


def test_exchange_commission():
    assert ev.net_price("Betfair Exchange", 3.0, 0.05) == pytest.approx(2.9)
    assert ev.net_price("Bet365", 3.0, 0.05) == 3.0


def test_consensus_priority_and_best_price():
    book = {"Pinnacle": {"H": 2.0, "D": 3.5, "A": 4.0}, "Bet365": {"H": 2.2, "D": 3.3, "A": 3.6},
            "Max": {"H": 2.5, "D": 3.6, "A": 4.1}}
    c, src = ev.consensus(book, ["H", "D", "A"])
    assert src == "Pinnacle" and sum(c.values()) == pytest.approx(1)
    bk, q, net = ev.best_price(book, "H", 0.05)
    assert bk == "Bet365" and q == 2.2  # aggregates ("Max") are never selectable


def synthetic(n_seasons=3, seed=1):
    rng = np.random.default_rng(seed)
    teams = [f"T{i}" for i in range(12)]
    att = rng.normal(0, 0.3, 12); att -= att.mean()
    dfn = rng.normal(0, 0.25, 12); dfn -= dfn.mean()
    H, A, HG, AG, D = [], [], [], [], []
    day = 0
    for _ in range(n_seasons):
        for i in range(12):
            for j in range(12):
                if i == j:
                    continue
                lam = np.exp(0.25 + att[i] + dfn[j]); mu = np.exp(att[j] + dfn[i])
                H.append(teams[i]); A.append(teams[j]); HG.append(rng.poisson(lam)); AG.append(rng.poisson(mu))
                D.append(day); day += 1
    D = np.array(D)
    return teams, att, dfn, np.array(H), np.array(A), np.array(HG), np.array(AG), (D.max() - D) / 3


def test_dc_recovers_parameters():
    teams, att, dfn, H, A, HG, AG, days = synthetic(4)
    m = dc.fit(H, A, HG, AG, days, xi=0.0, ridge=0.1)
    # MLE of home advantage in a balanced schedule ~= log ratio of home/away goals
    assert m.home == pytest.approx(np.log(HG.mean() / AG.mean()), abs=0.03)
    assert abs(m.home - 0.25) < 3 * np.sqrt(m.cov[0, 0])
    est = np.array([m.att[m.index[t]] for t in teams])
    assert np.corrcoef(est, att)[0, 1] > 0.85
    assert m.cov is not None and np.all(np.diag(m.cov) > 0)


def test_price_event_and_selection_rules():
    teams, att, dfn, H, A, HG, AG, days = synthetic(3)
    m = dc.fit(H, A, HG, AG, days, xi=0.002, ridge=2.0)
    rows = []
    for bk, (h, d, a) in {"Pinnacle": (2.0, 3.6, 4.0), "Bet365": (2.05, 3.5, 3.9), "Bwin": (1.95, 3.6, 4.6),
                          "Betfred": (2.0, 3.4, 3.9)}.items():
        rows += [("1X2", None, bk, "H", h), ("1X2", None, bk, "D", d), ("1X2", None, bk, "A", a)]
    books = books_from_rows(rows)
    cands = price_event(m, "T0", "T1", books, {"1X2": 0.0}, 0.05, n_draws=50, rng=np.random.default_rng(0))
    assert len(cands) == 3
    # with blend weight 0 the final prob equals the market consensus
    for c in cands:
        assert c.final_q == pytest.approx(c.market_q)
    # Bwin's 4.6 on the away side vs consensus ~0.24 -> positive EV, should be picked
    rules = SelectionRules(min_ev=0.02, max_prob_sd=1.0)
    picks = select({"e1": cands}, rules, {"e1": True})
    assert len(picks) == 1 and picks[0][1].selection == "A" and picks[0][1].bookmaker == "Bwin"
    # but not when team history is insufficient
    assert select({"e1": cands}, rules, {"e1": False}) == []
