"""Source coverage audit: what the stored data actually covers, measured, not assumed.

`python -m sbi coverage` reads the database READ-ONLY and writes
  data/coverage/latest.json and reports/source_coverage.md
(developer reports; nothing here is shown on the public site).

It answers, per sport x competition x market x source:
  * how many upcoming events are priced, and how old the newest quote is;
  * how many bookmaker NAMES there are versus how many independent OPERATORS. Only bookmakers
    with an entry in the ownership map (sources/books.py GROUPS) are counted as known operators.
    A bookmaker with no entry is UNKNOWN: it is never assumed independent, so operator counts
    are a range (lower bound: known operators only; upper bound: every unknown one is separate);
  * what a quote's age actually measures: the bookmaker's own update time, the publication
    time of a file, or merely when Doyen first saw the price (see TIMESTAMP_BASIS);
  * whether a sharp reference price (Pinnacle / Betfair Exchange) is present;
and separately: which providers are configured versus actually succeeding, credentials by
presence only (never values), The Odds API credit use per day, and stored history.

A frozen snapshot (data/coverage/baseline_*.json) is the "before" that later data-source
changes are measured against. No network calls, no writes to the database.
"""
from __future__ import annotations

import json
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

from . import config
from .sources.books import GROUPS, normalize_book
from .sources.football_data import AGGREGATES

SHARP = ("Pinnacle", "Betfair Exchange")       # the references ev.CONSENSUS_PRIORITY trusts
CREDENTIALS = ("ODDS_API_KEY",)                # reported by presence only
SPORT_NAMES = {"football": "soccer", "nfl": "nfl", "nba": "nba", "tennis": "tennis"}
SUMMARY_KEYS = ("scheduled_events", "with_any_quote", "with_fresh_quote_observed", "with_fresh_quote_bookmaker_timed",
                "with_3plus_operators_lower", "with_3plus_operators_upper", "with_sharp_reference",
                "bookmaker_names", "known_operators", "unknown_bookmakers")

# What `odds.retrieved_at` means differs by source. Only the first is evidence of a recent REPRICE.
#   bookmaker_update : the bookmaker's own last-update time, as passed on by the provider
#   file_published   : HTTP Last-Modified of the file (when the snapshot was published; prices are older)
#   first_seen       : when Doyen first fetched this price. The bookmaker's update time is unknown,
#                      so a small age means "recently observed", not "recently repriced".
TIMESTAMP_BASIS = {"the-odds-api.com": "bookmaker_update", "football-data.co.uk": "file_published"}
FIRST_SEEN = "first_seen"        # the weakest claim, and the default for any source not listed above
BASIS_TEXT = {"bookmaker_update": "bookmaker's own update time", "file_published": "file publication time",
              FIRST_SEEN: "first seen by Doyen (reprice time unknown)"}


def timestamp_basis(source: str) -> str:
    return TIMESTAMP_BASIS.get(source, FIRST_SEEN)


def operator_bounds(books) -> tuple[int, int]:
    """(lower, upper) number of independent operators behind a set of normalised bookmaker names.

    Known = has an entry in the ownership map. Unknown bookmakers are never assumed independent:
    each could be a separate operator (upper bound) or a brand of one already counted (lower bound)."""
    books = set(books)
    known = {GROUPS[b] for b in books if b in GROUPS}
    unknown = {b for b in books if b not in GROUPS}
    lower = len(known) if known else (1 if unknown else 0)
    return lower, len(known) + len(unknown)


