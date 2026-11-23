"""Upcoming club-soccer fixtures from the ESPN public scoreboard (issue #66).

football-data.co.uk publishes `fixtures.csv` only about twice a week (Tue/Fri), so after an
international break the active leagues can have no stored upcoming events for days. The Odds API
run then skips every club competition ("skipped_no_matching_event") and no prices are stored.

This connector reads the free, keyless ESPN soccer scoreboard for each active league, one request
per league per day, for the next `AHEAD_DAYS` days (and the last `BACK_DAYS` days for results):

* Team names are mapped to the football-data names Doyen already uses (explicit aliases, then an
  accent-insensitive exact comparison against the league's stored teams). A team that cannot be
  mapped is reported and its game is skipped: nothing is guessed.
* Event IDs use the football-data format (`football:<div>:<UTC date>:<home>:<away>`), so when
  football-data later lists the same game it updates the SAME event. A game already stored for
  the same league and teams within +/-3 days is reused, never duplicated.
* Scoreboard odds (DraftKings) are stored for upcoming games, as for internationals.
* Final scores fill events that are still unsettled, so club games created here settle even when
  football-data is late. A football-data score already stored is never overwritten.

Only the active allowlist (`leagues.active()`) is read. Nothing here changes a model, a threshold or
a published pick.
"""
from __future__ import annotations

import json
import time
import unicodedata
from datetime import date, datetime, timedelta

from .. import db, leagues
from . import football_data as fd
from .http import fetch
from .international import ESPN, SOURCE_ESPN, _parse_event

SOURCE = SOURCE_ESPN
AHEAD_DAYS = 7          # issue #66: fixtures for the next 7 days
BACK_DAYS = 2           # recent days re-read for final scores
NEAR_DAYS = 3           # same league + teams within this many days = the same game

# football-data division -> ESPN soccer league slug
ESPN_LEAGUES = {
    "E0": "eng.1", "E1": "eng.2", "SP1": "esp.1", "D1": "ger.1", "I1": "ita.1", "F1": "fra.1",
    "N1": "ned.1", "P1": "por.1", "B1": "bel.1", "SC0": "sco.1",
}

# ESPN display name -> football-data name, where neither ESPN's display nor short name matches
# (checked against the ESPN scoreboards and the stored football-data teams on 2026-11-18).
ALIASES = {
    # England
    "Manchester United": "Man United", "Manchester City": "Man City", "Nottingham Forest": "Nott'm Forest",
    "Tottenham Hotspur": "Tottenham", "Lincoln City": "Lincoln", "Norwich City": "Norwich",
    "Wolverhampton Wanderers": "Wolves", "Sheffield Wednesday": "Sheffield Weds",
    # Spain
    "Athletic Club": "Ath Bilbao", "Atlético Madrid": "Ath Madrid", "Celta Vigo": "Celta",
    "Deportivo": "La Coruna", "Deportivo La Coruña": "La Coruna", "Espanyol": "Espanol",
    "Racing Santander": "Santander", "Rayo Vallecano": "Vallecano", "Real Sociedad": "Sociedad",
    "Real Betis": "Betis",
    # France
    "Le Havre AC": "Le Havre", "Paris Saint-Germain": "Paris SG",
    # Germany
    "Borussia Mönchengladbach": "M'gladbach", "Eintracht Frankfurt": "Ein Frankfurt", "FC Cologne": "FC Koln",
    "1. FC Köln": "FC Koln",
    # Italy
    "AS Roma": "Roma", "Internazionale": "Inter",
    # Netherlands
    "ADO Den Haag": "Den Haag", "FC Groningen": "Groningen", "FC Twente": "Twente", "FC Utrecht": "Utrecht",
    "Fortuna Sittard": "For Sittard", "NEC Nijmegen": "Nijmegen", "PEC Zwolle": "Zwolle",
    # Portugal
    "Académico de Viseu": "Academico Viseu", "Braga": "Sp Braga", "SC Braga": "Sp Braga", "FC Porto": "Porto",
    "Sporting CP": "Sp Lisbon", "Vitória de Guimaraes": "Guimaraes", "Vitória de Guimarães": "Guimaraes",
    "Estoril Praia": "Estoril", "C.D. Nacional": "Nacional",
    # Belgium
    "KAA Gent": "Gent", "KV Kortrijk": "Kortrijk", "KV Mechelen": "Mechelen", "OH Leuven": "Oud-Heverlee Leuven",
    "Royal Charleroi SC": "Charleroi", "Sint-Truidense": "St Truiden", "Standard Liege": "Standard",
    "Union St.-Gilloise": "St. Gilloise", "Waasland-Beveren": "Beveren", "Zulte-Waregem": "Waregem",
    "RAAL La Louvière": "RAAL La Louviere",
    # Scotland
    "Heart of Midlothian": "Hearts",
}


