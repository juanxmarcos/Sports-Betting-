# Sports Betting Doyen — Daily Report, 2026-11-15

*Research and paper-trading only. Not financial advice. No bets are placed automatically.
All times America/New_York. Generated Sun 15 Nov 02:49 EST. Model `dc-0.1`.*

## Daily overview

| Item | Value |
|---|---|
| Period | next 7 days (rolling 168h, same as the website "This Week") |
| Events discovered | 203 |
| Events with fresh odds | 57 |
| Events fully evaluated (3+ independent bookmakers, complete history) | 53 |
| Markets evaluated | 506 |
| Events passing all rules | 3 |
| Published today | **2** |
| Highest estimated EV | +9.4% |
| Blend weight on model (1X2/OU/AH) | 0.00/0.00/0.00 |




## Ranked selections

Ranking: by **pessimistic EV** (EV computed with the 10th-percentile model probability from
parameter uncertainty), so that thinly estimated edges rank below robust ones.


### 1. Romania to win — Bosnia and Herzegovina v Romania

| Field | Value |
|---|---|
| Sport / competition | Football — UEFA Nations League |
| Kick-off | Tue 17 Nov 14:45 EST |
| Market / selection | 1X2 — **Romania to win** |
| Best price | **4.60** @ Unibet |
| Model probability (raw) | 29.5% (±8.1 pp param. sd; p10 20.6%) |
| Market no-vig probability | 23.8% (Betfair Exchange) |
| Final probability (blend) | 23.8% |
| Fair odds | 4.20 |
| Expected value | **+9.4%** (pessimistic +9.4%) |
| Stake (paper) | 1.0 unit |
| Bookmakers quoting | 12 |
| Odds snapshot | Sun 15 Nov 01:39 EST |

**Statistical evidence.** Expected goals 1.41–1.13.
Recent form — Bosnia and Herzegovina: LDWDWL (GF 8, GA 8);
Romania: WLLLLW (GF 7, GA 15).
Model 1X2: 42/28/29%,
O2.5 47%, BTTS 52%.

**Why it may be value.** The best available price (4.60) exceeds the estimated fair
price (4.20). The
model rates this outcome 5.7 pp above the de-vigged consensus.

