"""Issue #99: single picks under the owner-approved loosened rules, shown on the Today page.
Issue #112: new picks (`singles-v3`) use the typical price (median across 2+ bookmakers) and are
chosen by likelihood with typical odds >= 1.60.

Every price, game and team below is test data built for these tests, never a real quote. The
database tests use a temporary database; the browser tests run the real docs/assets/doyen.js."""
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sbi import config, db, engine, settle, site
from sbi import singles_loose as sl
from sbi.markets import Outcome

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tests" / "js" / "render_home.js"
NOW = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)          # 10:00 in New York
DAY = "2026-11-13"
needs_node = pytest.mark.skipif(not shutil.which("node") and not os.environ.get("CI"), reason="node is not installed")


@pytest.fixture
def con(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(config, "SITE_DIR", tmp_path / "site")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    return db.connect(tmp_path / "t.sqlite")


def _event(con, eid, ko, home, away, sport="nba", league="NBA"):
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""", (eid, sport, league, ko.isoformat(), home, away, "scheduled", "test", db.utcnow()))


def _odds(con, eid, bk, prices, at, market="ML", line=None):
    for sel, price in prices.items():
        con.execute("""INSERT INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,retrieved_at)
                       VALUES (?,?,?,?,?,?,?,?,?)""", (eid, bk, market, sel, line, price, "pre", "test", at.isoformat()))


def _model(con, eid, probs, at, market="ML"):
    run = f"test:{eid}"
    con.execute("INSERT OR IGNORE INTO model_runs VALUES (?,?,?,?,?,?,?)", (run, "test", "NBA", at.isoformat(), 0, "{}", at.isoformat()))
    for sel, p in probs.items():
        con.execute("""INSERT INTO predictions(run_id,event_id,market,selection,line,model_prob,created_at)
                       VALUES (?,?,?,?,?,?,?)""", (run, eid, market, sel, None, p, at.isoformat()))


def _game(con, i, *, hours=5, home_price=1.90, away_price=1.95, model_home=0.56, books=("Bet365", "DraftKings"),
          at=None):
    """One NBA game priced by `books` (same prices) with a Doyen model probability for the home side."""
    at = at or NOW - timedelta(minutes=30)
    eid = f"nba:{i}"
    _event(con, eid, NOW + timedelta(hours=hours), f"H{i}", f"A{i}")
    for bk in books:
        _odds(con, eid, bk, {"home": home_price, "away": away_price}, at)
    _model(con, eid, {"home": model_home, "away": 1 - model_home}, at)
    return eid


# ---------- issue #112: typical price, chosen by likelihood ----------
def test_typical_price_pick_is_published_under_the_new_rules_only(con):
    eid = f"nba:1"
    _event(con, eid, NOW + timedelta(hours=5), "H1", "A1")
    at = NOW - timedelta(minutes=30)
    for bk, home in (("Bet365", 1.88), ("DraftKings", 1.90), ("Unibet", 1.95)):
        _odds(con, eid, bk, {"home": home, "away": 1.95}, at)
    _model(con, eid, {"home": 0.56, "away": 0.44}, at)
    con.commit()
    s = sl.publish(con, NOW)
    assert s["published"] == 1 and s["rules_version"] == "singles-v3"
    [r] = con.execute("SELECT * FROM recommendations").fetchall()
    ev = json.loads(r["evidence_json"])
    assert r["event_id"] == eid and r["market"] == "ML" and r["selection"] == "home"
    # The typical price (median of 1.88 / 1.90 / 1.95), never one bookmaker's: no sportsbook is named.
    assert r["bookmaker"] == "consensus" and r["odds"] == pytest.approx(1.90)
    # Probability used = the #106 cap: at most the de-vigged market + 0.05 (model 0.56 is above it).
    assert r["final_prob"] < 0.56 and r["final_prob"] == pytest.approx(r["market_prob"] + 0.05)
    assert r["model_prob"] == pytest.approx(0.56) and r["published_at"] == NOW.isoformat()
    assert ev["rules_version"] == sl.RULES_VERSION and ev["price_basis"] == "consensus" and ev["n_bookmakers"] == 3
    assert ev["all_prices"] == {"Bet365": {"home": 1.88}, "DraftKings": {"home": 1.90}, "Unibet": {"home": 1.95}}
    assert ev["odds_note"] == sl.ODDS_NOTE and ev["raw_prob"] == pytest.approx(0.56)
    assert sl.is_loose(r) and sl.rules_version(r["evidence_json"]) == "singles-v3"
    assert r["model_version"] == "singles-v3:model"
    # A second run does not publish the same game twice.
    assert sl.publish(con, NOW + timedelta(minutes=10))["published"] == 0


def test_kept_screens_minimum_odds_and_two_bookmakers(con):
    _game(con, 1, home_price=1.50, away_price=2.60, model_home=0.70)   # likely, but 1.50 < 1.60; away: model below
    _game(con, 2, home_price=1.20, model_home=0.90)       # outside the 0.30-0.85 band
    _game(con, 3, home_price=2.40, model_home=0.62)       # model 0.62 vs market ~0.45: disagreement > 0.12
    _game(con, 4, at=NOW - timedelta(hours=16))           # priced yesterday (New York): not same-day
    _game(con, 5, hours=-1)                               # already started
    _game(con, 6, books=("Bet365",))                      # one bookmaker: no typical price
    con.commit()
    s = sl.publish(con, NOW)
    assert s["published"] == 0
    assert s["excluded"].get("typical odds below 1.60") == 1


def test_no_value_is_required_at_the_typical_price(con):
    # 0.50 at 1.90: estimated value is negative (the margin is in the typical price), yet it is a pick.
    _game(con, 1, home_price=1.90, away_price=1.90, model_home=0.50)
    con.commit()
    assert sl.publish(con, NOW)["published"] == 1
    r = con.execute("SELECT * FROM recommendations").fetchone()
    assert r["ev"] < 0 and r["odds"] == pytest.approx(1.90)


def test_an_open_injury_note_does_not_exclude_the_pick_and_is_stored(con):
    eid = _game(con, 1)
    con.execute("""INSERT INTO research_notes(event_id,category,claim,evidence_type,created_at)
                   VALUES (?,'injury','H1 starting guard out','verified_fact',?)""", (eid, NOW.isoformat()))
    con.commit()
    assert sl.publish(con, NOW)["published"] == 1
    ev = json.loads(con.execute("SELECT evidence_json FROM recommendations").fetchone()[0])
    assert ev["risk_note"] == "Injury/lineup note open: H1 starting guard out"


def test_at_most_one_pick_per_game_and_five_per_day_most_likely_first(con):
    # Game 1 offers the moneyline and a total: still one pick for that game.
    eid = _game(con, 1, home_price=2.00, model_home=0.55)
    for bk in ("Bet365", "DraftKings"):
        _odds(con, eid, bk, {"over": 2.10, "under": 1.75}, NOW - timedelta(minutes=30), market="TOTAL", line=220.5)
    for i in range(2, 9):                                 # 7 more games, likelihood rising with i
        _game(con, i, home_price=1.90, model_home=0.49 + 0.008 * i)
    con.commit()
    s = sl.publish(con, NOW)
    rows = con.execute("SELECT event_id, market, selection, final_prob, rank FROM recommendations ORDER BY rank").fetchall()
    assert s["published"] == 5 and len(rows) == 5
    assert len({r["event_id"] for r in rows}) == 5
    assert [r["final_prob"] for r in rows] == sorted((r["final_prob"] for r in rows), reverse=True)
    assert [r["event_id"] for r in rows] == ["nba:8", "nba:1", "nba:7", "nba:6", "nba:5"]
    # Game 1's most likely selection at 1.60 or longer is the total's under (market ~0.549 at 1.75).
    g1 = next(r for r in rows if r["event_id"] == "nba:1")
    assert (g1["market"], g1["selection"]) == ("TOTAL", "under")
    # The day is full: a later run adds nothing for today, even with a new game.
    _game(con, 9, home_price=2.20, model_home=0.55)
    con.commit()
    assert sl.publish(con, NOW + timedelta(hours=1))["published"] == 0


def test_published_picks_stay_immutable_and_old_picks_keep_their_rules(con):
    _game(con, 1)
    # An old pick (no rules_version) on another game, published before #99.
    _event(con, "nba:old", NOW + timedelta(hours=3), "OH", "OA")
    con.execute("""INSERT INTO recommendations(rec_id,event_id,published_at,sport,league,kickoff_utc,home,away,market,selection,
                   line,bookmaker,odds,model_prob,final_prob,fair_odds,ev,ev_lower,stake_units,model_version,evidence_json)
                   VALUES ('old1','nba:old',?,'nba','NBA',?,'OH','OA','ML','home',NULL,'Pinnacle',2.0,0.55,0.55,1.82,0.1,0.05,1,
                   'nba-x','{}')""", ((NOW - timedelta(days=1)).isoformat(), (NOW + timedelta(hours=3)).isoformat()))
    con.commit()
    before = [tuple(r) for r in con.execute("SELECT * FROM recommendations WHERE rec_id='old1'")]
    sl.publish(con, NOW)
    assert [tuple(r) for r in con.execute("SELECT * FROM recommendations WHERE rec_id='old1'")] == before
    old = con.execute("SELECT * FROM recommendations WHERE rec_id='old1'").fetchone()
    assert sl.rules_version(old["evidence_json"]) == "singles-v1" and not sl.is_loose(old)
    new = con.execute("SELECT rec_id FROM recommendations WHERE rec_id != 'old1'").fetchone()[0]
    import sqlite3
    with pytest.raises(sqlite3.DatabaseError):
        con.execute("UPDATE recommendations SET odds=9.9 WHERE rec_id=?", (new,))
    with pytest.raises(sqlite3.DatabaseError):
        con.execute("DELETE FROM recommendations WHERE rec_id=?", (new,))


def test_reassessment_leaves_loosened_picks_active_until_the_start(con):
    _game(con, 1)
    con.commit()
    sl.publish(con, NOW)
    settle.reassess_open(con, NOW + timedelta(minutes=5))
    rid = con.execute("SELECT rec_id FROM recommendations").fetchone()[0]
    assert con.execute("SELECT COUNT(*) FROM rec_updates WHERE rec_id=?", (rid,)).fetchone()[0] == 0
    settle.reassess_open(con, NOW + timedelta(hours=6))
    assert [r[0] for r in con.execute("SELECT status FROM rec_updates WHERE rec_id=?", (rid,))] == ["expired"]


def test_site_block_has_todays_picks_previews_and_the_new_rules_record(con):
    _game(con, 1)
    _game(con, 2, hours=29)                               # tomorrow (New York): a preview, not published
    con.commit()
    sl.publish(con, NOW)
    d = json.loads(site.build(con, NOW).read_text())
    g = d["singles"]
    assert g["rules_version"] == "singles-v3" and g["date"] == DAY and g["max_per_day"] == 5
    assert g["min_odds"] == 1.6 and g["odds_note"] == sl.ODDS_NOTE
    [p] = g["days"][DAY]
    assert p["event_id"] == "nba:1" and p["odds"] == 1.90 and p["rules_version"] == "singles-v3"
    assert p["price_basis"] == "consensus" and "bookmaker" not in p
    assert p["status"]["state"] == "active" and p["market"] == "Moneyline" and p["selection"] == "H1 to win"
    [prev] = [x for x in g["previews"] if x["date"] == "2026-11-14"]
    [pv] = prev["recommendations"]
    assert pv["preview"] is True and pv["event_id"] == "nba:2" and pv["price_basis"] == "consensus"
    assert "bookmaker" not in pv and pv["price_books"] == 2
    assert con.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0] == 1     # previews never published
    assert g["record"]["picks"] == 1 and g["record"]["open"] == 1
    lite = json.loads((config.ROOT / "docs" / "data" / "parlays.json").read_text())
    assert lite["singles"] == g
    [h] = d["history"]
    assert h["rules_version"] == "singles-v3" and "Typical odds 1.90" in h["why"] and "median across 2 sportsbooks" in h["why"]
    assert h["bookmaker"] == "Typical odds" and h["price_basis"] == "consensus"


# ---------- browser ----------
def _run(payload):
    out = subprocess.run(["node", str(HARNESS)], input=json.dumps(payload), capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout


def _pick(i, hours=5, **over):
    p = {"id": f"s{i}", "event_id": f"nba:{i}", "sport": "nba", "competition": "NBA", "title": f"H{i} v A{i}",
         "start_utc": (NOW + timedelta(hours=hours)).isoformat(), "published_at": (NOW - timedelta(hours=1)).isoformat(),
         "market": "Moneyline", "selection": f"H{i} to win", "odds": 2.5, "bookmaker": "Bet365",
         "price_at": (NOW - timedelta(hours=1)).isoformat(), "rules_version": "singles-v2",
         "status": {"state": "active", "label": "Active"}}
    p.update(over)
    return p


def _render(singles, **extra):
    data = {"generated": NOW.isoformat(), "default_timezone": "America/New_York",
            "parlays": {"date": DAY, "status": "not_published", "blockers": [{"key": "x", "text": "x"}], "recommendations": []},
            "estimated_parlays": {"status": "estimated", "kind": "estimated_product", "date": DAY, "recommendations": []},
            "singles": singles, "picks": [], "history": [], "events": [], "watching": [], "close_to_value": [],
            "briefing": {}, "funnel_7d": {}, "sports": {}, "record": {"won": 0, "lost": 0, "push": 0, "profit_units": 0, "open": 0}}
    return _run({"data": data, "now": NOW.isoformat(), **extra})


def _block(today=None, previews=None):
    return {"rules_version": "singles-v2", "date": DAY, "days": {DAY: today or []}, "previews": previews or []}


@needs_node
def test_today_page_shows_single_picks_below_the_parlays():
    won = _pick(2, hours=-3, odds=1.8, status={"state": "settled", "label": "Won", "result": "won", "pnl": 0.8})
    html = _render(_block([_pick(1, risk_note="Injury/lineup note open: H1 guard out"), won]))
    assert html.index('id="parlays"') < html.index('id="singles"') and "<h2>Single picks</h2>" in html
    cards = re.findall(r'<article class="card parlay single" data-single="([^"]+)"', html)
    assert cards == ["s2", "s1"]                                  # earliest start first
    c1 = html[html.index('data-single="s1"'):]
    c1 = c1[:c1.index("</article>")]
    assert "+150 (2.50)" in c1 and "$25.00" in c1 and "H1 to win" in c1 and "Moneyline" in c1 and "NBA" in c1
    assert "Open: starts at" in c1 and "Injury/lineup note open: H1 guard out" in c1 and 'value="10"' in c1
    c2 = html[html.index('data-single="s2"'):]
    c2 = c2[:c2.index("</article>")]
    assert "-125 (1.80)" in c2 and 'data-result="won"' in c2 and "Won: would have paid $18.00" in c2


@needs_node
def test_single_cards_name_no_bookmaker_and_label_typical_odds():
    """Issue #112: no bookmaker on single cards; a typical-price pick says "Typical odds" plus one muted line."""
    typical = _pick(1, odds=1.75, rules_version="singles-v3", price_basis="consensus")
    typical.pop("bookmaker")
    html = _render(_block([typical, _pick(2, hours=6)]))
    c1 = html[html.index('data-single="s1"'):]
    c1 = c1[:c1.index("</article>")]
    assert '<div class="k">Typical odds</div>' in c1 and "-133 (1.75)" in c1
    c2 = html[html.index('data-single="s2"'):]
    c2 = c2[:c2.index("</article>")]
    assert '<div class="k">Odds</div>' in c2                       # a singles-v2 pick was priced at one book
    assert "Bet365" not in html and "consensus" not in html.replace("data-", "")
    assert html.count("data-odds-note") == 1 and "your sportsbook&#39;s price may differ slightly" in html


