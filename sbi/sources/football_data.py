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


class SchemaError(RuntimeError):
    """The file is not a football-data match file (columns renamed, or an HTML/error page).

    A RuntimeError, so the ingest job records it against this provider and carries on with the others."""


REQUIRED = ("Div", "Date", "HomeTeam", "AwayTeam")
MAX_PRICE = 1000.0      # decimal odds above this are data errors, not prices


def read_csv(content: bytes) -> pd.DataFrame:
    """Parse a football-data CSV. An empty file gives an empty frame; a changed schema raises SchemaError."""
    text = content.decode("utf-8-sig", errors="replace")
    if not text.strip():
        return pd.DataFrame(columns=list(REQUIRED))
    try:
        df = pd.read_csv(io.StringIO(text), on_bad_lines="skip")
    except pd.errors.ParserError as e:
        raise SchemaError(f"unreadable football-data file: {e}") from e
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=list(REQUIRED))
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise SchemaError(f"football-data file is missing column(s) {missing}; first columns: {list(df.columns)[:6]}")
    keep = df["HomeTeam"].notna() & df["AwayTeam"].notna() & df["Div"].notna()
    df = df[keep]
    df = df.dropna(axis=1, how="all") if len(df) else df
    for c in REQUIRED:          # dropna(axis=1) must never remove a required column
        if c not in df.columns:
            df[c] = np.nan
    return df.reset_index(drop=True)


def _time_ok(t) -> bool:
    m = re.match(r"^(\d{1,2}):(\d{2})$", str(t).strip())
    return bool(m) and int(m.group(1)) < 24 and int(m.group(2)) < 60


def _kickoff_utc(row) -> datetime:
    """Kick-off in UTC. football-data prints UK local time for every division, including Spain's,
    so the UK zone (GMT in winter, BST in summer) is applied whatever the country. A missing or
    malformed time falls back to 15:00 UK."""
    d = pd.to_datetime(row["Date"], dayfirst=True).date()
    t = str(row.get("Time") or "").strip()
    if not _time_ok(t):
        t = "15:00"
    hh, mm = map(int, t.split(":"))
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=UK).astimezone(timezone.utc)


def clean_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Drop rows that cannot be a match, keeping the original index so odds rows still line up.

    Removed: an unparseable date, a blank team, a team playing itself, and any repeat of a
    (division, UK date, home, away) already seen in the file (the first is kept). Returns the kept
    rows and a count of each reason, so nothing disappears silently."""
    if df.empty:
        return df, {"bad_date": 0, "bad_team": 0, "duplicate": 0, "assumed_kickoff_time": 0}
    dates = pd.to_datetime(df["Date"].astype(str).str.strip(), format="%d/%m/%Y", errors="coerce")
    short = dates.isna()
    if short.any():         # seasons before 2018-19 print two-digit years
        dates[short] = pd.to_datetime(df.loc[short, "Date"].astype(str).str.strip(), format="%d/%m/%y", errors="coerce")
    home = df["HomeTeam"].astype(str).str.strip()
    away = df["AwayTeam"].astype(str).str.strip()
    bad_date = dates.isna()
    bad_team = (home == "") | (away == "") | (home.str.lower() == away.str.lower())
    key = df["Div"].astype(str).str.strip() + "|" + dates.dt.strftime("%Y%m%d").fillna("") + "|" + home.map(slug) + "|" + away.map(slug)
    dup = key.duplicated(keep="first") & ~bad_date & ~bad_team
    keep = ~(bad_date | bad_team | dup)
    times = df["Time"] if "Time" in df.columns else pd.Series("", index=df.index)
    assumed = int((~times.map(_time_ok))[keep].sum())
    return df[keep], {"bad_date": int(bad_date.sum()), "bad_team": int((bad_team & ~bad_date).sum()),
                      "duplicate": int(dup.sum()), "assumed_kickoff_time": assumed}


def parse_matches(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise a football-data frame: kickoff_utc, goals, xG, season.

    Rows that cannot be a match are dropped (see clean_rows); the index of the remaining rows is
    the row position in `df`, which is what parse_odds uses as `idx`."""
    df, _ = clean_rows(df)
    out = pd.DataFrame({
        "div": df["Div"].astype(str).str.strip(),
        "home": df["HomeTeam"].astype(str).str.strip(),
        "away": df["AwayTeam"].astype(str).str.strip(),
    })
    out["kickoff_utc"] = pd.Series([_kickoff_utc(r) for _, r in df.iterrows()], index=df.index,
                                   dtype="datetime64[ns, UTC]")
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
            if not (isinstance(p, float) and np.isfinite(p) and 1.0 < p <= MAX_PRICE):
                continue        # blank, zero, negative, 1.0 or absurd: not a price
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
    ids = matches["event_id"].to_dict()      # rows dropped by clean_rows have no event
    for r in odds[odds["kind"].isin(kinds)].itertuples():
        eid = ids.get(r.idx)
        if eid is None:
            continue
        if only_events is not None and eid not in only_events:
            continue
        # The table's UNIQUE key cannot stop a repeat when `line` is NULL (1X2): SQLite treats NULLs as
        # distinct. Re-reading the SAME snapshot must add nothing, so skip a row that is already stored
        # with this exact timestamp. A newer snapshot repeating a price is still recorded, as before.
        if pd.isna(r.line) and con.execute(
                """SELECT 1 FROM odds WHERE event_id=? AND bookmaker=? AND market=? AND selection=? AND line IS NULL
                   AND kind=? AND price=? AND retrieved_at=? LIMIT 1""",
                (eid, r.bookmaker, r.market, r.selection, r.kind, r.price, retrieved_at)).fetchone():
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


def ingest_results(con, div: str, season: str, max_age_hours: float = 6) -> dict:
    """Results for a league-season. Stores closing odds only for events we predicted
    (keeps the DB small; full history stays reproducible from the CSVs)."""
    url = season_url(div, season)
    content, lm = fetch(url, max_age_hours=max_age_hours)
    df = read_csv(content)
    df = df[df["Div"].astype(str).str.strip() == div].reset_index(drop=True)   # a season file holds one division
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
    divs = df["Div"].astype(str).str.strip()
    in_file = divs.value_counts().to_dict()
    allow = list(leagues)
    # Divisions in the file that are not on the allowlist are counted, never stored.
    skipped = {d: int(n) for d, n in sorted(in_file.items()) if d not in allow}
    df = df[divs.isin(allow)].reset_index(drop=True)
    if df.empty:
        return {"events": 0, "odds": 0, "last_modified": lm, "by_division": {}, "not_on_allowlist": skipped}
    _, dropped = clean_rows(df)
    m = parse_matches(df)
    n = upsert_events(con, m, url, finished=False)
    o = parse_odds(df)
    k = insert_odds(con, m, o, url, lm or db.utcnow(), kinds=("pre",))
    return {"events": n, "odds": k, "last_modified": lm,
            "by_division": {d: int(c) for d, c in sorted(m["div"].value_counts().items())},
            "not_on_allowlist": skipped, "rows_dropped": dropped}
