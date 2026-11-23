"""Issue #107: History shows expected vs actual wins for parlays (by size), parlay legs (a "behind
expectation" line by market) and single picks (by sport).

Every game, price, probability and pick below is test data built for these tests, never a real
recommendation. Database tests use a temporary database; browser tests run the real
docs/assets/doyen.js with node."""
import re
from datetime import timedelta

import pytest

from sbi import parlay_estimated as pe
from tests import test_parlay_history as ph
from tests import test_singles_table as st
from tests.test_parlay_markets import NOW, _event, _leg, _write_ledger, con  # noqa: F401


# ---------- data: per-size and per-market expected wins ----------
def test_settle_sums_expected_wins_per_size_and_per_market(con):  # noqa: F811
    _event(con, "g1", "Arsenal", "Chelsea", NOW - timedelta(hours=3), "finished", 2, 0)   # home win, 2 goals
    _event(con, "g2", "Leeds", "Fulham", NOW - timedelta(hours=3), "finished", 1, 1)      # draw, 2 goals
    _event(con, "g3", "Spurs", "Wolves", NOW + timedelta(hours=3))                        # not played yet
    con.commit()
    a = dict(_leg("g1", "1X2", "H", 1.8), prob=0.55)
    b = dict(_leg("g2", "OU", "over", 1.9, 2.5, "Leeds v Fulham"), prob=0.52)
    c = dict(_leg("g2", "1X2", "D", 3.4, title="Leeds v Fulham"), prob=0.3)
    d = dict(_leg("g3", "OU", "over", 1.9, 2.5, "Spurs v Wolves"), prob=0.5)
    _write_ledger([("pe-a", [a, b], 3.42), ("pe-b", [a, c], 6.12), ("pe-c", [a, c, d], 11.6)])
    s = pe.settle(con)
    # pe-a lost (under), pe-b won, pe-c open: every row records est_hit_chance 0.3
    assert (s["won"], s["lost"], s["open"]) == (1, 1, 1)
    assert s["by_legs"]["2"]["expected_wins_settled"] == pytest.approx(0.6)
    assert s["by_legs"]["3"]["expected_wins_settled"] == 0.0                # open rows add nothing
    assert s["expected_wins_settled"] == pytest.approx(0.6)
    # Legs: 1X2 settled a, a, c (a counted in pe-a and pe-b; pe-c's a and c too) = 0.55*3 + 0.3*2
    assert s["by_market"]["1X2"]["won"] == 5
    assert s["by_market"]["1X2"]["expected_wins_settled"] == pytest.approx(0.55 * 3 + 0.3 * 2)
    assert s["by_market"]["OU"] == {"won": 0, "lost": 1, "push": 0, "void": 0, "open": 1, "label": "Over/Under",
                                    "expected_wins_settled": 0.52}


def test_market_without_recorded_leg_probability_shows_no_expected(con):  # noqa: F811
    _event(con, "g1", "Arsenal", "Chelsea", NOW - timedelta(hours=3), "finished", 2, 0)
    con.commit()
    leg = _leg("g1", "1X2", "H", 1.8)
    del leg["prob"]
    _write_ledger([("pe-a", [leg, dict(_leg("g1", "BTTS", "no", 1.9), prob=0.4)], 3.42)])
    bm = pe.settle(con)["by_market"]
    assert bm["1X2"]["expected_wins_settled"] is None                      # never a partial sum
    assert bm["BTTS"]["expected_wins_settled"] == 0.4


# ---------- browser: Expected columns and the behind-expectation line ----------
def _history(by_market):
    rec = ph._data([])
    rec["estimated_parlays"]["record"]["by_market"] = by_market
    return ph._run({"data": rec, "now": ph.NOW.isoformat(), "hash": "#/history"})


def _cells(html, attr):
    i = html.index(f"<table {attr}>")
    table = html[i:html.index("</table>", i)]
    return {m[0]: re.findall(r"<td[^>]*>([^<]*)</td>", m[1])
            for m in re.findall(r'<tr[^>]*><th scope="row">([^<]+)</th>(.*?)</tr>', table)}


def _mk(label, won, lost, exp):
    return {"won": won, "lost": lost, "push": 0, "void": 0, "open": 0, "label": label, "expected_wins_settled": exp}


@ph.needs_node
def test_parlay_table_has_expected_column_matching_fixture_sums():
    html = _history({})
    assert '<th scope="col" title="Wins the model expected' in html and '<span class="lg">Expected</span><span class="sh" aria-hidden="true">Exp</span></th>' in html
    rows = _cells(html, "data-ph-by-legs")
    # fixture: 2 legs 0.35, 3 legs 0.2, total 0.55 (Won–lost, Expected, Hit rate, Void, Open, Paper P/L)
    assert rows["2 legs"][:2] == ["1–0", "0.3"] and rows["3 legs"][:2] == ["0–1", "0.2"]
    assert rows["Total"][:2] == ["1–1", "0.6"]
    assert "data-be-note" in html                                           # the break-even note stays
    assert "data-ph-by-market" not in html                                  # no market table comes back


@ph.needs_node
def test_behind_expectation_line_only_under_its_conditions():
    html = _history({
        "OU": _mk("Over/Under", 5, 11, 8.9),            # 16 legs, 3.9 behind: shown
        "DC": _mk("Double chance", 4, 4, 6.0),          # 8 legs, 2.0 behind: shown
        "ML": _mk("Moneyline", 15, 14, 16.4),           # behind by 1.4: not enough
        "BTTS": _mk("Both teams to score", 1, 6, 4.0),  # 7 legs: too few
        "1X2": _mk("Match result", 9, 3, 6.0),          # ahead of expectation
        "DNB": _mk("Draw no bet", 2, 10, None),         # no expected value recorded
    })
    m = re.search(r"<p [^>]*data-behind-expectation>([^<]*)</p>", html)
    assert m and m.group(1) == "Behind expectation: Over/Under legs 5–11 (expected ~9), Double chance legs 4–4 (expected ~6)."
    i = html.index("data-ph-by-legs")
    assert i < html.index("data-behind-expectation") < html.index("data-be-note", i)  # under the table, before the note


@ph.needs_node
def test_behind_expectation_line_hidden_when_nothing_qualifies():
    html = _history({"OU": _mk("Over/Under", 8, 2, 6.0), "ML": _mk("Moneyline", 2, 3, 4.0)})
    assert "data-behind-expectation" not in html and "Behind expectation" not in html
    assert "data-behind-expectation" not in _history({})


@ph.needs_node
def test_singles_expected_blank_when_a_graded_pick_lacks_a_probability():
    html = st._render()
    assert _cells(html, "data-singles-by-sport")["Total"][1] == "2.8"
    picks = [dict(p) for p in st.PICKS]
    del picks[0]["prob"]
    orig = st.PICKS
    try:
        st.PICKS = picks
        rows = _cells(st._render(), "data-singles-by-sport")
    finally:
        st.PICKS = orig
    assert rows["Soccer"][1] == "–" and rows["Total"][1] == "–" and rows["NBA"][1] == "1.3"
