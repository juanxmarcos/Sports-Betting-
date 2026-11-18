"""Issue #84: a readable competition name on every bet (parlay legs and single picks).

Display mapping only. Teams, prices and games below are test data, never real quotes."""
import json
from shutil import which as shutil_which
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sbi import competitions
from sbi.competitions import competition_name, label

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tests" / "js" / "render_home.js"
NOW = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)          # 10:00 in New York
DAY = "2026-11-13"


# ---------- mapping ----------
@pytest.mark.parametrize("league,want", [
    ("E0", "Premier League"), ("E1", "Championship (England)"), ("SP1", "La Liga"), ("D1", "Bundesliga"),
    ("I1", "Serie A"), ("F1", "Ligue 1"), ("N1", "Eredivisie"), ("P1", "Primeira Liga"),
    ("B1", "Belgian Pro League"), ("SC0", "Scottish Premiership"), ("NBA", "NBA"), ("NFL", "NFL"),
    ("INT:uefa.nations", "UEFA Nations League"), ("INT:fifa.friendly", "FIFA Friendly"),
    ("INT:caf.nations_qual", "AFCON Qualifying"), ("INT:concacaf.nations.league", "CONCACAF Nations League"),
    ("TENNIS:ATP", "ATP"), ("TENNIS:WTA", "WTA"),
])
def test_league_codes_map_to_readable_names(league, want):
    assert competition_name(league) == want


def test_tennis_uses_the_tournament_and_keeps_the_tour_when_the_name_lacks_it():
    assert competition_name("TENNIS:ATP", "ATP · Nitto ATP Finals · Final") == "Nitto ATP Finals"
    assert competition_name(None, "ATP · Bybit Stockholm Open · Round 1", "tennis:ATP:20261020:1") == \
        "ATP · Bybit Stockholm Open"
    assert competition_name(None, None, "tennis:WTA:20261125:186833") == "WTA"


def test_event_id_gives_the_league_when_the_leg_has_none():
    assert competition_name(event_id="football:E0:20261123:brentford:everton") == "Premier League"
    assert competition_name(event_id="football:INT:uefa.nations:20261117:401861193") == "UEFA Nations League"
    assert competition_name(event_id="nba:NBA:20261118:401910003") == "NBA"


def test_unknown_codes_fall_back_to_the_raw_name_never_blank():
    assert competition_name("XYZ9") == "XYZ9"
    assert competition_name("INT:some.cup") == "some.cup"
    assert competition_name("XYZ9", "Some Cup") == "Some Cup"
    assert competition_name("NBA", "NBA Playoffs") == "NBA Playoffs"
    assert competition_name(event_id="nba:1") == ""                 # nothing known: no invented name
    leg = label({"event_id": "nba:1", "title": "A v B", "league": "QQ"})
    assert leg["competition_name"] == "QQ"


def test_every_league_in_the_database_maps_to_a_readable_name():
    path = ROOT / "data" / "sbi.sqlite"
    assert path.exists(), "data/sbi.sqlite is tracked in the repository"
    con = sqlite3.connect(path)
    leagues = [r[0] for r in con.execute("SELECT DISTINCT league FROM events")]
    assert leagues
    for lg in leagues:
        name = competition_name(lg)
        mapped = lg in competitions.LEAGUE_NAMES or (lg.startswith("INT:") and (
            lg[4:] in competitions.INT_DISPLAY or lg[4:] in competitions.INT_COMPETITIONS))
        assert mapped and name and name != lg[4:], lg                # in the mapping, not the raw code


def test_label_all_sets_names_and_never_edits_other_fields():
    block = {"recommendations": [{"parlay_id": "p", "legs": [
        {"event_id": "nba:NBA:1", "title": "A v B", "league": "NBA", "price": 1.9},
        {"event_id": "football:E0:x", "title": "C v D", "league": "E0", "price": 2.0}]}]}
    before = json.loads(json.dumps(block))
    competitions.label_all(block)
    legs = block["recommendations"][0]["legs"]
    assert [x["competition_name"] for x in legs] == ["NBA", "Premier League"]
    for a, b in zip(legs, before["recommendations"][0]["legs"]):
        assert {k: v for k, v in a.items() if k != "competition_name"} == b
    hist = [{"event_id": "tennis:ATP:2026:1", "title": "P v Q"}]
    competitions.label_all(hist, {"tennis:ATP:2026:1": "ATP · Nitto ATP Finals · Group Stage"})
    assert hist[0]["competition_name"] == "Nitto ATP Finals"


