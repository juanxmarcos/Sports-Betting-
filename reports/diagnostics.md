# Sports Betting Doyen — diagnostics (2026-11-13 02:39 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 147 → complete history 144 → valid forecast 147 → fresh odds available 57 → stale odds only 0 → three plus bookmakers 22 → fully evaluated 22 → markets evaluated 337 → markets positive ev 23 → events positive ev 14 → events passing all rules 2 → final recommendations 3
  - market rejections: too few bookmakers (227), EV below threshold (89), odds outside range (19)
  - primary blocker per event: no bookmaker prices yet (90), too few bookmakers price these markets (40), prices are in line with the sharp market (11), value only at long odds outside the allowed range (4), qualified (2)

**NFL**: events discovered 14 → complete history 14 → valid forecast 14 → fresh odds available 14 → stale odds only 0 → three plus bookmakers 14 → fully evaluated 14 → markets evaluated 180 → markets positive ev 8 → events positive ev 7 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (117), too few bookmakers (58), odds outside range (5)
  - primary blocker per event: prices are in line with the sharp market (12), value only at long odds outside the allowed range (2)

**NBA**: events discovered 52 → complete history 52 → valid forecast 52 → fresh odds available 9 → stale odds only 0 → three plus bookmakers 0 → fully evaluated 0 → markets evaluated 54 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - market rejections: too few bookmakers (54)
  - primary blocker per event: no bookmaker prices yet (43), too few bookmakers price these markets (9)

**TENNIS**: events discovered 47 → complete history 17 → valid forecast 47 → fresh odds available 2 → stale odds only 0 → three plus bookmakers 2 → fully evaluated 2 → markets evaluated 4 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (4)
  - primary blocker per event: no bookmaker prices yet (45), prices are in line with the sharp market (2)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 57, 'median_odds_age_h': 0.0, 'median_bookmakers': 1, 'share_3plus_books': 0.46}
- nfl: {'events_with_odds': 14, 'median_odds_age_h': 0.0, 'median_bookmakers': 22.0, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 9, 'median_odds_age_h': 0.0, 'median_bookmakers': 1, 'share_3plus_books': 0.0}
- tennis: {'events_with_odds': 2, 'median_odds_age_h': 5.2, 'median_bookmakers': 22.0, 'share_3plus_books': 1.0}

## The Odds API

{'skipped': None, 'credits_remaining_after': '479', 'credits_spent': 3, 'fetched': ['americanfootball_nfl'], 'matched': 14, 'unmatched': []}

## Providers

- football-data:fixtures: last success 2026-11-13T02:39:35+00:00
- football-data:E0: last success 2026-11-13T02:39:36+00:00
- football-data:E1: last success 2026-11-13T02:39:38+00:00
- football-data:SP1: last success 2026-11-13T02:39:39+00:00
- football-data:D1: last success 2026-11-13T02:39:40+00:00
- football-data:I1: last success 2026-11-13T02:39:42+00:00
- football-data:F1: last success 2026-11-13T02:39:43+00:00
- football-data:N1: last success 2026-11-13T02:39:44+00:00
- football-data:P1: last success 2026-11-13T02:39:45+00:00
- football-data:B1: last success 2026-11-13T02:39:47+00:00
- football-data:SC0: last success 2026-11-13T02:39:48+00:00
- espn:international: last success 2026-11-13T02:40:44+00:00
- the-odds-api: last success 2026-11-13T02:41:05+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-13T02:40:46+00:00
- espn:nba: last success 2026-11-13T02:40:47+00:00
- espn:tennis: last success 2026-11-13T02:41:16+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-13T02:40:58+00:00
