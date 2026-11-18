# Sports Betting Doyen — diagnostics (2026-11-18 17:24 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 94 → complete history 85 → valid forecast 94 → fresh odds available 84 → stale odds only 0 → three plus bookmakers 17 → fully evaluated 12 → markets evaluated 646 → markets positive ev 16 → events positive ev 10 → events passing all rules 1 → final recommendations 1
  - market rejections: too few bookmakers (487), insufficient team history (81), EV below threshold (70), odds outside range (7)
  - primary blocker per event: too few bookmakers price these markets (63), no bookmaker prices yet (10), prices are in line with the sharp market (9), not enough history on one side (9), value only at long odds outside the allowed range (2), qualified (1)

**NFL**: events discovered 13 → complete history 13 → valid forecast 13 → fresh odds available 13 → stale odds only 0 → three plus bookmakers 13 → fully evaluated 13 → markets evaluated 174 → markets positive ev 4 → events positive ev 4 → events passing all rules 1 → final recommendations 3
  - market rejections: EV below threshold (111), too few bookmakers (52), odds outside range (10)
  - primary blocker per event: prices are in line with the sharp market (8), value only at long odds outside the allowed range (3), too few bookmakers price these markets (1), qualified (1)

**NBA**: events discovered 51 → complete history 51 → valid forecast 51 → fresh odds available 12 → stale odds only 0 → three plus bookmakers 12 → fully evaluated 12 → markets evaluated 174 → markets positive ev 5 → events positive ev 5 → events passing all rules 0 → final recommendations 1
  - market rejections: EV below threshold (91), too few bookmakers (80), odds outside range (3)
  - primary blocker per event: no bookmaker prices yet (39), prices are in line with the sharp market (10), value only at long odds outside the allowed range (1), too few bookmakers price these markets (1)

**TENNIS**: events discovered 45 → complete history 10 → valid forecast 45 → fresh odds available 3 → stale odds only 0 → three plus bookmakers 3 → fully evaluated 3 → markets evaluated 6 → markets positive ev 1 → events positive ev 1 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (6)
  - primary blocker per event: no bookmaker prices yet (42), prices are in line with the sharp market (3)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 84, 'median_odds_age_h': 0.0, 'median_bookmakers': 1.0, 'share_3plus_books': 0.2}
- nfl: {'events_with_odds': 13, 'median_odds_age_h': 0.0, 'median_bookmakers': 22, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 12, 'median_odds_age_h': 0.0, 'median_bookmakers': 23.0, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 3, 'median_odds_age_h': 0.2, 'median_bookmakers': 16, 'share_3plus_books': 1.0}

## The Odds API

{'skipped': None, 'credits_remaining_after': '334', 'credits_spent': 0, 'fetched': [], 'matched': 0, 'unmatched': [], 'skipped_no_matching_event': [], 'bookmakers_requested': None, 'bookmakers_ignored': None, 'cost_mismatch': None}

## Providers

- football-data:fixtures: last success 2026-11-18T17:23:20+00:00
- football-data:E0: last success 2026-11-18T17:23:20+00:00
- football-data:E1: last success 2026-11-18T17:23:20+00:00
- football-data:SP1: last success 2026-11-18T17:23:20+00:00
- football-data:D1: last success 2026-11-18T17:23:20+00:00
- football-data:I1: last success 2026-11-18T17:23:20+00:00
- football-data:F1: last success 2026-11-18T17:23:20+00:00
- football-data:N1: last success 2026-11-18T17:23:20+00:00
- football-data:P1: last success 2026-11-18T17:23:20+00:00
- football-data:B1: last success 2026-11-18T17:23:21+00:00
- football-data:SC0: last success 2026-11-18T17:23:21+00:00
- espn:international: last success 2026-11-18T17:24:00+00:00
- the-odds-api: last success 2026-11-18T17:24:04+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-18T17:24:00+00:00
- espn:nba: last success 2026-11-18T17:24:00+00:00
- espn:tennis: last success 2026-11-18T17:24:15+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-18T17:24:01+00:00
- espn:club-fixtures: last success 2026-11-18T17:23:36+00:00
