# Parlay candidates (shadow) — 2026-11-27 23:19 New York

Developer-only. **Nothing here is published.** Prices are computed products of single-market quotes (`computed_product_not_a_quote`), not bookmaker combined quotes. Method `parlay-fullslate-shadow-v1`; no network request, no API credit.

## 1. Coverage: before (straight picks only) and after (full slate)

| Measure | Stage-1 (published picks) | Full-slate engine |
|---|---|---|
| Legs considered today | 13 picks | 0 events |
| Usable legs | 0 | 0 (candidate legs 0, events with a leg 0) |
| Combinations checked | 0 | 0 (bounded; truncated: False) |
| Passed leg/combination screens | 0 | 0 |

| Sport | Events today | Fresh prices | Stored model prob | Events with candidate legs |
|---|---|---|---|---|

Excluded: {"leg: no bookmaker at or above fair value": 0}

| Legs | Combinations evaluated | Kept (positive computed EV, beam-capped) |
|---|---|---|
| 2 | 0 | 0 |
| 3 | 0 | 0 |
| 4 | 0 | 0 |
| 5 | 0 | 0 |
| 6 | 0 | 0 |

The Odds API (read from job log, not called here): last run 2026-11-28T04:21:08+00:00, spent 7, remaining 110.

## 2. Shadow shortlist (not shown on the homepage)

- none

## 3. Shadow settlement (`ledger/parlay_candidates_shadow.csv`, read-only from final scores)

- Rows: 7; won 1, lost 5, void 0, open 1; expected wins among settled (product of fair probs): 1.844
- By legs: {"2": {"won": 1, "lost": 5, "void": 0, "open": 1}}
- Far too small for any conclusion; walk-forward multi-leg validation is follow-up work (issue #35, PR B).

## 4. Why not 3–5 recommended parlays today

- No combination of today's legs is priced at or above leave-one-out fair value at one bookmaker after the screens; 0 candidates is the honest result.
- Only 0 leg(s) are at or above fair value at any bookmaker.
- Every candidate is shadow: no free source returns a bookmaker's own combined price, so the shown price is a computed product of single-market prices, not a quote.
- Joint calibration not passed (66 disjoint settled pairs of 200 required; 2-leg, six club leagues only).
