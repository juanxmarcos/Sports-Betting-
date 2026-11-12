"""Interface between the deterministic pipeline and Claude's contextual research.

Claude (run interactively or as a Claude Code scheduled task on the Max subscription)
reads the research brief, investigates team news with web search, and records each
finding with `python -m sbi note ...`. Notes are QUALITATIVE RISK FLAGS ONLY: they are
shown next to selections but never change probabilities or published records.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from . import config, db

CATEGORIES = ("injury", "suspension", "lineup", "motivation", "schedule", "weather", "travel", "manager", "other")


def brief(con, now: datetime) -> dict:
    recs = [dict(r) for r in con.execute(
        "SELECT rec_id,event_id,league,kickoff_utc,home,away,market,selection,line,odds,bookmaker,final_prob,ev "
        "FROM recommendations WHERE status='open' AND kickoff_utc > ? ORDER BY kickoff_utc", (now.isoformat(),))]
    upcoming = [dict(r) for r in con.execute(
        "SELECT event_id,league,kickoff_utc,home,away FROM events WHERE status='scheduled' "
        "AND kickoff_utc BETWEEN ? AND ? ORDER BY kickoff_utc",
        (now.isoformat(), (now + timedelta(hours=48)).isoformat()))]
    return {
        "generated": db.utcnow(),
        "instructions": (
            "For each open selection, check team news (injuries, suspensions, expected/confirmed lineups, "
            "rotation, motivation, schedule congestion, weather, travel). Record each finding with "
            "`python -m sbi note --event <event_id> --category <cat> --evidence-type "
            "<verified_fact|interpretation|speculation> --direction <supports|against|neutral> "
            "--claim '<text>' --url <source>`. Only 'verified_fact' needs a primary/reputable source URL. "
            "Never alter probabilities or odds. Do not invent information; if nothing is found, record nothing."),
        "open_selections": recs,
        "upcoming_events": upcoming,
    }


def write_brief(con, now: datetime):
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    p = config.REPORTS_DIR / "research_brief.json"
    p.write_text(json.dumps(brief(con, now), indent=2, default=str))
    return p


def add_note(con, event_id: str, category: str, claim: str, evidence_type: str,
             direction: str = "neutral", source_url: str | None = None, created_by: str = "claude") -> int:
    if not con.execute("SELECT 1 FROM events WHERE event_id=?", (event_id,)).fetchone():
        raise ValueError(f"unknown event_id {event_id}")
    if category not in CATEGORIES:
        raise ValueError(f"category must be one of {CATEGORIES}")
    if evidence_type == "verified_fact" and not source_url:
        raise ValueError("verified_fact requires --url")
    cur = con.execute("""INSERT INTO research_notes(event_id,category,claim,evidence_type,direction,source_url,
                         retrieved_at,created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
                      (event_id, category, claim, evidence_type, direction, source_url,
                       db.utcnow() if source_url else None, created_by, db.utcnow()))
    con.commit()
    return cur.lastrowid
