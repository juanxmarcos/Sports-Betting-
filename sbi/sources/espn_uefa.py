"""UEFA club competitions from the ESPN public scoreboard (issue #114).

Champions League, Europa League and Conference League games were missing everywhere (fixtures, odds
and results): `espn_club.py` reads only the domestic leagues and the international connector reads
only national-team competitions. This connector reads the free, keyless ESPN scoreboards
`uefa.champions`, `uefa.europa` and `uefa.europa.conf` for the same window as the club connector
(`espn_club.BACK_DAYS` back, `espn_club.AHEAD_DAYS` ahead, plus missed-run catch-up dates from
`sbi/catchup.py`), one request per competition per day:

* Events get their own league codes (`UCL`, `UEL`, `UECL`) and a stable id built from the ESPN game id
  (`football:<code>:<UTC date of first sighting>:<espn id>`). A re-run finds the game by its ESPN id
  (`espn_event_ids`) and refreshes it, never creating a duplicate; a game moved by ESPN keeps its id.
* Team names are mapped to the football-data names Doyen already uses where that is certain
  (`espn_club.ALIASES`, then an accent-insensitive exact comparison against the stored teams of the
  domestic leagues). A team that cannot be mapped keeps its ESPN name; nothing is guessed.
* Scoreboard odds (DraftKings) are stored for upcoming games. The price-only ESPN summary read in
  `espn_extra.enrich_events` adds the extra books of the soccer `odds` block (the games are listed in
  `espn_event_ids` like the club games), and The Odds API keys in `odds_api.UEFA` add more.
* Final scores fill games that are still unsettled. A game decided after extra time or penalties is
  NOT filled automatically (the ESPN score may include extra time, while match-result and goal markets
  settle on 90 minutes); it is reported in `extra_time_skipped` and stays open.

Doyen's domestic Dixon-Coles models cannot rate cross-league matches reliably, so no model runs on these
games: parlays and single picks use the de-vigged market consensus (`parlay_estimated`), labelled
"Probability: market consensus". Nothing here changes a model, a threshold or a published pick.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta

from .. import db, leagues
from . import football_data as fd
from .espn_club import AHEAD_DAYS, BACK_DAYS, SOURCE, _ensure, known_teams, near_event, resolve, scoreboard

# league code -> (ESPN soccer league slug, display name)
COMPETITIONS = {
    "UCL": ("uefa.champions", "Champions League"),
    "UEL": ("uefa.europa", "Europa League"),
    "UECL": ("uefa.europa.conf", "Conference League"),
}
CODES = tuple(COMPETITIONS)
PROB_NOTE = "Probability: market consensus"
# ESPN status names of games not decided in 90 minutes (results are not filled automatically)
EXTRA_TIME_STATES = ("STATUS_FINAL_AET", "STATUS_FINAL_PEN", "STATUS_END_OF_EXTRATIME", "STATUS_FINAL_ET")


def is_uefa(league: str | None) -> bool:
    return league in COMPETITIONS


def event_id(code: str, kickoff: datetime, espn_id: str) -> str:
    return f"football:{code}:{kickoff.strftime('%Y%m%d')}:{espn_id}"


def domestic_teams(con, now: datetime) -> set[str]:
    """football-data team names of every active domestic league (the names the rest of Doyen uses)."""
    out: set[str] = set()
    for div in leagues.active():
        out |= known_teams(con, div, now)
    return out


def team_name(display: str, short: str | None, known: set[str]) -> str:
    """football-data name when it can be mapped with certainty, otherwise ESPN's display name."""
    return resolve(display, short, known) or (display or short or "").strip()


def _by_espn_id(con, code: str, espn_id: str):
    return con.execute("""SELECT e.event_id, e.kickoff_utc, e.status, e.home_score FROM espn_event_ids x
                          JOIN events e USING(event_id) WHERE x.espn_id=? AND e.league=?""",
                       (str(espn_id), code)).fetchone()


