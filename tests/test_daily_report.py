"""Regression for #31: the daily report crashed (KeyError: 'form') whenever a tennis, NBA or NFL pick
was published, because only soccer picks store form / expected goals / 1X2 model markets. The crash
aborted `python -m sbi daily` before the commit step, so the whole run's data was discarded."""
import json
from datetime import datetime, timedelta, timezone

from sbi import config, db, report

NOW = datetime(2026, 11, 16, 20, 30, tzinfo=timezone.utc)

# Keys publish_pick() always adds, for every sport.
COMMON = {"consensus_source": "Pinnacle", "n_bookmakers": 4, "model_q_p10": 0.52, "net_odds": 2.1,
          "stake_share_active": 1.0, "outcome_split": {"pw": 0.55, "phw": 0, "pp": 0, "phl": 0, "pl": 0.45},
          "all_prices": {"Pinnacle": 2.0}, "risks": [], "blend_weight": 0.0}

SOCCER = {**COMMON, "competition": "UEFA Nations League", "expected_goals": {"home": 1.6, "away": 0.9},
          "form": {"Spain": {"last": "WWDWW", "gf": 11, "ga": 3}, "England": {"last": "WDLWW", "gf": 8, "ga": 5}},
          "model_markets": {"1X2:H": 0.5, "1X2:D": 0.27, "1X2:A": 0.23, "OU:over:2.5": 0.48, "BTTS:yes": 0.45}}
TENNIS = {**COMMON, "context": "Elo 2110 v 2045 over the last 52 weeks.", "competition": "ATP Finals"}   # tennis.py
NBA = {**COMMON, "context": "Rest days 2 v 1.", "competition": "NBA", "projection": {"home": 114.2, "away": 109.8}}  # us.py


def _rec(con, rid, league, home, away, market, sel, evidence, line=None):
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,updated_at)
                   VALUES (?,'football',?,?,?,?,'scheduled','t','t')""",
                (f"e-{rid}", league, (NOW + timedelta(hours=20)).isoformat(), home, away))
    con.execute("""INSERT INTO recommendations(rec_id,event_id,published_at,sport,league,kickoff_utc,home,away,market,selection,
                   line,bookmaker,odds,odds_retrieved_at,model_prob,market_prob,final_prob,fair_odds,ev,ev_lower,prob_sd,
                   stake_units,model_version,rank,evidence_json,source_urls)
                   VALUES (?,?,?,'football',?,?,?,?,?,?,?,'Pinnacle',2.1,?,0.55,0.5,0.52,1.92,0.09,0.03,0.02,1,'t',1,?,'[]')""",
                (rid, f"e-{rid}", NOW.isoformat(), league, (NOW + timedelta(hours=20)).isoformat(), home, away, market, sel,
                 line, NOW.isoformat(), json.dumps(evidence)))


def test_daily_report_handles_tennis_nba_and_soccer_picks(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    con = db.connect(tmp_path / "t.sqlite")
    _rec(con, "s", "INT:uefa.nations", "Spain", "England", "1X2", "H", SOCCER)
    _rec(con, "t", "TENNIS:ATP", "Sinner", "Alcaraz", "ML", "home", TENNIS)
    _rec(con, "n", "NBA", "Celtics", "Knicks", "ML", "away", NBA)
    con.commit()

    md = report.write_daily(con, NOW, {}).read_text()           # used to raise KeyError: 'form'

    assert "Published today | **3**" in md
    # soccer detail is unchanged
    assert "Football — UEFA Nations League" in md and "Expected goals 1.6–0.9" in md and "Spain: WWDWW" in md
    # non-soccer picks are labelled with their sport and show their stored context, nothing invented
    assert "Tennis — ATP Finals" in md and "Elo 2110 v 2045" in md and "Sinner to win" in md
    assert "NBA — NBA" in md and "Projected score Celtics 114.2 – Knicks 109.8" in md and "Knicks to win" in md
    assert md.count("Expected goals") == 1 and "Recent form — Sinner" not in md


def test_daily_report_soccer_pick_missing_form_does_not_crash(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    con = db.connect(tmp_path / "t.sqlite")
    _rec(con, "s", "E0", "Arsenal", "Chelsea", "1X2", "H", {**COMMON, "competition": "Premier League"})
    con.commit()
    md = report.write_daily(con, NOW, {}).read_text()
    assert "Football — Premier League" in md and "No further model detail is stored" in md
