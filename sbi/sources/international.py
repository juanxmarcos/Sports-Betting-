"""National-team football: fixtures, results and odds.

History: martj42/international_results (CC0) - every men's international since 1872,
         with tournament and neutral-venue flag. Updated periodically by its maintainer.
Fixtures, recent results, odds: ESPN public scoreboard JSON (undocumented, no key).
         Odds are a single bookmaker (DraftKings), with opening and current prices.
Usage is light: one request per competition per day in the window, cached.
"""
from __future__ import annotations

import io
import json
import time
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from .. import db
from .http import fetch

HISTORY_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/{lg}/scoreboard?dates={d}"
SOURCE_ESPN = "espn.com (public scoreboard)"
SOURCE_HIST = "github.com/martj42/international_results (CC0)"

COMPETITIONS = {
    "uefa.nations": "UEFA Nations League", "fifa.friendly": "International Friendly",
    "uefa.euroq": "UEFA Euro Qualifying", "fifa.worldq.uefa": "WC Qualifying UEFA",
    "fifa.worldq.caf": "WC Qualifying CAF", "fifa.worldq.afc": "WC Qualifying AFC",
    "fifa.worldq.conmebol": "WC Qualifying CONMEBOL", "fifa.worldq.concacaf": "WC Qualifying CONCACAF",
    "caf.nations_qual": "AFCON Qualifying", "concacaf.nations.league": "CONCACAF Nations League",
"fifa.world": "FIFA World Cup", "uefa.euro": "UEFA Euro",
    "caf.nations": "Africa Cup of Nations", "afc.asian.cup": "AFC Asian Cup", "concacaf.gold": "Gold Cup",
    "conmebol.america": "Copa America",
}

# ESPN display name -> martj42 name
ALIASES = {
    "Türkiye": "Turkey", "Turkiye": "Turkey", "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Congo DR": "DR Congo", "Congo": "Congo", "Ivory Coast": "Ivory Coast", "Côte d'Ivoire": "Ivory Coast",
    "St. Lucia": "Saint Lucia", "St. Kitts and Nevis": "Saint Kitts and Nevis",
    "St. Vincent and the Grenadines": "Saint Vincent and the Grenadines", "Sint Maarten": "Sint Maarten",
    "USA": "United States", "Korea Republic": "South Korea", "Korea DPR": "North Korea",
    "IR Iran": "Iran", "Cape Verde Islands": "Cape Verde", "Cabo Verde": "Cape Verde", "Cape Verde": "Cape Verde",
    "England": "England", "Scotland": "Scotland", "Wales": "Wales", "Northern Ireland": "Northern Ireland",
    "Czechia": "Czech Republic", "Republic of Ireland": "Republic of Ireland", "Ireland": "Republic of Ireland",
    "Chinese Taipei": "Taiwan", "China PR": "China PR", "Kyrgyz Republic": "Kyrgyzstan",
    "Curaçao": "Curaçao", "Curacao": "Curaçao", "São Tomé and Príncipe": "São Tomé and Príncipe",
    "Sao Tome and Principe": "São Tomé and Príncipe", "The Gambia": "Gambia", "Gambia": "Gambia",
    "Eswatini": "Eswatini", "Swaziland": "Eswatini", "North Macedonia": "North Macedonia",
    "U.S. Virgin Islands": "United States Virgin Islands", "US Virgin Islands": "United States Virgin Islands",
    "Brunei Darussalam": "Brunei", "Timor-Leste": "East Timor", "Hong Kong": "Hong Kong",
    "Macau": "Macau", "Antigua & Barbuda": "Antigua and Barbuda", "Trinidad & Tobago": "Trinidad and Tobago",
    "Turks and Caicos": "Turks and Caicos Islands", "Bonaire": "Bonaire", "French Guiana": "French Guiana",
    "Guadeloupe": "Guadeloupe", "Martinique": "Martinique", "Saint Martin": "Saint Martin", "St. Martin": "Saint Martin",
}


def canon(name: str) -> str:
    return ALIASES.get(name, name)


