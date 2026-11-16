# Sports Betting Doyen — Daily Report, 2026-11-16

*Research and paper-trading only. Not financial advice. No bets are placed automatically.
All times America/New_York. Generated Mon 16 Nov 16:38 EST. Model `dc-0.1`.*

## Daily overview

| Item | Value |
|---|---|
| Period | next 7 days (rolling 168h, same as the website "This Week") |
| Events discovered | 171 |
| Events with fresh odds | 59 |
| Events fully evaluated (3+ independent bookmakers, complete history) | 22 |
| Markets evaluated | 422 |
| Events passing all rules | 1 |
| Published today | **1** |
| Highest estimated EV | +5.8% |
| Blend weight on model (1X2/OU/AH) | 0.00/0.00/0.00 |




## Ranked selections

Ranking: by **pessimistic EV** (EV computed with the 10th-percentile model probability from
parameter uncertainty), so that thinly estimated edges rank below robust ones.


### 1. New Orleans Saints to win — Chicago Bears v New Orleans Saints

| Field | Value |
|---|---|
| Sport / competition | NFL — NFL |
| Kick-off | Sun 22 Nov 13:00 EST |
| Market / selection | ML — **New Orleans Saints to win** |
| Best price | **5.90** @ DraftKings |
| Model probability (raw) | 25.4% (±0.0 pp param. sd; p10 25.4%) |
| Market no-vig probability | 17.9% (Pinnacle) |
| Final probability (blend) | 17.9% |
| Fair odds | 5.58 |
| Expected value | **+5.8%** (pessimistic +5.8%) |
| Stake (paper) | 1.0 unit |
| Bookmakers quoting | 12 |
| Odds snapshot | Mon 16 Nov 16:40 EST |

**Statistical evidence.** Projected score Chicago Bears 27.9 – New Orleans Saints 20.3. Doyen's ratings project Chicago Bears 27.9 – New Orleans Saints 20.3 pts (margin +7.6, total 48.1); power ranks 10 and 25 of 32.

**Why it may be value.** The best available price (5.90) exceeds the estimated fair
price (5.58). The
model rates this outcome 7.4 pp above the de-vigged consensus.

**Context / research flags.** No contextual research recorded yet (team news is not modelled — check before acting).

**Reasons this could be wrong.**
- Model weight 0.00: the edge is the price versus the multi-bookmaker consensus, not a model opinion.
- Model and market disagree by +7.4%.

Sources: <https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds?regions=eu&markets=h2h,spreads,totals> <https://www.espn.com/football/game/_/gameId/401873071> 




## Closest candidates (transparency)

| Match | Market | Odds | Final p | EV | Pess. EV | Status |
|---|---|---|---|---|---|---|


## International fixtures — model monitoring (not recommendations)

56 national-team matches analysed in the next 48h (model `dc-intl-0.1`,
trained on 50058 internationals; 8 with multi-bookmaker odds).
The model's gaps against bookmakers are **monitoring signals, not selections**: no free historical international
odds exist to validate the model against the market, so it has weight 0. Real (paper) international selections
appear in *Ranked selections* only when The Odds API supplies 3+ bookmakers and a price beats the sharp
de-vigged consensus under the standard rules.

