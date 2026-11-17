# Parlay candidates (shadow) — 2026-11-17 13:10 New York

Developer-only. **Nothing here is published.** Prices are computed products of single-market quotes (`computed_product_not_a_quote`), not bookmaker combined quotes. Method `parlay-fullslate-shadow-v1`; no network request, no API credit.

## 1. Coverage: before (straight picks only) and after (full slate)

| Measure | Stage-1 (published picks) | Full-slate engine |
|---|---|---|
| Legs considered today | 0 picks | 36 events |
| Usable legs | 0 | 4 (candidate legs 16, events with a leg 11) |
| Combinations checked | 0 | 3 (bounded; truncated: False) |
| Passed leg/combination screens | 0 | 3 |

| Sport | Events today | Fresh prices | Stored model prob | Events with candidate legs |
|---|---|---|---|---|
| nba | 5 | 5 | 5 | 4 |
| soccer | 27 | 19 | 27 | 6 |
| tennis | 4 | 1 | 0 | 1 |

Excluded: {"event: model and market disagree strongly": 1, "event: no fresh result-market prices": 11, "event: open injury/lineup research note": 2, "event: too few independent bookmakers": 11, "leg: no bookmaker at or above fair value": 7}

| Legs | Combinations evaluated | Kept (positive computed EV, beam-capped) |
|---|---|---|
| 2 | 3 | 3 |
| 3 | 0 | 0 |
| 4 | 0 | 0 |
| 5 | 0 | 0 |
| 6 | 0 | 0 |

The Odds API (read from job log, not called here): last run 2026-11-17T18:10:55+00:00, spent 3, remaining 355.

## 2. Shadow shortlist (not shown on the homepage)

- `pc-455a29868f18` 2 legs at **1xBet**: computed product 2.2176, joint prob (if independent) 0.467, computed EV +3.6%. Blocked: no verified bookmaker combined quote (price shown is a computed product); joint calibration criteria not met
  - Ben Shelton v Alexander Zverev (TENNIS:ATP) — ML away @ 1.54 (fair ex-book 0.666; model None; 2026-11-17T19:30:00+00:00)
  - Wales v Portugal (INT:uefa.nations) — 1X2 A @ 1.44 (fair ex-book 0.702; model 0.629668; 2026-11-17T19:45:00+00:00)
- `pc-197c3e01cc6a` 2 legs at **Unibet**: computed product 4.7306, joint prob (if independent) 0.214, computed EV +1.4%. Blocked: no verified bookmaker combined quote (price shown is a computed product); joint calibration criteria not met
  - Ukraine v Georgia (INT:uefa.nations) — 1X2 H @ 2.17 (fair ex-book 0.466; model 0.42654; 2026-11-17T19:45:00+00:00)
  - Minnesota Timberwolves v Portland Trail Blazers (NBA) — ML away @ 2.18 (fair ex-book 0.460; model 0.395626; 2026-11-18T01:00:00+00:00)

## 3. Shadow settlement (`ledger/parlay_candidates_shadow.csv`, read-only from final scores)

- Rows: 2; won 0, lost 0, void 0, open 2; expected wins among settled (product of fair probs): 0.0
- By legs: {"2": {"won": 0, "lost": 0, "void": 0, "open": 2}}
- Far too small for any conclusion; walk-forward multi-leg validation is follow-up work (issue #35, PR B).

## 4. Why not 3–5 recommended parlays today

- Every candidate is shadow: no free source returns a bookmaker's own combined price, so the shown price is a computed product of single-market prices, not a quote.
- Joint calibration not passed (66 disjoint settled pairs of 200 required; 2-leg, six club leagues only).
