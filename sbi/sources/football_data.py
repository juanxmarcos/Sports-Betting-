"""football-data.co.uk connector.

Free CSVs, published for personal/research use. Provides results, match stats,
(from 2026-27, xG for some leagues), pre-match and closing odds for many bookmakers,
and an upcoming `fixtures.csv` with current odds. Update cadence: results ~twice
weekly (Sun/Mon and midweek); fixtures.csv typically Tue (midweek) and Fri (weekend).
Times are UK local time.
"""
from __future__ import annotations

import io
import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .. import db
from .http import fetch

BASE = "https://www.football-data.co.uk"
SOURCE = "football-data.co.uk"
UK = ZoneInfo("Europe/London")

# Bookmaker column prefixes -> canonical names. Order matters (longest first).
BOOKMAKERS = {
    "BFE": "Betfair Exchange", "BFD": "Betfred", "BMGM": "BetMGM", "B365": "Bet365",
    "BbMx": "Max", "BbAv": "Avg", "SKB": "Sky Bet", "1XB": "1xBet", "Max": "Max", "Avg": "Avg",
    "PS": "Pinnacle", "PP": "Paddy Power", "BW": "Bwin", "BV": "BetVictor", "CL": "Coral",
    "LB": "Ladbrokes", "IW": "Interwetten", "WH": "William Hill", "VC": "VC Bet",
    "GB": "Gamebookers", "SB": "Sportingbet", "SJ": "Stan James", "BS": "Blue Square",
    "P": "Pinnacle",
}
AGGREGATES = {"Max", "Avg"}
EXCHANGES = {"Betfair Exchange", "Matchbook"}
_BK = "|".join(sorted(map(re.escape, BOOKMAKERS), key=len, reverse=True))
RE_1X2 = re.compile(rf"^({_BK})(C?)([HDA])$")
RE_OU = re.compile(rf"^({_BK})(C?)([<>])2\.5$")
RE_AH = re.compile(rf"^({_BK})(C?)AH([HA])$")


def season_code(d: date) -> str:
    y = d.year if d.month >= 7 else d.year - 1
    return f"{y % 100:02d}{(y + 1) % 100:02d}"


def season_url(div: str, season: str) -> str:
    return f"{BASE}/mmz4281/{season}/{div}.csv"


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def event_id(div: str, ko_utc: datetime, home: str, away: str) -> str:
    return f"football:{div}:{ko_utc.strftime('%Y%m%d')}:{slug(home)}:{slug(away)}"


def read_csv(content: bytes) -> pd.DataFrame:
    text = content.decode("utf-8-sig", errors="replace")
    df = pd.read_csv(io.StringIO(text), on_bad_lines="skip")
    df = df.dropna(axis=1, how="all")
    df = df[df.get("HomeTeam").notna()] if "HomeTeam" in df else df.iloc[0:0]
    return df.reset_index(drop=True)


def _kickoff_utc(row) -> datetime:
    d = pd.to_datetime(row["Date"], dayfirst=True).date()
    t = str(row.get("Time") or "15:00")
    if not re.match(r"^\d{1,2}:\d{2}$", t):
        t = "15:00"
    hh, mm = map(int, t.split(":"))
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=UK).astimezone(timezone.utc)


