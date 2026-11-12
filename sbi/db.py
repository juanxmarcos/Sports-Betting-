"""SQLite storage. Single file, zero cost, committed-friendly.

Immutability: the published fields of `recommendations` cannot be UPDATEd and rows
cannot be DELETEd (enforced by triggers). Only settlement columns may change.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import config

SCHEMA = r"""
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS events (
    event_id     TEXT PRIMARY KEY,           -- sport:league:YYYYMMDD:home:away
    sport        TEXT NOT NULL,
    league       TEXT NOT NULL,
    season       TEXT,
    kickoff_utc  TEXT NOT NULL,              -- ISO-8601 UTC
    home         TEXT NOT NULL,
    away         TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'scheduled',  -- scheduled|finished|postponed
    home_score   INTEGER,
    away_score   INTEGER,
    home_xg      REAL,
    away_xg      REAL,
    source       TEXT NOT NULL,
    source_url   TEXT,
    updated_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_events_league_ko ON events(league, kickoff_utc);
CREATE INDEX IF NOT EXISTS ix_events_status ON events(status);

CREATE TABLE IF NOT EXISTS odds (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id     TEXT NOT NULL REFERENCES events(event_id),
    bookmaker    TEXT NOT NULL,
    market       TEXT NOT NULL,              -- 1X2 | OU | AH
    selection    TEXT NOT NULL,              -- H D A | over under | home away
    line         REAL,                       -- goals line / handicap (home perspective)
    price        REAL NOT NULL,              -- decimal odds as quoted
    kind         TEXT NOT NULL,              -- pre | closing
    source       TEXT NOT NULL,
    source_url   TEXT,
    retrieved_at TEXT NOT NULL,
    UNIQUE(event_id, bookmaker, market, selection, line, kind, price)
);
CREATE INDEX IF NOT EXISTS ix_odds_event ON odds(event_id);

CREATE TABLE IF NOT EXISTS model_runs (
    run_id         TEXT PRIMARY KEY,
    model_version  TEXT NOT NULL,
    league         TEXT NOT NULL,
    trained_through TEXT NOT NULL,
    n_matches      INTEGER,
    params_json    TEXT,
    created_at     TEXT NOT NULL
);

-- Every model probability for every analysed event (bet or not) -> calibration.
CREATE TABLE IF NOT EXISTS predictions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL REFERENCES model_runs(run_id),
    event_id     TEXT NOT NULL REFERENCES events(event_id),
    market       TEXT NOT NULL,
    selection    TEXT NOT NULL,
    line         REAL,
    model_prob   REAL NOT NULL,
    prob_sd      REAL,
    market_prob  REAL,
    final_prob   REAL,
    created_at   TEXT NOT NULL,
    UNIQUE(run_id, event_id, market, selection, line)
);

CREATE TABLE IF NOT EXISTS recommendations (
    rec_id        TEXT PRIMARY KEY,
    event_id      TEXT NOT NULL REFERENCES events(event_id),
    published_at  TEXT NOT NULL,
    sport         TEXT NOT NULL,
    league        TEXT NOT NULL,
    kickoff_utc   TEXT NOT NULL,
    home          TEXT NOT NULL,
    away          TEXT NOT NULL,
    market        TEXT NOT NULL,
    selection     TEXT NOT NULL,
    line          REAL,
    bookmaker     TEXT NOT NULL,
    odds          REAL NOT NULL,
    odds_retrieved_at TEXT,
    model_prob    REAL NOT NULL,
    market_prob   REAL,
    final_prob    REAL NOT NULL,
    fair_odds     REAL NOT NULL,
    ev            REAL NOT NULL,
    ev_lower      REAL NOT NULL,
    prob_sd       REAL,
    stake_units   REAL NOT NULL,
    model_version TEXT NOT NULL,
    rank          INTEGER,
    evidence_json TEXT,
    source_urls   TEXT,
    is_paper      INTEGER NOT NULL DEFAULT 1,   -- always 1: simulated only
    -- settlement (the only mutable columns)
    status        TEXT NOT NULL DEFAULT 'open', -- open|won|lost|push|half_won|half_lost|void
    pnl_units     REAL,
    closing_odds  REAL,
    clv           REAL,
    settled_at    TEXT,
    UNIQUE(event_id, market, selection, line)
);