# ---------- rendered site (real docs/assets/doyen.js in Node) ----------
def _iso(dt):
    return dt.isoformat()


def _legs(pid, started=False):
    base = NOW - timedelta(hours=1) if started else NOW + timedelta(hours=3)
    legs = [{"event_id": f"nba:NBA:{pid}", "sport": "nba", "league": "NBA", "title": "Home 0 v Away 0"},
            {"event_id": f"football:E0:{pid}", "sport": "soccer", "league": "E0", "title": "Home 1 v Away 1"}]
    for i, (leg, p) in enumerate(zip(legs, (1.9, 2.1))):
        leg.update(market="ML", selection="home", selection_text=f"Home {i} to win", status="active", price=p,
                   prob=round(1 / p + 0.01, 4), prob_source="model", start_utc=_iso(base + timedelta(minutes=i)),
                   price_at=_iso(NOW - timedelta(minutes=30)), result="open")
    return legs


def _data():
    rec = {"parlay_id": "pe-c", "date": DAY, "status": "active", "kind": "estimated_product", "badge": "Estimate",
           "bookmaker": "BookA", "n_legs": 2, "estimated_odds": 3.99, "stake": 10, "est_hit_chance": 0.3,
           "legs": _legs("c")}
    led = {"parlay_id": "pe-l", "date": DAY, "first_seen": _iso(NOW - timedelta(hours=2)), "kind": "estimated_product",
           "bookmaker": "BookA", "n_legs": 2, "estimated_odds": 3.99, "stake": "10.00", "gross_payout": "39.90",
           "result": "open", "paper_pl": "0.00", "legs": _legs("l", started=True)}
    pick = {"id": "r1", "event_id": "football:E0:r1", "sport": "soccer", "competition": "England Premier League",
            "title": "Home 9 v Away 9", "start_utc": _iso(NOW + timedelta(hours=4)),
            "published_at": _iso(NOW - timedelta(hours=3)), "market": "Match result", "selection": "Home 9 to win",
            "odds": 2.1, "bookmaker": "Book", "prob": 0.5, "fair_odds": 2.0, "ev": 0.05, "why_short": "x",
            "stale": False, "status": {"state": "active", "label": "Active"}}
    est = {"status": "estimated", "kind": "estimated_product", "date": DAY, "recommendations": [rec],
           "ledger_today": [led], "record": {"rows": 1, "won": 0, "lost": 0, "void": 0, "open": 1, "paper_pl": "0.00"}}
    strict = {"date": DAY, "status": "not_published", "blockers": [{"key": "combined_quote", "text": "x"}],
              "recommendations": []}
    data = {"generated": _iso(NOW), "default_timezone": "America/New_York", "parlays": strict,
            "estimated_parlays": est, "parlay_history": [led], "picks": [pick], "history": [pick], "events": [],
            "watching": [], "close_to_value": [], "briefing": {}, "funnel_7d": {}, "sports": {},
            "record": {"won": 0, "lost": 0, "push": 0, "profit_units": 0, "open": 1}}
    for k in ("picks", "history", "estimated_parlays", "parlay_history"):
        competitions.label_all(data[k])
    return data


def _run(hash_=""):
    assert shutil_which("node"), "node is required for the site render tests"
    payload = {"data": _data(), "now": _iso(NOW), "hash": hash_}
    out = subprocess.run(["node", str(HARNESS)], input=json.dumps(payload), capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout


def _card(html, pid):
    i = html.index(f'data-parlay="{pid}"')
    return html[i:html.index("</article>", i)]


def test_card_with_an_nba_and_a_premier_league_leg_shows_both_competitions():
    html = _run()
    for pid in ("pe-c", "pe-l"):                                   # today's card and the started ledger card
        card = _card(html, pid)
        assert '<span class="lg-c" data-comp>NBA</span>Home 0 vs. Away 0' in card
        assert '<span class="lg-c" data-comp>Premier League</span>Home 1 vs. Away 1' in card


def test_history_and_single_picks_show_the_competition():
    html = _run("#/history")
    assert '<span class="ph-c" data-comp>NBA · </span>Home 0 vs. Away 0' in html
    assert '<span class="ph-c" data-comp>Premier League · </span>Home 1 vs. Away 1' in html
    assert '<span data-comp>Premier League · Home 9 to win</span>' in html
    picks = _run("#/picks")
    assert "PREMIER LEAGUE ·" in picks and "England Premier League" not in picks
