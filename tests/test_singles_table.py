"""Issue #85: History shows a single-pick statistics table by sport (and market), like the parlay table.

All picks below are test fixtures built for this test, never real recommendations. The browser test runs
the real docs/assets/doyen.js in Node through tests/js/render_home.js."""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tests" / "js" / "render_home.js"
NOW = "2026-11-18T23:00:00+00:00"


def _pick(i, sport, market, state, result=None, pnl=None):
    status = {"state": state, "label": state}
    if state == "settled":
        status.update(result=result, pnl=pnl)
    return {"id": f"p{i}", "event_id": f"ev{i}", "sport": sport, "competition": "Test", "title": f"H{i} v A{i}",
            "start_utc": "2026-11-15T18:00:00+00:00", "published_at": "2026-11-15T10:00:00+00:00",
            "market": market, "selection": f"H{i} to win", "odds": 2.0, "bookmaker": "BookA", "status": status}


PICKS = [
    _pick(1, "soccer", "Match result", "settled", "won", 1.0),
    _pick(2, "soccer", "Match result", "settled", "lost", -1.0),
    _pick(3, "soccer", "Total goals", "settled", "lost", -1.0),
    _pick(4, "soccer", "Total goals", "settled", "push", 0.0),
    _pick(5, "soccer", "Match result", "active"),
    _pick(6, "nba", "Moneyline", "settled", "won", 0.75),
    _pick(7, "nba", "Moneyline", "settled", "won", 0.5),
    _pick(8, "nba", "Moneyline", "withdrawn"),
]
RECORD = {"won": 3, "lost": 2, "push": 1, "profit_units": 0.25, "open": 2}


def _render():
    data = {"generated": NOW, "default_timezone": "America/New_York", "picks": [], "history": PICKS, "record": RECORD,
            "events": [], "watching": [], "close_to_value": [], "briefing": {}, "funnel_7d": {}, "sports": {},
            "parlays": {"recommendations": []}, "estimated_parlays": {}, "parlay_history": []}
    out = subprocess.run(["node", str(HARNESS)], input=json.dumps({"data": data, "now": NOW, "hash": "#/history"}),
                         capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout


def _rows(html, attr):
    i = html.index(f"<table {attr}>")
    table = html[i:html.index("</table>", i)]
    return {m[0]: re.findall(r"<td[^>]*>([^<]*)</td>", m[1])
            for m in re.findall(r'<tr[^>]*><th scope="row">([^<]+)</th>(.*?)</tr>', table)}


def test_single_pick_table_by_sport_and_total_matches_record():
    html = _render()
    sec = html[html.index('id="pick-history"'):]
    assert sec.index("data-singles-by-sport") < sec.index('class="rows hist"')   # top of the singles section
    assert '<div class="card ph-rec sg-rec"><table data-singles-by-sport>' in sec      # same component as parlays
    assert "flat 1-unit stake per pick" in sec
    rows = _rows(sec, "data-singles-by-sport")
    assert list(rows) == ["Soccer", "NFL", "NBA", "Tennis", "Total"]
    # Won–lost, Hit rate, Void/push, Open, Paper P/L, ROI
    assert rows["Soccer"] == ["1–2", "33%", "1", "1", "−1.00 u", "−25.0%"]
    assert rows["NBA"] == ["2–0", "100%", "0", "1", "+1.25 u", "+62.5%"]
    assert rows["NFL"] == ["0–0", "–", "0", "0", "–", "–"]
    assert rows["Total"] == ["3–2", "60%", "1", "2", "+0.25 u", "+4.2%"]
    # Total equals the site's single-pick record.
    t = rows["Total"]
    assert t[0] == f"{RECORD['won']}–{RECORD['lost']}" and t[2] == str(RECORD["push"]) and t[3] == str(RECORD["open"])
    assert t[4] == f"+{RECORD['profit_units']:.2f} u"
    assert f"Record <b>{RECORD['won']}–{RECORD['lost']}–{RECORD['push']}</b>" in sec
    assert 'class="pl pos">+1.25 u' in sec and 'class="pl neg">−1.00 u' in sec


def test_single_pick_table_by_market_hides_empty_markets():
    rows = _rows(_render(), "data-singles-by-market")
    assert list(rows) == ["Match result", "Moneyline", "Total goals", "Total"]
    assert rows["Total goals"] == ["0–1", "0%", "1", "0", "−1.00 u", "−50.0%"]
    assert rows["Match result"] == ["1–1", "50%", "0", "1", "0.00 u", "0.0%"]
