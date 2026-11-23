# Sports Betting Doyen — diagnostics (2026-11-23 14:45 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 105 → complete history 95 → valid forecast 105 → fresh odds available 101 → stale odds only 0 → three plus bookmakers 58 → fully evaluated 56 → markets evaluated 827 → markets positive ev 78 → events positive ev 48 → events passing all rules 13 → final recommendations 15
  - market rejections: too few bookmakers (443), EV below threshold (277), insufficient team history (74), odds outside range (19), extreme disagreement (review) (1)
  - primary blocker per event: too few bookmakers price these markets (36), prices are in line with the sharp market (36), qualified (13), not enough history on one side (10), value only at long odds outside the allowed range (5), no bookmaker prices yet (4), extreme disagreement (review) (1)

**NFL**: events discovered 16 → complete history 16 → valid forecast 16 → fresh odds available 16 → stale odds only 0 → three plus bookmakers 16 → fully evaluated 16 → markets evaluated 202 → markets positive ev 4 → events positive ev 3 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (126), too few bookmakers (72), odds outside range (4)
  - primary blocker per event: prices are in line with the sharp market (11), value only at long odds outside the allowed range (3), too few bookmakers price these markets (2)

**NBA**: events discovered 48 → complete history 48 → valid forecast 48 → fresh odds available 10 → stale odds only 0 → three plus bookmakers 10 → fully evaluated 10 → markets evaluated 142 → markets positive ev 4 → events positive ev 3 → events passing all rules 0 → final recommendations 2
  - market rejections: EV below threshold (91), too few bookmakers (44), odds outside range (7)
  - primary blocker per event: no bookmaker prices yet (38), prices are in line with the sharp market (6), value only at long odds outside the allowed range (3), too few bookmakers price these markets (1)

**TENNIS**: events discovered 62 → complete history 8 → valid forecast 62 → fresh odds available 0 → stale odds only 0 → three plus bookmakers 0 → fully evaluated 0 → markets evaluated 0 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - primary blocker per event: no bookmaker prices yet (62)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 101, 'median_odds_age_h': 0.0, 'median_bookmakers': 12, 'share_3plus_books': 0.57}
- nfl: {'events_with_odds': 16, 'median_odds_age_h': 0.0, 'median_bookmakers': 20.5, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 10, 'median_odds_age_h': 0.0, 'median_bookmakers': 23.0, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 0, 'median_odds_age_h': None, 'median_bookmakers': None, 'share_3plus_books': None}

## The Odds API

{'skipped': None, 'credits_remaining_after': '280', 'credits_spent': 0, 'fetched': [], 'matched': 0, 'unmatched': [], 'skipped_no_matching_event': [], 'bookmakers_requested': None, 'bookmakers_ignored': None, 'cost_mismatch': None}

## Providers

- football-data:fixtures: last success 2026-11-23T14:44:15+00:00
- football-data:E0: last success 2026-11-23T14:44:15+00:00
- football-data:E1: last success 2026-11-23T14:44:15+00:00
- football-data:SP1: last success 2026-11-23T14:44:15+00:00
- football-data:D1: last success 2026-11-23T14:44:15+00:00
- football-data:I1: last success 2026-11-23T14:44:15+00:00
- football-data:F1: last success 2026-11-23T14:44:15+00:00
- football-data:N1: last success 2026-11-23T14:44:16+00:00
- football-data:P1: last success 2026-11-23T14:44:16+00:00
- football-data:B1: last success 2026-11-23T14:44:16+00:00
- football-data:SC0: last success 2026-11-23T14:44:16+00:00
- espn:international: last success 2026-11-23T14:44:56+00:00
- the-odds-api: last success 2026-11-23T14:44:58+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-23T14:44:56+00:00
- espn:nba: last success 2026-11-23T14:44:56+00:00
- espn:tennis: last success 2026-11-23T14:45:14+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-23T14:44:56+00:00
- espn:club-fixtures: last success 2026-11-23T14:44:32+00:00
