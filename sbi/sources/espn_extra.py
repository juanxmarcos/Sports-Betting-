"""ESPN enrichment (free, keyless): injuries, ESPN Analytics forecasts, lineups, extra bookmakers.

- League injury reports (NBA, NFL): one request per league per run.
- Per-game summaries for events starting in the next 36h:
    * "predictor": ESPN Analytics matchup predictor (BPI/FPI-based) -> stored as an
      EXTERNAL forecast, kept separate from Doyen's model and from bookmaker prices.
    * "leaders": team statistical leaders -> used to flag injured *key* players.
    * soccer "odds": extra bookmakers beyond DraftKings (e.g. Bet365) -> odds table.
    * soccer "rosters": starters -> lineup confirmation status.
Everything is stored with source URL and retrieval time. Nothing here changes probabilities:
injuries/lineups/forecasts are context, risk flags and reassessment triggers.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta

from .. import db
from .books import normalize_book
from .http import fetch

S = "https://site.api.espn.com/apis/site/v2/sports"
PATHS = {"nba": "basketball/nba", "nfl": "football/nfl"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS injuries_current (
    sport TEXT, team TEXT, player TEXT, status TEXT, detail TEXT, reported TEXT, retrieved_at TEXT,
    source_url TEXT, PRIMARY KEY (sport, team, player));
CREATE TABLE IF NOT EXISTS injury_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, sport TEXT, team TEXT, player TEXT, old_status TEXT,
    new_status TEXT, detail TEXT, first_seen TEXT, source_url TEXT);
CREATE TABLE IF NOT EXISTS external_forecasts (
    event_id TEXT, source TEXT, p_home REAL, p_away REAL, p_draw REAL, retrieved_at TEXT, source_url TEXT,
    PRIMARY KEY (event_id, source));
CREATE TABLE IF NOT EXISTS key_players (
    sport TEXT, team TEXT, player TEXT, category TEXT, retrieved_at TEXT, PRIMARY KEY (sport, team, player));
CREATE TABLE IF NOT EXISTS event_weather (
    event_id TEXT PRIMARY KEY, temperature_f REAL, gust_mph REAL, precip_pct REAL, source_url TEXT, retrieved_at TEXT);
CREATE TABLE IF NOT EXISTS lineups (
    event_id TEXT, team TEXT, confirmed INTEGER, starters TEXT, retrieved_at TEXT, PRIMARY KEY (event_id, team));
"""


def _ensure(con):
    con.executescript(SCHEMA)


def _pct(v):
    try:
        x = float(v)
        return x / 100 if x > 1 else x
    except (TypeError, ValueError):
        return None


def injuries(con, sport: str) -> dict:
    """Refresh the current injury list; log every new or changed status (append-only)."""
    _ensure(con)
    url = f"{S}/{PATHS[sport]}/injuries"
    content, _ = fetch(url, max_age_hours=0.9)
    data = json.loads(content)
    now = db.utcnow()
    seen, changes = set(), 0
    for t in data.get("injuries", []):
        team = t.get("displayName")
        for i in t.get("injuries", []):
            player = (i.get("athlete") or {}).get("displayName")
            if not team or not player:
                continue
            status, detail = i.get("status"), i.get("shortComment") or ""
            seen.add((team, player))
            old = con.execute("SELECT status FROM injuries_current WHERE sport=? AND team=? AND player=?",
                              (sport, team, player)).fetchone()
            if not old or old["status"] != status:
                con.execute("""INSERT INTO injury_changes(sport,team,player,old_status,new_status,detail,first_seen,source_url)
                               VALUES (?,?,?,?,?,?,?,?)""", (sport, team, player, old["status"] if old else None,
                                                             status, detail, now, url))
                changes += 1
            con.execute("""INSERT OR REPLACE INTO injuries_current VALUES (?,?,?,?,?,?,?,?)""",
                        (sport, team, player, status, detail, i.get("date"), now, url))
    # players no longer listed -> cleared (log as change)
    for r in con.execute("SELECT team, player, status FROM injuries_current WHERE sport=?", (sport,)).fetchall():
        if (r["team"], r["player"]) not in seen:
            con.execute("""INSERT INTO injury_changes(sport,team,player,old_status,new_status,detail,first_seen,source_url)
                           VALUES (?,?,?,?,?,?,?,?)""", (sport, r["team"], r["player"], r["status"], "Cleared", "", now, url))
            con.execute("DELETE FROM injuries_current WHERE sport=? AND team=? AND player=?", (sport, r["team"], r["player"]))
            changes += 1
    con.commit()
    return {"players": len(seen), "changes": changes}


def _summary(path: str, espn_id: str) -> dict:
    content, _ = fetch(f"{S}/{path}/summary?event={espn_id}", max_age_hours=0.9)
    return json.loads(content)


