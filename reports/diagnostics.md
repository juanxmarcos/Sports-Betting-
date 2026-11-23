# Sports Betting Doyen — diagnostics (2026-11-23 21:11 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 106 → complete history 98 → valid forecast 106 → fresh odds available 104 → stale odds only 0 → three plus bookmakers 91 → fully evaluated 85 → markets evaluated 796 → markets positive ev 122 → events positive ev 78 → events passing all rules 23 → final recommendations 24
  - market rejections: EV below threshold (424), too few bookmakers (267), insufficient team history (52), odds outside range (28), extreme disagreement (review) (2)
  - primary blocker per event: prices are in line with the sharp market (50), qualified (23), too few bookmakers price these markets (12), value only at long odds outside the allowed range (9), not enough history on one side (8), extreme disagreement (review) (2), no bookmaker prices yet (2)

**NFL**: events discovered 16 → complete history 16 → valid forecast 16 → fresh odds available 16 → stale odds only 0 → three plus bookmakers 16 → fully evaluated 16 → markets evaluated 212 → markets positive ev 11 → events positive ev 6 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (144), too few bookmakers (64), odds outside range (4)
  - primary blocker per event: prices are in line with the sharp market (13), too few bookmakers price these markets (2), value only at long odds outside the allowed range (1)

**NBA**: events discovered 48 → complete history 48 → valid forecast 48 → fresh odds available 10 → stale odds only 0 → three plus bookmakers 10 → fully evaluated 10 → markets evaluated 138 → markets positive ev 7 → events positive ev 7 → events passing all rules 1 → final recommendations 2
  - market rejections: EV below threshold (74), too few bookmakers (56), odds outside range (7)
  - primary blocker per event: no bookmaker prices yet (38), prices are in line with the sharp market (4), too few bookmakers price these markets (4), value only at long odds outside the allowed range (1), qualified (1)

**TENNIS**: events discovered 57 → complete history 7 → valid forecast 57 → fresh odds available 0 → stale odds only 0 → three plus bookmakers 0 → fully evaluated 0 → markets evaluated 0 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - primary blocker per event: no bookmaker prices yet (57)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 104, 'median_odds_age_h': 0.0, 'median_bookmakers': 18.0, 'share_3plus_books': 0.88}
- nfl: {'events_with_odds': 16, 'median_odds_age_h': 0.0, 'median_bookmakers': 22.0, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 10, 'median_odds_age_h': 0.0, 'median_bookmakers': 23.0, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 0, 'median_odds_age_h': None, 'median_bookmakers': None, 'share_3plus_books': None}

## The Odds API

{'skipped': None, 'credits_remaining_after': '262', 'credits_spent': 0, 'fetched': [], 'matched': 0, 'unmatched': [], 'skipped_no_matching_event': [], 'bookmakers_requested': None, 'bookmakers_ignored': None, 'cost_mismatch': None}

## Providers

- football-data:fixtures: last success 2026-11-23T21:09:29+00:00
- football-data:E0: last success 2026-11-23T21:09:31+00:00
- football-data:E1: last success 2026-11-23T21:09:32+00:00
- football-data:SP1: last success 2026-11-23T21:09:33+00:00
- football-data:D1: last success 2026-11-23T21:09:35+00:00
- football-data:I1: last success 2026-11-23T21:09:36+00:00
- football-data:F1: last success 2026-11-23T21:09:37+00:00
- football-data:N1: last success 2026-11-23T21:09:39+00:00
- football-data:P1: last success 2026-11-23T21:09:40+00:00
- football-data:B1: last success 2026-11-23T21:09:41+00:00
- football-data:SC0: last success 2026-11-23T21:09:42+00:00
- espn:international: last success 2026-11-23T21:10:41+00:00
- the-odds-api: last success 2026-11-23T21:10:52+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-23T21:10:42+00:00
- espn:nba: last success 2026-11-23T21:10:43+00:00
- espn:tennis: last success 2026-11-23T21:11:05+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-23T21:10:46+00:00
- espn:club-fixtures: last success 2026-11-23T21:10:05+00:00
