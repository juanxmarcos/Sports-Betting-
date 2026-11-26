import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


@pytest.fixture(autouse=True)
def _legacy_singles_on(monkeypatch, request):
    """The legacy best-price engine is off in production (owner, 2026-11-25). Its own tests still
    exercise it, so they run with the switch on; tests marked `legacy_off` see the production default."""
    if request.node.get_closest_marker("legacy_off"):
        monkeypatch.delenv("SBI_LEGACY_SINGLES", raising=False)
    else:
        monkeypatch.setenv("SBI_LEGACY_SINGLES", "1")


def pytest_configure(config):
    config.addinivalue_line("markers", "legacy_off: run with the legacy single-pick engine switched off")
    config.addinivalue_line("markers", "sensible_rules: run with the production parlay rules (v5, 2026-11-26)")


@pytest.fixture(autouse=True)
def _parlay_v4_limits(monkeypatch, request):
    """Owner decision 2026-11-26 (parlay-estimated-v5): strong legs only, 2-3 legs, at most 3 cards.
    Most parlay tests check plumbing (ledger, previews, markets, lines, settlement) with coin-flip test
    legs, so they run with the v4 limits; tests marked `sensible_rules` see the production rules."""
    if request.node.get_closest_marker("sensible_rules"):
        return
    from sbi import parlay_estimated as pe
    monkeypatch.setattr(pe, "MIN_LEG_MARKET_PROB", 0.0)
    monkeypatch.setattr(pe, "MIN_LEG_PRICE", 1.0)
    monkeypatch.setattr(pe, "MIN_COMBINED_ODDS", {"2": 2.2, "3": 3.5, "4-5": 6.0})
    monkeypatch.setattr(pe, "SIZE_BUCKETS", ((2, 2), (3, 3), (4, 5)))
    monkeypatch.setattr(pe, "MAX_CARDS", 5)
    monkeypatch.setattr(pe, "PER_SIZE", 2)
