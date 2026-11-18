"""Issue #92: one short muted note under each History statistics table (break-even and small-sample warning).

Every parlay, pick and price below is a test fixture built for this test, never a real quote or
recommendation. The browser test runs the real docs/assets/doyen.js in Node through tests/js/render_home.js."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tests" / "js" / "render_home.js"
NOW = "2026-11-18T23:00:00+00:00"
LUCK = "Small sample, so luck swings results a lot."
pytestmark = pytest.mark.skipif(not shutil.which("node") and not os.environ.get("CI"), reason="node is not installed")


def _leg(i, market, price, result):
    return {"event_id": f"ev{i}", "title": f"H{i} v A{i}", "market": market, "selection": "home",
            "selection_text": f"H{i} to win", "price": price, "start_utc": "2026-11-15T18:00:00+00:00", "result": result}


def _parlay(i, n, odds, result, market="ML", leg_price=1.6):
    leg_res = "lost" if result == "lost" else ("won" if result == "won" else "open")
    return {"parlay_id": f"pe-{i}", "date": "2026-11-15", "bookmaker": "BookA", "n_legs": n, "estimated_odds": odds,
            "stake": "10.00", "gross_payout": f"{10 * odds:.2f}", "result": result, "paper_pl": "0.00",
            "legs": [_leg(f"{i}-{k}", market, leg_price, leg_res) for k in range(n)]}


def _pick(i, sport, odds, state, result=None, pnl=None):
    status = {"state": state, "label": state}
    if state == "settled":
        status.update(result=result, pnl=pnl)
    return {"id": f"p{i}", "event_id": f"e{i}", "sport": sport, "competition": "Test", "title": f"H{i} v A{i}",
            "start_utc": "2026-11-15T18:00:00+00:00", "published_at": "2026-11-15T10:00:00+00:00",
            "market": "Moneyline", "selection": f"H{i} to win", "odds": odds, "bookmaker": "BookA", "status": status}


def _render(parlays, record, picks):
    data = {"generated": NOW, "default_timezone": "America/New_York", "picks": [], "history": picks, "record": {},
            "events": [], "watching": [], "close_to_value": [], "briefing": {}, "funnel_7d": {}, "sports": {},
            "parlays": {"recommendations": []}, "estimated_parlays": {"record": record}, "parlay_history": parlays}
    out = subprocess.run(["node", str(HARNESS)], input=json.dumps({"data": data, "now": NOW, "hash": "#/history"}),
                         capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout


def _note(html, attr):
    m = re.search(rf'<p class="small muted tnote" {attr}>([^<]*)</p>', html)
    assert m, attr
    return m.group(1)


PARLAYS = [
    _parlay(1, 2, 2.5, "won"), _parlay(2, 2, 3.5, "lost"), _parlay(3, 2, 9.0, "open"),   # open is skipped
    _parlay(4, 4, 11.0, "lost", market="1X2", leg_price=2.5), _parlay(5, 5, 12.0, "void"),
]
RECORD = {"won": 1, "lost": 2, "void": 1, "open": 1, "paper_pl": "-5.00", "expected_wins_settled": 0.83,
          "by_legs": {"2": {"won": 1, "lost": 1, "open": 1, "void": 0, "paper_pl": "5.00"},
                      "4": {"won": 0, "lost": 1, "open": 0, "void": 0, "paper_pl": "-10.00"},
                      "5": {"won": 0, "lost": 0, "open": 0, "void": 1, "paper_pl": "0.00"}},
          "by_market": {"ML": {"won": 2, "lost": 2, "push": 0, "void": 0, "open": 2, "label": "Moneyline"},
                        "1X2": {"won": 0, "lost": 4, "push": 0, "void": 0, "open": 0, "label": "Match result"}}}
PICKS = [_pick(1, "nba", 1.9, "settled", "won", 0.9), _pick(2, "nba", 1.94, "settled", "lost", -1.0),
         _pick(3, "soccer", 5.0, "settled", "push", 0.0), _pick(4, "soccer", 9.0, "active")]


def test_notes_under_each_table_with_break_even():
    html = _render(PARLAYS, RECORD, PICKS)
    # 2 legs: settled odds 2.5 and 3.5, average 3.0 → 33%. 3 legs: none settled → skipped. 4–5: 11.0 → 9%.
    assert _note(html, "data-note-by-legs") == f"Break-even: 2 legs 33% · 4–5 legs 9%. Expected wins 0.8, actual 1. {LUCK}"
    # Leg prices: Moneyline 1.6 → 63%; Match result 2.5 → 40%.
    assert _note(html, "data-note-by-market") == f"Break-even per leg: Moneyline 63% · Match result 40%. {LUCK}"
    # Singles: won/lost at 1.90 and 1.94, average 1.92 → 52%. Push and active picks are excluded.
    assert _note(html, "data-note-singles") == f"Break-even at these odds: about 52%. {LUCK}"
    # Each note sits directly after its own table.
    for table, attr in (("data-ph-by-legs", "data-note-by-legs"), ("data-ph-by-market", "data-note-by-market"),
                        ("data-singles-by-sport", "data-note-singles")):
        i = html.index(f"<table {table}>")
        assert html.index("</div>", html.index("</table>", i)) < html.index(attr) < html.index("</p>", html.index(attr))
        assert html.count(attr) == 1


def test_no_settled_bets_shows_only_the_warning():
    parlays = [_parlay(1, 2, 3.0, "open")]
    record = {"won": 0, "lost": 0, "void": 0, "open": 1, "paper_pl": "0.00",
              "by_legs": {"2": {"won": 0, "lost": 0, "open": 1, "void": 0, "paper_pl": "0.00"}},
              "by_market": {"ML": {"won": 0, "lost": 0, "push": 0, "void": 0, "open": 2, "label": "Moneyline"}}}
    html = _render(parlays, record, [_pick(1, "nba", 1.9, "active")])
    assert _note(html, "data-note-by-legs") == LUCK
    assert _note(html, "data-note-by-market") == LUCK
    assert _note(html, "data-note-singles") == LUCK
