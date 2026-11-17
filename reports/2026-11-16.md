# Sports Betting Doyen — Daily Report, 2026-11-16

*Research and paper-trading only. Not financial advice. No bets are placed automatically.
All times America/New_York. Generated Mon 16 Nov 23:31 EST. Model `dc-0.1`.*

## Daily overview

| Item | Value |
|---|---|
| Period | next 7 days (rolling 168h, same as the website "This Week") |
| Events discovered | 169 |
| Events with fresh odds | 57 |
| Events fully evaluated (3+ independent bookmakers, complete history) | 30 |
| Markets evaluated | 468 |
| Events passing all rules | 3 |
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

53 national-team matches analysed in the next 48h (model `dc-intl-0.1`,
trained on 50062 internationals; 8 with multi-bookmaker odds).
The model's gaps against bookmakers are **monitoring signals, not selections**: no free historical international
odds exist to validate the model against the market, so it has weight 0. Real (paper) international selections
appear in *Ranked selections* only when The Odds API supplies 3+ bookmakers and a price beats the sharp
de-vigged consensus under the standard rules.

| Kick-off | Competition | Match | Model H/D/A | Book H/D/A (no-vig) | Largest model–book gap |
|---|---|---|---|---|---|
| Tue 17 Nov 11:00 EST | AFCON Qualifying | Guinea-Bissau v Madagascar | 38/29/33 | 69/21/10 | 1X2 A @ 8.00: model EV +164.5% |
| Tue 17 Nov 07:00 EST | International Friendly | China v Bahrain (N) | 28/32/40 | 52/27/21 | 1X2 A @ 4.30: model EV +70.6% |
| Tue 17 Nov 14:00 EST | CONCACAF Nations League | Dominica v Cayman Islands (N) | 43/34/23 | 71/18/11 | 1X2 A @ 7.00: model EV +63.8% ⚠ bias |
| Tue 17 Nov 18:30 EST | International Friendly | Ecuador v Bolivia | 72/21/7 | 82/12/6 | 1X2 D @ 7.00: model EV +47.6% ⚠ bias |
| Tue 17 Nov 21:30 EST | CONCACAF Nations League | Mexico v Jamaica | 74/18/7 | 87/9/5 | 1X2 D @ 7.50: model EV +37.6% ⚠ bias |
| Tue 17 Nov 19:00 EST | CONCACAF Nations League | United States v Haiti | 82/11/7 | 94/4/2 | 1X2 D @ 12.00: model EV +37.0% ⚠ bias |
| Tue 17 Nov 11:30 EST | International Friendly | Kuwait v Honduras | 34/27/39 | 24/27/49 | 1X2 H @ 3.95: model EV +34.3% |
| Tue 17 Nov 14:00 EST | CONCACAF Nations League | Saint Lucia v Barbados (N) | 44/25/31 | 58/22/21 | 1X2 A @ 4.20: model EV +30.1% |
| Tue 17 Nov 08:10 EST | International Friendly | Japan v Paraguay (N) | 45/33/21 | 59/23/18 | 1X2 D @ 3.90: model EV +29.5% |
| Tue 17 Nov 09:10 EST | International Friendly | United Arab Emirates v Syria | 62/23/15 | 71/19/10 | 1X2 A @ 8.50: model EV +26.1% ⚠ bias |
| Tue 17 Nov 08:00 EST | AFCON Qualifying | Burundi v Zambia | 35/28/37 | 43/30/27 | 1X2 A @ 3.35: model EV +24.2% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Bosnia and Herzegovina v Romania | 42/28/29 | 47/26/27 | 1X2 A @ 4.20: model EV +22.5% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Wales v Portugal | 14/23/63 | 13/18/69 | 1X2 D @ 5.50: model EV +21.4% |
| Tue 17 Nov 08:00 EST | AFCON Qualifying | Malawi v Egypt | 7/19/74 | 4/12/84 | 1X2 D @ 6.00: model EV +15.1% ⚠ bias |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Hungary v Northern Ireland | 42/34/24 | 48/29/23 | 1X2 D @ 3.38: model EV +14.6% |
| Tue 17 Nov 08:00 EST | AFCON Qualifying | South Sudan v Angola | 8/23/69 | 6/16/78 | 1X2 D @ 5.00: model EV +13.1% ⚠ bias |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Denmark v Norway | 47/24/29 | 41/23/36 | 1X2 H @ 2.38: model EV +12.4% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Republic of Ireland v Kosovo | 38/34/28 | 46/30/24 | 1X2 A @ 4.00: model EV +12.2% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Israel v Austria (N) | 18/23/60 | 23/25/52 | 1X2 A @ 1.90: model EV +10.5% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Poland v Sweden | 41/24/35 | 43/26/31 | 1X2 A @ 3.12: model EV +10.1% |
| Tue 17 Nov 18:00 EST | International Friendly | Chile v Colombia | 21/27/52 | 26/29/46 | 1X2 A @ 2.10: model EV +9.4% |
| Tue 17 Nov 10:30 EST | International Friendly | Saudi Arabia v Uzbekistan (N) | 31/33/36 | 39/29/32 | 1X2 D @ 3.25: model EV +8.1% |
| Tue 17 Nov 07:00 EST | International Friendly | Kyrgyzstan v Vietnam (N) | 32/31/37 | 40/27/34 | 1X2 D @ 3.45: model EV +7.0% |
| Tue 17 Nov 09:00 EST | International Friendly | Qatar v South Korea | 16/22/62 | 13/20/67 | 1X2 H @ 6.50: model EV +5.5% |
| Tue 17 Nov 11:00 EST | International Friendly | Jordan v Australia (N) | 16/26/58 | 22/25/53 | 1X2 A @ 1.80: model EV +4.5% |
| Tue 17 Nov 08:00 EST | AFCON Qualifying | Ethiopia v Mozambique | 33/30/36 | 32/36/32 | 1X2 A @ 2.90: model EV +4.5% |
| Tue 17 Nov 08:00 EST | AFCON Qualifying | Tanzania v Nigeria | 13/24/63 | 10/20/71 | 1X2 D @ 4.30: model EV +4.5% ⚠ bias |
| Tue 17 Nov 18:30 EST | International Friendly | Uruguay v Dominican Republic | 96/4/1 | 91/6/4 | 1X2 H @ 1.09: model EV +4.2% |
| Tue 17 Nov 08:00 EST | AFCON Qualifying | Lesotho v Gabon (N) | 14/27/59 | 12/22/66 | 1X2 D @ 3.85: model EV +2.2% |
| Tue 17 Nov 18:00 EST | International Friendly | Argentina v Costa Rica | 94/5/1 | 91/6/3 | 1X2 H @ 1.09: model EV +2.1% |
| Tue 17 Nov 11:00 EST | AFCON Qualifying | Gambia v Ivory Coast | 17/23/61 | 16/27/57 | 1X2 A @ 1.67: model EV +1.1% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Ukraine v Georgia (N) | 43/30/28 | 45/29/26 | 1X2 A @ 3.66: model EV +0.9% |
| Tue 17 Nov 14:00 EST | CONCACAF Nations League | Belize v Sint Maarten | 54/25/21 | 50/25/25 | 1X2 H @ 1.87: model EV +0.5% |
| Tue 17 Nov 11:00 EST | AFCON Qualifying | Kenya v South Africa | 17/27/55 | 17/28/54 | 1X2 A @ 1.74: model EV -4.0% |
| Tue 17 Nov 00:30 EST | International Friendly | Tahiti v Cook Islands | 93/6/2 | — |  |
| Tue 17 Nov 01:00 EST | International Friendly | Malaysia v Yemen (N) | 43/26/31 | — |  |
| Tue 17 Nov 05:00 EST | International Friendly | Singapore v Brazil | 0/0/100 | — |  |
| Tue 17 Nov 08:00 EST | International Friendly | Lebanon v Palestine (N) | 21/33/46 | — |  |
| Tue 17 Nov 11:00 EST | International Friendly | Russia v Venezuela | 50/28/21 | — |  |
| Tue 17 Nov 11:00 EST | AFCON Qualifying | Libya v Tunisia | 29/32/39 | — |  |

⚠ bias = the model is backing an underdog against a heavy bookmaker favourite (>70%). Out of sample the model
is underconfident on heavy favourites, so these gaps are most likely model error, not value.




## Track record (paper, fixed 1-unit stakes)

Settled 11 · W 3 / L 8 / P 0 ·
profit -5.83u · yield -53.0%
(95% CI -100.0% to -5.0%) ·
avg CLV +1.2% · max drawdown 7.2u.
*Only 11 settled selections. Yield CIs are wide; at typical odds, several hundred to a few thousand bets are needed before ROI distinguishes skill from luck. CLV is the faster, more reliable early indicator.*