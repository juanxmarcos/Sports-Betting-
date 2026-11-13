"""Per-league walk-forward validation for monitoring leagues. Evidence only: it never changes the allowlist.

`python -m sbi league-eval` answers, for ONE league at a time, with that league's own data:
  * is the history complete and well-formed (matches, teams, promoted teams, kick-off times, xG, bookmakers)?
  * out of sample, how do the Dixon-Coles model, Elo, the pre-match market and their blend compare
    (log loss, Brier, calibration), with a bootstrap interval on model minus market?
  * how sensitive is that to the hyperparameters (every grid point is scored on the test seasons and shown;
    only the tune seasons choose one)?
  * what would the deployed selection rules have done on the test seasons (bets, ROI and CLV with intervals)?

Chronology is strict and identical to sbi.backtest: hyperparameters are chosen on the tune seasons, the blend
weight on the validate seasons, and every reported number comes from test seasons that chose nothing. The
hyperparameters tuned on the six big leagues (data/tuned.json) are NOT reused; they are scored alongside only to
show whether they would have transferred.

The verdict is deliberately conservative. A league is a 'candidate for owner review' only if every check in
`verdict` passes; otherwise it stays 'monitoring' with the reasons listed. Either way promotion is a separate,
owner-approved code change in sbi/leagues.py. This module writes
  data/backtest/league_validation.json and reports/league_validation.md
and nothing else: no tuned.json, no database rows, no picks.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import backtest as bt
from . import config, leagues

SEASONS = ["1718", "1819", "1920", "2021", "2122", "2223", "2324", "2425", "2526", "2627"]
TUNE, VALIDATE, TEST = ["2021", "2122"], ["2223", "2324"], ["2425", "2526", "2627"]     # same split as sbi.backtest
XI_GRID, RIDGE_GRID = (0.0013, 0.0019, 0.0026), (2.0, 4.0, 8.0)

# Thresholds for the verdict. Fixed before looking at any league's result; they are not betting thresholds.
MIN_TEST_MATCHES = 500        # test matches with a pre-match market consensus
MIN_TEST_BETS = 100           # simulated selections needed before ROI/CLV mean anything
MIN_KNOWN_OPERATORS = config.RULES.min_bookmakers


def audit(m: pd.DataFrame, o: pd.DataFrame) -> list[dict]:
    """Per season: matches, teams, teams new to the division, kick-off times, xG rows and bookmaker depth."""
    rows, prev = [], None
    pre = o[(o["kind"] == "pre") & ~o["bookmaker"].isin(("Max", "Avg"))]
    clo = o[(o["kind"] == "closing") & ~o["bookmaker"].isin(("Max", "Avg"))]
    for season, g in m.groupby("season", sort=True):
        teams = set(g["home"]) | set(g["away"])
        p, c = pre[pre["idx"].isin(g.index)], clo[clo["idx"].isin(g.index)]

        def depth(d, market):
            d = d[d["market"] == market]
            return float(d.groupby("idx")["bookmaker"].nunique().median()) if len(d) else 0.0
        rows.append({
            "season": season, "matches": int(len(g)), "teams": len(teams),
            "teams_new_to_division": None if prev is None else len(teams - prev),
            "duplicate_events": int(g["event_id"].duplicated().sum()),
            "kickoff_not_1500": int((g["kickoff_utc"].dt.tz_convert("Europe/London").dt.strftime("%H:%M") != "15:00").sum()),
            "xg_rows": int(g["hxg"].notna().sum()),
            "median_bookmakers_pre": {k: depth(p, k) for k in ("1X2", "OU", "AH")},
            "median_bookmakers_closing_1x2": depth(c, "1X2"),
            "matches_with_pre_1x2": int(p[p["market"] == "1X2"]["idx"].nunique()),
            "sharp_references_pre": sorted(set(p["bookmaker"]) & {"Pinnacle", "Betfair Exchange"}),
        })
        prev = teams
    return rows


def verdict(test: dict, bets: dict, blend_w: float, live: dict | None = None) -> dict:
    """Conservative, rule-based reading of the evidence. Returns the checks, the blockers and a status.

    Status is 'candidate_for_owner_review' only when every check passes; otherwise 'monitoring'.
    Neither status changes what Doyen analyses."""
    live = live or {}
    n = test.get("n_matches", 0)
    mk, dcl, base = (test.get(k, {}).get("logloss") for k in ("market_pre", "dixon_coles", "base_rate"))
    blend = test.get("blend", {}).get("logloss")
    clv_lo = (bets.get("clv_ci95") or [None])[0]
    roi_lo = (bets.get("roi_ci95") or [None])[0]
    checks = {
        "enough_test_matches": n >= MIN_TEST_MATCHES,
        "market_beats_base_rate": mk is not None and base is not None and mk < base,
        "model_adds_to_market": blend_w > 0.01 and blend is not None and mk is not None and blend < mk,
        "enough_simulated_bets": bets.get("n_bets", 0) >= MIN_TEST_BETS,
        "clv_interval_above_zero": clv_lo is not None and clv_lo > 0,
        "roi_interval_above_zero": roi_lo is not None and roi_lo > 0,
        "live_known_operators": live.get("known_operators", 0) >= MIN_KNOWN_OPERATORS,
        "live_bookmaker_timed_quotes": live.get("events_fresh_bookmaker_timed", 0) > 0,
    }
    why = {
        "enough_test_matches": f"only {n} test matches with a market consensus (need {MIN_TEST_MATCHES})",
        "market_beats_base_rate": "the pre-match market does not beat the base rate out of sample",
        "model_adds_to_market": (f"the model adds nothing to the market out of sample (validation blend weight {blend_w:.3f}; "
                                 f"test log loss model {dcl}, market {mk})"),
        "enough_simulated_bets": f"only {bets.get('n_bets', 0)} simulated selections on the test seasons (need {MIN_TEST_BETS})",
        "clv_interval_above_zero": "closing-line value is not reliably positive (95% interval includes zero or is missing)",
        "roi_interval_above_zero": "simulated return is not distinguishable from zero (95% interval includes zero or is missing)",
        "live_known_operators": f"fewer than {MIN_KNOWN_OPERATORS} known independent operators in the current feed",
        "live_bookmaker_timed_quotes": "current quotes carry only a file-publication time, never the bookmaker's own update time",
    }
    blockers = [why[k] for k, ok in checks.items() if not ok]
    return {"status": "candidate_for_owner_review" if not blockers else "monitoring", "checks": checks,
            "blockers": blockers, "promotion": "never automatic: needs an owner-approved change to sbi/leagues.py"}


def evaluate(div: str, m: pd.DataFrame, o: pd.DataFrame, xi_grid=XI_GRID, ridge_grid=RIDGE_GRID,
             tune=TUNE, validate=VALIDATE, test=TEST, pooled: tuple | None = None, live: dict | None = None) -> dict:
    """Walk-forward evaluation of one league on its own data. `pooled` = (xi, ridge) tuned on other leagues,
    scored for comparison only."""
    out = {"league": div, "name": leagues.name(div), "tier": leagues.status(div),
           "seasons": {"tune": tune, "validate": validate, "test": test}, "audit": audit(m, o)}
    scores = {}
    for xi in xi_grid:
        for rg in ridge_grid:
            df, _ = bt.walk_forward(div, m[m.season <= tune[-1]], o, tune[0], xi, rg)
            df = df.dropna(subset=["mkt_H"]) if len(df) and "mkt_H" in df else df.iloc[0:0]
            if len(df):
                scores[(xi, rg)] = bt.logloss(bt.probs(df, "dc"), bt.y1x2(df))
    if not scores:
        out["error"] = "no tune-season predictions (too little history before the tune seasons)"
        out["verdict"] = verdict({}, {}, 0.0, live)
        return out
    xi, rg = min(scores, key=scores.get)
    pred, _ = bt.walk_forward(div, m, o, validate[0], xi, rg)
    val, tst = pred[pred.season.isin(validate)], pred[pred.season.isin(test)]
    w = bt.fit_blend_1x2(val) if len(val.dropna(subset=["mkt_H"])) >= 200 else 0.0
    out["hyperparameters"] = {"xi": xi, "ridge": rg, "chosen_on": "this league's tune seasons only",
                              "tune_grid_logloss": {f"{k[0]}|{k[1]}": round(v, 5) for k, v in scores.items()}}
    out["blend_weight_1x2"] = round(w, 4)
    out["validation_1x2"] = bt.evaluate_predictions(val, w) if len(val.dropna(subset=["mkt_H"])) else {"n_matches": 0}
    out["test_1x2"] = bt.evaluate_predictions(tst, w) if len(tst.dropna(subset=["mkt_H"])) else {"n_matches": 0}
    d = tst.dropna(subset=["mkt_H"]) if len(tst) else tst
    if len(d):
        out["test_1x2"]["calibration_market_home"] = bt.calibration(bt.probs(d, "mkt")[:, 0], (bt.y1x2(d) == 0).astype(int))
    ou = tst.dropna(subset=["ou_model"]) if "ou_model" in tst else tst.iloc[0:0]
    out["test_ou25_logloss"] = ({"n": int(len(ou)), "model": round(bt.bin_logloss(ou["ou_model"], ou["ou_y"]), 5),
                                 "market": round(bt.bin_logloss(ou["ou_mkt"], ou["ou_y"]), 5)} if len(ou) else {"n": 0})
    # Sensitivity: every grid point scored on the TEST seasons. Shown, never used to choose anything.
    sens = {}
    grid = [(a, b) for a in xi_grid for b in ridge_grid]
    for a, b in grid + ([pooled] if pooled and pooled not in grid else []):
        df, _ = bt.walk_forward(div, m, o, test[0], a, b)
        df = df.dropna(subset=["mkt_H"]) if len(df) and "mkt_H" in df else df.iloc[0:0]
        if len(df):
            sens[f"{a}|{b}"] = round(bt.logloss(bt.probs(df, "dc"), bt.y1x2(df)), 5)
    out["sensitivity_test_logloss_dc"] = sens
    if sens:
        out["sensitivity_spread"] = round(max(sens.values()) - min(sens.values()), 5)
    if pooled:
        out["pooled_hyperparameters_from_other_leagues"] = {
            "xi": pooled[0], "ridge": pooled[1], "test_logloss_dc": sens.get(f"{pooled[0]}|{pooled[1]}"),
            "note": "tuned on E0,E1,SP1,D1,I1,F1; scored here for comparison only, not adopted"}
    # What the deployed selection rules would have done on the test seasons (blend weight as fitted above).
    bw = {"1X2": w if w > 0.01 else 0.0, "OU": 0.0, "AH": 0.0}
    _, bets = bt.walk_forward(div, m, o, test[0], xi, rg, blend_w=bw, rules=config.RULES,
                              n_draws=100 if w > 0.01 else 0)
    out["test_bets_deployed_rules"] = bt.evaluate_bets(pd.DataFrame(bets))
    out["live"] = {k: (live or {}).get(k) for k in ("scheduled_events", "events_priced", "usable_markets", "known_operators",
                                                    "unknown_bookmakers", "events_fresh_bookmaker_timed",
                                                    "events_fresh_observed_only", "events_with_sharp_reference")}
    out["verdict"] = verdict(out["test_1x2"], out["test_bets_deployed_rules"], w, live)
    return out


def to_markdown(rep: dict) -> str:
    L = [f"# League validation ({rep['generated'][:16].replace('T', ' ')} UTC)", "",
         "Walk-forward, out-of-sample evidence for each **monitoring** league, on that league's own data. "
         "Generated by `python -m sbi league-eval`; method in `sbi/league_eval.py`.", "",
         f"Split by season: tune {', '.join(rep['seasons']['tune'])}; validate {', '.join(rep['seasons']['validate'])}; "
         f"test {', '.join(rep['seasons']['test'])}. Hyperparameters are chosen per league on its tune seasons. "
         "Parameters tuned on other leagues are scored for comparison and never adopted. "
         "**Nothing here changes what Doyen analyses or publishes.**", "",
         "## Verdict", "", "| League | Status | Blockers |", "|---|---|---|"]
    for code, r in rep["leagues"].items():
        L.append(f"| {code} {r['name']} | {r['verdict']['status'].replace('_', ' ')} | "
                 + ("; ".join(r["verdict"]["blockers"]) or "none") + " |")
    L += ["", "## 1X2 out of sample (test seasons)", "",
          "Lower log loss and Brier are better. *Model − market* is the paired difference in log loss with a 95% "
          "bootstrap interval: above zero means the model is worse than the pre-match market.", "",
          "| League | Matches | Base rate LL | Elo LL | Model LL | Market LL | Closing LL | Model Brier | Market Brier | "
          "Model − market (95%) | Blend weight | Chosen xi / ridge |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for code, r in rep["leagues"].items():
        t = r.get("test_1x2", {})
        if not t.get("n_matches"):
            L.append(f"| {code} | 0 | | | | | | | | | | |")
            continue
        g = lambda k, f="logloss": t.get(k, {}).get(f, "n/a")  # noqa: E731
        ci = t.get("dc_minus_market_logloss_ci95", ["", ""])
        L.append(f"| {code} | {t['n_matches']} | {g('base_rate')} | {g('elo')} | {g('dixon_coles')} | {g('market_pre')} | "
                 f"{g('market_closing')} | {g('dixon_coles', 'brier')} | {g('market_pre', 'brier')} | {ci[0]} to {ci[1]} | "
                 f"{r['blend_weight_1x2']} | {r['hyperparameters']['xi']} / {r['hyperparameters']['ridge']} |")
    L += ["", "## Sensitivity and transfer", "",
          "Model test log loss at every hyperparameter grid point (shown, not used to choose). *Pooled* is the setting "
          "tuned on the six big leagues.", "",
          "| League | Best grid point | Worst grid point | Spread | Chosen on tune seasons | Pooled setting | O/U 2.5 model LL | O/U 2.5 market LL |",
          "|---|---|---|---|---|---|---|---|"]
    for code, r in rep["leagues"].items():
        s = r.get("sensitivity_test_logloss_dc") or {}
        if not s:
            continue
        ch = f"{r['hyperparameters']['xi']}|{r['hyperparameters']['ridge']}"
        po = r.get("pooled_hyperparameters_from_other_leagues", {})
        ou = r.get("test_ou25_logloss", {})
        L.append(f"| {code} | {min(s.values())} | {max(s.values())} | {r.get('sensitivity_spread')} | {s.get(ch)} | "
                 f"{po.get('test_logloss_dc', 'n/a')} | {ou.get('model', 'n/a')} | {ou.get('market', 'n/a')} |")
    L += ["", "## Deployed selection rules on the test seasons (simulation)", "",
          "The current, unchanged rules applied to historical pre-match prices. Fixed one-unit stakes. "
          "A simulation on past prices, not a forecast and not a recommendation.", "",
          "| League | Selections | Return per unit | 95% interval | Mean CLV | 95% interval | Hit rate | Mean odds |",
          "|---|---|---|---|---|---|---|---|"]
    for code, r in rep["leagues"].items():
        b = r.get("test_bets_deployed_rules", {})
        if not b.get("n_bets"):
            L.append(f"| {code} | 0 | | | | | | |")
            continue
        L.append(f"| {code} | {b['n_bets']} | {b['roi']:+.4f} | {b['roi_ci95'][0]:+.4f} to {b['roi_ci95'][1]:+.4f} | "
                 f"{b.get('avg_clv', 'n/a')} | {' to '.join(str(x) for x in b.get('clv_ci95', [])) or 'n/a'} | "
                 f"{b['hit_rate']} | {b['avg_odds']} |")
    L += ["", "## Market calibration (home win, test seasons)", ""]
    for code, r in rep["leagues"].items():
        cal = r.get("test_1x2", {}).get("calibration_market_home") or []
        if cal:
            L.append(f"- **{code}**: " + "; ".join(f"{c['bin']}: predicted {c['pred']:.3f}, observed {c['obs']:.3f} (n={c['n']})" for c in cal))
    L += ["", "## History audit", "",
          "| League | Season | Matches | Teams | New to division | Duplicates | Kick-offs not 15:00 UK | xG rows | "
          "Median books 1X2 / OU / AH (pre) | Median books closing 1X2 | Sharp reference (pre) |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for code, r in rep["leagues"].items():
        for a in r["audit"]:
            mb = a["median_bookmakers_pre"]
            L.append(f"| {code} | {a['season']} | {a['matches']} | {a['teams']} | "
                     f"{'' if a['teams_new_to_division'] is None else a['teams_new_to_division']} | {a['duplicate_events']} | "
                     f"{a['kickoff_not_1500']} | {a['xg_rows']} | {mb['1X2']:g} / {mb['OU']:g} / {mb['AH']:g} | "
                     f"{a['median_bookmakers_closing_1x2']:g} | {', '.join(a['sharp_references_pre']) or 'none'} |")
    return "\n".join(L) + "\n"


def run(codes: list[str] | None = None, live: dict | None = None) -> dict:
    """Evaluate each league separately and write the JSON and markdown evidence. Needs the season files
    (downloaded once, then cached); writes no model parameters and touches no database."""
    codes = codes or leagues.monitoring()
    pooled = None
    tp = config.DATA_DIR / "tuned.json"
    if tp.exists():
        t = json.loads(tp.read_text())
        pooled = (t.get("xi"), t.get("ridge")) if t.get("xi") and t.get("ridge") else None
    rep = {"generated": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
           "seasons": {"tune": TUNE, "validate": VALIDATE, "test": TEST},
           "grid": {"xi": list(XI_GRID), "ridge": list(RIDGE_GRID)},
           "thresholds": {"min_test_matches": MIN_TEST_MATCHES, "min_test_bets": MIN_TEST_BETS,
                          "min_known_operators": MIN_KNOWN_OPERATORS},
           "leagues": {}}
    for div in codes:
        print(f"evaluating {div}")
        m, o = bt.load_league(div, SEASONS)
        rep["leagues"][div] = evaluate(div, m, o, pooled=pooled, live=(live or {}).get(div))
    out = config.DATA_DIR / "backtest"
    out.mkdir(parents=True, exist_ok=True)
    (out / "league_validation.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (config.REPORTS_DIR / "league_validation.md").write_text(to_markdown(rep))
    return rep
