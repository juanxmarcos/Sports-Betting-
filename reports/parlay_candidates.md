# Parlay candidates (shadow) — 2026-11-27 00:14 New York

Developer-only. **Nothing here is published.** Prices are computed products of single-market quotes (`computed_product_not_a_quote`), not bookmaker combined quotes. Method `parlay-fullslate-shadow-v1`; no network request, no API credit.

## 1. Coverage: before (straight picks only) and after (full slate)

| Measure | Stage-1 (published picks) | Full-slate engine |
|---|---|---|
| Legs considered today | 19 picks | 25 events |
| Usable legs | 1 | 7 (candidate legs 24, events with a leg 17) |
| Combinations checked | 0 | 16 (bounded; truncated: False) |
| Passed leg/combination screens | 0 | 10 |

| Sport | Events today | Fresh prices | Stored model prob | Events with candidate legs |
|---|---|---|---|---|
| nba | 11 | 11 | 11 | 11 |
| nfl | 1 | 1 | 1 | 0 |
| soccer | 9 | 9 | 9 | 6 |
| tennis | 4 | 0 | 0 | 0 |

Excluded: {"event: model and market disagree strongly": 1, "event: no fresh result-market prices": 4, "event: open injury/lineup research note": 2, "event: too few independent bookmakers": 1, "leg: no bookmaker at or above fair value": 10}

| Legs | Combinations evaluated | Kept (positive computed EV, beam-capped) |
|---|---|---|
| 2 | 10 | 8 |
| 3 | 5 | 2 |
| 4 | 1 | 0 |
| 5 | 0 | 0 |
| 6 | 0 | 0 |

The Odds API (read from job log, not called here): last run 2026-11-27T05:15:05+00:00, spent 16, remaining 133.

## 2. Shadow shortlist (not shown on the homepage)

- `pc-ec6e71b5bc39` 2 legs at **Marathon Bet**: computed product 10.472, joint prob (if independent) 0.104, computed EV +8.6%. Blocked: no verified bookmaker combined quote (price shown is a computed product); joint calibration criteria not met
  - Venezia v Bologna (I1) — 1X2 D @ 3.4 (fair ex-book 0.300; model 0.246218; 2026-11-27T19:45:00+00:00)
  - San Antonio Spurs v Los Angeles Lakers (NBA) — ML away @ 3.08 (fair ex-book 0.345; model 0.28464; 2026-11-28T02:30:00+00:00)
- `pc-a877c1d14698` 2 legs at **1xBet**: computed product 3.3748, joint prob (if independent) 0.297, computed EV +0.4%. Blocked: no verified bookmaker combined quote (price shown is a computed product); joint calibration criteria not met
  - Groningen v Willem II (N1) — 1X2 H @ 1.43 (fair ex-book 0.701; model 0.725174; 2026-11-27T19:00:00+00:00)
  - LA Clippers v New Orleans Pelicans (NBA) — ML away @ 2.36 (fair ex-book 0.424; model 0.361208; 2026-11-28T02:30:00+00:00)

## 3. Shadow settlement (`ledger/parlay_candidates_shadow.csv`, read-only from final scores)

- Rows: 7; won 1, lost 4, void 0, open 2; expected wins among settled (product of fair probs): 1.546
- By legs: {"2": {"won": 1, "lost": 4, "void": 0, "open": 2}}
- Far too small for any conclusion; walk-forward multi-leg validation is follow-up work (issue #35, PR B).

## 4. Why not 3–5 recommended parlays today

- Every candidate is shadow: no free source returns a bookmaker's own combined price, so the shown price is a computed product of single-market prices, not a quote.
- Joint calibration not passed (66 disjoint settled pairs of 200 required; 2-leg, six club leagues only).
