# Sports Betting Doyen — diagnostics (2026-11-19 03:55 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 98 → complete history 89 → valid forecast 98 → fresh odds available 94 → stale odds only 0 → three plus bookmakers 55 → fully evaluated 48 → markets evaluated 566 → markets positive ev 58 → events positive ev 34 → events passing all rules 3 → final recommendations 4
  - market rejections: too few bookmakers (249), EV below threshold (221), insufficient team history (71), odds outside range (22)
  - primary blocker per event: prices are in line with the sharp market (39), too few bookmakers price these markets (38), not enough history on one side (9), value only at long odds outside the allowed range (5), no bookmaker prices yet (4), qualified (3)

**NFL**: events discovered 14 → complete history 14 → valid forecast 14 → fresh odds available 14 → stale odds only 0 → three plus bookmakers 12 → fully evaluated 12 → markets evaluated 142 → markets positive ev 7 → events positive ev 5 → events passing all rules 1 → final recommendations 3
  - market rejections: too few bookmakers (74), EV below threshold (59), odds outside range (8)
  - primary blocker per event: prices are in line with the sharp market (6), value only at long odds outside the allowed range (4), too few bookmakers price these markets (3), qualified (1)

**NBA**: events discovered 48 → complete history 48 → valid forecast 48 → fresh odds available 1 → stale odds only 0 → three plus bookmakers 0 → fully evaluated 0 → markets evaluated 6 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - market rejections: too few bookmakers (6)
  - primary blocker per event: no bookmaker prices yet (47), too few bookmakers price these markets (1)

**TENNIS**: events discovered 42 → complete history 8 → valid forecast 42 → fresh odds available 4 → stale odds only 0 → three plus bookmakers 4 → fully evaluated 4 → markets evaluated 8 → markets positive ev 2 → events positive ev 2 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (6), odds outside range (2)
  - primary blocker per event: no bookmaker prices yet (38), prices are in line with the sharp market (3), value only at long odds outside the allowed range (1)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 94, 'median_odds_age_h': 0.0, 'median_bookmakers': 7.0, 'share_3plus_books': 0.59}
- nfl: {'events_with_odds': 14, 'median_odds_age_h': 0.0, 'median_bookmakers': 22.0, 'share_3plus_books': 0.93}
- nba: {'events_with_odds': 1, 'median_odds_age_h': 0.0, 'median_bookmakers': 1, 'share_3plus_books': 0.0}
- tennis: {'events_with_odds': 4, 'median_odds_age_h': 0.0, 'median_bookmakers': 15.0, 'share_3plus_books': 1.0}

## The Odds API

{'skipped': None, 'credits_remaining_after': '320', 'credits_spent': 1, 'fetched': ['tennis_atp_finals'], 'matched': 4, 'unmatched': [], 'skipped_no_matching_event': [], 'bookmakers_requested': None, 'bookmakers_ignored': None, 'cost_mismatch': None}

## Providers

- football-data:fixtures: last success 2026-11-19T03:53:23+00:00
- football-data:E0: last success 2026-11-19T03:53:23+00:00
- football-data:E1: last success 2026-11-19T03:53:23+00:00
- football-data:SP1: last success 2026-11-19T03:53:23+00:00
- football-data:D1: last success 2026-11-19T03:53:23+00:00
- football-data:I1: last success 2026-11-19T03:53:23+00:00
- football-data:F1: last success 2026-11-19T03:53:24+00:00
- football-data:N1: last success 2026-11-19T03:53:24+00:00
- football-data:P1: last success 2026-11-19T03:53:24+00:00
- football-data:B1: last success 2026-11-19T03:53:24+00:00
- football-data:SC0: last success 2026-11-19T03:53:24+00:00
- espn:international: last success 2026-11-19T03:54:42+00:00
- the-odds-api: last success 2026-11-19T03:55:02+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-19T03:54:43+00:00
- espn:nba: last success 2026-11-19T03:54:45+00:00
- espn:tennis: last success 2026-11-19T03:55:12+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-19T03:54:57+00:00
- espn:club-fixtures: last success 2026-11-19T03:53:54+00:00
