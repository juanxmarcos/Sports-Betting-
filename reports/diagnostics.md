# Sports Betting Doyen — diagnostics (2026-11-12 21:50 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 150 → complete history 147 → valid forecast 150 → fresh odds available 57 → stale odds only 0 → three plus bookmakers 22 → markets evaluated 431 → markets positive ev 14 → events positive ev 10 → events passing all rules 3 → final recommendations 3
  - market rejections: too few bookmakers (315), EV below threshold (94), odds outside range (19)
  - primary blocker per event: no bookmaker prices yet (93), too few bookmakers price these markets (38), prices are in line with the sharp market (10), value only at long odds outside the allowed range (6), qualified (3)

**NFL**: events discovered 14 → complete history 14 → valid forecast 14 → fresh odds available 14 → stale odds only 0 → three plus bookmakers 1 → markets evaluated 94 → markets positive ev 1 → events positive ev 1 → events passing all rules 0 → final recommendations 0
  - market rejections: too few bookmakers (80), EV below threshold (14)
  - primary blocker per event: too few bookmakers price these markets (13), prices are in line with the sharp market (1)

**NBA**: events discovered 52 → complete history 52 → valid forecast 52 → fresh odds available 4 → stale odds only 0 → three plus bookmakers 4 → markets evaluated 56 → markets positive ev 1 → events positive ev 1 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (47), too few bookmakers (8), odds outside range (1)
  - primary blocker per event: no bookmaker prices yet (48), prices are in line with the sharp market (4)

**TENNIS**: events discovered 48 → complete history 18 → valid forecast 48 → fresh odds available 3 → stale odds only 0 → three plus bookmakers 3 → markets evaluated 6 → markets positive ev 1 → events positive ev 1 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (6)
  - primary blocker per event: no bookmaker prices yet (45), prices are in line with the sharp market (3)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 57, 'median_odds_age_h': 0.0, 'median_bookmakers': 1, 'share_3plus_books': 0.46}
- nfl: {'events_with_odds': 14, 'median_odds_age_h': 0.0, 'median_bookmakers': 1.0, 'share_3plus_books': 0.07}
- nba: {'events_with_odds': 4, 'median_odds_age_h': 0.0, 'median_bookmakers': 31.0, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 3, 'median_odds_age_h': 0.4, 'median_bookmakers': 22, 'share_3plus_books': 1.0}

## The Odds API

{'skipped': None, 'credits_remaining_after': '482', 'credits_spent': 2, 'fetched': ['soccer_uefa_nations_league'], 'matched': 26, 'unmatched': ['soccer_uefa_nations_league: Austria v Iceland']}

## Providers

- football-data:fixtures: last success 2026-11-12T21:50:38+00:00
- football-data:E0: last success 2026-11-12T21:50:38+00:00
- football-data:E1: last success 2026-11-12T21:50:38+00:00
- football-data:SP1: last success 2026-11-12T21:50:38+00:00
- football-data:D1: last success 2026-11-12T21:50:38+00:00
- football-data:I1: last success 2026-11-12T21:50:38+00:00
- football-data:F1: last success 2026-11-12T21:50:38+00:00
- football-data:N1: last success 2026-11-12T21:50:38+00:00
- football-data:P1: last success 2026-11-12T21:50:38+00:00
- football-data:B1: last success 2026-11-12T21:50:38+00:00
- football-data:SC0: last success 2026-11-12T21:50:38+00:00
- espn:international: last success 2026-11-12T21:51:03+00:00
- the-odds-api: last success 2026-11-12T21:51:05+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-12T21:51:03+00:00
- espn:nba: last success 2026-11-12T21:51:03+00:00
- espn:tennis: last success 2026-11-12T21:51:12+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-12T21:51:03+00:00
