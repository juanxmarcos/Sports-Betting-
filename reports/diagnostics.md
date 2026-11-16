# Sports Betting Doyen — diagnostics (2026-11-16 21:38 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 56 → complete history 55 → valid forecast 56 → fresh odds available 36 → stale odds only 0 → three plus bookmakers 8 → fully evaluated 8 → markets evaluated 214 → markets positive ev 6 → events positive ev 5 → events passing all rules 0 → final recommendations 4
  - market rejections: too few bookmakers (178), EV below threshold (35), odds outside range (1)
  - primary blocker per event: too few bookmakers price these markets (28), no bookmaker prices yet (20), prices are in line with the sharp market (7), value only at long odds outside the allowed range (1)

**NFL**: events discovered 13 → complete history 13 → valid forecast 13 → fresh odds available 13 → stale odds only 0 → three plus bookmakers 12 → fully evaluated 12 → markets evaluated 158 → markets positive ev 13 → events positive ev 10 → events passing all rules 1 → final recommendations 1
  - market rejections: EV below threshold (89), too few bookmakers (60), odds outside range (8)
  - primary blocker per event: prices are in line with the sharp market (8), value only at long odds outside the allowed range (3), too few bookmakers price these markets (1), qualified (1)

**NBA**: events discovered 51 → complete history 51 → valid forecast 51 → fresh odds available 8 → stale odds only 0 → three plus bookmakers 0 → fully evaluated 0 → markets evaluated 46 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - market rejections: too few bookmakers (46)
  - primary blocker per event: no bookmaker prices yet (43), too few bookmakers price these markets (8)

**TENNIS**: events discovered 51 → complete history 16 → valid forecast 51 → fresh odds available 2 → stale odds only 0 → three plus bookmakers 2 → fully evaluated 2 → markets evaluated 4 → markets positive ev 2 → events positive ev 2 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (4)
  - primary blocker per event: no bookmaker prices yet (49), prices are in line with the sharp market (2)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 36, 'median_odds_age_h': 0.0, 'median_bookmakers': 1.0, 'share_3plus_books': 0.22}
- nfl: {'events_with_odds': 13, 'median_odds_age_h': 0.0, 'median_bookmakers': 18, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 8, 'median_odds_age_h': 0.0, 'median_bookmakers': 23.0, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 2, 'median_odds_age_h': 0.0, 'median_bookmakers': 16.0, 'share_3plus_books': 1.0}

## The Odds API

{'skipped': None, 'credits_remaining_after': '375', 'credits_spent': 1, 'fetched': ['tennis_atp_finals'], 'matched': 2, 'unmatched': []}

## Providers

- football-data:fixtures: last success 2026-11-16T21:39:00+00:00
- football-data:E0: last success 2026-11-16T21:39:02+00:00
- football-data:E1: last success 2026-11-16T21:39:03+00:00
- football-data:SP1: last success 2026-11-16T21:39:05+00:00
- football-data:D1: last success 2026-11-16T21:39:06+00:00
- football-data:I1: last success 2026-11-16T21:39:08+00:00
- football-data:F1: last success 2026-11-16T21:39:09+00:00
- football-data:N1: last success 2026-11-16T21:39:11+00:00
- football-data:P1: last success 2026-11-16T21:39:12+00:00
- football-data:B1: last success 2026-11-16T21:39:13+00:00
- football-data:SC0: last success 2026-11-16T21:39:15+00:00
- espn:international: last success 2026-11-16T21:40:05+00:00
- the-odds-api: last success 2026-11-16T21:40:24+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-16T21:40:06+00:00
- espn:nba: last success 2026-11-16T21:40:08+00:00
- espn:tennis: last success 2026-11-16T21:40:32+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-16T21:40:17+00:00
