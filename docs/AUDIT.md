# Sports Betting Doyen — engineering & statistical audit (2026-11-12)

## Architecture as found (retained)
| Layer | Files | Status |
|---|---|---|
| Storage | `sbi/db.py` (SQLite, immutable `recommendations` via triggers) | ✅ retained |
| Club soccer data | `sbi/sources/football_data.py` (results, xG, multi-book pre/closing odds, fixtures) | ✅ retained |
| International soccer | `sbi/sources/international.py`, `sbi/intl.py` (martj42 history + ESPN fixtures/odds) | ✅ retained, merged into "Soccer" in the UI |
| Multi-book odds | `sbi/sources/odds_api.py` (The Odds API free tier, budgeted) | ✅ retained, extended to NFL/NBA/tennis |
| Models | `sbi/models/dixon_coles.py`, `sbi/models/elo.py` | ✅ retained |
| Pricing / EV | `sbi/markets.py`, `sbi/ev.py`, `sbi/engine.py` | ✅ retained; generic 2-way pricing added for other sports |
| Pipeline | `sbi/pipeline.py`, `sbi/settle.py`, `sbi/performance.py` | ✅ retained; reassessment lifecycle added |
| Backtest | `sbi/backtest.py` | ⚠️ fixed (A1) |
| Front end | `sbi/templates/dashboard.html` → `docs/dashboard/` | 🔁 replaced by the Doyen site (`docs/index.html`); the technical dashboard moved to `docs/dev/` (unlinked dev tool) |
| Automation | `.github/workflows/daily.yml`, Claude scheduled research task | ✅ retained; schedule densified for pre-game reassessment |

## Findings

**A1 — "Model strategy" and "market-only benchmark" reported identical results.**
*Cause:* not a coding bug in the selection logic. The validation-fitted blend weights were about 6e-6 for every market, so the deployed strategy *was* the market-only strategy (`w·model + (1−w)·market ≈ market`), and both simulations made the same 250 bets. Presenting them as two strategies was misleading.
*Fix:* the backtest now evaluates three explicitly defined strategies: **market_only** (w=0), **model_only** (w=1) and **blend** (validation-fitted). It reports `blend_equals_market_only = true` instead of duplicating the table. This measures the model's incremental value directly (see §Results).

**A2 — Does the model add predictive value?** On club soccer, no. Dixon-Coles has worse out-of-sample log loss than the de-vigged market (paired 95% CI of the per-match difference +0.016 to +0.025 on 5,258 test matches), which is why w→0. Any club pick therefore rests on *price versus sharp consensus*, not on the model. The UI and explanations now say so plainly.

**A3 — Look-ahead / leakage review.** No leakage found:
- DC fits use only matches with kickoff < refit date.
- Elo is computed sequentially from pre-match information only.
- The ordered-logit map is fitted on training rows only.
- Hyperparameters are tuned on 2020–22, blend weights fitted on 2022–24, and the test is 2024–Nov 2026.
- Selection thresholds were fixed a priori and never tuned on test results.

Residual caveat: football-data "pre" odds are snapshots collected Tue/Fri, so their exact availability time is approximate.

**A4 — Historical odds handling.** Bets use pre-match odds, and CLV uses closing odds. However, 78% of test bets came from a single soft bookmaker column (1xBet) that football-data stopped publishing after 2024-25. That bookmaker also commonly restricts winning accounts. The +11.4% test ROI (95% CI −7.5% to +32%) is **not evidence of profitability**. It must not be presented as such, and the UI no longer shows it.

**A5 — Calibration.**
- Club DC is calibrated to within about 2–4 pp.
- The international DC is underconfident on heavy favourites (0.85 predicted → 0.94 observed). A tune-period power calibration did not fix it, so such gaps are flagged as artifacts and never published.

**A6 — Pessimistic EV ranking degenerates when w=0.** EV and pessimistic EV coincide when w=0, so ranking falls back to EV. This is accepted and documented. Uncertainty for w=0 picks comes from market dispersion and staleness, now shown as "risk".

**A7 — Stale odds.** Club odds from football-data can be up to 96h old (accepted by the rules). The site now labels any price older than 24h as *stale* on the card. The Odds API refresh is prioritised for events starting soonest.

**A8 — Prediction tracking duplicates.** Each run inserts a new prediction set. Calibration uses the latest pre-kickoff prediction per event, which is correct. This is accepted.

## Results after the A1 fix
See `data/backtest/report.json → strategies` (filled in by the re-run on 2026-11-12) and the summary at the end of this file.

### Re-run with three explicit strategies (test seasons 2024-25 → Nov 2026, deployed rules)

| Strategy | Bets | ROI (95% CI) | Avg claimed EV | Avg CLV (95% CI) | Beat the close |
|---|---|---|---|---|---|
| **market_only** (price vs sharp consensus) | 250 | +11.4% (−7.5% … +32.0%) | +4.5% | **+4.5% (+3.6% … +5.3%)** | 83% |
| **model_only** (trust Dixon-Coles) | 136 | **−23.6%** (−50.7% … +7.8%) | +26.7% | −0.9% (−2.1% … +0.3%) | 54% |
| blend (fitted w ≈ 0) | identical to market_only by construction (`blend_equals_market_only: true`) | | | | |

**Conclusion:** the model's apparent edges are illusory. They claim +27% EV, but bets placed on them fail to beat the closing line. The only defensible club-soccer signal is a soft bookmaker's price beating a sharp de-vigged consensus, and even that has an ROI interval spanning zero. Doyen therefore publishes picks only on that basis and labels them accordingly. The model is used for context (expected goals, form) and for flagging disagreement as a risk.
