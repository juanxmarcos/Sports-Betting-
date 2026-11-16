"""nflverse weekly NFL injury reports: official game designation and practice participation.

Source   : https://github.com/nflverse/nflverse-data/releases/tag/injuries  (injuries_<season>.csv)
Licence  : CC-BY-4.0 (nflverse-data LICENSE.md). Attribution: "nflverse".
Access   : open data published for programmatic download; no key, no cost.
Cadence  : the provider documents one update a day in season (07:00 UTC). Checked 2026-11-13.

What one row is: one player, one team, one game week. It carries TWO separate facts:
  * report_status   - the club's official game designation (Out / Doubtful / Questionable, and
                      Probable in seasons before 2016). Blank until the club has published it.
  * practice_status - practice participation (DNP / Limited / Full) as of that file.
They are stored separately and never derived from one another: a player who did not practise has
no designation until the club gives one.

What the feed does NOT carry (stated, not worked around):
  * no practice-by-day history: one practice value per player-week. The daily sequence is rebuilt
    here from then on by logging every change between files (`nfl_report_updates`);
  * no per-row time from 2025 on (`date_modified` was dropped). The only provider time is then the
    file's HTTP Last-Modified, stored as `source_published_at`;
  * no starting line-ups. Nothing here confirms who starts at quarterback.

Everything stored is context: nothing in this module touches probabilities, thresholds, odds or picks.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import time
from email.utils import parsedate_to_datetime

import requests

from .. import config, db
from .http import SourceBlocked

PROVIDER = "nflverse:injuries"
LICENSE = "CC-BY-4.0"
URL = "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{season}.csv"
MAX_BYTES = 20 * 1024 * 1024          # a season file is under 1 MB; anything huge is not this file
REQUIRED = ("season", "game_type", "team", "week", "gsis_id", "full_name", "position",
            "report_status", "practice_status")

# nflverse abbreviation -> ESPN display name (the name used in `events`). Fixed table: a team that is
# not listed here is skipped and counted, never guessed.
TEAMS = {
    "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens", "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers", "CHI": "Chicago Bears", "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys", "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
    "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars", "KC": "Kansas City Chiefs",
    "LA": "Los Angeles Rams", "LAC": "Los Angeles Chargers", "LV": "Las Vegas Raiders", "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings", "NE": "New England Patriots", "NO": "New Orleans Saints", "NYG": "New York Giants",
    "NYJ": "New York Jets", "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers", "SEA": "Seattle Seahawks",
    "SF": "San Francisco 49ers", "TB": "Tampa Bay Buccaneers", "TEN": "Tennessee Titans", "WAS": "Washington Commanders",
}
PRACTICE = {"did not participate in practice": "DNP", "limited participation in practice": "Limited",
            "full participation in practice": "Full"}
REPORT = {"out": "Out", "doubtful": "Doubtful", "questionable": "Questionable", "probable": "Probable"}
GSIS = re.compile(r"^\d{2}-\d{7}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS nfl_report_current (
    season INTEGER NOT NULL, game_type TEXT NOT NULL, week INTEGER NOT NULL, team TEXT NOT NULL,
    gsis_id TEXT NOT NULL,              -- NFL player id: the only identity key (names are display only)
    team_name TEXT, player TEXT, position TEXT,
    report_status TEXT,                 -- Out|Doubtful|Questionable|Probable, NULL = no designation published
    report_raw TEXT,                    -- the provider's text when it is not one of the above (e.g. "Note")
    practice_status TEXT,               -- DNP|Limited|Full, NULL = none given
    practice_raw TEXT,
    report_injury TEXT, practice_injury TEXT,
    row_modified_at TEXT,               -- provider's per-row time (only seasons that publish date_modified)
    source_published_at TEXT,           -- HTTP Last-Modified of the file this state was first seen in
    first_seen TEXT NOT NULL,           -- when Doyen first retrieved this player-week
    last_changed TEXT NOT NULL,         -- when Doyen last retrieved a different state
    retracted_at TEXT,                  -- set when the provider removed the row from the file
    source_url TEXT NOT NULL, row_hash TEXT NOT NULL,
    PRIMARY KEY (season, game_type, week, team, gsis_id));
CREATE INDEX IF NOT EXISTS ix_nfl_report_team_week ON nfl_report_current(season, week, team);

CREATE TABLE IF NOT EXISTS nfl_report_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season INTEGER NOT NULL, game_type TEXT NOT NULL, week INTEGER NOT NULL, team TEXT NOT NULL,
    gsis_id TEXT NOT NULL, player TEXT, position TEXT,
    change TEXT NOT NULL CHECK (change IN ('new','changed','retracted','restored')),
    old_report_status TEXT, new_report_status TEXT, old_practice_status TEXT, new_practice_status TEXT,
    row_modified_at TEXT, source_published_at TEXT, observed_at TEXT NOT NULL,
    source_url TEXT NOT NULL, row_hash TEXT);
CREATE INDEX IF NOT EXISTS ix_nfl_report_updates_key ON nfl_report_updates(season, week, team, gsis_id);
CREATE TRIGGER IF NOT EXISTS trg_nfl_report_updates_append_only
BEFORE UPDATE ON nfl_report_updates BEGIN SELECT RAISE(ABORT, 'nfl_report_updates is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_nfl_report_updates_nodelete
BEFORE DELETE ON nfl_report_updates BEGIN SELECT RAISE(ABORT, 'nfl_report_updates is append-only'); END;

CREATE TABLE IF NOT EXISTS nfl_report_fetches (
    id INTEGER PRIMARY KEY AUTOINCREMENT, fetched_at TEXT NOT NULL, season INTEGER NOT NULL, url TEXT NOT NULL,
    outcome TEXT NOT NULL,              -- fetched|not_modified|not_published|blocked|malformed|error
    http_status INTEGER, etag TEXT, source_published_at TEXT,
    rows INTEGER, new INTEGER, changed INTEGER, retracted INTEGER, restored INTEGER,
    skipped TEXT, error TEXT);
"""


