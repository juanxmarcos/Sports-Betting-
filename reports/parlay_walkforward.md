# Parlay walk-forward validation (shadow) — 2026-11-12T17:31:12+00:00 to 2026-11-17T04:32:17+00:00

Developer-only, issue #38 (PR B of #35). Method `parlay-walkforward-v1`. **Nothing here is published.** Every price is a computed product (`computed_product_not_a_quote`), never a bookmaker combined quote. No network request, no API credit. Reproduce with `python -m sbi parlay-walkforward`.

## Verdict

- **Joint estimates fit to back a recommendation: NO.**
- Replay (34 recorded scheduled runs over 5 days, 71 settled screened legs): 2 legs: not shown (30 combinations; 200 required); 3 legs: not shown (11 combinations; 200 required); 4 legs: not shown (3 combinations; 200 required); 5 legs: not shown (0 combinations; 200 required; no joint outcomes); 6 legs: not shown (0 combinations; 200 required; no joint outcomes)
- Leg evidence (replay): 71 settled legs; 500 required.
- Straight-pick backtest sample (club soccer only): 2 legs: 66 combinations; 200 required; 3 legs: 23 combinations; 200 required; 4 legs: 5 combinations; 200 required; 5 legs: 0 combinations; 200 required; no joint outcomes; 6 legs: 0 combinations; 200 required; no joint outcomes
- Backtest leg/correlation evidence: 250 settled legs; 500 required; 194 different-competition pairs; 200 required.
- More data needed (replay, at the observed rate of disjoint combinations per day): 2 legs ≈ 29 more days, 3 legs ≈ 86 more days, 4 legs ≈ 329 more days, 5 legs ≈ no combinations yet, 6 legs ≈ no combinations yet.

Pre-registered criteria (fixed in `sbi/parlay_walkforward.py` before scoring): {"min_combinations_per_leg_count": 200, "max_abs_joint_z": 1.96, "min_legs": 500, "max_abs_leg_z": 1.96, "min_pairs_correlation": 200}. A leg count is "calibrated" only if all hold.

## 1. Leg calibration (replay; market de-vigged consensus)

- 71 settled legs ({"tennis": 6, "nba": 26, "nfl": 14, "soccer": 25}): wins 45 vs expected 42.1 (z +0.74); log loss 0.5907 (0.5191 to 0.6648); Brier 0.203 (0.1708 to 0.2379).

| Probability bucket | n | Mean predicted | Observed (95%) |
|---|---|---|---|
| 0.30-0.40 | 11 | 0.3509 | 0.1818 (0.0514 to 0.4770) |
| 0.40-0.50 | 13 | 0.4476 | 0.6923 (0.4237 to 0.8732) |
| 0.50-0.60 | 9 | 0.5521 | 0.7778 (0.4526 to 0.9368) |
| 0.60-0.70 | 14 | 0.6439 | 0.5714 (0.3259 to 0.7862) |
| 0.70-0.85 | 24 | 0.7682 | 0.7917 (0.5953 to 0.9076) |

| Sport | Legs | Wins obs / exp | z | Log loss (95%) | Brier (95%) |
|---|---|---|---|---|---|
| nba | 26 | 16 / 16.28 | -0.12 | 0.5964 (0.4604 to 0.7457) | 0.2045 (0.1423 to 0.2705) |
| nfl | 14 | 9 / 8.22 | +0.45 | 0.5644 (0.4177 to 0.7373) | 0.1922 (0.1268 to 0.2652) |
| soccer | 25 | 16 / 13.91 | +0.89 | 0.612 (0.4964 to 0.7235) | 0.2135 (0.1621 to 0.2668) |
| tennis | 6 | 4 / 3.69 | +0.28 | 0.5384 (0.3390 to 0.7849) | 0.1786 (0.0816 to 0.2901) |

- Legs with a stored model probability: 65. Model log loss 0.6247 vs market 0.5955 on the same legs; model Brier 0.2182 vs market 0.2053.

## 2. Joint calibration by leg count — replay (independence product of market probabilities)

| Legs | Combinations | Joint wins obs / exp | z | Log loss (95%) | Brier (95%) | Legs z |
|---|---|---|---|---|---|---|
| 2 | 30 | 14 / 10.61 | +1.35 | 0.6791 (0.5396 to 0.8195) | 0.244 (0.1789 to 0.3122) | +0.66 |
| 3 | 11 | 3 / 2.51 | +0.36 | 0.5698 (0.2723 to 0.9265) | 0.1943 (0.0673 to 0.3419) | +1.04 |
| 4 | 3 | 0 / 0.36 | -0.65 | 0.1305 (0.0568 to 0.2430) | 0.0191 (0.0030 to 0.0465) | -0.67 |
| 5 | 0 | – | – | – | – | – |
| 6 | 0 | – | – | – | – | – |

- 2 legs, 24 combinations with a model probability on every leg: model log loss 0.6765 vs market 0.6555.
- 3 legs, 5 combinations with a model probability on every leg: model log loss 0.6342 vs market 0.6302.

Reliability, 2-leg replay combinations:

| Joint bucket | n | Mean predicted | Observed (95%) |
|---|---|---|---|
| 0.10-0.20 | 4 | 0.1582 | 0.0 (0.0000 to 0.4899) |
| 0.20-0.35 | 12 | 0.2763 | 0.5 (0.2538 to 0.7462) |
| 0.35-0.50 | 7 | 0.3949 | 0.5714 (0.2505 to 0.8418) |
| 0.50-1.00 | 7 | 0.5574 | 0.5714 (0.2505 to 0.8418) |

## 3. Joint calibration by leg count — straight-pick backtest (club soccer, older sample)

