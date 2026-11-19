"""The daily report must render picks made under the loosened single-pick rules (singles-v2, #99),
whose evidence has no `model_q_p10`. On 2026-11-19 that missing key crashed `python -m sbi daily`."""
import json
from datetime import datetime, timezone

from sbi import db, report


def test_write_daily_renders_a_singles_v2_pick(tmp_path, monkeypatch):
    con = db.connect(tmp_path / "t.sqlite")
    now = datetime(2026, 11, 19, 21, 27, tzinfo=timezone.utc)
    con.execute("""INSERT INTO events(event_id,sport,league,season,kickoff_utc,home,away,status,source,source_url,updated_at)
                   VALUES ('nba:NBA:x','nba','NBA','2026','2026-11-20T01:00:00+00:00','Bucks','Blazers','scheduled','s','u',?)""",
                (now.isoformat(),))
    ev = {"rules_version": "singles-v2", "consensus_source": "other bookmakers' consensus", "n_bookmakers": 3,
          "risks": ["Selected under the loosened single-pick rules."], "selection_text": "Bucks to win"}
    con.execute("""INSERT INTO recommendations(rec_id,event_id,published_at,sport,league,kickoff_utc,home,away,market,selection,
                   line,bookmaker,odds,odds_retrieved_at,model_prob,market_prob,final_prob,fair_odds,ev,ev_lower,prob_sd,
                   stake_units,model_version,rank,evidence_json,source_urls,is_paper,status)
                   VALUES ('r1','nba:NBA:x',?,'nba','NBA','2026-11-20T01:00:00+00:00','Bucks','Blazers','ML','home',NULL,
                   'BookA',2.1,?,0.5,0.47,0.5,2.0,0.05,0.05,NULL,1,'singles-v2',1,?,'[]',1,'open')""",
                (now.isoformat(), now.isoformat(), json.dumps(ev)))
    monkeypatch.setattr(report.config, "REPORTS_DIR", tmp_path)
    out = report.write_daily(con, now, {"analysed_events": 1, "published": 1})
    assert "Bucks" in open(out, encoding="utf-8").read()