class SourceMalformed(RuntimeError):
    """The response is not a usable injury file. Nothing is written when this is raised."""


class SourceUnavailable(RuntimeError):
    """Timeouts or server errors after the bounded retries."""


def ensure(con) -> None:
    con.executescript(SCHEMA)


def season_for(now) -> int:
    """NFL season a date belongs to: January and February belong to the season that started the year before."""
    return now.year if now.month >= 3 else now.year - 1


# ------------------------------------------------------------------ HTTP

def _cache_paths(url: str):
    key = hashlib.sha1(url.encode()).hexdigest()
    return config.CACHE_DIR / f"nflverse_{key}.bin", config.CACHE_DIR / f"nflverse_{key}.json"


def conditional_fetch(url: str, retries: int = 3, timeout: int = 30, session=requests, sleep=time.sleep) -> dict:
    """One conditional GET. Returns {outcome, http_status, content, etag, last_modified}.

    * Sends If-None-Match / If-Modified-Since from the previous response, so an unchanged file costs a 304.
    * The cache is one file per URL (overwritten), so it cannot grow.
    * 401 / 403 / 429 raise SourceBlocked at once: no retry, no workaround.
    * 404 is `not_published` (the season file does not exist yet); it is not an error.
    * Timeouts and 5xx are retried `retries` times with exponential backoff, then SourceUnavailable.
      There is no silent fallback to an old copy: the caller keeps what it has and reports its age.
    """
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    body_p, meta_p = _cache_paths(url)
    meta = {}
    if body_p.exists() and meta_p.exists():
        try:
            meta = json.loads(meta_p.read_text())
        except ValueError:
            meta = {}
    headers = {"User-Agent": config.USER_AGENT}
    if meta.get("etag"):
        headers["If-None-Match"] = meta["etag"]
    if meta.get("last_modified_http"):
        headers["If-Modified-Since"] = meta["last_modified_http"]
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            r = session.get(url, headers=headers, timeout=timeout)
        except Exception as e:  # noqa: BLE001 - network errors are retried, then reported
            last_exc = e
        else:
            code = r.status_code
            if code in (401, 403, 429):
                raise SourceBlocked(f"{url} -> HTTP {code}; not retrying/circumventing")
            if code == 404:
                return {"outcome": "not_published", "http_status": 404, "content": None, "etag": None, "last_modified": None}
            if code == 304 and meta:
                return {"outcome": "not_modified", "http_status": 304, "content": body_p.read_bytes(),
                        "etag": meta.get("etag"), "last_modified": meta.get("last_modified")}
            if code == 200:
                if len(r.content) > MAX_BYTES:
                    raise SourceMalformed(f"{url}: {len(r.content)} bytes exceeds the {MAX_BYTES} byte limit")
                lm_http = r.headers.get("Last-Modified")
                try:
                    lm = parsedate_to_datetime(lm_http).isoformat() if lm_http else None
                except (TypeError, ValueError):
                    lm_http, lm = None, None
                etag = r.headers.get("ETag") or r.headers.get("Etag")
                body_p.write_bytes(r.content)
                meta_p.write_text(json.dumps({"etag": etag, "last_modified_http": lm_http, "last_modified": lm}))
                return {"outcome": "fetched", "http_status": 200, "content": r.content, "etag": etag, "last_modified": lm}
            last_exc = RuntimeError(f"HTTP {code}")
        if attempt < retries - 1:
            sleep(2 ** attempt)
    raise SourceUnavailable(f"{url}: {type(last_exc).__name__}: {last_exc} after {retries} attempts")


