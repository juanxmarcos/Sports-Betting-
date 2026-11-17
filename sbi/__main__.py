"""CLI: python -m sbi <command>"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="sbi", description="Sports Betting Doyen (research / paper trading only)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create the SQLite database")
    sub.add_parser("ingest", help="fetch fixtures, odds and results")
    sub.add_parser("settle", help="settle open paper selections")
    a = sub.add_parser("analyse", help="model upcoming fixtures and publish qualifying selections")
    a.add_argument("--horizon", type=float, default=48)
    sub.add_parser("daily", help="ingest + settle + analyse + report + dashboard")
    sub.add_parser("report", help="re-render today's report and dashboard (e.g. after research notes)")
    sub.add_parser("dashboard", help="rebuild the static dashboard")
    sub.add_parser("brief", help="write reports/research_brief.json for Claude's contextual research")
    b = sub.add_parser("backtest", help="walk-forward backtest; writes data/tuned.json")
    b.add_argument("--leagues", default="E0,E1,SP1,D1,I1,F1")
    b.add_argument("--quick", action="store_true", help="single league, small grid (smoke test)")
    b.add_argument("--fixed", action="store_true", help="reuse tuned xi/ridge (skip the tuning grid)")
    n = sub.add_parser("note", help="record a contextual research finding (risk flag only)")
    n.add_argument("--event", required=True)
    n.add_argument("--category", required=True)
    n.add_argument("--claim", required=True)
    n.add_argument("--evidence-type", required=True, choices=["verified_fact", "interpretation", "speculation"])
    n.add_argument("--direction", default="neutral", choices=["supports", "against", "neutral"])
    n.add_argument("--url")
    s = sub.add_parser("serve", help="serve the dashboard locally")
    s.add_argument("--port", type=int, default=8000)
    sub.add_parser("status", help="print system status")
    c = sub.add_parser("coverage", help="source coverage audit (read-only); writes reports/source_coverage.md")
    c.add_argument("--as-of", help="ISO-8601 UTC time to measure at (default: now)")
    c.add_argument("--baseline", action="store_true", help="also freeze this run as data/coverage/baseline_<date>.json")
    le = sub.add_parser("league-eval", help="walk-forward validation of monitoring leagues (evidence only; "
                                            "writes reports/league_validation.md, changes no model or allowlist)")
    le.add_argument("--leagues", help="comma-separated division codes (default: every monitoring league)")
    sub.add_parser("monitor-leagues", help="opt-in, LOCAL ONLY: fetch monitoring soccer leagues into "
                                           "data/local/monitoring.sqlite (gitignored; never the public database)")
    i = sub.add_parser("independence", help="bookmaker-independence audit (read-only); writes reports/independence_audit.md")
    i.add_argument("--as-of", help="ISO-8601 UTC time to measure at (default: now)")
    i.add_argument("--history", action="store_true",
                   help="also replay the backtest test seasons under both rules (network, several minutes)")
    qs = sub.add_parser("quote-sources", help="quote-source audit (read-only): licensing matrix, credit economics, "
                                              "operator yield; writes reports/quote_sources.md")
    qs.add_argument("--as-of", help="ISO-8601 UTC time to measure at (default: now)")
    qs.add_argument("--probe-bookmakers", metavar="KEYS", help="owner-run check: ONE h2h call (1 credit) for up to 10 "
                    "comma-separated bookmaker keys; stores nothing; needs ODDS_API_KEY")
    qs.add_argument("--probe-sport", default="basketball_nba", help="The Odds API sport key for --probe-bookmakers")
    nr = sub.add_parser("nfl-reports", help="NFL practice/injury/QB availability (nflverse, informational); "
                                            "writes reports/nfl_availability.md")
    nr.add_argument("--season", type=int, action="append", help="season to fetch (default: the current one)")
    nr.add_argument("--no-fetch", action="store_true", help="report from what is stored; do not fetch injury files")
    nr.add_argument("--history", type=int, nargs="*", default=[], help="also measure coverage of these season files")
    fb = sub.add_parser("forecast-bench", help="shadow benchmark of third-party soccer forecasts (research only); "
                                               "writes reports/forecast_benchmark.md")
    fb.add_argument("--openmodel-repo", help="local clone of github.com/Hicruben/theopenmodel")
    fb.add_argument("--football-analytics-repo", help="local clone of github.com/serayd61/football-predictions-open-data")
    pq = sub.add_parser("parlay-quote", help="record a combined parlay price read off a bookmaker's bet slip "
                                             "(owner only; verified, append-only; never places a bet)")
    pq.add_argument("--bookmaker", required=True, help="exactly as Doyen names it, e.g. Unibet")
    pq.add_argument("--odds", type=float, required=True, help="the slip's combined DECIMAL odds")
    pq.add_argument("--legs", required=True, help="comma-separated pick ids (python -m sbi parlay-research lists them)")
    pq.add_argument("--quoted-at", help="ISO-8601 time the slip showed this price, with timezone (default: now)")
    pq.add_argument("--source", required=True, help="where the price was seen, e.g. 'Unibet bet slip, desktop'")
    pq.add_argument("--dry-run", action="store_true", help="verify only; do not record")
    pc = sub.add_parser("parlay-candidates", help="full-slate parlay candidate research, shadow only (no network); "
                                                  "writes reports/parlay_candidates.md")
    pc.add_argument("--as-of", help="ISO timestamp to evaluate at (default: now)")
    pc.add_argument("--record", action="store_true", help="also append the shortlist to ledger/parlay_candidates_shadow.csv")
    pw = sub.add_parser("parlay-walkforward", help="walk-forward validation of multi-leg joint probabilities, "
                                                   "shadow only (no network); writes reports/parlay_walkforward.md")
    pw.add_argument("--since", help="first decision time to replay (ISO, default: all recorded runs)")
    pw.add_argument("--until", help="last decision time to replay (ISO)")
    pw.add_argument("--focus-day", default="2026-11-16", help="New York day to explain in detail")
    pw.add_argument("--record", action="store_true",
                    help="also append replayed shortlist rows to ledger/parlay_walkforward_shadow.csv")
    sub.add_parser("parlay-research", help="parlay calibration, scarcity and shadow-ledger report (read-only); "
                                           "writes reports/parlay_research.md")
    args = ap.parse_args(argv)

    from . import config, db
    now = datetime.now(timezone.utc).replace(microsecond=0)
    if args.cmd == "coverage":      # read-only: must not open the database for writing
        from . import coverage
        at = datetime.fromisoformat(args.as_of) if args.as_of else now
        rep = coverage.write(at if at.tzinfo else at.replace(tzinfo=timezone.utc), baseline=args.baseline)
        print(json.dumps(rep["summary"], indent=1))
        print(config.REPORTS_DIR / "source_coverage.md")
        return 0
    if args.cmd == "league-eval":   # evidence only: reads the database read-only, writes two report files
        from . import coverage, league_eval
        live = {}
        if config.DB_PATH.exists():
            ro = coverage.connect_ro()
            try:
                live = coverage.soccer_leagues_all(ro, now)      # adds the local monitoring file when it exists
            finally:
                ro.close()
        rep = league_eval.run(args.leagues.split(",") if args.leagues else None, live=live)
        print(json.dumps({k: v["verdict"]["status"] for k, v in rep["leagues"].items()}, indent=1))
        print(config.REPORTS_DIR / "league_validation.md")
        return 0
    if args.cmd == "monitor-leagues":   # never opens the public database
        from . import monitoring
        try:
            out = monitoring.ingest(now)
        except monitoring.NotLocalOnly as e:
            print(f"refused: {e}", file=sys.stderr)
            return 2
        print(json.dumps(out, indent=1, default=str))
        print("Local research copy only. Do not commit or publish this file.")
        return 0
    if args.cmd == "independence":  # read-only: must not open the database for writing
        from . import independence
        at = datetime.fromisoformat(args.as_of) if args.as_of else now
        rep = independence.write(at if at.tzinfo else at.replace(tzinfo=timezone.utc), with_history=args.history)
        print(json.dumps({"deployed_policy": rep["deployed_policy"], "registry": rep["registry_summary"],
                          "blocked_share": rep["upcoming"]["blocked_share"]}, indent=1))
        print(config.REPORTS_DIR / "independence_audit.md")
        return 0
    if args.cmd == "quote-sources":     # read-only as well
        from . import quote_sources
        if args.probe_bookmakers:
            print(json.dumps(quote_sources.probe(args.probe_bookmakers, args.probe_sport), indent=1))
            return 0
        at = datetime.fromisoformat(args.as_of) if args.as_of else now
        rep = quote_sources.write(at if at.tzinfo else at.replace(tzinfo=timezone.utc))
        print(json.dumps({"credit_economics": rep["credit_economics"]["total"],
                          "slots_left_for_other_operators": rep["operator_yield"]["slots_left_for_other_operators"]}, indent=1))
        print(config.REPORTS_DIR / "quote_sources.md")
        return 0
    if args.cmd == "forecast-bench":   # research only: never opens the database
        from . import forecast_bench
        rep = forecast_bench.write({"openmodel": args.openmodel_repo,
                                    "football-analytics": args.football_analytics_repo}, now=now)
        print(json.dumps({k: {"rows": v.get("rows"), "match_status": v.get("match_status")}
                          for k, v in rep["sources"].items()}, indent=1))
        print(config.REPORTS_DIR / "forecast_benchmark.md")
        return 0
    con = db.connect()

    if args.cmd == "init":
        print(f"database ready at {config.DB_PATH}")
    elif args.cmd == "ingest":
        from .pipeline import ingest
        with db.job(con, "ingest") as d:
            d.update(ingest(con, now))
        print(json.dumps(d, indent=1, default=str))
    elif args.cmd == "settle":
        from .settle import settle_all
        with db.job(con, "settle") as d:
            d.update(settle_all(con, now))
        print(d)
    elif args.cmd == "analyse":
        from .pipeline import analyse
        s = analyse(con, now, args.horizon)
        print(json.dumps({k: v for k, v in s.items() if k != "top_candidates"}, indent=1, default=str))
    elif args.cmd == "daily":
        from .pipeline import run_daily
        from .research import write_brief
        r = run_daily(con, now)
        write_brief(con, now)
        a = r["analyse"]
        print(f"analysed {a.get('analysed_events', 0)} events, published {a.get('published', 0)}; "
              f"report {r.get('publish', '')}")
        for w in a.get("warnings", [])[:20]:
            print("  warning:", w)
    elif args.cmd in ("report", "dashboard"):
        from . import dashboard, report
        if args.cmd == "report":
            last = con.execute("SELECT details FROM job_runs WHERE job='analyse' AND status='ok' ORDER BY id DESC LIMIT 1").fetchone()
            s = json.loads(last["details"]) if last else {}
            print(report.write_daily(con, now, s))
        print(dashboard.build(con))
    elif args.cmd == "brief":
        from .research import write_brief
        print(write_brief(con, now))
    elif args.cmd == "backtest":
        from . import backtest
        seasons = ["1718", "1819", "1920", "2021", "2122", "2223", "2324", "2425", "2526", "2627"]
        if args.quick:
            r = backtest.run(["E0"], seasons[4:], tune=["2223"], validate=["2324"], test=["2425", "2526", "2627"],
                             xi_grid=(0.0019,), ridge_grid=(2.0,), n_draws=50)
        else:
            grid = {}
            if args.fixed:
                config.load_tuned()
                grid = {"xi_grid": (config.MODEL.xi,), "ridge_grid": (config.MODEL.ridge,)}
            r = backtest.run(args.leagues.split(","), seasons, tune=["2021", "2122"], validate=["2223", "2324"],
                             test=["2425", "2526", "2627"], **grid)
        print(json.dumps({k: r[k] for k in ("hyperparameters", "blend_weight", "strategies",
                                            "blend_equals_market_only")}, indent=1, default=str))
    elif args.cmd == "note":
        from .research import add_note
        print("note id", add_note(con, args.event, args.category, args.claim, args.evidence_type,
                                  args.direction, args.url))
    elif args.cmd == "serve":
        import functools
        import http.server
        h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(config.SITE_DIR))
        print(f"dashboard: http://localhost:{args.port}/")
        http.server.ThreadingHTTPServer(("127.0.0.1", args.port), h).serve_forever()
    elif args.cmd == "nfl-reports":
        from . import nfl_reports
        r = nfl_reports.run(con, now, seasons=args.season, fetch=not args.no_fetch, history=args.history)
        print(json.dumps({k: r[k] for k in ("ingest", "summary", "source")}, indent=1, default=str))
        print(r["report"])
    elif args.cmd == "parlay-quote":
        from . import parlay_quotes, parlays, site
        at = datetime.fromisoformat(args.quoted_at) if args.quoted_at else now
        if at.tzinfo is None:
            print("--quoted-at needs a timezone, e.g. 2026-11-16T18:05:00-05:00")
            return 2
        rec = parlay_quotes.make(args.bookmaker, args.odds, [x.strip() for x in args.legs.split(",") if x.strip()],
                                 at, args.source, now)
        legs = {leg["id"]: leg for leg in site.parlay_legs(con, now)}
        why = parlay_quotes.quote_problem(rec, legs, now, parlays.MAX_QUOTE_AGE_MINUTES)
        print(json.dumps({"quote": rec, "verified_now": why is None, "problem": why}, indent=1))
        if why or args.dry_run:
            return 0 if args.dry_run and why is None else 1
        print("recorded" if parlay_quotes.append(rec) else "duplicate: already recorded")
        print(site.build(con, now))       # refresh docs/data now: the quote only counts for 30 minutes
        print("Commit and push data/parlay_quotes.json and docs/data/ to update the site. The quote stops "
              "counting 30 minutes after --quoted-at, and the page hides it then; it is never relabelled fresh.")
    elif args.cmd == "parlay-candidates":
        from . import parlay_engine
        at = datetime.fromisoformat(args.as_of) if args.as_of else now
        at = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
        r = parlay_engine.write(con, at, record_ledger=args.record)
        print(f"events today {r['coverage']['events_today']}, pool legs {r['coverage']['pool_legs']}, "
              f"combinations evaluated {r['search']['evaluated']}, shadow shortlist {len(r['shortlist'])}")
        print(config.REPORTS_DIR / "parlay_candidates.md")
    elif args.cmd == "parlay-walkforward":
        from . import parlay_walkforward as pw
        times = pw.decision_times(con, args.since, args.until)
        out = pw.write(con, times, record_ledger=args.record, focus_day=args.focus_day)
        r = out["result"]
        print(f"decision times {r['decision_times']}, settled legs {r['legs_settled']}, "
              f"fit to back a recommendation: {r['verdict_replay']['fit_to_back_recommendation'] and r['verdict_backtest']['fit_to_back_recommendation']}")
        print(out["report"])
    elif args.cmd == "parlay-research":
        from . import parlay_research
        print(parlay_research.write(con, now))
    elif args.cmd == "status":
        for r in con.execute("SELECT job,started_at,status FROM job_runs ORDER BY id DESC LIMIT 10"):
            print(dict(r))
        for r in con.execute("SELECT * FROM provider_status"):
            print(dict(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
