# Sports Betting Doyen — diagnostics (2026-11-16 02:12 UTC)

## Opportunity funnel (next 7 days)

**SOCCER**: events discovered 76 → complete history 74 → valid forecast 76 → fresh odds available 38 → stale odds only 0 → three plus bookmakers 18 → fully evaluated 18 → markets evaluated 282 → markets positive ev 20 → events positive ev 13 → events passing all rules 3 → final recommendations 10
  - market rejections: too few bookmakers (185), EV below threshold (78), odds outside range (9), insufficient team history (7)
  - primary blocker per event: no bookmaker prices yet (38), too few bookmakers price these markets (20), prices are in line with the sharp market (11), qualified (3), value only at long odds outside the allowed range (3), not enough history on one side (1)

**NFL**: events discovered 13 → complete history 13 → valid forecast 13 → fresh odds available 12 → stale odds only 1 → three plus bookmakers 2 → fully evaluated 2 → markets evaluated 76 → markets positive ev 2 → events positive ev 1 → events passing all rules 0 → final recommendations 0
  - market rejections: too few bookmakers (68), EV below threshold (7), odds outside range (1)
  - primary blocker per event: too few bookmakers price these markets (11), prices are in line with the sharp market (1), only stale prices available (1)

**NBA**: events discovered 51 → complete history 51 → valid forecast 51 → fresh odds available 3 → stale odds only 0 → three plus bookmakers 0 → fully evaluated 0 → markets evaluated 18 → markets positive ev 0 → events positive ev 0 → events passing all rules 0 → final recommendations 0
  - market rejections: too few bookmakers (18)
  - primary blocker per event: no bookmaker prices yet (48), too few bookmakers price these markets (3)

**TENNIS**: events discovered 44 → complete history 24 → valid forecast 44 → fresh odds available 2 → stale odds only 0 → three plus bookmakers 2 → fully evaluated 2 → markets evaluated 4 → markets positive ev 2 → events positive ev 2 → events passing all rules 0 → final recommendations 0
  - market rejections: odds outside range (2), EV below threshold (2)
  - primary blocker per event: no bookmaker prices yet (42), value only at long odds outside the allowed range (1), prices are in line with the sharp market (1)

## Odds freshness (events in next 48h)

- soccer: {'events_with_odds': 38, 'median_odds_age_h': 0.0, 'median_bookmakers': 1.0, 'share_3plus_books': 0.47}
- nfl: {'events_with_odds': 13, 'median_odds_age_h': 0.0, 'median_bookmakers': 1, 'share_3plus_books': 0.15}
- nba: {'events_with_odds': 3, 'median_odds_age_h': 0.0, 'median_bookmakers': 1, 'share_3plus_books': 0.0}
- tennis: {'events_with_odds': 2, 'median_odds_age_h': 5.1, 'median_bookmakers': 18.0, 'share_3plus_books': 1.0}

## The Odds API

{'skipped': None, 'credits_remaining_after': '388', 'credits_spent': 12, 'fetched': ['soccer_germany_bundesliga', 'soccer_belgium_first_div', 'soccer_france_ligue_one', 'soccer_spain_la_liga', 'soccer_efl_champ', 'soccer_epl'], 'matched': 0, 'unmatched': ['soccer_germany_bundesliga: Bayern Munich v 1. FC Köln', 'soccer_germany_bundesliga: Bayer Leverkusen v SC Paderborn', 'soccer_germany_bundesliga: Borussia Monchengladbach v Borussia Dortmund', 'soccer_germany_bundesliga: Eintracht Frankfurt v TSG Hoffenheim', 'soccer_germany_bundesliga: Elversberg v SC Freiburg', 'soccer_germany_bundesliga: Union Berlin v RB Leipzig', 'soccer_germany_bundesliga: FC Schalke 04 v VfB Stuttgart', 'soccer_germany_bundesliga: Augsburg v FSV Mainz 05', 'soccer_germany_bundesliga: Werder Bremen v Hamburger SV', 'soccer_belgium_first_div: Cercle Brugge KSV v Westerlo', 'soccer_belgium_first_div: Charleroi v Sint Truiden', 'soccer_belgium_first_div: Genk v RAAL La Louvière', 'soccer_belgium_first_div: KV Mechelen v Club Brugge', 'soccer_belgium_first_div: SV Zulte-Waregem v Royal Antwerp', 'soccer_belgium_first_div: SK Beveren v Gent', 'soccer_belgium_first_div: KV Kortrijk v Union Saint-Gilloise', 'soccer_belgium_first_div: Anderlecht v Leuven', 'soccer_belgium_first_div: Lommel SK v Standard Liege', 'soccer_france_ligue_one: Troyes v Le Havre', 'soccer_france_ligue_one: Nice v Paris Saint Germain']}

## Providers

- football-data:fixtures: last success 2026-11-16T02:12:04+00:00
- football-data:E0: last success 2026-11-16T02:12:05+00:00
- football-data:E1: last success 2026-11-16T02:12:05+00:00
- football-data:SP1: last success 2026-11-16T02:12:05+00:00
- football-data:D1: last success 2026-11-16T02:12:05+00:00
- football-data:I1: last success 2026-11-16T02:12:05+00:00
- football-data:F1: last success 2026-11-16T02:12:05+00:00
- football-data:N1: last success 2026-11-16T02:12:05+00:00
- football-data:P1: last success 2026-11-16T02:12:05+00:00
- football-data:B1: last success 2026-11-16T02:12:06+00:00
- football-data:SC0: last success 2026-11-16T02:12:06+00:00
- espn:international: last success 2026-11-16T02:12:48+00:00
- the-odds-api: last success 2026-11-16T02:13:02+00:00 · last error 2026-11-12T21:48:27+00:00 422 Client Error: Unprocessable Entity for url: https://api.the-odds-api.com/v4/sports/soccer_uefa_nations_league/odds?regions=eu&markets=h2h%2Ctotals%2Cbtts&oddsFormat=decimal&dateFormat=iso&apiKey=REDACTED
- espn:nfl: last success 2026-11-16T02:12:49+00:00
- espn:nba: last success 2026-11-16T02:12:50+00:00
- espn:tennis: last success 2026-11-16T02:13:12+00:00
- espn:golf: last success 2026-11-12T20:55:40+00:00
- espn:context: last success 2026-11-16T02:12:56+00:00
