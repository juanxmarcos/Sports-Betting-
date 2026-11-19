# Sports Betting Doyen — diagnostics (2026-11-19 19:12 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 98 → complete history 89 → valid forecast 98 → fresh odds available 94 → stale odds only 0 → three plus bookmakers 54 → fully evaluated 47 → markets evaluated 514 → markets positive ev 49 → events positive ev 35 → events passing all rules 2 → final recommendations 4
  - market rejections: too few bookmakers (248), EV below threshold (185), insufficient team history (57), odds outside range (22)
  - primary blocker per event: prices are in line with the sharp market (40), too few bookmakers price these markets (39), not enough history on one side (9), value only at long odds outside the allowed range (4), no bookmaker prices yet (4), qualified (2)

**NFL**: events discovered 15 → complete history 15 → valid forecast 15 → fresh odds available 15 → stale odds only 0 → three plus bookmakers 15 → fully evaluated 15 → markets evaluated 206 → markets positive ev 8 → events positive ev 5 → events passing all rules 1 → final recommendations 4
  - market rejections: EV below threshold (112), too few bookmakers (84), odds outside range (9)
  - primary blocker per event: prices are in line with the sharp market (7), value only at long odds outside the allowed range (5), too few bookmakers price these markets (2), qualified (1)

**NBA**: events discovered 48 → complete history 48 → valid forecast 48 → fresh odds available 4 → stale odds only 0 → three plus bookmakers 4 → fully evaluated 4 → markets evaluated 56 → markets positive ev 2 → events positive ev 1 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (39), too few bookmakers (14), odds outside range (3)
  - primary blocker per event: no bookmaker prices yet (44), prices are in line with the sharp market (2), value only at long odds outside the allowed range (2)

**TENNIS**: events discovered 38 → complete history 4 → valid forecast 38 → fresh odds available 3 → stale odds only 0 → three plus bookmakers 3 → fully evaluated 3 → markets evaluated 6 → markets positive ev 1 → events positive ev 1 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (5), odds outside range (1)
  - primary blocker per event: no bookmaker prices yet (35), prices are in line with the sharp market (2), value only at long odds outside the allowed range (1)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 94, 'median_odds_age_h': 0.0, 'median_bookmakers': 7.0, 'share_3plus_books': 0.59}
- nfl: {'events_with_odds': 15, 'median_odds_age_h': 0.0, 'median_bookmakers': 22, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 4, 'median_odds_age_h': 0.0, 'median_bookmakers': 23.0, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 3, 'median_odds_age_h': 0.0, 'median_bookmakers': 17, 'share_3plus_books': 1.0}

## The Odds API

{'skipped': None, 'credits_remaining_after': '296', 'credits_spent': 13, 'fetched': ['tennis_atp_finals', 'basketball_nba', 'americanfootball_nfl', 'soccer_germany_bundesliga', 'soccer_belgium_first_div', 'soccer_france_ligue_one'], 'matched': 47, 'unmatched': ['soccer_germany_bundesliga: Borussia Monchengladbach v Borussia Dortmund', 'soccer_france_ligue_one: Nice v Paris Saint Germain'], 'skipped_no_matching_event': [], 'bookmakers_requested': None, 'bookmakers_ignored': None, 'cost_mismatch': None}

## Providers

- football-data:fixtures: last success 2026-11-19T19:10:36+00:00
- football-data:E0: last success 2026-11-19T19:10:37+00:00
- football-data:E1: last success 2026-11-19T19:10:38+00:00
- football-data:SP1: last success 2026-11-19T19:10:40+00:00
- football-data:D1: last success 2026-11-19T19:10:41+00:00
- football-data:I1: last success 2026-11-19T19:10:42+00:00
- football-data:F1: last success 2026-11-19T19:10:43+00:00
- football-data:N1: last success 2026-11-19T19:10:44+00:00
- football-data:P1: last success 2026-11-19T19:10:45+00:00
- football-data:B1: last success 2026-11-19T19:10:46+00:00
- football-data:SC0: last success 2026-11-19T19:10:47+00:00
- espn:international: last success 2026-11-19T19:11:49+00:00
- the-odds-api: last success 2026-11-19T19:12:13+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-19T19:11:51+00:00
- espn:nba: last success 2026-11-19T19:11:53+00:00
- espn:tennis: last success 2026-11-19T19:12:28+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-19T19:12:09+00:00
- espn:club-fixtures: last success 2026-11-19T19:11:07+00:00
