"""The Odds API (the-odds-api.com) connector - free tier, ~500 credits/month.

Key: environment variable ODDS_API_KEY (GitHub Actions secret). Never logged or stored:
every stored URL has the key stripped. Without a key the connector is skipped.

Credit model (v4): /sports and /sports/{key}/events are free; /sports/{key}/odds costs
len(markets) x len(regions) credits. We query regions=eu (includes Pinnacle and Betfair
Exchange - the sharp references) and markets h2h,totals = 2 credits per competition.

Budgeting: per-run budget = min(MAX_CREDITS_PER_RUN, remaining / runs left this month),
spent only on competitions with events in the next 36h, internationals first (they have
no other multi-bookmaker source), then club leagues.
"""
from __future__ import annotations

import calendar
import difflib
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone

import requests

from .. import config, db

BASE = "https://api.the-odds-api.com/v4"
SOURCE = "the-odds-api.com"
REGIONS = "eu"
MARKETS = "h2h,totals"   # btts is not offered on the bulk /odds endpoint (HTTP 422), only per event
MAX_CREDITS_PER_RUN = 12   # several competitions per run; the DAILY allowance is the real limit
RUNS_PER_DAY = 2
RESERVE = 20  # never spend the last credits of the month

# The Odds API sport key -> our league code. Internationals map to the ESPN-based INT:* events.
INTERNATIONAL = {
    "soccer_uefa_nations_league": "INT:uefa.nations",
    "soccer_fifa_world_cup_qualifiers_europe": "INT:fifa.worldq.uefa",
    "soccer_fifa_world_cup_qualifiers_south_america": "INT:fifa.worldq.conmebol",
    "soccer_uefa_european_championship_qualification": "INT:uefa.euroq",
    "soccer_international_friendlies": "INT:fifa.friendly",
    "soccer_africa_cup_of_nations_qualification": "INT:caf.nations_qual",
    "soccer_concacaf_nations_league": "INT:concacaf.nations.league",
    "soccer_fifa_world_cup": "INT:fifa.world", "soccer_uefa_european_championship": "INT:uefa.euro",
    "soccer_africa_cup_of_nations": "INT:caf.nations", "soccer_copa_america": "INT:conmebol.america",
    "soccer_concacaf_gold_cup": "INT:concacaf.gold",
}
US = {"americanfootball_nfl": "NFL", "basketball_nba": "NBA"}
US_MARKETS = "h2h,spreads,totals"
CLUB = {
    "soccer_epl": "E0", "soccer_efl_champ": "E1", "soccer_spain_la_liga": "SP1",
    "soccer_germany_bundesliga": "D1", "soccer_italy_serie_a": "I1", "soccer_france_ligue_one": "F1",
    "soccer_netherlands_eredivisie": "N1", "soccer_portugal_primeira_liga": "P1",
    "soccer_belgium_first_div": "B1", "soccer_spl": "SC0",
}
BOOK_NAMES = {"pinnacle": "Pinnacle", "betfair_ex_eu": "Betfair Exchange", "betfair_ex_uk": "Betfair Exchange",
              "matchbook": "Matchbook"}
EXCHANGE_KEYS = {"betfair_ex_eu", "betfair_ex_uk", "matchbook"}


def key() -> str | None:
    k = os.environ.get("ODDS_API_KEY", "").strip()
    return k or None