@needs_node
def test_today_page_says_so_when_there_are_no_single_picks():
    html = _render(_block())
    assert "<h2>Single picks</h2>" in html and "No single picks today." in html


@needs_node
def test_preview_tab_shows_that_days_singles_with_preview_wording():
    day = "2026-11-14"
    pv = _pick(3, hours=29, id="preview:x", preview=True, status={"state": "preview", "label": "Preview"})
    html = _render(_block(previews=[{"date": day, "recommendations": [pv]}]), hday="1")
    assert 'data-singles-day="2026-11-14"' in html and 'data-single="preview:x"' in html
    assert "Preview: may change at the next daily update" in html and "may change at the next daily update" in html
    # A preview dated for another day is not shown, and an empty preview day says so.
    html = _render(_block(previews=[{"date": day, "recommendations": [pv]}]), hday="2")
    assert "data-single=" not in html and "No single picks for this day yet." in html


def test_top_menu_has_no_single_picks_tab_and_the_route_still_exists():
    index = (ROOT / "docs" / "index.html").read_text()
    nav = index[index.index('<nav class="nav"'):index.index("</nav>")]
    assert "Single picks" not in nav and "#/picks" not in nav and "Today" in nav and "History" in nav
    js = (ROOT / "docs" / "assets" / "doyen.js").read_text()
    assert 'r === "picks") html = picksView()' in js


