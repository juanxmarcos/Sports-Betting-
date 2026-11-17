# Sports Betting Doyen — diagnostics (2026-11-17 16:05 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 29 → complete history 29 → valid forecast 29 → fresh odds available 21 → stale odds only 0 → three plus bookmakers 8 → fully evaluated 8 → markets evaluated 167 → markets positive ev 9 → events positive ev 5 → events passing all rules 0 → final recommendations 4
  - market rejections: too few bookmakers (129), EV below threshold (37), odds outside range (1)
  - primary blocker per event: too few bookmakers price these markets (13), no bookmaker prices yet (8), prices are in line with the sharp market (8)

**NFL**: events discovered 13 → complete history 13 → valid forecast 13 → fresh odds available 13 → stale odds only 0 → three plus bookmakers 13 → fully evaluated 13 → markets evaluated 170 → markets positive ev 6 → events positive ev 4 → events passing all rules 0 → final recommendations 2
  - market rejections: EV below threshold (98), too few bookmakers (62), odds outside range (10)
  - primary blocker per event: prices are in line with the sharp market (9), value only at long odds outside the allowed range (4)

**NBA**: events discovered 53 → complete history 53 → valid forecast 53 → fresh odds available 5 → stale odds only 0 → three plus bookmakers 5 → fully evaluated 5 → markets evaluated 90 → markets positive ev 2 → events positive ev 2 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (55), too few bookmakers (34), odds outside range (1)
  - primary blocker per event: no bookmaker prices yet (48), prices are in line with the sharp market (4), value only at long odds outside the allowed range (1)

**TENNIS**: events discovered 46 → complete history 13 → valid forecast 46 → fresh odds available 3 → stale odds only 0 → three plus bookmakers 3 → fully evaluated 3 → markets evaluated 6 → markets positive ev 1 → events positive ev 1 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (5), odds outside range (1)
  - primary blocker per event: no bookmaker prices yet (43), prices are in line with the sharp market (2), value only at long odds outside the allowed range (1)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 21, 'median_odds_age_h': 0.0, 'median_bookmakers': 1, 'share_3plus_books': 0.38}
- nfl: {'events_with_odds': 13, 'median_odds_age_h': 0.0, 'median_bookmakers': 22, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 5, 'median_odds_age_h': 0.0, 'median_bookmakers': 23, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 3, 'median_odds_age_h': 0.0, 'median_bookmakers': 16, 'share_3plus_books': 1.0}

## The Odds API

{'skipped': None, 'credits_remaining_after': '358', 'credits_spent': 6, 'fetched': ['tennis_atp_finals', 'soccer_uefa_nations_league', 'basketball_nba'], 'matched': 16, 'unmatched': [], 'skipped_no_matching_event': ['soccer_epl', 'soccer_efl_champ', 'soccer_spain_la_liga', 'soccer_germany_bundesliga', 'soccer_italy_serie_a', 'soccer_france_ligue_one', 'soccer_netherlands_eredivisie', 'soccer_belgium_first_div', 'soccer_spl'], 'bookmakers_requested': None, 'bookmakers_ignored': None, 'cost_mismatch': None}

## Providers

- football-data:fixtures: last success 2026-11-17T16:05:09+00:00
- football-data:E0: last success 2026-11-17T16:05:13+00:00
- football-data:E1: last success 2026-11-17T16:05:16+00:00
- football-data:SP1: last success 2026-11-17T16:05:20+00:00
- football-data:D1: last success 2026-11-17T16:05:26+00:00
- football-data:I1: last success 2026-11-17T16:05:28+00:00
- football-data:F1: last success 2026-11-17T16:05:32+00:00
- football-data:N1: last success 2026-11-17T16:05:35+00:00
- football-data:P1: last success 2026-11-17T16:05:39+00:00
- football-data:B1: last success 2026-11-17T16:05:43+00:00
- football-data:SC0: last success 2026-11-17T16:05:47+00:00
- espn:international: last success 2026-11-17T16:06:18+00:00
- the-odds-api: last success 2026-11-17T16:06:26+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-17T16:06:19+00:00
- espn:nba: last success 2026-11-17T16:06:20+00:00
- espn:tennis: last success 2026-11-17T16:06:33+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-17T16:06:23+00:00