| Kick-off | Competition | Match | Model H/D/A | Book H/D/A (no-vig) | Largest model–book gap |
|---|---|---|---|---|---|
| Tue 17 Nov 11:00 EST | AFCON Qualifying | Guinea-Bissau v Madagascar | 38/29/33 | 69/21/10 | 1X2 A @ 8.00: model EV +164.6% |
| Tue 17 Nov 07:00 EST | International Friendly | China v Bahrain (N) | 28/32/40 | 50/28/23 | 1X2 A @ 4.10: model EV +62.8% |
| Tue 17 Nov 14:00 EST | CONCACAF Nations League | Dominica v Cayman Islands (N) | 43/34/23 | 67/19/14 | 1X2 D @ 4.40: model EV +49.1% |
| Tue 17 Nov 11:30 EST | International Friendly | Kuwait v Honduras | 34/27/38 | 23/27/50 | 1X2 H @ 4.10: model EV +39.7% |
| Tue 17 Nov 18:30 EST | International Friendly | Ecuador v Bolivia | 72/21/7 | 82/12/6 | 1X2 D @ 6.50: model EV +36.9% ⚠ bias |
| Tue 17 Nov 19:00 EST | CONCACAF Nations League | United States v Haiti | 82/11/7 | 94/4/3 | 1X2 D @ 12.00: model EV +36.4% ⚠ bias |
| Tue 17 Nov 14:00 EST | CONCACAF Nations League | Saint Lucia v Barbados (N) | 44/25/31 | 58/22/21 | 1X2 A @ 4.20: model EV +29.4% |
| Tue 17 Nov 21:30 EST | CONCACAF Nations League | Mexico v Jamaica | 74/18/7 | 85/10/5 | 1X2 D @ 7.00: model EV +28.4% ⚠ bias |
| Tue 17 Nov 08:10 EST | International Friendly | Japan v Paraguay (N) | 45/33/21 | 58/24/18 | 1X2 D @ 3.85: model EV +27.8% |
| Tue 17 Nov 09:10 EST | International Friendly | United Arab Emirates v Syria | 62/23/15 | 71/19/10 | 1X2 A @ 8.50: model EV +26.2% ⚠ bias |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Bosnia and Herzegovina v Romania | 42/28/29 | 52/25/23 | 1X2 A @ 4.24: model EV +23.8% |
| Tue 17 Nov 08:00 EST | AFCON Qualifying | Burundi v Zambia | 35/28/37 | 43/30/27 | 1X2 A @ 3.30: model EV +22.4% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Hungary v Northern Ireland | 42/34/24 | 50/29/22 | 1X2 D @ 3.48: model EV +17.9% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Wales v Portugal | 14/23/63 | 13/19/68 | 1X2 D @ 5.12: model EV +17.6% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Denmark v Norway | 47/24/29 | 40/25/35 | 1X2 H @ 2.48: model EV +17.3% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Poland v Sweden | 41/24/35 | 43/26/31 | 1X2 A @ 3.20: model EV +12.5% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Republic of Ireland v Kosovo | 38/34/28 | 46/30/24 | 1X2 A @ 3.95: model EV +10.5% |
| Tue 17 Nov 18:00 EST | International Friendly | Chile v Colombia | 21/27/52 | 26/29/45 | 1X2 A @ 2.10: model EV +9.4% |
| Tue 17 Nov 10:30 EST | International Friendly | Saudi Arabia v Uzbekistan (N) | 31/33/36 | 39/29/32 | 1X2 D @ 3.25: model EV +8.0% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Israel v Austria (N) | 18/23/60 | 21/25/54 | 1X2 A @ 1.85: model EV +7.7% |
| Tue 17 Nov 07:00 EST | International Friendly | Kyrgyzstan v Vietnam (N) | 32/31/37 | 39/27/34 | 1X2 D @ 3.45: model EV +6.9% |
| Tue 17 Nov 08:00 EST | AFCON Qualifying | Ethiopia v Mozambique | 34/30/36 | 32/38/31 | 1X2 A @ 2.95: model EV +6.4% |
| Tue 17 Nov 08:00 EST | AFCON Qualifying | South Sudan v Angola | 8/23/69 | 6/17/77 | 1X2 D @ 4.70: model EV +6.2% ⚠ bias |
| Tue 17 Nov 08:00 EST | AFCON Qualifying | Malawi v Egypt | 7/19/74 | 6/14/81 | 1X2 D @ 5.50: model EV +5.4% ⚠ bias |
| Tue 17 Nov 09:00 EST | International Friendly | Qatar v South Korea | 16/22/62 | 14/21/66 | 1X2 H @ 6.50: model EV +5.1% |
| Tue 17 Nov 11:00 EST | International Friendly | Jordan v Australia (N) | 16/26/58 | 22/25/53 | 1X2 A @ 1.80: model EV +4.6% |
| Tue 17 Nov 18:30 EST | International Friendly | Uruguay v Dominican Republic | 96/4/1 | 91/6/3 | 1X2 H @ 1.08: model EV +3.5% |
| Tue 17 Nov 05:00 EST | International Friendly | Singapore v Brazil | 0/0/100 | 1/2/97 | 1X2 A @ 1.02: model EV +1.7% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Ukraine v Georgia (N) | 43/30/28 | 44/29/27 | 1X2 D @ 3.42: model EV +1.7% |
| Tue 17 Nov 18:00 EST | International Friendly | Argentina v Costa Rica | 94/5/1 | 91/6/3 | 1X2 H @ 1.08: model EV +1.4% |
| Tue 17 Nov 14:00 EST | CONCACAF Nations League | Belize v Sint Maarten | 54/25/21 | 50/25/25 | 1X2 H @ 1.87: model EV +0.8% |
| Tue 17 Nov 08:00 EST | AFCON Qualifying | Lesotho v Gabon (N) | 14/27/59 | 11/22/66 | 1X2 D @ 3.80: model EV +0.8% |
| Tue 17 Nov 11:00 EST | AFCON Qualifying | Gambia v Ivory Coast | 17/23/61 | 15/27/58 | 1X2 A @ 1.65: model EV -0.1% |
| Tue 17 Nov 08:00 EST | AFCON Qualifying | Tanzania v Nigeria | 13/24/63 | 10/20/69 | 1X2 D @ 4.10: model EV -0.5% |
| Tue 17 Nov 11:00 EST | AFCON Qualifying | Kenya v South Africa | 17/27/55 | 18/29/53 | 1X2 A @ 1.77: model EV -2.5% |
| Mon 16 Nov 20:00 EST | CONCACAF Nations League | Canada v Guatemala | 81/14/6 | 83/11/6 | 1X2 H @ 1.17: model EV -5.1% |
| Mon 16 Nov 19:00 EST | CONCACAF Nations League | Martinique v Aruba | 70/19/11 | — |  |
| Mon 16 Nov 19:00 EST | CONCACAF Nations League | Trinidad and Tobago v Antigua and Barbuda | 87/10/3 | — |  |
| Tue 17 Nov 00:30 EST | International Friendly | Tahiti v Cook Islands | 93/6/2 | — |  |
| Tue 17 Nov 01:00 EST | International Friendly | Malaysia v Yemen (N) | 43/26/31 | — |  |

⚠ bias = the model is backing an underdog against a heavy bookmaker favourite (>70%). Out of sample the model
is underconfident on heavy favourites, so these gaps are most likely model error, not value.




## Track record (paper, fixed 1-unit stakes)

Settled 6 · W 1 / L 5 / P 0 ·
profit -4.20u · yield -70.0%
(95% CI -100.0% to -10.0%) ·
avg CLV +2.0% · max drawdown 4.2u.
*Only 6 settled selections. Yield CIs are wide; at typical odds, several hundred to a few thousand bets are needed before ROI distinguishes skill from luck. CLV is the faster, more reliable early indicator.*