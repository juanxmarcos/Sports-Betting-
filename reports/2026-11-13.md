# Sports Betting Doyen — Daily Report, 2026-11-13

*Research and paper-trading only. Not financial advice. No bets are placed automatically.
All times America/New_York. Generated Fri 13 Nov 07:15 EST. Model `dc-0.1`.*

## Daily overview

| Item | Value |
|---|---|
| Period | next 7 days (rolling 168h, same as the website "This Week") |
| Events discovered | 263 |
| Events with fresh odds | 86 |
| Events fully evaluated (3+ independent bookmakers, complete history) | 55 |
| Markets evaluated | 651 |
| Events passing all rules | 2 |
| Published today | **2** |
| Highest estimated EV | +5.1% |
| Blend weight on model (1X2/OU/AH) | 0.00/0.00/0.00 |




## Ranked selections

Ranking: by **pessimistic EV** (EV computed with the 10th-percentile model probability from
parameter uncertainty), so that thinly estimated edges rank below robust ones.


### 1. Draw — Germany v Netherlands

| Field | Value |
|---|---|
| Sport / competition | Football — UEFA Nations League |
| Kick-off | Mon 16 Nov 14:45 EST |
| Market / selection | 1X2 — **Draw** |
| Best price | **4.12** @ 1xBet |
| Model probability (raw) | 23.3% (±2.5 pp param. sd; p10 19.2%) |
| Market no-vig probability | 25.5% (Betfair Exchange) |
| Final probability (blend) | 25.5% |
| Fair odds | 3.92 |
| Expected value | **+5.1%** (pessimistic +5.1%) |
| Stake (paper) | 1.0 unit |
| Bookmakers quoting | 7 |
| Odds snapshot | Fri 13 Nov 07:16 EST |

**Statistical evidence.** Expected goals 1.94–1.55.
Recent form — Germany: LDDLWD (GF 5, GA 5);
Netherlands: WDDWDW (GF 11, GA 7).
Model 1X2: 46/23/31%,
O2.5 68%, BTTS 68%.

**Why it may be value.** The best available price (4.12) exceeds the estimated fair
price (3.92). The edge
comes mainly from the price being out of line with the consensus of other bookmakers.

**Context / research flags.** No contextual research recorded yet (team news is not modelled — check before acting).

**Reasons this could be wrong.**
- International selection: the model has weight 0. The edge is the price versus the sharp de-vigged consensus (validated on club data: +4.5% CLV), not a model opinion.
- Team news (call-ups, withdrawals, rotation) moves international prices sharply and is not modelled.

Sources: <https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h,totals> <https://www.espn.com/soccer/match/_/gameId/401861185> 


### 2. Draw — Denmark v Norway

| Field | Value |
|---|---|
| Sport / competition | Football — UEFA Nations League |
| Kick-off | Tue 17 Nov 14:45 EST |
| Market / selection | 1X2 — **Draw** |
| Best price | **3.92** @ 1xBet |
| Model probability (raw) | 24.2% (±2.7 pp param. sd; p10 19.3%) |
| Market no-vig probability | 26.7% (Betfair Exchange) |
| Final probability (blend) | 26.7% |
| Fair odds | 3.74 |
| Expected value | **+4.7%** (pessimistic +4.7%) |
| Stake (paper) | 1.0 unit |
| Bookmakers quoting | 7 |
| Odds snapshot | Fri 13 Nov 07:16 EST |

**Statistical evidence.** Expected goals 1.82–1.48.
Recent form — Denmark: DWLWLW (GF 9, GA 8);
Norway: WLWLLL (GF 9, GA 11).
Model 1X2: 45/24/31%,
O2.5 64%, BTTS 65%.

**Why it may be value.** The best available price (3.92) exceeds the estimated fair
price (3.74). The edge
comes mainly from the price being out of line with the consensus of other bookmakers.

**Context / research flags.** No contextual research recorded yet (team news is not modelled — check before acting).

**Reasons this could be wrong.**
- International selection: the model has weight 0. The edge is the price versus the sharp de-vigged consensus (validated on club data: +4.5% CLV), not a model opinion.
- Team news (call-ups, withdrawals, rotation) moves international prices sharply and is not modelled.

Sources: <https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h,totals> <https://www.espn.com/soccer/match/_/gameId/401861194> 




## Closest candidates (transparency)

| Match | Market | Odds | Final p | EV | Pess. EV | Status |
|---|---|---|---|---|---|---|


