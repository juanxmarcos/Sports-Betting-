# Sports Betting Doyen — diagnostics (2026-11-27 04:38 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 110 → complete history 100 → valid forecast 110 → fresh odds available 110 → stale odds only 0 → three plus bookmakers 104 → fully evaluated 94 → markets evaluated 798 → markets positive ev 117 → events positive ev 74 → events passing all rules 22 → final recommendations 28
  - market rejections: EV below threshold (402), too few bookmakers (266), insufficient team history (70), odds outside range (34), extreme disagreement (review) (4)
  - primary blocker per event: prices are in line with the sharp market (61), qualified (22), not enough history on one side (10), too few bookmakers price these markets (8), value only at long odds outside the allowed range (6), extreme disagreement (review) (3)

**NFL**: events discovered 13 → complete history 13 → valid forecast 13 → fresh odds available 12 → stale odds only 1 → three plus bookmakers 12 → fully evaluated 12 → markets evaluated 134 → markets positive ev 3 → events positive ev 3 → events passing all rules 0 → final recommendations 3
  - market rejections: EV below threshold (73), too few bookmakers (58), odds outside range (3)
  - primary blocker per event: prices are in line with the sharp market (10), value only at long odds outside the allowed range (2), only stale prices available (1)

**NBA**: events discovered 55 → complete history 55 → valid forecast 55 → fresh odds available 11 → stale odds only 0 → three plus bookmakers 11 → fully evaluated 11 → markets evaluated 188 → markets positive ev 13 → events positive ev 7 → events passing all rules 2 → final recommendations 0
  - market rejections: EV below threshold (120), too few bookmakers (62), odds outside range (4)
  - primary blocker per event: no bookmaker prices yet (44), prices are in line with the sharp market (7), value only at long odds outside the allowed range (2), qualified (2)

**TENNIS**: events discovered 56 → complete history 4 → valid forecast 56 → fresh odds available 0 → stale odds only 0 → three plus bookmakers 0 → fully evaluated 0 → markets evaluated 0 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - primary blocker per event: no bookmaker prices yet (56)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 110, 'median_odds_age_h': 0.0, 'median_bookmakers': 19.0, 'share_3plus_books': 0.95}
- nfl: {'events_with_odds': 13, 'median_odds_age_h': 0.0, 'median_bookmakers': 22, 'share_3plus_books': 0.92}
- nba: {'events_with_odds': 11, 'median_odds_age_h': 0.0, 'median_bookmakers': 21, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 0, 'median_odds_age_h': None, 'median_bookmakers': None, 'share_3plus_books': None}

## The Odds API

{'skipped': None, 'credits_remaining_after': '149', 'credits_spent': 10, 'fetched': ['americanfootball_nfl', 'basketball_nba', 'soccer_netherlands_eredivisie', 'soccer_germany_bundesliga'], 'matched': 40, 'unmatched': ['soccer_germany_bundesliga: Werder Bremen v Borussia Monchengladbach'], 'skipped_no_matching_event': [], 'bookmakers_requested': None, 'bookmakers_ignored': None, 'cost_mismatch': None}

## Providers

- football-data:fixtures: last success 2026-11-27T04:36:13+00:00
- football-data:E0: last success 2026-11-27T04:36:14+00:00
- football-data:E1: last success 2026-11-27T04:36:16+00:00
- football-data:SP1: last success 2026-11-27T04:36:17+00:00
- football-data:D1: last success 2026-11-27T04:36:18+00:00
- football-data:I1: last success 2026-11-27T04:36:19+00:00
- football-data:F1: last success 2026-11-27T04:36:20+00:00
- football-data:N1: last success 2026-11-27T04:36:21+00:00
- football-data:P1: last success 2026-11-27T04:36:22+00:00
- football-data:B1: last success 2026-11-27T04:36:23+00:00
- football-data:SC0: last success 2026-11-27T04:36:25+00:00
- espn:international: last success 2026-11-27T04:37:52+00:00
- the-odds-api: last success 2026-11-27T04:38:20+00:00 · last error 2026-11-26T05:17:11+00:00 The Odds API quota/rate limit reached (HTTP 429)
- espn:nfl: last success 2026-11-27T04:37:53+00:00
- espn:nba: last success 2026-11-27T04:37:54+00:00
- espn:tennis: last success 2026-11-27T04:38:35+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-27T04:38:13+00:00
- espn:club-fixtures: last success 2026-11-27T04:37:05+00:00
