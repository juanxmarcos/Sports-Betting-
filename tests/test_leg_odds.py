"""Issue #74: every parlay card shows each leg's own price, American odds first with decimal alongside.

All prices, games and teams below are test data; the browser tests run the real docs/assets/doyen.js."""
import re
from datetime import timedelta
from math import prod

import pytest

from tests import test_parlay_history as ph
from tests.test_parlay_previews import DAYS, _previews, pcard
from tests.test_parlay_estimated import DAY, _iso, _verified, eblock, ecard, needs_node, render

LEG_PRICE = re.compile(r'class="lg-p" data-leg-price="([^"]+)">([+-]\d+) \((\d+\.\d\d)\)<')


def _card(html, pid):
    i = html.index(f'data-parlay="{pid}"')
    return html[i:html.index("</article>", i)]


def _american(dec):
    """Same rule as the site: +100 x (d - 1) from 2.00 up, else -100 / (d - 1)."""
    return f"+{round((dec - 1) * 100)}" if dec >= 2 else f"-{round(100 / (dec - 1))}"


@pytest.mark.parametrize("dec,us", [(1.40, "-250"), (2.50, "+150"), (2.00, "+100"), (1.91, "-110"), (3.25, "+225")])
def test_american_conversion(dec, us):
    assert _american(dec) == us


@needs_node
@pytest.mark.parametrize("dec,us", [(1.40, "-250"), (2.50, "+150"), (2.00, "+100")])
def test_site_converts_to_american(dec, us):
    html = render(eblock([ecard("pe-c", prices=[dec, 1.9])]))
    assert LEG_PRICE.findall(_card(html, "pe-c"))[0][1:] == (us, f"{dec:.2f}")


@needs_node
def test_three_leg_card_shows_each_leg_price_and_they_multiply_to_the_combined_odds():
    rec = ecard("pe-3", prices=[1.40, 2.50, 2.00])
    card = _card(render(eblock([rec])), "pe-3")
    got = LEG_PRICE.findall(card)
    assert [(us, d) for _, us, d in got] == [("-250", "1.40"), ("+150", "2.50"), ("+100", "2.00")]
    assert card.count("<li>") == 3
    shown = prod(float(d) for _, _, d in got)
    assert shown == pytest.approx(rec["estimated_odds"], rel=0.005)       # within rounding
    assert ">7.00<" in card and "<b>$10 bet pays $70.00</b>" in card       # combined odds and payout unchanged


@needs_node
def test_preview_cards_show_leg_prices():
    html = render(eblock([], previews=_previews({DAYS[0]: [pcard("pe-pv", DAYS[0])]})), hday="1")
    assert [(us, d) for _, us, d in LEG_PRICE.findall(_card(html, "pe-pv"))] == [("-111", "1.90"), ("+110", "2.10")]


@needs_node
def test_leg_without_price_shows_nothing_for_that_leg():
    later = [("T3H v T3A", "T3H to win", ph.NOW + timedelta(hours=1)), ("T4H v T4A", "T4H to win", ph.NOW + timedelta(hours=2))]
    rec = ph._rec("pe-old", legs=later)
    del rec["legs"][0]["price"]                                            # old row: no stored leg price
    rec["legs"][1]["price"] = 1.5
    card = _card(ph._run({"data": ph._data([rec]), "now": _iso(ph.NOW)}), "pe-old")
    assert [(us, d) for _, us, d in LEG_PRICE.findall(card)] == [("-200", "1.50")]
    assert card.count("data-leg-price") == 1 and "NaN" not in card and "undefined" not in card


@needs_node
def test_started_and_settled_ledger_cards_show_leg_prices():
    won = ph._rec("pe-w", result="won", paper_pl="30.00", leg_results=["won", "won"],
                  legs=[("A v B", "A to win", ph.NOW - timedelta(hours=4)), ("C v D", "C to win", ph.NOW - timedelta(hours=3))])
    html = ph._run({"data": ph._data([won, ph._rec("pe-s")]), "now": _iso(ph.NOW)})
    for pid in ("pe-w", "pe-s"):
        assert [(us, d) for _, us, d in LEG_PRICE.findall(_card(html, pid))] == [("+100", "2.00")] * 2


@needs_node
def test_history_parlay_row_shows_leg_prices():
    rec = ph._rec("pe-h", day=ph.YESTERDAY, result="won", paper_pl="20.00", odds=3.0, leg_results=["won", "won"])
    rec["legs"][0]["price"], rec["legs"][1]["price"] = 1.5, 2.0
    html = ph._run({"data": ph._data([], history=[rec]), "now": _iso(ph.NOW), "hash": "#/history"})
    row = html[html.index('data-ph="pe-h"'):]
    row = row[:row.index('<div class="ph-f')]
    assert re.findall(r'<span class="lg-p" data-leg-price="[^"]+">([^<]+)</span>', row) == ["-200 (1.50)", "+100 (2.00)"]
    assert "T1A to win ✓" in row


@needs_node
def test_verified_quote_card_shows_leg_price_only_when_present():
    v = _verified("v1", ["e1", "e2"])
    v["legs"][0]["price"] = 1.75
    strict = {"date": DAY, "status": "published", "blockers": [], "recommendations": [v]}
    card = _card(render(eblock([]), strict), "v1")
    assert [(us, d) for _, us, d in LEG_PRICE.findall(card)] == [("-133", "1.75")] and card.count("data-leg-price") == 1
