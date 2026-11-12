# Sports Betting Doyen — Quantitative methodology (football, model `dc-0.1`)

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

## 8. Results — walk-forward backtest run 2026-11-12 (`data/backtest/report.json`)

**Selected hyperparameters (tune seasons):** ξ = 0.0026/day (half-life ≈ 9 months), ridge = 2.0.
The grid was nearly flat: log loss ranged from 1.0100 to 1.0132.

**1X2 forecasting, out-of-sample test (2024-25 → Nov 2026; 5,258 matches, 6 leagues)**

| Model | Log loss | Brier |
|---|---|---|
| Base rate (in-sample) | 1.0738 | 0.6498 |
| Elo + ordered logit | 1.0024 | 0.5990 |
| Dixon-Coles | 1.0036 | 0.5998 |
| Market consensus, pre-match (de-vigged) | **0.9834** | **0.5867** |
| Market consensus, closing | 0.9814 | 0.5853 |

- Dixon-Coles is well calibrated (reliability bins within about 2–4 pp) and far better than base rates. It is **about as good as Elo**, but **clearly worse than the betting market**: the per-match log-loss gap is +0.016 to +0.025 (95% CI), and the validation seasons show the same result.
- O/U 2.5: model 0.6859 vs market 0.6737 log loss.
- **Consequently the fitted blend weights are ≈ 0 for every market.** The model's probabilities carry no information the market lacks. The system therefore does **not** trust the model's disagreements with the market, which is exactly the safeguard intended.

**Simulated betting, test seasons, deployed rules** (equal to the model-ignored benchmark, because w ≈ 0)

| Metric | Value |
|---|---|
| Bets | 250 (212 in 2024-25, 27 in 2025-26, 11 in 2026-27) |
| Profit / ROI | +28.5 u / +11.4% (95% CI −7.5% to +32.0%), **not significant** |
| Average CLV vs closing sharp consensus | **+4.5% (95% CI +3.6% to +5.3%)**; 83% of bets beat the close |
| Average odds / hit rate / max drawdown | 3.46 / 35.6% / 12.4 u |

**Interpretation (honest):**
1. The only edge the system detects is **price-shopping**: prices at individual bookmakers that exceed a sharp de-vigged consensus. Positive CLV is credible evidence that those prices really were above fair value. However, 78% of test bets came from a single soft bookmaker (1xBet) that football-data stopped publishing after 2024-25. Volume has since fallen sharply, and such bookmakers often limit winning accounts.
2. ROI is positive, but its confidence interval comfortably includes zero. **This is not proof of a persistent advantage.**
3. Next model improvements must beat the market's log loss to earn non-zero weight. Candidates are xG-based ratings, lineup strength, and fresher odds snapshots (Roadmap 2b/3b). Until then, recommendations should be read as "this price is above the sharp consensus", not "the model knows better".

## 9. National teams (model `dc-intl-0.1`) — monitoring mode

- **Data:** every men's international result (martj42/international_results, CC0) with tournament and a neutral-venue flag. ESPN scoreboards fill the gap after the dataset's last update and supply fixtures plus DraftKings odds (opening and current).
- **Model:** the same Dixon-Coles likelihood, with the home-advantage term switched off at neutral venues, over an 8-year window. Friendlies get their own weight factor. Teams need at least 15 matches in the window.
- **Hyperparameters** were tuned on 2023–24 walk-forward predictions (monthly refits): ξ = 0.001/day (half-life ≈ 1.9 years), ridge = 0.1, friendly weight = 1.0. Several optima sat at grid edges, so the grid was extended once.
- **Known bias:** on the test period the model is **underconfident on heavy favourites**. Predicted home-win probabilities of 0.70–0.80 hit 0.83, and 0.80–0.90 hit 0.94. A power calibration fitted on the tune period came out at a ≈ 0.98 and did not correct it, and it was not re-fitted on test data. Monitoring rows where the model backs an underdog against a >70% bookmaker favourite are flagged as likely artifacts. Fix candidates (Roadmap 3c): per-outcome Platt/isotonic calibration on a rolling validation window, and a goal model with over-dispersion or a mismatch-dependent draw term.
- **Out-of-sample test (Jan 2025 – Oct 2026, 1,758 matches), 1X2 log loss:**

| Subset | n | Dixon-Coles | Elo | Base rate |
|---|---|---|---|---|
| All | 1,758 | **0.8294** (calibrated 0.8305) | 0.8434 | 1.0469 |
| Competitive | 1,273 | **0.8167** | 0.8304 | 1.0480 |
| Friendlies | 485 | **0.8627** | 0.8777 | 1.0439 |

  DC beats Elo significantly (paired 95% CI of the log-loss difference: −0.025 to −0.004).
