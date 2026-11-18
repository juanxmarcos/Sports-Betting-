"""Twice-a-day refresh with backup runs (issue #53, two slots since issue #63).

`.github/workflows/daily.yml` runs the data pipeline twice a day (New York time), each slot with a
primary cron at an unusual minute (GitHub drops many scheduled runs, most of all at the top of the
hour) plus later backup crons:

* morning slot: any time before 14:00 New York (primary 10:47 UTC = 5:47 AM EST / 6:47 AM EDT);
* evening slot: 14:00 New York or later (primary 22:47 UTC = 5:47 PM EST / 6:47 PM EDT).

A backup cron must exit early (no Odds API calls, no commit) when ITS slot already had a successful
run that New York day. A morning success never skips an evening backup.

The proof of success is `data/last_daily_run.json`, written by `python -m sbi daily` only after
the pipeline finished. It reaches `main` only through the workflow's commit step, so a run that
failed, or whose push failed, leaves the marker without that slot and a backup run goes ahead.

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
EVENING_FROM_HOUR = 14                 # New York hour at which the evening slot starts
SLOTS = ("morning", "evening")


def path() -> Path:
    return Path(os.environ.get("SBI_DATA_DIR", ROOT / "data")) / "last_daily_run.json"


def ny_day(t: datetime) -> str:
    return t.astimezone(NY).date().isoformat()


def slot(t: datetime) -> str:
    """"morning" before 14:00 New York time, "evening" from 14:00 to midnight."""
    return "morning" if t.astimezone(NY).hour < EVENING_FROM_HOUR else "evening"


def _runs(p: Path) -> dict[str, datetime]:
    """Successful runs recorded in the marker, by slot (timezone-aware datetimes only).
    A marker from before issue #63 (only `completed_at`) counts for the slot of that time."""
    try:
        data = json.loads(p.read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    raw = data.get("runs")
    if not isinstance(raw, dict):
        raw = {}
        try:
            at = datetime.fromisoformat(data["completed_at"])
            if at.tzinfo is not None:
                raw = {slot(at): data["completed_at"]}
        except (KeyError, TypeError, ValueError):
            pass
    out = {}
    for k, v in raw.items():
        try:
            at = datetime.fromisoformat(v)
        except (TypeError, ValueError):
            continue
        if k in SLOTS and at.tzinfo is not None:
            out[k] = at
    return out


def mark(now: datetime, p: Path | None = None) -> Path:
    """Record that the daily pipeline completed at `now` (timezone-aware) in `now`'s slot. The other
    slot's success is kept when it was on the same New York day."""
    p = p or path()
    runs = {k: v.isoformat() for k, v in _runs(p).items() if ny_day(v) == ny_day(now)}
    runs[slot(now)] = now.isoformat()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"completed_at": now.isoformat(), "ny_date": ny_day(now), "slot": slot(now),
                             "runs": {k: runs[k] for k in SLOTS if k in runs}}, indent=1) + "\n")
    return p


def ran_this_slot(now: datetime, p: Path | None = None) -> bool:
    """True when a run completed earlier in `now`'s slot on `now`'s New York day. Missing,
    unreadable, future-dated or naive markers count as 'not run', so the backup goes ahead."""
    at = _runs(p or path()).get(slot(now))
    if at is None or at > now:
        return False
    return ny_day(at) == ny_day(now) and slot(at) == slot(now)


def main(argv=None) -> int:
    """Print `skip=true` or `skip=false` (for $GITHUB_OUTPUT) and a human-readable reason."""
    now = datetime.now(timezone.utc)
    skip = ran_this_slot(now)
    print(f"skip={'true' if skip else 'false'}")
    print((f"this {slot(now)}'s run already succeeded; backup run skipped" if skip
           else f"no successful {slot(now)} run yet; running") + f" (New York day {ny_day(now)})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
