# Sports Betting Doyen — Data source register

> **Latest audit: 2026-11-13** (issue #15, phase 1). The measured baseline, the provider checks and the
> prioritised next steps are in [Source audit 2026-11-13](#source-audit-2026-11-13) at the end of this
> file. The numbers come from `python -m sbi coverage` (`reports/source_coverage.md`).

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
- **Access:** free "Starter" plan, 500 credits/month (re-verified 2026-11-13 on the-odds-api.com, and by the provider's own usage headers in production: 500 → 472 after the first two days). The key lives in the `ODDS_API_KEY` GitHub Actions secret, is never logged, and is stripped from every stored URL. Without a key the connector skips itself.
- **Requests:** `/v4/sports` and `/v4/sports/{key}/events` are free. `/v4/sports/{key}/odds?regions=eu&markets=h2h,totals` costs 2 credits. The `eu` region includes Pinnacle and Betfair Exchange, which are the sharp consensus references.
- **Budget:** a daily allowance of (remaining − 20 reserve) / days left in the month, shared by the day's runs and capped at 12 credits per run (`sbi/sources/odds_api.py: budget`). A competition is fetched only when it has events in the next 7 days and its refresh is due (more often close to start time): NFL/NBA, internationals and tennis first, then club leagues.
- **Matching:** an Odds API event is matched to our event when kick-off is within ±3h and both team names are similar (normalised; difflib ≥ 0.6). Unmatched events are logged, never guessed.
- **Timestamps:** each bookmaker's own `last_update` is stored as `retrieved_at`.

### NFL / NBA / tennis (Doyen v0.2)
- **ESPN public scoreboards** (`site.api.espn.com/apis/site/v2/sports/{football/nfl|basketball/nba|tennis/atp|tennis/wta}/scoreboard`): fixtures, results, DraftKings odds (NFL/NBA), full tennis draws with set scores. These endpoints are undocumented, so usage is kept light and past dates are cached.
- **nflverse games.csv** (`raw.githubusercontent.com/nflverse/nfldata`): every NFL game since 1999 with closing moneyline, spread and total, plus ESPN game ids.
- **The Odds API**: `americanfootball_nfl`, `basketball_nba` (h2h, spreads, totals = 3 credits) and active `tennis_*` tournament keys (h2h = 1 credit), within the daily credit allowance.
- **Not available free:** historical NBA and tennis odds (models cannot be validated against the market); reliable injury and lineup feeds.

### ESPN game context (Doyen v0.3)
- **League injury reports** (`/sports/{basketball/nba|football/nfl}/injuries`), one request each per run. Current status is kept in `injuries_current`, and every new, changed or cleared status is appended to `injury_changes`. These changes trigger pick reassessment notes.
- **Game summaries** (`/summary?event=<id>`) for events in the next 36h:
  - ESPN Analytics matchup predictor, stored separately as an *external forecast* (`external_forecasts`).
  - Team statistical leaders, used to flag injured *key* players.
  - Soccer: extra bookmakers (e.g. Bet365) and starting lineups (`lineups`, confirmed when 11 starters are listed).
- **Discrepancies:** when ESPN Analytics differs from the bookmakers or Doyen's model by ≥ 10 points, the gap is flagged on the match's Details page. It is never resolved by picking a side.
- **Bookmaker normalisation** (`sbi/sources/books.py`): the same bookmaker from two feeds counts once (e.g. "Bet 365" = "Bet365"), and in-play feeds are excluded.

### nflverse play-by-play (evaluated feature)
`github.com/nflverse/nflverse-data/releases` is an open dataset intended for programmatic download. Team EPA/play features were tested in the NFL model and **not adopted**: no out-of-sample gain (see METHODOLOGY §11).

## Candidate sources reviewed 2026-11-12 (automated-access check)
| Source | Result | Decision |
|---|---|---|
| Forebet, FBref, SofaScore (site + API), Pro Football Reference, ATP Tour | 403 / bot protection | Not used: no circumvention |
| Flashscore, FotMob, OddsPortal | Reachable, but terms prohibit scraping (FotMob API disallowed by robots) | Not used |
| Oddschecker | 403 | Not used |
| WorldFootball | 403 | Not used |
| Understat | Reachable, robots allow | Not needed: football-data.co.uk now carries xG for all covered leagues |
| Basketball-Reference, NFL.com, PFF, WTA, ITF, Tennis Abstract, Ultimate Tennis Statistics | Reachable | Not integrated: terms/rate limits restrict bulk automated use, or data is behind JS/paywall; ESPN covers the needed context |
| official.nba.com injury report | Reachable (PDF) | ESPN injuries endpoint used instead (structured, same information) |
| stats.nba.com | Blocks cloud IPs | Not used |
| pbpstats API | Reachable | Candidate for NBA efficiency features (next step) |

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

## Source audit 2026-11-13

Scope: Soccer (clubs and internationals), NFL, NBA and Tennis only. This is the **baseline before any
new connector**. Everything below was either measured from the stored database or checked against the
provider's own pages on 2026-11-13. Where a check failed, it says so; nothing is assumed.

### How to reproduce

```bash
python -m sbi coverage                      # reads the database read-only; no network calls
python -m sbi coverage --as-of 2026-11-13T12:17:02+00:00 --baseline   # how the baseline was frozen
```

- `reports/source_coverage.md`: the full matrix (sport × competition × market × source), providers,
  credentials by presence only, credit use and stored history.
- `data/coverage/baseline_2026-11-13.json`: the frozen "before". Later runs print the change against it.
- The command is not part of the 2-hour job and is not shown on the public site.

### Measured baseline (events starting in the next 7 days, as of the 12:17 UTC run)

| Sport | Scheduled | With any quote | With 3+ independent operators | With a sharp reference (Pinnacle / Betfair Exchange) |
|---|---|---|---|---|
| Soccer | 146 | 57 | 26 | 26 |
| NBA | 52 | 9 | 9 | 9 |
| NFL | 14 | 14 | 14 | 13 |
| Tennis | 51 | 6 | 6 | 2 |

*Operators* counts brand aliases and books with a shared owner or pricing platform once.

What the numbers say:
- **Independent comparison depends on one vendor.** Every event with 3+ operators or a sharp reference
  gets them from The Odds API. ESPN contributes one bookmaker (DraftKings). football-data.co.uk
  contributed nothing to this window: it is an international break, and its last stored fixtures
  snapshot was dated 2026-11-06.
- **Soccer internationals outside the UEFA Nations League have one operator.** AFCON qualifying
  (15 priced of 39), CONCACAF Nations League (6 of 26) and friendlies (10 of 37) have DraftKings
  only, so no independent comparison is possible and no value claim can be made.
- **Tennis is thin.** 6 of 51 scheduled matches are priced, all from the ATP/WTA Finals keys.
  The ATP matches have 4 operators and no sharp reference. ESPN supplies no tennis odds.
- **NBA is priced about a day ahead** (9 of 52). That is how the books post NBA lines, not a fault.
- **39 stored bookmaker names are 29 bookmakers and 25 operators.** 15 of them have no operator
  mapping and are treated as independent without verification (list in the report).
- **History stored in the database is short.** NBA 20 finished games, NFL 1, tennis 41. Closing odds
  are stored only for events Doyen predicted (by design), and no closing rows are stored yet.
- **Lineups:** 124 team rows, none confirmed (11 named starters) at the time of the run.
- **Housekeeping found:** 2 soccer events still marked `scheduled` more than 6 hours after kick-off,
  and a leftover `espn:golf` provider row (golf is not a supported sport).

### Configured versus working

| Source | Credential | Status on 2026-11-13 |
|---|---|---|
| football-data.co.uk (11 files) | none | Working. All 11 succeeded in the 12:16 UTC run |
| ESPN scoreboards, injuries, summaries | none | Working (internationals, NFL, NBA, tennis, context) |
| martj42 international results | none | Reachable (checked directly). Still ends 2026-10-06; ESPN fills the gap |
| nflverse games.csv | none | Reachable (checked directly). 2026 schedule through week 18 |
| The Odds API | `ODDS_API_KEY` (GitHub secret) | Working in production. 28 credits used in two days, 472 left. One HTTP 422 on 2026-11-12 (a `btts` market request, since removed) |

Runs that log "ODDS_API_KEY not set" are local or research sessions without the secret. That is
expected: the connector skips itself.

### The Odds API: what the free plan really allows

Checked on `https://the-odds-api.com/` and `/liveapi/guides/v4/` on 2026-11-13.
- **Plan:** Starter, $0, 500 credits/month, "most bookmakers", all markets. Paid plans start at $30/month.
- **Cost:** markets × regions per `/odds` call. `/sports` and `/events` are free, and so are empty responses.
- **Historical odds:** the pricing table and the historical section disagree. Treat it as paid-only.
- **Terms** (`/terms-and-conditions.html`): storing, displaying and model training are allowed.
  Reselling or redistributing the data "as a standalone data product" is not. Attribution is optional.
  **Owner to note:** `data/sbi.sqlite` in this public repository contains raw Odds API quotes. It is a
  research database, not a data product, but the owner should decide whether that is comfortable.
- **Overage:** the terms do not say what happens at zero credits. The code keeps a 20-credit reserve.
- **Headroom:** current use is about 14 credits/day, which is roughly the whole monthly allowance.
  Adding a region (`uk`: 21 books including Smarkets; `us`: the regulated US books) doubles the cost of
  each call. **More bookmakers from this API means fewer refreshes, or a paid plan. Neither is done here.**
- **Same name, different company:** `odds-api.io` is a separate provider. It has no free tier
  ("New free keys are paused") and starts at £49/month. Not used.

### Candidate sources checked 2026-11-13

One polite request per URL with the project User-Agent. A 401, 403 or 429 ends the check.

| Source | URL checked | Result | Free tier | Decision |
|---|---|---|---|---|
| nflverse injuries | `github.com/nflverse/nflverse-data/releases/download/injuries/injuries_2026.csv` | 200, updated 2026-11-13 15:18 GMT | Open data, repository lists CC-BY-4.0; no key | **Next adapter.** Official report status plus practice participation, which ESPN does not give |
| football-data.co.uk lower divisions | `football-data.co.uk/fixtures.csv` | 200, updated 2026-11-13 14:16 GMT; 51 fixtures in E2, E3, EC, SC1–SC3, SP2 | Free, no key | **Candidate.** Same file already fetched: 6 bookmakers (5 operators) plus Betfair Exchange. Each division needs its own backtest before any pick |
| football-data.co.uk extra leagues | `football-data.co.uk/new/ARG.csv` (16 countries) | 200, updated 2026-11-10 | Free, no key | History only: closing odds, no pre-match prices. Useful for validation, not for picks |
| football-data.org | `football-data.org/pricing` | 200 | 12 competitions, 10 calls/min, delayed scores; **no odds, lineups or statistics**; free token | Rejected for now: adds fixtures we already have |
| BALLDONTLIE | `docs.balldontlie.io` | 200 | Teams, players and games only, 5 requests/min, key required. Stats and injuries from $9.99/month, odds from $39.99/month | Rejected: the free tier adds nothing over ESPN. Do not start the 7-day trial |
| API-Football | `api-football.com/pricing` | 403 | Not verifiable | Not used |
| Jeff Sackmann tennis_atp / tennis_wta | `raw.githubusercontent.com/JeffSackmann/tennis_atp/master/…` | 404 | Not verifiable (licence was CC BY-NC-SA) | Blocked: cannot confirm the files or licence |
| tennis-data.co.uk | `tennis-data.co.uk/alldata.php` | 403 | Not verifiable | Not used |
| pbpstats API | `api.pbpstats.com/docs` | 200 (API docs) | No published terms found | Not integrated until the terms are known |
| NBA CDN schedule / odds JSON | `cdn.nba.com/static/json/…` | 403 | n/a | Not used |
| FiveThirtyEight SPI | `projects.fivethirtyeight.com/soccer-api/club/spi_matches.csv` | Redirects to a news page | Dataset no longer served | Rejected |
| ClubElo | `api.clubelo.com` | 502 / no connection | Not verifiable | Not used |
| OpenLigaDB | `api.openligadb.de/getmatchdata/bl1/2026` | 200 | Keyless; licence not verified here | Low value: Bundesliga fixtures and results only, no odds |
| TheSportsDB | `thesportsdb.com/free_sports_api` | 200 | Free tier exists, limits not stated; no odds | Low value |
| SportsDataIO | `api.sportsdata.io` | 401 | Key and paid plan or trial | Not used |

**No new zero-cost source of fresh, independent bookmaker prices was found.** The realistic free gains
are context data (NFL practice reports), wider coverage from a file already downloaded (lower English,
Scottish and Spanish divisions) and history for validation.

### Third-party forecasts and advisers

- Stored today: ESPN Analytics only (15 events), kept in `external_forecasts` as context.
- Forebet returns 403 and the FiveThirtyEight feed is gone. No other forecast source passed the access check.
- A forecast is a model, not a price. It never counts toward the "3+ bookmakers" rule, and none is used
  as an input until it has been scored out of sample against the market.

### Same-book parlay prices: exact blockers

1. No connected source returns a bookmaker's own combined price. The Odds API guide documents single
   markets only, and ESPN publishes single-market DraftKings lines.
2. Sportsbook sites that show combined prices sit behind logins, geo-blocks and anti-bot protection.
   These are not bypassed.
3. So a combined price can only be the product of single-leg prices, which is **not** a
   bookmaker-offered price and is never described as one. See `docs/PARLAYS.md`.

### Prioritised next steps (each a separate, reviewable PR)

1. **NFL practice and injury reports from nflverse** (free, no key): adapter with recorded fixtures,
   stored as context only. Any model use needs a walk-forward test first.
2. **Lower divisions from football-data.co.uk** (free, already downloaded): ingest fixtures and odds
   for E2, E3, EC, SP2 and SC1–SC3; publish nothing until each division passes its own backtest.
3. **Operator mapping:** verify ownership for the 15 unmapped bookmakers so independence counts are not
   overstated. This can only make the "3+ bookmakers" rule stricter.
4. **The Odds API visibility:** record which mapped competitions the API lists as active but the budget
   skipped, so gaps like AFCON qualifying can be explained rather than guessed.
5. **Housekeeping:** events stuck in `scheduled` after kick-off; the leftover `espn:golf` row.

### Decisions only the owner can make

- **A paid odds plan** (The Odds API from $30/month) is the only verified way to add regions and
  refresh more often. Nothing paid is enabled and no trial is started.
- **Tennis history:** if the owner can confirm the current location and licence of the Sackmann
  archives, an adapter can follow. The licence was non-commercial.
- **Public database:** whether raw Odds API quotes should stay in the public `data/sbi.sqlite`.