- **Why there are no recommendations yet:** free international odds come from one bookmaker, and there is no free history of international odds. The model's skill *relative to the market*, which is what matters for value, therefore cannot be backtested. The system publishes model-vs-book comparisons as **monitoring signals**, stores every prediction with the bookmaker's de-vigged probability, and scores both once results arrive (dashboard → Model analytics → live prediction tracking). Once roughly 300 or more matches have settled, a blend weight can be fitted on that live out-of-sample record. Adding multi-bookmaker odds (The Odds API free key) would allow consensus pricing like the club-football pipeline.


## 10. NFL, NBA and tennis (Doyen v0.2)

*Golf was built and evaluated, then removed from Doyen on 2026-11-12 at the owner's request. Its code remains in git history.*

| Sport | Model | Out-of-sample test | Result | Weight vs market |
|---|---|---|---|---|
| NFL | Points ratings (time-decayed ridge on offence/defence, home field), discrete-normal margin/total | 989 games, 2023–2026, vs **de-vigged closing moneyline** (nflverse) | log loss 0.63927 vs market 0.60926 (95% CI of gap 0.01688 … 0.04306); home-rate baseline 0.68962 | **0** (fitted on 2021–22) |
| NBA | Same points model; a back-to-back feature was tested and **dropped** (no out-of-sample gain) | 1492 games, 2025-26 season to date | log loss 0.60552 (with rest feature 0.60517 without); home-rate 0.68822 | **0**: no free NBA odds history to validate against |
| Tennis | Overall + surface Elo (dynamic K); best-of-5 conversion for men's Slams; match winner only | 11609 matches since Jul 2025 (29057 in history) | log loss 0.63811 vs coin flip 0.69315; favourite won 62.7% | **0**: no free tennis odds history |

**Consequence.** For every sport, a published pick rests on *price versus the sharp multi-bookmaker consensus*, the only mechanism with positive evidence (club soccer CLV +4.5%). Models supply context (projections, ratings, simulations) and risk flags when they disagree with the market. They earn weight only by beating the market out of sample.

**Markets.**
- Soccer: 1X2, O/U, Asian handicap.
- NFL/NBA: moneyline, spread, total (discrete margin/total distributions handle pushes on whole-number lines).
- Tennis: match winner only. Set handicaps and total games are excluded because they are not modelled reliably.

**Pre-game reassessment.** Every run (every 2 hours) re-prices open picks against the latest odds and appends a status: *active* (still qualifies), *updated* (edge narrowed), *withdrawn* (no longer value) or *expired* (started). These go to the append-only `rec_updates` table. The original pick, its odds and its timestamp never change, and withdrawn picks are still settled and counted in Pick History.

## 11. Doyen v0.3: diagnostics, context and feature tests

