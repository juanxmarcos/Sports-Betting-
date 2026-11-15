# Sports Betting Doyen — diagnostics (2026-11-15 21:04 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 77 → complete history 75 → valid forecast 77 → fresh odds available 30 → stale odds only 0 → three plus bookmakers 18 → fully evaluated 18 → markets evaluated 222 → markets positive ev 20 → events positive ev 12 → events passing all rules 3 → final recommendations 10
  - market rejections: too few bookmakers (125), EV below threshold (78), odds outside range (9), insufficient team history (7)
  - primary blocker per event: no bookmaker prices yet (47), too few bookmakers price these markets (12), prices are in line with the sharp market (11), qualified (3), value only at long odds outside the allowed range (3), not enough history on one side (1)

**NFL**: events discovered 13 → complete history 13 → valid forecast 13 → fresh odds available 6 → stale odds only 7 → three plus bookmakers 6 → fully evaluated 6 → markets evaluated 62 → markets positive ev 5 → events positive ev 4 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (34), too few bookmakers (26), odds outside range (2)
  - primary blocker per event: only stale prices available (7), prices are in line with the sharp market (5), value only at long odds outside the allowed range (1)

**NBA**: events discovered 52 → complete history 52 → valid forecast 52 → fresh odds available 7 → stale odds only 0 → three plus bookmakers 7 → fully evaluated 7 → markets evaluated 96 → markets positive ev 3 → events positive ev 3 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (65), too few bookmakers (26), odds outside range (5)
  - primary blocker per event: no bookmaker prices yet (45), prices are in line with the sharp market (5), value only at long odds outside the allowed range (2)

**TENNIS**: events discovered 44 → complete history 20 → valid forecast 44 → fresh odds available 2 → stale odds only 0 → three plus bookmakers 2 → fully evaluated 2 → markets evaluated 4 → markets positive ev 2 → events positive ev 2 → events passing all rules 0 → final recommendations 0
  - market rejections: odds outside range (2), EV below threshold (2)
  - primary blocker per event: no bookmaker prices yet (42), value only at long odds outside the allowed range (1), prices are in line with the sharp market (1)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 30, 'median_odds_age_h': 0.0, 'median_bookmakers': 15.5, 'share_3plus_books': 0.6}
- nfl: {'events_with_odds': 13, 'median_odds_age_h': 14.4, 'median_bookmakers': 1, 'share_3plus_books': 0.46}
- nba: {'events_with_odds': 7, 'median_odds_age_h': 0.0, 'median_bookmakers': 23, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 2, 'median_odds_age_h': 0.0, 'median_bookmakers': 18.0, 'share_3plus_books': 1.0}

## The Odds API

{'skipped': None, 'credits_remaining_after': '400', 'credits_spent': 11, 'fetched': ['americanfootball_nfl', 'basketball_nba', 'tennis_atp_finals', 'soccer_uefa_nations_league', 'soccer_belgium_first_div'], 'matched': 33, 'unmatched': ['soccer_belgium_first_div: Cercle Brugge KSV v Westerlo', 'soccer_belgium_first_div: Charleroi v Sint Truiden', 'soccer_belgium_first_div: Genk v RAAL La Louvière', 'soccer_belgium_first_div: KV Mechelen v Club Brugge', 'soccer_belgium_first_div: SV Zulte-Waregem v Royal Antwerp', 'soccer_belgium_first_div: SK Beveren v Gent', 'soccer_belgium_first_div: KV Kortrijk v Union Saint-Gilloise', 'soccer_belgium_first_div: Anderlecht v Leuven', 'soccer_belgium_first_div: Lommel SK v Standard Liege']}

## Providers

- football-data:fixtures: last success 2026-11-15T21:04:23+00:00
- football-data:E0: last success 2026-11-15T21:04:24+00:00
- football-data:E1: last success 2026-11-15T21:04:25+00:00
- football-data:SP1: last success 2026-11-15T21:04:26+00:00
- football-data:D1: last success 2026-11-15T21:04:27+00:00
- football-data:I1: last success 2026-11-15T21:04:28+00:00
- football-data:F1: last success 2026-11-15T21:04:29+00:00
- football-data:N1: last success 2026-11-15T21:04:30+00:00
- football-data:P1: last success 2026-11-15T21:04:31+00:00
- football-data:B1: last success 2026-11-15T21:04:32+00:00
- football-data:SC0: last success 2026-11-15T21:04:33+00:00
- espn:international: last success 2026-11-15T21:05:09+00:00
- the-odds-api: last success 2026-11-15T21:05:17+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-15T21:05:10+00:00
- espn:nba: last success 2026-11-15T21:05:10+00:00
- espn:tennis: last success 2026-11-15T21:05:25+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-15T21:05:14+00:00
