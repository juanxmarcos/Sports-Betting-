"""Issue #57: today's recorded parlays stay on the homepage after kickoff, and History lists every parlay.

Every game, price and bookmaker below is test data built for these tests, never a real quote. The
database tests use a temporary database; the browser tests run the real docs/assets/doyen.js."""
import csv
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from sbi import config, db, site
from sbi import parlay_estimated as pe

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tests" / "js" / "render_home.js"
NOW = datetime(2026, 11, 13, 23, 0, tzinfo=timezone.utc)          # 6:00 PM in New York
DAY, YESTERDAY = "2026-11-13", "2026-11-12"
needs_node = pytest.mark.skipif(not shutil.which("node") and not os.environ.get("CI"), reason="node is not installed")


def _iso(dt):
    return dt.isoformat()


@pytest.fixture
def con(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(config, "SITE_DIR", tmp_path / "site")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    return db.connect(tmp_path / "t.sqlite")


def _event(con, eid, ko, home, away, status="scheduled", hs=None, as_=None):
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,home_score,away_score,source,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (eid, "nba", "NBA", ko.isoformat(), home, away, status, hs, as_, "test", db.utcnow()))


def _leg(eid, title, ko, sel="home", price=2.0, prob=0.55):
    return {"event_id": eid, "market": "ML", "selection": sel, "price": price, "prob": prob, "title": title,
            "start_utc": _iso(ko)}


def _row(pid, day, first_seen, legs, odds, stake=10, hit=0.3):
    return {"first_seen": _iso(first_seen), "date": day, "parlay_id": pid, "bookmaker": "BookA", "n_legs": len(legs),
            "legs": json.dumps(legs), "kind": pe.ESTIMATE_KIND, "estimated_odds": odds, "est_hit_chance": hit,
            "estimated_ev": 0.1, "stake": stake}


def _fixture(con):
    """Yesterday: one won 2-leg, one lost 3-leg. Today: a 2-leg whose first leg started an hour ago."""
    y = NOW - timedelta(days=1)
    _event(con, "nba:y1", y - timedelta(hours=1), "Y1H", "Y1A", "finished", 110, 100)
    _event(con, "nba:y2", y, "Y2H", "Y2A", "finished", 100, 90)
    _event(con, "nba:y3", y, "Y3H", "Y3A", "finished", 80, 95)
    _event(con, "nba:t1", NOW - timedelta(hours=1), "T1H", "T1A")
    _event(con, "nba:t2", NOW + timedelta(hours=2), "T2H", "T2A")
    con.commit()
    rows = [
        _row("pe-won", YESTERDAY, y - timedelta(hours=6),
             [_leg("nba:y1", "Y1H v Y1A", y - timedelta(hours=1)), _leg("nba:y2", "Y2H v Y2A", y, price=1.5)], 3.0),
        _row("pe-lost", YESTERDAY, y - timedelta(hours=5),
             [_leg("nba:y1", "Y1H v Y1A", y - timedelta(hours=1)), _leg("nba:y2", "Y2H v Y2A", y),
              _leg("nba:y3", "Y3H v Y3A", y)], 8.0),
        _row("pe-today", DAY, NOW - timedelta(hours=2),
             [_leg("nba:t1", "T1H v T1A", NOW - timedelta(hours=1), sel="away"),
              _leg("nba:t2", "T2H v T2A", NOW + timedelta(hours=2))], 4.0),
    ]
    path = pe.ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=pe.LEDGER_FIELDS)
        w.writeheader()
        w.writerows(rows)
    return path


