# Sports Betting Doyen — diagnostics (2026-11-27 19:43 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 111 → complete history 100 → valid forecast 111 → fresh odds available 110 → stale odds only 0 → three plus bookmakers 109 → fully evaluated 99 → markets evaluated 988 → markets positive ev 104 → events positive ev 65 → events passing all rules 21 → final recommendations 29
  - market rejections: too few bookmakers (428), EV below threshold (415), insufficient team history (83), odds outside range (41)
  - primary blocker per event: prices are in line with the sharp market (65), qualified (21), not enough history on one side (11), too few bookmakers price these markets (7), value only at long odds outside the allowed range (6), no bookmaker prices yet (1)

**NFL**: events discovered 13 → complete history 13 → valid forecast 13 → fresh odds available 13 → stale odds only 0 → three plus bookmakers 13 → fully evaluated 13 → markets evaluated 162 → markets positive ev 8 → events positive ev 5 → events passing all rules 1 → final recommendations 3
  - market rejections: EV below threshold (101), too few bookmakers (56), odds outside range (3)
  - primary blocker per event: prices are in line with the sharp market (12), qualified (1)

**NBA**: events discovered 55 → complete history 55 → valid forecast 55 → fresh odds available 11 → stale odds only 0 → three plus bookmakers 11 → fully evaluated 11 → markets evaluated 148 → markets positive ev 13 → events positive ev 8 → events passing all rules 2 → final recommendations 0
  - market rejections: EV below threshold (94), too few bookmakers (50), odds outside range (2)
  - primary blocker per event: no bookmaker prices yet (44), prices are in line with the sharp market (8), qualified (2), value only at long odds outside the allowed range (1)

**TENNIS**: events discovered 58 → complete history 1 → valid forecast 58 → fresh odds available 0 → stale odds only 0 → three plus bookmakers 0 → fully evaluated 0 → markets evaluated 0 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - primary blocker per event: no bookmaker prices yet (58)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 110, 'median_odds_age_h': 0.0, 'median_bookmakers': 27.0, 'share_3plus_books': 0.99}
- nfl: {'events_with_odds': 13, 'median_odds_age_h': 0.0, 'median_bookmakers': 22, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 11, 'median_odds_age_h': 0.0, 'median_bookmakers': 21, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 0, 'median_odds_age_h': None, 'median_bookmakers': None, 'share_3plus_books': None}

## The Odds API

{'skipped': None, 'credits_remaining_after': '117', 'credits_spent': 16, 'fetched': ['americanfootball_nfl', 'basketball_nba', 'soccer_belgium_first_div', 'soccer_france_ligue_one', 'soccer_italy_serie_a', 'soccer_efl_champ', 'soccer_epl'], 'matched': 81, 'unmatched': ['soccer_france_ligue_one: Paris Saint Germain v Lorient', 'soccer_efl_champ: Lincoln City v Wolverhampton Wanderers', 'soccer_efl_champ: Queens Park Rangers v Sheffield United'], 'skipped_no_matching_event': [], 'bookmakers_requested': None, 'bookmakers_ignored': None, 'cost_mismatch': None}

## Providers

- football-data:fixtures: last success 2026-11-27T19:40:14+00:00
- football-data:E0: last success 2026-11-27T19:40:18+00:00
- football-data:E1: last success 2026-11-27T19:40:53+00:00
- football-data:SP1: last success 2026-11-27T19:40:56+00:00
- football-data:D1: last success 2026-11-27T19:41:00+00:00
- football-data:I1: last success 2026-11-27T19:41:03+00:00
- football-data:F1: last success 2026-11-27T19:41:05+00:00
- football-data:N1: last success 2026-11-27T19:41:08+00:00
- football-data:P1: last success 2026-11-27T19:41:11+00:00
- football-data:B1: last success 2026-11-27T19:41:14+00:00
- football-data:SC0: last success 2026-11-27T19:41:17+00:00
- espn:international: last success 2026-11-27T19:42:31+00:00
- the-odds-api: last success 2026-11-27T19:42:53+00:00 · last error 2026-11-26T05:17:11+00:00 The Odds API quota/rate limit reached (HTTP 429)
- espn:nfl: last success 2026-11-27T19:42:31+00:00
- espn:nba: last success 2026-11-27T19:42:32+00:00
- espn:tennis: last success 2026-11-27T19:43:04+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-27T19:42:46+00:00
- espn:club-fixtures: last success 2026-11-27T19:41:49+00:00
