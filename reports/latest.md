# Sports Betting Doyen — Daily Report, 2026-11-24

*Research and paper-trading only. Not financial advice. No bets are placed automatically.
All times America/New_York. Generated Tue 24 Nov 09:04 EST. Model `dc-0.1`.*

## Daily overview

| Item | Value |
|---|---|
| Period | next 7 days (rolling 168h, same as the website "This Week") |
| Events discovered | 224 |
| Events with fresh odds | 127 |
| Events fully evaluated (3+ independent bookmakers, complete history) | 108 |
| Markets evaluated | 1066 |
| Events passing all rules | 22 |
| Published today | **7** |
| Highest estimated EV | +6.4% |
| Blend weight on model (1X2/OU/AH) | 0.00/0.00/0.00 |




## Ranked selections

Ranking: by **pessimistic EV** (EV computed with the 10th-percentile model probability from
parameter uncertainty), so that thinly estimated edges rank below robust ones.


### 1. Stoke to win — Stoke v Millwall

| Field | Value |
|---|---|
| Sport / competition | Football — England Championship |
| Kick-off | Wed 25 Nov 15:00 EST |
| Market / selection | 1X2 — **Stoke to win** |
| Best price | **2.40** @ LeoVegas |
| Model probability (raw) | 41.1% (±8.2 pp param. sd; p10 29.6%) |
| Market no-vig probability | 43.7% (Betfair Exchange) |
| Final probability (blend) | 43.7% |
| Fair odds | 2.29 |
| Expected value | **+4.8%** (pessimistic +4.8%) |
| Stake (paper) | 1.0 unit |
| Bookmakers quoting | 17 |
| Odds snapshot | Tue 24 Nov 01:31 EST |

**Statistical evidence.** Expected goals 1.29–1.09;
model strength rank 19 vs 13 (of 36).
Recent form — Stoke: WDWWWW (GF 8, GA 2, xG 1.23/0.82);
Millwall: DLWLLL (GF 7, GA 12, xG 1.45/1.66).
Model 1X2: 41/28/31%,
O2.5 43%, BTTS 48%.

**Why it may be value.** The best available price (2.40) exceeds the estimated fair
price (2.29). The edge
comes mainly from the price being out of line with the consensus of other bookmakers.

**Context / research flags.** No contextual research recorded yet (team news is not modelled — check before acting).

**Reasons this could be wrong.**
- Model uses results/goals only: it does not see lineups, injuries or suspensions beyond what is already reflected in recent results and market prices.

Sources: <https://api.the-odds-api.com/v4/sports/soccer_efl_champ/odds?regions=eu&markets=h2h,totals> <https://www.espn.com/soccer/match/_/gameId/401880138> 


### 2. Tampa Bay Buccaneers to win — Tampa Bay Buccaneers v Carolina Panthers

| Field | Value |
|---|---|
| Sport / competition | NFL — NFL |
| Kick-off | Mon 30 Nov 20:15 EST |
| Market / selection | ML — **Tampa Bay Buccaneers to win** |
| Best price | **1.72** @ Marathon Bet |
| Model probability (raw) | 64.3% (±0.0 pp param. sd; p10 64.3%) |
| Market no-vig probability | 59.9% (Pinnacle) |
| Final probability (blend) | 59.9% |
| Fair odds | 1.67 |
| Expected value | **+3.0%** (pessimistic +3.0%) |
| Stake (paper) | 1.0 unit |
| Bookmakers quoting | 16 |
| Odds snapshot | Tue 24 Nov 01:31 EST |

**Statistical evidence.** Projected score Tampa Bay Buccaneers 25.6 – Carolina Panthers 21.4. Doyen's ratings project Tampa Bay Buccaneers 25.6 – Carolina Panthers 21.4 pts (margin +4.2, total 47.0); power ranks 15 and 22 of 32.

**Why it may be value.** The best available price (1.72) exceeds the estimated fair
price (1.67). The
model rates this outcome 4.4 pp above the de-vigged consensus.