| Legs | Combinations | Joint wins obs / exp | z | Log loss (95%) | Brier (95%) | Legs z |
|---|---|---|---|---|---|---|
| 2 | 66 | 6 / 6.52 | -0.22 | 0.3102 (0.1735 to 0.4803) | 0.0848 (0.0353 to 0.1466) | +0.38 |
| 3 | 23 | 1 / 0.67 | +0.41 | 0.2016 (0.0245 to 0.5469) | 0.0431 (0.0006 to 0.1270) | +1.63 |
| 4 | 5 | 0 / 0.05 | -0.23 | 0.0101 (0.0059 to 0.0180) | 0.0002 (0.0000 to 0.0004) | -0.13 |
| 5 | 0 | – | – | – | – | – |
| 6 | 0 | – | – | – | – | – |

## 4. Engine shortlist replay

- Unique shortlisted candidates across all replayed runs: 1; settled and event-disjoint per day: 1.
- 2 legs: n 1, won 0 vs expected 0.16 (fair) / 0.15 (slip implied); log loss fair 0.1688 vs implied 0.1663; shadow return per unit -1.000 (computed product, not a quote).
- Appended 0 new row(s) to `ledger/parlay_walkforward_shadow.csv` (append-only, labelled `walk_forward_replay`).

## 5. Correlation risk (same-day leg pairs; residual covariance, 0 = independent and calibrated)

| Relation | Pairs | Mean residual covariance | 95% (optimistic) |
|---|---|---|---|
| same competition | 201 | -0.00413 | -0.0312 to 0.0251 |
| different competition | 406 | +0.00980 | -0.0081 to 0.0278 |
| shared team | 0 | n/a | n/a |

Pairs within a day share legs, so they are not independent: the intervals are optimistic. The same-competition pairs are what the live screen excludes. Same-day shared-team pairs cannot occur except in back-to-back fixtures.

Reading: no same-competition dependence detected (201 overlapping pairs, interval -0.0312 to +0.0251), but the pairs come from few days and share legs, so this is not evidence of independence; the exclusion stays until a larger, pre-registered test says otherwise.

## 6. Daily candidates against the 3–5 target (replay; thresholds unchanged)

| NY day | Runs | Max pool legs | Max shortlist in one run | Unique shortlisted |
|---|---|---|---|---|
| 2026-11-12 | 22 | 2 | 1 | 1 |
| 2026-11-13 | 3 | 4 | 0 | 0 |
| 2026-11-14 | 3 | 2 | 0 | 0 |
| 2026-11-15 | 3 | 4 | 0 | 0 |
| 2026-11-16 | 3 | 3 | 0 | 0 |

## 7. Why 2026-11-16 gave 0 candidates

| Run (UTC) | Events | By sport | Excluded for prices | Of those, ≥3 groups at any age | Candidate legs | Pool | Pool by sport | Books with ≥2 value legs | Evaluated | Linked rejects | Shortlist |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 09:51 | 42 | {"soccer": 23, "tennis": 10, "nba": 8, "nfl": 1} | 21 | 0 | 21 | 3 | {"nba": 3} | 1 | 1 | 1 | 0 |
| 21:40 | 13 | {"tennis": 1, "soccer": 3, "nba": 8, "nfl": 1} | 13 | 9 | 0 | 0 | {} | 0 | 0 | 0 | 0 |
| 04:32 | 0 | {} | 0 | 0 | 0 | 0 | {} | 0 | 0 | 0 | 0 |

Exclusion reasons summed over the day's runs: {"event: too few independent bookmakers": 21, "event: no fresh result-market prices": 13, "leg: no bookmaker at or above fair value": 12, "event: probability outside research band": 4, "event: model and market disagree strongly": 1, "event: open injury/lineup research note": 1}

**Counterfactual diagnostics (never used live; no threshold changes):**

| Run (UTC) | Live shortlist | All quotes fresh | No same-competition screen | Both | Pool live / all fresh |
|---|---|---|---|---|---|
| 09:51 | 0 | 0 | 1 | 1 | 3 / 3 |
| 21:40 | 0 | 0 | 0 | 1 | 0 / 4 |
| 04:32 | 0 | 0 | 0 | 0 | 0 / 0 |

Best single run per day (all replayed days):

| NY day | Live | All quotes fresh | No same-competition screen | Both |
|---|---|---|---|---|
| 2026-11-12 | 1 | 1 | 1 | 1 |
| 2026-11-13 | 0 | 1 | 1 | 2 |
| 2026-11-14 | 0 | 0 | 1 | 1 |
| 2026-11-15 | 0 | 0 | 0 | 0 |
| 2026-11-16 | 0 | 0 | 1 | 1 |

Reading: "all quotes fresh" measures the timing/coverage share (structural: the multi-bookmaker refresh versus start times); "no same-competition screen" measures the rule share. Removing that screen is NOT supported unless section 5 shows same-competition outcomes are uncorrelated on an adequate sample.

## Limits

- The replay covers only the days the database holds multi-bookmaker quotes (the job log starts 2026-11-12). Samples are small; intervals are wide and, for pairs, optimistic.
- Decision times are the recorded runs of the daily job (`job_runs`, job `publish`), including the extra runs made on 2026-11-12 while the job was being set up.
- Decision times are the recorded scheduled runs. Event kick-off times are as stored now (a later reschedule would be visible to the replay). Kick-off-time changes are rare and do not touch prices or outcomes.
- The backtest sample is straight-pick value selections in six club soccer leagues; it says nothing about NBA, NFL, tennis or international soccer, and its leg probabilities are blended model/market values.
- Void/postponed legs are dropped from scoring; bookmaker void rules are not modelled.
