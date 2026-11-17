# Parlay research — 2026-11-16 16:46 New York

Status: **not_published**. Open gates: combined_quote, joint_calibration.

## 1. Combined-quote sources (pages read 2026-11-16)

| Source | Status | Finding | Link |
|---|---|---|---|
| The Odds API (in use, free 500 credits/month) | no combined price | Endpoints return single-market outcomes only (sports, odds, scores, events, event odds, markets, participants; historical on paid plans). No parlay or bet-builder endpoint. | https://the-odds-api.com/liveapi/guides/v4/ |
| ESPN public JSON (in use) | no combined price | One moneyline/spread/total per event from one provider. | — |
| football-data.co.uk (in use) | no combined price | Historical single-market closing/opening odds files. | — |
| OpticOdds Parlay API (POST /parlay/odds) | paid, not enabled | Prices parlays across sportsbooks, but needs a licence key obtained by contacting sales; no public price or free tier found. | https://developer.opticodds.com/reference/post_parlay-odds |
| OddsBlaze same-game-parlay endpoint | paid, not enabled | Sportsbook-specific SGP prices (DraftKings, FanDuel, Fanatics ...). Third-party review: Plan 1 $299/month, 'does not offer a free tier'. | https://sportsapis.dev/apis/oddsblaze |
| SportsGameOdds | no combined price | Leg odds as building blocks; the combined price is computed by the client, which is exactly the product Doyen may not present as a quote. | https://sportsgameodds.com/use-cases/parlay-builder-api |
| Bookmaker bet slips (websites/apps) | owner manual entry only | The only no-cost source of a real combined price. Automated reading of bet slips (scraping) is not acceptable; the owner can record a slip price with `python -m sbi parlay-quote`. | — |

No legally usable, no-cost source returns a bookmaker's own combined price. Paid sources are listed for the owner's information only; none is enabled.

## 2. Today's screen

- Straight picks seen: 2; usable as legs today: 0
- Combinations checked: 0; passed leg screens: 0
- Verified owner quotes: 0 (recorded in total: 0)
- Excluded: {"leg: pick is not active": 2}

## 3. Joint calibration (pre-registered criteria)

- Source: data/backtest/bets_test.csv (walk-forward test seasons); settled selections: 250
- Disjoint two-leg combinations (same New York day; different competitions, events and teams): **66** (required: 200)
- Both legs won: observed 6, multiplied probabilities predict 6.52 (z = -0.22)
- Legs won: observed 43, predicted 41.03 (z = 0.38)
- Outcome correlation between paired legs (phi): -0.039
- Leagues covered: D1, E0, E1, F1, I1, SP1; legs per combination: 2
- Verdict: **not passed** — only 66 disjoint settled combinations; at least 200 are required

The sample is consistent with independence but far too small to rely on, and it covers only six club leagues and two legs. Live picks so far are UEFA Nations League, which the evidence does not cover.

## 4. Scarcity of eligible legs (all published straight picks, by New York day)

| Day | Picks | Competitions | Bookmakers | Pairs under current screens | Pairs if same competition were allowed |
|---|---|---|---|---|---|
| 2026-11-13 | 2 | 1 | 2 | 0 | 1 |
| 2026-11-14 | 1 | 1 | 1 | 0 | 0 |
| 2026-11-15 | 3 | 1 | 2 | 0 | 3 |
| 2026-11-16 | 6 | 1 | 3 | 0 | 15 |
| 2026-11-17 | 4 | 1 | 2 | 0 | 6 |
| 2026-11-22 | 1 | 1 | 1 | 0 | 0 |

Total published straight picks: 17. Whenever every pick is in one competition, the same-competition screen leaves zero pairs. The last column is a counterfactual only; the screen is unchanged and relaxing it is an owner decision that needs its own evidence.

## 5. Shadow ledger (`ledger/parlay_shadow.csv`, unpublished, computed prices)

- Rows: 0; both/all legs won: 0; lost: 0; open: 0

## 6. Open straight picks (leg candidates; ids for `parlay-quote`)

- `0795fb50263195c7` Chicago Bears v New Orleans Saints — New Orleans Saints to win (2026-11-22T18:00:00+00:00)
- `891ed45cef4e0fe7` Denmark v Norway — Draw (2026-11-17T19:45:00+00:00)
