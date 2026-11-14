# Sports Betting Doyen — diagnostics (2026-11-14 11:31 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 105 → complete history 103 → valid forecast 105 → fresh odds available 43 → stale odds only 0 → three plus bookmakers 34 → fully evaluated 34 → markets evaluated 305 → markets positive ev 34 → events positive ev 23 → events passing all rules 6 → final recommendations 9
  - market rejections: EV below threshold (145), too few bookmakers (135), odds outside range (19)
  - primary blocker per event: no bookmaker prices yet (62), prices are in line with the sharp market (21), too few bookmakers price these markets (11), qualified (6), value only at long odds outside the allowed range (5)

**NFL**: events discovered 14 → complete history 14 → valid forecast 14 → fresh odds available 14 → stale odds only 0 → three plus bookmakers 14 → fully evaluated 14 → markets evaluated 156 → markets positive ev 5 → events positive ev 5 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (92), too few bookmakers (60), odds outside range (4)
  - primary blocker per event: prices are in line with the sharp market (11), value only at long odds outside the allowed range (3)

**NBA**: events discovered 52 → complete history 52 → valid forecast 52 → fresh odds available 5 → stale odds only 0 → three plus bookmakers 5 → fully evaluated 5 → markets evaluated 74 → markets positive ev 3 → events positive ev 3 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (45), too few bookmakers (26), odds outside range (3)
  - primary blocker per event: no bookmaker prices yet (47), prices are in line with the sharp market (5)

**TENNIS**: events discovered 45 → complete history 12 → valid forecast 45 → fresh odds available 4 → stale odds only 0 → three plus bookmakers 4 → fully evaluated 4 → markets evaluated 8 → markets positive ev 2 → events positive ev 1 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (6), odds outside range (2)
  - primary blocker per event: no bookmaker prices yet (41), prices are in line with the sharp market (3), value only at long odds outside the allowed range (1)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 43, 'median_odds_age_h': 0.0, 'median_bookmakers': 12, 'share_3plus_books': 0.79}
- nfl: {'events_with_odds': 14, 'median_odds_age_h': 0.0, 'median_bookmakers': 22.0, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 5, 'median_odds_age_h': 0.0, 'median_bookmakers': 23, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 4, 'median_odds_age_h': 0.0, 'median_bookmakers': 17.5, 'share_3plus_books': 1.0}

## The Odds API

{'skipped': None, 'credits_remaining_after': '437', 'credits_spent': 12, 'fetched': ['soccer_uefa_nations_league', 'tennis_wta_finals', 'basketball_nba', 'tennis_atp_finals', 'americanfootball_nfl', 'soccer_france_ligue_one'], 'matched': 57, 'unmatched': ['soccer_uefa_nations_league: Austria v Iceland', 'tennis_wta_finals: Jessica Pegula v Mirra Andreeva', 'tennis_wta_finals: Linda Noskova v Elina Svitolina', 'soccer_france_ligue_one: Troyes v Le Havre']}

## Providers

- football-data:fixtures: last success 2026-11-14T11:31:21+00:00
- football-data:E0: last success 2026-11-14T11:31:22+00:00
- football-data:E1: last success 2026-11-14T11:31:23+00:00
- football-data:SP1: last success 2026-11-14T11:31:24+00:00
- football-data:D1: last success 2026-11-14T11:31:25+00:00
- football-data:I1: last success 2026-11-14T11:31:26+00:00
- football-data:F1: last success 2026-11-14T11:31:27+00:00
- football-data:N1: last success 2026-11-14T11:31:28+00:00
- football-data:P1: last success 2026-11-14T11:31:29+00:00
- football-data:B1: last success 2026-11-14T11:31:30+00:00
- football-data:SC0: last success 2026-11-14T11:31:31+00:00
- espn:international: last success 2026-11-14T11:32:15+00:00
- the-odds-api: last success 2026-11-14T11:32:30+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-14T11:32:17+00:00
- espn:nba: last success 2026-11-14T11:32:18+00:00
- espn:tennis: last success 2026-11-14T11:32:37+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-14T11:32:25+00:00
