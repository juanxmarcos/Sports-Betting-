"""The Odds API (the-odds-api.com) connector - free tier, ~500 credits/month.

Key: environment variable ODDS_API_KEY (GitHub Actions secret). Never logged or stored:
every stored URL has the key stripped. Without a key the connector is skipped.

Credit model (v4): /sports and /sports/{key}/events are free; /sports/{key}/odds costs
len(markets) x len(regions) credits. We query regions=eu (includes Pinnacle and Betfair
Exchange - the sharp references) and markets h2h,totals = 2 credits per competition.

Budgeting: daily allowance = (remaining - RESERVE) / days left this month, capped at
MAX_CREDITS_PER_DAY (UNKNOWN_REMAINING_CAP when the remaining credits are unknown). Since issue #63
there are two data runs a day: the morning run (before 14:00 New York) may spend MORNING_SHARE of the
day's allowance, the evening run what is left of it. The total per New York day never exceeds the
allowance, so two runs spend no more than the single run did (issue #53).
Competitions with a stored event starting LATER TODAY (America/New_York) are bought first, so the
estimated parlays of the day get fresh prices (issue #51); then future days. Within each group,
internationals, US and tennis come first (they have no other multi-bookmaker source), then club
leagues, soonest start first. The budget and the safeguards below are unchanged: ordering decides
only which competitions the existing allowance is spent on.

Quota safeguards (issue #24):
  * a competition is paid for only when the FREE /events list contains at least one event that
    matches an event we store; a response nothing can be attached to is not bought;
  * the provider's own `x-requests-last` header is compared with the expected cost. If a call
    cost more than expected, the run stops buying and records the mismatch;
  * SBI_ODDS_API_BOOKMAKERS (opt-in, unset by default) asks for named bookmakers instead of a
    region. The provider bills "every group of 10 bookmakers" as one region, so a list of up
    to 10 costs the same as today's single region. Longer lists, unknown keys, paid-only keys
    and prediction-market or DFS keys are refused and the default region is used instead.
"""
from __future__ import annotations

import calendar
import difflib
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

from .. import config, db

BASE = "https://api.the-odds-api.com/v4"
SOURCE = "the-odds-api.com"
REGIONS = "eu"
MARKETS = "h2h,totals"   # btts is not offered on the bulk /odds endpoint (HTTP 422), only per event
MAX_CREDITS_PER_RUN = 40   # hard per-run cap; the DAILY allowance below is the real limit
MAX_CREDITS_PER_DAY = 40   # the single daily run's old cap (#53): two runs a day share it (#63)
UNKNOWN_REMAINING_CAP = 12  # remaining credits unknown: at most this many per New York day
MORNING_SHARE = 0.5         # issue #63: the morning run spends about half, the evening run the rest
EVENING_FROM_HOUR = 14      # New York hour where the evening run's slot starts (sbi/run_marker.py)
RESERVE = 20  # never spend the last credits of the month
NY = ZoneInfo("America/New_York")   # the parlay day (issue #51): today's games are refreshed first

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

BOOKMAKERS_ENV = "SBI_ODDS_API_BOOKMAKERS"
BOOKMAKERS_PER_REGION = 10      # provider: "Every group of 10 bookmakers is the equivalent of 1 region"
# Keys the provider lists (the-odds-api.com/sports-odds-data/bookmaker-apis.html, read 2026-11-16) that
# must never be stored as bookmaker odds:
#   * prediction markets and peer-to-peer exchanges of the `us_ex` region: a contract price there is
#     not a sportsbook quote (different settlement, fees, currency and access);
#   * daily-fantasy "books" of the `us_dfs` region: the provider calls their odds indicative only.
# parse_odds drops them even if the provider returns them, so they cannot count toward the
# "3+ bookmakers" rule or be offered as a best price.
NOT_BOOKMAKER_KEYS = frozenset({
    "polymarket", "polymarket_us", "kalshi", "limitless", "novig", "prophetx", "betopenly",
    "dabble_us_dfs", "parlayplay", "pick6", "prizepicks", "underdog"})
# Listed by the provider as "paid subscriptions only": asking for them on the free plan buys nothing.
PAID_ONLY_KEYS = frozenset({"williamhill_us", "fanatics", "courtside", "rebet", "bet365_au", "dabble_au",
                            "bet99_ca_on"})
# Bookmaker keys of the regions relevant to Soccer/NFL/NBA/Tennis, as listed on the same page.
# Only these may be named in SBI_ODDS_API_BOOKMAKERS; a typo is refused rather than sent.
KNOWN_BOOKMAKER_KEYS = frozenset({
    # eu
    "onexbet", "sport888", "betclic_fr", "betanysports", "betfair_ex_eu", "betonlineag", "betsson", "betvictor",
    "coolbet", "everygame", "gtbets", "leovegas_se", "marathonbet", "matchbook", "mybookieag", "nordicbet",
    "pinnacle", "pmu_fr", "tipico_de", "unibet_fr", "unibet_nl", "unibet_se", "williamhill", "winamax_de",
    "winamax_fr",
    # uk
    "betano_uk", "betfair_ex_uk", "betfair_sb_uk", "betfred_uk", "betway", "boylesports", "casumo", "coral",
    "grosvenor", "ladbrokes_uk", "leovegas", "livescorebet", "paddypower", "skybet", "smarkets", "unibet_uk",
    "virginbet",
    # us, us2
    "betmgm", "betrivers", "betus", "bovada", "draftkings", "fanduel", "lowvig", "ballybet", "betparx",
    "betwhale", "espnbet", "fliff", "hardrockbet",
})


