# Sports Betting Doyen — diagnostics (2026-11-21 14:03 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 87 → complete history 79 → valid forecast 87 → fresh odds available 83 → stale odds only 0 → three plus bookmakers 48 → fully evaluated 42 → markets evaluated 457 → markets positive ev 45 → events positive ev 31 → events passing all rules 2 → final recommendations 4
  - market rejections: too few bookmakers (219), EV below threshold (164), insufficient team history (54), odds outside range (18)
  - primary blocker per event: prices are in line with the sharp market (35), too few bookmakers price these markets (34), not enough history on one side (8), value only at long odds outside the allowed range (4), no bookmaker prices yet (4), qualified (2)

**NFL**: events discovered 15 → complete history 15 → valid forecast 15 → fresh odds available 15 → stale odds only 0 → three plus bookmakers 14 → fully evaluated 14 → markets evaluated 196 → markets positive ev 8 → events positive ev 5 → events passing all rules 1 → final recommendations 4
  - market rejections: EV below threshold (110), too few bookmakers (78), odds outside range (7)
  - primary blocker per event: prices are in line with the sharp market (7), value only at long odds outside the allowed range (4), too few bookmakers price these markets (3), qualified (1)

**NBA**: events discovered 35 → complete history 35 → valid forecast 35 → fresh odds available 0 → stale odds only 0 → three plus bookmakers 0 → fully evaluated 0 → markets evaluated 0 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - primary blocker per event: no bookmaker prices yet (35)

**TENNIS**: events discovered 26 → complete history 0 → valid forecast 26 → fresh odds available 0 → stale odds only 0 → three plus bookmakers 0 → fully evaluated 0 → markets evaluated 0 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - primary blocker per event: no bookmaker prices yet (26)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 83, 'median_odds_age_h': 40.4, 'median_bookmakers': 7, 'share_3plus_books': 0.58}
- nfl: {'events_with_odds': 16, 'median_odds_age_h': 40.4, 'median_bookmakers': 22.0, 'share_3plus_books': 0.88}
- nba: {'events_with_odds': 0, 'median_odds_age_h': None, 'median_bookmakers': None, 'share_3plus_books': None}
- tennis: {'events_with_odds': 0, 'median_odds_age_h': None, 'median_bookmakers': None, 'share_3plus_books': None}

## The Odds API

{'skipped': None, 'credits_remaining_after': '296', 'credits_spent': 0, 'fetched': [], 'matched': 0, 'unmatched': [], 'skipped_no_matching_event': [], 'bookmakers_requested': None, 'bookmakers_ignored': None, 'cost_mismatch': None}

## Providers

- football-data:fixtures: last success 2026-11-19T21:41:09+00:00
- football-data:E0: last success 2026-11-19T21:41:09+00:00
- football-data:E1: last success 2026-11-19T21:41:09+00:00
- football-data:SP1: last success 2026-11-19T21:41:09+00:00
- football-data:D1: last success 2026-11-19T21:41:09+00:00
- football-data:I1: last success 2026-11-19T21:41:09+00:00
- football-data:F1: last success 2026-11-19T21:41:09+00:00
- football-data:N1: last success 2026-11-19T21:41:09+00:00
- football-data:P1: last success 2026-11-19T21:41:10+00:00
- football-data:B1: last success 2026-11-19T21:41:10+00:00
- football-data:SC0: last success 2026-11-19T21:41:10+00:00
- espn:international: last success 2026-11-19T21:42:20+00:00
- the-odds-api: last success 2026-11-19T21:42:43+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-19T21:42:21+00:00
- espn:nba: last success 2026-11-19T21:42:22+00:00
- espn:tennis: last success 2026-11-19T21:42:54+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-19T21:42:39+00:00
- espn:club-fixtures: last success 2026-11-19T21:41:36+00:00
