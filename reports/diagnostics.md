# Sports Betting Doyen — diagnostics (2026-11-14 18:07 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 98 → complete history 96 → valid forecast 98 → fresh odds available 39 → stale odds only 0 → three plus bookmakers 31 → fully evaluated 31 → markets evaluated 301 → markets positive ev 32 → events positive ev 21 → events passing all rules 6 → final recommendations 11
  - market rejections: too few bookmakers (142), EV below threshold (137), odds outside range (16)
  - primary blocker per event: no bookmaker prices yet (59), prices are in line with the sharp market (18), too few bookmakers price these markets (10), qualified (6), value only at long odds outside the allowed range (5)

**NFL**: events discovered 14 → complete history 14 → valid forecast 14 → fresh odds available 14 → stale odds only 0 → three plus bookmakers 14 → fully evaluated 14 → markets evaluated 122 → markets positive ev 3 → events positive ev 3 → events passing all rules 0 → final recommendations 0
  - market rejections: too few bookmakers (72), EV below threshold (46), odds outside range (4)
  - primary blocker per event: prices are in line with the sharp market (8), value only at long odds outside the allowed range (4), too few bookmakers price these markets (2)

**NBA**: events discovered 53 → complete history 53 → valid forecast 53 → fresh odds available 5 → stale odds only 0 → three plus bookmakers 0 → fully evaluated 0 → markets evaluated 28 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - market rejections: too few bookmakers (28)
  - primary blocker per event: no bookmaker prices yet (48), too few bookmakers price these markets (5)

**TENNIS**: events discovered 45 → complete history 12 → valid forecast 45 → fresh odds available 4 → stale odds only 0 → three plus bookmakers 4 → fully evaluated 4 → markets evaluated 8 → markets positive ev 2 → events positive ev 1 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (6), odds outside range (2)
  - primary blocker per event: no bookmaker prices yet (41), prices are in line with the sharp market (3), value only at long odds outside the allowed range (1)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 39, 'median_odds_age_h': 0.0, 'median_bookmakers': 14, 'share_3plus_books': 0.79}
- nfl: {'events_with_odds': 14, 'median_odds_age_h': 0.0, 'median_bookmakers': 22.0, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 5, 'median_odds_age_h': 0.0, 'median_bookmakers': 23, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 4, 'median_odds_age_h': 6.6, 'median_bookmakers': 17.5, 'share_3plus_books': 1.0}

## The Odds API

{'skipped': None, 'credits_remaining_after': '435', 'credits_spent': 2, 'fetched': ['soccer_uefa_nations_league'], 'matched': 31, 'unmatched': ['soccer_uefa_nations_league: Austria v Iceland']}

## Providers

- football-data:fixtures: last success 2026-11-14T18:07:37+00:00
- football-data:E0: last success 2026-11-14T18:07:38+00:00
- football-data:E1: last success 2026-11-14T18:07:39+00:00
- football-data:SP1: last success 2026-11-14T18:07:40+00:00
- football-data:D1: last success 2026-11-14T18:07:41+00:00
- football-data:I1: last success 2026-11-14T18:07:43+00:00
- football-data:F1: last success 2026-11-14T18:07:44+00:00
- football-data:N1: last success 2026-11-14T18:07:45+00:00
- football-data:P1: last success 2026-11-14T18:07:46+00:00
- football-data:B1: last success 2026-11-14T18:07:47+00:00
- football-data:SC0: last success 2026-11-14T18:07:48+00:00
- espn:international: last success 2026-11-14T18:08:36+00:00
- the-odds-api: last success 2026-11-14T18:08:51+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-14T18:08:37+00:00
- espn:nba: last success 2026-11-14T18:08:38+00:00
- espn:tennis: last success 2026-11-14T18:08:58+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-14T18:08:45+00:00