**Context / research flags.** No contextual research recorded yet (team news is not modelled — check before acting).

**Reasons this could be wrong.**
- Model weight 0.00: the edge is the price versus the multi-bookmaker consensus, not a model opinion.

Sources: <https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds?regions=eu&markets=h2h,spreads,totals> <https://www.espn.com/football/game/_/gameId/401873094> 


### 3. Detroit Pistons to win — Orlando Magic v Detroit Pistons

| Field | Value |
|---|---|
| Sport / competition | NBA — NBA |
| Kick-off | Tue 24 Nov 19:00 EST |
| Market / selection | ML — **Detroit Pistons to win** |
| Best price | **1.76** @ consensus |
| Model probability (raw) | 63.6% |
| Market no-vig probability | 55.4% (Doyen model (shrunk and capped toward the market)) |
| Final probability (blend) | 60.4% |
| Fair odds | 1.65 |
| Expected value | **+6.4%** (pessimistic +6.4%) |
| Stake (paper) | 1.0 unit |
| Bookmakers quoting | 19 |
| Odds snapshot | Tue 24 Nov 01:31 EST |

**Statistical evidence.** No further model detail is stored for this pick.

**Why it may be value.** The best available price (1.76) exceeds the estimated fair
price (1.65). The
model rates this outcome 8.1 pp above the de-vigged consensus.

**Context / research flags.** 
- [interpretation · injury · supports] TalkBasket's 24 Nov 2026 NBA injury report roundup (via search summary; page not directly readable) lists Magic F Paolo Banchero out (high ankle sprain) with Isaac, Penda and Nelson also out, and Pistons G Cade Cunningham probable (right knee soreness) with Duren, Robinson, Prince and Okorie out, ahead of the 7pm ET game; not confirmed against the official NBA report. ([source](https://www.talkbasket.net/229884-nba-injury-report-banchero-cunningham-listed-on-tuesday-november-24), 2026-11-24T14:04:02+00:00)


