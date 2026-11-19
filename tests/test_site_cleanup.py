"""Issue #98: cache-busting, leg result badges, "see tomorrow" link, yesterday's results line and a
simpler Eastern-time-only footer. Every game, price and bookmaker below is test data, never a real quote.
The browser tests run the real docs/assets/doyen.js in Node."""
import json
import re
import shutil
from datetime import timedelta
from pathlib import Path

from sbi import config, site

from tests.test_parlay_history import (DAY, NOW, YESTERDAY, _card, _data, _fixture, _iso, _rec, _run, con,  # noqa: F401
                                       needs_node)
from tests.test_parlay_previews import DAYS, _previews, pcard

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "docs" / "index.html"


def _footer(html):
    return html[html.index("<footer"):html.index("</footer>")]


# ---------- 5. simpler footer, Eastern time only ----------
def test_footer_has_no_timezone_select_and_only_two_links():
    f = _footer(INDEX.read_text())
    assert "<select" not in f and 'id="tz"' not in f
    assert re.findall(r"<a [^>]*>([^<]+)</a>", f) == ["Methodology", "Parlay rules"]
    for gone in ("Upcoming", "Watchlist", "Ask Doyen", "Diagnostics"):
        assert gone not in f
    assert 'id="updated"' in f and "Please gamble responsibly" in f       # disclaimer and "Updated" stay
    js = (ROOT / "docs" / "assets" / "doyen.js").read_text()
    assert "tzSelect" not in js and 'store.get("tz"' not in js


@needs_node
def test_times_are_eastern_even_with_an_old_saved_timezone():
    later = [("T3H v T3A", "T3H to win", NOW + timedelta(hours=1)), ("T4H v T4A", "T4H to win", NOW + timedelta(hours=2))]
    html = _run({"data": _data([_rec("pe-open", legs=later)]), "now": _iso(NOW),
                 "storage": {"doyen.tz": json.dumps("Europe/London")}})
    card = _card(html, "pe-open")
    assert re.search(r"Open: first game at 7:00\sPM", card) and re.search(r"lg-when\">7:00\sPM<", card)


@needs_node
def test_old_routes_stay_reachable_by_url():
    for h in ("#/upcoming", "#/watchlist", "#/ask"):
        assert _run({"data": _data([]), "now": _iso(NOW), "hash": h}).strip()


# ---------- 2. leg result badges ----------
@needs_node
def test_leg_results_are_badges_apart_from_the_time():
    legs = [(f"G{i}H v G{i}A", f"G{i}H to win", NOW - timedelta(hours=3 - i)) for i in range(4)]
    legs.append(("G9H v G9A", "G9H to win", NOW + timedelta(hours=1)))
    r = _rec("pe-mix", legs=legs, leg_results=["won", "lost", "void", "push", "open"])
    r2 = _rec("pe-pend", leg_results=["open", "open"])                    # first leg started an hour ago
    html = _run({"data": _data([r, r2]), "now": _iso(NOW)})
    marks = re.findall(r'data-leg-result="(\w+)"[^>]*>([^<]+)<', _card(html, "pe-mix"))
    assert marks == [("won", "✓"), ("lost", "✗"), ("void", "void"), ("push", "push")]   # nothing before kickoff
    assert re.findall(r'data-leg-result="(\w+)"[^>]*>([^<]+)<', _card(html, "pe-pend")) == [("pending", "⏳")]
    for c in (_card(html, "pe-mix"), _card(html, "pe-pend")):
        assert ">pending<" not in c
        for t in re.findall(r'class="lg-when">([^<]*)<', c):
            assert re.fullmatch(r"\d{1,2}:\d\d\s[AP]M", t)                # the time text alone


# ---------- 3. "see tomorrow" link ----------
NEXT = re.compile(r'data-next-day="(\d)">All of today\'s parlays have started\. '
                  r'<button class="linkbtn" data-f="hday" data-v="(\d)">See ([^<]+) →</button>')


@needs_node
def test_see_tomorrow_shows_only_when_no_parlay_is_open():
    started = _rec("pe-s")                                                # first leg started
    settled = _rec("pe-w", result="won", paper_pl="30.00", leg_results=["won", "won"])
    html = _run({"data": _data([started, settled]), "now": _iso(NOW)})
    assert NEXT.findall(html) == [("1", "1", "tomorrow's")]
    i = html.index("data-next-day")
    assert i < html.index('data-parlay="pe-s"')                           # above the cards
    later = [("T3H v T3A", "T3H to win", NOW + timedelta(hours=1)), ("T4H v T4A", "T4H to win", NOW + timedelta(hours=2))]
    html = _run({"data": _data([started, _rec("pe-open", legs=later)]), "now": _iso(NOW)})
    assert "data-next-day" not in html
    assert "data-next-day" not in _run({"data": _data([]), "now": _iso(NOW)})   # nothing today: the empty text


