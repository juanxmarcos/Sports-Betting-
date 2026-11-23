# Sports Betting Doyen — diagnostics (2026-11-23 20:16 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 106 → complete history 96 → valid forecast 106 → fresh odds available 104 → stale odds only 0 → three plus bookmakers 91 → fully evaluated 83 → markets evaluated 966 → markets positive ev 123 → events positive ev 77 → events passing all rules 22 → final recommendations 22
  - market rejections: EV below threshold (411), too few bookmakers (410), insufficient team history (92), odds outside range (28), extreme disagreement (review) (3)
  - primary blocker per event: prices are in line with the sharp market (49), qualified (22), too few bookmakers price these markets (12), not enough history on one side (10), value only at long odds outside the allowed range (9), extreme disagreement (review) (2), no bookmaker prices yet (2)

**NFL**: events discovered 16 → complete history 16 → valid forecast 16 → fresh odds available 16 → stale odds only 0 → three plus bookmakers 16 → fully evaluated 16 → markets evaluated 218 → markets positive ev 12 → events positive ev 6 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (144), too few bookmakers (70), odds outside range (4)
  - primary blocker per event: prices are in line with the sharp market (12), too few bookmakers price these markets (3), value only at long odds outside the allowed range (1)

**NBA**: events discovered 48 → complete history 48 → valid forecast 48 → fresh odds available 10 → stale odds only 0 → three plus bookmakers 10 → fully evaluated 10 → markets evaluated 192 → markets positive ev 11 → events positive ev 6 → events passing all rules 0 → final recommendations 2
  - market rejections: EV below threshold (121), too few bookmakers (64), odds outside range (7)
  - primary blocker per event: no bookmaker prices yet (38), prices are in line with the sharp market (6), too few bookmakers price these markets (2), value only at long odds outside the allowed range (2)

**TENNIS**: events discovered 57 → complete history 6 → valid forecast 57 → fresh odds available 0 → stale odds only 0 → three plus bookmakers 0 → fully evaluated 0 → markets evaluated 0 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - primary blocker per event: no bookmaker prices yet (57)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 104, 'median_odds_age_h': 0.0, 'median_bookmakers': 18.0, 'share_3plus_books': 0.88}
- nfl: {'events_with_odds': 16, 'median_odds_age_h': 0.0, 'median_bookmakers': 22.0, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 10, 'median_odds_age_h': 0.0, 'median_bookmakers': 23.0, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 0, 'median_odds_age_h': None, 'median_bookmakers': None, 'share_3plus_books': None}

## The Odds API

{'skipped': None, 'credits_remaining_after': '262', 'credits_spent': 18, 'fetched': ['basketball_nba', 'americanfootball_nfl', 'soccer_netherlands_eredivisie', 'soccer_germany_bundesliga', 'soccer_belgium_first_div', 'soccer_france_ligue_one', 'soccer_italy_serie_a', 'soccer_epl'], 'matched': 80, 'unmatched': ['soccer_germany_bundesliga: Werder Bremen v Borussia Monchengladbach', 'soccer_france_ligue_one: Paris Saint Germain v Lorient'], 'skipped_no_matching_event': [], 'bookmakers_requested': None, 'bookmakers_ignored': None, 'cost_mismatch': None}

## Providers

- football-data:fixtures: last success 2026-11-23T20:15:23+00:00
- football-data:E0: last success 2026-11-23T20:15:23+00:00
- football-data:E1: last success 2026-11-23T20:15:23+00:00
- football-data:SP1: last success 2026-11-23T20:15:23+00:00
- football-data:D1: last success 2026-11-23T20:15:23+00:00
- football-data:I1: last success 2026-11-23T20:15:23+00:00
- football-data:F1: last success 2026-11-23T20:15:23+00:00
- football-data:N1: last success 2026-11-23T20:15:24+00:00
- football-data:P1: last success 2026-11-23T20:15:24+00:00
- football-data:B1: last success 2026-11-23T20:15:24+00:00
- football-data:SC0: last success 2026-11-23T20:15:24+00:00
- espn:international: last success 2026-11-23T20:16:21+00:00
- the-odds-api: last success 2026-11-23T20:16:29+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-23T20:16:21+00:00
- espn:nba: last success 2026-11-23T20:16:22+00:00
- espn:tennis: last success 2026-11-23T20:16:44+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-23T20:16:25+00:00
- espn:club-fixtures: last success 2026-11-23T20:15:46+00:00