def request_cost(markets: str, regions: str = REGIONS, bookmakers: tuple[str, ...] = ()) -> int:
    """Credits one /odds call is expected to cost: markets x regions, where a bookmaker list
    replaces the regions and is billed as one region per started group of ten."""
    n_markets = len([m for m in markets.split(",") if m])
    if bookmakers:
        n_regions = -(-len(bookmakers) // BOOKMAKERS_PER_REGION)
    else:
        n_regions = len([r for r in regions.split(",") if r])
    return n_markets * n_regions


def bookmaker_selection(raw: str | None = None) -> tuple[tuple[str, ...], str | None]:
    """-> (keys, reason). Parse the opt-in bookmaker list. Any problem returns an empty selection
    and the reason, so the caller falls back to the default region. A list is never trimmed or
    partly used: the owner gets exactly what was asked for, or the unchanged default."""
    raw = os.environ.get(BOOKMAKERS_ENV, "") if raw is None else raw
    keys = tuple(dict.fromkeys(k.strip().lower() for k in raw.split(",") if k.strip()))
    if not keys:
        return (), None
    if len(keys) > BOOKMAKERS_PER_REGION:
        return (), (f"{len(keys)} bookmakers requested; more than {BOOKMAKERS_PER_REGION} would be billed "
                    "as a second region, so the list is ignored")
    for label, group in (("not bookmaker odds (prediction market, peer-to-peer exchange or DFS)", NOT_BOOKMAKER_KEYS),
                         ("paid plans only", PAID_ONLY_KEYS)):
        bad = sorted(k for k in keys if k in group)
        if bad:
            return (), f"{', '.join(bad)}: {label}; the list is ignored"
    unknown = sorted(k for k in keys if k not in KNOWN_BOOKMAKER_KEYS)
    if unknown:
        return (), f"unknown bookmaker key(s) {', '.join(unknown)}; the list is ignored"
    return keys, None


def key() -> str | None:
    k = os.environ.get("ODDS_API_KEY", "").strip()
    return k or None


def _get(path: str, params: dict, api_key: str) -> tuple[object, dict]:
    from .http import count
    count(BASE, "network")      # host only: the key is never recorded
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
        if bk["key"] in NOT_BOOKMAKER_KEYS:      # prediction markets / DFS are never bookmaker odds
            continue
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


def _int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _matches(con, league: str, e: dict) -> bool:
    """Would this provider event attach to an event we store? Same test the paid response gets."""
    commence = datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00"))
    if match_event(con, league, e["home_team"], e["away_team"], commence):
        return True
    return league.startswith("TENNIS") and bool(match_event(con, league, e["away_team"], e["home_team"], commence))


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


def run_slot(now: datetime) -> str:
    """"morning" before 14:00 New York time, otherwise "evening" (same rule as sbi/run_marker.py)."""
    return "morning" if now.astimezone(NY).hour < EVENING_FROM_HOUR else "evening"


def budget(remaining: int | None, now: datetime, spent_today: int = 0, slot: str | None = None) -> int:
    """Daily allowance = (remaining - reserve) / days left in the month, capped at MAX_CREDITS_PER_DAY
    (UNKNOWN_REMAINING_CAP when remaining is unknown). Issue #63: the morning run may spend up to
    MORNING_SHARE of it, the evening run (or any later run that day) what is left. `spent_today` is
    what earlier runs spent that New York day, so the day's total never exceeds the allowance."""
    slot = slot or run_slot(now)
    if remaining is None:
        daily = UNKNOWN_REMAINING_CAP
    else:
        days_left = calendar.monthrange(now.year, now.month)[1] - now.day + 1
        daily = min(MAX_CREDITS_PER_DAY, (remaining + spent_today - RESERVE) / max(days_left, 1))
    share = MORNING_SHARE if slot == "morning" else 1.0
    return int(max(0, min(MAX_CREDITS_PER_RUN, daily * share - spent_today)))


def spent_today(con, now: datetime) -> int:
    """Credits spent by earlier runs on `now`'s New York day (both slots, issue #63)."""
    import json as _j
    day = now.astimezone(NY).date()
    utc_days = sorted({(now.astimezone(timezone.utc) + timedelta(days=k)).strftime("%Y-%m-%d") for k in (-1, 0, 1)})
    tot = 0
    for started, d in con.execute(
            "SELECT started_at, details FROM job_runs WHERE job='ingest-odds-api' AND substr(started_at,1,10) IN (?,?,?)",
            utc_days):
        try:
            t = datetime.fromisoformat(started)
            t = t if t.tzinfo else t.replace(tzinfo=timezone.utc)
            if t.astimezone(NY).date() == day:
                tot += int((_j.loads(d or "{}")).get("credits_spent") or 0)
        except (ValueError, TypeError):
            pass
    return tot


def later_today(t: datetime, now: datetime) -> bool:
    """Starts after `now` on the same New York day."""
    return now < t and t.astimezone(NY).date() == now.astimezone(NY).date()


def plan_order(items: list[tuple]) -> list[tuple]:
    """items: (today, prio, soonest, sport_key, league). Today's games first, then priority group,
    then soonest start. Returned as (prio, soonest, sport_key, league, today)."""
    return [(p, t, sk, lg, today) for today, p, t, sk, lg in sorted(items, key=lambda x: (not x[0], x[1], x[2], x[3]))]


def ingest(con, now: datetime, horizon_h: float = 168) -> dict:
    """Fetch odds for competitions with events in the next 7 days and STORE EVERY EVENT in that window
    (v0.3 kept only <36h, discarding most of what each paid request returned)."""
    api_key = key()
    if not api_key:
        return {"skipped": "ODDS_API_KEY not set"}
    books, books_problem = bookmaker_selection()
    sports, usage = _get("/sports", {}, api_key)  # free
    active = {s["key"] for s in sports if s.get("active")}
    # find competitions with events in the window (free endpoint)
    window_end = now + timedelta(hours=horizon_h)
    plan, no_match = [], []
    tennis = {k: ("TENNIS:ATP" if "_atp_" in k else "TENNIS:WTA") for k in active if k.startswith("tennis_")}
    for prio, mapping in ((0, US), (0, INTERNATIONAL), (0, tennis), (1, CLUB)):
        for sk, league in mapping.items():
            if sk not in active:
                continue
            evs, usage = _get(f"/sports/{sk}/events", {"dateFormat": "iso"}, api_key)
            starts = [datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00")) for e in evs]
            soon = [t for t in starts if now < t <= window_end]
            if not soon:
                continue
            # Free pre-check: buy the odds only if at least one listed event matches an event we
            # store. Otherwise every returned quote would be discarded as unmatched.
            matched = [t for e, t in zip(evs, starts) if now < t <= window_end and _matches(con, league, e)]
            if not matched:
                no_match.append(sk)
                continue
            if _due(con, sk, min(soon), now):
                today = any(later_today(t, now) for t in matched)
                plan.append((today, prio, min(soon), sk, league))
    plan = plan_order(plan)
    remaining = int(usage["remaining"]) if usage.get("remaining") not in (None, "") else None
    allowed = budget(remaining, now, spent_today(con, now))
    out = {"credits_remaining_before": remaining, "budget_credits": allowed, "slot": run_slot(now), "planned": [p[2] for p in plan],
           "fetched": [], "matched": 0, "unmatched": [], "odds_rows": 0, "coverage": {},
           "skipped_no_matching_event": no_match, "planned_today_first": [p[2] for p in plan if p[4]],
           "today": {"events_in_responses": 0, "events_priced": 0}}
    if books:
        out["bookmakers_requested"] = list(books)
    if books_problem:
        out["bookmakers_ignored"] = books_problem
    spent = 0
    for _, _, sk, league, _today in plan:
        two_way = sk in US or sk.startswith("tennis_")
        markets = ("h2h" if sk.startswith("tennis_") else US_MARKETS) if two_way else MARKETS
        c = request_cost(markets, REGIONS, books)
        if spent + c > allowed:
            continue
        scope = {"bookmakers": ",".join(books)} if books else {"regions": REGIONS}
        try:
            data, usage = _get(f"/sports/{sk}/odds", {**scope, "markets": markets,
                                                      "oddsFormat": "decimal", "dateFormat": "iso"}, api_key)
        except (RuntimeError, requests.RequestException) as ex:   # one competition failing must not stop the rest
            out.setdefault("errors", []).append(db.redact(str(ex))[:200])
            continue
        charged = _int(usage.get("last"))
        overcharged = charged is not None and charged > c
        c = max(c, charged or 0)      # account for what the provider says it charged, never less
        spent += c
        out["fetched"].append(sk)
        con.execute("INSERT INTO odds_api_fetches(sport_key, fetched_at, credits) VALUES (?,?,?)", (sk, now.isoformat(), c))
        url = f"{BASE}/sports/{sk}/odds?{'&'.join(f'{k}={v}' for k, v in scope.items())}&markets={markets}"  # key stripped
        if overcharged:
            # The call cost more than the documented formula. Keep what was paid for, buy nothing more.
            out["cost_mismatch"] = {"sport_key": sk, "expected": request_cost(markets, REGIONS, books), "charged": charged}
            allowed = spent
        cov = out["coverage"].setdefault(sk, {"returned": 0, "in_window": 0, "matched": 0})
        cov["returned"] = len(data)
        for e in data:
            commence = datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00"))
            if not (now < commence <= window_end):
                continue
            cov["in_window"] += 1
            is_today = later_today(commence, now)
            out["today"]["events_in_responses"] += is_today
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
            out["today"]["events_priced"] += is_today
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