def parse_matches(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise a football-data frame: kickoff_utc, goals, xG, season."""
    out = pd.DataFrame({
        "div": df["Div"],
        "home": df["HomeTeam"].str.strip(),
        "away": df["AwayTeam"].str.strip(),
    })
    out["kickoff_utc"] = [_kickoff_utc(r) for _, r in df.iterrows()]
    out["hg"] = pd.to_numeric(df.get("FTHG"), errors="coerce") if "FTHG" in df else np.nan
    out["ag"] = pd.to_numeric(df.get("FTAG"), errors="coerce") if "FTAG" in df else np.nan
    out["hxg"] = pd.to_numeric(df["HxG"], errors="coerce") if "HxG" in df else np.nan
    out["axg"] = pd.to_numeric(df["AxG"], errors="coerce") if "AxG" in df else np.nan
    out["season"] = [season_code(k.date()) for k in out["kickoff_utc"]]
    out["event_id"] = [event_id(d, k, h, a) for d, k, h, a in
                       zip(out["div"], out["kickoff_utc"], out["home"], out["away"])]
    return out


def parse_odds(df: pd.DataFrame) -> pd.DataFrame:
    """Long-format odds: one row per (match idx, bookmaker, market, selection, line, kind)."""
    recs = []
    cols = list(df.columns)
    ah_line = {"": next((c for c in ("AHh", "BbAHh") if c in cols), None),
               "C": next((c for c in ("AHCh",) if c in cols), None)}
    for c in cols:
        m = RE_1X2.match(c)
        if m:
            bk, cl, sel = m.groups()
            recs.append((c, BOOKMAKERS[bk], "1X2", sel, None, cl))
            continue
        m = RE_OU.match(c)
        if m:
            bk, cl, sel = m.groups()
            recs.append((c, BOOKMAKERS[bk], "OU", "over" if sel == ">" else "under", 2.5, cl))
            continue
        m = RE_AH.match(c)
        if m and ah_line.get(m.group(2)):
            bk, cl, sel = m.groups()
            recs.append((c, BOOKMAKERS[bk], "AH", "home" if sel == "H" else "away", ah_line[cl], cl))
    rows = []
    for col, bk, market, sel, line, cl in recs:
        prices = pd.to_numeric(df[col], errors="coerce")
        if market == "AH":
            lines = pd.to_numeric(df[line], errors="coerce")
        for i, p in prices.items():
            if not (isinstance(p, float) and np.isfinite(p) and p > 1.0):
                continue
            ln = line if market == "OU" else (float(lines[i]) if market == "AH" else None)
            if market == "AH" and not np.isfinite(ln):
                continue
            rows.append((i, bk, market, sel, ln, float(p), "closing" if cl else "pre"))
    return pd.DataFrame(rows, columns=["idx", "bookmaker", "market", "selection", "line", "price", "kind"])


def upsert_events(con, matches: pd.DataFrame, source_url: str, finished: bool) -> int:
    now = db.utcnow()
    n = 0
    for r in matches.itertuples():
        done = finished and pd.notna(r.hg) and pd.notna(r.ag)
        con.execute("""
            INSERT INTO events(event_id,sport,league,season,kickoff_utc,home,away,status,
                               home_score,away_score,home_xg,away_xg,source,source_url,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(event_id) DO UPDATE SET
              kickoff_utc=excluded.kickoff_utc,
              status=CASE WHEN excluded.status='finished' THEN 'finished' ELSE events.status END,
              home_score=COALESCE(excluded.home_score, events.home_score),
              away_score=COALESCE(excluded.away_score, events.away_score),
              home_xg=COALESCE(excluded.home_xg, events.home_xg),
              away_xg=COALESCE(excluded.away_xg, events.away_xg),
              source_url=excluded.source_url, updated_at=excluded.updated_at
        """, (r.event_id, "football", r.div, r.season, r.kickoff_utc.isoformat(), r.home, r.away,
              "finished" if done else "scheduled",
              int(r.hg) if done else None, int(r.ag) if done else None,
              None if pd.isna(r.hxg) else float(r.hxg), None if pd.isna(r.axg) else float(r.axg),
              SOURCE, source_url, now))
        n += 1
    return n


def insert_odds(con, matches: pd.DataFrame, odds: pd.DataFrame, source_url: str,
                retrieved_at: str, kinds=("pre", "closing"), only_events: set | None = None) -> int:
    n = 0
    for r in odds[odds["kind"].isin(kinds)].itertuples():
        eid = matches.at[r.idx, "event_id"]
        if only_events is not None and eid not in only_events:
            continue
        cur = con.execute("""INSERT OR IGNORE INTO odds(event_id,bookmaker,market,selection,line,price,
                             kind,source,source_url,retrieved_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                          (eid, r.bookmaker, r.market, r.selection, r.line, r.price, r.kind,
                           SOURCE, source_url, retrieved_at))
        n += cur.rowcount
    return n


def load_season_frame(div: str, season: str, max_age_hours: float = 12) -> pd.DataFrame:
    content, _ = fetch(season_url(div, season), max_age_hours=max_age_hours)
    return read_csv(content)


def ingest_results(con, div: str, season: str) -> dict:
    """Results for a league-season. Stores closing odds only for events we predicted
    (keeps the DB small; full history stays reproducible from the CSVs)."""
    url = season_url(div, season)
    content, lm = fetch(url, max_age_hours=6)
    df = read_csv(content)
    if df.empty:
        return {"events": 0, "closing_odds": 0}
    m = parse_matches(df)
    n = upsert_events(con, m, url, finished=True)
    predicted = {r[0] for r in con.execute("SELECT DISTINCT event_id FROM predictions")}
    o = parse_odds(df)
    k = insert_odds(con, m, o, url, lm or db.utcnow(), kinds=("closing",), only_events=predicted)
    return {"events": n, "closing_odds": k, "last_modified": lm}


def ingest_fixtures(con, leagues) -> dict:
    """Upcoming fixtures + current odds from fixtures.csv."""
    url = f"{BASE}/fixtures.csv"
    content, lm = fetch(url, max_age_hours=2)
    df = read_csv(content)
    df = df[df["Div"].isin(list(leagues))].reset_index(drop=True)
    if df.empty:
        return {"events": 0, "odds": 0, "last_modified": lm}
    m = parse_matches(df)
    n = upsert_events(con, m, url, finished=False)
    o = parse_odds(df)
    k = insert_odds(con, m, o, url, lm or db.utcnow(), kinds=("pre",))
    return {"events": n, "odds": k, "last_modified": lm}