def enrich_events(con, now: datetime, horizon_h: float = 36) -> dict:
    """Per-game summaries for soon-starting NFL/NBA/soccer-international events."""
    _ensure(con)
    out = {"summaries": 0, "forecasts": 0, "extra_odds": 0, "lineups": 0, "errors": 0}
    rows = con.execute("""SELECT event_id, league, home, away FROM events WHERE status='scheduled'
                          AND kickoff_utc BETWEEN ? AND ? AND (league IN ('NFL','NBA') OR league LIKE 'INT:%')""",
                       (now.isoformat(), (now + timedelta(hours=horizon_h)).isoformat())).fetchall()
    ts = db.utcnow()
    for r in rows:
        espn_id = r["event_id"].split(":")[-1]
        if r["league"] in ("NFL", "NBA"):
            sport, path = r["league"].lower(), PATHS[r["league"].lower()]
        else:
            sport, path = "soccer", "soccer/" + r["league"].split(":", 1)[1]
        url = f"https://www.espn.com/{path.split('/')[0]}/game/_/gameId/{espn_id}"
        try:
            s = _summary(path, espn_id)
        except Exception:  # noqa: BLE001
            out["errors"] += 1
            continue
        out["summaries"] += 1
        # ESPN Analytics predictor (external forecast)
        pr = s.get("predictor") or {}
        ph = _pct((pr.get("homeTeam") or {}).get("gameProjection"))
        pa = _pct((pr.get("awayTeam") or {}).get("gameProjection"))
        if ph is not None and pa is not None and 0 < ph + pa <= 1.02:
            pd_ = max(0.0, 1 - ph - pa) if sport == "soccer" else None
            con.execute("INSERT OR REPLACE INTO external_forecasts VALUES (?,?,?,?,?,?,?)",
                        (r["event_id"], "ESPN Analytics", ph, pa, pd_, ts, url))
            out["forecasts"] += 1
        # weather (outdoor NFL games; ESPN via AccuWeather)
        wx = (s.get("gameInfo") or {}).get("weather")
        if isinstance(wx, dict) and wx.get("temperature") is not None:
            con.execute("INSERT OR REPLACE INTO event_weather VALUES (?,?,?,?,?,?)",
                        (r["event_id"], wx.get("temperature"), wx.get("gust"), wx.get("precipitation"),
                         ((wx.get("link") or {}).get("href") or url), ts))
        # team leaders -> key players
        for team in s.get("leaders") or []:
            tname = (team.get("team") or {}).get("displayName")
            for cat in team.get("leaders") or []:
                for ldr in (cat.get("leaders") or [])[:1]:
                    nm = (ldr.get("athlete") or {}).get("displayName")
                    if tname and nm:
                        con.execute("INSERT OR REPLACE INTO key_players VALUES (?,?,?,?,?)",
                                    (sport, tname, nm, cat.get("displayName") or cat.get("name"), ts))
        if sport == "soccer":
            from .international import american_to_decimal as a2d
            for o in s.get("odds") or []:
                if not isinstance(o, dict):
                    continue
                name = normalize_book((o.get("provider") or {}).get("name", ""))
                if not name or "live" in name.lower():
                    continue
                prices = {"H": a2d((o.get("homeTeamOdds") or {}).get("moneyLine")),
                          "A": a2d((o.get("awayTeamOdds") or {}).get("moneyLine")),
                          "D": a2d((o.get("drawOdds") or {}).get("moneyLine"))}
                if all(prices.values()):
                    for sel, px in prices.items():
                        cur = con.execute("""INSERT OR IGNORE INTO odds(event_id,bookmaker,market,selection,line,price,kind,
                                             source,source_url,retrieved_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                                          (r["event_id"], name, "1X2", sel, None, px, "pre", "espn.com (game summary)", url, ts))
                        out["extra_odds"] += cur.rowcount
            for ro in s.get("rosters") or []:
                tname = (ro.get("team") or {}).get("displayName")
                starters = [p["athlete"]["displayName"] for p in ro.get("roster") or [] if p.get("starter") and p.get("athlete")]
                if tname:
                    con.execute("INSERT OR REPLACE INTO lineups VALUES (?,?,?,?,?)",
                                (r["event_id"], tname, int(len(starters) == 11), json.dumps(starters), ts))
                    out["lineups"] += 1
    con.commit()
    return out


def context_for(con, event_id: str, sport: str, home: str, away: str) -> dict:
    """Injuries (with key-player flags), external forecast and lineup status for one event."""
    _ensure(con)
    out = {}
    if sport in ("nba", "nfl"):
        keys = {(r["team"], r["player"]) for r in con.execute("SELECT team, player FROM key_players WHERE sport=?", (sport,))}
        inj = {}
        for team in (home, away):
            rows = con.execute("SELECT player, status, detail FROM injuries_current WHERE sport=? AND team=? "
                               "AND status IN ('Out','Doubtful','Questionable','Day-To-Day') ORDER BY status", (sport, team)).fetchall()
            inj[team] = [{"player": x["player"], "status": x["status"], "key": (team, x["player"]) in keys} for x in rows]
        out["injuries"] = inj
    f = con.execute("SELECT * FROM external_forecasts WHERE event_id=?", (event_id,)).fetchone()
    if f:
        probs = {home: f["p_home"], away: f["p_away"]}
        if f["p_draw"] is not None:
            probs["Draw"] = f["p_draw"]
        out["external_forecast"] = {"source": f["source"], "probs": probs, "retrieved_at": f["retrieved_at"],
                                    "url": f["source_url"]}
    w = con.execute("SELECT * FROM event_weather WHERE event_id=?", (event_id,)).fetchone()
    if w:
        out["weather"] = {"temperature_f": w["temperature_f"], "gust_mph": w["gust_mph"], "precip_pct": w["precip_pct"],
                          "retrieved_at": w["retrieved_at"], "notable": bool((w["gust_mph"] or 0) >= 20 or (w["precip_pct"] or 0) >= 60
                                                                             or (w["temperature_f"] or 60) <= 25)}
    lu = con.execute("SELECT team, confirmed FROM lineups WHERE event_id=?", (event_id,)).fetchall()
    if lu:
        out["lineups_confirmed"] = all(x["confirmed"] for x in lu) and len(lu) == 2
    return out


def snapshot_hash(ctx: dict) -> str:
    return hashlib.sha1(json.dumps(ctx, sort_keys=True, default=str).encode()).hexdigest()[:12]
