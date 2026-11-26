# Sports Betting Doyen — diagnostics (2026-11-26 05:17 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 109 → complete history 99 → valid forecast 109 → fresh odds available 95 → stale odds only 6 → three plus bookmakers 34 → fully evaluated 30 → markets evaluated 431 → markets positive ev 29 → events positive ev 21 → events passing all rules 5 → final recommendations 28
  - market rejections: too few bookmakers (253), EV below threshold (121), insufficient team history (42), odds outside range (10)
  - primary blocker per event: too few bookmakers price these markets (55), prices are in line with the sharp market (24), not enough history on one side (10), no bookmaker prices yet (8), only stale prices available (6), qualified (5), value only at long odds outside the allowed range (1)

**NFL**: events discovered 15 → complete history 15 → valid forecast 15 → fresh odds available 15 → stale odds only 0 → three plus bookmakers 15 → fully evaluated 15 → markets evaluated 206 → markets positive ev 11 → events positive ev 7 → events passing all rules 0 → final recommendations 3
  - market rejections: EV below threshold (118), too few bookmakers (84), odds outside range (4)
  - primary blocker per event: prices are in line with the sharp market (13), value only at long odds outside the allowed range (1), too few bookmakers price these markets (1)

**NBA**: events discovered 50 → complete history 50 → valid forecast 50 → fresh odds available 0 → stale odds only 0 → three plus bookmakers 0 → fully evaluated 0 → markets evaluated 0 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - primary blocker per event: no bookmaker prices yet (50)

**TENNIS**: events discovered 60 → complete history 6 → valid forecast 60 → fresh odds available 0 → stale odds only 0 → three plus bookmakers 0 → fully evaluated 0 → markets evaluated 0 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - primary blocker per event: no bookmaker prices yet (60)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 137, 'median_odds_age_h': 0.0, 'median_bookmakers': 18, 'share_3plus_books': 0.82}
- nfl: {'events_with_odds': 15, 'median_odds_age_h': 0.0, 'median_bookmakers': 22, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 0, 'median_odds_age_h': None, 'median_bookmakers': None, 'share_3plus_books': None}
- tennis: {'events_with_odds': 0, 'median_odds_age_h': None, 'median_bookmakers': None, 'share_3plus_books': None}

## The Odds API

{'skipped': None, 'credits_remaining_after': None, 'credits_spent': None, 'fetched': None, 'matched': None, 'unmatched': None, 'skipped_no_matching_event': None, 'bookmakers_requested': None, 'bookmakers_ignored': None, 'cost_mismatch': None}

## Providers

- football-data:fixtures: last success 2026-11-26T05:16:22+00:00
- football-data:E0: last success 2026-11-26T05:16:22+00:00
- football-data:E1: last success 2026-11-26T05:16:22+00:00
- football-data:SP1: last success 2026-11-26T05:16:22+00:00
- football-data:D1: last success 2026-11-26T05:16:22+00:00
- football-data:I1: last success 2026-11-26T05:16:22+00:00
- football-data:F1: last success 2026-11-26T05:16:22+00:00
- football-data:N1: last success 2026-11-26T05:16:22+00:00
- football-data:P1: last success 2026-11-26T05:16:22+00:00
- football-data:B1: last success 2026-11-26T05:16:22+00:00
- football-data:SC0: last success 2026-11-26T05:16:22+00:00
- espn:international: last success 2026-11-26T05:17:06+00:00
- the-odds-api: last success 2026-11-26T04:31:23+00:00 · last error 2026-11-26T05:17:11+00:00 The Odds API quota/rate limit reached (HTTP 429)
- espn:nfl: last success 2026-11-26T05:17:06+00:00
- espn:nba: last success 2026-11-26T05:17:06+00:00
- espn:tennis: last success 2026-11-26T05:17:21+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-26T05:17:10+00:00
- espn:club-fixtures: last success 2026-11-26T05:16:42+00:00
