# Parlay candidates (shadow) — 2026-11-28 03:53 New York

Developer-only. **Nothing here is published.** Prices are computed products of single-market quotes (`computed_product_not_a_quote`), not bookmaker combined quotes. Method `parlay-fullslate-shadow-v1`; no network request, no API credit.

## 1. Coverage: before (straight picks only) and after (full slate)

| Measure | Stage-1 (published picks) | Full-slate engine |
|---|---|---|
| Legs considered today | 8 picks | 53 events |
| Usable legs | 0 | 10 (candidate legs 45, events with a leg 35) |
| Combinations checked | 0 | 16 (bounded; truncated: False) |
| Passed leg/combination screens | 0 | 11 |

| Sport | Events today | Fresh prices | Stored model prob | Events with candidate legs |
|---|---|---|---|---|
| nba | 5 | 5 | 5 | 4 |
| soccer | 46 | 46 | 46 | 31 |
| tennis | 2 | 0 | 0 | 0 |

Excluded: {"event: model and market disagree strongly": 2, "event: no fresh result-market prices": 2, "event: probability outside research band": 6, "event: too few independent bookmakers": 8, "leg: no bookmaker at or above fair value": 25}

| Legs | Combinations evaluated | Kept (positive computed EV, beam-capped) |
|---|---|---|
| 2 | 11 | 9 |
| 3 | 4 | 2 |
| 4 | 1 | 0 |
| 5 | 0 | 0 |
| 6 | 0 | 0 |

The Odds API (read from job log, not called here): last run 2026-11-28T08:55:02+00:00, spent 14, remaining 96.

## 2. Shadow shortlist (not shown on the homepage)

- `pc-4b4283db206d` 2 legs at **DraftKings**: computed product 6.2808, joint prob (if independent) 0.180, computed EV +13.0%. Blocked: no verified bookmaker combined quote (price shown is a computed product); joint calibration criteria not met
  - Nice v Troyes (F1) — 1X2 H @ 1.7692307692307692 (fair ex-book 0.578; model 0.515471; 2026-11-28T19:45:00+00:00)
  - Cambuur v Sparta Rotterdam (N1) — 1X2 A @ 3.55 (fair ex-book 0.311; model 0.209669; 2026-11-28T20:00:00+00:00)
- `pc-cfbec32f341b` 3 legs at **1xBet**: computed product 3.817, joint prob (if independent) 0.269, computed EV +2.8%. Blocked: no verified bookmaker combined quote (price shown is a computed product); joint calibration criteria not met
  - Leeds v Coventry (E0) — 1X2 H @ 1.53 (fair ex-book 0.660; model 0.568693; 2026-11-28T15:00:00+00:00)
  - Stuttgart v Ein Frankfurt (D1) — 1X2 H @ 1.89 (fair ex-book 0.536; model 0.586569; 2026-11-28T17:30:00+00:00)
  - Inter v Genoa (I1) — 1X2 H @ 1.32 (fair ex-book 0.761; model 0.759041; 2026-11-28T19:45:00+00:00)
- `pc-63fefb30e786` 2 legs at **Unibet**: computed product 5.301, joint prob (if independent) 0.193, computed EV +2.4%. Blocked: no verified bookmaker combined quote (price shown is a computed product); joint calibration criteria not met
  - Man United v Brentford (E0) — 1X2 A @ 3.1 (fair ex-book 0.330; model 0.350152; 2026-11-28T15:00:00+00:00)
  - West Ham v Stoke (E1) — 1X2 H @ 1.71 (fair ex-book 0.586; model 0.517871; 2026-11-28T15:00:00+00:00)

## 3. Shadow settlement (`ledger/parlay_candidates_shadow.csv`, read-only from final scores)

- Rows: 10; won 1, lost 6, void 0, open 3; expected wins among settled (product of fair probs): 1.948
- By legs: {"2": {"won": 1, "lost": 6, "void": 0, "open": 2}, "3": {"won": 0, "lost": 0, "void": 0, "open": 1}}
- Far too small for any conclusion; walk-forward multi-leg validation is follow-up work (issue #35, PR B).

## 4. Why not 3–5 recommended parlays today

- Every candidate is shadow: no free source returns a bookmaker's own combined price, so the shown price is a computed product of single-market prices, not a quote.
- Joint calibration not passed (66 disjoint settled pairs of 200 required; 2-leg, six club leagues only).