- **Opportunity funnel** (`sbi/diagnostics.py` → `data/diagnostics.json`, `reports/diagnostics.md`). For each sport over the next 48h it counts: events discovered → with sufficient statistics → with odds → stale-only → with ≥ 3 bookmakers → markets evaluated → qualifying, plus the primary blocker per event. On 2026-11-12 the dominant blockers were missing multi-bookmaker coverage (international friendlies and qualifiers have only DraftKings; tomorrow's NBA and most tennis are not yet priced). Where several books quoted, prices matched the sharp consensus. That makes it a coverage problem, not a threshold problem, so **thresholds were not changed**.
- **Minimum-bookmaker rule reviewed.** Kept at 3 independent bookmakers (after name normalisation). With fewer, there is no market consensus to measure a price against, and a lone soft book's price can't be checked.
- **NFL EPA features.** Prior-game, exponentially weighted offensive/defensive EPA per play from nflverse play-by-play was added to the points model:
  - Tune 2018–20: 0.6283 → 0.6252.
  - Test 2023–26 (989 games): 0.6393 → 0.6393, 95% CI of the difference −0.0057 … +0.0055.
  - **Not adopted** (no out-of-sample gain). The closing market (0.6093) remains far better.
- **External forecasts** (ESPN Analytics) are stored and compared, never blended, until they are validated out of sample like any other model.
- **Reassessment** now also appends notes for injury status changes on either team and for confirmed soccer lineups. Price-based status (active, updated, withdrawn) is unchanged.
- **Odds API timing.** A competition is fetched when its next event is within 10h (refresh every 4h, plus a final refresh ≤ 2.5h before start). Otherwise it gets one first look per day, within the daily credit allowance.


## 12. Doyen v0.4: weekly coverage, rule sensitivity, model audit

**Why the week had zero picks (diagnosed 2026-11-12).** In the 7-day window, NBA had 52 games but only 4 (all that night) had any odds. Sunday's 11 NFL games had only DraftKings. Soccer beyond day 0 had no multi-bookmaker prices, and tennis had almost none. The causes:
1. A connector defect: The Odds API returns every upcoming game per request, but Doyen stored only games starting within 36h. About 50 of 58 paid-for games were discarded per run.
2. Credits were under-used: a per-run cap of 8, with roughly 483 of 500 monthly credits idle.
3. ESPN prices NBA games only on game day.
4. Picks could only be published within 48h.
5. Genuine coverage gaps: international friendlies, most qualifiers and most tennis are not offered by any free multi-bookmaker source.

Fixes 1, 2 and 4 are in v0.4. Point 5 is a real limitation.

**Actionable versus preliminary.** Analysis covers 7 days. A market is *actionable* only with quotes no more than 24h old (previously 96h). Older quotes are treated as stale and excluded, and the event shows a preliminary model forecast only. Picks may be published up to 7 days ahead when fresh multi-bookmaker prices exist.

**Odds API allocation.**
- Every event in the 7-day window is stored from each response, with per-competition coverage logged (returned / in window / matched).
- Fetches happen once a day per competition with events this week, every 8h within 36h of the start, every 4h within 10h, plus a final refresh within 2.5h.
- Up to 12 credits per run, inside the daily allowance.
- Both-teams-to-score: The Odds API rejects `btts` on its bulk endpoint (HTTP 422; per-event requests only, which would cost one call per match), so BTTS is supported in pricing and settlement but **not fetched live**.

**Rule sensitivity** (club soccer, market-only, validation 2022–24 / test 2024–Nov 2026):

| Variant | Val bets | Val CLV | Val ROI | Test bets | Test CLV | Test ROI (95% CI) |
|---|---|---|---|---|---|---|
| baseline (EV>=3%, 3 books, odds<=6) | 45 | +1.2% | +45.3% | 250 | +4.5% | +11.4% (-7…+32) |
| EV>=1% | 258 | +0.6% | -14.9% | 1013 | +2.4% | -2.6% (-12…+7) |
| EV>=2% | 103 | +0.8% | +2.6% | 508 | +3.2% | +5.3% (-8…+19) |
| EV>=5% | 10 | +3.9% | +145.8% | 43 | +4.8% | +11.3% (-31…+57) |
| 2 bookmakers | 57 | +2.7% | +35.8% | 250 | +4.5% | +11.4% (-7…+32) |
| 5 bookmakers | 45 | +1.2% | +45.3% | 189 | +4.9% | +13.4% (-10…+40) |
| odds<=10 | 93 | +1.7% | +27.0% | 259 | +4.3% | +9.0% (-9…+30) |
| odds<=3.5 | 21 | +2.9% | -3.4% | 115 | +5.1% | +36.2% (+10…+63) |

**Conclusion: rules unchanged.**
- Lowering the EV threshold raises volume but lowers CLV, and turns ROI negative at 1%.
- The 3-bookmaker rule is not binding in the historical data, because football-data rows carry many books. Live, it binds only on single-bookmaker markets that have no sharp reference.
- Odds ≤ 3.5 looks promising (test ROI CI excludes zero) but rests on only 21 validation bets. It is flagged for re-testing and **not adopted**.

**Model audit.**
- Tennis Elo was re-tuned chronologically: surface weight 0.15, K scale 0.6. Test log loss went from 0.63811 to 0.63479 on 11609 matches, so it was **adopted**.
- A fatigue feature (matches in the previous 7 days) gave 0.63395, below the adoption bar, so it was **not adopted**.
- NFL EPA: no out-of-sample gain (§11).
- NBA rest: no gain (§10).
- Soccer and international models: unchanged. The club model is still worse than the market.

None of the models beats a bookmaker baseline, so all keep weight 0.

**Markets.**
- Enabled: soccer 1X2, O/U and Asian handicap (BTTS is ready in code, but no free bulk odds exist); NFL/NBA moneyline, spread and total; tennis match winner.
- Not enabled: tennis set handicaps and total games. Settlement needs game-level scores that are not yet stored, and there is no validated model for them.

**Value method audit.**
- Fair value comes from the sharp source's own two- or three-way market, de-vigged with the power method.
- The best price is taken from a *different*, independent bookmaker. If the best price comes from the consensus source itself, it cannot beat its own fair value. Exchange prices are net of commission.
- Bookmaker names are normalised so duplicate feeds don't count twice.
- Missing or stale data excludes a market rather than filling it in.
- Correlated markets on the same event are limited to one pick per event.
