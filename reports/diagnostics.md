# Sports Betting Doyen — diagnostics (2026-11-18 14:54 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: 

**NFL**: events discovered 13 → complete history 13 → valid forecast 13 → fresh odds available 13 → stale odds only 0 → three plus bookmakers 13 → fully evaluated 13 → markets evaluated 174 → markets positive ev 4 → events positive ev 4 → events passing all rules 1 → final recommendations 3
  - market rejections: EV below threshold (111), too few bookmakers (52), odds outside range (10)
  - primary blocker per event: prices are in line with the sharp market (8), value only at long odds outside the allowed range (3), too few bookmakers price these markets (1), qualified (1)

**NBA**: events discovered 51 → complete history 51 → valid forecast 51 → fresh odds available 12 → stale odds only 0 → three plus bookmakers 12 → fully evaluated 12 → markets evaluated 168 → markets positive ev 5 → events positive ev 5 → events passing all rules 0 → final recommendations 1
  - market rejections: EV below threshold (91), too few bookmakers (74), odds outside range (3)
  - primary blocker per event: no bookmaker prices yet (39), prices are in line with the sharp market (10), value only at long odds outside the allowed range (1), too few bookmakers price these markets (1)

**TENNIS**: events discovered 46 → complete history 11 → valid forecast 46 → fresh odds available 3 → stale odds only 0 → three plus bookmakers 3 → fully evaluated 3 → markets evaluated 6 → markets positive ev 2 → events positive ev 1 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (6)
  - primary blocker per event: no bookmaker prices yet (43), prices are in line with the sharp market (3)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 0, 'median_odds_age_h': None, 'median_bookmakers': None, 'share_3plus_books': None}
- nfl: {'events_with_odds': 13, 'median_odds_age_h': 0.0, 'median_bookmakers': 22, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 12, 'median_odds_age_h': 0.0, 'median_bookmakers': 23.0, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 3, 'median_odds_age_h': 0.0, 'median_bookmakers': 16, 'share_3plus_books': 1.0}

## The Odds API

{'skipped': None, 'credits_remaining_after': '339', 'credits_spent': 7, 'fetched': ['tennis_atp_finals', 'basketball_nba', 'americanfootball_nfl'], 'matched': 28, 'unmatched': [], 'skipped_no_matching_event': ['soccer_epl', 'soccer_efl_champ', 'soccer_spain_la_liga', 'soccer_germany_bundesliga', 'soccer_italy_serie_a', 'soccer_france_ligue_one', 'soccer_netherlands_eredivisie', 'soccer_belgium_first_div', 'soccer_spl'], 'bookmakers_requested': None, 'bookmakers_ignored': None, 'cost_mismatch': None}

## Providers

- football-data:fixtures: last success 2026-11-18T14:54:08+00:00
- football-data:E0: last success 2026-11-18T14:54:09+00:00
- football-data:E1: last success 2026-11-18T14:54:11+00:00
- football-data:SP1: last success 2026-11-18T14:54:12+00:00
- football-data:D1: last success 2026-11-18T14:54:14+00:00
- football-data:I1: last success 2026-11-18T14:54:15+00:00
- football-data:F1: last success 2026-11-18T14:54:16+00:00
- football-data:N1: last success 2026-11-18T14:54:18+00:00
- football-data:P1: last success 2026-11-18T14:54:19+00:00
- football-data:B1: last success 2026-11-18T14:54:20+00:00
- football-data:SC0: last success 2026-11-18T14:54:22+00:00
- espn:international: last success 2026-11-18T14:55:29+00:00
- the-odds-api: last success 2026-11-18T14:55:50+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-18T14:55:33+00:00
- espn:nba: last success 2026-11-18T14:55:34+00:00
- espn:tennis: last success 2026-11-18T14:55:56+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-18T14:55:43+00:00
