"""Issue #33: the publication gates for real parlays. A card appears only with an owner-recorded,
verified single-bookmaker combined quote AND joint-calibration evidence that meets the
pre-registered criteria for those legs. Computed products never become quotes."""
import csv
import json
from datetime import datetime, timedelta, timezone

import pytest

from sbi import config, db, parlay_calibration as cal, parlay_quotes as pq, parlays, site

NOW = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)          # 10:00 in New York
TZ = "America/New_York"
PASSING = {"passed": True, "legs_per_combination": 2, "leagues": ["E0", "SP1", "I1"], "combinations": 250}


def _leg(i, *, league="E0", hours=5, prob=0.55, prices=None, event_id=None):
    return {"id": f"p{i}", "event_id": event_id or f"e{i}", "sport": "soccer", "competition": f"League {league}",
            "participants": [f"Home {i}", f"Away {i}"], "start_utc": (NOW + timedelta(hours=hours)).isoformat(),
            "state": "active", "prob": prob, "odds_updated": (NOW - timedelta(hours=1)).isoformat(),
            "source": "https://api.the-odds-api.com/v4/x", "selection_key": "H",
            "prices": prices if prices is not None else {"BookA": {"H": 2.2}, "BookB": {"H": 2.1}},
            "league": league, "title": f"Home {i} v Away {i}", "selection_label": f"Home {i} to win",
            "market": "Match result"}


def _quote(legs=("p1", "p2"), odds=4.8, age_min=5, book="BookA", **over):
    q = pq.make(book, odds, list(legs), NOW - timedelta(minutes=age_min), "BookA bet slip, desktop", NOW)
    q.update(over)
    return q


TWO = [_leg(1, league="E0"), _leg(2, league="SP1")]


# ---------- calibration ----------
def _sel(i, day, league, prob, won, team=None):
    return {"event": f"ev{i}", "league": league, "start": datetime(2025, 1, 1, 15, tzinfo=timezone.utc) + timedelta(days=day),
            "teams": {team or f"t{i}a", f"t{i}b"}, "prob": prob, "won": won}


def _calibrated(n_pairs):
    pattern = [(1, 1), (1, 0), (0, 1), (0, 0)]                       # exactly the independent 0.5 x 0.5 frequencies
    out = []
    for k in range(n_pairs):
        a, b = pattern[k % 4]
        out += [_sel(2 * k, k, "E0", 0.5, a), _sel(2 * k + 1, k, "SP1", 0.5, b)]
    return out


def test_committed_evidence_does_not_pass_the_preregistered_criteria():
    e = cal.evaluate()
    assert e["combinations"] < cal.MIN_COMBINATIONS and not e["passed"]
    assert (cal.MIN_COMBINATIONS, cal.MAX_ABS_Z, cal.SUPPORTED_LEGS) == (200, 1.96, 2)


def test_small_sample_fails_even_when_perfectly_calibrated():
    e = cal.evaluate(_calibrated(100))
    assert e["combinations"] == 100 and e["joint_z"] == 0 and not e["passed"]
    assert e["reasons"] == ["only 100 disjoint settled combinations; at least 200 are required"]


def test_large_calibrated_sample_passes():
    e = cal.evaluate(_calibrated(240))
    assert e["passed"] and e["leagues"] == ["E0", "SP1"] and e["legs_per_combination"] == 2


def test_miscalibrated_joint_outcomes_fail():
    sel = []
    for k in range(240):                                              # legs win together: strongly correlated
        w = 1 if k % 2 == 0 else 0
        sel += [_sel(2 * k, k, "E0", 0.5, w), _sel(2 * k + 1, k, "SP1", 0.5, w)]
    e = cal.evaluate(sel)
    assert not e["passed"] and any("95% band" in r for r in e["reasons"])


def test_pairs_are_disjoint_and_respect_the_live_screens():
    sel = [_sel(1, 0, "E0", 0.5, 1), _sel(2, 0, "E0", 0.5, 1),       # same league: never paired
           _sel(3, 0, "SP1", 0.5, 1, team="t1a"),                    # shares a team with 1
           _sel(4, 0, "I1", 0.5, 0)]
    pairs = cal.disjoint_pairs(sel)
    used = [s["event"] for p in pairs for s in p]
    assert len(used) == len(set(used))
    for a, b in pairs:
        assert a["league"] != b["league"] and not a["teams"] & b["teams"]


