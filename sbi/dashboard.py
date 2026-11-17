"""Static dashboard: one HTML file + data.json. Zero hosting cost: open locally
(`python -m sbi serve`) or publish the folder with GitHub Pages (free for public repos)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from . import config, db
from .performance import prediction_metrics, rec_metrics
from .report import describe, local

TEMPLATE = Path(__file__).parent / "templates" / "dashboard.html"


def build(con) -> Path:
    config.load_tuned()
    site = config.SITE_DIR
    site.mkdir(parents=True, exist_ok=True)
    recs = [dict(r) for r in con.execute("SELECT * FROM recommendations ORDER BY published_at DESC, rank")]
    for r in recs:
        r["desc"] = describe(r)
        r["ko_local"] = local(r["kickoff_utc"])
        r["evidence"] = json.loads(r.pop("evidence_json") or "{}")
        r["source_urls"] = json.loads(r["source_urls"] or "[]")
        r["notes"] = [dict(n) for n in con.execute("SELECT * FROM research_notes WHERE event_id=?", (r["event_id"],))]
    upcoming = pd.read_sql_query("""
        SELECT e.event_id, e.league, e.kickoff_utc, e.home, e.away,
               MAX(CASE WHEN p.selection='H' AND p.market='1X2' THEN p.model_prob END) AS p_home,
               MAX(CASE WHEN p.selection='D' AND p.market='1X2' THEN p.model_prob END) AS p_draw,
               MAX(CASE WHEN p.selection='A' AND p.market='1X2' THEN p.model_prob END) AS p_away,
               MAX(CASE WHEN p.selection='H' AND p.market='1X2' THEN p.market_prob END) AS m_home,
               MAX(CASE WHEN p.selection='D' AND p.market='1X2' THEN p.market_prob END) AS m_draw,
               MAX(CASE WHEN p.selection='A' AND p.market='1X2' THEN p.market_prob END) AS m_away,
               (SELECT COUNT(DISTINCT bookmaker) FROM odds o WHERE o.event_id=e.event_id) AS n_books
        FROM events e LEFT JOIN predictions p ON p.event_id=e.event_id
             AND p.run_id=(SELECT MAX(run_id) FROM predictions p2 WHERE p2.event_id=e.event_id)
        WHERE e.status='scheduled' AND e.kickoff_utc > datetime('now','-3 hours')
        GROUP BY e.event_id ORDER BY e.kickoff_utc LIMIT 300""", con)
    from . import leagues
    upcoming = upcoming[upcoming.league.map(leagues.status) != leagues.MONITORING].reset_index(drop=True)   # stored, never analysed
    upcoming["ko_local"] = upcoming.kickoff_utc.map(local)
    bt = con.execute("SELECT metrics_json, created_at FROM backtest_results WHERE label LIKE 'walkforward:%' ORDER BY id DESC LIMIT 1").fetchone()
    data = {
        "generated": db.utcnow(), "generated_local": local(db.utcnow()), "timezone": config.TIMEZONE,
        "model_version": config.MODEL.model_version, "blend_weight": config.MODEL.blend_weight,
        "rules": config.RULES.__dict__, "leagues": config.FOOTBALL_LEAGUES,
        "recommendations": recs,
        "upcoming": json.loads(upcoming.to_json(orient="records")),
        "performance": rec_metrics(con), "predictions": prediction_metrics(con),
        "backtest": json.loads(bt["metrics_json"]) if bt else None,
        "backtest_at": bt["created_at"] if bt else None,
        "international": (json.loads((config.DATA_DIR / "international_latest.json").read_text())
                          if (config.DATA_DIR / "international_latest.json").exists() else None),
        "intl_backtest": (json.loads((config.DATA_DIR / "backtest" / "international.json").read_text())
                          if (config.DATA_DIR / "backtest" / "international.json").exists() else None),
        "jobs": [dict(r) for r in con.execute("SELECT * FROM job_runs ORDER BY id DESC LIMIT 30")],
        "providers": [dict(r) for r in con.execute("SELECT * FROM provider_status ORDER BY provider")],
    }
    for r in (data["international"] or {}).get("rows", []):
        r["ko_local"] = local(r["kickoff_utc"])
    (site / "data.json").write_text(json.dumps(data, default=str))
    # Human-readable permanent ledger (git-tracked; mirrors the immutable DB rows)
    ledger = config.ROOT / "ledger"
    ledger.mkdir(exist_ok=True)
    pd.read_sql_query("""SELECT rec_id,published_at,sport,league,kickoff_utc,home,away,market,selection,line,
                         bookmaker,odds,odds_retrieved_at,model_prob,market_prob,final_prob,fair_odds,ev,ev_lower,
                         stake_units,model_version,is_paper,status,pnl_units,closing_odds,clv,settled_at
                         FROM recommendations ORDER BY published_at, rank""", con).to_csv(
        ledger / "recommendations.csv", index=False)
    shutil.copy(TEMPLATE, site / "index.html")
    return site / "index.html"
