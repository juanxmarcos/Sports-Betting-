"""Issue #58: parlay previews for the next 3 New York days.

Previews use the same rules as today's estimated parlays, except that a price only has to be the
latest stored one and read before the game starts. They are replaced on every run, are never
written to the ledger, and are labelled as previews. Every price, game and team below is test data."""
import json
import re
from datetime import timedelta

import pytest

from sbi import config, site
from sbi import parlay_estimated as pe

from tests.test_parlay_estimated import (DAY, NOW, _store, _two_way, con, ecard, eblock, needs_node,  # noqa: F401
                                         render)

DAYS = ["2026-11-14", "2026-11-15", "2026-11-16"]


def _slate(con, prices=2.10, retrieved=None):
    """Two NBA games on today, +1 and +2 (New York); nothing priced on +3."""
    retrieved = retrieved or NOW - timedelta(minutes=20)
    for d in range(3):
        for i in (1, 2):
            _store(con, f"nba:{d}{i}", "nba", "NBA", NOW + timedelta(days=d, hours=4 + i), f"H{d}{i}", f"A{d}{i}",
                   _two_way(soft_home=prices), retrieved)
    _store(con, "nba:31", "nba", "NBA", NOW + timedelta(days=3, hours=5), "H31", "A31", {}, retrieved)   # no prices
    con.commit()


def test_preview_days_are_the_next_three_new_york_dates():
    assert pe.preview_days(NOW) == DAYS
    late = NOW.replace(hour=4, minute=30)                          # 23:30 New York on Nov 12
    assert pe.preview_days(late) == ["2026-11-13", "2026-11-14", "2026-11-15"]


def test_site_data_has_a_section_per_day_and_only_today_is_recorded(con):
    _slate(con)
    d = json.loads(site.build(con, NOW, write_shadow=True).read_text())
    e = d["estimated_parlays"]
    assert e["date"] == DAY and len(e["recommendations"]) == 1 and e["ledger_rows_added"] == 1
    assert [p["date"] for p in e["previews"]] == DAYS
    p1, p2, p3 = e["previews"]
    for p in (p1, p2):
        assert p["preview"] is True and p["status"] == "preview" and p["preview_badge"] == pe.PREVIEW_BADGE
        [r] = p["recommendations"]
        assert r["preview"] is True and r["preview_badge"] == "Preview: may change at the next daily update"
        assert r["date"] == p["date"] and r["prices_at"] == (NOW - timedelta(minutes=20)).isoformat()
        assert pe.card_problem(r, NOW, p["date"], preview=True) is None
        assert pe.card_problem(r, NOW, p["date"]) is not None    # never valid as today's card
    assert p3["recommendations"] == [] and p3["empty_text"] == "No preview yet for this day"
    assert "preview" not in e["recommendations"][0]
    rows = pe.ledger_path().read_text().splitlines()
    assert len(rows) == 2 and DAY in rows[1] and not any(day in rows[1] for day in DAYS)
    lite = json.loads((config.ROOT / "docs" / "data" / "parlays.json").read_text())
    assert lite["estimated_parlays"]["previews"] == e["previews"]


def test_rerun_with_new_prices_replaces_previews_without_touching_the_ledger(con):
    _slate(con)
    d1 = json.loads(site.build(con, NOW, write_shadow=True).read_text())["estimated_parlays"]
    ledger = pe.ledger_path().read_bytes()
    later = NOW + timedelta(hours=1)
    for d in (1, 2):                                               # a newer, different price on future games
        for i in (1, 2):
            con.execute("""INSERT INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,retrieved_at)
                           VALUES (?,?,?,?,?,?,?,?,?)""", (f"nba:{d}{i}", "Bet365", "ML", "home", None, 2.25, "pre", "x",
                                                         (later - timedelta(minutes=5)).isoformat()))
    con.commit()
    d2 = json.loads(site.build(con, later, write_shadow=True).read_text())["estimated_parlays"]
    assert d2["ledger_rows_added"] == 0 and pe.ledger_path().read_bytes() == ledger
    for a, b in zip(d1["previews"][:2], d2["previews"][:2]):
        assert a["recommendations"][0]["estimated_odds"] == pytest.approx(2.10 * 2.10)
        assert b["recommendations"][0]["estimated_odds"] == pytest.approx(2.25 * 2.25)


def test_preview_prices_may_be_older_than_today_but_never_after_the_start(con):
    old = NOW - timedelta(days=1)                                  # yesterday (New York)
    _slate(con, retrieved=old)
    b1 = pe.build_preview(con, NOW, DAYS[0])
    assert len(b1["recommendations"]) == 1                         # previews accept yesterday's latest price
    assert pe.build(con, NOW)["recommendations"] == []             # today keeps the same-day rule
    r = b1["recommendations"][0]
    bad = json.loads(json.dumps(r))
    bad["legs"][0]["price_at"] = bad["legs"][0]["start_utc"]
    assert pe.card_problem(bad, NOW + timedelta(days=2), DAYS[0], preview=True) is not None
    assert pe.card_problem(r, NOW, DAYS[1], preview=True) == "not this day's preview"


