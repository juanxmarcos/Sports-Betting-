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

## Evaluated, not (yet) automated

| Source | Sport | Status | Notes |
|---|---|---|---|
| ESPN site API | multi | accessible | Undocumented, no published terms. Fallback for fixtures/results only |
| Understat | football | accessible | xG history. Terms unclear, so not scraped |
| Forebet | football | 403 | Independent prediction signal. Manual reference only |
| FBref | football | 403 | Sports-Reference bot policy |
| The Odds API | multi | key needed | Free tier ~500 credits/month. Best free live-odds API. Planned optional connector (`ODDS_API_KEY` env var) |
| Open-Meteo | weather | free (non-commercial) | Rate-limited on shared IPs |
| MLB Stats API | MLB | accessible | Schedules, results, probable pitchers |
| NHL api-web | NHL | accessible | Schedules, results, goalies |
| nflverse | NFL | GitHub releases | Verify from Actions |
| Basketball-Reference | NBA | accessible (200) | Strict rate limits (about 20 req/min); low-volume only |
| stats.nba.com | NBA | 403 from cloud IPs | Not used |
| Jeff Sackmann tennis_atp/wta | tennis | not verifiable here | CC BY-NC-SA. Verify from Actions |
| tennis-data.co.uk | tennis | 403 here | Has historical tennis odds. Verify from Actions |
