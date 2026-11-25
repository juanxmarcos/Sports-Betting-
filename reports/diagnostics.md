# Sports Betting Doyen — diagnostics (2026-11-25 05:06 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 97 → complete history 88 → valid forecast 97 → fresh odds available 94 → stale odds only 3 → three plus bookmakers 37 → fully evaluated 35 → markets evaluated 410 → markets positive ev 34 → events positive ev 25 → events passing all rules 9 → final recommendations 30
  - market rejections: too few bookmakers (224), EV below threshold (131), insufficient team history (33), odds outside range (13)
  - primary blocker per event: too few bookmakers price these markets (50), prices are in line with the sharp market (23), not enough history on one side (9), qualified (9), value only at long odds outside the allowed range (3), only stale prices available (3)

**NFL**: events discovered 16 → complete history 16 → valid forecast 16 → fresh odds available 16 → stale odds only 0 → three plus bookmakers 16 → fully evaluated 16 → markets evaluated 234 → markets positive ev 15 → events positive ev 12 → events passing all rules 1 → final recommendations 4
  - market rejections: EV below threshold (163), too few bookmakers (66), odds outside range (4)
  - primary blocker per event: prices are in line with the sharp market (14), too few bookmakers price these markets (1), qualified (1)

**NBA**: events discovered 50 → complete history 50 → valid forecast 50 → fresh odds available 9 → stale odds only 0 → three plus bookmakers 9 → fully evaluated 9 → markets evaluated 160 → markets positive ev 4 → events positive ev 4 → events passing all rules 0 → final recommendations 2
  - market rejections: EV below threshold (95), too few bookmakers (64), odds outside range (1)
  - primary blocker per event: no bookmaker prices yet (41), prices are in line with the sharp market (8), value only at long odds outside the allowed range (1)

**TENNIS**: events discovered 65 → complete history 7 → valid forecast 65 → fresh odds available 0 → stale odds only 0 → three plus bookmakers 0 → fully evaluated 0 → markets evaluated 0 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - primary blocker per event: no bookmaker prices yet (65)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 142, 'median_odds_age_h': 0.0, 'median_bookmakers': 18.0, 'share_3plus_books': 0.87}
- nfl: {'events_with_odds': 16, 'median_odds_age_h': 0.0, 'median_bookmakers': 22.0, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 9, 'median_odds_age_h': 0.0, 'median_bookmakers': 19, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 0, 'median_odds_age_h': None, 'median_bookmakers': None, 'share_3plus_books': None}

## The Odds API

{'skipped': None, 'credits_remaining_after': '212', 'credits_spent': 16, 'fetched': ['basketball_nba', 'americanfootball_nfl', 'soccer_uefa_champs_league', 'soccer_efl_champ', 'soccer_uefa_europa_conference_league', 'soccer_uefa_europa_league', 'soccer_netherlands_eredivisie'], 'matched': 89, 'unmatched': ['soccer_uefa_champs_league: Paris Saint Germain v AS Roma', 'soccer_efl_champ: Lincoln City v Wolverhampton Wanderers', 'soccer_efl_champ: Queens Park Rangers v Sheffield United', 'soccer_uefa_europa_conference_league: Brighton and Hove Albion v Universitatea Craiova', "soccer_uefa_europa_conference_league: Inter Club d'Escaldes v FC Copenhagen", 'soccer_uefa_europa_league: Juventus v Omonoia FC'], 'skipped_no_matching_event': [], 'bookmakers_requested': None, 'bookmakers_ignored': None, 'cost_mismatch': None}

## Providers

- football-data:fixtures: last success 2026-11-25T05:04:36+00:00
- football-data:E0: last success 2026-11-25T05:04:37+00:00
- football-data:E1: last success 2026-11-25T05:04:38+00:00
- football-data:SP1: last success 2026-11-25T05:04:39+00:00
- football-data:D1: last success 2026-11-25T05:04:40+00:00
- football-data:I1: last success 2026-11-25T05:04:41+00:00
- football-data:F1: last success 2026-11-25T05:04:42+00:00
- football-data:N1: last success 2026-11-25T05:04:43+00:00
- football-data:P1: last success 2026-11-25T05:04:44+00:00
- football-data:B1: last success 2026-11-25T05:04:45+00:00
- football-data:SC0: last success 2026-11-25T05:04:46+00:00
- espn:international: last success 2026-11-25T05:05:46+00:00
- the-odds-api: last success 2026-11-25T05:06:00+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-25T05:05:46+00:00
- espn:nba: last success 2026-11-25T05:05:47+00:00
- espn:tennis: last success 2026-11-25T05:06:17+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-25T05:05:56+00:00
- espn:club-fixtures: last success 2026-11-25T05:05:13+00:00
