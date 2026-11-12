# Sports Betting Doyen — diagnostics (2026-11-12 22:12 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 149 → complete history 146 → valid forecast 149 → fresh odds available 57 → stale odds only 0 → three plus bookmakers 22 → fully evaluated 22 → markets evaluated 431 → markets positive ev 118 → events positive ev 50 → events passing all rules 2 → final recommendations 3
  - market rejections: too few bookmakers (321), EV below threshold (89), odds outside range (19)
  - primary blocker per event: no bookmaker prices yet (92), too few bookmakers price these markets (50), prices are in line with the sharp market (3), qualified (2), value only at long odds outside the allowed range (2)

**NFL**: events discovered 14 → complete history 14 → valid forecast 14 → fresh odds available 14 → stale odds only 0 → three plus bookmakers 1 → fully evaluated 1 → markets evaluated 94 → markets positive ev 34 → events positive ev 14 → events passing all rules 0 → final recommendations 0
  - market rejections: too few bookmakers (80), EV below threshold (14)
  - primary blocker per event: too few bookmakers price these markets (14)

**NBA**: events discovered 52 → complete history 52 → valid forecast 52 → fresh odds available 4 → stale odds only 0 → three plus bookmakers 4 → fully evaluated 4 → markets evaluated 56 → markets positive ev 5 → events positive ev 4 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (41), too few bookmakers (14), odds outside range (1)
  - primary blocker per event: no bookmaker prices yet (48), prices are in line with the sharp market (2), too few bookmakers price these markets (2)

**TENNIS**: events discovered 47 → complete history 17 → valid forecast 47 → fresh odds available 2 → stale odds only 0 → three plus bookmakers 2 → fully evaluated 2 → markets evaluated 4 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (4)
  - primary blocker per event: no bookmaker prices yet (45), prices are in line with the sharp market (2)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 57, 'median_odds_age_h': 0.0, 'median_bookmakers': 1, 'share_3plus_books': 0.46}
- nfl: {'events_with_odds': 14, 'median_odds_age_h': 0.0, 'median_bookmakers': 1.0, 'share_3plus_books': 0.07}
- nba: {'events_with_odds': 4, 'median_odds_age_h': 0.0, 'median_bookmakers': 31.0, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 2, 'median_odds_age_h': 0.8, 'median_bookmakers': 22.0, 'share_3plus_books': 1.0}

## The Odds API

{'skipped': 'ODDS_API_KEY not set', 'credits_remaining_after': None, 'credits_spent': None, 'fetched': None, 'matched': None, 'unmatched': None}

## Providers

- football-data:fixtures: last success 2026-11-12T22:11:28+00:00
- football-data:E0: last success 2026-11-12T22:11:28+00:00
- football-data:E1: last success 2026-11-12T22:11:28+00:00
- football-data:SP1: last success 2026-11-12T22:11:29+00:00
- football-data:D1: last success 2026-11-12T22:11:29+00:00
- football-data:I1: last success 2026-11-12T22:11:29+00:00
- football-data:F1: last success 2026-11-12T22:11:29+00:00
- football-data:N1: last success 2026-11-12T22:11:29+00:00
- football-data:P1: last success 2026-11-12T22:11:29+00:00
- football-data:B1: last success 2026-11-12T22:11:29+00:00
- football-data:SC0: last success 2026-11-12T22:11:29+00:00
- espn:international: last success 2026-11-12T22:11:54+00:00
- the-odds-api: last success 2026-11-12T21:51:05+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-12T22:11:54+00:00
- espn:nba: last success 2026-11-12T22:11:54+00:00
- espn:tennis: last success 2026-11-12T22:12:06+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-12T22:11:55+00:00
