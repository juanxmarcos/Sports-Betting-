# Parlay candidates (shadow) — 2026-11-26 00:16 New York

Developer-only. **Nothing here is published.** Prices are computed products of single-market quotes (`computed_product_not_a_quote`), not bookmaker combined quotes. Method `parlay-fullslate-shadow-v1`; no network request, no API credit.

## 1. Coverage: before (straight picks only) and after (full slate)

| Measure | Stage-1 (published picks) | Full-slate engine |
|---|---|---|
| Legs considered today | 8 picks | 43 events |
| Usable legs | 0 | 11 (candidate legs 41, events with a leg 33) |
| Combinations checked | 0 | 44 (bounded; truncated: False) |
| Passed leg/combination screens | 0 | 12 |

| Sport | Events today | Fresh prices | Stored model prob | Events with candidate legs |
|---|---|---|---|---|
| nfl | 3 | 3 | 3 | 2 |
| soccer | 36 | 36 | 0 | 31 |
| tennis | 4 | 0 | 0 | 0 |

Excluded: {"event: model and market disagree strongly": 1, "event: no fresh result-market prices": 4, "event: probability outside research band": 2, "event: too few independent bookmakers": 3, "leg: no bookmaker at or above fair value": 22}

| Legs | Combinations evaluated | Kept (positive computed EV, beam-capped) |
|---|---|---|
| 2 | 42 | 12 |
| 3 | 2 | 0 |
| 4 | 0 | 0 |
| 5 | 0 | 0 |
| 6 | 0 | 0 |

The Odds API (read from job log, not called here): last run 2026-11-26T05:17:10+00:00, spent None, remaining None.

## 2. Shadow shortlist (not shown on the homepage)

- `pc-894cbdedf61b` 2 legs at **Unibet**: computed product 3.5984, joint prob (if independent) 0.285, computed EV +2.5%. Blocked: no verified bookmaker combined quote (price shown is a computed product); joint calibration criteria not met
  - Detroit Lions v Chicago Bears (NFL) — ML home @ 2.08 (fair ex-book 0.481; model 0.590446; 2026-11-26T18:00:00+00:00)
  - Torreense v Celtic (UEL) — 1X2 A @ 1.73 (fair ex-book 0.592; model None; 2026-11-26T20:00:00+00:00)
- `pc-b8f9d2b1f759` 2 legs at **1xBet**: computed product 3.0636, joint prob (if independent) 0.332, computed EV +1.6%. Blocked: no verified bookmaker combined quote (price shown is a computed product); joint calibration criteria not met
  - Marseille v Levski Sofia (UEL) — 1X2 H @ 1.38 (fair ex-book 0.728; model None; 2026-11-26T17:45:00+00:00)
  - Hajduk Split v St Truiden (UECL) — 1X2 H @ 2.22 (fair ex-book 0.456; model None; 2026-11-26T20:00:00+00:00)

## 3. Shadow settlement (`ledger/parlay_candidates_shadow.csv`, read-only from final scores)

- Rows: 4; won 1, lost 1, void 0, open 2; expected wins among settled (product of fair probs): 0.682
- By legs: {"2": {"won": 1, "lost": 1, "void": 0, "open": 2}}
- Far too small for any conclusion; walk-forward multi-leg validation is follow-up work (issue #35, PR B).

## 4. Why not 3–5 recommended parlays today

- Every candidate is shadow: no free source returns a bookmaker's own combined price, so the shown price is a computed product of single-market prices, not a quote.
- Joint calibration not passed (66 disjoint settled pairs of 200 required; 2-leg, six club leagues only).