def test_coverage_is_limited_to_what_was_measured():
    assert cal.coverage_problem(None, TWO) == "no joint calibration evidence"
    assert cal.coverage_problem({**PASSING, "passed": False}, TWO) == "joint calibration criteria not met"
    assert "2-leg" in cal.coverage_problem(PASSING, TWO + [_leg(3, league="I1")])
    assert "outside" in cal.coverage_problem(PASSING, [_leg(1), _leg(2, league="INT:uefa.nations")])
    assert cal.coverage_problem(PASSING, TWO) is None


# ---------- owner quotes ----------
def test_a_fresh_consistent_quote_is_verified():
    assert pq.quote_problem(_quote(), {l["id"]: l for l in TWO}, NOW, 30) is None      # 4.8 vs 2.2 x 2.2 = 4.84


@pytest.mark.parametrize("q, why", [
    (_quote(age_min=31), "quote is stale"),
    (_quote(age_min=-5), "quote has no valid time"),
    (_quote(quoted_at="2026-11-13T14:55:00"), "quote has no valid time"),
    (_quote(book="BookZ"), "bookmaker does not price every leg in Doyen's data"),
    (_quote(odds=6.0), "combined odds inconsistent with the bookmaker's leg prices (review)"),
    (_quote(odds=3.5), "combined odds inconsistent with the bookmaker's leg prices (review)"),
    (_quote(odds=1.0), "invalid combined odds"),
    (_quote(legs=("p1",)), "needs 2-6 distinct legs"),
    (_quote(legs=("p1", "p9")), "a leg is not a current usable pick"),
    (_quote(source=" "), "missing provenance"),
    (_quote(kind="computed_product"), "not an owner-recorded bookmaker quote"),
    (_quote(origin="scraper"), "not an owner-recorded bookmaker quote"),
])
def test_quote_rejections(q, why):
    assert pq.quote_problem(q, {l["id"]: l for l in TWO}, NOW, 30) == why


def test_quote_on_two_legs_of_one_event_is_rejected():
    legs = {l["id"]: l for l in [_leg(1), _leg(2, league="SP1", event_id="e1")]}
    assert pq.quote_problem(_quote(), legs, NOW, 30) == "two legs on the same event"


def test_quote_file_is_append_only(tmp_path):
    p = tmp_path / "q.json"
    a, b = _quote(), _quote(odds=4.7)
    assert pq.append(a, p) and pq.append(b, p) and not pq.append(a, p)
    assert pq.load(p) == [a, b]


# ---------- the block ----------
def test_quote_and_passing_calibration_publish_a_valid_card():
    b = parlays.build(TWO, NOW, TZ, quotes=[_quote()], calibration=PASSING)
    assert b["status"] == "published" and b["blockers"] == [] and len(b["recommendations"]) == 1
    r = b["recommendations"][0]
    assert r["bookmaker"] == "BookA" and r["quote"]["decimal_odds"] == 4.8 and r["quote"]["kind"] == "bookmaker_combined"
    assert [leg["title"] for leg in r["legs"]] == ["Home 1 v Away 1", "Home 2 v Away 2"]
    assert r["ev"] == pytest.approx(0.55 * 0.55 * 4.8 - 1, abs=1e-6)
    assert parlays.shown_cards(b, NOW) == [r]
    assert parlays.card_view(r)["gross_payout"] == "48.00"


def test_quote_without_calibration_is_not_published():
    b = parlays.build(TWO, NOW, TZ, quotes=[_quote()], calibration=cal.evaluate())
    assert b["status"] == "not_published" and b["recommendations"] == []
    assert [x["key"] for x in b["blockers"]] == ["joint_calibration"]
    assert b["audit"]["verified_quotes"] == 1
    assert b["audit"]["excluded"] == {"combination: joint calibration criteria not met": 1}


def test_calibration_without_a_quote_is_not_published_and_no_product_becomes_a_quote():
    shadow = []
    b = parlays.build(TWO, NOW, TZ, quotes=[], calibration=PASSING, shadow=shadow)
    assert b["recommendations"] == [] and [x["key"] for x in b["blockers"]] == ["combined_quote"]
    assert "4.84" not in json.dumps(b) and "BookA" not in json.dumps(b)          # computed price stays out of the block
    assert {s["bookmaker"] for s in shadow} == {"BookA", "BookB"}
    assert shadow[0]["computed_product_odds"] == pytest.approx(4.84)


def test_stale_quote_is_never_used():
    b = parlays.build(TWO, NOW, TZ, quotes=[_quote(age_min=45)], calibration=PASSING)
    assert b["recommendations"] == [] and b["audit"]["verified_quotes"] == 0