## International fixtures — model monitoring (not recommendations)

146 national-team matches analysed in the next 48h (model `dc-intl-0.1`,
trained on 49969 internationals; 26 with multi-bookmaker odds).
The model's gaps against bookmakers are **monitoring signals, not selections**: no free historical international
odds exist to validate the model against the market, so it has weight 0. Real (paper) international selections
appear in *Ranked selections* only when The Odds API supplies 3+ bookmakers and a price beats the sharp
de-vigged consensus under the standard rules.

| Kick-off | Competition | Match | Model H/D/A | Book H/D/A (no-vig) | Largest model–book gap |
|---|---|---|---|---|---|
| Fri 13 Nov 14:00 EST | CONCACAF Nations League | Bermuda v Saint Lucia (N) | 45/23/32 | 7/11/82 | 1X2 H @ 10.00: model EV +352.8% ⚠ bias |
| Fri 13 Nov 14:45 EST | UEFA Nations League | Scotland v North Macedonia | 66/22/12 | 83/13/5 | 1X2 A @ 20.00: model EV +130.8% ⚠ bias |
| Fri 13 Nov 14:45 EST | UEFA Nations League | Serbia v Germany | 18/22/59 | 8/14/77 | 1X2 H @ 11.50: model EV +110.6% ⚠ bias |
| Fri 13 Nov 14:45 EST | UEFA Nations League | Andorra v Gibraltar | 34/42/24 | 58/29/13 | 1X2 A @ 7.80: model EV +76.5% |
| Sat 14 Nov 12:00 EST | UEFA Nations League | Norway v Wales | 68/20/12 | 79/13/8 | 1X2 A @ 13.00: model EV +60.6% ⚠ bias |
| Fri 13 Nov 15:00 EST | CONCACAF Nations League | Grenada v Saint Kitts and Nevis (N) | 35/26/39 | 19/21/60 | 1X2 H @ 4.60: model EV +60.2% |
| Fri 13 Nov 14:45 EST | UEFA Nations League | Liechtenstein v Azerbaijan | 6/24/69 | 4/15/81 | 1X2 H @ 27.00: model EV +56.0% ⚠ bias |
| Fri 13 Nov 11:00 EST | AFCON Qualifying | Tunisia v Libya | 57/26/16 | 71/20/8 | 1X2 A @ 9.50: model EV +53.0% ⚠ bias |
| Fri 13 Nov 14:00 EST | AFCON Qualifying | Mali v Rwanda | 56/32/12 | 75/17/8 | 1X2 D @ 4.70: model EV +49.6% ⚠ bias |
| Mon 16 Nov 14:45 EST | UEFA Nations League | Greece v Serbia | 54/28/18 | 71/18/11 | 1X2 A @ 7.50: model EV +37.6% ⚠ bias |
| Fri 13 Nov 11:00 EST | AFCON Qualifying | Cape Verde v Liberia | 69/21/11 | 79/16/6 | 1X2 A @ 13.00: model EV +36.8% ⚠ bias |
| Fri 13 Nov 14:00 EST | CONCACAF Nations League | Puerto Rico v Dominica (N) | 71/21/8 | 82/11/7 | 1X2 D @ 6.50: model EV +36.3% ⚠ bias |
| Fri 13 Nov 14:45 EST | UEFA Nations League | Slovenia v Switzerland | 21/29/50 | 15/28/57 | 1X2 H @ 6.32: model EV +35.4% |
| Fri 13 Nov 19:00 EST | International Friendly | Ecuador v Costa Rica | 69/22/9 | 78/14/7 | 1X2 D @ 6.00: model EV +33.2% ⚠ bias |
| Fri 13 Nov 14:00 EST | AFCON Qualifying | Egypt v Malawi | 79/17/5 | 90/8/2 | 1X2 D @ 8.00: model EV +32.2% ⚠ bias |
| Fri 13 Nov 12:00 EST | UEFA Nations League | Moldova v Kazakhstan | 29/28/43 | 37/32/31 | 1X2 A @ 3.15: model EV +29.4% |
| Fri 13 Nov 11:00 EST | AFCON Qualifying | Gabon v Lesotho | 66/22/12 | 79/15/6 | 1X2 A @ 11.00: model EV +27.8% ⚠ bias |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Wales v Portugal | 13/23/65 | 15/17/67 | 1X2 D @ 5.59: model EV +26.7% |
| Sun 15 Nov 14:45 EST | UEFA Nations League | Croatia v Czech Republic | 59/22/19 | 65/22/14 | 1X2 A @ 6.80: model EV +25.9% |
| Fri 13 Nov 14:45 EST | UEFA Nations League | Bulgaria v Iceland | 25/25/50 | 19/26/56 | 1X2 H @ 5.11: model EV +25.8% |
| Fri 13 Nov 09:45 EST | International Friendly | Qatar v Australia | 13/23/64 | 24/27/49 | 1X2 A @ 1.95: model EV +24.6% |
| Sat 14 Nov 14:45 EST | UEFA Nations League | Portugal v Denmark | 58/23/18 | 64/20/15 | 1X2 A @ 6.75: model EV +23.1% |
| Fri 13 Nov 14:45 EST | UEFA Nations League | Slovakia v Faroe Islands | 65/23/11 | 72/19/9 | 1X2 A @ 11.50: model EV +21.6% ⚠ bias |
| Sat 14 Nov 14:45 EST | UEFA Nations League | Romania v Poland | 29/27/44 | 24/24/52 | 1X2 H @ 4.10: model EV +20.1% |
| Fri 13 Nov 08:00 EST | AFCON Qualifying | Mozambique v Ethiopia | 54/26/20 | 61/25/14 | 1X2 A @ 6.00: model EV +18.6% |
| Fri 13 Nov 08:00 EST | AFCON Qualifying | Zambia v Burundi | 53/25/22 | 58/25/17 | 1X2 A @ 5.25: model EV +16.4% |
| Fri 13 Nov 09:10 EST | International Friendly | United Arab Emirates v Honduras | 55/27/18 | 46/28/26 | 1X2 H @ 2.10: model EV +15.9% |
| Fri 13 Nov 10:00 EST | International Friendly | Iraq v Lebanon | 60/26/13 | 70/20/10 | 1X2 D @ 4.40: model EV +15.7% |
| Sun 15 Nov 14:45 EST | UEFA Nations League | France v Turkey | 76/15/9 | 80/13/8 | 1X2 A @ 12.50: model EV +15.5% ⚠ bias |
| Fri 13 Nov 09:30 EST | International Friendly | Saudi Arabia v South Korea (N) | 21/32/47 | 19/25/55 | 1X2 D @ 3.60: model EV +15.2% |
| Fri 13 Nov 14:45 EST | UEFA Nations League | Netherlands v Greece | 56/25/19 | 62/21/17 | 1X2 D @ 4.60: model EV +14.7% |
| Sat 14 Nov 11:00 EST | AFCON Qualifying | Uganda v Botswana | 53/28/19 | 62/25/13 | 1X2 A @ 6.00: model EV +14.6% |
| Sat 14 Nov 14:45 EST | UEFA Nations League | Austria v Republic of Ireland | 55/27/18 | 60/24/16 | 1X2 D @ 4.25: model EV +14.3% |
| Fri 13 Nov 11:00 EST | AFCON Qualifying | Nigeria v Tanzania | 74/19/7 | 82/13/5 | 1X2 D @ 6.00: model EV +14.1% ⚠ bias |
| Fri 13 Nov 20:00 EST | International Friendly | Peru v Bolivia | 53/28/19 | 62/23/15 | 1X2 D @ 4.00: model EV +13.8% |
| Mon 16 Nov 14:45 EST | UEFA Nations League | Germany v Netherlands | 46/23/31 | 51/26/23 | 1X2 A @ 3.70: model EV +13.3% |
| Fri 13 Nov 11:00 EST | AFCON Qualifying | South Africa v Kenya | 69/22/9 | 78/16/6 | 1X2 D @ 5.25: model EV +12.9% ⚠ bias |
| Fri 13 Nov 14:45 EST | UEFA Nations League | Luxembourg v Estonia | 34/37/30 | 36/32/32 | 1X2 D @ 3.08: model EV +12.8% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Denmark v Norway | 45/24/31 | 37/27/37 | 1X2 H @ 2.49: model EV +12.0% |
| Sat 14 Nov 12:00 EST | UEFA Nations League | Georgia v Hungary | 35/31/33 | 31/31/38 | 1X2 H @ 3.15: model EV +11.5% |

⚠ bias = the model is backing an underdog against a heavy bookmaker favourite (>70%). Out of sample the model
is underconfident on heavy favourites, so these gaps are most likely model error, not value.




## Track record (paper, fixed 1-unit stakes)

*No settled selections yet. Nothing can be concluded.*