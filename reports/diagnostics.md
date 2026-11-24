# Sports Betting Doyen — diagnostics (2026-11-24 06:31 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 106 → complete history 98 → valid forecast 106 → fresh odds available 104 → stale odds only 0 → three plus bookmakers 91 → fully evaluated 85 → markets evaluated 762 → markets positive ev 123 → events positive ev 78 → events passing all rules 21 → final recommendations 29
  - market rejections: EV below threshold (414), too few bookmakers (245), insufficient team history (52), odds outside range (28), extreme disagreement (review) (2)
  - primary blocker per event: prices are in line with the sharp market (54), qualified (21), too few bookmakers price these markets (11), not enough history on one side (8), value only at long odds outside the allowed range (8), extreme disagreement (review) (2), no bookmaker prices yet (2)

**NFL**: events discovered 16 → complete history 16 → valid forecast 16 → fresh odds available 16 → stale odds only 0 → three plus bookmakers 16 → fully evaluated 16 → markets evaluated 232 → markets positive ev 15 → events positive ev 5 → events passing all rules 1 → final recommendations 1
  - market rejections: EV below threshold (153), too few bookmakers (74), odds outside range (4)
  - primary blocker per event: prices are in line with the sharp market (14), too few bookmakers price these markets (1), qualified (1)

**NBA**: events discovered 45 → complete history 45 → valid forecast 45 → fresh odds available 7 → stale odds only 0 → three plus bookmakers 7 → fully evaluated 7 → markets evaluated 72 → markets positive ev 6 → events positive ev 5 → events passing all rules 0 → final recommendations 1
  - market rejections: EV below threshold (41), too few bookmakers (30), odds outside range (1)
  - primary blocker per event: no bookmaker prices yet (38), prices are in line with the sharp market (7)

**TENNIS**: events discovered 57 → complete history 7 → valid forecast 57 → fresh odds available 0 → stale odds only 0 → three plus bookmakers 0 → fully evaluated 0 → markets evaluated 0 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - primary blocker per event: no bookmaker prices yet (57)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 158, 'median_odds_age_h': 0.0, 'median_bookmakers': 18.0, 'share_3plus_books': 0.89}
- nfl: {'events_with_odds': 16, 'median_odds_age_h': 0.0, 'median_bookmakers': 22.0, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 7, 'median_odds_age_h': 0.0, 'median_bookmakers': 10, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 0, 'median_odds_age_h': None, 'median_bookmakers': None, 'share_3plus_books': None}

## The Odds API

{'skipped': None, 'credits_remaining_after': '246', 'credits_spent': 16, 'fetched': ['basketball_nba', 'soccer_uefa_champs_league', 'soccer_efl_champ', 'soccer_spl', 'americanfootball_nfl', 'soccer_uefa_europa_conference_league', 'soccer_uefa_europa_league'], 'matched': 101, 'unmatched': ['soccer_uefa_champs_league: Paris Saint Germain v AS Roma', 'soccer_efl_champ: Norwich City v Queens Park Rangers', 'soccer_efl_champ: Wolverhampton Wanderers v Derby County', 'soccer_efl_champ: Lincoln City v Wolverhampton Wanderers', 'soccer_efl_champ: Queens Park Rangers v Sheffield United', 'soccer_uefa_europa_conference_league: Brighton and Hove Albion v Universitatea Craiova', "soccer_uefa_europa_conference_league: Inter Club d'Escaldes v FC Copenhagen", 'soccer_uefa_europa_league: Juventus v Omonoia FC'], 'skipped_no_matching_event': [], 'bookmakers_requested': None, 'bookmakers_ignored': None, 'cost_mismatch': None}

## Providers

- football-data:fixtures: last success 2026-11-24T06:29:56+00:00
- football-data:E0: last success 2026-11-24T06:29:57+00:00
- football-data:E1: last success 2026-11-24T06:29:59+00:00
- football-data:SP1: last success 2026-11-24T06:30:00+00:00
- football-data:D1: last success 2026-11-24T06:30:01+00:00
- football-data:I1: last success 2026-11-24T06:30:03+00:00
- football-data:F1: last success 2026-11-24T06:30:06+00:00
- football-data:N1: last success 2026-11-24T06:30:08+00:00
- football-data:P1: last success 2026-11-24T06:30:09+00:00
- football-data:B1: last success 2026-11-24T06:30:10+00:00
- football-data:SC0: last success 2026-11-24T06:30:11+00:00
- espn:international: last success 2026-11-24T06:31:15+00:00
- the-odds-api: last success 2026-11-24T06:31:34+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-24T06:31:16+00:00
- espn:nba: last success 2026-11-24T06:31:17+00:00
- espn:tennis: last success 2026-11-24T06:31:46+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-24T06:31:27+00:00
- espn:club-fixtures: last success 2026-11-24T06:30:39+00:00