def connect_ro(path: Path | str | None = None) -> sqlite3.Connection:
    """Read-only connection: the audit must never modify the database."""
    con = sqlite3.connect(f"file:{Path(path or config.DB_PATH)}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _has(con, table: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _age_h(now: datetime, iso: str) -> float:
    t = datetime.fromisoformat(iso)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (now - t).total_seconds() / 3600


def _upcoming_quotes(con, now: datetime, horizon_h: float):
    """Latest pre-match quote time per (event, market, source, normalised bookmaker) for upcoming events."""
    end = (now + timedelta(hours=horizon_h)).isoformat()
    events = {r["event_id"]: (r["sport"], r["league"]) for r in con.execute(
        "SELECT event_id, sport, league FROM events WHERE status='scheduled' AND kickoff_utc > ? AND kickoff_utc <= ?",
        (now.isoformat(), end))}
    latest: dict[tuple, str] = {}
    raw_names: dict[tuple, set] = defaultdict(set)
    for r in con.execute("""SELECT o.event_id, o.market, o.source, o.bookmaker, MAX(o.retrieved_at) m
                            FROM odds o JOIN events e ON e.event_id = o.event_id
                            WHERE o.kind='pre' AND e.status='scheduled' AND e.kickoff_utc > ? AND e.kickoff_utc <= ?
                            GROUP BY o.event_id, o.market, o.source, o.bookmaker""", (now.isoformat(), end)):
        book = normalize_book(r["bookmaker"])
        if not book or book in AGGREGATES:      # in-play feeds and Max/Avg are not bookmakers
            continue
        k = (r["event_id"], r["market"], r["source"], book)
        if k not in latest or r["m"] > latest[k]:
            latest[k] = r["m"]
        raw_names[(r["event_id"], r["market"], r["source"])].add(r["bookmaker"])
    return events, latest, raw_names


def matrix(con, now: datetime, horizon_h: float = 168, fresh_h: float | None = None) -> list[dict]:
    """sport x competition x market x source rows for events starting in the next `horizon_h` hours."""
    fresh_h = config.RULES.max_odds_age_hours if fresh_h is None else fresh_h
    events, latest, raw_names = _upcoming_quotes(con, now, horizon_h)
    cells: dict[tuple, dict] = {}
    for (eid, market, source, book), ts in latest.items():
        sport, league = events[eid]
        c = cells.setdefault((sport, league, market, source),
                             {"events": set(), "fresh_events": set(), "names": set(), "books": set(), "newest": {}})
        c["events"].add(eid)
        c["books"].add(book)
        c["names"] |= raw_names[(eid, market, source)]
        if _age_h(now, ts) <= fresh_h:
            c["fresh_events"].add(eid)
        if eid not in c["newest"] or ts > c["newest"][eid]:
            c["newest"][eid] = ts
    scheduled = defaultdict(int)
    for sport, league in events.values():
        scheduled[(sport, league)] += 1
    rows = []
    for (sport, league, market, source), c in sorted(cells.items()):
        ages = [_age_h(now, t) for t in c["newest"].values()]
        rows.append({
            "sport": SPORT_NAMES.get(sport, sport), "competition": league, "market": market, "source": source,
            "scheduled_events": scheduled[(sport, league)], "events_priced": len(c["events"]),
            "events_priced_fresh": len(c["fresh_events"]),
            "bookmaker_names": len(c["names"]), "bookmakers": len(c["books"]),
            "operators_lower": operator_bounds(c["books"])[0], "operators_upper": operator_bounds(c["books"])[1],
            "timestamp_basis": timestamp_basis(source),
            "sharp_references": sorted(b for b in c["books"] if b in SHARP),
            "median_quote_age_h": round(median(ages), 1), "newest_quote": max(c["newest"].values()),
        })
    return rows


def summary(con, now: datetime, horizon_h: float = 168, fresh_h: float | None = None) -> dict:
    """Per sport: how many upcoming events can be compared across independent books, as a range.

    * observed fresh: some quote has a timestamp within `fresh_h`, whatever that timestamp means;
    * bookmaker-timed fresh: a quote whose timestamp is the bookmaker's own update time is within `fresh_h`;
    * 3+ operators (lower / upper): at least one market has observed-fresh quotes from three or more
      operators, counting only known operators (lower) or treating every unknown bookmaker as separate (upper).

    These are audit measures of raw material, not of prices that can be bet now. The pick rules in
    sbi.ev are stricter (complete selections, sanity filters) and are not changed by this module."""
    fresh_h = config.RULES.max_odds_age_hours if fresh_h is None else fresh_h
    events, latest, raw_names = _upcoming_quotes(con, now, horizon_h)
    per_market: dict[tuple, set] = defaultdict(set)     # (event, market) -> observed-fresh books
    any_quote, names, books, timed = defaultdict(set), defaultdict(set), defaultdict(set), defaultdict(set)
    for (eid, market, source, book), ts in latest.items():
        sport = events[eid][0]
        any_quote[sport].add(eid)
        books[sport].add(book)
        names[sport] |= raw_names[(eid, market, source)]
        if _age_h(now, ts) <= fresh_h:
            per_market[(eid, market)].add(book)
            if timestamp_basis(source) == "bookmaker_update":
                timed[sport].add(eid)
    out = {}
    for sport in sorted({s for s, _ in events.values()}):
        ids = {e for e, (s, _) in events.items() if s == sport}
        mine = {k: b for k, b in per_market.items() if k[0] in ids and b}
        out[SPORT_NAMES.get(sport, sport)] = {
            "scheduled_events": len(ids), "with_any_quote": len(any_quote[sport]),
            "with_fresh_quote_observed": len({e for e, _ in mine}),
            "with_fresh_quote_bookmaker_timed": len(timed[sport]),
            "with_3plus_operators_lower": len({e for (e, _), b in mine.items() if operator_bounds(b)[0] >= 3}),
            "with_3plus_operators_upper": len({e for (e, _), b in mine.items() if operator_bounds(b)[1] >= 3}),
            "with_sharp_reference": len({e for (e, _), b in mine.items() if any(x in SHARP for x in b)}),
            "bookmaker_names": len(names[sport]),
            "known_operators": len({GROUPS[b] for b in books[sport] if b in GROUPS}),
            "unknown_bookmakers": len({b for b in books[sport] if b not in GROUPS}),
        }
    return out


def book_audit(con) -> dict:
    """Every stored bookmaker name -> normalised name -> operator, split into known and unknown ownership."""
    raw = [r[0] for r in con.execute("SELECT DISTINCT bookmaker FROM odds ORDER BY 1")]
    groups: dict[str, set] = defaultdict(set)
    variants, unknown, excluded = {}, set(), []
    for name in raw:
        book = normalize_book(name)
        if not book or book in AGGREGATES:
            excluded.append(name)
        elif book in GROUPS:
            groups[GROUPS[book]].add(book)
        else:
            unknown.add(book)
        if book and book != name:
            variants[name] = book
    lower, upper = operator_bounds({b for v in groups.values() for b in v} | unknown)
    return {"stored_names": len(raw), "bookmakers": sum(len(v) for v in groups.values()) + len(unknown),
            "known_operators": len(groups), "unknown_ownership": sorted(unknown),
            "operators_lower": lower, "operators_upper": upper,
            "known_operator_brands": {g: sorted(b) for g, b in sorted(groups.items())},
            "name_variants_merged": variants, "excluded_not_bookmakers": excluded}


def sources(con, now: datetime, working_h: float = 6.0) -> dict:
    """Configured versus actually working: a provider is 'working' if its last success is recent."""
    prov = {}
    if _has(con, "provider_status"):
        for r in con.execute("SELECT * FROM provider_status ORDER BY provider"):
            age = round(_age_h(now, r["last_success"]), 1) if r["last_success"] else None
            prov[r["provider"]] = {"last_success": r["last_success"], "hours_since_success": age,
                                   "working": age is not None and age <= working_h, "rows_last": r["rows_last"],
                                   "last_error": r["last_error"]}
    jobs = defaultdict(dict)
    if _has(con, "job_runs"):
        for r in con.execute("SELECT job, status, COUNT(*) n FROM job_runs WHERE job LIKE 'ingest%' GROUP BY 1,2"):
            jobs[r["job"]][r["status"]] = r["n"]
    return {"providers": prov, "ingest_job_runs": dict(jobs)}


def credentials(con) -> dict:
    """Presence only. Values are never read into the report."""
    out = {name: {"set_in_this_environment": bool(os.environ.get(name, "").strip())} for name in CREDENTIALS}
    if _has(con, "job_runs"):
        last_ok = None
        for r in con.execute("SELECT started_at, details FROM job_runs WHERE job='ingest-odds-api' ORDER BY id DESC"):
            try:
                d = json.loads(r["details"] or "{}")
            except ValueError:
                continue
            if "skipped" not in d and d.get("credits_remaining_after") not in (None, ""):
                last_ok = r["started_at"]
                break
        out["ODDS_API_KEY"]["last_run_that_used_a_working_key"] = last_ok
    return out


def odds_api_usage(con) -> dict:
    """Credits actually spent, from the job log (each ingest-odds-api run records what it spent)."""
    out = {"credits_by_day": {}, "credits_remaining_after_last_run": None}
    if not _has(con, "job_runs"):
        return out
    for r in con.execute("SELECT started_at, details FROM job_runs WHERE job='ingest-odds-api' ORDER BY id"):
        try:
            d = json.loads(r["details"] or "{}")
        except ValueError:
            continue
        if d.get("credits_spent"):
            day = out["credits_by_day"].setdefault(r["started_at"][:10], {"credits": 0, "runs_that_spent": 0})
            day["credits"] += int(d["credits_spent"])
            day["runs_that_spent"] += 1
        if d.get("credits_remaining_after") not in (None, ""):
            out["credits_remaining_after_last_run"] = int(d["credits_remaining_after"])
    return out


def history(con) -> dict:
    """What is stored for validation: finished events and odds rows by kind, per sport."""
    out: dict = defaultdict(lambda: {"finished_events": 0, "first": None, "last": None, "odds_rows_by_kind": {}})
    for r in con.execute("""SELECT sport, COUNT(*) n, MIN(kickoff_utc) a, MAX(kickoff_utc) b FROM events
                            WHERE status='finished' GROUP BY 1"""):
        out[SPORT_NAMES.get(r["sport"], r["sport"])].update(finished_events=r["n"], first=r["a"][:10], last=r["b"][:10])
    for r in con.execute("""SELECT e.sport, o.kind, COUNT(*) n FROM odds o JOIN events e ON e.event_id=o.event_id
                            GROUP BY 1,2"""):
        out[SPORT_NAMES.get(r["sport"], r["sport"])]["odds_rows_by_kind"][r["kind"]] = r["n"]
    return dict(out)


def context(con, now: datetime) -> dict:
    out = {"scheduled_events_past_start": {SPORT_NAMES.get(r[0], r[0]): r[1] for r in con.execute(
        "SELECT sport, COUNT(*) FROM events WHERE status='scheduled' AND kickoff_utc < ? GROUP BY 1",
        ((now - timedelta(hours=6)).isoformat(),))}}
    if _has(con, "injuries_current"):
        out["injuries_current"] = {r[0]: r[1] for r in con.execute("SELECT sport, COUNT(*) FROM injuries_current GROUP BY 1")}
    if _has(con, "nfl_report_current"):      # nflverse practice/injury reports (opt-in adapter, issue #17)
        r = con.execute("""SELECT COUNT(*), COUNT(DISTINCT team), COUNT(DISTINCT season || '-' || week),
                           COALESCE(SUM(report_status IS NOT NULL),0), COALESCE(SUM(practice_status IS NOT NULL),0)
                           FROM nfl_report_current WHERE retracted_at IS NULL""").fetchone()
        out["nfl_reports"] = {"player_weeks": r[0], "teams": r[1], "weeks": r[2], "with_designation": r[3],
                              "with_practice_status": r[4],
                              "updates_logged": con.execute("SELECT COUNT(*) FROM nfl_report_updates").fetchone()[0]}
    if _has(con, "lineups"):
        r = con.execute("SELECT COUNT(*), COALESCE(SUM(confirmed),0) FROM lineups").fetchone()
        out["lineups"] = {"team_rows": r[0], "confirmed": r[1]}
    if _has(con, "external_forecasts"):
        out["external_forecasts"] = {r[0]: r[1] for r in con.execute("SELECT source, COUNT(*) FROM external_forecasts GROUP BY 1")}
    if _has(con, "odds_match_audit"):
        r = con.execute("SELECT COUNT(*), MIN(score), SUM(swapped) FROM odds_match_audit").fetchone()
        out["odds_event_matching"] = {"matched_events": r[0], "lowest_name_score": r[1], "player_order_swapped": r[2] or 0}
    return out


def build(con, now: datetime, horizon_h: float = 168) -> dict:
    return {"as_of": now.isoformat(), "horizon_hours": horizon_h, "fresh_quote_max_age_hours": config.RULES.max_odds_age_hours,
            "timestamp_basis": {**TIMESTAMP_BASIS, "(any other source)": FIRST_SEEN},
            "summary": summary(con, now, horizon_h), "matrix": matrix(con, now, horizon_h),
            "bookmakers": book_audit(con), "sources": sources(con, now), "credentials": credentials(con),
            "odds_api_usage": odds_api_usage(con), "history": history(con), "context": context(con, now)}


def latest_baseline(directory: Path | None = None) -> Path | None:
    files = sorted((directory or config.DATA_DIR / "coverage").glob("baseline_*.json"))
    return files[-1] if files else None


def delta(report: dict, baseline: dict) -> dict:
    """Per sport and measure: (baseline, now, change). Sports missing on one side count as zero."""
    out = {}
    for sport in sorted(set(report["summary"]) | set(baseline.get("summary", {}))):
        a, b = baseline.get("summary", {}).get(sport, {}), report["summary"].get(sport, {})
        out[sport] = {k: {"baseline": a.get(k, 0), "now": b.get(k, 0), "change": b.get(k, 0) - a.get(k, 0)}
                      for k in SUMMARY_KEYS}
    return out


def to_markdown(rep: dict, cmp: dict | None = None, baseline_as_of: str | None = None) -> str:
    fh = rep["fresh_quote_max_age_hours"]
    L = [f"# Source coverage audit ({rep['as_of'][:16].replace('T', ' ')} UTC)", "",
         f"Measured from the stored database for events starting in the next {rep['horizon_hours']:g} hours. "
         "Generated by `python -m sbi coverage`; see docs/DATA_SOURCES.md.", "",
         "**How to read this.** These are stored, delayed quotes used for research. Nothing here is a live or "
         "executable price.", "",
         f"- **Observed fresh** means a stored quote carries a timestamp at most {fh:g}h old. What that timestamp is "
         "depends on the source (see *Age basis* in the matrix). For ESPN it is only when Doyen first saw the price, "
         "so a small age shows the price was recently *observed*, not that the bookmaker recently *repriced* it.",
         f"- **Bookmaker-timed fresh** counts only quotes whose timestamp is the bookmaker's own update time (at most {fh:g}h old).",
         "- **Operators** are a range. *Lower* counts only bookmakers whose owner or pricing platform is recorded in the map in "
         "`sbi/sources/books.py`. *Upper* also treats every bookmaker of unknown ownership as a separate operator. "
         "Unknown ownership is never assumed independent, so anything above the lower bound is provisional.", "",
         "## Per sport", "",
         "| Sport | Scheduled | Any quote | Observed fresh | Bookmaker-timed fresh | 3+ operators (lower) | "
         "3+ operators (upper, provisional) | Sharp reference | Names | Known operators | Unknown ownership |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for s, v in rep["summary"].items():
        L.append(f"| {s} | " + " | ".join(str(v[k]) for k in SUMMARY_KEYS) + " |")
    if cmp:
        L += ["", f"## Change since baseline ({(baseline_as_of or '')[:16].replace('T', ' ')} UTC)", "",
              "| Sport | Measure | Baseline | Now | Change |", "|---|---|---|---|---|"]
        for s, d in cmp.items():
            for k, v in d.items():
                L.append(f"| {s} | {k.replace('_', ' ')} | {v['baseline']} | {v['now']} | {v['change']:+d} |")
    L += ["", "## Coverage matrix", "",
          "| Sport | Competition | Market | Source | Events priced / scheduled | Observed fresh | Names | "
          "Operators (lower–upper) | Sharp | Median age h | Age basis |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rep["matrix"]:
        L.append(f"| {r['sport']} | {r['competition']} | {r['market']} | {r['source']} | "
                 f"{r['events_priced']} / {r['scheduled_events']} | {r['events_priced_fresh']} | {r['bookmaker_names']} | "
                 f"{r['operators_lower']}–{r['operators_upper']} | {', '.join(r['sharp_references']) or 'none'} | "
                 f"{r['median_quote_age_h']} | {BASIS_TEXT[r['timestamp_basis']]} |")
    b = rep["bookmakers"]
    L += ["", "## Bookmaker independence", "",
          f"- {b['stored_names']} stored names are {b['bookmakers']} bookmakers after merging name variants.",
          f"- **Known operators: {b['known_operators']}** (owner or pricing platform recorded in the map): "
          + ("; ".join(f"{g} ({', '.join(v)})" if v != [g] else g for g, v in b["known_operator_brands"].items()) or "none") + ".",
          f"- **Unknown ownership: {len(b['unknown_ownership'])}** (not verified, not counted as independent): "
          + (", ".join(b["unknown_ownership"]) or "none") + ".",
          f"- Independent operators overall: **between {b['operators_lower']} and {b['operators_upper']}**. "
          "The upper figure is provisional until ownership and pricing-platform independence are verified.",
          "- Name variants merged: " + (", ".join(f"{k} → {v}" for k, v in b["name_variants_merged"].items()) or "none") + ".",
          "- Excluded (aggregates or in-play feeds, not bookmakers): " + (", ".join(b["excluded_not_bookmakers"]) or "none") + ".",
          "", "## Providers: configured versus working", "",
          "| Provider | Working | Hours since success | Rows last run | Last error |", "|---|---|---|---|---|"]
    for p, v in rep["sources"]["providers"].items():
        L.append(f"| {p} | {'yes' if v['working'] else 'NO'} | {v['hours_since_success']} | {v['rows_last']} | "
                 f"{(v['last_error'] or '')[:90].replace('|', '/')} |")
    L += ["", "Ingest job runs by status: " + "; ".join(
        f"{j} ({', '.join(f'{k} {n}' for k, n in sorted(s.items()))})" for j, s in sorted(rep["sources"]["ingest_job_runs"].items())) + ".",
          "", "## Credentials (presence only)", ""]
    for name, v in rep["credentials"].items():
        L.append(f"- `{name}`: " + "; ".join(f"{k.replace('_', ' ')}: {x}" for k, x in v.items()))
    u = rep["odds_api_usage"]
    L += ["", "## The Odds API credits", "",
          f"- Remaining after the last run: {u['credits_remaining_after_last_run']}",
          "- Spent per day: " + (", ".join(f"{d}: {v['credits']} credits in {v['runs_that_spent']} runs"
                                           for d, v in u["credits_by_day"].items()) or "none recorded"),
          "", "## Stored history", "", "| Sport | Finished events | From | To | Odds rows by kind |", "|---|---|---|---|---|"]
    for s, v in rep["history"].items():
        L.append(f"| {s} | {v['finished_events']} | {v['first']} | {v['last']} | "
                 f"{', '.join(f'{k} {n}' for k, n in sorted(v['odds_rows_by_kind'].items())) or 'none'} |")
    L += ["", "## Context feeds", ""] + [f"- {k}: {v}" for k, v in rep["context"].items()]
    return "\n".join(L) + "\n"


def write(now: datetime | None = None, baseline: bool = False, db_path: Path | str | None = None) -> dict:
    """Build the report and write latest.json + source_coverage.md (and a dated baseline if asked)."""
    now = now or datetime.now(timezone.utc).replace(microsecond=0)
    con = connect_ro(db_path)
    try:
        rep = build(con, now)
    finally:
        con.close()
    out_dir = config.DATA_DIR / "coverage"
    out_dir.mkdir(parents=True, exist_ok=True)
    base_p = latest_baseline(out_dir)
    cmp = base = None
    if base_p and not baseline:
        base = json.loads(base_p.read_text())
        cmp = delta(rep, base)
        rep["baseline"] = {"file": base_p.name, "as_of": base.get("as_of"), "delta": cmp}
    text = json.dumps(rep, indent=1, default=str)
    (out_dir / "latest.json").write_text(text + "\n")
    if baseline:
        (out_dir / f"baseline_{now:%Y-%m-%d}.json").write_text(text + "\n")
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (config.REPORTS_DIR / "source_coverage.md").write_text(to_markdown(rep, cmp, base.get("as_of") if base else None))
    return rep
