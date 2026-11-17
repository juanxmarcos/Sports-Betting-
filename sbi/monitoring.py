"""Local-only storage for monitoring leagues. Opt-in; never part of the scheduled job or the public database.

Why a separate file. `data/sbi.sqlite` is committed to a public repository, so every quote in it is
republished. football-data.co.uk offers its files free for testing betting systems, and no permission to
republish its bookmaker odds was found (docs/DATA_SOURCES.md, "Source-use and redistribution rights").
Until the owner has that permission in writing, fixtures, odds and results for the monitoring leagues
(sbi/leagues.py) are kept out of the public database:

  * `python -m sbi daily` and the GitHub workflow ingest the ten active leagues only, exactly as before;
  * `python -m sbi monitor-leagues` is the only thing that fetches the monitoring leagues, and it writes
    to `data/local/monitoring.sqlite`, which is gitignored. It refuses to run if that path is the public
    database or is not ignored by git.

What is stored there is a published snapshot: each quote carries the file's publication time. It was
collected earlier, is not timed by the bookmaker and is not an executable price. Nothing in this file is
ever priced, published or shown on the site; `pipeline.analyse` reads the public database and the active
leagues only.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import config, db, leagues
from .sources import football_data as fd
from .sources.http import SourceBlocked

RESULTS_MAX_AGE_H = 24.0        # nothing is priced from these files: once a day is enough
QUOTE_BASIS = "file_published"  # see coverage.TIMESTAMP_BASIS
NOTICE = ("Local research copy of football-data.co.uk files for monitoring leagues. Not for redistribution: "
          "do not commit or publish this file. Quotes are a published snapshot stamped with the file's "
          "publication time; they are observed, not bookmaker-timed, and are not executable prices.")


class NotLocalOnly(RuntimeError):
    """The monitoring database path could end up published. Nothing was fetched or written."""


def db_path() -> Path:
    return Path(os.environ.get("SBI_MONITORING_DB") or (config.DATA_DIR / "local" / "monitoring.sqlite"))


def _git_ignored(path: Path) -> bool | None:
    """True/False if `path` is inside a git work tree; None if it is not in one (or git is unavailable)."""
    parent = next((p for p in [path.parent, *path.parent.parents] if p.exists()), None)
    if parent is None:
        return None
    try:
        inside = subprocess.run(["git", "-C", str(parent), "rev-parse", "--is-inside-work-tree"],
                                capture_output=True, text=True, timeout=10)
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return None
        r = subprocess.run(["git", "-C", str(parent), "check-ignore", "-q", str(path)], capture_output=True, timeout=10)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return None


def check_local_only(path: Path | None = None) -> Path:
    """Return the path if it is safe; raise NotLocalOnly if it is the public database or git would track it."""
    path = (path or db_path()).resolve()
    if path == Path(config.DB_PATH).resolve():
        raise NotLocalOnly(f"{path} is the public database; monitoring leagues must not be stored there")
    if _git_ignored(path) is False:
        raise NotLocalOnly(f"{path} is inside a git repository and not ignored, so it could be committed and published")
    return path


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = check_local_only(path)
    con = db.connect(path)
    con.execute("CREATE TABLE IF NOT EXISTS local_notice (id INTEGER PRIMARY KEY CHECK (id = 1), notice TEXT, quote_basis TEXT)")
    con.execute("INSERT OR REPLACE INTO local_notice VALUES (1, ?, ?)", (NOTICE, QUOTE_BASIS))
    con.commit()
    return con


def connect_ro(path: Path | None = None) -> sqlite3.Connection | None:
    """Read-only handle for reports, or None when the local database has never been created."""
    path = path or db_path()
    if not Path(path).exists():
        return None
    con = sqlite3.connect(f"file:{Path(path)}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def ingest(now: datetime | None = None, path: Path | None = None) -> dict:
    """Fetch fixtures, snapshot odds and results for the monitoring leagues into the LOCAL database."""
    now = now or datetime.now(timezone.utc).replace(microsecond=0)
    con = connect(path)                      # raises before any request if the path is not local-only
    out: dict = {"database": str(check_local_only(path)), "local_only": True, "quote_basis": QUOTE_BASIS,
                 "quotes_are": "observed in a published file; not bookmaker-timed; not executable"}
    try:
        try:
            out["fixtures"] = fd.ingest_fixtures(con, leagues.monitoring())
            db.provider_ok(con, "football-data:fixtures", out["fixtures"]["events"])
        except (SourceBlocked, RuntimeError) as e:
            db.provider_err(con, "football-data:fixtures", str(e))
            out["fixtures_error"] = str(e)
        season = fd.season_code(now.date())
        for div in leagues.monitoring():
            try:
                out[div] = fd.ingest_results(con, div, season, max_age_hours=RESULTS_MAX_AGE_H)
                db.provider_ok(con, f"football-data:{div}", out[div]["events"])
            except (SourceBlocked, RuntimeError) as e:      # one division failing never stops the others
                db.provider_err(con, f"football-data:{div}", str(e))
                out[f"{div}_error"] = str(e)
        con.commit()
    finally:
        con.close()
    return out
