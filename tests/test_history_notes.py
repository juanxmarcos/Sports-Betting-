"""Issue #92: one short note under each History table (break-even rate + small-sample warning).
Test fixtures only. Runs the real docs/assets/doyen.js in Node through tests/js/render_home.js."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tests" / "js" / "render_home.js"
NOW = "2026-11-18T23:00:00+00:00"


def _pick(i, result, odds):
    return {"id": f"p{i}", "event_id": f"ev{i}", "sport": "soccer", "competition": "Test", "title": f"H{i} v A{i}",
            "start_utc": "2026-11-15T18:00:00+00:00", "published_at": "2026-11-15T10:00:00+00:00",
            "market": "Match result", "selection": f"H{i} to win", "odds": odds, "bookmaker": "BookA",
            "status": {"state": "settled", "label": "settled", "result": result, "pnl": 1.0 if result == "won" else -1.0}}


def _parlay(pid, n, odds, result):
    legs = [{"event_id": f"{pid}-{k}", "title": f"A{k} v B{k}", "selection": "home", "selection_text": f"A{k} to win",
             "price": 1.5, "start_utc": "2026-11-15T18:00:00+00:00", "result": "won"} for k in range(n)]
    return {"parlay_id": pid, "date": "2026-11-15", "bookmaker": "BookA", "n_legs": n, "estimated_odds": odds,
            "stake": "10.00", "gross_payout": "30.00", "result": result, "paper_pl": "0.00", "legs": legs}


def _render(history, parlays):
    est = {"record": {"rows": len(parlays), "won": 1, "lost": 3, "void": 0, "open": 0, "paper_pl": "-10.00",
                      "by_legs": {"2": {"won": 1, "lost": 1, "void": 0, "open": 0, "paper_pl": "10.00"},
                                  "3": {"won": 0, "lost": 1, "void": 0, "open": 0, "paper_pl": "-10.00"},
                                  "4": {"won": 0, "lost": 1, "void": 0, "open": 0, "paper_pl": "-10.00"}}},
           "record_line": "Estimated parlays record: 1–3, paper P/L −$10.00"}
    data = {"generated": NOW, "default_timezone": "America/New_York", "picks": [], "history": history,
            "record": {"won": 1, "lost": 1, "push": 0, "profit_units": 0, "open": 0}, "events": [], "watching": [],
            "close_to_value": [], "briefing": {}, "funnel_7d": {}, "sports": {}, "parlays": {"recommendations": []},
            "estimated_parlays": est, "parlay_history": parlays}
    out = subprocess.run(["node", str(HARNESS)], input=json.dumps({"data": data, "now": NOW, "hash": "#/history"}),
                         capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout


def test_break_even_notes_under_each_table():
    parlays = [_parlay("a", 2, 3.0, "won"), _parlay("b", 2, 3.0, "lost"), _parlay("c", 3, 6.0, "lost"),
               _parlay("d", 4, 11.0, "lost"), _parlay("e", 2, 9.0, "open")]           # open bets don't count
    html = _render([_pick(1, "won", 1.92), _pick(2, "lost", 1.92)], parlays)
    assert "Break-even: 2 legs 33% · 3 legs 17% · 4–5 legs 9%. Small sample, so luck swings results a lot." in html
    assert "Break-even at these odds: about 52%. Small sample, so luck swings results a lot." in html
    assert html.count("data-be-note") == 2


def test_note_without_settled_bets_is_only_the_warning():
    html = _render([], [_parlay("e", 2, 3.0, "open")])
    assert "Break-even" not in html.split('id="pick-history"')[0].split("data-ph-by-legs")[-1].split("ph-list")[0]
    assert "Small sample, so luck swings results a lot." in html
