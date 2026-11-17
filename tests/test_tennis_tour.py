"""Tennis tour labels (issue #49): ATP/WTA comes from the draw, not from the ESPN endpoint. No network."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sbi import db, tennis

FIX = Path(__file__).parent / "fixtures" / "espn_tennis"


def _load(name, feed="atp"):
    return tennis._parse(json.loads((FIX / name).read_text()), feed)


def test_womens_grand_slam_match_from_atp_feed_is_wta_and_best_of_three():
    rows = _load("atp_20250601_roland_garros.json")
    w = next(m for m in rows if m["p1"] == "Lulu Sun")
    assert (w["tour"], w["feed_tour"], w["tour_source"], w["slam"]) == ("wta", "atp", "grouping_slug", True)
    assert not tennis.best_of_five(w)
    elo = tennis.Elo(0.5, 1.0)
    for _ in range(5):
        elo.update("Lulu Sun", "Victoria Mboko", "clay")
    p3 = elo.prob("Lulu Sun", "Victoria Mboko", "clay")
    assert tennis.match_prob(elo, w) == pytest.approx(p3)        # no best-of-five conversion


def test_mens_grand_slam_match_still_best_of_five():
    rows = _load("atp_20250601_roland_garros.json")
    m = next(r for r in rows if r["p1"] == "Tristan Schoolkate")
    assert (m["tour"], m["tour_source"], m["slam"]) == ("atp", "grouping_slug", True)
    assert tennis.best_of_five(m)
    elo = tennis.Elo(0.5, 1.0)
    for _ in range(5):
        elo.update("Tristan Schoolkate", "Marton Fucsovics", "clay")
    p3 = elo.prob("Tristan Schoolkate", "Marton Fucsovics", "clay")
    assert tennis.match_prob(elo, m) == pytest.approx(tennis.bo5(p3))
    assert tennis.match_prob(elo, m) > p3 > 0.5


def test_doubles_are_not_parsed():
    rows = _load("atp_20250601_roland_garros.json")
    assert {r["p1"] for r in rows} == {"Tristan Schoolkate", "Lulu Sun"}


def test_combined_masters_event_labelled_per_match():
    rows = _load("atp_20250428_madrid.json")
    by = {r["p1"]: r for r in rows}
    assert by["Alexandra Eala"]["tour"] == "wta" and by["Mariano Navone"]["tour"] == "atp"
    assert not any(r["slam"] for r in rows) and not any(tennis.best_of_five(r) for r in rows)
    # the same event read from the wta endpoint gives the same labels
    assert {r["p1"]: r["tour"] for r in _load("atp_20250428_madrid.json", feed="wta")} == \
        {r["p1"]: r["tour"] for r in rows}


@pytest.mark.parametrize("grouping,ctype,feed,expected", [
    ({"slug": "womens-singles", "displayName": "Women's Singles"}, {}, "atp", ("wta", "grouping_slug")),
    ({"slug": "mens-singles", "displayName": "Men's Singles"}, {}, "wta", ("atp", "grouping_slug")),
    ({"displayName": "Women's Singles"}, {"slug": "womens-singles"}, "atp", ("wta", "competition_type_slug")),
    ({"displayName": "Women’s Singles"}, {}, "atp", ("wta", "grouping_name")),
    ({"displayName": "Men's Singles"}, {}, "wta", ("atp", "grouping_name")),
    ({"displayName": "Singles"}, {"text": "Women's Singles"}, "atp", ("wta", "competition_type_name")),
    ({"displayName": "Singles"}, {}, "wta", ("wta", "feed_fallback")),     # no draw signal at all
    ({}, {}, "atp", ("atp", "feed_fallback")),
])
def test_tour_rule_ambiguous_cases(grouping, ctype, feed, expected):
    assert tennis.tour_of(grouping, {"type": ctype}, feed) == expected


def test_best_of_five_only_mens_slam():
    assert tennis.best_of_five({"slam": True, "tour": "atp"})
    assert not tennis.best_of_five({"slam": True, "tour": "wta"})
    assert not tennis.best_of_five({"slam": False, "tour": "atp"})


def test_womens_match_feeds_its_own_ratings_and_is_stored_as_wta(tmp_path, monkeypatch):
    monkeypatch.setattr(db.config, "DB_PATH", tmp_path / "t.sqlite")
    con = db.connect()
    rows = _load("atp_20250601_roland_garros.json")
    now = datetime(2025, 5, 26, 12, tzinfo=timezone.utc)
    tennis.register(con, now, rows)
    got = dict(con.execute("SELECT home, league FROM events WHERE sport='tennis'").fetchall())
    assert got == {"Lulu Sun": "TENNIS:WTA", "Tristan Schoolkate": "TENNIS:ATP"}
    eids = {r[0] for r in con.execute("SELECT event_id FROM events")}
    assert any(e.startswith("tennis:WTA:") for e in eids)


def _legacy_row(con, eid, league="TENNIS:ATP"):
    con.execute("""INSERT INTO events(event_id,sport,league,season,kickoff_utc,home,away,status,source,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""", (eid, "tennis", league, "2025", "2025-05-26T10:00:00+00:00",
                                                     "Lulu Sun", "Victoria Mboko", "scheduled", "espn", "t"))


def test_stored_legacy_row_keeps_id_and_gets_correct_league(tmp_path, monkeypatch):
    monkeypatch.setattr(db.config, "DB_PATH", tmp_path / "t.sqlite")
    con = db.connect()
    w = next(m for m in _load("atp_20250601_roland_garros.json") if m["p1"] == "Lulu Sun")
    legacy = tennis._eid({**w, "tour": "atp"})
    _legacy_row(con, legacy)
    tennis.register(con, datetime(2025, 5, 26, 12, tzinfo=timezone.utc), [w])
    rows = [tuple(r) for r in con.execute("SELECT event_id, league FROM events")]
    assert rows == [(legacy, "TENNIS:WTA")]          # no duplicate, same ID (odds stay linked), league fixed


def test_stored_legacy_row_with_published_pick_is_left_untouched(tmp_path, monkeypatch):
    monkeypatch.setattr(db.config, "DB_PATH", tmp_path / "t.sqlite")
    con = db.connect()
    w = next(m for m in _load("atp_20250601_roland_garros.json") if m["p1"] == "Lulu Sun")
    legacy = tennis._eid({**w, "tour": "atp"})
    _legacy_row(con, legacy)
    con.execute("""INSERT INTO recommendations(event_id, published_at, sport, league, kickoff_utc, home, away, market,
                   selection, line, bookmaker, odds, model_prob, final_prob, fair_odds, ev, ev_lower, stake_units,
                   model_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (legacy, "2025-05-26T09:00:00+00:00", "tennis", "TENNIS:ATP", "2025-05-26T10:00:00+00:00",
                 "Lulu Sun", "Victoria Mboko", "ML", "home", 0.0, "book", 2.0, 0.55, 0.55, 1.82, 0.1, 0.02, 1.0, "t"))
    tennis.register(con, datetime(2025, 5, 26, 12, tzinfo=timezone.utc), [w])
    assert tuple(con.execute("SELECT league FROM events WHERE event_id=?", (legacy,)).fetchone()) == ("TENNIS:ATP",)
    assert tuple(con.execute("SELECT league, odds FROM recommendations").fetchone()) == ("TENNIS:ATP", 2.0)
    assert con.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1


def test_audit_counts_and_walk_forward_on_fixtures(tmp_path, monkeypatch):
    from sbi import tennis_tour_audit as ta
    rows = _load("atp_20250601_roland_garros.json") + _load("atp_20250428_madrid.json")
    L = ta.label_counts(rows)
    assert (L["completed_matches"], L["completed_label_changed"], L["completed_label_changed_grand_slam"]) == (4, 2, 1)
    assert L["completed_label_changed_by_direction"] == {"atp->wta": 2}
    monkeypatch.setattr(db.config, "DB_PATH", tmp_path / "t.sqlite")
    con = db.connect()
    w = next(m for m in rows if m["p1"] == "Lulu Sun")
    _legacy_row(con, tennis._eid({**w, "tour": "atp"}))
    S = ta.stored_rows(con, rows)
    assert (S["stored_events"], S["mislabelled"], S["mislabelled_with_published_pick"]) == (1, 1, [])
    wf = ta.walk_forward(rows)
    assert wf["all_test_matches"]["n"] == 0          # fixtures predate TEST_FROM: nothing scored, nothing invented