def test_ledger_rows_are_newest_first_with_results_that_match_settle(con):
    path = _fixture(con)
    before = path.read_bytes()
    rows = pe.ledger_rows(con)
    assert [r["parlay_id"] for r in rows] == ["pe-today", "pe-lost", "pe-won"]
    by = {r["parlay_id"]: r for r in rows}
    assert by["pe-won"]["result"] == "won" and by["pe-won"]["paper_pl"] == "20.00"
    assert by["pe-won"]["gross_payout"] == "30.00" and [x["result"] for x in by["pe-won"]["legs"]] == ["won", "won"]
    assert by["pe-lost"]["result"] == "lost" and by["pe-lost"]["paper_pl"] == "-10.00"
    assert [x["result"] for x in by["pe-lost"]["legs"]] == ["won", "won", "lost"]
    assert by["pe-today"]["result"] == "open" and by["pe-today"]["paper_pl"] == "0.00"
    assert by["pe-today"]["legs"][0]["selection_text"] == "T1A to win"
    assert by["pe-today"]["legs"][1]["selection_text"] == "T2H to win"
    # Totals equal the read-only settlement, overall and by leg count.
    s = pe.settle(con)
    assert sum(Decimal(r["paper_pl"]) for r in rows) == Decimal(s["paper_pl"])
    for st in ("won", "lost", "void", "open"):
        assert sum(r["result"] == st for r in rows) == s[st]
        for n, g in s["by_legs"].items():
            assert sum(r["result"] == st and str(r["n_legs"]) == n for r in rows) == g[st]
    assert [r["parlay_id"] for r in pe.ledger_rows(con, day=DAY)] == ["pe-today"]
    assert path.read_bytes() == before                             # the ledger is never edited


def test_site_build_exports_todays_rows_to_the_homepage_and_all_rows_to_history(con):
    _fixture(con)
    d = json.loads(site.build(con, NOW).read_text())
    assert [r["parlay_id"] for r in d["estimated_parlays"]["ledger_today"]] == ["pe-today"]
    assert [r["parlay_id"] for r in d["parlay_history"]] == ["pe-today", "pe-lost", "pe-won"]
    lite = json.loads((config.ROOT / "docs" / "data" / "parlays.json").read_text())
    assert "parlay_history" not in lite                            # the homepage file stays small
    assert lite["estimated_parlays"]["ledger_today"] == d["estimated_parlays"]["ledger_today"]


