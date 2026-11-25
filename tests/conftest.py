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
