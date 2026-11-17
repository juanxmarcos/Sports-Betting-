"""Once-a-day refresh with backup runs (issue #53).

`.github/workflows/daily.yml` runs the data pipeline once each morning (New York time) at an
unusual minute, because GitHub drops many scheduled runs, most of all at the top of the hour.
Later backup crons start the same workflow but must exit early (no Odds API calls, no commit)
when a successful daily run already happened that New York day.

The proof of success is `data/last_daily_run.json`, written by `python -m sbi daily` only after
the pipeline finished. It reaches `main` only through the workflow's commit step, so a run that
failed, or whose push failed, leaves the marker on the previous day and a backup run goes ahead.

Standard library only: the workflow calls `python -m sbi.run_marker` before installing the
project requirements, so a skipped backup costs seconds.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")      # the site's publishing day
ROOT = Path(__file__).resolve().parent.parent


def path() -> Path:
    return Path(os.environ.get("SBI_DATA_DIR", ROOT / "data")) / "last_daily_run.json"


def ny_day(t: datetime) -> str:
    return t.astimezone(NY).date().isoformat()


def mark(now: datetime, p: Path | None = None) -> Path:
    """Record that the daily pipeline completed at `now` (timezone-aware)."""
    p = p or path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"completed_at": now.isoformat(), "ny_date": ny_day(now)}, indent=1) + "\n")
    return p


def ran_today(now: datetime, p: Path | None = None) -> bool:
    """True when a daily run completed earlier on `now`'s New York day. Missing, unreadable,
    future-dated or naive markers count as 'not run', so the backup goes ahead."""
    p = p or path()
    try:
        at = datetime.fromisoformat(json.loads(p.read_text())["completed_at"])
    except (OSError, ValueError, KeyError, TypeError):
        return False
    if at.tzinfo is None or at > now:
        return False
    return ny_day(at) == ny_day(now)


def main(argv=None) -> int:
    """Print `skip=true` or `skip=false` (for $GITHUB_OUTPUT) and a human-readable reason."""
    now = datetime.now(timezone.utc)
    skip = ran_today(now)
    print(f"skip={'true' if skip else 'false'}")
    print(("today's daily run already succeeded; backup run skipped" if skip
           else "no successful daily run yet today; running") + f" (New York day {ny_day(now)})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
