# Sports Betting Doyen — diagnostics (2026-11-16 09:50 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 76 → complete history 74 → valid forecast 76 → fresh odds available 50 → stale odds only 0 → three plus bookmakers 18 → fully evaluated 18 → markets evaluated 309 → markets positive ev 11 → events positive ev 9 → events passing all rules 0 → final recommendations 10
  - market rejections: too few bookmakers (216), EV below threshold (76), odds outside range (10), insufficient team history (7)
  - primary blocker per event: too few bookmakers price these markets (31), no bookmaker prices yet (26), prices are in line with the sharp market (15), value only at long odds outside the allowed range (3), not enough history on one side (1)

**NFL**: events discovered 13 → complete history 13 → valid forecast 13 → fresh odds available 13 → stale odds only 0 → three plus bookmakers 13 → fully evaluated 13 → markets evaluated 154 → markets positive ev 12 → events positive ev 10 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (96), too few bookmakers (50), odds outside range (8)
  - primary blocker per event: prices are in line with the sharp market (8), value only at long odds outside the allowed range (4), too few bookmakers price these markets (1)

**NBA**: events discovered 51 → complete history 51 → valid forecast 51 → fresh odds available 8 → stale odds only 0 → three plus bookmakers 8 → fully evaluated 8 → markets evaluated 112 → markets positive ev 4 → events positive ev 4 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (87), too few bookmakers (24), odds outside range (1)
  - primary blocker per event: no bookmaker prices yet (43), prices are in line with the sharp market (6), too few bookmakers price these markets (1), value only at long odds outside the allowed range (1)

**TENNIS**: events discovered 60 → complete history 24 → valid forecast 60 → fresh odds available 4 → stale odds only 0 → three plus bookmakers 4 → fully evaluated 4 → markets evaluated 8 → markets positive ev 2 → events positive ev 2 → events passing all rules 0 → final recommendations 0
  - market rejections: EV below threshold (6), odds outside range (2)
  - primary blocker per event: no bookmaker prices yet (56), prices are in line with the sharp market (3), value only at long odds outside the allowed range (1)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 50, 'median_odds_age_h': 0.0, 'median_bookmakers': 1.0, 'share_3plus_books': 0.36}
- nfl: {'events_with_odds': 13, 'median_odds_age_h': 0.0, 'median_bookmakers': 18, 'share_3plus_books': 1.0}
- nba: {'events_with_odds': 8, 'median_odds_age_h': 0.0, 'median_bookmakers': 23.0, 'share_3plus_books': 1.0}
- tennis: {'events_with_odds': 4, 'median_odds_age_h': 0.0, 'median_bookmakers': 16.0, 'share_3plus_books': 1.0}

## The Odds API

{'skipped': None, 'credits_remaining_after': '377', 'credits_spent': 11, 'fetched': ['tennis_atp_finals', 'soccer_uefa_nations_league', 'basketball_nba', 'americanfootball_nfl', 'soccer_italy_serie_a'], 'matched': 43, 'unmatched': ['soccer_italy_serie_a: Como v Cagliari', 'soccer_italy_serie_a: Lazio v Lecce', 'soccer_italy_serie_a: Parma v AS Roma', 'soccer_italy_serie_a: Napoli v Torino', 'soccer_italy_serie_a: Juventus v Venezia', 'soccer_italy_serie_a: Bologna v Udinese', 'soccer_italy_serie_a: Sassuolo v Genoa', 'soccer_italy_serie_a: AC Milan v Frosinone', 'soccer_italy_serie_a: Atalanta BC v Inter Milan']}

## Providers

- football-data:fixtures: last success 2026-11-16T09:50:55+00:00
- football-data:E0: last success 2026-11-16T09:50:56+00:00
- football-data:E1: last success 2026-11-16T09:50:57+00:00
- football-data:SP1: last success 2026-11-16T09:50:58+00:00
- football-data:D1: last success 2026-11-16T09:50:59+00:00
- football-data:I1: last success 2026-11-16T09:51:00+00:00
- football-data:F1: last success 2026-11-16T09:51:01+00:00
- football-data:N1: last success 2026-11-16T09:51:02+00:00
- football-data:P1: last success 2026-11-16T09:51:03+00:00
- football-data:B1: last success 2026-11-16T09:51:04+00:00
- football-data:SC0: last success 2026-11-16T09:51:05+00:00
- espn:international: last success 2026-11-16T09:51:37+00:00
- the-odds-api: last success 2026-11-16T09:51:45+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-16T09:51:38+00:00
- espn:nba: last success 2026-11-16T09:51:38+00:00
- espn:tennis: last success 2026-11-16T09:51:53+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-16T09:51:42+00:00
