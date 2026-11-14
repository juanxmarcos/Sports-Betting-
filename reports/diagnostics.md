# Sports Betting Doyen — diagnostics (2026-11-14 02:28 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 108 → complete history 105 → valid forecast 108 → fresh odds available 38 → stale odds only 0 → three plus bookmakers 28 → fully evaluated 28 → markets evaluated 252 → markets positive ev 20 → events positive ev 16 → events passing all rules 3 → final recommendations 5
  - market rejections: too few bookmakers (126), EV below threshold (106), odds outside range (16)
  - primary blocker per event: no bookmaker prices yet (70), prices are in line with the sharp market (19), too few bookmakers price these markets (10), value only at long odds outside the allowed range (6), qualified (3)

**NFL**: events discovered 14 → complete history 14 → valid forecast 14 → fresh odds available 14 → stale odds only 0 → three plus bookmakers 14 → fully evaluated 14 → markets evaluated 192 → markets positive ev 10 → events positive ev 7 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (132), too few bookmakers (56), odds outside range (4)
  - primary blocker per event: prices are in line with the sharp market (11), value only at long odds outside the allowed range (3)

**NBA**: events discovered 52 → complete history 52 → valid forecast 52 → fresh odds available 3 → stale odds only 0 → three plus bookmakers 3 → fully evaluated 3 → markets evaluated 54 → markets positive ev 4 → events positive ev 3 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (31), too few bookmakers (20), odds outside range (3)
  - primary blocker per event: no bookmaker prices yet (49), prices are in line with the sharp market (3)

**TENNIS**: events discovered 45 → complete history 12 → valid forecast 45 → fresh odds available 4 → stale odds only 0 → three plus bookmakers 4 → fully evaluated 4 → markets evaluated 8 → markets positive ev 1 → events positive ev 1 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (5), odds outside range (3)
  - primary blocker per event: no bookmaker prices yet (41), prices are in line with the sharp market (2), value only at long odds outside the allowed range (2)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 38, 'median_odds_age_h': 0.0, 'median_bookmakers': 11.5, 'share_3plus_books': 0.74}
- nfl: {'events_with_odds': 14, 'median_odds_age_h': 0.0, 'median_bookmakers': 22.0, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 3, 'median_odds_age_h': 0.0, 'median_bookmakers': 21, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 4, 'median_odds_age_h': 0.0, 'median_bookmakers': 6.5, 'share_3plus_books': 1.0}

## The Odds API

{'skipped': None, 'credits_remaining_after': '449', 'credits_spent': 11, 'fetched': ['basketball_nba', 'tennis_atp_finals', 'americanfootball_nfl', 'soccer_germany_bundesliga', 'soccer_belgium_first_div'], 'matched': 21, 'unmatched': ['soccer_germany_bundesliga: Bayern Munich v 1. FC Köln', 'soccer_belgium_first_div: Cercle Brugge KSV v Westerlo']}

## Providers

- football-data:fixtures: last success 2026-11-14T02:28:13+00:00
- football-data:E0: last success 2026-11-14T02:28:14+00:00
- football-data:E1: last success 2026-11-14T02:28:14+00:00
- football-data:SP1: last success 2026-11-14T02:28:14+00:00
- football-data:D1: last success 2026-11-14T02:28:14+00:00
- football-data:I1: last success 2026-11-14T02:28:14+00:00
- football-data:F1: last success 2026-11-14T02:28:14+00:00
- football-data:N1: last success 2026-11-14T02:28:14+00:00
- football-data:P1: last success 2026-11-14T02:28:14+00:00
- football-data:B1: last success 2026-11-14T02:28:14+00:00
- football-data:SC0: last success 2026-11-14T02:28:14+00:00
- espn:international: last success 2026-11-14T02:29:07+00:00
- the-odds-api: last success 2026-11-14T02:29:22+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-14T02:29:09+00:00
- espn:nba: last success 2026-11-14T02:29:10+00:00
- espn:tennis: last success 2026-11-14T02:29:29+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-14T02:29:15+00:00
