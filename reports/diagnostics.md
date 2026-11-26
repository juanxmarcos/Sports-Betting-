# Sports Betting Doyen — diagnostics (2026-11-26 04:31 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 109 → complete history 99 → valid forecast 109 → fresh odds available 101 → stale odds only 0 → three plus bookmakers 44 → fully evaluated 40 → markets evaluated 479 → markets positive ev 37 → events positive ev 28 → events passing all rules 8 → final recommendations 28
  - market rejections: too few bookmakers (263), EV below threshold (155), insufficient team history (42), odds outside range (11)
  - primary blocker per event: too few bookmakers price these markets (51), prices are in line with the sharp market (31), not enough history on one side (10), qualified (8), no bookmaker prices yet (8), value only at long odds outside the allowed range (1)

**NFL**: events discovered 15 → complete history 15 → valid forecast 15 → fresh odds available 15 → stale odds only 0 → three plus bookmakers 15 → fully evaluated 15 → markets evaluated 234 → markets positive ev 17 → events positive ev 10 → events passing all rules 0 → final recommendations 3
  - market rejections: EV below threshold (138), too few bookmakers (92), odds outside range (4)
  - primary blocker per event: prices are in line with the sharp market (14), value only at long odds outside the allowed range (1)

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

{'skipped': None, 'credits_remaining_after': '189', 'credits_spent': 5, 'fetched': ['americanfootball_nfl', 'soccer_uefa_europa_conference_league'], 'matched': 31, 'unmatched': ['soccer_uefa_europa_conference_league: Brighton and Hove Albion v Universitatea Craiova', "soccer_uefa_europa_conference_league: Inter Club d'Escaldes v FC Copenhagen"], 'skipped_no_matching_event': [], 'bookmakers_requested': None, 'bookmakers_ignored': None, 'cost_mismatch': None}

## Providers

- football-data:fixtures: last success 2026-11-26T04:29:25+00:00
- football-data:E0: last success 2026-11-26T04:29:26+00:00
- football-data:E1: last success 2026-11-26T04:29:27+00:00
- football-data:SP1: last success 2026-11-26T04:29:29+00:00
- football-data:D1: last success 2026-11-26T04:29:30+00:00
- football-data:I1: last success 2026-11-26T04:29:31+00:00
- football-data:F1: last success 2026-11-26T04:29:33+00:00
- football-data:N1: last success 2026-11-26T04:29:34+00:00
- football-data:P1: last success 2026-11-26T04:29:35+00:00
- football-data:B1: last success 2026-11-26T04:29:37+00:00
- football-data:SC0: last success 2026-11-26T04:29:38+00:00
- espn:international: last success 2026-11-26T04:30:52+00:00
- the-odds-api: last success 2026-11-26T04:31:23+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-26T04:30:53+00:00
- espn:nba: last success 2026-11-26T04:30:55+00:00
- espn:tennis: last success 2026-11-26T04:31:36+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-26T04:31:14+00:00
- espn:club-fixtures: last success 2026-11-26T04:30:10+00:00
