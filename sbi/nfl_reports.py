"""NFL availability report: practice participation, game designations and quarterback risk flags.

Derived, read-only view over what `sources/nflverse_injuries.py` stored, for upcoming NFL games:
  * per team: official designations (Out / Doubtful / Questionable) and practice participation
    (DNP / Limited / Full), kept apart. Participation is never turned into an availability call;
  * source health: when the provider published, when Doyen last checked, whether that is stale;
  * missingness: teams with no rows for the game week, and games that cannot be mapped to a week;
  * quarterbacks: last game's starter (from results), whether he is on the report, and whether the
    nflverse schedule lists someone else. A starter is never reported as confirmed: no free source
    used here publishes confirmed starters before kick-off;
  * disagreements with the ESPN injury list already stored (`injuries_current`).

Informational only. Nothing here changes probabilities, calibration, thresholds, odds or picks, and
nothing is shown on the public site. Written to reports/nfl_availability.md (developer report).
"""
from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from . import config
from .sources import nflverse_injuries as nv

GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
DESIGNATIONS = ("Out", "Doubtful", "Questionable")
STALE_HOURS = 36.0        # the provider documents one update a day; 36h means at least one was missed
_SUFFIX = {"jr", "sr", "ii", "iii", "iv", "v"}


def load_games(content: bytes) -> list[dict]:
    """nflverse games.csv -> the columns used here. `played` means a final score is present."""
    out = []
    for r in csv.DictReader(io.StringIO(content.decode("utf-8-sig"))):
        try:
            season, week = int(r["season"]), int(r["week"])
        except (KeyError, TypeError, ValueError):
            continue
        out.append({"game_id": r.get("game_id"), "season": season, "game_type": r.get("game_type") or "REG", "week": week,
                    "gameday": r.get("gameday") or "", "home": r.get("home_team"), "away": r.get("away_team"),
                    "played": bool((r.get("home_score") or "").strip()), "espn": (r.get("espn") or "").strip(),
                    "home_qb_id": (r.get("home_qb_id") or "").strip() or None, "home_qb": (r.get("home_qb_name") or "").strip() or None,
                    "away_qb_id": (r.get("away_qb_id") or "").strip() or None, "away_qb": (r.get("away_qb_name") or "").strip() or None})
    return out


def fetch_games() -> list[dict]:
    """Same file and cache entry the NFL model already downloads, so this adds no request to a run."""
    from .sources.http import fetch
    return load_games(fetch(GAMES_URL, max_age_hours=12)[0])


def last_starters(games: list[dict]) -> dict:
    """team -> the quarterback who started that team's most recent PLAYED game (a fact, from results)."""
    out = {}
    for g in sorted((g for g in games if g["played"]), key=lambda g: (g["season"], g["gameday"], g["week"])):
        for side in ("home", "away"):
            if g[f"{side}_qb_id"]:
                out[g[side]] = {"gsis_id": g[f"{side}_qb_id"], "name": g[f"{side}_qb"], "game_id": g["game_id"]}
    return out


def name_key(name: str | None) -> str:
    """Comparison key for ESPN names, which carry no player id: accents, punctuation and generational
    suffixes removed. Used only within one team, and only when the key is unique there."""
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    toks = [t for t in re.sub(r"[^a-z ]", "", s.replace("-", " ")).split() if t not in _SUFFIX]
    return " ".join(toks)


def _age_h(now: datetime, iso: str | None) -> float | None:
    if not iso:
        return None
    t = datetime.fromisoformat(iso)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return round((now - t).total_seconds() / 3600, 1)


