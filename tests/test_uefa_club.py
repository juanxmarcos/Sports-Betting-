"""Issue #114: UEFA club competitions (Champions/Europa/Conference League) are ingested and labelled."""
from datetime import datetime, timezone

from sbi import competitions, db
from sbi.sources import espn_club, odds_api


def _ev(espn_id, home, away, ko, completed=False, hg=None, ag=None):
    return {"espn_id": espn_id, "kickoff_utc": ko, "completed": completed, "hg": hg, "ag": ag,
            "espn_home": (home, None), "espn_away": (away, None),
            "odds": [("DraftKings", "1X2", "H", None, 1.42, "current"), ("DraftKings", "1X2", "A", None, 7.5, "current"),
                     ("DraftKings", "1X2", "D", None, 4.9, "current")]}


def test_uefa_games_are_created_once_with_unmapped_names_kept_and_settle(tmp_path):
    con = db.connect(tmp_path / "t.sqlite")
    now = datetime(2026, 11, 23, 22, 0, tzinfo=timezone.utc)
    ko = datetime(2026, 11, 24, 20, 0, tzinfo=timezone.utc)
    evs = [_ev("1", "Arsenal", "Borussia Dortmund", ko)]
    r = espn_club.store(con, "UCL", "uefa.champions", evs, now, {"Arsenal"}, keep_unmapped=True)
    assert r["created"] == 1 and r["odds"] == 3
    row = con.execute("SELECT event_id, home, away, league FROM events WHERE league='UCL'").fetchone()
    assert (row["home"], row["away"], row["league"]) == ("Arsenal", "Borussia Dortmund", "UCL")
    assert espn_club.store(con, "UCL", "uefa.champions", evs, now, {"Arsenal"}, keep_unmapped=True)["created"] == 0
    later = datetime(2026, 11, 25, 9, 0, tzinfo=timezone.utc)
    done = [_ev("1", "Arsenal", "Borussia Dortmund", ko, completed=True, hg=2, ag=1)]
    assert espn_club.store(con, "UCL", "uefa.champions", done, later, {"Arsenal"}, keep_unmapped=True)["results_filled"] == 1
    assert con.execute("SELECT status, home_score FROM events WHERE league='UCL'").fetchone()[:] == ("finished", 2)


def test_domestic_leagues_still_skip_unmapped_teams(tmp_path):
    con = db.connect(tmp_path / "t.sqlite")
    now = datetime(2026, 11, 23, 22, 0, tzinfo=timezone.utc)
    ko = datetime(2026, 11, 24, 20, 0, tzinfo=timezone.utc)
    r = espn_club.store(con, "E0", "eng.1", [_ev("2", "Arsenal", "Unknown FC", ko)], now, {"Arsenal"})
    assert r["created"] == 0 and r["unmapped"] == ["Unknown FC"]


def test_uefa_labels_and_odds_api_keys():
    assert competitions.LEAGUE_NAMES["UCL"] == "Champions League"
    assert competitions.LEAGUE_NAMES["UEL"] == "Europa League"
    assert competitions.LEAGUE_NAMES["UECL"] == "Conference League"
    assert odds_api.CLUB["soccer_uefa_champs_league"] == "UCL"
    assert odds_api.CLUB["soccer_uefa_europa_league"] == "UEL"
    assert odds_api.CLUB["soccer_uefa_europa_conference_league"] == "UECL"
    assert espn_club.UEFA_LEAGUES == {"UCL": "uefa.champions", "UEL": "uefa.europa", "UECL": "uefa.europa.conf"}
