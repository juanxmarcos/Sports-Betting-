# Sports Betting Doyen — diagnostics (2026-11-15 07:49 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 86 → complete history 84 → valid forecast 86 → fresh odds available 30 → stale odds only 0 → three plus bookmakers 26 → fully evaluated 26 → markets evaluated 244 → markets positive ev 21 → events positive ev 16 → events passing all rules 3 → final recommendations 12
  - market rejections: too few bookmakers (122), EV below threshold (104), odds outside range (15)
  - primary blocker per event: no bookmaker prices yet (56), prices are in line with the sharp market (18), value only at long odds outside the allowed range (5), too few bookmakers price these markets (4), qualified (3)

**NFL**: events discovered 14 → complete history 14 → valid forecast 14 → fresh odds available 14 → stale odds only 0 → three plus bookmakers 14 → fully evaluated 14 → markets evaluated 138 → markets positive ev 9 → events positive ev 6 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (82), too few bookmakers (52), odds outside range (4)
  - primary blocker per event: prices are in line with the sharp market (10), value only at long odds outside the allowed range (3), too few bookmakers price these markets (1)

**NBA**: events discovered 53 → complete history 53 → valid forecast 53 → fresh odds available 9 → stale odds only 0 → three plus bookmakers 9 → fully evaluated 9 → markets evaluated 116 → markets positive ev 2 → events positive ev 2 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (58), too few bookmakers (52), odds outside range (6)
  - primary blocker per event: no bookmaker prices yet (44), prices are in line with the sharp market (7), value only at long odds outside the allowed range (2)

**TENNIS**: events discovered 50 → complete history 23 → valid forecast 50 → fresh odds available 4 → stale odds only 0 → three plus bookmakers 4 → fully evaluated 4 → markets evaluated 8 → markets positive ev 3 → events positive ev 3 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (6), odds outside range (2)
  - primary blocker per event: no bookmaker prices yet (46), prices are in line with the sharp market (3), value only at long odds outside the allowed range (1)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 30, 'median_odds_age_h': 1.2, 'median_bookmakers': 16.0, 'share_3plus_books': 0.87}
- nfl: {'events_with_odds': 14, 'median_odds_age_h': 1.2, 'median_bookmakers': 22.0, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 9, 'median_odds_age_h': 1.2, 'median_bookmakers': 23, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 4, 'median_odds_age_h': 1.2, 'median_bookmakers': 17.5, 'share_3plus_books': 1.0}

## The Odds API

{'skipped': None, 'credits_remaining_after': '423', 'credits_spent': 12, 'fetched': ['tennis_atp_finals', 'soccer_uefa_nations_league', 'americanfootball_nfl', 'basketball_nba', 'tennis_wta_finals', 'soccer_germany_bundesliga'], 'matched': 53, 'unmatched': ['soccer_uefa_nations_league: Iceland v Kosovo', 'tennis_wta_finals: Elina Svitolina v Mirra Andreeva', 'soccer_germany_bundesliga: Bayern Munich v 1. FC Köln', 'soccer_germany_bundesliga: Bayer Leverkusen v SC Paderborn', 'soccer_germany_bundesliga: Borussia Monchengladbach v Borussia Dortmund', 'soccer_germany_bundesliga: Eintracht Frankfurt v TSG Hoffenheim', 'soccer_germany_bundesliga: Elversberg v SC Freiburg', 'soccer_germany_bundesliga: Union Berlin v RB Leipzig', 'soccer_germany_bundesliga: FC Schalke 04 v VfB Stuttgart']}

## Providers

- football-data:fixtures: last success 2026-11-15T06:38:17+00:00
- football-data:E0: last success 2026-11-15T06:38:18+00:00
- football-data:E1: last success 2026-11-15T06:38:19+00:00
- football-data:SP1: last success 2026-11-15T06:38:20+00:00
- football-data:D1: last success 2026-11-15T06:38:21+00:00
- football-data:I1: last success 2026-11-15T06:38:22+00:00
- football-data:F1: last success 2026-11-15T06:38:23+00:00
- football-data:N1: last success 2026-11-15T06:38:24+00:00
- football-data:P1: last success 2026-11-15T06:38:25+00:00
- football-data:B1: last success 2026-11-15T06:38:26+00:00
- football-data:SC0: last success 2026-11-15T06:38:27+00:00
- espn:international: last success 2026-11-15T06:39:02+00:00
- the-odds-api: last success 2026-11-15T06:39:11+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-15T06:39:03+00:00
- espn:nba: last success 2026-11-15T06:39:03+00:00
- espn:tennis: last success 2026-11-15T06:39:18+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-15T06:39:07+00:00
