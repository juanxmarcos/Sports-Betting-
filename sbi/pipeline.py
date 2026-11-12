"""Daily deterministic pipeline: ingest -> settle -> analyse -> select -> publish.

No LLM calls happen here. Claude's contextual research is a separate, optional step
(see automation/) that can only attach qualitative risk flags.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from . import config, db
from . import ev as evm
from .backtest import load_league
from .engine import books_from_rows, passes, price_event, select
from .markets import standard_markets
from .models import dixon_coles as dc
from .sources import football_data as fd
from .sources.http import SourceBlocked


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def ingest(con, now: datetime | None = None) -> dict:
    now = now or _now()
    out = {}
    try:
        out["fixtures"] = fd.ingest_fixtures(con, config.FOOTBALL_LEAGUES)
        db.provider_ok(con, "football-data:fixtures", out["fixtures"]["events"])
    except (SourceBlocked, RuntimeError) as e:
        db.provider_err(con, "football-data:fixtures", str(e))
        out["fixtures_error"] = str(e)
    season = fd.season_code(now.date())
    for div in config.FOOTBALL_LEAGUES:
        try:
            out[div] = fd.ingest_results(con, div, season)
            db.provider_ok(con, f"football-data:{div}", out[div]["events"])
        except (SourceBlocked, RuntimeError) as e:
            db.provider_err(con, f"football-data:{div}", str(e))
            out[f"{div}_error"] = str(e)
    con.commit()
    return out


def _training_seasons(now: datetime, n: int = 4) -> list[str]:
    y = now.year if now.month >= 7 else now.year - 1
    return [f"{(y - k) % 100:02d}{(y - k + 1) % 100:02d}" for k in range(n - 1, -1, -1)]


def _latest_books(con, event_id: str, max_age_h: float, now: datetime) -> tuple[dict, str | None, list[str]]:
    rows = con.execute("""
        SELECT o.market, o.line, o.bookmaker, o.selection, o.price, o.retrieved_at, o.source_url
        FROM odds o JOIN (
            SELECT bookmaker, market, selection, IFNULL(line,-999) l, MAX(retrieved_at) mr
            FROM odds WHERE event_id=? AND kind='pre' GROUP BY bookmaker, market, selection, IFNULL(line,-999)
        ) x ON o.bookmaker=x.bookmaker AND o.market=x.market AND o.selection=x.selection
           AND IFNULL(o.line,-999)=x.l AND o.retrieved_at=x.mr
        WHERE o.event_id=? AND o.kind='pre'""", (event_id, event_id)).fetchall()
    fresh, warnings, urls = [], [], set()
    newest = None
    for r in rows:
        ts = datetime.fromisoformat(r["retrieved_at"])
        age = (now - ts).total_seconds() / 3600
        newest = max(newest or r["retrieved_at"], r["retrieved_at"])
        urls.add(r["source_url"])
        if age <= max_age_h:
            fresh.append((r["market"], r["line"], r["bookmaker"], r["selection"], r["price"]))
    if rows and not fresh:
        warnings.append(f"all odds older than {max_age_h:.0f}h (newest {newest}) - excluded as stale")
    return books_from_rows(fresh), newest, sorted(urls)


def _form(train: pd.DataFrame, team: str, n: int = 6) -> dict:
    g = train[(train.home == team) | (train.away == team)].tail(n)
    res, gf, ga, xgf, xga = [], 0, 0, [], []
    for r in g.itertuples():
        home = r.home == team
        f, a = (r.hg, r.ag) if home else (r.ag, r.hg)
        gf += f
        ga += a
        res.append("W" if f > a else ("D" if f == a else "L"))
        if pd.notna(r.hxg):
            xgf.append(r.hxg if home else r.axg)
            xga.append(r.axg if home else r.hxg)
    out = {"last": "".join(res), "gf": int(gf), "ga": int(ga), "n": len(g)}
    if xgf:
        out["xg_for_avg"] = round(float(np.mean(xgf)), 2)
        out["xg_against_avg"] = round(float(np.mean(xga)), 2)
    return out


def _risks(c, model, home, away, rules) -> list[str]:
    r = ["Model uses results/goals only: it does not see lineups, injuries or suspensions "
         "beyond what is already reflected in recent results and market prices."]
    if c.market_q is not None:
        gap = c.model_q - c.market_q
        if abs(gap) > 0.05:
            r.append(f"Model and market disagree by {gap:+.1%}: when the sharp market disagrees "
                     "this much it often holds information the model lacks (team news).")
    nmin = min(model.n_matches.get(home, 0), model.n_matches.get(away, 0))
    if nmin < 30:
        r.append(f"Thin data: a team has only {nmin} matches in the training window.")
    if c.odds >= 3.5:
        r.append("Price above 3.5: higher variance, and model error on longshots is larger.")
    if c.market == "AH" and c.active < 0.9:
        r.append(f"Quarter/whole line: {1 - c.active:.0%} of outcomes refund all or part of the stake.")
    if c.consensus_src == "Avg":
        r.append("Consensus from the market average rather than a sharp book/exchange.")
    return r


def analyse(con, now: datetime | None = None, horizon_h: float = 48) -> dict:
    now = now or _now()
    rules, mcfg = config.RULES, config.MODEL
    config.load_tuned()
    events = pd.read_sql_query(
        "SELECT * FROM events WHERE sport='football' AND status='scheduled' AND kickoff_utc > ? AND kickoff_utc <= ?",
        con, params=(now.isoformat(), (now + timedelta(hours=horizon_h)).isoformat()))
    summary = {"events_in_window": int(len(events)), "leagues": {}, "warnings": [], "published": 0}
    cands_by_event, hist_ok, meta = {}, {}, {}
    rng = np.random.default_rng(int(now.timestamp()) // 86400)
    for div, evs in events.groupby("league"):
        try:
            hist, _ = load_league(div, _training_seasons(now))
        except Exception as e:  # noqa: BLE001
            summary["warnings"].append(f"{div}: could not load history ({e})")
            continue
        train = hist[(hist.kickoff_utc < now) & (hist.kickoff_utc >= now - timedelta(days=mcfg.lookback_days))]
        if len(train) < 200:
            summary["warnings"].append(f"{div}: only {len(train)} training matches - skipped")
            continue
        days = (now - train.kickoff_utc).dt.total_seconds().values / 86400
        model = dc.fit(train.home.values, train.away.values, train.hg.values, train.ag.values, days,
                       xi=mcfg.xi, ridge=mcfg.ridge, with_cov=True)
        run_id = f"{mcfg.model_version}:{div}:{now.strftime('%Y%m%dT%H%M')}"
        con.execute("INSERT OR IGNORE INTO model_runs VALUES (?,?,?,?,?,?,?)",
                    (run_id, mcfg.model_version, div, now.isoformat(), int(len(train)),
                     json.dumps({"home": model.home, "rho": model.rho, "xi": mcfg.xi, "ridge": mcfg.ridge,
                                 "blend_weight": mcfg.blend_weight}), db.utcnow()))
        summary["leagues"][div] = {"events": int(len(evs)), "train_matches": int(len(train))}
        for ev in evs.itertuples():
            if not (model.has(ev.home) and model.has(ev.away)):
                summary["warnings"].append(f"{ev.event_id}: team not in training data (promoted/renamed?)")
                continue
            books, odds_ts, urls = _latest_books(con, ev.event_id, rules.max_odds_age_hours, now)
            mat = model.score_matrix(ev.home, ev.away, mcfg.max_goals)
            headline = standard_markets(mat)
            cands = price_event(model, ev.home, ev.away, books, mcfg.blend_weight, rules.exchange_commission,
                                n_draws=mcfg.n_param_draws, max_goals=mcfg.max_goals, rng=rng,
                                markets=rules.markets)
            for c in cands:
                con.execute("""INSERT OR IGNORE INTO predictions(run_id,event_id,market,selection,line,model_prob,
                               prob_sd,market_prob,final_prob,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                            (run_id, ev.event_id, c.market, c.selection, c.line, c.model_q, c.prob_sd,
                             c.market_q, c.final_q, db.utcnow()))
            if not books:
                # still record 1X2 model probabilities for calibration tracking
                for s, k in (("H", "1X2:H"), ("D", "1X2:D"), ("A", "1X2:A")):
                    con.execute("""INSERT OR IGNORE INTO predictions(run_id,event_id,market,selection,line,
                                   model_prob,created_at) VALUES (?,?,?,?,?,?,?)""",
                                (run_id, ev.event_id, "1X2", s, None, headline[k], db.utcnow()))
            nmin = min(model.n_matches.get(ev.home, 0), model.n_matches.get(ev.away, 0))
            hist_ok[ev.event_id] = nmin >= rules.min_team_matches
            cands_by_event[ev.event_id] = cands
            ix = model.index
            strength = sorted(model.teams, key=lambda t: model.att[ix[t]] - model.dfn[ix[t]], reverse=True)
            lam, mu = model.rates(ev.home, ev.away)
            meta[ev.event_id] = dict(ev=ev, model=model, run_id=run_id, odds_ts=odds_ts, urls=urls, books=books,
                                     evidence={
                                         "expected_goals": {"home": round(lam, 2), "away": round(mu, 2)},
                                         "model_markets": {k: round(v, 4) for k, v in headline.items()},
                                         "strength_rank": {"home": strength.index(ev.home) + 1,
                                                           "away": strength.index(ev.away) + 1,
                                                           "of": len(strength)},
                                         "attack_defence": {
                                             ev.home: [round(float(model.att[ix[ev.home]]), 3), round(float(model.dfn[ix[ev.home]]), 3)],
                                             ev.away: [round(float(model.att[ix[ev.away]]), 3), round(float(model.dfn[ix[ev.away]]), 3)]},
                                         "form": {ev.home: _form(train, ev.home), ev.away: _form(train, ev.away)},
                                         "train_matches": {ev.home: model.n_matches[ev.home], ev.away: model.n_matches[ev.away]},
                                         "home_advantage": round(model.home, 3), "rho": round(model.rho, 3),
                                     })
            meta[ev.event_id]["rejections"] = {f"{c.market}:{c.selection}:{c.line}": passes(c, rules, hist_ok[ev.event_id])[1]
                                               for c in cands}
            meta[ev.event_id]["cands"] = cands

    # do not re-publish an event that already has a recommendation (dedupe / exposure)
    already = {r[0] for r in con.execute("SELECT event_id FROM recommendations")}
    pool = {k: v for k, v in cands_by_event.items() if k not in already}
    picks = select(pool, rules, hist_ok)
    published_at = now.isoformat()
    for rank, (eid, c) in enumerate(picks, 1):
        m = meta[eid]
        ev = m["ev"]
        evidence = dict(m["evidence"])
        evidence.update({
            "consensus_source": c.consensus_src, "n_bookmakers": c.n_books,
            "model_q_p10": round(c.model_q_lo, 4), "net_odds": round(c.net_odds, 4),
            "stake_share_active": round(c.active, 4),
            "outcome_split": {k: round(getattr(c.outcome, k), 4) for k in ("pw", "phw", "pp", "phl", "pl")},
            "all_prices": {bk: q for bk, q in m["books"].get((c.market, c.line), {}).items()},
            "risks": _risks(c, m["model"], ev.home, ev.away, rules),
            "blend_weight": config.MODEL.blend_weight.get(c.market, 0.0),
        })
        rec_id = hashlib.sha1(f"{eid}|{c.market}|{c.selection}|{c.line}".encode()).hexdigest()[:16]
        cur = con.execute("""INSERT OR IGNORE INTO recommendations(rec_id,event_id,published_at,sport,league,kickoff_utc,
                home,away,market,selection,line,bookmaker,odds,odds_retrieved_at,model_prob,market_prob,final_prob,
                fair_odds,ev,ev_lower,prob_sd,stake_units,model_version,rank,evidence_json,source_urls)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                          (rec_id, eid, published_at, "football", ev.league, ev.kickoff_utc, ev.home, ev.away,
                           c.market, c.selection, c.line, c.bookmaker, c.odds, m["odds_ts"], c.model_q, c.market_q,
                           c.final_q, c.fair_odds, c.ev, c.ev_lower, c.prob_sd, rules.stake_units,
                           config.MODEL.model_version, rank, json.dumps(evidence, default=str),
                           json.dumps(m["urls"] + [ev.source_url])))
        summary["published"] += cur.rowcount
    con.commit()
    # candidate table for the report (top near-misses, transparency)
    near = []
    for eid, cands in cands_by_event.items():
        for c in cands:
            near.append({"event_id": eid, "match": f"{meta[eid]['ev'].home} v {meta[eid]['ev'].away}",
                         "league": meta[eid]["ev"].league, "market": c.market, "selection": c.selection,
                         "line": c.line, "odds": c.odds, "bookmaker": c.bookmaker, "final_q": c.final_q,
                         "ev": c.ev, "ev_lower": c.ev_lower,
                         "reason": meta[eid]["rejections"].get(f"{c.market}:{c.selection}:{c.line}")})
    near.sort(key=lambda x: x["ev"], reverse=True)
    summary["top_candidates"] = near[:15]
    summary["analysed_events"] = len(cands_by_event)
    summary["now"] = now.isoformat()
    return summary


def run_daily(con=None, now: datetime | None = None) -> dict:
    from . import report, settle, dashboard
    con = con or db.connect()
    now = now or _now()
    result = {}
    with db.job(con, "ingest") as d:
        d.update(ingest(con, now))
        result["ingest"] = d
    with db.job(con, "settle") as d:
        d.update(settle.settle_all(con, now))
        result["settle"] = d
    with db.job(con, "analyse") as d:
        s = analyse(con, now)
        d.update({k: v for k, v in s.items() if k != "top_candidates"})
        result["analyse"] = s
    with db.job(con, "publish") as d:
        d["report"] = str(report.write_daily(con, now, result["analyse"]))
        d["dashboard"] = str(dashboard.build(con))
        result["publish"] = d["report"]
    return result
