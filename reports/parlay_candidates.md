# Parlay candidates (shadow) — 2026-11-19 14:10 New York

Developer-only. **Nothing here is published.** Prices are computed products of single-market quotes (`computed_product_not_a_quote`), not bookmaker combined quotes. Method `parlay-fullslate-shadow-v1`; no network request, no API credit.

## 1. Coverage: before (straight picks only) and after (full slate)

| Measure | Stage-1 (published picks) | Full-slate engine |
|---|---|---|
| Legs considered today | 7 picks | 7 events |
| Usable legs | 0 | 1 (candidate legs 4, events with a leg 3) |
| Combinations checked | 0 | 0 (bounded; truncated: False) |
| Passed leg/combination screens | 0 | 0 |

| Sport | Events today | Fresh prices | Stored model prob | Events with candidate legs |
|---|---|---|---|---|
| nba | 4 | 4 | 4 | 2 |
| nfl | 1 | 1 | 1 | 0 |
| tennis | 2 | 1 | 0 | 1 |

Excluded: {"event: model and market disagree strongly": 1, "event: no fresh result-market prices": 1, "event: probability outside research band": 2, "leg: no bookmaker at or above fair value": 2}

| Legs | Combinations evaluated | Kept (positive computed EV, beam-capped) |
|---|---|---|
| 2 | 0 | 0 |
| 3 | 0 | 0 |
| 4 | 0 | 0 |
| 5 | 0 | 0 |
| 6 | 0 | 0 |

The Odds API (read from job log, not called here): last run 2026-11-19T19:12:11+00:00, spent 13, remaining 296.

## 2. Shadow shortlist (not shown on the homepage)

- none

## 3. Shadow settlement (`ledger/parlay_candidates_shadow.csv`, read-only from final scores)

- Rows: 2; won 1, lost 1, void 0, open 0; expected wins among settled (product of fair probs): 0.682
- By legs: {"2": {"won": 1, "lost": 1, "void": 0, "open": 0}}
- Far too small for any conclusion; walk-forward multi-leg validation is follow-up work (issue #35, PR B).

## 4. Why not 3–5 recommended parlays today

- No combination of today's legs is priced at or above leave-one-out fair value at one bookmaker after the screens; 0 candidates is the honest result.
- Only 1 leg(s) are at or above fair value at any bookmaker.
- Every candidate is shadow: no free source returns a bookmaker's own combined price, so the shown price is a computed product of single-market prices, not a quote.
- Joint calibration not passed (66 disjoint settled pairs of 200 required; 2-leg, six club leagues only).
