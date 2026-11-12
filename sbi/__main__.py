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
    args = ap.parse_args(argv)

    from . import config, db
    con = db.connect()
    now = datetime.now(timezone.utc).replace(microsecond=0)

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
    elif args.cmd == "status":
        for r in con.execute("SELECT job,started_at,status FROM job_runs ORDER BY id DESC LIMIT 10"):
            print(dict(r))
        for r in con.execute("SELECT * FROM provider_status"):
            print(dict(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