def _fold(s: str) -> str:
    """Accent- and case-insensitive form, for exact comparison only (no fuzzy matching)."""
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().strip().lower()


def known_teams(con, div: str, now: datetime, days: int = 400) -> set[str]:
    """Team names football-data has used for this division recently (the names the model knows)."""
    rows = con.execute("SELECT home, away FROM events WHERE league=? AND source=? AND kickoff_utc >= ?",
                       (div, fd.SOURCE, (now - timedelta(days=days)).isoformat())).fetchall()
    return {t for r in rows for t in (r["home"], r["away"]) if t}


def resolve(display: str, short: str | None, known: set[str]) -> str | None:
    """football-data name for an ESPN team, or None when it cannot be mapped with certainty."""
    by_fold = {}
    for k in known:
        by_fold.setdefault(_fold(k), set()).add(k)
    for cand in (ALIASES.get(display), ALIASES.get((short or "").strip()), display, short):
        if not cand:
            continue
        if cand in known:
            return cand
        hit = by_fold.get(_fold(cand), set())
        if len(hit) == 1:
            return next(iter(hit))
    return None


def _team_names(e: dict) -> dict:
    c = e["competitions"][0]
    return {t["homeAway"]: (t["team"].get("displayName") or "", t["team"].get("shortDisplayName"))
            for t in c["competitors"]}


def scoreboard(lg: str, d: date, max_age_hours: float = 0.9) -> list[dict]:
    """Parsed events of one ESPN league-day: kickoff, status, scores, odds, raw ESPN team names."""
    content, _ = fetch(ESPN.format(lg=lg, d=d.strftime("%Y%m%d")), max_age_hours=max_age_hours)
    data = json.loads(content)
    out = []
    for e in data.get("events", []):
        try:
            x = _parse_event(e, lg)
            names = _team_names(e)
            if x is None or "home" not in names or "away" not in names:
                continue
            x["espn_home"], x["espn_away"] = names["home"], names["away"]
        except (KeyError, TypeError, ValueError, AttributeError, IndexError) as ex:
            print(f"warning: skipped malformed ESPN club event {e.get('id')} ({lg}): {ex}")
            continue
        out.append(x)
    return out


def near_event(con, div: str, home: str, away: str, kickoff: datetime, days: int = NEAR_DAYS):
    """The stored event for the same league and teams closest to `kickoff` within +/-days, or None."""
    rows = con.execute("""SELECT event_id, kickoff_utc, status, source, home_score FROM events
                          WHERE league=? AND home=? AND away=? AND kickoff_utc BETWEEN ? AND ?""",
                       (div, home, away, (kickoff - timedelta(days=days)).isoformat(),
                        (kickoff + timedelta(days=days)).isoformat())).fetchall()
    if not rows:
        return None
    return min(rows, key=lambda r: abs((datetime.fromisoformat(r["kickoff_utc"]) - kickoff).total_seconds()))


def _ensure(con):
    con.execute("""CREATE TABLE IF NOT EXISTS espn_event_ids (
                     event_id TEXT PRIMARY KEY, espn_id TEXT, espn_league TEXT, updated_at TEXT)""")