# ------------------------------------------------------------------ parsing

def _clean(v) -> str | None:
    v = (v or "").strip()
    return v or None


def _status(raw: str | None, table: dict) -> tuple[str | None, str | None]:
    """(normalised, raw-if-unrecognised). Unknown text is kept verbatim, never mapped to a status."""
    if raw is None:
        return None, None
    norm = table.get(raw.lower())
    return (norm, None) if norm else (None, raw)


def _injury(a, b) -> str | None:
    parts = [x for x in (_clean(a), _clean(b)) if x]
    return " / ".join(parts) or None


def row_hash(rec: dict) -> str:
    """Hash of what the report says. Display fields and timestamps are excluded on purpose."""
    keys = ("report_status", "report_raw", "practice_status", "practice_raw", "report_injury", "practice_injury")
    return hashlib.sha1(json.dumps([rec.get(k) for k in keys]).encode()).hexdigest()[:16]


def parse(content: bytes) -> tuple[list[dict], dict]:
    """Parse one season file -> (records, skipped counts). Raises SourceMalformed if it is not that file.

    Rows are skipped (and counted) rather than repaired when the team is not in TEAMS, the player id
    is missing or malformed, or the season/week is not a number. Two rows for the same player-week:
    identical ones collapse; conflicting ones keep the later `date_modified`, or are both dropped when
    the file gives no time to choose by."""
    try:
        text = content.decode("utf-8-sig")
    except (UnicodeDecodeError, AttributeError) as e:
        raise SourceMalformed(f"not UTF-8 text: {e}") from e
    reader = csv.DictReader(io.StringIO(text))
    cols = set(reader.fieldnames or [])
    missing = [c for c in REQUIRED if c not in cols]
    if missing:
        raise SourceMalformed(f"missing columns: {', '.join(missing)}")
    skipped = {"unknown_team": 0, "no_player_id": 0, "bad_season_or_week": 0, "duplicate": 0, "conflicting_duplicate": 0}
    out: dict[tuple, dict] = {}
    dropped: set[tuple] = set()
    n = 0
    try:
        for row in reader:
            n += 1
            team = _clean(row.get("team"))
            if team not in TEAMS:
                skipped["unknown_team"] += 1
                continue
            gsis = _clean(row.get("gsis_id"))
            if not gsis or not GSIS.match(gsis):
                skipped["no_player_id"] += 1
                continue
            try:
                season, week = int(row["season"]), int(row["week"])
            except (TypeError, ValueError):
                skipped["bad_season_or_week"] += 1
                continue
            rep, rep_raw = _status(_clean(row.get("report_status")), REPORT)
            pra, pra_raw = _status(_clean(row.get("practice_status")), PRACTICE)
            rec = {"season": season, "game_type": _clean(row.get("game_type")) or "REG", "week": week, "team": team,
                   "gsis_id": gsis, "team_name": TEAMS[team], "player": _clean(row.get("full_name")),
                   "position": _clean(row.get("position")), "report_status": rep, "report_raw": rep_raw,
                   "practice_status": pra, "practice_raw": pra_raw,
                   "report_injury": _injury(row.get("report_primary_injury"), row.get("report_secondary_injury")),
                   "practice_injury": _injury(row.get("practice_primary_injury"), row.get("practice_secondary_injury")),
                   "row_modified_at": _clean(row.get("date_modified"))}
            rec["row_hash"] = row_hash(rec)
            key = (season, rec["game_type"], week, team, gsis)
            if key in dropped:
                skipped["conflicting_duplicate"] += 1
                continue
            old = out.get(key)
            if old is None:
                out[key] = rec
            elif old["row_hash"] == rec["row_hash"]:
                skipped["duplicate"] += 1
            elif old["row_modified_at"] and rec["row_modified_at"] and old["row_modified_at"] != rec["row_modified_at"]:
                skipped["duplicate"] += 1
                if rec["row_modified_at"] > old["row_modified_at"]:
                    out[key] = rec
            else:
                del out[key]
                dropped.add(key)
                skipped["conflicting_duplicate"] += 2
    except csv.Error as e:
        raise SourceMalformed(f"unreadable CSV: {e}") from e
    if n == 0:
        raise SourceMalformed("no data rows")
    if not out:
        raise SourceMalformed(f"no usable rows in {n}")
    return list(out.values()), {k: v for k, v in skipped.items() if v}


