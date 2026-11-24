# Sports Betting Doyen — diagnostics (2026-11-24 20:55 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 97 → complete history 88 → valid forecast 97 → fresh odds available 94 → stale odds only 1 → three plus bookmakers 37 → fully evaluated 35 → markets evaluated 456 → markets positive ev 33 → events positive ev 26 → events passing all rules 7 → final recommendations 27
  - market rejections: too few bookmakers (268), EV below threshold (122), insufficient team history (45), odds outside range (12), extreme disagreement (review) (2)
  - primary blocker per event: too few bookmakers price these markets (50), prices are in line with the sharp market (24), not enough history on one side (9), qualified (7), value only at long odds outside the allowed range (3), no bookmaker prices yet (2), extreme disagreement (review) (1), only stale prices available (1)

**NFL**: events discovered 16 → complete history 16 → valid forecast 16 → fresh odds available 16 → stale odds only 0 → three plus bookmakers 16 → fully evaluated 16 → markets evaluated 198 → markets positive ev 8 → events positive ev 6 → events passing all rules 1 → final recommendations 2
  - market rejections: EV below threshold (137), too few bookmakers (56), odds outside range (4)
  - primary blocker per event: prices are in line with the sharp market (13), value only at long odds outside the allowed range (2), qualified (1)

**NBA**: events discovered 45 → complete history 45 → valid forecast 45 → fresh odds available 7 → stale odds only 0 → three plus bookmakers 7 → fully evaluated 7 → markets evaluated 86 → markets positive ev 4 → events positive ev 4 → events passing all rules 0 → final recommendations 1
  - market rejections: EV below threshold (52), too few bookmakers (32), odds outside range (2)
  - primary blocker per event: no bookmaker prices yet (38), prices are in line with the sharp market (3), too few bookmakers price these markets (3), value only at long odds outside the allowed range (1)

**TENNIS**: events discovered 49 → complete history 6 → valid forecast 49 → fresh odds available 0 → stale odds only 0 → three plus bookmakers 0 → fully evaluated 0 → markets evaluated 0 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - primary blocker per event: no bookmaker prices yet (49)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 140, 'median_odds_age_h': 0.0, 'median_bookmakers': 18.0, 'share_3plus_books': 0.89}
- nfl: {'events_with_odds': 16, 'median_odds_age_h': 0.0, 'median_bookmakers': 22.0, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 7, 'median_odds_age_h': 0.0, 'median_bookmakers': 17, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 0, 'median_odds_age_h': None, 'median_bookmakers': None, 'share_3plus_books': None}

## The Odds API

{'skipped': None, 'credits_remaining_after': '228', 'credits_spent': 18, 'fetched': ['basketball_nba', 'americanfootball_nfl', 'soccer_uefa_champs_league', 'soccer_efl_champ', 'soccer_uefa_europa_conference_league', 'soccer_uefa_europa_league', 'soccer_netherlands_eredivisie', 'soccer_germany_bundesliga'], 'matched': 95, 'unmatched': ['soccer_uefa_champs_league: Paris Saint Germain v AS Roma', 'soccer_efl_champ: Lincoln City v Wolverhampton Wanderers', 'soccer_efl_champ: Queens Park Rangers v Sheffield United', 'soccer_uefa_europa_conference_league: Brighton and Hove Albion v Universitatea Craiova', "soccer_uefa_europa_conference_league: Inter Club d'Escaldes v FC Copenhagen", 'soccer_uefa_europa_league: Juventus v Omonoia FC', 'soccer_germany_bundesliga: Werder Bremen v Borussia Monchengladbach'], 'skipped_no_matching_event': [], 'bookmakers_requested': None, 'bookmakers_ignored': None, 'cost_mismatch': None}

## Providers

- football-data:fixtures: last success 2026-11-24T20:53:51+00:00
- football-data:E0: last success 2026-11-24T20:53:53+00:00
- football-data:E1: last success 2026-11-24T20:53:54+00:00
- football-data:SP1: last success 2026-11-24T20:53:56+00:00
- football-data:D1: last success 2026-11-24T20:53:57+00:00
- football-data:I1: last success 2026-11-24T20:53:58+00:00
- football-data:F1: last success 2026-11-24T20:54:00+00:00
- football-data:N1: last success 2026-11-24T20:54:01+00:00
- football-data:P1: last success 2026-11-24T20:54:03+00:00
- football-data:B1: last success 2026-11-24T20:54:04+00:00
- football-data:SC0: last success 2026-11-24T20:54:05+00:00
- espn:international: last success 2026-11-24T20:55:04+00:00
- the-odds-api: last success 2026-11-24T20:55:16+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-24T20:55:05+00:00
- espn:nba: last success 2026-11-24T20:55:05+00:00
- espn:tennis: last success 2026-11-24T20:55:33+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-24T20:55:11+00:00
- espn:club-fixtures: last success 2026-11-24T20:54:31+00:00