@needs_node
def test_see_tomorrow_points_to_the_next_day_with_previews_and_switches_to_it():
    data = _data([_rec("pe-s")])
    data["estimated_parlays"]["previews"] = _previews({DAYS[1]: [pcard("pe-p", DAYS[1])]})
    html = _run({"data": data, "now": _iso(NOW)})
    assert NEXT.findall(html) == [("2", "2", "Sun, Nov 15's")]
    html = _run({"data": data, "now": _iso(NOW), "hday": "2"})            # the link's data-f/data-v click
    assert 'data-preview-day="2026-11-15"' in html and 'data-parlay="pe-p"' in html


# ---------- 4. yesterday's results line ----------
def _yline(html):
    m = re.search(r"<p class=\"yday\" data-yesterday>([^<]+)</p>", html)
    return m and m.group(1)


@needs_node
def test_yesterday_line_matches_the_ledger(con):
    _fixture(con)                     # yesterday: won 2-leg (+$20.00) and lost 3-leg (−$10.00); today: one open
    site.build(con, NOW)
    lite = json.loads((config.ROOT / "docs" / "data" / "parlays.json").read_text())
    rows = lite["estimated_parlays"]["ledger_yesterday"]
    assert sorted(r["parlay_id"] for r in rows) == ["pe-lost", "pe-won"] and {r["date"] for r in rows} == {YESTERDAY}
    html = _run({"data": lite, "now": _iso(NOW)})
    assert _yline(html) == "Yesterday: 1 of 2 parlays won · +$10.00 (paper, $10 each)"
    assert html.index("data-yesterday") < html.index('class="seg days"')   # under the title


@needs_node
def test_yesterday_line_counts_open_and_void_and_hides_when_empty():
    y = NOW - timedelta(days=1)
    old = [("A v B", "A to win", y), ("C v D", "C to win", y)]
    rows = [_rec("y1", day=YESTERDAY, legs=old, result="lost", paper_pl="-10.00", leg_results=["lost", "won"]),
            _rec("y2", day=YESTERDAY, legs=old, result="void", leg_results=["void", "won"]),
            _rec("y3", day=YESTERDAY, legs=old)]
    data = _data([])
    data["estimated_parlays"]["ledger_yesterday"] = rows
    assert _yline(_run({"data": data, "now": _iso(NOW)})) == \
        "Yesterday: 0 of 1 parlay won · −$10.00 (paper, $10 each) · 1 void · 1 still open"
    data["estimated_parlays"]["ledger_yesterday"] = [rows[2]]
    assert _yline(_run({"data": data, "now": _iso(NOW)})) == "Yesterday: 1 parlay, still open"
    data["estimated_parlays"]["ledger_yesterday"] = [_rec("old", day="2026-11-11", legs=old, result="won", paper_pl="30.00")]
    assert _yline(_run({"data": data, "now": _iso(NOW)})) is None         # not yesterday: hidden
    data["estimated_parlays"].pop("ledger_yesterday")
    assert "data-yesterday" not in _run({"data": data, "now": _iso(NOW)})


# ---------- 1. cache-busting ----------
def _site(tmp):
    (tmp / "docs" / "assets").mkdir(parents=True)
    shutil.copy(INDEX, tmp / "docs" / "index.html")
    for n in ("doyen.css", "doyen.js"):
        shutil.copy(ROOT / "docs" / "assets" / n, tmp / "docs" / "assets" / n)
    return tmp / "docs" / "index.html"


def _versions(html):
    return dict(re.findall(r'"(assets/doyen\.(?:css|js))\?v=([0-9a-f]+)"', html))


def test_index_references_versioned_assets_and_the_version_changes_each_build(con):
    assert set(re.findall(r'"(assets/doyen\.(?:css|js))\?v=[\w-]+"', INDEX.read_text())) == {"assets/doyen.css", "assets/doyen.js"}
    index = _site(config.ROOT)
    site.build(con, NOW)
    v1 = _versions(index.read_text())
    assert set(v1) == {"assets/doyen.css", "assets/doyen.js"} and len(set(v1.values())) == 1
    site.build(con, NOW + timedelta(minutes=5))                           # a later run: new `generated`
    v2 = _versions(index.read_text())
    assert set(v2) == set(v1) and set(v2.values()) != set(v1.values())
    html = index.read_text()
    assert html.count("?v=") == 2 and 'href="assets/doyen.css?v=' in html and 'src="assets/doyen.js?v=' in html  # relative paths
    assert site.stamp_assets(config.ROOT / "missing.html", "x") is None   # no index: nothing to do


@needs_node
def test_data_fetches_reuse_the_build_id_from_the_script_tag():
    out = _run({"data": _data([]), "now": _iso(NOW), "fetched": True, "scriptSrc": "https://x.test/assets/doyen.js?v=abc123"})
    assert json.loads(out) == ["data/parlays.json?v=abc123"]
    assert json.loads(_run({"data": _data([]), "now": _iso(NOW), "fetched": True})) == ["data/parlays.json"]
