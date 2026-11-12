import numpy as np
import pytest

from sbi.models import dixon_coles as dc
from sbi.sources import international as src


def test_american_to_decimal():
    assert src.american_to_decimal("+150") == pytest.approx(2.5)
    assert src.american_to_decimal("-200") == pytest.approx(1.5)
    assert src.american_to_decimal(None) is None
    assert src.american_to_decimal("EVEN") is None


def test_aliases():
    assert src.canon("Türkiye") == "Turkey"
    assert src.canon("Congo DR") == "DR Congo"
    assert src.canon("Norway") == "Norway"


def test_parse_espn_event():
    e = {"id": "1", "date": "2026-11-14T17:00Z", "status": {"type": {"name": "STATUS_SCHEDULED", "completed": False}},
         "competitions": [{"neutralSite": False, "venue": {"address": {"country": "Norway"}},
                           "competitors": [{"homeAway": "home", "team": {"displayName": "Norway"}, "score": "0"},
                                           {"homeAway": "away", "team": {"displayName": "Wales"}, "score": "0"}],
                           "odds": [{"provider": {"name": "DraftKings"},
                                     "moneyline": {"home": {"open": {"odds": "-450"}, "close": {"odds": "-500"}},
                                                   "away": {"close": {"odds": "+950"}}},
                                     "drawOdds": {"moneyLine": 550},
                                     "total": {"over": {"close": {"line": "o3.5", "odds": "+105"}},
                                               "under": {"close": {"line": "u3.5", "odds": "-135"}}},
                                     "pointSpread": {"home": {"close": {"line": "-1.5", "odds": "-170"}},
                                                     "away": {"close": {"line": "+1.5", "odds": "+135"}}}}]}]}
    ev = src._parse_event(e, "uefa.nations")
    assert ev["home"] == "Norway" and not ev["neutral"] and not ev["completed"]
    odds = {(m, s, l, k): p for _, m, s, l, p, k in ev["odds"]}
    assert odds[("1X2", "H", None, "current")] == pytest.approx(1.2)
    assert odds[("1X2", "D", None, "current")] == pytest.approx(6.5)
    assert odds[("OU", "over", 3.5, "current")] == pytest.approx(2.05)
    assert odds[("AH", "home", -1.5, "current")] == pytest.approx(1 + 100 / 170)
    assert odds[("AH", "away", -1.5, "current")] == pytest.approx(2.35)  # stored on the home-perspective line


def test_neutral_venue_removes_home_advantage():
    rng = np.random.default_rng(0)
    teams = [f"N{i}" for i in range(8)]
    H, A, HG, AG, NEU = [], [], [], [], []
    for _ in range(30):
        for i in range(8):
            for j in range(8):
                if i == j:
                    continue
                neu = rng.random() < 0.3
                lam = np.exp((0 if neu else 0.35) + 0.1)
                H.append(teams[i]); A.append(teams[j]); HG.append(rng.poisson(lam)); AG.append(rng.poisson(np.exp(0.1)))
                NEU.append(neu)
    m = dc.fit(np.array(H), np.array(A), np.array(HG), np.array(AG), np.zeros(len(H)), xi=0, ridge=0.1,
               neutral=np.array(NEU))
    assert m.home == pytest.approx(0.35, abs=0.08)
    lam_home, _ = m.rates("N0", "N1")
    lam_neu, _ = m.rates("N0", "N1", neutral=True)
    assert lam_home / lam_neu == pytest.approx(np.exp(m.home))
