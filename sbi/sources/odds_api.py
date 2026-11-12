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
MARKETS = "h2h,totals"
MAX_CREDITS_PER_RUN = 8
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
    r.raise_for_status()
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


def match_event(con, league: str, home: str, away: str, commence: datetime) -> str | None:
    """Find our event for an Odds API event: same league family, kickoff within 3h, both names similar."""
    like = "INT:%" if league.startswith("INT:") else league
    rows = con.execute("""SELECT event_id, home, away FROM events WHERE league LIKE ? AND status='scheduled'
                          AND kickoff_utc BETWEEN ? AND ?""",
                       (like, (commence - timedelta(hours=3)).isoformat(),
                        (commence + timedelta(hours=3)).isoformat())).fetchall()
    best, best_s = None, 0.0
    for r in rows:
        s = min(similarity(home, r["home"]), similarity(away, r["away"]))
        if s > best_s:
            best, best_s = r["event_id"], s
    return best if best_s >= 0.6 else None


def parse_odds(event: dict) -> list[tuple]:
    """-> [(bookmaker_name, market, selection, line, price, last_update)]"""
    out = []
    home, away = event["home_team"], event["away_team"]
    for bk in event.get("bookmakers", []):
        name = BOOK_NAMES.get(bk["key"], bk.get("title", bk["key"]))
        for m in bk.get("markets", []):
            ts = m.get("last_update") or bk.get("last_update")
            if m["key"] == "h2h":
                for o in m["outcomes"]:
                    sel = "H" if o["name"] == home else ("A" if o["name"] == away else ("D" if o["name"] == "Draw" else None))
                    if sel:
                        out.append((name, "1X2", sel, None, float(o["price"]), ts))
            elif m["key"] == "totals":
                for o in m["outcomes"]:
                    if o.get("point") is not None and o["name"] in ("Over", "Under"):
                        out.append((name, "OU", o["name"].lower(), float(o["point"]), float(o["price"]), ts))
            elif m["key"] == "spreads":
                for o in m["outcomes"]:
                    if o.get("point") is None:
                        continue
                    if o["name"] == home:
                        out.append((name, "AH", "home", float(o["point"]), float(o["price"]), ts))
                    elif o["name"] == away:
                        out.append((name, "AH", "away", -float(o["point"]), float(o["price"]), ts))
    return out


def budget(remaining: int | None, now: datetime) -> int:
    if remaining is None:
        return MAX_CREDITS_PER_RUN
    days_left = calendar.monthrange(now.year, now.month)[1] - now.day + 1
    per_run = (remaining - RESERVE) / max(days_left * RUNS_PER_DAY, 1)
    return int(max(0, min(MAX_CREDITS_PER_RUN, per_run)))


def ingest(con, now: datetime, horizon_h: float = 36) -> dict:
    api_key = key()
    if not api_key:
        return {"skipped": "ODDS_API_KEY not set"}
    cost = len(MARKETS.split(",")) * len(REGIONS.split(","))
    sports, usage = _get("/sports", {}, api_key)  # free
    active = {s["key"] for s in sports if s.get("active")}
    # find competitions with events in the window (free endpoint)
    window_end = now + timedelta(hours=horizon_h)
    plan = []
    for prio, mapping in ((0, INTERNATIONAL), (1, CLUB)):
        for sk, league in mapping.items():
            if sk not in active:
                continue
            evs, usage = _get(f"/sports/{sk}/events", {"dateFormat": "iso"}, api_key)
            n = sum(1 for e in evs if now < datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00")) <= window_end)
            if n:
                plan.append((prio, -n, sk, league))
    plan.sort()
    remaining = int(usage["remaining"]) if usage.get("remaining") not in (None, "") else None
    allowed = budget(remaining, now)
    out = {"credits_remaining_before": remaining, "budget_credits": allowed, "planned": [p[2] for p in plan],
           "fetched": [], "matched": 0, "unmatched": [], "odds_rows": 0}
    spent = 0
    for _, _, sk, league in plan:
        if spent + cost > allowed:
            break
        data, usage = _get(f"/sports/{sk}/odds", {"regions": REGIONS, "markets": MARKETS,
                                                  "oddsFormat": "decimal", "dateFormat": "iso"}, api_key)
        spent += cost
        out["fetched"].append(sk)
        url = f"{BASE}/sports/{sk}/odds?regions={REGIONS}&markets={MARKETS}"  # key stripped
        for e in data:
            commence = datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00"))
            if not (now < commence <= window_end):
                continue
            eid = match_event(con, league, e["home_team"], e["away_team"], commence)
            if not eid:
                out["unmatched"].append(f"{sk}: {e['home_team']} v {e['away_team']}")
                continue
            out["matched"] += 1
            for bk, market, sel, line, price, ts in parse_odds(e):
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
