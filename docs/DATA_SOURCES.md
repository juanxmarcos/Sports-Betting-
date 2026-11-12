# Data source register

Every stored row carries `source`, `source_url` and a timestamp (`retrieved_at` for odds is
the HTTP `Last-Modified` time of the file, i.e. when football-data published that snapshot).

## Implemented

### football-data.co.uk (primary)
- **Access:** free CSV downloads; no key; robots/terms do not prohibit downloading the published files. We fetch about 11 small files per run with a descriptive User-Agent, cache them, and back off on errors. A 401, 403 or 429 aborts that source; we never circumvent it.
- **Files:** `mmz4281/{season}/{div}.csv` (results + stats + odds); `fixtures.csv` (upcoming matches with current odds).
- **Fields used:** Div, Date, Time (UK local, converted to UTC), Home/AwayTeam, FTHG/FTAG, HxG/AxG (2026-27 onwards, all 10 configured leagues), and odds for 1X2, O/U 2.5 and Asian handicap (`AHh` line). Pre-match odds come from up to 7–10 bookmakers plus Betfair Exchange, with Max/Avg aggregates; closing odds are the `C` columns.
- **Cadence:** results typically Sun/Mon and after midweek rounds; `fixtures.csv` typically Tue and Fri. **Implication:** odds snapshots can be one to three days old by kick-off. The pipeline excludes snapshots older than 96h and reports their timestamp.
- **Coverage:** E0, E1, SP1, D1, I1, F1, N1, P1, B1 and SC0 configured; more divisions are available. History goes back to the 1990s. Pinnacle odds stopped partway through 2025-26 and are absent in 2026-27, so the live consensus uses Betfair Exchange, then Pinnacle, then the market average.
- **Quality issues found:** illiquid exchange quotes (for example 1.02/1.12 on a two-way O/U market). These are handled by an overround sanity filter (0.97–1.20) before any book is used.

### National teams: martj42/international_results + ESPN scoreboard
- **History:** `raw.githubusercontent.com/martj42/international_results/master/results.csv` (CC0). About 50k men's internationals since 1872, with date, teams, score, tournament, city, country and a neutral flag. It is updated periodically; at the time of checking it ran to 2026-10-06.
- **Fixtures, recent results, odds:** `site.api.espn.com/apis/site/v2/sports/soccer/{competition}/scoreboard?dates=YYYYMMDD`. This is undocumented and keyless. It covers Nations League, friendlies, World Cup/Euro/AFCON qualifying, CONCACAF Nations League and the major tournaments. Odds are DraftKings only (American odds, converted to decimal), with moneyline open/current, draw, total and spread.
- **Load:** about 16 competitions × 3 days per run. Past dates are cached (persisted in Actions via `actions/cache`). On first run, a gap fill of up to 60 days covers results after the dataset's last update.
- **Name matching:** an ESPN→dataset alias table (for example Türkiye→Turkey, Congo DR→DR Congo, Czechia→Czech Republic). Unmatched teams are reported as warnings and never guessed.

### The Odds API (optional, free key)
- **Access:** free plan, about 500 credits/month. The key lives in the `ODDS_API_KEY` GitHub Actions secret, is never logged, and is stripped from every stored URL. Without a key the connector skips itself.
- **Requests:** `/v4/sports` and `/v4/sports/{key}/events` are free. `/v4/sports/{key}/odds?regions=eu&markets=h2h,totals` costs 2 credits. The `eu` region includes Pinnacle and Betfair Exchange, which are the sharp consensus references.
- **Budget:** each run spends at most min(8, (remaining − 20 reserve) / runs left this month) credits. It spends only on competitions with events in the next 36h: internationals first, then club leagues.
- **Matching:** an Odds API event is matched to our event when kick-off is within ±3h and both team names are similar (normalised; difflib ≥ 0.6). Unmatched events are logged, never guessed.
- **Timestamps:** each bookmaker's own `last_update` is stored as `retrieved_at`.

## Evaluated, not (yet) automated

| Source | Sport | Status | Notes |
|---|---|---|---|
| Understat | football | accessible | xG history. Terms unclear, so not scraped |
| Forebet | football | 403 | Independent prediction signal. Manual reference only |
| FBref | football | 403 | Sports-Reference bot policy |
| Open-Meteo | weather | free (non-commercial) | Rate-limited on shared IPs |
| MLB Stats API | MLB | accessible | Schedules, results, probable pitchers |
| NHL api-web | NHL | accessible | Schedules, results, goalies |
| nflverse | NFL | GitHub releases | Verify from Actions |
| Basketball-Reference | NBA | accessible (200) | Strict rate limits (about 20 req/min); low-volume only |
| stats.nba.com | NBA | 403 from cloud IPs | Not used |
| Jeff Sackmann tennis_atp/wta | tennis | not verifiable here | CC BY-NC-SA. Verify from Actions |
| tennis-data.co.uk | tennis | 403 here | Has historical tennis odds. Verify from Actions |