CREATE TRIGGER IF NOT EXISTS trg_recs_immutable
BEFORE UPDATE OF rec_id, event_id, published_at, market, selection, line, bookmaker,
                 odds, model_prob, market_prob, final_prob, fair_odds, ev, ev_lower,
                 stake_units, model_version, evidence_json, is_paper
ON recommendations
BEGIN
    SELECT RAISE(ABORT, 'published recommendations are immutable');
END;

CREATE TRIGGER IF NOT EXISTS trg_recs_nodelete
BEFORE DELETE ON recommendations
BEGIN
    SELECT RAISE(ABORT, 'published recommendations cannot be deleted');
END;

-- Claude's contextual research. Qualitative risk flags, never probability edits.
CREATE TABLE IF NOT EXISTS research_notes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id      TEXT NOT NULL REFERENCES events(event_id),
    category      TEXT NOT NULL,     -- injury|lineup|motivation|schedule|weather|travel|other
    claim         TEXT NOT NULL,
    evidence_type TEXT NOT NULL CHECK (evidence_type IN ('verified_fact','interpretation','speculation')),
    direction     TEXT CHECK (direction IN ('supports','against','neutral')),
    source_url    TEXT,
    retrieved_at  TEXT,
    created_by    TEXT NOT NULL DEFAULT 'claude',
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job         TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    status      TEXT NOT NULL,       -- running|ok|error|partial
    details     TEXT
);

CREATE TABLE IF NOT EXISTS provider_status (
    provider     TEXT PRIMARY KEY,
    last_attempt TEXT,
    last_success TEXT,
    last_error   TEXT,
    rows_last    INTEGER
);

CREATE TABLE IF NOT EXISTS backtest_results (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    model_version TEXT NOT NULL,
    label        TEXT NOT NULL,
    config_json  TEXT,
    metrics_json TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


@contextmanager
def job(con: sqlite3.Connection, name: str):
    """Log a job run; never swallow exceptions silently."""
    cur = con.execute("INSERT INTO job_runs(job, started_at, status) VALUES (?,?,?)",
                      (name, utcnow(), "running"))
    jid = cur.lastrowid
    con.commit()
    details: dict = {}
    try:
        yield details
        status = details.pop("_status", "ok")
    except Exception as e:  # noqa: BLE001
        con.rollback()
        details["error"] = f"{type(e).__name__}: {e}"
        con.execute("UPDATE job_runs SET finished_at=?, status='error', details=? WHERE id=?",
                    (utcnow(), json.dumps(details, default=str), jid))
        con.commit()
        raise
    con.execute("UPDATE job_runs SET finished_at=?, status=?, details=? WHERE id=?",
                (utcnow(), status, json.dumps(details, default=str), jid))
    con.commit()


def provider_ok(con, provider: str, rows: int) -> None:
    now = utcnow()
    con.execute("""INSERT INTO provider_status(provider,last_attempt,last_success,rows_last)
                   VALUES (?,?,?,?) ON CONFLICT(provider) DO UPDATE SET
                   last_attempt=excluded.last_attempt, last_success=excluded.last_success,
                   rows_last=excluded.rows_last""", (provider, now, now, rows))


def provider_err(con, provider: str, err: str) -> None:
    now = utcnow()
    con.execute("""INSERT INTO provider_status(provider,last_attempt,last_error)
                   VALUES (?,?,?) ON CONFLICT(provider) DO UPDATE SET
                   last_attempt=excluded.last_attempt, last_error=excluded.last_error""",
                (provider, now, f"{now} {err}"[:500]))
