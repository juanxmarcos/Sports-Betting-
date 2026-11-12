# Quantitative methodology (football, model `dc-0.1`)

## 1. Probability model — time-weighted Dixon-Coles
Goals: `log λ_home = h + att_home + def_away`, `log μ_away = att_away + def_home`, with the
Dixon-Coles low-score correction τ(ρ) for 0-0, 1-0, 0-1 and 1-1. Fitted per league by penalised
weighted maximum likelihood (L-BFGS-B, analytic gradient, about 15 ms per fit):

- **Time decay** `w = exp(−ξ · days)` over a 3-season window (Dixon & Coles 1997).
- **Ridge penalty** on att/def. This makes the model identifiable and shrinks thinly observed teams toward average.
- ξ and the ridge strength are **not hand-picked**. They are chosen by out-of-sample 1X2 log loss on the *tune* seasons (grid, see §5).
- **Parameter uncertainty:** inverse observed Fisher information of the Poisson likelihood. Each fixture is priced under 300 Monte-Carlo parameter draws, giving a probability sd and a 10th percentile. ρ is held fixed, so the bands are lower bounds on the true uncertainty.
- A full score matrix (0–10 goals) yields every market consistently.

**Baselines** (all must be beaten out of sample before the model gets weight): in-sample base
rates, Elo (goal-difference K) with an ordered-logit map to 1X2, de-vigged pre-match market
consensus, and de-vigged closing consensus (the hardest benchmark).

## 2. Markets and settlement
1X2, Over/Under 2.5 and Asian handicap at football-data's quoted line are priced and settled.
Double chance and BTTS are computed for display; they are not bet, because no free odds exist
for them yet. Quarter lines are split into two half-stakes. Every selection is reduced to
outcome shares (win, half-win, push, half-loss, loss), so

`EV(o) = p_w(o−1) + p_hw(o−1)/2 − p_hl/2 − p_l = (A+B)(q·o − 1)`, with `A = p_w + p_hw/2`,
`B = p_l + p_hl/2`, `q = A/(A+B)`.

For 1X2 this is the familiar `EV = p·o − 1`. Brute-force settlement over the score grid is
unit-tested to equal this formula.

## 3. Market probability and fair price
- Each bookmaker's market must be complete with an overround between 0.97 and 1.20, otherwise it is discarded (stale or illiquid quotes).
- Consensus = **power-method de-vig** of the sharpest available source: Betfair Exchange, then Pinnacle, then the market average. If none is usable, the median of the individual books' de-vigged probabilities is used.
- Best price = maximum across individual bookmakers (never the Max/Avg aggregates). Exchange prices are net of 5% commission.
- **Final probability** = linear pool `w·q_model + (1−w)·q_market`, with `w` per market fitted by log loss on the *validation* seasons. If the model adds nothing over the market, `w → 0`, and the system degenerates honestly into "price-shopping against a sharp consensus".
- Fair odds = `1/q_final`.

## 4. Selection rules (conservative; `config.SelectionRules`)
| Rule | Default | Why |
|---|---|---|
| EV at final probability | ≥ 3% | Covers residual model error and odds staleness |
| Pessimistic EV (model p10 in the pool) | > 0 | The edge must survive parameter uncertainty |
| Odds range | 1.30–6.00 | Longshot probabilities are least reliable |
| Bookmakers with a sane market | ≥ 3 | Consensus quality |
| Matches per team in window | ≥ 12 | Data completeness (promoted teams start thin) |
| sd of final probability (`w·sd_model`) | ≤ 6 pp | Maximum accepted model uncertainty |
| Odds snapshot age | ≤ 96 h | Stale prices excluded |
| Per event | 1 selection | Markets on one match are correlated |
| Stake / day cap | 1 unit / 10 units | Fixed-unit paper staking; no progression, no chasing |

**Ranking** = pessimistic EV, so robust edges outrank fragile ones. There are no arbitrary
confidence scores. Zero qualifying selections is a normal, expected outcome.

## 5. Backtest protocol (`python -m sbi backtest`)
- Six leagues (E0, E1, SP1, D1, I1, F1), seasons 2017-18 to 2026-27 (to date).
- **Walk-forward:** the model is refitted every 7 days on matches strictly before the refit date, then prices the next 7 days. Elo is computed sequentially from pre-match information only.
- Odds: football-data "pre" odds are collected before kick-off (typically Fri/Tue), and those are what we "bet" at. Closing odds are used only for CLV.
- **Splits:** tune 2020-22 (ξ, ridge) → validate 2022-24 (blend weights) → **test 2024-25, 2025-26, 2026-27 (untouched)**.
- The betting simulation on the test seasons uses exactly the deployed `engine.select` rules. It is compared with the same rules at `w=0` (model ignored), which isolates the model's contribution.
- Reported: log loss, Brier, a paired bootstrap CI of the model-vs-market log-loss difference, calibration bins, ROI with a bootstrap 95% CI, CLV, drawdown, and breakdowns by market and league.
- Limitations: football-data's "pre" odds snapshot time is approximate. Bookmaker limits and stake acceptance are not modelled. The in-sample base-rate baseline is optimistic.

## 6. Contextual research (Claude)
Claude researches team news for open selections and records findings with an evidence grade
(verified fact needs a source URL; interpretation; speculation) and a direction. Notes are
**risk flags only**: they never change probabilities, odds or published rows. A future
quantitative adjustment (for example lineup strength) will enter only as a model feature
validated by the same backtest.

## 7. Performance accounting
Every published row is immutable, enforced by database triggers. Settlement records the result, P/L
(after exchange commission), closing odds and CLV (`our net odds × closing fair probability − 1`).
Reported metrics: hit rate, yield with a bootstrap CI, cumulative P/L, maximum drawdown, CLV, and
breakdowns by league, market and odds band. Brier and log loss are reported for published selections
and for **all** predictions, so calibration is tracked even on days without bets. Sample-size
warnings are shown until at least 500 settled selections exist.

## 8. Results
See `RESULTS` below (generated from `data/backtest/report.json`).
