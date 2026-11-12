import numpy as np
import pytest

from sbi.markets import Outcome, outcome, pnl, settle_value
from sbi.models.dixon_coles import score_matrix


@pytest.mark.parametrize("line,hg,ag,exp", [
    (-0.5, 1, 0, 1.0), (-0.5, 1, 1, -1.0),
    (-1.0, 2, 1, 0.0), (-1.0, 3, 1, 1.0),
    (-0.75, 2, 1, 0.5), (-0.75, 1, 1, -1.0), (-0.75, 3, 1, 1.0),
    (-0.25, 1, 1, -0.5), (0.25, 1, 1, 0.5), (0.0, 0, 0, 0.0),
])
def test_ah_home_settlement(line, hg, ag, exp):
    assert settle_value("AH", "home", line, hg, ag) == exp


def test_ah_away_is_mirror():
    for hg in range(4):
        for ag in range(4):
            for ln in (-1.25, -0.5, 0, 0.75, 1.5):
                assert settle_value("AH", "away", ln, hg, ag) == -settle_value("AH", "home", ln, hg, ag)


@pytest.mark.parametrize("line,goals,exp", [(2.5, 3, 1.0), (2.5, 2, -1.0), (2.0, 2, 0.0), (2.25, 2, -0.5), (2.75, 3, 0.5)])
def test_ou_settlement(line, goals, exp):
    assert settle_value("OU", "over", line, goals, 0) == exp


def test_pnl():
    assert pnl(1.0, 2.5) == pytest.approx(1.5)
    assert pnl(0.5, 2.0) == pytest.approx(0.5)
    assert pnl(-0.5, 2.0) == pytest.approx(-0.5)
    assert pnl(0.0, 2.0) == 0


def test_outcomes_sum_to_one_and_match_settlement():
    m = score_matrix(1.6, 1.1, -0.08)
    assert m.sum() == pytest.approx(1)
    for mk, sel, ln in [("1X2", "H", None), ("OU", "over", 2.25), ("AH", "home", -0.75), ("AH", "away", 1.0)]:
        o = outcome(m, mk, sel, ln)
        assert o.pw + o.phw + o.pp + o.phl + o.pl == pytest.approx(1)
        # expected value via brute-force settlement must equal Outcome.ev
        odds = 2.1
        brute = sum(m[i, j] * pnl(settle_value(mk, sel, ln, i, j), odds)
                    for i in range(m.shape[0]) for j in range(m.shape[1]))
        assert o.ev(odds) == pytest.approx(brute, abs=1e-9)
        assert o.ev(o.fair_odds()) == pytest.approx(0, abs=1e-9)


def test_1x2_probs_sum():
    m = score_matrix(1.3, 1.3, 0.0)
    s = sum(outcome(m, "1X2", x).pw for x in "HDA")
    assert s == pytest.approx(1)
    assert outcome(m, "1X2", "H").pw == pytest.approx(outcome(m, "1X2", "A").pw)


def test_high_probability_is_not_value():
    o = Outcome(pw=0.8, pl=0.2)
    assert o.ev(1.20) < 0          # 80% at 1.20 -> negative EV
    assert Outcome(pw=0.3, pl=0.7).ev(3.6) > 0  # 30% at 3.60 -> positive EV
