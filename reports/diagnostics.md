# Sports Betting Doyen — diagnostics (2026-11-27 05:15 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 110 → complete history 100 → valid forecast 110 → fresh odds available 110 → stale odds only 0 → three plus bookmakers 105 → fully evaluated 95 → markets evaluated 816 → markets positive ev 115 → events positive ev 75 → events passing all rules 16 → final recommendations 29
  - market rejections: EV below threshold (433), too few bookmakers (259), insufficient team history (72), odds outside range (33), extreme disagreement (review) (3)
  - primary blocker per event: prices are in line with the sharp market (71), qualified (16), not enough history on one side (10), too few bookmakers price these markets (7), value only at long odds outside the allowed range (5), extreme disagreement (review) (1)

**NFL**: events discovered 13 → complete history 13 → valid forecast 13 → fresh odds available 12 → stale odds only 1 → three plus bookmakers 12 → fully evaluated 12 → markets evaluated 134 → markets positive ev 3 → events positive ev 3 → events passing all rules 0 → final recommendations 3
  - market rejections: EV below threshold (73), too few bookmakers (58), odds outside range (3)
  - primary blocker per event: prices are in line with the sharp market (10), value only at long odds outside the allowed range (2), only stale prices available (1)

**NBA**: events discovered 55 → complete history 55 → valid forecast 55 → fresh odds available 11 → stale odds only 0 → three plus bookmakers 11 → fully evaluated 11 → markets evaluated 188 → markets positive ev 13 → events positive ev 7 → events passing all rules 2 → final recommendations 0
  - market rejections: EV below threshold (120), too few bookmakers (62), odds outside range (4)
  - primary blocker per event: no bookmaker prices yet (44), prices are in line with the sharp market (7), value only at long odds outside the allowed range (2), qualified (2)

**TENNIS**: events discovered 61 → complete history 4 → valid forecast 61 → fresh odds available 0 → stale odds only 0 → three plus bookmakers 0 → fully evaluated 0 → markets evaluated 0 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - primary blocker per event: no bookmaker prices yet (61)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 110, 'median_odds_age_h': 0.0, 'median_bookmakers': 19.0, 'share_3plus_books': 0.95}
- nfl: {'events_with_odds': 13, 'median_odds_age_h': 0.0, 'median_bookmakers': 22, 'share_3plus_books': 0.92}
- nba: {'events_with_odds': 11, 'median_odds_age_h': 0.0, 'median_bookmakers': 21, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 0, 'median_odds_age_h': None, 'median_bookmakers': None, 'share_3plus_books': None}

## The Odds API

{'skipped': None, 'credits_remaining_after': '133', 'credits_spent': 16, 'fetched': ['soccer_belgium_first_div', 'soccer_france_ligue_one', 'soccer_italy_serie_a', 'soccer_efl_champ', 'soccer_epl', 'soccer_spain_la_liga', 'soccer_portugal_primeira_liga', 'soccer_spl'], 'matched': 88, 'unmatched': ['soccer_france_ligue_one: Paris Saint Germain v Lorient', 'soccer_efl_champ: Lincoln City v Wolverhampton Wanderers', 'soccer_efl_champ: Queens Park Rangers v Sheffield United', 'soccer_portugal_primeira_liga: Vitória SC v CF Estrela', 'soccer_portugal_primeira_liga: Benfica v Famalicão'], 'skipped_no_matching_event': [], 'bookmakers_requested': None, 'bookmakers_ignored': None, 'cost_mismatch': None}

## Providers

- football-data:fixtures: last success 2026-11-27T05:14:19+00:00
- football-data:E0: last success 2026-11-27T05:14:19+00:00
- football-data:E1: last success 2026-11-27T05:14:19+00:00
- football-data:SP1: last success 2026-11-27T05:14:19+00:00
- football-data:D1: last success 2026-11-27T05:14:19+00:00
- football-data:I1: last success 2026-11-27T05:14:19+00:00
- football-data:F1: last success 2026-11-27T05:14:19+00:00
- football-data:N1: last success 2026-11-27T05:14:19+00:00
- football-data:P1: last success 2026-11-27T05:14:19+00:00
- football-data:B1: last success 2026-11-27T05:14:19+00:00
- football-data:SC0: last success 2026-11-27T05:14:19+00:00
- espn:international: last success 2026-11-27T05:15:03+00:00
- the-odds-api: last success 2026-11-27T05:15:08+00:00 · last error 2026-11-26T05:17:11+00:00 The Odds API quota/rate limit reached (HTTP 429)
- espn:nfl: last success 2026-11-27T05:15:03+00:00
- espn:nba: last success 2026-11-27T05:15:03+00:00
- espn:tennis: last success 2026-11-27T05:15:18+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-27T05:15:05+00:00
- espn:club-fixtures: last success 2026-11-27T05:14:39+00:00
