# Sports Betting Doyen — diagnostics (2026-11-13 12:15 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 146 → complete history 143 → valid forecast 146 → fresh odds available 57 → stale odds only 0 → three plus bookmakers 26 → fully evaluated 26 → markets evaluated 343 → markets positive ev 33 → events positive ev 20 → events passing all rules 2 → final recommendations 5
  - market rejections: too few bookmakers (219), EV below threshold (98), odds outside range (24)
  - primary blocker per event: no bookmaker prices yet (89), too few bookmakers price these markets (37), prices are in line with the sharp market (13), value only at long odds outside the allowed range (5), qualified (2)

**NFL**: events discovered 14 → complete history 14 → valid forecast 14 → fresh odds available 14 → stale odds only 0 → three plus bookmakers 14 → fully evaluated 14 → markets evaluated 180 → markets positive ev 7 → events positive ev 6 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (119), too few bookmakers (56), odds outside range (5)
  - primary blocker per event: prices are in line with the sharp market (12), value only at long odds outside the allowed range (2)

**NBA**: events discovered 52 → complete history 52 → valid forecast 52 → fresh odds available 9 → stale odds only 0 → three plus bookmakers 9 → fully evaluated 9 → markets evaluated 116 → markets positive ev 1 → events positive ev 1 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (70), too few bookmakers (40), odds outside range (6)
  - primary blocker per event: no bookmaker prices yet (43), prices are in line with the sharp market (6), value only at long odds outside the allowed range (2), too few bookmakers price these markets (1)

**TENNIS**: events discovered 51 → complete history 17 → valid forecast 51 → fresh odds available 6 → stale odds only 0 → three plus bookmakers 6 → fully evaluated 6 → markets evaluated 12 → markets positive ev 3 → events positive ev 3 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (9), odds outside range (3)
  - primary blocker per event: no bookmaker prices yet (45), prices are in line with the sharp market (4), value only at long odds outside the allowed range (2)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 57, 'median_odds_age_h': 0.0, 'median_bookmakers': 1, 'share_3plus_books': 0.46}
- nfl: {'events_with_odds': 14, 'median_odds_age_h': 0.0, 'median_bookmakers': 22.0, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 9, 'median_odds_age_h': 0.0, 'median_bookmakers': 21, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 6, 'median_odds_age_h': 0.0, 'median_bookmakers': 5.0, 'share_3plus_books': 1.0}

## The Odds API

{'skipped': None, 'credits_remaining_after': '472', 'credits_spent': 7, 'fetched': ['soccer_uefa_nations_league', 'tennis_wta_finals', 'basketball_nba', 'tennis_atp_finals'], 'matched': 41, 'unmatched': ['soccer_uefa_nations_league: Austria v Iceland']}

## Providers

- football-data:fixtures: last success 2026-11-13T12:16:00+00:00
- football-data:E0: last success 2026-11-13T12:16:01+00:00
- football-data:E1: last success 2026-11-13T12:16:02+00:00
- football-data:SP1: last success 2026-11-13T12:16:04+00:00
- football-data:D1: last success 2026-11-13T12:16:05+00:00
- football-data:I1: last success 2026-11-13T12:16:06+00:00
- football-data:F1: last success 2026-11-13T12:16:07+00:00
- football-data:N1: last success 2026-11-13T12:16:08+00:00
- football-data:P1: last success 2026-11-13T12:16:09+00:00
- football-data:B1: last success 2026-11-13T12:16:10+00:00
- football-data:SC0: last success 2026-11-13T12:16:10+00:00
- espn:international: last success 2026-11-13T12:16:44+00:00
- the-odds-api: last success 2026-11-13T12:16:52+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-13T12:16:45+00:00
- espn:nba: last success 2026-11-13T12:16:45+00:00
- espn:tennis: last success 2026-11-13T12:17:02+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-13T12:16:50+00:00