def store(con, div: str, lg: str, events: list[dict], now: datetime, known: set[str]) -> dict:
    """Create/refresh club events from parsed ESPN events. Returns counts for the run log."""
    _ensure(con)
    out = {"created": 0, "existing": 0, "results_filled": 0, "odds": 0, "unmapped": [], "skipped_past": 0}
    ts = db.utcnow()
    for ev in events:
        home = resolve(*ev["espn_home"], known)
        away = resolve(*ev["espn_away"], known)
        if not home or not away or home == away:
            for raw, got in ((ev["espn_home"][0], home), (ev["espn_away"][0], away)):
                if not got and raw not in out["unmapped"]:
                    out["unmapped"].append(raw)
            continue
        ko = ev["kickoff_utc"]
        url = f"https://www.espn.com/soccer/match/_/gameId/{ev['espn_id']}"
        row = near_event(con, div, home, away, ko)
        if row is not None:
            eid = row["event_id"]
            out["existing"] += 1
            if row["status"] == "scheduled" and row["source"] == SOURCE and not ev["completed"] \
                    and row["kickoff_utc"] != ko.isoformat():
                # an ESPN-created game moved: follow ESPN until football-data takes it over
                con.execute("UPDATE events SET kickoff_utc=?, updated_at=? WHERE event_id=?", (ko.isoformat(), ts, eid))
            if ev["completed"] and row["status"] == "scheduled" and row["home_score"] is None:
                con.execute("""UPDATE events SET status='finished', home_score=?, away_score=?, updated_at=?
                               WHERE event_id=? AND status='scheduled' AND home_score IS NULL""",
                            (ev["hg"], ev["ag"], ts, eid))
                out["results_filled"] += 1
        else:
            if ev["completed"] or ko <= now:
                out["skipped_past"] += 1          # results for unknown games come from football-data
                continue
            eid = fd.event_id(div, ko, home, away)
            con.execute("""INSERT OR IGNORE INTO events(event_id,sport,league,season,kickoff_utc,home,away,status,
                                                        source,source_url,updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (eid, "football", div, fd.season_code(ko.date()), ko.isoformat(), home, away,
                         "scheduled", SOURCE, url, ts))
            out["created"] += 1
        con.execute("INSERT OR REPLACE INTO espn_event_ids VALUES (?,?,?,?)", (eid, ev["espn_id"], lg, ts))
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
    """Read the ESPN scoreboard for each active league and day in [today - back, today + ahead]."""
    out = {"leagues": {}, "created": 0, "results_filled": 0, "odds": 0, "errors": []}
    for div in leagues.active():
        lg = ESPN_LEAGUES.get(div)
        if not lg:
            continue
        known = known_teams(con, div, now)
        if not known:
            out["errors"].append(f"{div}: no stored football-data teams to map ESPN names to")
            continue
        tot = {"created": 0, "existing": 0, "results_filled": 0, "odds": 0, "unmapped": [], "skipped_past": 0}
        from ..catchup import stale_dates
        days = [now.date() + timedelta(days=k) for k in range(-back_days, ahead_days + 1)]
        days += sorted(d for d in stale_dates(con, now, div) if d not in days)   # missed-run catch-up
        for d in days:
            try:
                evs = scoreboard(lg, d)
            except Exception as e:  # noqa: BLE001 - one league-day failing never stops the rest
                out["errors"].append(db.redact(f"{lg} {d}: {e}")[:200])
                continue
            r = store(con, div, lg, evs, now, known)
            for key in ("created", "existing", "results_filled", "odds", "skipped_past"):
                tot[key] += r[key]
            tot["unmapped"] += [u for u in r["unmapped"] if u not in tot["unmapped"]]
            time.sleep(polite_delay)
        out["leagues"][div] = tot
        for key in ("created", "results_filled", "odds"):
            out[key] += tot[key]
    out["errors"] = out["errors"][:10]
    con.commit()
    return out
