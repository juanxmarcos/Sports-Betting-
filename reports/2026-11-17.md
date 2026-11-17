# Sports Betting Doyen — Daily Report, 2026-11-17

*Research and paper-trading only. Not financial advice. No bets are placed automatically.
All times America/New_York. Generated Tue 17 Nov 11:05 EST. Model `dc-0.1`.*

## Daily overview

| Item | Value |
|---|---|
| Period | next 7 days (rolling 168h, same as the website "This Week") |
| Events discovered | 141 |
| Events with fresh odds | 42 |
| Events fully evaluated (3+ independent bookmakers, complete history) | 29 |
| Markets evaluated | 433 |
| Events passing all rules | 0 |
| Published today | **1** |
| Highest estimated EV | +3.7% |
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




## Closest candidates (transparency)

| Match | Market | Odds | Final p | EV | Pess. EV | Status |
|---|---|---|---|---|---|---|


## International fixtures — model monitoring (not recommendations)

29 national-team matches analysed in the next 48h (model `dc-intl-0.1`,
trained on 50077 internationals; 8 with multi-bookmaker odds).
The model's gaps against bookmakers are **monitoring signals, not selections**: no free historical international
odds exist to validate the model against the market, so it has weight 0. Real (paper) international selections
appear in *Ranked selections* only when The Odds API supplies 3+ bookmakers and a price beats the sharp
de-vigged consensus under the standard rules.

| Kick-off | Competition | Match | Model H/D/A | Book H/D/A (no-vig) | Largest model–book gap |
|---|---|---|---|---|---|
| Tue 17 Nov 14:00 EST | CONCACAF Nations League | Dominica v Cayman Islands (N) | 43/34/23 | 72/17/11 | 1X2 A @ 7.50: model EV +75.6% ⚠ bias |
| Tue 17 Nov 21:30 EST | CONCACAF Nations League | Mexico v Jamaica | 74/18/7 | 88/8/4 | 1X2 D @ 8.50: model EV +55.5% ⚠ bias |
| Tue 17 Nov 19:00 EST | CONCACAF Nations League | French Guiana v Saint Vincent and the Grenadines | 55/24/21 | 34/26/41 | 1X2 H @ 2.75: model EV +51.5% |
| Tue 17 Nov 18:30 EST | International Friendly | Ecuador v Bolivia | 72/21/7 | 83/12/5 | 1X2 D @ 7.00: model EV +47.9% ⚠ bias |
| Tue 17 Nov 11:30 EST | International Friendly | Kuwait v Honduras | 34/27/39 | 22/26/52 | 1X2 H @ 4.10: model EV +38.9% |
| Tue 17 Nov 19:00 EST | CONCACAF Nations League | United States v Haiti | 82/11/7 | 93/4/2 | 1X2 D @ 12.00: model EV +36.8% ⚠ bias |
| Tue 17 Nov 14:00 EST | CONCACAF Nations League | Saint Lucia v Barbados (N) | 44/25/31 | 57/22/21 | 1X2 A @ 4.20: model EV +30.1% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Republic of Ireland v Kosovo | 38/34/28 | 49/29/22 | 1X2 A @ 4.43: model EV +24.2% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Wales v Portugal | 14/23/63 | 13/18/69 | 1X2 D @ 5.40: model EV +24.2% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Denmark v Norway | 47/24/29 | 37/23/40 | 1X2 H @ 2.60: model EV +22.8% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Hungary v Northern Ireland | 42/34/24 | 51/29/20 | 1X2 D @ 3.40: model EV +15.3% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Poland v Sweden | 41/24/35 | 44/24/31 | 1X2 A @ 3.25: model EV +14.7% |
| Tue 17 Nov 14:00 EST | CONCACAF Nations League | Saint Kitts and Nevis v Bonaire (N) | 56/22/22 | 48/20/32 | 1X2 H @ 1.95: model EV +9.1% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Israel v Austria (N) | 18/23/60 | 23/24/53 | 1X2 A @ 1.83: model EV +9.0% |
| Tue 17 Nov 11:15 EST | International Friendly | Iraq v Iran | 18/26/56 | 22/29/49 | 1X2 A @ 1.95: model EV +8.7% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Ukraine v Georgia (N) | 43/30/28 | 46/29/25 | 1X2 A @ 3.89: model EV +7.2% |
| Tue 17 Nov 18:00 EST | International Friendly | Chile v Colombia | 21/27/52 | 24/29/47 | 1X2 A @ 2.05: model EV +6.8% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Bosnia and Herzegovina v Romania | 42/28/29 | 45/26/29 | 1X2 D @ 3.74: model EV +6.1% |
| Tue 17 Nov 18:30 EST | International Friendly | Uruguay v Dominican Republic | 96/4/1 | 91/6/3 | 1X2 H @ 1.08: model EV +3.5% |
| Tue 17 Nov 14:00 EST | CONCACAF Nations League | Belize v Sint Maarten | 54/25/21 | 51/25/24 | 1X2 H @ 1.87: model EV +0.5% |
| Tue 17 Nov 18:00 EST | International Friendly | Argentina v Costa Rica | 94/5/1 | 92/6/2 | 1X2 H @ 1.07: model EV +0.3% |
| Tue 17 Nov 14:00 EST | AFCON Qualifying | Botswana v Uganda | 30/31/40 | — |  |
| Tue 17 Nov 14:00 EST | AFCON Qualifying | Congo v Comoros | 24/30/45 | — |  |
| Tue 17 Nov 14:00 EST | AFCON Qualifying | Liberia v Cape Verde | 17/24/58 | — |  |
| Tue 17 Nov 14:00 EST | AFCON Qualifying | Mauritania v Burkina Faso | 24/30/46 | — |  |
| Tue 17 Nov 14:00 EST | AFCON Qualifying | Rwanda v Mali | 19/34/47 | — |  |
| Tue 17 Nov 15:00 EST | AFCON Qualifying | Niger v Morocco (N) | 4/14/82 | — |  |
| Tue 17 Nov 20:00 EST | CONCACAF Nations League | El Salvador v Saint Martin | 64/22/14 | — |  |
| Tue 17 Nov 22:00 EST | CONCACAF Nations League | Nicaragua v Montserrat | 66/21/12 | — |  |

⚠ bias = the model is backing an underdog against a heavy bookmaker favourite (>70%). Out of sample the model
is underconfident on heavy favourites, so these gaps are most likely model error, not value.




## Track record (paper, fixed 1-unit stakes)

Settled 12 · W 3 / L 9 / P 0 ·
profit -6.83u · yield -56.9%
(95% CI -100.0% to -12.8%) ·
avg CLV +2.2% · max drawdown 8.2u.
*Only 12 settled selections. Yield CIs are wide; at typical odds, several hundred to a few thousand bets are needed before ROI distinguishes skill from luck. CLV is the faster, more reliable early indicator.*