# ------------------------------------------------------------------ storage

_COLS = ("season", "game_type", "week", "team", "gsis_id", "team_name", "player", "position", "report_status",
         "report_raw", "practice_status", "practice_raw", "report_injury", "practice_injury", "row_modified_at")


def _log_update(con, rec, change, old, published, observed, url):
    con.execute("""INSERT INTO nfl_report_updates(season,game_type,week,team,gsis_id,player,position,change,
                   old_report_status,new_report_status,old_practice_status,new_practice_status,
                   row_modified_at,source_published_at,observed_at,source_url,row_hash)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (rec["season"], rec["game_type"], rec["week"], rec["team"], rec["gsis_id"], rec["player"], rec["position"],
                 change, old["report_status"] if old else None, None if change == "retracted" else rec["report_status"],
                 old["practice_status"] if old else None, None if change == "retracted" else rec["practice_status"],
                 rec["row_modified_at"], published, observed, url, rec["row_hash"]))


def store(con, records: list[dict], season: int, url: str, published: str | None, observed: str) -> dict:
    """Apply one parsed file. Idempotent: the same file applied twice writes nothing the second time.

    A row that vanished from the file is a retraction: it is kept, marked `retracted_at`, and logged.
    If an implausible share of the stored season would vanish at once, the file is treated as broken
    and nothing is written."""
    ensure(con)
    records = [r for r in records if r["season"] == season]
    if not records:
        raise SourceMalformed(f"file has no rows for season {season}")
    cur = {(r["game_type"], r["week"], r["team"], r["gsis_id"]): r for r in con.execute(
        "SELECT * FROM nfl_report_current WHERE season=?", (season,))}
    seen = {(r["game_type"], r["week"], r["team"], r["gsis_id"]) for r in records}
    gone = [k for k, r in cur.items() if k not in seen and r["retracted_at"] is None]
    active = sum(1 for r in cur.values() if r["retracted_at"] is None)
    if gone and len(gone) > max(25, 0.2 * active):
        raise SourceMalformed(f"{len(gone)} of {active} stored rows are missing from the file; refusing to retract them")
    out = {"rows": len(records), "new": 0, "changed": 0, "retracted": 0, "restored": 0}
    for rec in records:
        key = (rec["game_type"], rec["week"], rec["team"], rec["gsis_id"])
        old = cur.get(key)
        if old is None:
            con.execute(f"""INSERT INTO nfl_report_current({','.join(_COLS)},source_published_at,first_seen,last_changed,
                            retracted_at,source_url,row_hash) VALUES ({','.join('?' * len(_COLS))},?,?,?,NULL,?,?)""",
                        (*[rec[c] for c in _COLS], published, observed, observed, url, rec["row_hash"]))
            _log_update(con, rec, "new", None, published, observed, url)
            out["new"] += 1
            continue
        restored = old["retracted_at"] is not None
        if old["row_hash"] == rec["row_hash"] and not restored:
            continue
        change = "restored" if restored else "changed"
        con.execute("""UPDATE nfl_report_current SET team_name=?, player=?, position=?, report_status=?, report_raw=?,
                       practice_status=?, practice_raw=?, report_injury=?, practice_injury=?, row_modified_at=?,
                       source_published_at=?, last_changed=?, retracted_at=NULL, source_url=?, row_hash=?
                       WHERE season=? AND game_type=? AND week=? AND team=? AND gsis_id=?""",
                    (rec["team_name"], rec["player"], rec["position"], rec["report_status"], rec["report_raw"],
                     rec["practice_status"], rec["practice_raw"], rec["report_injury"], rec["practice_injury"],
                     rec["row_modified_at"], published, observed, url, rec["row_hash"],
                     season, rec["game_type"], rec["week"], rec["team"], rec["gsis_id"]))
        _log_update(con, rec, change, old, published, observed, url)
        out[change] += 1
    for key in gone:
        old = cur[key]
        con.execute("""UPDATE nfl_report_current SET retracted_at=?, last_changed=? WHERE season=? AND game_type=?
                       AND week=? AND team=? AND gsis_id=?""", (observed, observed, season, *key))
        _log_update(con, dict(old), "retracted", old, published, observed, url)
        out["retracted"] += 1
    return out


def ingest(con, season: int, fetcher=conditional_fetch) -> dict:
    """Fetch and store one season. Never raises: every outcome, including failures, is logged in
    `nfl_report_fetches` and in `provider_status`, and stored data is left as it was on failure."""
    ensure(con)
    url = URL.format(season=season)
    observed = db.utcnow()
    info: dict = {"season": season, "url": url}
    res: dict = {}
    try:
        res = fetcher(url)
        info["outcome"] = res["outcome"]
        if res["outcome"] == "not_modified" and con.execute(
                "SELECT 1 FROM nfl_report_current WHERE season=? LIMIT 1", (season,)).fetchone():
            pass                                    # unchanged and already stored: nothing to do
        elif res["outcome"] in ("fetched", "not_modified"):
            records, skipped = parse(res["content"])
            info.update(store(con, records, season, url, res.get("last_modified"), observed))
            info["skipped"] = skipped
        if res["outcome"] != "not_published":
            db.provider_ok(con, PROVIDER, info.get("rows", 0))
    except SourceBlocked as e:
        info.update(outcome="blocked", error=str(e))
    except SourceMalformed as e:
        info.update(outcome="malformed", error=str(e))
    except Exception as e:  # noqa: BLE001 - one source failing must not stop a run
        info.update(outcome="error", error=f"{type(e).__name__}: {e}")
    if "error" in info:
        con.rollback()
        db.provider_err(con, PROVIDER, info["error"])
    con.execute("""INSERT INTO nfl_report_fetches(fetched_at,season,url,outcome,http_status,etag,source_published_at,
                   rows,new,changed,retracted,restored,skipped,error) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (observed, season, url, info["outcome"], res.get("http_status"), res.get("etag"), res.get("last_modified"),
                 info.get("rows"), info.get("new"), info.get("changed"), info.get("retracted"), info.get("restored"),
                 json.dumps(info.get("skipped") or {}), db.redact(info.get("error") or "")[:500] or None))
    con.commit()
    return info