# ---------- rendered pages (real docs/assets/doyen.js in Node) ----------
def _run(payload):
    out = subprocess.run(["node", str(HARNESS)], input=json.dumps(payload), capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout


def _rec(pid, day=DAY, legs=None, result="open", odds=4.0, first_seen=None, paper_pl="0.00", leg_results=None):
    legs = legs or [("T1H v T1A", "T1A to win", NOW - timedelta(hours=1)), ("T2H v T2A", "T2H to win", NOW + timedelta(hours=2))]
    leg_results = leg_results or ["open"] * len(legs)
    return {"parlay_id": pid, "date": day, "first_seen": _iso(first_seen or NOW - timedelta(hours=2)),
            "kind": pe.ESTIMATE_KIND, "bookmaker": "BookA", "n_legs": len(legs), "estimated_odds": odds,
            "stake": "10.00", "gross_payout": f"{10 * odds:.2f}", "est_hit_chance": 0.3, "result": result,
            "paper_pl": paper_pl,
            "legs": [{"event_id": f"ev-{pid}-{i}", "title": t, "market": "ML", "selection": "home", "selection_text": s,
                      "price": 2.0, "start_utc": _iso(ko), "result": lr}
                     for i, ((t, s, ko), lr) in enumerate(zip(legs, leg_results))]}


def _data(ledger_today, recs=None, history=None, record=None):
    est = {"status": "estimated", "kind": pe.ESTIMATE_KIND, "date": DAY, "recommendations": recs or [],
           "ledger_today": ledger_today,
           "record": record or {"rows": 3, "won": 1, "lost": 1, "void": 0, "open": 1, "paper_pl": "10.00",
                                "staked": "20.00",
                                "by_legs": {"2": {"rows": 2, "won": 1, "lost": 0, "void": 0, "open": 1, "paper_pl": "20.00"},
                                            "3": {"rows": 1, "won": 0, "lost": 1, "void": 0, "open": 0, "paper_pl": "-10.00"}}}}
    strict = {"date": DAY, "status": "not_published", "blockers": [{"key": "combined_quote", "text": "x"}], "recommendations": []}
    return {"generated": _iso(NOW), "default_timezone": "America/New_York", "parlays": strict, "estimated_parlays": est,
            "parlay_history": history or [], "picks": [], "history": [], "events": [], "watching": [], "close_to_value": [],
            "briefing": {}, "funnel_7d": {}, "sports": {}, "record": {"won": 0, "lost": 0, "push": 0, "profit_units": 0, "open": 0}}


def recorded(html):
    return re.findall(r'<article class="card parlay est recorded" data-parlay="([^"]+)"[^>]*data-state="([^"]+)"', html)


def _card(html, pid):
    i = html.index(f'data-parlay="{pid}"')
    return html[i:html.index("</article>", i)]


@needs_node
def test_started_parlay_stays_on_home_marked_closed_and_yesterdays_does_not():
    html = _run({"data": _data([_rec("pe-today"), _rec("pe-old", day=YESTERDAY)]), "now": _iso(NOW)})
    assert recorded(html) == [("pe-today", "closed")]
    card = _card(html, "pe-today")
    assert "Started, betting closed" in card and "Betting closed: a game in this parlay has started." in card
    # Issue #76: the display-only bet amount stays editable. Issue #78: no recorded-$10 line on the card.
    assert "data-stake" in card and ">Bet amount<" in card and "Record uses $10 paper stakes" not in card
    assert "Recorded" not in card and "bet pays" not in card and _payout(card) == "$40.00"
    assert "bet now" not in card.lower() and "check your book" not in card
    assert "Estimated odds at publication" in card and "Price at publication time (published" in card
    assert '<span class="pill estimate">Estimate</span>' in card and "not a bet-slip quote" in card
    assert "pending" in card
    assert pe.EMPTY_TEXT not in html and "Estimated parlays of the day" in html


@needs_node
def test_settled_parlays_show_leg_marks_and_the_result():
    won = _rec("pe-w", result="won", paper_pl="30.00", leg_results=["won", "won"],
               legs=[("A v B", "A to win", NOW - timedelta(hours=4)), ("C v D", "C to win", NOW - timedelta(hours=3))])
    lost = _rec("pe-l", result="lost", paper_pl="-10.00", leg_results=["lost", "open"])
    html = _run({"data": _data([won, lost]), "now": _iso(NOW)})
    assert sorted(recorded(html)) == [("pe-l", "lost"), ("pe-w", "won")]
    w = _card(html, "pe-w")
    assert "data-state-line>Won<" in w and w.count("✓") == 2 and _payout(w) == "Won: would have paid $40.00"
    lo = _card(html, "pe-l")
    assert "data-state-line>Lost<" in lo and "✗" in lo and "pending" not in lo and _payout(lo) == "Lost $10.00"
    for c in (w, lo):                                     # issue #78: no second recorded-$10 block on the card
        assert "Recorded" not in c and "bet pays" not in c and "Paper P/L" not in c


@needs_node
def test_open_recorded_card_and_live_card_are_not_duplicated():
    later = [("T3H v T3A", "T3H to win", NOW + timedelta(hours=1)), ("T4H v T4A", "T4H to win", NOW + timedelta(hours=2))]
    html = _run({"data": _data([_rec("pe-open", legs=later)]), "now": _iso(NOW)})
    card = _card(html, "pe-open")
    assert recorded(html) == [("pe-open", "open")]
    assert re.search(r"Open: first game at 7:00\sPM", card) and "Price from publication time; it may have moved." in card
    assert "Recorded" not in card and "bet pays" not in card
    # The same parlay_id still in the current block shows once, as the live card.
    live = {"parlay_id": "pe-open", "date": DAY, "status": "active", "kind": pe.ESTIMATE_KIND, "bookmaker": "BookA",
            "n_legs": 2, "estimated_odds": 4.0, "stake": 10,
            "legs": [{"event_id": f"ev-pe-open-{i}", "sport": "nba", "title": t, "selection": "home", "selection_text": s,
                      "start_utc": _iso(ko), "status": "active", "price": 2.0, "prob": 0.55,
                      "price_at": _iso(NOW - timedelta(minutes=30))} for i, (t, s, ko) in enumerate(later)]}
    html = _run({"data": _data([_rec("pe-open", legs=later)], recs=[live]), "now": _iso(NOW)})
    assert html.count('data-parlay="pe-open"') == 1 and recorded(html) == []
    assert 'data-kind="estimate"' in html


@needs_node
def test_empty_state_only_when_nothing_was_recorded_today():
    html = _run({"data": _data([_rec("pe-old", day=YESTERDAY)]), "now": _iso(NOW)})
    assert recorded(html) == [] and f"{pe.EMPTY_TEXT} <a" in html
    html = _run({"data": _data([]), "now": _iso(NOW)})
    assert f"{pe.EMPTY_TEXT} <a" in html


@needs_node
def test_history_page_lists_every_parlay_with_result_and_record():
    hist = [_rec("pe-today"),
            _rec("pe-lost", day=YESTERDAY, result="lost", paper_pl="-10.00", odds=8.0, leg_results=["won", "lost"]),
            _rec("pe-won", day=YESTERDAY, result="won", paper_pl="20.00", odds=3.0, leg_results=["won", "won"])]
    html = _run({"data": _data([], history=hist), "now": _iso(NOW), "hash": "#/history"})
    assert re.findall(r'data-ph="([^"]+)" data-result="([^"]+)"', html) == [
        ("pe-today", "open"), ("pe-lost", "lost"), ("pe-won", "won")]
    assert "<h2>Parlays</h2>" in html and "Record 1–1, paper P/L +$10.00" in html
    won = html[html.index('data-ph="pe-won"'):]
    assert "$10 bet pays <b>$30.00</b>" in won and "Paper P/L <b>+$20.00</b>" in won and "Thursday, November 12" in won
    assert html.count("Record uses $10 paper stakes") == 1                   # issue #78: said once, on History
    assert "BookA · 2 legs" in won and "T1A to win ✓" in won
    # Issue #65: record-by-size table sits in a card, adds a hit rate, colours P/L and ends in a Total row.
    assert '<div class="card ph-rec"><table data-ph-by-legs>' in html
    assert '<th scope="row">2 legs</th><td>1–0</td><td>100%</td><td>0</td><td>1</td><td class="pl pos">+$20.00</td>' in html
    assert '<th scope="row">3 legs</th><td>0–1</td><td>0%</td><td>0</td><td>0</td><td class="pl neg">−$10.00</td>' in html
    # Total row repeats the overall record line (1–1, +$10.00) and the overall open/void counts.
    assert '<tfoot><tr class="total"><th scope="row">Total</th><td>1–1</td><td>50%</td><td>0</td><td>1</td><td class="pl pos">+$10.00</td></tr></tfoot>' in html
    assert 'href="/' not in html and 'src="/' not in html            # relative paths only


# ---------- issue #76: editable, display-only bet amount on every parlay card ----------
def _live(pid, odds_legs=(2.0, 2.0)):
    later = [(f"L{i}H v L{i}A", f"L{i}H to win", NOW + timedelta(hours=1 + i)) for i in range(len(odds_legs))]
    return {"parlay_id": pid, "date": DAY, "status": "active", "kind": pe.ESTIMATE_KIND, "bookmaker": "BookA",
            "n_legs": len(later), "estimated_odds": round(odds_legs[0] * odds_legs[1], 4), "stake": 10,
            "legs": [{"event_id": f"ev-{pid}-{i}", "sport": "nba", "title": t, "selection": "home", "selection_text": s,
                      "start_utc": _iso(ko), "status": "active", "price": p, "prob": 0.55,
                      "price_at": _iso(NOW - timedelta(minutes=30))} for i, ((t, s, ko), p) in enumerate(zip(later, odds_legs))]}


def _payout(card):
    return re.search(r'data-payout>([^<]*)<', card).group(1)


@needs_node
def test_saved_bet_amount_drives_every_card_but_never_the_record():
    won = _rec("pe-w", result="won", paper_pl="30.00", leg_results=["won", "won"],
               legs=[("A v B", "A to win", NOW - timedelta(hours=4)), ("C v D", "C to win", NOW - timedelta(hours=3))])
    lost = _rec("pe-l", result="lost", paper_pl="-10.00", leg_results=["lost", "open"])
    hist = [won, lost]
    data = _data([_rec("pe-started"), won, lost], recs=[_live("pe-live")], history=hist)
    base = _run({"data": data, "now": _iso(NOW)})
    typed = _run({"data": data, "now": _iso(NOW), "storage": {"doyen.betAmount": "25"}})
    # Default $10 with nothing stored; the stored amount on every card's input and payout.
    assert _payout(_card(base, "pe-live")) == "$40.00" and _payout(_card(base, "pe-started")) == "$40.00"
    live, started = _card(typed, "pe-live"), _card(typed, "pe-started")
    assert 'value="25" data-stake' in live and _payout(live) == "$100.00"
    assert 'value="25" data-stake' in started and _payout(started) == "$100.00"
    w, lo = _card(typed, "pe-w"), _card(typed, "pe-l")
    assert _payout(w) == "Won: would have paid $100.00" and _payout(lo) == "Lost $25.00"
    # Issue #78: no card repeats the recorded $10 figures; they stay on History (checked below).
    for c in (live, started, w, lo):
        assert "Recorded" not in c and "bet pays" not in c and "Record uses $10 paper stakes" not in c
    # Footer record line and History P/L are identical with or without a stored amount.
    for page in ({"footer": True}, {"hash": "#/history"}):
        a = _run({"data": data, "now": _iso(NOW), **page})
        b = _run({"data": data, "now": _iso(NOW), "storage": {"doyen.betAmount": "25"}, **page})
        assert a == b
    hp = _run({"data": data, "now": _iso(NOW), "storage": {"doyen.betAmount": "25"}, "hash": "#/history"})
    assert "data-stake" not in hp and "$10 bet pays <b>$40.00</b>" in hp


@needs_node
@pytest.mark.parametrize("stored", ["0", "-3", "\"abc\"", "99999", "true", "not json"])
def test_bad_stored_bet_amount_falls_back_to_ten(stored):
    html = _run({"data": _data([_rec("pe-started")], recs=[_live("pe-live")]), "now": _iso(NOW),
                 "storage": {"doyen.betAmount": stored}})
    assert 'value="10" data-stake' in _card(html, "pe-live") and _payout(_card(html, "pe-started")) == "$40.00"


@needs_node
@pytest.mark.parametrize("value,result,want,saved", [
    ("25", None, "$100.00", "25"), ("25", "won", "Won: would have paid $100.00", "25"),
    ("25", "lost", "Lost $25.00", "25"), ("7.5", "void", "Void: $7.50 returned", "7.5"),
    ("12.345", None, "$49.40", "12.35"), ("0", None, "—", None), ("", "won", "—", None), ("20000", None, "—", None)])
def test_typing_on_open_and_ledger_cards_updates_payout_and_remembers_amount(value, result, want, saved):
    stake = {"value": value, "odds": 4.0, "dump": True, **({"result": result} if result else {})}
    out = json.loads(_run({"data": {}, "now": _iso(NOW), "stake": stake}))
    assert out["payout"] == want
    assert out["storage"].get("doyen.betAmount") == saved
