"""Owner decision 2026-11-25: the legacy best-price engine (singles-v1) publishes nothing by default."""
import pytest

from sbi import pipeline


@pytest.mark.legacy_off
def test_publish_pick_is_off_by_default():
    # Returns before touching any argument, so no database or candidate is needed.
    assert pipeline.publish_pick(None, None, "e", None, None, {}, {}, [], None, 1, "v", []) == 0