def test_on_its_own_day_a_preview_date_is_rebuilt_and_recorded_as_today(con):
    _slate(con)
    pid = pe.build_preview(con, NOW, DAYS[0])["recommendations"][0]["parlay_id"]
    tomorrow = NOW + timedelta(days=1, hours=-1)                   # 09:00 New York on Nov 14
    for i in (1, 2):                                               # that day's run re-reads the prices
        for bk, q in _two_way().get(("ML", None)).items():
            for sel, price in q.items():
                con.execute("""INSERT OR REPLACE INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,retrieved_at)
                               VALUES (?,?,?,?,?,?,?,?,?)""", (f"nba:1{i}", bk, "ML", sel, None, price, "pre", "x",
                                                             (tomorrow - timedelta(minutes=10)).isoformat()))
    con.commit()
    b = pe.build(con, tomorrow)
    [r] = b["recommendations"]
    assert r["date"] == DAYS[0] and "preview" not in r and r["parlay_id"] == pid
    assert pe.record(b, tomorrow) == 1


# ---------- rendered homepage ----------
def _previews(cards_by_day):
    return [{"status": "preview", "preview": True, "date": d, "kind": pe.ESTIMATE_KIND,
             "preview_badge": pe.PREVIEW_BADGE, "empty_text": pe.PREVIEW_EMPTY_TEXT, "recommendations": cards_by_day.get(d, [])}
            for d in DAYS]


def pcard(pid, day, **over):
    r = ecard(pid, prices=[1.9, 2.1])
    shift = timedelta(days=DAYS.index(day) + 1)
    for leg in r["legs"]:
        leg["start_utc"] = (NOW + timedelta(hours=3) + shift).isoformat()
        leg["event_id"] = f"{leg['event_id']}-{day}"
        leg["price_at"] = (NOW - timedelta(days=1)).isoformat()   # older than today: allowed for previews
    r.update(date=day, preview=True, preview_badge=pe.PREVIEW_BADGE, **over)
    return r


@needs_node
def test_home_day_switcher_shows_today_and_three_dated_days():
    html = render(eblock([ecard("pe-t")], previews=_previews({})))
    days = re.findall(r'data-day="([^"]+)">([^<]+)</button>', html)
    assert [d for d, _ in days] == [DAY] + DAYS
    assert [t for _, t in days] == ["Today · Fri, Nov 13", "Tomorrow · Sat, Nov 14", "+2 · Sun, Nov 15", "+3 · Mon, Nov 16"]
    assert 'class="on" data-f="hday" data-v="0"' in html and 'data-parlay="pe-t"' in html
    assert 'Past days' not in html and pe.PREVIEW_BADGE not in html


@needs_node
def test_home_preview_day_shows_badge_and_price_time():
    html = render(eblock([ecard("pe-t")], previews=_previews({DAYS[0]: [pcard("pe-p", DAYS[0])]})), hday="1")
    assert 'data-parlay="pe-p"' in html and 'data-parlay="pe-t"' not in html
    card = html[html.index("<article"):html.index("</article>")]
    assert f'<span class="pill preview">{pe.PREVIEW_BADGE}</span>' in card and "Estimate</span>" in card
    assert "check your book" not in card      # footnotes removed (owner, 2026-11-18)
    assert "Preview Parlays" in html and 'class="on" data-f="hday" data-v="1"' in html


@needs_node
def test_home_preview_day_without_prices_shows_the_empty_text():
    html = render(eblock([], previews=_previews({DAYS[0]: [pcard("pe-p", DAYS[0])]})), hday="3")
    assert "<article" not in html and f">{pe.PREVIEW_EMPTY_TEXT}</p>" in html
    html = render(eblock([]), hday="2")                            # an old data file with no previews
    assert f">{pe.PREVIEW_EMPTY_TEXT}</p>" in html


@needs_node
def test_browser_rejects_unmarked_or_misdated_previews():
    unmarked = pcard("pe-u", DAYS[0])
    unmarked.pop("preview")
    wrong_day = pcard("pe-w", DAYS[1])                             # in day 1's block but dated day 2
    late = pcard("pe-l", DAYS[0])
    late["legs"][0]["price_at"] = late["legs"][0]["start_utc"]
    html = render(eblock([], previews=_previews({DAYS[0]: [unmarked, wrong_day, late]})), hday="1")
    assert "<article" not in html and pe.PREVIEW_EMPTY_TEXT in html
    # A preview card never shows as today's card.
    x = pcard("pe-x", DAYS[0])
    x["date"] = DAY
    html = render(eblock([x]))
    assert 'data-parlay="pe-x"' not in html
