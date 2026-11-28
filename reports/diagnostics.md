# Sports Betting Doyen — diagnostics (2026-11-28 08:55 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 109 → complete history 98 → valid forecast 109 → fresh odds available 107 → stale odds only 0 → three plus bookmakers 98 → fully evaluated 89 → markets evaluated 799 → markets positive ev 84 → events positive ev 60 → events passing all rules 17 → final recommendations 25
  - market rejections: too few bookmakers (343), EV below threshold (327), insufficient team history (76), odds outside range (35), extreme disagreement (review) (1)
  - primary blocker per event: prices are in line with the sharp market (59), qualified (17), too few bookmakers price these markets (14), not enough history on one side (10), value only at long odds outside the allowed range (6), no bookmaker prices yet (2), extreme disagreement (review) (1)

**NFL**: events discovered 12 → complete history 12 → valid forecast 12 → fresh odds available 12 → stale odds only 0 → three plus bookmakers 6 → fully evaluated 6 → markets evaluated 82 → markets positive ev 5 → events positive ev 4 → events passing all rules 1 → final recommendations 2
  - market rejections: too few bookmakers (56), EV below threshold (25)
  - primary blocker per event: too few bookmakers price these markets (6), prices are in line with the sharp market (5), qualified (1)

**NBA**: events discovered 48 → complete history 48 → valid forecast 48 → fresh odds available 7 → stale odds only 0 → three plus bookmakers 5 → fully evaluated 5 → markets evaluated 82 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - market rejections: too few bookmakers (46), EV below threshold (34), odds outside range (2)
  - primary blocker per event: no bookmaker prices yet (41), prices are in line with the sharp market (3), value only at long odds outside the allowed range (2), too few bookmakers price these markets (2)

**TENNIS**: events discovered 61 → complete history 2 → valid forecast 61 → fresh odds available 0 → stale odds only 0 → three plus bookmakers 0 → fully evaluated 0 → markets evaluated 0 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - primary blocker per event: no bookmaker prices yet (61)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 107, 'median_odds_age_h': 0.0, 'median_bookmakers': 27, 'share_3plus_books': 0.99}
- nfl: {'events_with_odds': 12, 'median_odds_age_h': 0.0, 'median_bookmakers': 22.0, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 7, 'median_odds_age_h': 0.0, 'median_bookmakers': 18, 'share_3plus_books': 0.71}
- tennis: {'events_with_odds': 0, 'median_odds_age_h': None, 'median_bookmakers': None, 'share_3plus_books': None}

## The Odds API

{'skipped': None, 'credits_remaining_after': '96', 'credits_spent': 14, 'fetched': ['soccer_efl_champ', 'soccer_spain_la_liga', 'soccer_italy_serie_a', 'soccer_germany_bundesliga', 'soccer_belgium_first_div', 'soccer_epl', 'soccer_spl'], 'matched': 80, 'unmatched': ['soccer_efl_champ: Lincoln City v Wolverhampton Wanderers', 'soccer_efl_champ: Queens Park Rangers v Sheffield United'], 'skipped_no_matching_event': [], 'bookmakers_requested': None, 'bookmakers_ignored': None, 'cost_mismatch': None}

## Providers

- football-data:fixtures: last success 2026-11-28T08:53:53+00:00
- football-data:E0: last success 2026-11-28T08:53:53+00:00
- football-data:E1: last success 2026-11-28T08:53:53+00:00
- football-data:SP1: last success 2026-11-28T08:53:53+00:00
- football-data:D1: last success 2026-11-28T08:53:53+00:00
- football-data:I1: last success 2026-11-28T08:53:53+00:00
- football-data:F1: last success 2026-11-28T08:53:54+00:00
- football-data:N1: last success 2026-11-28T08:53:54+00:00
- football-data:P1: last success 2026-11-28T08:53:54+00:00
- football-data:B1: last success 2026-11-28T08:53:54+00:00
- football-data:SC0: last success 2026-11-28T08:53:54+00:00
- espn:international: last success 2026-11-28T08:54:53+00:00
- the-odds-api: last success 2026-11-28T08:55:04+00:00 · last error 2026-11-26T05:17:11+00:00 The Odds API quota/rate limit reached (HTTP 429)
- espn:nfl: last success 2026-11-28T08:54:53+00:00
- espn:nba: last success 2026-11-28T08:54:53+00:00
- espn:tennis: last success 2026-11-28T08:55:20+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-28T08:55:00+00:00
- espn:club-fixtures: last success 2026-11-28T08:54:20+00:00
