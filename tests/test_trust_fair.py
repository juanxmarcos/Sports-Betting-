"""Owner request 2026-11-26: a trust check (said vs actually won, parlays since 24 Nov 2026) and a fair
price on each open parlay card. Every game, price and probability here is test data."""
import re
from datetime import timedelta

from sbi import site
from tests import test_parlay_history as ph
from tests.test_parlay_history import NOW, _card, _data, _rec, _run, needs_node


def _hist(pid, day, result, hit):
    r = _rec(pid, day=day, result=result)
    r["est_hit_chance"] = hit
    return r


def test_trust_summary_counts_only_settled_parlays_since_24_nov():
    rows = [_hist("a", "2026-11-25", "won", 0.4), _hist("b", "2026-11-25", "lost", 0.2),
            _hist("c", "2026-11-24", "lost", 0.3), _hist("d", "2026-11-25", "open", 0.5),
            _hist("e", "2026-11-23", "won", 0.9)]                     # before the current rules: left out
    assert site.trust_summary(rows) == {"since": "2026-11-24", "settled": 3, "won": 1, "said": 0.3}
    assert site.trust_summary(rows[3:]) is None


@needs_node
def test_trust_line_on_today_and_history():
    for h in ("#/", "#/history"):
        d = _data([])
        d["estimated_parlays"]["trust"] = {"since": "2026-11-24", "settled": 3, "won": 1, "said": 0.3}
        html = _run({"data": d, "now": ph._iso(NOW), "hash": h})
        line = re.search(r"data-trust-check>(.*?)</p>", html).group(1)
        assert "said 30% would win, actually won 33% (1 of 3 parlays)" in line and "Too early to judge" in line


@needs_node
def test_no_trust_line_without_settled_parlays():
    assert "data-trust-check" not in _run({"data": _data([]), "now": ph._iso(NOW)})


@needs_node
def test_open_parlay_shows_fair_price_from_market_probabilities():
    later = [("A v B", "A to win", NOW + timedelta(hours=1)), ("C v D", "C to win", NOW + timedelta(hours=2))]
    r = _rec("pe-open", legs=later)
    r["legs"][0]["market_prob"], r["legs"][1]["market_prob"] = 0.5, 0.4    # fair = 1 / 0.2 = 5.00
    started = _rec("pe-started")
    for l in started["legs"]:
        l["market_prob"] = 0.5
    html = _run({"data": _data([r, started]), "now": ph._iso(NOW)})
    card = _card(html, "pe-open")
    assert "Fair price +400 (5.00)" in card and "paying more than it should" in card
    assert "data-fair-odds" not in _card(html, "pe-started")             # betting closed: no fair price


@needs_node
def test_no_fair_price_when_a_leg_lacks_a_market_probability():
    later = [("A v B", "A to win", NOW + timedelta(hours=1)), ("C v D", "C to win", NOW + timedelta(hours=2))]
    r = _rec("pe-open", legs=later)
    r["legs"][0]["market_prob"] = 0.5
    assert "data-fair-odds" not in _card(_run({"data": _data([r]), "now": ph._iso(NOW)}), "pe-open")