@needs_node
def test_history_shows_the_record_since_the_loosened_rules():
    old = _pick(5, hours=-48, rules_version="singles-v1", published_at=(NOW - timedelta(days=3)).isoformat(),
                status={"state": "settled", "label": "Lost", "result": "lost", "pnl": -1})
    new = _pick(6, hours=-3, status={"state": "settled", "label": "Won", "result": "won", "pnl": 1.5})
    data_hist = [old, new]
    data = {"generated": NOW.isoformat(), "default_timezone": "America/New_York", "parlays": {}, "estimated_parlays": {},
            "singles": _block(), "picks": [], "history": data_hist, "events": [], "watching": [], "close_to_value": [],
            "parlay_history": [], "briefing": {}, "funnel_7d": {}, "sports": {},
            "record": {"won": 1, "lost": 1, "push": 0, "profit_units": 0.5, "open": 0}}
    html = _run({"data": data, "now": NOW.isoformat(), "hash": "#/history"})
    assert "data-singles-by-sport" in html
    line = re.search(r"<p class=\"small muted\" data-singles-v2>(.*?)</p>", html).group(1)
    assert "Since the loosened rules" in line and "1–0" in line and "+1.50 u" in line
    assert "data-singles-v3" not in html                          # no typical-odds picks yet
    data["history"] = data_hist + [_pick(7, hours=-2, rules_version="singles-v3",
                                         status={"state": "settled", "label": "Lost", "result": "lost", "pnl": -1})]
    html = _run({"data": data, "now": NOW.isoformat(), "hash": "#/history"})
    line = re.search(r"<p class=\"small muted\" data-singles-v3>(.*?)</p>", html).group(1)
    assert "Since typical odds" in line and "0–1" in line