def american_to_decimal(s) -> float | None:
    try:
        v = float(str(s).replace("+", ""))
    except (TypeError, ValueError):
        return None
    if v == 0:
        return None
    return 1 + (v / 100 if v > 0 else 100 / -v)


def load_history(max_age_hours: float = 24) -> pd.DataFrame:
    content, _ = fetch(HISTORY_URL, max_age_hours=max_age_hours)
    df = pd.read_csv(io.BytesIO(content))
    df = df.dropna(subset=["home_score", "away_score"])
    df["kickoff_utc"] = pd.to_datetime(df["date"], utc=True) + pd.Timedelta(hours=18)
    return pd.DataFrame({
        "home": df.home_team, "away": df.away_team, "hg": df.home_score.astype(int),
        "ag": df.away_score.astype(int), "tournament": df.tournament,
        "neutral": df.neutral.astype(str).str.upper().eq("TRUE"), "kickoff_utc": df.kickoff_utc,
        "src": "martj42"})


def _parse_event(e: dict, lg: str) -> dict | None:
    c = e["competitions"][0]
    teams = {t["homeAway"]: t for t in c["competitors"]}
    if "home" not in teams or "away" not in teams:
        return None
    home, away = canon(teams["home"]["team"]["displayName"]), canon(teams["away"]["team"]["displayName"])
    venue_country = (((c.get("venue") or {}).get("address")) or {}).get("country")
    raw_home = teams["home"]["team"]["displayName"]
    vc = canon(venue_country) if venue_country else None
    neutral = bool(c.get("neutralSite")) or (vc is not None and vc not in (home, raw_home)
                                             and venue_country not in (home, raw_home))
    st = e["status"]["type"]
    out = {"espn_id": e["id"], "league": f"INT:{lg}", "competition": COMPETITIONS.get(lg, lg),
           "kickoff_utc": datetime.fromisoformat(e["date"].replace("Z", "+00:00")),
           "home": home, "away": away, "neutral": neutral, "completed": bool(st.get("completed")),
           "state": st.get("name"), "hg": None, "ag": None, "odds": []}
    if out["completed"]:
        try:
            out["hg"], out["ag"] = int(teams["home"]["score"]), int(teams["away"]["score"])
        except (TypeError, ValueError):
            out["completed"] = False
    for o in c.get("odds") or []:
        bk = (o.get("provider") or {}).get("name", "ESPN odds")
        ml = o.get("moneyline") or {}
        for side, sel in (("home", "H"), ("away", "A")):
            for kind in ("open", "close"):
                px = american_to_decimal(((ml.get(side) or {}).get(kind) or {}).get("odds"))
                if px:
                    out["odds"].append((bk, "1X2", sel, None, px, "open" if kind == "open" else "current"))
        dpx = american_to_decimal((o.get("drawOdds") or {}).get("moneyLine"))
        if dpx:
            out["odds"].append((bk, "1X2", "D", None, dpx, "current"))
        tot = o.get("total") or {}
        for side in ("over", "under"):
            for kind in ("open", "close"):
                rec = (tot.get(side) or {}).get(kind) or {}
                px = american_to_decimal(rec.get("odds"))
                line = rec.get("line")
                try:
                    ln = float(str(line)[1:]) if line else None
                except ValueError:
                    ln = None
                if px and ln is not None:
                    out["odds"].append((bk, "OU", side, ln, px, "open" if kind == "open" else "current"))
        sp = o.get("pointSpread") or {}
        for side in ("home", "away"):
            rec = (sp.get(side) or {}).get("close") or {}
            px = american_to_decimal(rec.get("odds"))
            try:
                ln = float(rec.get("line"))
            except (TypeError, ValueError):
                ln = None
            if px and ln is not None:
                # store AH line from the home perspective
                out["odds"].append((bk, "AH", side, ln if side == "home" else -ln, px, "current"))
    return out


def scoreboard(lg: str, d: date, max_age_hours: float) -> list[dict]:
    content, _ = fetch(ESPN.format(lg=lg, d=d.strftime("%Y%m%d")), max_age_hours=max_age_hours)
    data = json.loads(content)
    out = []
    for e in data.get("events", []):
        try:
            x = _parse_event(e, lg)
        except (KeyError, TypeError, ValueError, AttributeError):
            continue  # one malformed event must not drop the whole day
        if x:
            out.append(x)
    return out


