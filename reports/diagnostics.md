# Sports Betting Doyen — diagnostics (2026-11-17 23:47 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 5 → complete history 5 → valid forecast 5 → fresh odds available 3 → stale odds only 0 → three plus bookmakers 0 → fully evaluated 0 → markets evaluated 19 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - market rejections: too few bookmakers (19)
  - primary blocker per event: too few bookmakers price these markets (3), no bookmaker prices yet (2)

**NFL**: events discovered 13 → complete history 13 → valid forecast 13 → fresh odds available 13 → stale odds only 0 → three plus bookmakers 13 → fully evaluated 13 → markets evaluated 176 → markets positive ev 6 → events positive ev 4 → events passing all rules 0 → final recommendations 2
  - market rejections: EV below threshold (94), too few bookmakers (72), odds outside range (10)
  - primary blocker per event: prices are in line with the sharp market (9), value only at long odds outside the allowed range (4)

**NBA**: events discovered 53 → complete history 53 → valid forecast 53 → fresh odds available 5 → stale odds only 0 → three plus bookmakers 5 → fully evaluated 5 → markets evaluated 76 → markets positive ev 3 → events positive ev 3 → events passing all rules 1 → final recommendations 1
  - market rejections: EV below threshold (50), too few bookmakers (24), odds outside range (1)
  - primary blocker per event: no bookmaker prices yet (48), prices are in line with the sharp market (4), qualified (1)

**TENNIS**: events discovered 41 → complete history 13 → valid forecast 41 → fresh odds available 2 → stale odds only 0 → three plus bookmakers 2 → fully evaluated 2 → markets evaluated 4 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (3), odds outside range (1)
  - primary blocker per event: no bookmaker prices yet (39), value only at long odds outside the allowed range (1), prices are in line with the sharp market (1)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 3, 'median_odds_age_h': 0.0, 'median_bookmakers': 1, 'share_3plus_books': 0.0}
- nfl: {'events_with_odds': 13, 'median_odds_age_h': 0.0, 'median_bookmakers': 22, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 5, 'median_odds_age_h': 0.0, 'median_bookmakers': 23, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 2, 'median_odds_age_h': 5.6, 'median_bookmakers': 16.0, 'share_3plus_books': 1.0}

## The Odds API

{'skipped': None, 'credits_remaining_after': '352', 'credits_spent': 0, 'fetched': [], 'matched': 0, 'unmatched': [], 'skipped_no_matching_event': ['soccer_epl', 'soccer_efl_champ', 'soccer_spain_la_liga', 'soccer_germany_bundesliga', 'soccer_italy_serie_a', 'soccer_france_ligue_one', 'soccer_netherlands_eredivisie', 'soccer_belgium_first_div', 'soccer_spl'], 'bookmakers_requested': None, 'bookmakers_ignored': None, 'cost_mismatch': None}

## Providers

- football-data:fixtures: last success 2026-11-17T23:47:38+00:00
- football-data:E0: last success 2026-11-17T23:47:38+00:00
- football-data:E1: last success 2026-11-17T23:47:38+00:00
- football-data:SP1: last success 2026-11-17T23:47:39+00:00
- football-data:D1: last success 2026-11-17T23:47:39+00:00
- football-data:I1: last success 2026-11-17T23:47:39+00:00
- football-data:F1: last success 2026-11-17T23:47:39+00:00
- football-data:N1: last success 2026-11-17T23:47:39+00:00
- football-data:P1: last success 2026-11-17T23:47:39+00:00
- football-data:B1: last success 2026-11-17T23:47:39+00:00
- football-data:SC0: last success 2026-11-17T23:47:39+00:00
- espn:international: last success 2026-11-17T23:48:15+00:00
- the-odds-api: last success 2026-11-17T23:48:21+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-17T23:48:16+00:00
- espn:nba: last success 2026-11-17T23:48:17+00:00
- espn:tennis: last success 2026-11-17T23:48:25+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-17T23:48:18+00:00
