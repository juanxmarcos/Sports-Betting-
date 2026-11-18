"""Quotes fetched during a run must be visible to that run's parlay build (2026-11-18 fix)."""
from datetime import datetime, timedelta, timezone

from sbi import db, parlay_estimated as pe
from sbi.pipeline import build_clock


def test_build_clock_advances_by_elapsed_time():
    now = datetime(2026, 11, 18, 17, 8, 33, tzinfo=timezone.utc)
    assert build_clock(now, 100.0, 100.0) == now + timedelta(seconds=1)
    assert build_clock(now, 100.0, 190.4) == now + timedelta(seconds=91)
    assert build_clock(now, 100.0, 50.0) == now + timedelta(seconds=1)      # never goes back


def test_quote_fetched_after_run_start_is_seen_with_build_clock(tmp_path, monkeypatch):
    monkeypatch.setenv("SBI_DATA_DIR", str(tmp_path))
    con = db.connect(tmp_path / "t.sqlite")
    start = datetime(2026, 11, 18, 17, 8, 33, tzinfo=timezone.utc)
    fetched = start + timedelta(seconds=4)                 # stamped by the real clock mid-run
    con.execute("""INSERT INTO events(event_id,sport,league,season,kickoff_utc,home,away,status,source,source_url,updated_at)
                   VALUES ('e1','football','E0','2627','2026-11-21T12:30:00+00:00','A','B','scheduled','s','u',?)""",
                (start.isoformat(),))
    con.execute("""INSERT INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,source_url,retrieved_at)
                   VALUES ('e1','DraftKings','1X2','H',NULL,1.4,'pre','s','u',?)""", (fetched.isoformat(),))
    kickoff = datetime(2026, 11, 21, 12, 30, tzinfo=timezone.utc)
    assert pe.fresh_books(con, "e1", start, kickoff, same_day=False) == {}          # the old bug
    assert pe.fresh_books(con, "e1", build_clock(start, 0.0, 90.0), kickoff, same_day=False)