**Context / research flags.** 
- [verified_fact · motivation · neutral] UEFA (updated 14 Nov 2026) says Bosnia and Herzegovina will enter the A/B play-offs; Romania drop to the B/C play-offs if they do not win or if Poland beat Sweden. ([source](https://uefa.com/uefanationsleague/news/02ab-2209792f2fda-6a523d4500bb-1000--nations-league-latest-on-quarter-final-qualification-prom), 2026-11-15T07:49:11+00:00)


**Reasons this could be wrong.**
- International selection: the model has weight 0. The edge is the price versus the sharp de-vigged consensus (validated on club data: +4.5% CLV), not a model opinion.
- Team news (call-ups, withdrawals, rotation) moves international prices sharply and is not modelled.
- Model and market disagree by +5.7%.

Sources: <https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h,totals> <https://www.espn.com/soccer/match/_/gameId/401861196> 


### 2. Austria to win — Israel v Austria

| Field | Value |
|---|---|
| Sport / competition | Football — UEFA Nations League |
| Kick-off | Tue 17 Nov 14:45 EST |
| Market / selection | 1X2 — **Austria to win** |
| Best price | **1.65** @ Unibet |
| Model probability (raw) | 59.8% (±9.9 pp param. sd; p10 47.1%) |
| Market no-vig probability | 62.9% (Betfair Exchange) |
| Final probability (blend) | 62.9% |
| Fair odds | 1.59 |
| Expected value | **+3.8%** (pessimistic +3.8%) |
| Stake (paper) | 1.0 unit |
| Bookmakers quoting | 12 |
| Odds snapshot | Sun 15 Nov 01:39 EST |

**Statistical evidence.** Expected goals 1.0–2.02; neutral venue.
Recent form — Israel: WLLDDD (GF 3, GA 7);
Austria: LWWDDW (GF 10, GA 8).
Model 1X2: 18/23/60%,
O2.5 58%, BTTS 55%.

**Why it may be value.** The best available price (1.65) exceeds the estimated fair
price (1.59). The edge
comes mainly from the price being out of line with the consensus of other bookmakers.

**Context / research flags.** 
- [verified_fact · motivation · neutral] UEFA (updated 14 Nov 2026) says Austria will be promoted to League A; Israel enter the B/C play-offs if they do not beat Austria. ([source](https://uefa.com/uefanationsleague/news/02ab-2209792f2fda-6a523d4500bb-1000--nations-league-latest-on-quarter-final-qualification-prom), 2026-11-15T07:49:11+00:00)


**Reasons this could be wrong.**
- International selection: the model has weight 0. The edge is the price versus the sharp de-vigged consensus (validated on club data: +4.5% CLV), not a model opinion.
- Team news (call-ups, withdrawals, rotation) moves international prices sharply and is not modelled.

Sources: <https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h,totals> <https://www.espn.com/soccer/match/_/gameId/401861193> 




## Closest candidates (transparency)

| Match | Market | Odds | Final p | EV | Pess. EV | Status |
|---|---|---|---|---|---|---|


## International fixtures — model monitoring (not recommendations)

86 national-team matches analysed in the next 48h (model `dc-intl-0.1`,
trained on 50029 internationals; 26 with multi-bookmaker odds).
The model's gaps against bookmakers are **monitoring signals, not selections**: no free historical international
odds exist to validate the model against the market, so it has weight 0. Real (paper) international selections
appear in *Ranked selections* only when The Odds API supplies 3+ bookmakers and a price beats the sharp
de-vigged consensus under the standard rules.

| Kick-off | Competition | Match | Model H/D/A | Book H/D/A (no-vig) | Largest model–book gap |
|---|---|---|---|---|---|
| Mon 16 Nov 12:00 EST | UEFA Nations League | Lithuania v Liechtenstein | 77/20/3 | 89/9/3 | 1X2 D @ 10.50: model EV +99.0% ⚠ bias |
| Mon 16 Nov 14:45 EST | UEFA Nations League | Greece v Serbia | 50/28/22 | 68/20/12 | 1X2 A @ 7.80: model EV +64.2% |
| Sun 15 Nov 14:45 EST | UEFA Nations League | France v Turkey | 76/15/9 | 83/11/6 | 1X2 A @ 16.00: model EV +48.7% ⚠ bias |
| Mon 16 Nov 14:45 EST | UEFA Nations League | Gibraltar v Malta | 16/29/55 | 10/24/66 | 1X2 H @ 9.20: model EV +43.4% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Bosnia and Herzegovina v Romania | 42/28/29 | 50/26/24 | 1X2 A @ 4.60: model EV +35.6% |
| Mon 16 Nov 14:45 EST | UEFA Nations League | North Macedonia v Slovenia | 20/33/48 | 14/24/62 | 1X2 H @ 7.00: model EV +32.6% |
| Mon 16 Nov 14:00 EST | CONCACAF Nations League | Guadeloupe v Bermuda | 64/19/16 | 77/14/9 | 1X2 A @ 8.00: model EV +31.7% ⚠ bias |
| Mon 16 Nov 14:45 EST | UEFA Nations League | Germany v Netherlands | 44/23/33 | 51/23/26 | 1X2 A @ 3.74: model EV +23.3% |
| Sun 15 Nov 14:45 EST | UEFA Nations League | Croatia v Czech Republic | 58/22/20 | 62/22/16 | 1X2 A @ 6.25: model EV +22.1% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Denmark v Norway | 47/24/29 | 39/24/37 | 1X2 H @ 2.55: model EV +20.0% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Republic of Ireland v Kosovo | 38/33/28 | 46/30/24 | 1X2 A @ 4.25: model EV +19.7% |
| Mon 16 Nov 12:00 EST | UEFA Nations League | Iceland v Luxembourg | 69/21/9 | 75/17/8 | 1X2 D @ 5.54: model EV +18.5% ⚠ bias |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Hungary v Northern Ireland | 42/34/24 | 49/29/22 | 1X2 D @ 3.48: model EV +17.5% |
| Sun 15 Nov 12:00 EST | UEFA Nations League | Belarus v Albania (N) | 24/34/42 | 22/30/48 | 1X2 D @ 3.40: model EV +16.6% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Wales v Portugal | 14/23/63 | 13/20/67 | 1X2 D @ 5.00: model EV +14.2% |
| Mon 16 Nov 14:45 EST | UEFA Nations League | Switzerland v Scotland | 66/21/13 | 56/26/18 | 1X2 H @ 1.77: model EV +14.0% |
| Sun 15 Nov 09:00 EST | UEFA Nations League | Latvia v Armenia | 34/30/35 | 30/30/41 | 1X2 H @ 3.30: model EV +13.4% |
| Mon 16 Nov 12:00 EST | UEFA Nations League | Estonia v Bulgaria | 41/31/29 | 46/30/23 | 1X2 A @ 4.10: model EV +13.2% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Poland v Sweden | 41/24/35 | 42/26/32 | 1X2 A @ 3.12: model EV +10.1% |
| Mon 16 Nov 14:00 EST | CONCACAF Nations League | Guyana v Puerto Rico | 61/20/18 | 53/24/22 | 1X2 H @ 1.77: model EV +8.8% |
| Sun 15 Nov 09:00 EST | UEFA Nations League | Cyprus v Montenegro | 33/28/39 | 31/28/41 | 1X2 H @ 3.22: model EV +6.6% |
| Sun 15 Nov 14:45 EST | UEFA Nations League | Belgium v Italy | 48/26/26 | 45/26/30 | 1X2 H @ 2.21: model EV +5.8% |
| Sun 15 Nov 14:45 EST | UEFA Nations League | Spain v England | 53/26/21 | 50/25/25 | 1X2 H @ 1.97: model EV +5.3% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Israel v Austria (N) | 18/23/60 | 16/21/63 | 1X2 H @ 5.92: model EV +4.4% |
| Tue 17 Nov 14:45 EST | UEFA Nations League | Ukraine v Georgia (N) | 42/30/28 | 44/28/28 | 1X2 D @ 3.50: model EV +4.1% |
| Mon 16 Nov 10:00 EST | UEFA Nations League | Kazakhstan v Slovakia | 18/25/57 | 21/25/54 | 1X2 A @ 1.83: model EV +3.9% |
| Sun 15 Nov 12:00 EST | UEFA Nations League | Finland v San Marino | 96/3/1 | 96/3/1 | 1X2 H @ 1.05: model EV +0.9% |
| Mon 16 Nov 14:00 EST | CONCACAF Nations League | Cuba v Grenada | 68/19/13 | 74/15/11 | 1X2 D @ 5.25: model EV +0.1% ⚠ bias |
| Mon 16 Nov 10:00 EST | UEFA Nations League | Faroe Islands v Moldova | 54/27/19 | 55/27/18 | 1X2 D @ 3.68: model EV +0.1% |
| Sun 15 Nov 18:00 EST | CONCACAF Nations League | Panama v Curaçao | 62/22/16 | 63/22/14 | 1X2 H @ 1.50: model EV -7.7% |
| Sun 15 Nov 12:00 EST | International Friendly | Suriname v Eswatini (N) | 46/32/22 | — |  |
| Mon 16 Nov 08:00 EST | AFCON Qualifying | Namibia v Cameroon (N) | 7/24/68 | — |  |
| Mon 16 Nov 08:00 EST | AFCON Qualifying | Sudan v Senegal (N) | 5/16/79 | — |  |
| Mon 16 Nov 08:00 EST | AFCON Qualifying | Zimbabwe v Equatorial Guinea | 46/32/22 | — |  |
| Mon 16 Nov 10:00 EST | AFCON Qualifying | Somalia v Ghana (N) | 5/24/71 | — |  |
| Mon 16 Nov 11:00 EST | AFCON Qualifying | Central African Republic v Benin (N) | 14/21/64 | — |  |
| Mon 16 Nov 12:00 EST | AFCON Qualifying | Eritrea v Guinea (N) | 15/22/63 | — |  |
| Mon 16 Nov 13:00 EST | International Friendly | Andorra v Azerbaijan | 18/38/44 | — |  |
| Mon 16 Nov 19:00 EST | CONCACAF Nations League | Martinique v Aruba | 69/20/11 | — |  |
| Mon 16 Nov 19:00 EST | CONCACAF Nations League | Trinidad and Tobago v Antigua and Barbuda | 88/9/3 | — |  |

⚠ bias = the model is backing an underdog against a heavy bookmaker favourite (>70%). Out of sample the model
is underconfident on heavy favourites, so these gaps are most likely model error, not value.




## Track record (paper, fixed 1-unit stakes)

Settled 3 · W 1 / L 2 / P 0 ·
profit -1.20u · yield -40.0%
(95% CI -100.0% to +80.0%) ·
avg CLV -0.3% · max drawdown 1.2u.
*Only 3 settled selections. Yield CIs are wide; at typical odds, several hundred to a few thousand bets are needed before ROI distinguishes skill from luck. CLV is the faster, more reliable early indicator.*