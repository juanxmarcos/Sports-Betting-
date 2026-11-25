# Sports Betting Doyen — diagnostics (2026-11-25 20:15 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 104 → complete history 94 → valid forecast 104 → fresh odds available 97 → stale odds only 0 → three plus bookmakers 44 → fully evaluated 40 → markets evaluated 561 → markets positive ev 43 → events positive ev 29 → events passing all rules 8 → final recommendations 28
  - market rejections: too few bookmakers (315), EV below threshold (183), insufficient team history (44), odds outside range (11)
  - primary blocker per event: too few bookmakers price these markets (47), prices are in line with the sharp market (31), not enough history on one side (10), qualified (8), no bookmaker prices yet (7), value only at long odds outside the allowed range (1)

**NFL**: events discovered 16 → complete history 16 → valid forecast 16 → fresh odds available 16 → stale odds only 0 → three plus bookmakers 16 → fully evaluated 16 → markets evaluated 238 → markets positive ev 16 → events positive ev 10 → events passing all rules 0 → final recommendations 4
  - market rejections: EV below threshold (148), too few bookmakers (86), odds outside range (4)
  - primary blocker per event: prices are in line with the sharp market (15), value only at long odds outside the allowed range (1)

**NBA**: events discovered 50 → complete history 50 → valid forecast 50 → fresh odds available 9 → stale odds only 0 → three plus bookmakers 9 → fully evaluated 9 → markets evaluated 114 → markets positive ev 3 → events positive ev 2 → events passing all rules 0 → final recommendations 2
  - market rejections: EV below threshold (81), too few bookmakers (32), odds outside range (1)
  - primary blocker per event: no bookmaker prices yet (41), prices are in line with the sharp market (9)

**TENNIS**: events discovered 61 → complete history 5 → valid forecast 61 → fresh odds available 0 → stale odds only 0 → three plus bookmakers 0 → fully evaluated 0 → markets evaluated 0 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - primary blocker per event: no bookmaker prices yet (61)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 137, 'median_odds_age_h': 0.0, 'median_bookmakers': 18, 'share_3plus_books': 0.82}
- nfl: {'events_with_odds': 16, 'median_odds_age_h': 0.0, 'median_bookmakers': 22.0, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 9, 'median_odds_age_h': 0.0, 'median_bookmakers': 21, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 0, 'median_odds_age_h': None, 'median_bookmakers': None, 'share_3plus_books': None}

## The Odds API

{'skipped': None, 'credits_remaining_after': '194', 'credits_spent': 18, 'fetched': ['basketball_nba', 'americanfootball_nfl', 'soccer_uefa_europa_conference_league', 'soccer_uefa_europa_league', 'soccer_netherlands_eredivisie', 'soccer_germany_bundesliga', 'soccer_belgium_first_div', 'soccer_france_ligue_one'], 'matched': 92, 'unmatched': ['soccer_uefa_europa_conference_league: Brighton and Hove Albion v Universitatea Craiova', "soccer_uefa_europa_conference_league: Inter Club d'Escaldes v FC Copenhagen", 'soccer_uefa_europa_league: Juventus v Omonoia FC', 'soccer_germany_bundesliga: Werder Bremen v Borussia Monchengladbach', 'soccer_france_ligue_one: Paris Saint Germain v Lorient'], 'skipped_no_matching_event': [], 'bookmakers_requested': None, 'bookmakers_ignored': None, 'cost_mismatch': None}

## Providers

- football-data:fixtures: last success 2026-11-25T20:13:07+00:00
- football-data:E0: last success 2026-11-25T20:13:08+00:00
- football-data:E1: last success 2026-11-25T20:13:10+00:00
- football-data:SP1: last success 2026-11-25T20:13:11+00:00
- football-data:D1: last success 2026-11-25T20:13:13+00:00
- football-data:I1: last success 2026-11-25T20:13:14+00:00
- football-data:F1: last success 2026-11-25T20:13:16+00:00
- football-data:N1: last success 2026-11-25T20:13:17+00:00
- football-data:P1: last success 2026-11-25T20:13:18+00:00
- football-data:B1: last success 2026-11-25T20:13:20+00:00
- football-data:SC0: last success 2026-11-25T20:13:21+00:00
- espn:international: last success 2026-11-25T20:14:27+00:00
- the-odds-api: last success 2026-11-25T20:14:48+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-25T20:14:27+00:00
- espn:nba: last success 2026-11-25T20:14:28+00:00
- espn:tennis: last success 2026-11-25T20:15:04+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-25T20:14:41+00:00
- espn:club-fixtures: last success 2026-11-25T20:13:51+00:00