**Reasons this could be wrong.**
- Typical odds (issue #112): the price is the median across sportsbooks and includes their margin, so the estimated value is usually slightly negative; picks are chosen by likelihood, and your sportsbook's price may differ slightly.

Sources: 


### 4. Under 3.5 goals — Rangers v Aberdeen

| Field | Value |
|---|---|
| Sport / competition | Football — SC0 |
| Kick-off | Tue 24 Nov 15:00 EST |
| Market / selection | OU — **Under 3.5 goals** |
| Best price | **1.66** @ consensus |
| Model probability (raw) | 62.5% |
| Market no-vig probability | 56.6% (Doyen model (shrunk and capped toward the market)) |
| Final probability (blend) | 58.0% |
| Fair odds | 1.72 |
| Expected value | **-3.9%** (pessimistic -3.9%) |
| Stake (paper) | 1.0 unit |
| Bookmakers quoting | 4 |
| Odds snapshot | Tue 24 Nov 01:31 EST |

**Statistical evidence.** No further model detail is stored for this pick.

**Why it may be value.** The best available price (1.66) exceeds the estimated fair
price (1.72). The
model rates this outcome 5.9 pp above the de-vigged consensus.

**Context / research flags.** No contextual research recorded yet (team news is not modelled — check before acting).

**Reasons this could be wrong.**
- Typical odds (issue #112): the price is the median across sportsbooks and includes their margin, so the estimated value is usually slightly negative; picks are chosen by likelihood, and your sportsbook's price may differ slightly.

Sources: 


### 5. Over 2.5 goals — Sheffield United v Southampton

| Field | Value |
|---|---|
| Sport / competition | Football — E1 |
| Kick-off | Tue 24 Nov 14:45 EST |
| Market / selection | OU — **Over 2.5 goals** |
| Best price | **1.66** @ consensus |
| Model probability (raw) | 55.5% |
| Market no-vig probability | 57.5% (Doyen model (shrunk and capped toward the market)) |
| Final probability (blend) | 57.0% |
| Fair odds | 1.75 |
| Expected value | **-5.4%** (pessimistic -5.4%) |
| Stake (paper) | 1.0 unit |
| Bookmakers quoting | 2 |
| Odds snapshot | Tue 24 Nov 01:30 EST |

**Statistical evidence.** No further model detail is stored for this pick.

**Why it may be value.** The best available price (1.66) exceeds the estimated fair
price (1.75). The edge
comes mainly from the price being out of line with the consensus of other bookmakers.

**Context / research flags.** No contextual research recorded yet (team news is not modelled — check before acting).

**Reasons this could be wrong.**
- Typical odds (issue #112): the price is the median across sportsbooks and includes their margin, so the estimated value is usually slightly negative; picks are chosen by likelihood, and your sportsbook's price may differ slightly.

Sources: 


### 6. Under 3.5 goals — Cardiff v Preston

| Field | Value |
|---|---|
| Sport / competition | Football — E1 |
| Kick-off | Tue 24 Nov 14:45 EST |
| Market / selection | OU — **Under 3.5 goals** |
| Best price | **1.70** @ consensus |
| Model probability (raw) | 64.0% |
| Market no-vig probability | 54.5% (Doyen model (shrunk and capped toward the market)) |
| Final probability (blend) | 56.9% |
| Fair odds | 1.76 |
| Expected value | **-3.6%** (pessimistic -3.6%) |
| Stake (paper) | 1.0 unit |
| Bookmakers quoting | 2 |
| Odds snapshot | Tue 24 Nov 01:30 EST |

**Statistical evidence.** No further model detail is stored for this pick.

**Why it may be value.** The best available price (1.70) exceeds the estimated fair
price (1.76). The
model rates this outcome 9.4 pp above the de-vigged consensus.

**Context / research flags.** No contextual research recorded yet (team news is not modelled — check before acting).

**Reasons this could be wrong.**
- Typical odds (issue #112): the price is the median across sportsbooks and includes their margin, so the estimated value is usually slightly negative; picks are chosen by likelihood, and your sportsbook's price may differ slightly.

Sources: 


### 7. Under 2.5 goals — Charlton v Lincoln

| Field | Value |
|---|---|
| Sport / competition | Football — E1 |
| Kick-off | Tue 24 Nov 14:45 EST |
| Market / selection | OU — **Under 2.5 goals** |
| Best price | **1.73** @ consensus |
| Model probability (raw) | 63.7% |
| Market no-vig probability | 54.5% (Doyen model (shrunk and capped toward the market)) |
| Final probability (blend) | 56.8% |
| Fair odds | 1.76 |
| Expected value | **-1.7%** (pessimistic -1.7%) |
| Stake (paper) | 1.0 unit |
| Bookmakers quoting | 7 |
| Odds snapshot | Tue 24 Nov 01:31 EST |

**Statistical evidence.** No further model detail is stored for this pick.

**Why it may be value.** The best available price (1.73) exceeds the estimated fair
price (1.76). The
model rates this outcome 9.2 pp above the de-vigged consensus.

**Context / research flags.** No contextual research recorded yet (team news is not modelled — check before acting).

**Reasons this could be wrong.**
- Typical odds (issue #112): the price is the median across sportsbooks and includes their margin, so the estimated value is usually slightly negative; picks are chosen by likelihood, and your sportsbook's price may differ slightly.

Sources: 




## Closest candidates (transparency)

| Match | Market | Odds | Final p | EV | Pess. EV | Status |
|---|---|---|---|---|---|---|


## International fixtures — model monitoring (not recommendations)

No national-team fixtures in the next 48h.

## Track record (paper, fixed 1-unit stakes)

Settled 41 · W 14 / L 26 / P 1 ·
profit -11.47u · yield -28.0%
(95% CI -58.3% to +4.7%) ·
avg CLV +0.7% · max drawdown 11.88u.
*Only 41 settled selections. Yield CIs are wide; at typical odds, several hundred to a few thousand bets are needed before ROI distinguishes skill from luck. CLV is the faster, more reliable early indicator.*