def store(con, code: str, events: list[dict], now: datetime, known: set[str]) -> dict:
    """Create/refresh UEFA club events from parsed ESPN events. Returns counts for the run log."""
    _ensure(con)
    con.execute("CREATE TABLE IF NOT EXISTS event_meta (event_id TEXT PRIMARY KEY, neutral INTEGER, competition TEXT)")
    lg, label = COMPETITIONS[code]
    out = {"created": 0, "existing": 0, "results_filled": 0, "odds": 0, "skipped_past": 0,
           "extra_time_skipped": [], "unmapped": []}
    ts = db.utcnow()
    for ev in events:
        home = team_name(*ev["espn_home"], known)
        away = team_name(*ev["espn_away"], known)
        if not home or not away or home == away:
            continue
        for raw, got in ((ev["espn_home"][0], home), (ev["espn_away"][0], away)):
            if got == raw and got not in known and raw not in out["unmapped"]:
                out["unmapped"].append(raw)          # kept under its ESPN name (information only)
        ko = ev["kickoff_utc"]
        url = f"https://www.espn.com/soccer/match/_/gameId/{ev['espn_id']}"
        row = _by_espn_id(con, code, ev["espn_id"]) or near_event(con, code, home, away, ko)
        if row is not None:
            eid = row["event_id"]
            out["existing"] += 1
            if row["status"] == "scheduled" and not ev["completed"] and row["kickoff_utc"] != ko.isoformat():
                con.execute("UPDATE events SET kickoff_utc=?, updated_at=? WHERE event_id=?", (ko.isoformat(), ts, eid))
            if ev["completed"] and row["status"] == "scheduled" and row["home_score"] is None:
                if ev.get("state") in EXTRA_TIME_STATES:
                    out["extra_time_skipped"].append(eid)
                else:
                    con.execute("""UPDATE events SET status='finished', home_score=?, away_score=?, updated_at=?
                                   WHERE event_id=? AND status='scheduled' AND home_score IS NULL""",
                                (ev["hg"], ev["ag"], ts, eid))
                    out["results_filled"] += 1
        else:
            if ev["completed"] or ko <= now:
                out["skipped_past"] += 1          # only games first seen before kick-off are created
                continue
            eid = event_id(code, ko, ev["espn_id"])
            con.execute("""INSERT OR IGNORE INTO events(event_id,sport,league,season,kickoff_utc,home,away,status,
                                                        source,source_url,updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (eid, "football", code, fd.season_code(ko.date()), ko.isoformat(), home, away,
                         "scheduled", SOURCE, url, ts))
            out["created"] += 1
        con.execute("INSERT OR REPLACE INTO espn_event_ids VALUES (?,?,?,?)", (eid, ev["espn_id"], lg, ts))
        con.execute("INSERT OR IGNORE INTO event_meta VALUES (?,?,?)", (eid, None, label))
        if not ev["completed"] and ko > now:
            for bk, market, sel, line, px, kind in ev["odds"]:
                k = "pre" if kind == "current" else "open"
                cur = con.execute("""INSERT OR IGNORE INTO odds(event_id,bookmaker,market,selection,line,price,kind,
                                     source,source_url,retrieved_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                                  (eid, bk, market, sel, line, px, k, SOURCE, url, ts))
                out["odds"] += cur.rowcount
    return out


def ingest(con, now: datetime, ahead_days: int = AHEAD_DAYS, back_days: int = BACK_DAYS,
           polite_delay: float = 0.15) -> dict:
    """Read each UEFA scoreboard for every day in [today - back, today + ahead] plus catch-up dates."""
    from ..catchup import stale_dates
    out = {"competitions": {}, "created": 0, "results_filled": 0, "odds": 0, "errors": []}
    known = domestic_teams(con, now)
    for code, (lg, _label) in COMPETITIONS.items():
        tot = {"created": 0, "existing": 0, "results_filled": 0, "odds": 0, "skipped_past": 0,
               "extra_time_skipped": [], "unmapped": []}
        days = [now.date() + timedelta(days=k) for k in range(-back_days, ahead_days + 1)]
        days += sorted(d for d in stale_dates(con, now, code) if d not in days)   # missed-run catch-up
        for d in days:
            try:
                evs = scoreboard(lg, d)
            except Exception as e:  # noqa: BLE001 - one competition-day failing never stops the rest
                out["errors"].append(db.redact(f"{lg} {d}: {e}")[:200])
                continue
            r = store(con, code, evs, now, known)
            for key in ("created", "existing", "results_filled", "odds", "skipped_past"):
                tot[key] += r[key]
            for key in ("extra_time_skipped", "unmapped"):
                tot[key] += [u for u in r[key] if u not in tot[key]]
            time.sleep(polite_delay)
        tot["unmapped"] = tot["unmapped"][:20]
        out["competitions"][code] = tot
        for key in ("created", "results_filled", "odds"):
            out[key] += tot[key]
    out["errors"] = out["errors"][:10]
    con.commit()
    return out
