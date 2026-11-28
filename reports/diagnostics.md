# Sports Betting Doyen — diagnostics (2026-11-28 04:21 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 109 → complete history 98 → valid forecast 109 → fresh odds available 107 → stale odds only 0 → three plus bookmakers 102 → fully evaluated 93 → markets evaluated 815 → markets positive ev 89 → events positive ev 61 → events passing all rules 19 → final recommendations 25
  - market rejections: too few bookmakers (350), EV below threshold (334), insufficient team history (74), odds outside range (38)
  - primary blocker per event: prices are in line with the sharp market (60), qualified (19), too few bookmakers price these markets (11), not enough history on one side (10), value only at long odds outside the allowed range (7), no bookmaker prices yet (2)

**NFL**: events discovered 12 → complete history 12 → valid forecast 12 → fresh odds available 12 → stale odds only 0 → three plus bookmakers 12 → fully evaluated 12 → markets evaluated 132 → markets positive ev 6 → events positive ev 5 → events passing all rules 1 → final recommendations 2
  - market rejections: EV below threshold (66), too few bookmakers (62), odds outside range (3)
  - primary blocker per event: prices are in line with the sharp market (8), too few bookmakers price these markets (3), qualified (1)

**NBA**: events discovered 44 → complete history 44 → valid forecast 44 → fresh odds available 5 → stale odds only 0 → three plus bookmakers 5 → fully evaluated 5 → markets evaluated 66 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (34), too few bookmakers (30), odds outside range (2)
  - primary blocker per event: no bookmaker prices yet (39), prices are in line with the sharp market (3), value only at long odds outside the allowed range (2)

**TENNIS**: events discovered 57 → complete history 2 → valid forecast 57 → fresh odds available 0 → stale odds only 0 → three plus bookmakers 0 → fully evaluated 0 → markets evaluated 0 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - primary blocker per event: no bookmaker prices yet (57)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 107, 'median_odds_age_h': 0.0, 'median_bookmakers': 27, 'share_3plus_books': 0.97}
- nfl: {'events_with_odds': 12, 'median_odds_age_h': 0.0, 'median_bookmakers': 22.0, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 5, 'median_odds_age_h': 0.0, 'median_bookmakers': 19, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 0, 'median_odds_age_h': None, 'median_bookmakers': None, 'share_3plus_books': None}

## The Odds API

{'skipped': None, 'credits_remaining_after': '110', 'credits_spent': 7, 'fetched': ['basketball_nba', 'soccer_efl_champ', 'soccer_spain_la_liga'], 'matched': 27, 'unmatched': ['basketball_nba: Atlanta Hawks v Philadelphia 76ers', 'soccer_efl_champ: Lincoln City v Wolverhampton Wanderers', 'soccer_efl_champ: Queens Park Rangers v Sheffield United'], 'skipped_no_matching_event': [], 'bookmakers_requested': None, 'bookmakers_ignored': None, 'cost_mismatch': None}

## Providers

- football-data:fixtures: last success 2026-11-28T04:19:31+00:00
- football-data:E0: last success 2026-11-28T04:19:32+00:00
- football-data:E1: last success 2026-11-28T04:19:33+00:00
- football-data:SP1: last success 2026-11-28T04:19:34+00:00
- football-data:D1: last success 2026-11-28T04:19:35+00:00
- football-data:I1: last success 2026-11-28T04:19:36+00:00
- football-data:F1: last success 2026-11-28T04:19:37+00:00
- football-data:N1: last success 2026-11-28T04:19:38+00:00
- football-data:P1: last success 2026-11-28T04:19:39+00:00
- football-data:B1: last success 2026-11-28T04:19:39+00:00
- football-data:SC0: last success 2026-11-28T04:19:41+00:00
- espn:international: last success 2026-11-28T04:20:52+00:00
- the-odds-api: last success 2026-11-28T04:21:10+00:00 · last error 2026-11-26T05:17:11+00:00 The Odds API quota/rate limit reached (HTTP 429)
- espn:nfl: last success 2026-11-28T04:20:53+00:00
- espn:nba: last success 2026-11-28T04:20:53+00:00
- espn:tennis: last success 2026-11-28T04:21:24+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-28T04:21:04+00:00
- espn:club-fixtures: last success 2026-11-28T04:20:12+00:00
