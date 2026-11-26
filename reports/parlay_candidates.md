# Parlay candidates (shadow) — 2026-11-26 14:51 New York

Developer-only. **Nothing here is published.** Prices are computed products of single-market quotes (`computed_product_not_a_quote`), not bookmaker combined quotes. Method `parlay-fullslate-shadow-v1`; no network request, no API credit.

## 1. Coverage: before (straight picks only) and after (full slate)

| Measure | Stage-1 (published picks) | Full-slate engine |
|---|---|---|
| Legs considered today | 22 picks | 22 events |
| Usable legs | 5 | 6 (candidate legs 21, events with a leg 16) |
| Combinations checked | 26 | 10 (bounded; truncated: False) |
| Passed leg/combination screens | 1 | 3 |

| Sport | Events today | Fresh prices | Stored model prob | Events with candidate legs |
|---|---|---|---|---|
| nfl | 2 | 2 | 2 | 1 |
| soccer | 18 | 18 | 0 | 15 |
| tennis | 2 | 0 | 0 | 0 |

Excluded: {"event: model and market disagree strongly": 1, "event: no fresh result-market prices": 2, "event: probability outside research band": 1, "event: too few independent bookmakers": 2, "leg: no bookmaker at or above fair value": 10}

| Legs | Combinations evaluated | Kept (positive computed EV, beam-capped) |
|---|---|---|
| 2 | 7 | 3 |
| 3 | 3 | 0 |
| 4 | 0 | 0 |
| 5 | 0 | 0 |
| 6 | 0 | 0 |

The Odds API (read from job log, not called here): last run 2026-11-26T19:52:44+00:00, spent 30, remaining 159.

## 2. Shadow shortlist (not shown on the homepage)

- `pc-732f4e87444e` 2 legs at **1xBet**: computed product 4.095, joint prob (if independent) 0.249, computed EV +1.8%. Blocked: no verified bookmaker combined quote (price shown is a computed product); joint calibration criteria not met
  - FC Nordsjælland v Panathinaikos (UECL) — 1X2 A @ 3.15 (fair ex-book 0.319; model None; 2026-11-26T20:00:00+00:00)
  - Sunderland v Jagiellonia Bialystok (UEL) — 1X2 H @ 1.3 (fair ex-book 0.779; model None; 2026-11-26T20:00:00+00:00)

## 3. Shadow settlement (`ledger/parlay_candidates_shadow.csv`, read-only from final scores)

- Rows: 5; won 1, lost 1, void 0, open 3; expected wins among settled (product of fair probs): 0.682
- By legs: {"2": {"won": 1, "lost": 1, "void": 0, "open": 3}}
- Far too small for any conclusion; walk-forward multi-leg validation is follow-up work (issue #35, PR B).

## 4. Why not 3–5 recommended parlays today

- Legs cluster in few competitions, and two legs from one competition are never combined.
- Every candidate is shadow: no free source returns a bookmaker's own combined price, so the shown price is a computed product of single-market prices, not a quote.
- Joint calibration not passed (66 disjoint settled pairs of 200 required; 2-leg, six club leagues only).