def test_no_value_at_the_quoted_price_is_not_published():
    legs = [_leg(1, prob=0.46), _leg(2, league="SP1", prob=0.46)]           # 0.2116 x 4.84 > 1, x 4.5 < 1
    b = parlays.build(legs, NOW, TZ, quotes=[_quote(odds=4.5)], calibration=PASSING)
    assert b["recommendations"] == []
    assert b["audit"]["excluded"] == {"combination: no positive value at the quoted combined price": 1}


def test_a_pick_is_in_at_most_one_published_parlay():
    legs = TWO + [_leg(3, league="I1")]
    quotes = [_quote(("p1", "p2")), _quote(("p1", "p3"), odds=4.84)]
    b = parlays.build(legs, NOW, TZ, quotes=quotes, calibration=PASSING)
    assert len(b["recommendations"]) == 1
    assert b["audit"]["excluded"]["combination: shares a leg with a better published parlay"] == 1


def test_three_leg_combination_is_not_covered_by_two_leg_evidence():
    legs = TWO + [_leg(3, league="I1")]
    q = _quote(("p1", "p2", "p3"), odds=10.6)                                 # 2.2^3 = 10.648
    b = parlays.build(legs, NOW, TZ, quotes=[q], calibration=PASSING)
    assert b["recommendations"] == []
    assert b["audit"]["excluded"]["combination: joint calibration measured only 2-leg combinations"] == 1


# ---------- shadow ledger ----------
def test_shadow_ledger_is_append_only_and_labelled_computed(tmp_path):
    p = tmp_path / "s.csv"
    rows = [{"date": "2026-11-13", "legs": ["p1", "p2"], "bookmaker": "BookA", "computed_product_odds": 4.84,
             "joint_prob_independent": 0.3025, "computed_ev": 0.4641}]
    assert parlays.record_shadow(rows, NOW, p) == 1
    assert parlays.record_shadow(rows, NOW + timedelta(hours=2), p) == 0
    got = list(csv.DictReader(p.open()))
    assert len(got) == 1 and got[0]["price_kind"] == "computed_product_not_a_quote"
    assert got[0]["first_seen"] == NOW.isoformat()


def test_site_build_writes_no_shadow_ledger_unless_asked(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path / "r")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    con = db.connect(tmp_path / "t.sqlite")
    site.build(con, datetime.now(timezone.utc))
    assert not (tmp_path / "ledger" / "parlay_shadow.csv").exists()


def test_cli_refuses_an_unverifiable_quote_and_records_nothing(tmp_path, monkeypatch, capsys):
    from sbi.__main__ import main
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    rc = main(["parlay-quote", "--bookmaker", "Unibet", "--odds", "5.1", "--legs", "a,b", "--source", "slip"])
    assert rc == 1 and "a leg is not a current usable pick" in capsys.readouterr().out
    assert not (tmp_path / "parlay_quotes.json").exists()
    assert main(["parlay-quote", "--bookmaker", "U", "--odds", "5", "--legs", "a,b", "--source", "s",
                 "--quoted-at", "2026-11-16T18:00:00"]) == 2                      # naive time refused


# ---------- the real front end renders a backend-built card (no mock flag) ----------
def test_front_end_renders_a_gated_backend_card_and_hides_it_once_the_quote_expires():
    import os
    import shutil
    import subprocess
    from pathlib import Path
    if not shutil.which("node") and not os.environ.get("CI"):
        pytest.skip("node is not installed")
    harness = Path(__file__).resolve().parent / "js" / "render_home.js"
    block = parlays.build(TWO, NOW, TZ, quotes=[_quote()], calibration=PASSING)

    def render(now):
        data = {"generated": NOW.isoformat(), "default_timezone": TZ, "parlays": block, "picks": [], "history": [],
                "events": [], "watching": [], "close_to_value": [], "briefing": {}, "funnel_7d": {}, "sports": {},
                "record": {"won": 0, "lost": 0, "push": 0, "profit_units": 0, "open": 0}}
        out = subprocess.run(["node", str(harness)], input=json.dumps({"data": data, "now": now.isoformat(), "hash": ""}),
                             capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        return out.stdout

    html = render(NOW)
    assert "Home 1 vs. Away 1" in html and "BookA" in html and "48.00" in html and "4.80" in html
    assert "Mock data" not in html
    later = render(NOW + timedelta(minutes=40))                                # quote now older than 30 minutes
    assert "Home 1 vs. Away 1" not in later and "No verified parlays today" in later