def _has(con, table: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def source_health(con, now: datetime, season: int) -> dict:
    """Last attempt, last success, and how old the provider's own publication is."""
    out = {"season": season, "last_attempt": None, "last_outcome": None, "last_error": None, "last_success": None,
           "source_published_at": None, "published_age_h": None, "checked_age_h": None, "stale": True,
           "outcomes": {}, "url": nv.URL.format(season=season)}
    if not _has(con, "nfl_report_fetches"):
        return out
    rows = con.execute("SELECT * FROM nfl_report_fetches WHERE season=? ORDER BY id", (season,)).fetchall()
    out["outcomes"] = dict(Counter(r["outcome"] for r in rows))
    if rows:
        out.update(last_attempt=rows[-1]["fetched_at"], last_outcome=rows[-1]["outcome"], last_error=rows[-1]["error"])
    ok = [r for r in rows if r["outcome"] in ("fetched", "not_modified")]
    if ok:
        out.update(last_success=ok[-1]["fetched_at"], source_published_at=ok[-1]["source_published_at"],
                   checked_age_h=_age_h(now, ok[-1]["fetched_at"]),
                   published_age_h=_age_h(now, ok[-1]["source_published_at"]))
        age = out["published_age_h"] if out["published_age_h"] is not None else out["checked_age_h"]
        out["stale"] = age is None or age > STALE_HOURS or (out["checked_age_h"] or 0) > STALE_HOURS
    return out


def _espn_compare(con, team_name: str, rows: list) -> dict:
    """nflverse designations against ESPN's list for one team. Players are paired by name within the
    team only; a name that is not unique on either side is left unpaired and counted."""
    out = {"available": False, "status_conflicts": [], "espn_only": [], "nflverse_only": [],
           "espn_designated_nflverse_pending": 0, "ambiguous_names": 0, "espn_retrieved_at": None}
    if not _has(con, "injuries_current"):
        return out
    espn_rows = con.execute("SELECT player, status, reported, retrieved_at FROM injuries_current WHERE sport='nfl' AND team=?",
                            (team_name,)).fetchall()
    if not espn_rows:
        return out
    out["available"] = True
    out["espn_retrieved_at"] = max(r["retrieved_at"] for r in espn_rows)
    ek, nk = defaultdict(list), defaultdict(list)
    for r in espn_rows:
        ek[name_key(r["player"])].append(r)
    for r in rows:
        nk[name_key(r["player"])].append(r)
    out["ambiguous_names"] = sum(1 for d in (ek, nk) for v in d.values() if len(v) > 1)
    espn = {k: v[0] for k, v in ek.items() if len(v) == 1 and k}
    mine = {k: v[0] for k, v in nk.items() if len(v) == 1 and k}
    for k, n in mine.items():
        e = espn.get(k)
        es = e["status"] if e else None
        if n["report_status"] in DESIGNATIONS:
            if es in DESIGNATIONS and es != n["report_status"]:
                out["status_conflicts"].append({"player": n["player"], "nflverse": n["report_status"], "espn": es,
                                                "espn_reported": e["reported"]})
            elif es not in DESIGNATIONS:
                out["nflverse_only"].append({"player": n["player"], "nflverse": n["report_status"], "espn": es})
        elif es in DESIGNATIONS:
            out["espn_designated_nflverse_pending"] += 1
    for k, e in espn.items():
        if e["status"] in DESIGNATIONS and k not in mine and k not in nk:
            out["espn_only"].append({"player": e["player"], "espn": e["status"], "espn_reported": e["reported"]})
    return out


def _team(con, g: dict, side: str, starters: dict) -> dict:
    abbr = g[side]
    name = nv.TEAMS.get(abbr)
    rows = con.execute("""SELECT * FROM nfl_report_current WHERE season=? AND game_type=? AND week=? AND team=?
                          AND retracted_at IS NULL ORDER BY player""", (g["season"], g["game_type"], g["week"], abbr)).fetchall()
    des = Counter(r["report_status"] for r in rows if r["report_status"])
    pra = Counter(r["practice_status"] for r in rows if r["practice_status"])
    state = "missing" if not rows else ("designated" if any(des.get(d) for d in DESIGNATIONS) else "practice_only")
    last = starters.get(abbr)
    listed_id, listed = g[f"{side}_qb_id"], g[f"{side}_qb"]
    qbs = [{"player": r["player"], "gsis_id": r["gsis_id"], "report_status": r["report_status"],
            "practice_status": r["practice_status"], "injury": r["report_injury"] or r["practice_injury"],
            "is_last_starter": bool(last and r["gsis_id"] == last["gsis_id"])} for r in rows if r["position"] == "QB"]
    flags = []
    for q in qbs:
        if not q["is_last_starter"]:
            continue
        if q["report_status"] in DESIGNATIONS:
            flags.append(f"last game's starter {q['player']} is designated {q['report_status']}")
        elif q["practice_status"] in ("DNP", "Limited"):
            flags.append(f"last game's starter {q['player']} practice: {q['practice_status']}; no designation published")
    if last and listed_id and listed_id != last["gsis_id"]:
        flags.append(f"schedule file lists {listed} instead of last game's starter {last['name']} (unconfirmed)")
    return {"team": abbr, "team_name": name, "state": state, "listed_players": len(rows),
            "designations": {d: des.get(d, 0) for d in DESIGNATIONS}, "other_report_status": des.get("Probable", 0),
            "practice": {p: pra.get(p, 0) for p in ("DNP", "Limited", "Full")},
            "newest_change": max((r["last_changed"] for r in rows), default=None),
            "qb": {"last_starter": last, "schedule_listed": {"gsis_id": listed_id, "name": listed} if listed_id else None,
                   "on_report": qbs, "flags": flags, "confirmed_starter": None},
            "espn": _espn_compare(con, name, rows) if name else {"available": False}}


def build(con, now: datetime, games: list[dict], horizon_h: float = 192) -> dict:
    """Report for scheduled NFL events starting within `horizon_h` hours."""
    nv.ensure(con)
    season = nv.season_for(now)
    by_espn = {g["espn"]: g for g in games if g["espn"]}
    starters = last_starters(games)
    events = con.execute("""SELECT event_id, kickoff_utc, home, away FROM events WHERE league='NFL' AND status='scheduled'
                            AND kickoff_utc > ? AND kickoff_utc <= ? ORDER BY kickoff_utc, event_id""",
                         (now.isoformat(), (now + timedelta(hours=horizon_h)).isoformat())).fetchall()
    out_games, unmapped = [], []
    for e in events:
        g = by_espn.get(e["event_id"].split(":")[-1])
        if not g or g["home"] not in nv.TEAMS or g["away"] not in nv.TEAMS:
            unmapped.append({"event_id": e["event_id"], "home": e["home"], "away": e["away"]})
            continue
        if nv.TEAMS[g["home"]] != e["home"] or nv.TEAMS[g["away"]] != e["away"]:   # ids agree but teams do not: do not guess
            unmapped.append({"event_id": e["event_id"], "home": e["home"], "away": e["away"], "reason": "team mismatch"})
            continue
        out_games.append({"event_id": e["event_id"], "kickoff_utc": e["kickoff_utc"], "season": g["season"],
                          "game_type": g["game_type"], "week": g["week"],
                          "home": _team(con, g, "home", starters), "away": _team(con, g, "away", starters)})
    teams = [t for g in out_games for t in (g["home"], g["away"])]
    since = (now - timedelta(hours=24)).isoformat()
    updates = {r[0]: r[1] for r in con.execute("SELECT change, COUNT(*) FROM nfl_report_updates WHERE season=? GROUP BY 1", (season,))}
    recent = {r[0]: r[1] for r in con.execute(
        "SELECT change, COUNT(*) FROM nfl_report_updates WHERE season=? AND observed_at>=? GROUP BY 1", (season, since))}
    stored = con.execute("""SELECT COUNT(*) n, COUNT(DISTINCT team) teams, COUNT(DISTINCT week) weeks,
                            SUM(report_status IS NOT NULL) designated, SUM(retracted_at IS NOT NULL) retracted
                            FROM nfl_report_current WHERE season=?""", (season,)).fetchone()
    return {"as_of": now.isoformat(), "horizon_hours": horizon_h, "stale_after_hours": STALE_HOURS,
            "source": {"name": "nflverse injuries", "licence": nv.LICENSE, **source_health(con, now, season)},
            "stored": {"player_weeks": stored["n"], "teams": stored["teams"], "weeks": stored["weeks"],
                       "with_designation": stored["designated"] or 0, "retracted": stored["retracted"] or 0,
                       "updates_logged": updates, "updates_last_24h": recent},
            "summary": {"scheduled_events": len(events), "mapped_games": len(out_games), "unmapped_events": len(unmapped),
                        "teams": len(teams), "teams_with_designations": sum(t["state"] == "designated" for t in teams),
                        "teams_practice_only": sum(t["state"] == "practice_only" for t in teams),
                        "teams_missing": sum(t["state"] == "missing" for t in teams),
                        "qb_flags": sum(len(t["qb"]["flags"]) for t in teams),
                        "espn_status_conflicts": sum(len(t["espn"].get("status_conflicts", [])) for t in teams),
                        "espn_only": sum(len(t["espn"].get("espn_only", [])) for t in teams),
                        "nflverse_only": sum(len(t["espn"].get("nflverse_only", [])) for t in teams),
                        "espn_designated_nflverse_pending": sum(t["espn"].get("espn_designated_nflverse_pending", 0) for t in teams)},
            "games": out_games, "unmapped": unmapped}


def history_coverage(records: list[dict], games: list[dict], season: int) -> dict:
    """What one season file covers, against the schedule: how many team-games have any row at all."""
    recs = [r for r in records if r["season"] == season]
    have = {(r["game_type"], r["week"], r["team"]) for r in recs}
    designated = {(r["game_type"], r["week"], r["team"]) for r in recs if r["report_status"] in DESIGNATIONS}
    weeks = {(r["game_type"], r["week"]) for r in recs}
    sched = {(g["game_type"], g["week"], g[s]) for g in games if g["season"] == season
             and (g["game_type"], g["week"]) in weeks for s in ("home", "away")}
    return {"season": season, "rows": len(recs), "players": len({r["gsis_id"] for r in recs}),
            "teams": len({r["team"] for r in recs}), "weeks": len(weeks),
            "team_games_scheduled": len(sched), "team_games_with_rows": len(sched & have),
            "team_games_with_designation": len(sched & designated), "team_games_no_rows": len(sched - have),
            "designations": dict(Counter(r["report_status"] for r in recs if r["report_status"])),
            "practice": dict(Counter(r["practice_status"] for r in recs if r["practice_status"])),
            "unrecognised_status_text": sum(1 for r in recs if r["report_raw"] or r["practice_raw"]),
            "rows_with_provider_time": sum(1 for r in recs if r["row_modified_at"]),
            "qb_rows": sum(1 for r in recs if r["position"] == "QB")}


def to_markdown(rep: dict) -> str:
    s, src, st = rep["summary"], rep["source"], rep["stored"]
    L = [f"# NFL availability report ({rep['as_of'][:16].replace('T', ' ')} UTC)", "",
         "Developer report from `python -m sbi nfl-reports`. **Informational risk flags only**: nothing here changes "
         "model probabilities, thresholds, odds or picks, and none of it is shown on the public site.", "",
         "**How to read this.**",
         "- *Designation* is the club's official game status (Out, Doubtful, Questionable). *Practice* is participation "
         "(DNP, Limited, Full). They are separate facts. A player with no designation is **not** assumed available or "
         "unavailable from practice alone.",
         "- *Practice only* means the club has rows for the game week but no designation yet. *Missing* means no rows at "
         "all: either nothing to report or not yet published. The feed cannot tell these two apart.",
         "- No source used here confirms a starting quarterback before kick-off. QB lines are flags to check, not facts "
         "about who starts.", "",
         "## Source health", "",
         f"- Source: nflverse injuries ({src['licence']}), `{src['url']}`",
         f"- Provider published: {src['source_published_at'] or 'unknown'} ({src['published_age_h']}h before this report)",
         f"- Last successful check: {src['last_success'] or 'never'} ({src['checked_age_h']}h ago); last attempt outcome: "
         f"{src['last_outcome'] or 'none'}" + (f"; last error: {src['last_error']}" if src["last_error"] else ""),
         f"- **Stale: {'YES' if src['stale'] else 'no'}** (stale means no publication or check within {rep['stale_after_hours']:g}h)",
         "- Fetch outcomes this season: " + (", ".join(f"{k} {v}" for k, v in sorted(src["outcomes"].items())) or "none"),
         f"- Stored this season: {st['player_weeks']} player-weeks, {st['teams']} teams, {st['weeks']} weeks, "
         f"{st['with_designation']} with a designation, {st['retracted']} retracted by the provider",
         "- Updates logged: " + (", ".join(f"{k} {v}" for k, v in sorted(st["updates_logged"].items())) or "none")
         + "; in the last 24h: " + (", ".join(f"{k} {v}" for k, v in sorted(st["updates_last_24h"].items())) or "none"),
         "", f"## Upcoming games (next {rep['horizon_hours']:g}h)", "",
         f"{s['mapped_games']} of {s['scheduled_events']} scheduled events mapped to a game week. Of {s['teams']} teams: "
         f"{s['teams_with_designations']} with designations, {s['teams_practice_only']} practice only, {s['teams_missing']} missing.", "",
         "| Kick-off (UTC) | Wk | Team | State | Out | Doubtful | Questionable | DNP | Limited | Full | Newest change seen |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for g in rep["games"]:
        for side in ("away", "home"):
            t = g[side]
            d, p = t["designations"], t["practice"]
            L.append(f"| {g['kickoff_utc'][:16].replace('T', ' ')} | {g['week']} | {t['team_name']}{' (home)' if side == 'home' else ''} | "
                     f"{t['state'].replace('_', ' ')} | {d['Out']} | {d['Doubtful']} | {d['Questionable']} | "
                     f"{p['DNP']} | {p['Limited']} | {p['Full']} | {(t['newest_change'] or '')[:16].replace('T', ' ')} |")
    if rep["unmapped"]:
        L += ["", "Events not mapped to a game week (no guess made): " + ", ".join(
            f"{u['away']} at {u['home']}" for u in rep["unmapped"])]
    L += ["", "## Quarterbacks", "",
          "| Team | Last game's starter | On this week's report | Flags |", "|---|---|---|---|"]
    for g in rep["games"]:
        for side in ("away", "home"):
            t, q = g[side], g[side]["qb"]
            on = "; ".join(f"{x['player']}: designation {x['report_status'] or 'none'}, practice {x['practice_status'] or 'none'}"
                           for x in q["on_report"]) or "no QB listed"
            L.append(f"| {t['team_name']} | {(q['last_starter'] or {}).get('name') or 'unknown'} | {on} | "
                     f"{'; '.join(q['flags']) or 'none'} |")
    L += ["", "## Disagreements with ESPN", "",
          "Players are paired by name within a team (ESPN carries no shared player id); names that are not unique are "
          "left unpaired. The two sources are read at different times, so a difference can simply be an update one "
          "of them has not published yet.", "",
          f"- Different designation in the two sources: {s['espn_status_conflicts']}",
          f"- Designated by nflverse, not by ESPN: {s['nflverse_only']}",
          f"- Designated by ESPN, on the nflverse report with practice status but no designation yet: {s['espn_designated_nflverse_pending']}",
          f"- Designated by ESPN, absent from the nflverse week (often long-term absences): {s['espn_only']}", ""]
    for g in rep["games"]:
        for side in ("away", "home"):
            t = g[side]
            for c in t["espn"].get("status_conflicts", []):
                L.append(f"- {t['team_name']}: {c['player']} is {c['nflverse']} (nflverse) but {c['espn']} (ESPN, reported {c['espn_reported']})")
    if rep.get("history"):
        L += ["", "## Stored history by season (measured from the provider's files)", "",
              "| Season | Rows | Players | Teams | Weeks | Team-games with rows / scheduled | With a designation | No rows | "
              "Out | Doubtful | Questionable | DNP | Limited | Full | Rows with provider time | QB rows |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for h in rep["history"]:
            if h.get("error"):
                L.append(f"| {h['season']} | {h['error']} |")
                continue
            d, p = h["designations"], h["practice"]
            L.append(f"| {h['season']} | {h['rows']} | {h['players']} | {h['teams']} | {h['weeks']} | "
                     f"{h['team_games_with_rows']} / {h['team_games_scheduled']} | {h['team_games_with_designation']} | "
                     f"{h['team_games_no_rows']} | {d.get('Out', 0)} | {d.get('Doubtful', 0)} | {d.get('Questionable', 0)} | "
                     f"{p.get('DNP', 0)} | {p.get('Limited', 0)} | {p.get('Full', 0)} | {h['rows_with_provider_time']} | {h['qb_rows']} |")
    L += ["", "Data: nflverse (CC-BY-4.0), https://github.com/nflverse/nflverse-data. ESPN comparison from the stored ESPN injury list."]
    return "\n".join(L) + "\n"


def write(con, now: datetime, games: list[dict], history: list[dict] | None = None) -> dict:
    rep = build(con, now, games)
    if history:
        rep["history"] = history
    out_dir = config.DATA_DIR / "coverage"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "nfl_reports_latest.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (config.REPORTS_DIR / "nfl_availability.md").write_text(to_markdown(rep))
    return rep


def run(con, now: datetime, seasons: list[int] | None = None, fetch: bool = True, history: list[int] | None = None) -> dict:
    """Fetch (unless told not to), store and write the report. Used by the CLI and the opt-in pipeline step."""
    nv.ensure(con)
    info = {"ingest": [nv.ingest(con, s) for s in (seasons or [nv.season_for(now)])] if fetch else []}
    games = fetch_games()
    hist = []
    for s in history or []:
        try:
            res = nv.conditional_fetch(nv.URL.format(season=s))
            if res["outcome"] == "not_published":
                hist.append({"season": s, "error": "not published"})
            else:
                hist.append(history_coverage(nv.parse(res["content"])[0], games, s))
        except Exception as e:  # noqa: BLE001 - history is evidence, not a dependency
            hist.append({"season": s, "error": f"{type(e).__name__}: {e}"})
    rep = write(con, now, games, hist)
    info.update(summary=rep["summary"], source=rep["source"], report=str(config.REPORTS_DIR / "nfl_availability.md"))
    return info
