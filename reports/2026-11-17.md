# Sports Betting Doyen — Daily Report, 2026-11-17

*Research and paper-trading only. Not financial advice. No bets are placed automatically.
All times America/New_York. Generated Tue 17 Nov 17:19 EST. Model `dc-0.1`.*

## Daily overview

| Item | Value |
|---|---|
| Period | next 7 days (rolling 168h, same as the website "This Week") |
| Events discovered | 116 |
| Events with fresh odds | 27 |
| Events fully evaluated (3+ independent bookmakers, complete history) | 20 |
| Markets evaluated | 289 |
| Events passing all rules | 0 |
| Published today | **2** |
| Highest estimated EV | +5.5% |
| Blend weight on model (1X2/OU/AH) | 0.00/0.00/0.00 |




## Ranked selections

Ranking: by **pessimistic EV** (EV computed with the 10th-percentile model probability from
parameter uncertainty), so that thinly estimated edges rank below robust ones.


### 1. Carolina Panthers to win — Carolina Panthers v Baltimore Ravens

| Field | Value |
|---|---|
| Sport / competition | NFL — NFL |
| Kick-off | Sun 22 Nov 13:00 EST |
| Market / selection | ML — **Carolina Panthers to win** |
| Best price | **1.79** @ Marathon Bet |
| Model probability (raw) | 49.1% (±0.0 pp param. sd; p10 49.1%) |
| Market no-vig probability | 57.9% (Betfair Exchange) |
| Final probability (blend) | 57.9% |
| Fair odds | 1.73 |
| Expected value | **+3.7%** (pessimistic +3.7%) |
| Stake (paper) | 1.0 unit |
| Bookmakers quoting | 11 |
| Odds snapshot | Mon 16 Nov 23:32 EST |

**Statistical evidence.** Projected score Carolina Panthers 23.7 – Baltimore Ravens 24.0. Doyen's ratings project Carolina Panthers 23.7 – Baltimore Ravens 24.0 pts (margin -0.3, total 47.7); power ranks 21 and 18 of 32.

**Why it may be value.** The best available price (1.79) exceeds the estimated fair
price (1.73). The edge
comes mainly from the price being out of line with the consensus of other bookmakers.

**Context / research flags.** No contextual research recorded yet (team news is not modelled — check before acting).

**Reasons this could be wrong.**
- Model weight 0.00: the edge is the price versus the multi-bookmaker consensus, not a model opinion.
- Model and market disagree by -8.8%.

Sources: <https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds?regions=eu&markets=h2h,spreads,totals> <https://www.espn.com/football/game/_/gameId/401873068> 


### 2. Under 2 goals — Hungary v Northern Ireland

| Field | Value |
|---|---|
| Sport / competition | Football — UEFA Nations League |
| Kick-off | Tue 17 Nov 14:45 EST |
| Market / selection | OU — **Under 2 goals** |
| Best price | **2.05** @ Pinnacle |
| Model probability (raw) | 63.0% (±13.0 pp param. sd; p10 42.1%) |
| Market no-vig probability | 52.5% (median) |
| Final probability (blend) | 52.5% |
| Fair odds | 1.90 |
| Expected value | **+5.5%** (pessimistic +5.5%) |
| Stake (paper) | 1.0 unit |
| Bookmakers quoting | 3 |
| Odds snapshot | Tue 17 Nov 13:10 EST |

**Statistical evidence.** Expected goals 1.07–0.73.
Recent form — Hungary: WLDWWW (GF 8, GA 3);
Northern Ireland: LWDWDW (GF 6, GA 3).
Model 1X2: 42/34/24%,
O2.5 27%, BTTS 35%.

**Why it may be value.** The best available price (2.05) exceeds the estimated fair
price (1.90). The
model rates this outcome 10.5 pp above the de-vigged consensus.

**Context / research flags.** No contextual research recorded yet (team news is not modelled — check before acting).

**Reasons this could be wrong.**
- International selection: the model has weight 0. The edge is the price versus the sharp de-vigged consensus (validated on club data: +4.5% CLV), not a model opinion.
- Team news (call-ups, withdrawals, rotation) moves international prices sharply and is not modelled.
- Model and market disagree by +10.5%.

Sources: <https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h,totals> <https://www.espn.com/soccer/match/_/gameId/401861191> 




## Closest candidates (transparency)

| Match | Market | Odds | Final p | EV | Pess. EV | Status |
|---|---|---|---|---|---|---|


## International fixtures — model monitoring (not recommendations)

9 national-team matches analysed in the next 48h (model `dc-intl-0.1`,
trained on 50106 internationals; 0 with multi-bookmaker odds).
The model's gaps against bookmakers are **monitoring signals, not selections**: no free historical international
odds exist to validate the model against the market, so it has weight 0. Real (paper) international selections
appear in *Ranked selections* only when The Odds API supplies 3+ bookmakers and a price beats the sharp
de-vigged consensus under the standard rules.

| Kick-off | Competition | Match | Model H/D/A | Book H/D/A (no-vig) | Largest model–book gap |
|---|---|---|---|---|---|
| Tue 17 Nov 18:30 EST | International Friendly | Ecuador v Bolivia | 72/21/7 | 86/10/4 | 1X2 D @ 8.00: model EV +69.2% ⚠ bias |
| Tue 17 Nov 21:30 EST | CONCACAF Nations League | Mexico v Jamaica | 74/18/7 | 88/8/4 | 1X2 D @ 8.50: model EV +56.0% ⚠ bias |
| Tue 17 Nov 19:00 EST | CONCACAF Nations League | French Guiana v Saint Vincent and the Grenadines | 55/24/21 | 35/26/40 | 1X2 H @ 2.65: model EV +45.7% |
| Tue 17 Nov 19:00 EST | CONCACAF Nations League | United States v Haiti | 82/12/7 | 93/5/2 | 1X2 A @ 20.00: model EV +34.9% ⚠ bias |
| Tue 17 Nov 18:00 EST | International Friendly | Chile v Colombia | 21/27/52 | 23/29/48 | 1X2 A @ 2.00: model EV +3.8% |
| Tue 17 Nov 18:30 EST | International Friendly | Uruguay v Dominican Republic | 95/4/1 | 92/5/3 | 1X2 H @ 1.07: model EV +2.2% |
| Tue 17 Nov 18:00 EST | International Friendly | Argentina v Costa Rica | 94/5/1 | 94/4/2 | 1X2 H @ 1.05: model EV -1.7% |
| Tue 17 Nov 20:00 EST | CONCACAF Nations League | El Salvador v Saint Martin | 64/23/14 | — |  |
| Tue 17 Nov 22:00 EST | CONCACAF Nations League | Nicaragua v Montserrat | 67/21/12 | — |  |

⚠ bias = the model is backing an underdog against a heavy bookmaker favourite (>70%). Out of sample the model
is underconfident on heavy favourites, so these gaps are most likely model error, not value.




## Track record (paper, fixed 1-unit stakes)

Settled 12 · W 3 / L 9 / P 0 ·
profit -6.83u · yield -56.9%
(95% CI -100.0% to -12.8%) ·
avg CLV +2.2% · max drawdown 8.2u.
*Only 12 settled selections. Yield CIs are wide; at typical odds, several hundred to a few thousand bets are needed before ROI distinguishes skill from luck. CLV is the faster, more reliable early indicator.*