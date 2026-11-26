# Sports Betting Doyen — diagnostics (2026-11-26 19:53 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 109 → complete history 99 → valid forecast 109 → fresh odds available 109 → stale odds only 0 → three plus bookmakers 104 → fully evaluated 94 → markets evaluated 853 → markets positive ev 113 → events positive ev 73 → events passing all rules 18 → final recommendations 28
  - market rejections: EV below threshold (441), too few bookmakers (289), insufficient team history (68), odds outside range (33), extreme disagreement (review) (4)
  - primary blocker per event: prices are in line with the sharp market (66), qualified (18), not enough history on one side (10), too few bookmakers price these markets (7), value only at long odds outside the allowed range (5), extreme disagreement (review) (3)

**NFL**: events discovered 14 → complete history 14 → valid forecast 14 → fresh odds available 14 → stale odds only 0 → three plus bookmakers 14 → fully evaluated 14 → markets evaluated 200 → markets positive ev 16 → events positive ev 9 → events passing all rules 1 → final recommendations 5
  - market rejections: EV below threshold (135), too few bookmakers (60), odds outside range (4)
  - primary blocker per event: prices are in line with the sharp market (12), qualified (1), too few bookmakers price these markets (1)

**NBA**: events discovered 50 → complete history 50 → valid forecast 50 → fresh odds available 11 → stale odds only 0 → three plus bookmakers 11 → fully evaluated 11 → markets evaluated 136 → markets positive ev 7 → events positive ev 5 → events passing all rules 2 → final recommendations 0
  - market rejections: EV below threshold (80), too few bookmakers (50), odds outside range (4)
  - primary blocker per event: no bookmaker prices yet (39), prices are in line with the sharp market (8), qualified (2), value only at long odds outside the allowed range (1)

**TENNIS**: events discovered 58 → complete history 4 → valid forecast 58 → fresh odds available 0 → stale odds only 0 → three plus bookmakers 0 → fully evaluated 0 → markets evaluated 0 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - primary blocker per event: no bookmaker prices yet (58)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 127, 'median_odds_age_h': 0.0, 'median_bookmakers': 19, 'share_3plus_books': 0.94}
- nfl: {'events_with_odds': 14, 'median_odds_age_h': 0.0, 'median_bookmakers': 22.0, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 11, 'median_odds_age_h': 0.0, 'median_bookmakers': 17, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 0, 'median_odds_age_h': None, 'median_bookmakers': None, 'share_3plus_books': None}

## The Odds API

{'skipped': None, 'credits_remaining_after': '159', 'credits_spent': 30, 'fetched': ['americanfootball_nfl', 'soccer_uefa_europa_conference_league', 'soccer_uefa_europa_league', 'basketball_nba', 'soccer_netherlands_eredivisie', 'soccer_germany_bundesliga', 'soccer_belgium_first_div', 'soccer_france_ligue_one', 'soccer_italy_serie_a', 'soccer_efl_champ', 'soccer_epl', 'soccer_spain_la_liga', 'soccer_portugal_primeira_liga', 'soccer_spl'], 'matched': 145, 'unmatched': ["soccer_uefa_europa_conference_league: Inter Club d'Escaldes v FC Copenhagen", 'soccer_uefa_europa_league: Juventus v Omonoia FC', 'soccer_germany_bundesliga: Werder Bremen v Borussia Monchengladbach', 'soccer_france_ligue_one: Paris Saint Germain v Lorient', 'soccer_efl_champ: Lincoln City v Wolverhampton Wanderers', 'soccer_efl_champ: Queens Park Rangers v Sheffield United', 'soccer_portugal_primeira_liga: Vitória SC v CF Estrela', 'soccer_portugal_primeira_liga: Benfica v Famalicão'], 'skipped_no_matching_event': [], 'bookmakers_requested': None, 'bookmakers_ignored': None, 'cost_mismatch': None}

## Providers

- football-data:fixtures: last success 2026-11-26T19:51:17+00:00
- football-data:E0: last success 2026-11-26T19:51:18+00:00
- football-data:E1: last success 2026-11-26T19:51:20+00:00
- football-data:SP1: last success 2026-11-26T19:51:22+00:00
- football-data:D1: last success 2026-11-26T19:51:23+00:00
- football-data:I1: last success 2026-11-26T19:51:24+00:00
- football-data:F1: last success 2026-11-26T19:51:26+00:00
- football-data:N1: last success 2026-11-26T19:51:27+00:00
- football-data:P1: last success 2026-11-26T19:51:29+00:00
- football-data:B1: last success 2026-11-26T19:51:30+00:00
- football-data:SC0: last success 2026-11-26T19:51:32+00:00
- espn:international: last success 2026-11-26T19:52:32+00:00
- the-odds-api: last success 2026-11-26T19:52:48+00:00 · last error 2026-11-26T05:17:11+00:00 The Odds API quota/rate limit reached (HTTP 429)
- espn:nfl: last success 2026-11-26T19:52:32+00:00
- espn:nba: last success 2026-11-26T19:52:33+00:00
- espn:tennis: last success 2026-11-26T19:53:05+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-26T19:52:42+00:00
- espn:club-fixtures: last success 2026-11-26T19:51:58+00:00
