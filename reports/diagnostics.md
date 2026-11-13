# Sports Betting Doyen — diagnostics (2026-11-13 20:55 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 115 → complete history 112 → valid forecast 115 → fresh odds available 42 → stale odds only 0 → three plus bookmakers 28 → fully evaluated 28 → markets evaluated 268 → markets positive ev 22 → events positive ev 17 → events passing all rules 2 → final recommendations 5
  - market rejections: too few bookmakers (130), EV below threshold (119), odds outside range (16)
  - primary blocker per event: no bookmaker prices yet (73), prices are in line with the sharp market (21), too few bookmakers price these markets (14), value only at long odds outside the allowed range (5), qualified (2)

**NFL**: events discovered 14 → complete history 14 → valid forecast 14 → fresh odds available 14 → stale odds only 0 → three plus bookmakers 14 → fully evaluated 14 → markets evaluated 180 → markets positive ev 7 → events positive ev 6 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (118), too few bookmakers (58), odds outside range (4)
  - primary blocker per event: prices are in line with the sharp market (12), value only at long odds outside the allowed range (2)

**NBA**: events discovered 52 → complete history 52 → valid forecast 52 → fresh odds available 9 → stale odds only 0 → three plus bookmakers 9 → fully evaluated 9 → markets evaluated 108 → markets positive ev 4 → events positive ev 2 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (72), too few bookmakers (30), odds outside range (6)
  - primary blocker per event: no bookmaker prices yet (43), prices are in line with the sharp market (6), value only at long odds outside the allowed range (3)

**TENNIS**: events discovered 46 → complete history 13 → valid forecast 46 → fresh odds available 5 → stale odds only 0 → three plus bookmakers 5 → fully evaluated 5 → markets evaluated 10 → markets positive ev 2 → events positive ev 2 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (7), odds outside range (3)
  - primary blocker per event: no bookmaker prices yet (41), prices are in line with the sharp market (3), value only at long odds outside the allowed range (2)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 42, 'median_odds_age_h': 0.0, 'median_bookmakers': 11.0, 'share_3plus_books': 0.67}
- nfl: {'events_with_odds': 14, 'median_odds_age_h': 0.0, 'median_bookmakers': 22.0, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 9, 'median_odds_age_h': 0.0, 'median_bookmakers': 21, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 5, 'median_odds_age_h': 8.6, 'median_bookmakers': 5, 'share_3plus_books': 1.0}

## The Odds API

{'skipped': None, 'credits_remaining_after': '460', 'credits_spent': 12, 'fetched': ['tennis_wta_finals', 'basketball_nba', 'soccer_uefa_nations_league', 'soccer_germany_bundesliga', 'soccer_belgium_first_div', 'soccer_france_ligue_one'], 'matched': 38, 'unmatched': ['tennis_wta_finals: Jessica Pegula v Mirra Andreeva', 'soccer_uefa_nations_league: Austria v Iceland', 'soccer_germany_bundesliga: Bayern Munich v 1. FC Köln', 'soccer_belgium_first_div: Cercle Brugge KSV v Westerlo', 'soccer_france_ligue_one: Troyes v Le Havre']}

## Providers

- football-data:fixtures: last success 2026-11-13T20:55:13+00:00
- football-data:E0: last success 2026-11-13T20:55:14+00:00
- football-data:E1: last success 2026-11-13T20:55:15+00:00
- football-data:SP1: last success 2026-11-13T20:55:16+00:00
- football-data:D1: last success 2026-11-13T20:55:17+00:00
- football-data:I1: last success 2026-11-13T20:55:18+00:00
- football-data:F1: last success 2026-11-13T20:55:19+00:00
- football-data:N1: last success 2026-11-13T20:55:20+00:00
- football-data:P1: last success 2026-11-13T20:55:21+00:00
- football-data:B1: last success 2026-11-13T20:55:22+00:00
- football-data:SC0: last success 2026-11-13T20:55:23+00:00
- espn:international: last success 2026-11-13T20:55:58+00:00
- the-odds-api: last success 2026-11-13T20:56:06+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-13T20:55:58+00:00
- espn:nba: last success 2026-11-13T20:55:59+00:00
- espn:tennis: last success 2026-11-13T20:56:12+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-13T20:56:02+00:00
