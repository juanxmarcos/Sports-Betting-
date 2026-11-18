# Sports Betting Doyen — Daily Report, 2026-11-17

*Research and paper-trading only. Not financial advice. No bets are placed automatically.
All times America/New_York. Generated Tue 17 Nov 19:31 EST. Model `dc-0.1`.*

## Daily overview

| Item | Value |
|---|---|
| Period | next 7 days (rolling 168h, same as the website "This Week") |
| Events discovered | 109 |
| Events with fresh odds | 24 |
| Events fully evaluated (3+ independent bookmakers, complete history) | 23 |
| Markets evaluated | 343 |
| Events passing all rules | 2 |
| Published today | **2** |
| Highest estimated EV | +9.4% |
| Blend weight on model (1X2/OU/AH) | 0.00/0.00/0.00 |




## Ranked selections

Ranking: by **pessimistic EV** (EV computed with the 10th-percentile model probability from
parameter uncertainty), so that thinly estimated edges rank below robust ones.


### 1. Boston Celtics to win — Denver Nuggets v Boston Celtics

| Field | Value |
|---|---|
| Sport / competition | NBA — NBA |
| Kick-off | Wed 18 Nov 21:30 EST |
| Market / selection | ML — **Boston Celtics to win** |
| Best price | **1.93** @ 1xBet |
| Model probability (raw) | 57.1% (±0.0 pp param. sd; p10 57.1%) |
| Market no-vig probability | 56.7% (median) |
| Final probability (blend) | 56.7% |
| Fair odds | 1.76 |
| Expected value | **+9.4%** (pessimistic +9.4%) |
| Stake (paper) | 1.0 unit |
| Bookmakers quoting | 8 |
| Odds snapshot | Tue 17 Nov 19:31 EST |

**Statistical evidence.** Projected score Denver Nuggets 110.9 – Boston Celtics 113.4. Doyen's ratings project Denver Nuggets 110.9 – Boston Celtics 113.4 pts (margin -2.5, total 224.3); power ranks 10 and 3 of 33.

**Why it may be value.** The best available price (1.93) exceeds the estimated fair
price (1.76). The
model rates this outcome 0.4 pp above the de-vigged consensus.

**Context / research flags.** No contextual research recorded yet (team news is not modelled — check before acting).

**Reasons this could be wrong.**
- Model weight 0.00: the edge is the price versus the multi-bookmaker consensus, not a model opinion.

Sources: <https://api.the-odds-api.com/v4/sports/basketball_nba/odds?regions=eu&markets=h2h,spreads,totals> <https://www.espn.com/basketball/game/_/gameId/401910015> 


### 2. Minnesota Timberwolves to win — Minnesota Timberwolves v Portland Trail Blazers

| Field | Value |
|---|---|
| Sport / competition | NBA — NBA |
| Kick-off | Tue 17 Nov 20:00 EST |
| Market / selection | ML — **Minnesota Timberwolves to win** |
| Best price | **1.77** @ DraftKings (net 1.769 after commission) |
| Model probability (raw) | 60.4% (±0.0 pp param. sd; p10 60.4%) |
| Market no-vig probability | 60.5% (Betfair Exchange) |
| Final probability (blend) | 60.5% |
| Fair odds | 1.65 |
| Expected value | **+7.1%** (pessimistic +7.1%) |
| Stake (paper) | 1.0 unit |
| Bookmakers quoting | 20 |
| Odds snapshot | Tue 17 Nov 19:31 EST |

**Statistical evidence.** Projected score Minnesota Timberwolves 115.0 – Portland Trail Blazers 111.3. Doyen's ratings project Minnesota Timberwolves 115.0 – Portland Trail Blazers 111.3 pts (margin +3.7, total 226.3); power ranks 7 and 9 of 33. Minnesota Timberwolves and Portland Trail Blazers on the second night of a back-to-back (not a model input: it did not improve out-of-sample accuracy).

**Why it may be value.** The best available price (1.77) exceeds the estimated fair
price (1.65). The edge
comes mainly from the price being out of line with the consensus of other bookmakers.

**Context / research flags.** No contextual research recorded yet (team news is not modelled — check before acting).

**Reasons this could be wrong.**
- Model weight 0.00: the edge is the price versus the multi-bookmaker consensus, not a model opinion.

Sources: <https://api.the-odds-api.com/v4/sports/basketball_nba/odds?regions=eu&markets=h2h,spreads,totals> <https://www.espn.com/basketball/game/_/gameId/401910003> 




## Closest candidates (transparency)

| Match | Market | Odds | Final p | EV | Pess. EV | Status |
|---|---|---|---|---|---|---|


## International fixtures — model monitoring (not recommendations)

3 national-team matches analysed in the next 48h (model `dc-intl-0.1`,
trained on 50106 internationals; 0 with multi-bookmaker odds).
The model's gaps against bookmakers are **monitoring signals, not selections**: no free historical international
odds exist to validate the model against the market, so it has weight 0. Real (paper) international selections
appear in *Ranked selections* only when The Odds API supplies 3+ bookmakers and a price beats the sharp
de-vigged consensus under the standard rules.

| Kick-off | Competition | Match | Model H/D/A | Book H/D/A (no-vig) | Largest model–book gap |
|---|---|---|---|---|---|
| Tue 17 Nov 21:30 EST | CONCACAF Nations League | Mexico v Jamaica | 74/18/7 | 87/9/4 | 1X2 D @ 8.00: model EV +46.8% ⚠ bias |
| Tue 17 Nov 20:00 EST | CONCACAF Nations League | El Salvador v Saint Martin | 64/23/14 | — |  |
| Tue 17 Nov 22:00 EST | CONCACAF Nations League | Nicaragua v Montserrat | 67/21/12 | — |  |

⚠ bias = the model is backing an underdog against a heavy bookmaker favourite (>70%). Out of sample the model
is underconfident on heavy favourites, so these gaps are most likely model error, not value.




## Track record (paper, fixed 1-unit stakes)

Settled 17 · W 4 / L 12 / P 1 ·
profit -7.14u · yield -42.0%
(95% CI -84.2% to +8.5%) ·
avg CLV +1.4% · max drawdown 8.2u.
*Only 17 settled selections. Yield CIs are wide; at typical odds, several hundred to a few thousand bets are needed before ROI distinguishes skill from luck. CLV is the faster, more reliable early indicator.*