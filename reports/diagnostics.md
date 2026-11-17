# Sports Betting Doyen — diagnostics (2026-11-17 04:31 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 53 → complete history 52 → valid forecast 53 → fresh odds available 35 → stale odds only 0 → three plus bookmakers 8 → fully evaluated 8 → markets evaluated 182 → markets positive ev 13 → events positive ev 8 → events passing all rules 2 → final recommendations 4
  - market rejections: too few bookmakers (140), EV below threshold (39), odds outside range (1)
  - primary blocker per event: too few bookmakers price these markets (27), no bookmaker prices yet (18), prices are in line with the sharp market (5), qualified (2), value only at long odds outside the allowed range (1)

**NFL**: events discovered 13 → complete history 13 → valid forecast 13 → fresh odds available 13 → stale odds only 0 → three plus bookmakers 13 → fully evaluated 13 → markets evaluated 200 → markets positive ev 14 → events positive ev 9 → events passing all rules 1 → final recommendations 2
  - market rejections: EV below threshold (139), too few bookmakers (50), odds outside range (10)
  - primary blocker per event: prices are in line with the sharp market (9), value only at long odds outside the allowed range (2), too few bookmakers price these markets (1), qualified (1)

**NBA**: events discovered 53 → complete history 53 → valid forecast 53 → fresh odds available 5 → stale odds only 0 → three plus bookmakers 5 → fully evaluated 5 → markets evaluated 78 → markets positive ev 1 → events positive ev 1 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (44), too few bookmakers (34)
  - primary blocker per event: no bookmaker prices yet (48), prices are in line with the sharp market (5)

**TENNIS**: events discovered 50 → complete history 15 → valid forecast 50 → fresh odds available 4 → stale odds only 0 → three plus bookmakers 4 → fully evaluated 4 → markets evaluated 8 → markets positive ev 3 → events positive ev 3 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (7), odds outside range (1)
  - primary blocker per event: no bookmaker prices yet (46), prices are in line with the sharp market (3), value only at long odds outside the allowed range (1)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 35, 'median_odds_age_h': 0.0, 'median_bookmakers': 1, 'share_3plus_books': 0.23}
- nfl: {'events_with_odds': 13, 'median_odds_age_h': 0.0, 'median_bookmakers': 22, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 5, 'median_odds_age_h': 0.0, 'median_bookmakers': 21, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 4, 'median_odds_age_h': 0.0, 'median_bookmakers': 15.0, 'share_3plus_books': 1.0}

## The Odds API

{'skipped': None, 'credits_remaining_after': '364', 'credits_spent': 11, 'fetched': ['tennis_atp_finals', 'soccer_uefa_nations_league', 'basketball_nba', 'americanfootball_nfl', 'soccer_germany_bundesliga'], 'matched': 30, 'unmatched': ['soccer_germany_bundesliga: Bayern Munich v 1. FC Köln', 'soccer_germany_bundesliga: Bayer Leverkusen v SC Paderborn', 'soccer_germany_bundesliga: Borussia Monchengladbach v Borussia Dortmund', 'soccer_germany_bundesliga: Eintracht Frankfurt v TSG Hoffenheim', 'soccer_germany_bundesliga: Elversberg v SC Freiburg', 'soccer_germany_bundesliga: Union Berlin v RB Leipzig', 'soccer_germany_bundesliga: FC Schalke 04 v VfB Stuttgart', 'soccer_germany_bundesliga: Augsburg v FSV Mainz 05', 'soccer_germany_bundesliga: Werder Bremen v Hamburger SV']}

## Providers

- football-data:fixtures: last success 2026-11-17T04:31:03+00:00
- football-data:E0: last success 2026-11-17T04:31:04+00:00
- football-data:E1: last success 2026-11-17T04:31:05+00:00
- football-data:SP1: last success 2026-11-17T04:31:06+00:00
- football-data:D1: last success 2026-11-17T04:31:07+00:00
- football-data:I1: last success 2026-11-17T04:31:08+00:00
- football-data:F1: last success 2026-11-17T04:31:09+00:00
- football-data:N1: last success 2026-11-17T04:31:11+00:00
- football-data:P1: last success 2026-11-17T04:31:12+00:00
- football-data:B1: last success 2026-11-17T04:31:13+00:00
- football-data:SC0: last success 2026-11-17T04:31:14+00:00
- espn:international: last success 2026-11-17T04:31:56+00:00
- the-odds-api: last success 2026-11-17T04:32:12+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-17T04:31:57+00:00
- espn:nba: last success 2026-11-17T04:31:58+00:00
- espn:tennis: last success 2026-11-17T04:32:17+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-17T04:32:06+00:00
