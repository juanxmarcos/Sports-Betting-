# Sports Betting Doyen — diagnostics (2026-11-18 23:04 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 98 → complete history 89 → valid forecast 98 → fresh odds available 94 → stale odds only 0 → three plus bookmakers 55 → fully evaluated 48 → markets evaluated 758 → markets positive ev 54 → events positive ev 34 → events passing all rules 3 → final recommendations 4
  - market rejections: too few bookmakers (427), EV below threshold (221), insufficient team history (85), odds outside range (22)
  - primary blocker per event: prices are in line with the sharp market (39), too few bookmakers price these markets (38), not enough history on one side (9), value only at long odds outside the allowed range (5), no bookmaker prices yet (4), qualified (3)

**NFL**: events discovered 13 → complete history 13 → valid forecast 13 → fresh odds available 13 → stale odds only 0 → three plus bookmakers 13 → fully evaluated 13 → markets evaluated 178 → markets positive ev 6 → events positive ev 5 → events passing all rules 1 → final recommendations 3
  - market rejections: EV below threshold (109), too few bookmakers (58), odds outside range (10)
  - primary blocker per event: prices are in line with the sharp market (8), value only at long odds outside the allowed range (3), too few bookmakers price these markets (1), qualified (1)

**NBA**: events discovered 52 → complete history 52 → valid forecast 52 → fresh odds available 12 → stale odds only 0 → three plus bookmakers 12 → fully evaluated 12 → markets evaluated 178 → markets positive ev 9 → events positive ev 6 → events passing all rules 1 → final recommendations 2
  - market rejections: EV below threshold (118), too few bookmakers (56), odds outside range (3)
  - primary blocker per event: no bookmaker prices yet (40), prices are in line with the sharp market (9), value only at long odds outside the allowed range (2), qualified (1)

**TENNIS**: events discovered 42 → complete history 7 → valid forecast 42 → fresh odds available 2 → stale odds only 0 → three plus bookmakers 2 → fully evaluated 2 → markets evaluated 4 → markets positive ev 1 → events positive ev 1 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (4)
  - primary blocker per event: no bookmaker prices yet (40), prices are in line with the sharp market (2)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 94, 'median_odds_age_h': 0.0, 'median_bookmakers': 7.0, 'share_3plus_books': 0.59}
- nfl: {'events_with_odds': 13, 'median_odds_age_h': 0.0, 'median_bookmakers': 22, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 12, 'median_odds_age_h': 0.0, 'median_bookmakers': 23.0, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 2, 'median_odds_age_h': 5.9, 'median_bookmakers': 16.0, 'share_3plus_books': 1.0}

## The Odds API

{'skipped': None, 'credits_remaining_after': '321', 'credits_spent': 0, 'fetched': [], 'matched': 0, 'unmatched': [], 'skipped_no_matching_event': [], 'bookmakers_requested': None, 'bookmakers_ignored': None, 'cost_mismatch': None}

## Providers

- football-data:fixtures: last success 2026-11-18T23:02:45+00:00
- football-data:E0: last success 2026-11-18T23:02:45+00:00
- football-data:E1: last success 2026-11-18T23:02:45+00:00
- football-data:SP1: last success 2026-11-18T23:02:45+00:00
- football-data:D1: last success 2026-11-18T23:02:45+00:00
- football-data:I1: last success 2026-11-18T23:02:45+00:00
- football-data:F1: last success 2026-11-18T23:02:45+00:00
- football-data:N1: last success 2026-11-18T23:02:45+00:00
- football-data:P1: last success 2026-11-18T23:02:45+00:00
- football-data:B1: last success 2026-11-18T23:02:45+00:00
- football-data:SC0: last success 2026-11-18T23:02:45+00:00
- espn:international: last success 2026-11-18T23:03:48+00:00
- the-odds-api: last success 2026-11-18T23:04:03+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-18T23:03:49+00:00
- espn:nba: last success 2026-11-18T23:03:49+00:00
- espn:tennis: last success 2026-11-18T23:04:12+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-18T23:03:57+00:00
- espn:club-fixtures: last success 2026-11-18T23:03:09+00:00