def collect(start: date, end: date, now: datetime, polite_delay: float = 0.15) -> tuple[list[dict], list[str]]:
    """All international events between two dates. Past dates are cached ~forever."""
    events, errors = [], []
    d = start
    while d <= end:
        past = d < (now.date() - timedelta(days=2))
        for lg in COMPETITIONS:
            try:
                events += scoreboard(lg, d, max_age_hours=24 * 365 if past else 1)
            except Exception as e:  # noqa: BLE001
                errors.append(f"{lg} {d}: {e}")
            time.sleep(0 if past else polite_delay)
        d += timedelta(days=1)
    return events, errors


def event_id(ev: dict) -> str:
    return f"football:{ev['league']}:{ev['kickoff_utc'].strftime('%Y%m%d')}:{ev['espn_id']}"


def store(con, events: list[dict]) -> dict:
    now = db.utcnow()
    n_ev = n_odds = 0
    for ev in events:
        eid = event_id(ev)
        url = f"https://www.espn.com/soccer/match/_/gameId/{ev['espn_id']}"
        con.execute("""
            INSERT INTO events(event_id,sport,league,season,kickoff_utc,home,away,status,home_score,away_score,
                               source,source_url,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(event_id) DO UPDATE SET kickoff_utc=excluded.kickoff_utc,
              status=CASE WHEN excluded.status='finished' THEN 'finished' ELSE events.status END,
              home_score=COALESCE(excluded.home_score, events.home_score),
              away_score=COALESCE(excluded.away_score, events.away_score), updated_at=excluded.updated_at
        """, (eid, "football", ev["league"], str(ev["kickoff_utc"].year), ev["kickoff_utc"].isoformat(),
              ev["home"], ev["away"], "finished" if ev["completed"] else "scheduled",
              ev["hg"], ev["ag"], SOURCE_ESPN, url, now))
        n_ev += 1
        if not ev["completed"]:
            for bk, market, sel, line, px, kind in ev["odds"]:
                k = "pre" if kind == "current" else "open"
                cur = con.execute("""INSERT OR IGNORE INTO odds(event_id,bookmaker,market,selection,line,price,kind,
                                     source,source_url,retrieved_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                                  (eid, bk, market, sel, line, px, k, SOURCE_ESPN, url, now))
                n_odds += cur.rowcount
    # neutral flag lives in a side table (events schema is sport-agnostic)
    con.execute("CREATE TABLE IF NOT EXISTS event_meta (event_id TEXT PRIMARY KEY, neutral INTEGER, competition TEXT)")
    for ev in events:
        con.execute("INSERT OR REPLACE INTO event_meta VALUES (?,?,?)",
                    (event_id(ev), int(ev["neutral"]), ev["competition"]))
    return {"events": n_ev, "odds": n_odds}


def training_frame(now: datetime, recent: list[dict]) -> pd.DataFrame:
    """martj42 history + ESPN results after the dataset's last date (gap fill). Before `now` only."""
    hist = load_history()
    last = hist.kickoff_utc.max()
    extra = [{"home": e["home"], "away": e["away"], "hg": e["hg"], "ag": e["ag"], "tournament": e["competition"],
              "neutral": e["neutral"], "kickoff_utc": pd.Timestamp(e["kickoff_utc"]), "src": "espn"}
             for e in recent if e["completed"] and pd.Timestamp(e["kickoff_utc"]) > last + pd.Timedelta(hours=6)]
    df = pd.concat([hist, pd.DataFrame(extra)], ignore_index=True) if extra else hist
    df["kickoff_utc"] = pd.to_datetime(df["kickoff_utc"], utc=True)
    df = df[df.kickoff_utc < pd.Timestamp(now).tz_convert("UTC")]
    return df.sort_values("kickoff_utc").drop_duplicates(["home", "away", "kickoff_utc"]).reset_index(drop=True)


def is_friendly(t: str) -> bool:
    return "friendly" in str(t).lower()