def _get(path: str, params: dict, api_key: str) -> tuple[object, dict]:
    r = requests.get(f"{BASE}{path}", params={**params, "apiKey": api_key},
                     headers={"User-Agent": config.USER_AGENT}, timeout=30)
    if r.status_code in (401, 403):
        raise PermissionError(f"The Odds API rejected the key (HTTP {r.status_code})")
    if r.status_code == 429:
        raise RuntimeError("The Odds API quota/rate limit reached (HTTP 429)")
    if r.status_code >= 400:
        # never let requests' default message (full URL incl. apiKey) escape
        raise RuntimeError(f"The Odds API HTTP {r.status_code} for {path} ({r.text[:120]!r})")
    usage = {k: r.headers.get(h) for k, h in (("remaining", "x-requests-remaining"),
                                              ("used", "x-requests-used"), ("last", "x-requests-last"))}
    return r.json(), usage


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ")
    s = re.sub(r"\b(fc|cf|afc|sc|ac|ssc|as|cd|ud|rc|sv|vfb|vfl|tsg|1\.|fk|sk)\b", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def similarity(a: str, b: str) -> float:
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    if na == nb or na in nb or nb in na:
        return 1.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def match_event(con, league: str, home: str, away: str, commence: datetime, with_info: bool = False):
    """Find our event for an Odds API event: same league family, kickoff within a window, both names similar.
    with_info=True returns (event_id, name_score, kickoff_diff_minutes)."""
    like = "INT:%" if league.startswith("INT:") else league
    win = 30 if league.startswith("TENNIS") else 3   # tennis start times are order-of-play estimates
    rows = con.execute("""SELECT event_id, home, away, kickoff_utc FROM events WHERE league LIKE ? AND status='scheduled'
                          AND kickoff_utc BETWEEN ? AND ?""",
                       (like, (commence - timedelta(hours=win)).isoformat(),
                        (commence + timedelta(hours=win)).isoformat())).fetchall()
    best, best_s, best_d = None, 0.0, None
    for r in rows:
        sc = min(similarity(home, r["home"]), similarity(away, r["away"]))
        if sc > best_s:
            best, best_s = r["event_id"], sc
            best_d = (datetime.fromisoformat(r["kickoff_utc"]) - commence).total_seconds() / 60
    eid = best if best_s >= 0.6 else None
    return (eid, best_s, best_d) if with_info else eid


def parse_odds(event: dict, two_way: bool = False) -> list[tuple]:
    """-> [(bookmaker_name, market, selection, line, price, last_update)]
    two_way=True for NFL/NBA: h2h -> ML, spreads -> SPREAD, totals -> TOTAL."""
    out = []
    home, away = event["home_team"], event["away_team"]
    for bk in event.get("bookmakers", []):
        from .books import normalize_book
        name = normalize_book(BOOK_NAMES.get(bk["key"], bk.get("title", bk["key"])))
        if not name:
            continue
        for m in bk.get("markets", []):
            ts = m.get("last_update") or bk.get("last_update")
            if two_way:
                mk = {"h2h": "ML", "spreads": "SPREAD", "totals": "TOTAL"}.get(m["key"])
                for o in m.get("outcomes", []):
                    if mk == "ML" and o["name"] in (home, away):
                        out.append((name, "ML", "home" if o["name"] == home else "away", None, float(o["price"]), ts))
                    elif mk == "SPREAD" and o.get("point") is not None and o["name"] in (home, away):
                        pt = float(o["point"])
                        out.append((name, "SPREAD", "home" if o["name"] == home else "away",
                                    pt if o["name"] == home else -pt, float(o["price"]), ts))
                    elif mk == "TOTAL" and o.get("point") is not None and o["name"] in ("Over", "Under"):
                        out.append((name, "TOTAL", o["name"].lower(), float(o["point"]), float(o["price"]), ts))
                continue
            if m["key"] == "h2h":
                for o in m["outcomes"]:
                    sel = "H" if o["name"] == home else ("A" if o["name"] == away else ("D" if o["name"] == "Draw" else None))
                    if sel:
                        out.append((name, "1X2", sel, None, float(o["price"]), ts))
            elif m["key"] == "totals":
                for o in m["outcomes"]:
                    if o.get("point") is not None and o["name"] in ("Over", "Under"):
                        out.append((name, "OU", o["name"].lower(), float(o["point"]), float(o["price"]), ts))
            elif m["key"] == "btts":
                for o in m["outcomes"]:
                    if o["name"] in ("Yes", "No"):
                        out.append((name, "BTTS", o["name"].lower(), None, float(o["price"]), ts))
            elif m["key"] == "spreads":
                for o in m["outcomes"]:
                    if o.get("point") is None:
                        continue
                    if o["name"] == home:
                        out.append((name, "AH", "home", float(o["point"]), float(o["price"]), ts))
                    elif o["name"] == away:
                        out.append((name, "AH", "away", -float(o["point"]), float(o["price"]), ts))
    return out


def _due(con, sport_key: str, soonest: datetime, now: datetime) -> bool:
    """Spend credits close to start times: fetch a competition when its next event is within 10h
    and the last fetch is >= 4h old, or once a day earlier (first look) when nothing was fetched today."""
    con.execute("CREATE TABLE IF NOT EXISTS odds_api_fetches (sport_key TEXT, fetched_at TEXT, credits INTEGER)")
    r = con.execute("SELECT MAX(fetched_at) m FROM odds_api_fetches WHERE sport_key=?", (sport_key,)).fetchone()
    last = datetime.fromisoformat(r["m"]) if r and r["m"] else None
    hours_to = (soonest - now).total_seconds() / 3600
    if last is None:
        return True
    age = (now - last).total_seconds() / 3600
    if hours_to <= 10:
        return age >= 4 or (hours_to <= 2.5 and age >= 1.5)   # final pre-game refresh
    if hours_to <= 36:
        return age >= 8                                        # day-before refresh
    return last.date() != now.date()                           # weekly horizon: one look per day


def budget(remaining: int | None, now: datetime, spent_today: int = 0) -> int:
    """Daily allowance = (remaining - reserve) / days left in the month; a run may spend what is
    left of today's allowance, capped per run. Several runs a day share the allowance, with the
    soonest-starting events served first."""
    if remaining is None:
        return MAX_CREDITS_PER_RUN
    days_left = calendar.monthrange(now.year, now.month)[1] - now.day + 1
    daily = (remaining + spent_today - RESERVE) / max(days_left, 1)
    return int(max(0, min(MAX_CREDITS_PER_RUN, daily - spent_today)))


def spent_today(con, now: datetime) -> int:
    import json as _j
    tot = 0
    for (d,) in con.execute("SELECT details FROM job_runs WHERE job='ingest-odds-api' AND substr(started_at,1,10)=?",
                            (now.strftime("%Y-%m-%d"),)):
        try:
            tot += int((_j.loads(d or "{}")).get("credits_spent") or 0)
        except (ValueError, TypeError):
            pass
    return tot


def ingest(con, now: datetime, horizon_h: float = 168) -> dict:
    """Fetch odds for competitions with events in the next 7 days and STORE EVERY EVENT in that window
    (v0.3 kept only <36h, discarding most of what each paid request returned)."""
    api_key = key()
    if not api_key:
        return {"skipped": "ODDS_API_KEY not set"}
    cost = len(MARKETS.split(",")) * len(REGIONS.split(","))
    sports, usage = _get("/sports", {}, api_key)  # free
    active = {s["key"] for s in sports if s.get("active")}
    # find competitions with events in the window (free endpoint)
    window_end = now + timedelta(hours=horizon_h)
    plan = []
    tennis = {k: ("TENNIS:ATP" if "_atp_" in k else "TENNIS:WTA") for k in active if k.startswith("tennis_")}
    for prio, mapping in ((0, US), (0, INTERNATIONAL), (0, tennis), (1, CLUB)):
        for sk, league in mapping.items():
            if sk not in active:
                continue
            evs, usage = _get(f"/sports/{sk}/events", {"dateFormat": "iso"}, api_key)
            starts = [datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00")) for e in evs]
            soon = [t for t in starts if now < t <= window_end]
            if soon and _due(con, sk, min(soon), now):
                plan.append((prio, min(soon), sk, league))   # soonest kick-off first within priority
    plan.sort()
    remaining = int(usage["remaining"]) if usage.get("remaining") not in (None, "") else None
    allowed = budget(remaining, now, spent_today(con, now))
    out = {"credits_remaining_before": remaining, "budget_credits": allowed, "planned": [p[2] for p in plan],
           "fetched": [], "matched": 0, "unmatched": [], "odds_rows": 0, "coverage": {}}
    spent = 0
    for _, _, sk, league in plan:
        two_way = sk in US or sk.startswith("tennis_")
        markets = ("h2h" if sk.startswith("tennis_") else US_MARKETS) if two_way else MARKETS
        c = len(markets.split(",")) * len(REGIONS.split(","))
        if spent + c > allowed:
            continue
        try:
            data, usage = _get(f"/sports/{sk}/odds", {"regions": REGIONS, "markets": markets,
                                                      "oddsFormat": "decimal", "dateFormat": "iso"}, api_key)
        except (RuntimeError, requests.RequestException) as ex:   # one competition failing must not stop the rest
            out.setdefault("errors", []).append(db.redact(str(ex))[:200])
            continue
        spent += c
        out["fetched"].append(sk)
        con.execute("INSERT INTO odds_api_fetches(sport_key, fetched_at, credits) VALUES (?,?,?)", (sk, now.isoformat(), c))
        url = f"{BASE}/sports/{sk}/odds?regions={REGIONS}&markets={markets}"  # key stripped
        cov = out["coverage"].setdefault(sk, {"returned": 0, "in_window": 0, "matched": 0})
        cov["returned"] = len(data)
        for e in data:
            commence = datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00"))
            if not (now < commence <= window_end):
                continue
            cov["in_window"] += 1
            eid, score, kdiff = match_event(con, league, e["home_team"], e["away_team"], commence, with_info=True)
            swapped = False
            if not eid and league.startswith("TENNIS"):   # player order differs between sources
                eid, score, kdiff = match_event(con, league, e["away_team"], e["home_team"], commence, with_info=True)
                swapped = bool(eid)
            if eid:
                from ..disagreement import ensure as _ens
                _ens(con)
                con.execute("INSERT OR REPLACE INTO odds_match_audit VALUES (?,?,?,?,?,?,?,?)",
                            (eid, SOURCE, e["home_team"], e["away_team"], round(score, 3),
                             None if kdiff is None else round(kdiff, 1), int(swapped), db.utcnow()))
            if not eid:
                out["unmatched"].append(f"{sk}: {e['home_team']} v {e['away_team']}")
                continue
            out["matched"] += 1
            cov["matched"] += 1
            for bk, market, sel, line, price, ts in parse_odds(e, two_way=two_way):
                if swapped:
                    sel = {"home": "away", "away": "home"}.get(sel, sel)
                ts_iso = (ts or db.utcnow()).replace("Z", "+00:00")
                cur = con.execute("""INSERT OR IGNORE INTO odds(event_id,bookmaker,market,selection,line,price,kind,
                                     source,source_url,retrieved_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                                  (eid, bk, market, sel, line, price, "pre", SOURCE, url, ts_iso))
                out["odds_rows"] += cur.rowcount
    out["credits_spent"] = spent
    out["credits_remaining_after"] = usage.get("remaining")
    out["unmatched"] = out["unmatched"][:20]
    con.commit()
    return out
