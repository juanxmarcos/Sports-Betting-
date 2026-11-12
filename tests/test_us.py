import numpy as np
import pytest

from sbi.markets import settle_value
from sbi.models import ratings
from sbi.us import parse_espn


def _synthetic(seed=0):
    rng = np.random.default_rng(seed)
    teams = [f"T{i}" for i in range(10)]
    strength = rng.normal(0, 4, 10)
    H, A, HS, AS = [], [], [], []
    for _ in range(6):
        for i in range(10):
            for j in range(10):
                if i != j:
                    m = 2.5 + strength[i] - strength[j]
                    hs = 110 + m / 2 + rng.normal(0, 8)
                    as_ = 110 - m / 2 + rng.normal(0, 8)
                    H.append(teams[i]); A.append(teams[j]); HS.append(round(hs)); AS.append(round(as_))
    return teams, strength, H, A, HS, AS


def test_points_model_recovers_strength_and_hfa():
    teams, strength, H, A, HS, AS = _synthetic()
    m = ratings.fit(H, A, HS, AS, np.zeros(len(H)), xi=0, ridge=0.5)
    assert m.hfa == pytest.approx(2.5, abs=1.0)
    est = np.array([m.rating(t) for t in teams])
    assert np.corrcoef(est, strength)[0, 1] > 0.8
    assert 9 < m.sd_margin < 14


def test_outcomes_consistent():
    teams, strength, H, A, HS, AS = _synthetic(1)
    m = ratings.fit(H, A, HS, AS, np.zeros(len(H)), xi=0, ridge=0.5)
    ph, pa = 112.0, 108.0
    home = ratings.outcome(m, ph, pa, "ML", "home", None)
    away = ratings.outcome(m, ph, pa, "ML", "away", None)
    assert home.pw + away.pw == pytest.approx(1)
    assert home.pw > 0.5
    s = ratings.outcome(m, ph, pa, "SPREAD", "home", -4.0)
    assert s.pp > 0 and s.pw + s.pp + s.pl == pytest.approx(1)  # integer line can push
    o = ratings.outcome(m, ph, pa, "TOTAL", "over", 220.5)
    u = ratings.outcome(m, ph, pa, "TOTAL", "under", 220.5)
    assert o.pw + u.pw == pytest.approx(1) and o.pp == 0


@pytest.mark.parametrize("market,sel,line,hs,as_,exp", [
    ("ML", "home", None, 24, 20, 1.0), ("ML", "away", None, 24, 20, -1.0), ("ML", "home", None, 20, 20, 0.0),
    ("SPREAD", "home", -3.5, 24, 20, 1.0), ("SPREAD", "home", -4.0, 24, 20, 0.0), ("SPREAD", "away", -4.5, 24, 20, 1.0),
    ("TOTAL", "over", 43.5, 24, 20, 1.0), ("TOTAL", "under", 44.0, 24, 20, 0.0),
])
def test_us_settlement(market, sel, line, hs, as_, exp):
    assert settle_value(market, sel, line, hs, as_) == exp


def test_parse_espn_us():
    e = {"id": "9", "date": "2026-11-15T18:00Z", "season": {"type": 2},
         "status": {"type": {"completed": False}},
         "competitions": [{"neutralSite": False, "competitors": [
             {"homeAway": "home", "team": {"displayName": "Detroit Lions", "abbreviation": "DET"}, "score": "0"},
             {"homeAway": "away", "team": {"displayName": "New England Patriots", "abbreviation": "NE"}, "score": "0"}],
             "odds": [None, {"provider": {"name": "DraftKings"},
                             "moneyline": {"home": {"close": {"odds": "-155"}}, "away": {"close": {"odds": "+130"}}},
                             "pointSpread": {"home": {"close": {"line": "-2.5", "odds": "-120"}},
                                             "away": {"close": {"line": "+2.5", "odds": "+100"}}},
                             "total": {"over": {"close": {"line": "o51.5", "odds": "-110"}},
                                       "under": {"close": {"line": "u51.5", "odds": "-110"}}}}]}]}
    ev = parse_espn(e, "nfl")
    d = {(m, s, l): p for _, m, s, l, p in ev["odds"]}
    assert d[("ML", "away", None)] == pytest.approx(2.3)
    assert d[("SPREAD", "away", -2.5)] == pytest.approx(2.0)
    assert d[("TOTAL", "under", 51.5)] == pytest.approx(1 + 100 / 110)
