# Sports Betting Doyen — Data source register

> **Latest audit: 2026-11-13** (issue #15, phase 1). The measured baseline, the provider checks and the
> prioritised next steps are in [Source audit 2026-11-13](#source-audit-2026-11-13) at the end of this
> file. The numbers come from `python -m sbi coverage` (`reports/source_coverage.md`).
>
> **Soccer league expansion: 2026-11-13, revised 2026-11-16** (issue #18, phase 2 of #15). Seven lower
> divisions are *monitoring only* and are **not in the public database**: they can be fetched into a
> local, gitignored file with an opt-in command. See
> [Soccer league expansion 2026-11-13](#soccer-league-expansion-2026-11-13), which also states the
> source-use and redistribution rights for football-data.co.uk.

> **Third-party forecast sites** (The Open Model, Football Analytics, Skorbot) were audited on
> 2026-11-16 (issue #23). None is ingested. See [FORECAST_SOURCES.md](FORECAST_SOURCES.md).

Every stored row carries `source`, `source_url` and a timestamp (`retrieved_at` for odds is
the HTTP `Last-Modified` time of the file, i.e. when football-data published that snapshot).

## Implemented

### football-data.co.uk (primary)
- **Access:** free CSV downloads; no key; robots/terms do not prohibit downloading the published files. We fetch about 11 small files per run with a descriptive User-Agent, cache them, and back off on errors. (The opt-in, local-only `python -m sbi monitor-leagues` fetches `fixtures.csv` and 7 more season files, at most once a day, only when the owner runs it.) A 401, 403 or 429 aborts that source; we never circumvent it.
- **Files:** `mmz4281/{season}/{div}.csv` (results + stats + odds); `fixtures.csv` (upcoming matches with current odds).
- **Fields used:** Div, Date, Time (UK local, converted to UTC), Home/AwayTeam, FTHG/FTAG, HxG/AxG (2026-27 onwards, all 10 configured leagues), and odds for 1X2, O/U 2.5 and Asian handicap (`AHh` line). Pre-match odds come from up to 7–10 bookmakers plus Betfair Exchange, with Max/Avg aggregates; closing odds are the `C` columns.
- **Cadence:** results typically Sun/Mon and after midweek rounds; `fixtures.csv` typically Tue and Fri. **Implication:** odds snapshots can be one to three days old by kick-off. The pipeline excludes snapshots older than 96h and reports their timestamp.
- **Coverage:** two explicit tiers in `sbi/leagues.py`. *Active* (analysed, may produce picks): E0, E1, SP1, D1, I1, F1, N1, P1, B1 and SC0. *Monitoring* (never priced or published, and **not in the public database**): E2, E3, EC, SC1, SC2, SC3 and SP2, available only through the opt-in local-only command. Any division the scheduled job did not ask for is counted in the ingest log and not stored. History goes back to the 1990s. Pinnacle odds stopped partway through 2025-26 and are absent in 2026-27, so the live consensus uses Betfair Exchange, then Pinnacle, then the market average.
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

### nflverse injury reports: practice participation and game designations (opt-in, issue #17)

Adapter `sbi/sources/nflverse_injuries.py`, report `sbi/nfl_reports.py`, command `python -m sbi nfl-reports`.
**Informational risk flags only.** Nothing here feeds model probabilities, calibration, EV thresholds
or pick selection; that needs its own walk-forward validation first. Nothing is shown on the public site.

**Source checks (2026-11-13, one polite request per URL with the project User-Agent):**

| Question | Finding | Where checked |
|---|---|---|
| File | `github.com/nflverse/nflverse-data/releases/download/injuries/injuries_<season>.csv`, one file per season, 2009 onwards. 2026 file: 355 KB, 3,121 rows | HTTP 200 |
| Licence | CC-BY-4.0. Attribution "nflverse" is given in the report and here | `nflverse-data/LICENSE.md` |
| Automated use | The repository states it "holds automated data releases" to be downloaded with nflreadr "or manually". No key, no cost, no published rate limit | `nflverse-data/README.md` |
| Cadence | "Injury Data updates every day at 7AM UTC throughout the season" | nflreadr data schedule article |
| Conditional requests | `If-None-Match` and `If-Modified-Since` both return 304 with an empty body | measured |
| Field meanings | `report_status`: "Player's status for game on official injury report". `practice_status`: "Player's participation in practice" | nflreadr injuries data dictionary |
| Original upstream | Not stated in the dictionary. nflverse is a volunteer project, **not** an official NFL feed; treat it as a faithful copy, not as the league's own publication | not verifiable here |

**What it gives that ESPN does not:** structured practice participation (DNP / Limited / Full) kept
apart from the official designation (Out / Doubtful / Questionable), keyed by the NFL player id
(`gsis_id`), with three earlier seasons in the same shape for later validation.

**Limits found (stated, not worked around):**
- **One practice value per player-week, not one per day.** The day-by-day sequence is only available
  from the moment Doyen starts logging changes between files (`nfl_report_updates`).
- **No per-row time from 2025 on.** `date_modified` exists in the 2023 and 2024 files and is absent in
  2025 and 2026. The only provider time is then the file's HTTP `Last-Modified`
  (`source_published_at`); Doyen's own retrieval time is stored separately (`first_seen`, `observed_at`).
- **Slower than ESPN.** A daily file means Friday designations appear the next morning. At 16:39 UTC
  on Friday 2026-11-13 the file (published 15:18 UTC) had designations for 2 of 28 upcoming teams;
  ESPN already showed a status for 153 players who were on the nflverse report with practice status
  only. ESPN's statuses are editorial and are not the official designation, so the two are compared,
  never merged.
- **"No rows" is ambiguous.** A team with no rows for a game week either has nothing to report or has
  not been published yet (Monday-night teams on a Friday, for example). The feed cannot tell these apart.
- **No confirmed starting quarterback.** The report shows last game's starter (from results in
  `games.csv`), whether he is on the injury report, and whether the nflverse schedule file lists
  someone else. That schedule entry is unconfirmed. The nflverse depth-chart file was checked and not
  used: 75 MB per season, too heavy for the 2-hour job, and a depth chart is not a confirmed starter either.
- Teams before relocation (OAK, SD, STL) are not in the team table and are skipped and counted.

**Measured coverage (provider files, 2026-11-13).** Team-games are counted against the nflverse schedule.

| Season | Rows | Players | Team-games with rows / scheduled | With a designation | Out | Doubtful | Questionable | DNP | Limited | Full | Rows with provider time |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2023 | 5,599 | 1,413 | 555 / 556 | 545 | 996 | 142 | 1,583 | 1,588 | 1,453 | 2,525 | 5,599 |
| 2024 | 6,213 | 1,459 | 569 / 570 | 556 | 1,116 | 194 | 1,511 | 1,537 | 1,496 | 3,145 | 6,213 |
| 2025 | 6,068 | 1,453 | 570 / 570 | 558 | 1,382 | 120 | 1,283 | 1,620 | 1,379 | 3,024 | 0 |
| 2026 (to week 10) | 3,121 | 1,108 | 298 / 300 | 267 | 596 | 43 | 600 | 802 | 749 | 1,566 | 0 |

Against the phase-1 baseline (`data/coverage/baseline_2026-11-13.json`), which had no practice data
at all and 800 ESPN NFL rows (215 of them Out, Doubtful or Questionable): one fetch on a copy of the
database added 3,121 player-weeks for 32 teams over 10 weeks (1,239 with a designation), and for the
14 upcoming games mapped 14 of 14 to a game week, with 300 week-10 rows for 26 teams (92 DNP, 102
Limited, 106 Full). A second run returned 304 and wrote no rows. `python -m sbi coverage` lists the
feed under *Context feeds* once the tables exist.

**How it behaves:**
- One conditional GET per season file per run. Unchanged file: a 304 and no writes. Cache: one file
  per URL, overwritten.
- 401, 403 and 429 stop at once with no retry. Timeouts and 5xx get three attempts with backoff, then
  the run keeps what is stored and reports its age. A 404 means the season file is not published yet.
- A file that is not the expected CSV, has no usable rows, is for another season, or would remove
  more than a fifth of the stored season at once is rejected whole and nothing is written.
- Rows with an unknown team, a missing or malformed player id, or a non-numeric week are skipped and
  counted. Duplicates: identical rows collapse; conflicting rows keep the later `date_modified`, and
  are both dropped when the file gives no time to choose by.
- Tables (additive): `nfl_report_current` (latest state per player-week), `nfl_report_updates`
  (append-only log of new, changed, retracted and restored rows) and `nfl_report_fetches` (every
  attempt and its outcome). A retracted row is kept and marked, never deleted.
- ESPN comparison pairs players by name inside one team only, because ESPN carries no shared id.
  A name that is not unique on a team is left unpaired and counted.

**Status: opt-in, not part of the 2-hour job.** The licence and the provider's stated purpose permit
automated downloads, and the fixture tests cover the failure modes, but the adapter has one live run
behind it, not weeks. To enable it in production the owner sets `SBI_NFL_REPORTS=1` in the
`Daily pipeline` step of `.github/workflows/daily.yml`; the step then costs one small conditional
request per run and can only mark its own job `partial`. Until then, run it by hand:

```bash
python -m sbi nfl-reports                       # fetch the current season, write reports/nfl_availability.md
python -m sbi nfl-reports --no-fetch            # report from what is stored
python -m sbi nfl-reports --history 2023 2024 2025 2026   # also measure coverage of those season files
```

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

These are stored, delayed quotes used for research. None is a live or executable price.

| Sport | Scheduled | Any quote | Observed fresh | Bookmaker-timed fresh | 3+ operators, lower bound | 3+ operators, upper bound (provisional) | Sharp reference |
|---|---|---|---|---|---|---|---|
| Soccer | 146 | 57 | 57 | 26 | 26 | 26 | 26 |
| NBA | 52 | 9 | 9 | 9 | 9 | 9 | 9 |
| NFL | 14 | 14 | 14 | 14 | 14 | 14 | 13 |
| Tennis | 51 | 6 | 6 | 6 | 2 | 6 | 2 |

How the two caveats are measured:

- **Operators are a range, not one number.** The *lower bound* counts only bookmakers whose owner or
  pricing platform is recorded in the map in `sbi/sources/books.py`. The *upper bound* also treats every
  bookmaker of unknown ownership as a separate operator. Unknown ownership is never assumed
  independent, so anything above the lower bound is provisional until it is verified.
  - Stored today: 29 bookmakers, of which **10 are known operators** and **15 have unknown ownership**
    (1xBet, BetAnything, BetVictor, Betclic, Betfred, Codere, Coolbet, DraftKings, Everygame, GTbets,
    Marathon Bet, Matchbook, MyBookie.ag, PMU, Tipico). Independent operators overall: between 10 and 25.
  - The map itself is best-effort and was not re-verified in this audit.
- **Fresh has two meanings, reported separately.** A quote's stored time (`retrieved_at`) means
  different things by source:

  | Source | What the stored time is | Evidence of a recent reprice? |
  |---|---|---|
  | The Odds API | The bookmaker's own last-update time, as passed on by the API | Yes, as reported by the provider |
  | football-data.co.uk | Publication time of the file (HTTP `Last-Modified`) | No. Prices were collected before publication |
  | ESPN | When Doyen first fetched that price | No. It shows the price was recently *observed*; the bookmaker's update time is unknown |

  *Observed fresh* accepts any of these within 24h. *Bookmaker-timed fresh* accepts only the first.
  An ESPN age of 0.0h therefore means "seen in the last run", not "repriced in the last run".
- Even bookmaker-timed quotes are delayed copies. The Odds API notes that its Pinnacle odds come
  "from public website, which may incur a delay".

What the numbers say:
- **Independent comparison depends on one vendor.** Every event with 3+ operators or a sharp reference
  gets them from The Odds API. ESPN contributes one bookmaker (DraftKings, ownership not yet in the
  map). football-data.co.uk contributed nothing to this window: it is an international break, and its
  last stored fixtures snapshot was dated 2026-11-06.
- **Soccer internationals outside the UEFA Nations League have one bookmaker.** AFCON qualifying
  (15 priced of 39), CONCACAF Nations League (6 of 26) and friendlies (10 of 37) have DraftKings
  only, observed by fetch time. No independent comparison is possible and no value claim can be made.
- **Soccer shows 57 observed fresh but only 26 bookmaker-timed.** The other 31 are ESPN-only events.
- **Tennis is thin, and thinner once unknown ownership is excluded.** 6 of 51 scheduled matches are
  priced, all from the ATP/WTA Finals keys. Only 2 reach 3+ known operators; the 4 ATP matches rely on
  bookmakers of unknown ownership and have no sharp reference. ESPN supplies no tennis odds.
- **NBA is priced about a day ahead** (9 of 52). That is how the books post NBA lines, not a fault.
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
- **Open review item: raw quotes in a public file.** `data/sbi.sqlite` is committed to this public
  repository and contains raw Odds API quotes (7,171 rows at the baseline). This audit does **not**
  conclude that publishing that copy is permitted. It has not been confirmed with the provider, and the
  same question applies to the football-data.co.uk and ESPN quotes in the file. It needs a decision.
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
| football-data.co.uk lower divisions | `football-data.co.uk/fixtures.csv` | 200, updated 2026-11-13 14:16 GMT; 51 fixtures in E2, E3, EC, SC1–SC3, SP2 | Free, no key | **Monitoring only, local opt-in (issue #18).** Not in the public database. Same file already fetched. Each division needs its own backtest before any pick; see [Soccer league expansion](#soccer-league-expansion-2026-11-13) |
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

1. **NFL practice and injury reports from nflverse** (free, no key): **done as an opt-in adapter in
   issue #17** (see the nflverse injury reports section above). Stored as context only. Any model use
   needs a walk-forward test first.
2. **Lower divisions from football-data.co.uk** (free, already downloaded): **done as monitoring only,
   local opt-in** (issue #18). E2, E3, EC, SP2 and SC1–SC3 are not in the public database; nothing is
   priced or published from them. See [Soccer league expansion](#soccer-league-expansion-2026-11-13).
3. **Operator verification:** confirm owner and pricing platform for the 15 bookmakers of unknown
   ownership, with a dated source for each, and re-check the existing map. Until then the lower bound is
   the figure to rely on. Note that the pick rule in `sbi/ev.py` still counts an unmapped bookmaker as
   its own operator; changing that is a rule change and is left for a separate, reviewed PR.
4. **The Odds API visibility:** record which mapped competitions the API lists as active but the budget
   skipped, so gaps like AFCON qualifying can be explained rather than guessed.
5. **Housekeeping:** events stuck in `scheduled` after kick-off; the leftover `espn:golf` row.

### Decisions only the owner can make

- **A paid odds plan** (The Odds API from $30/month) is the only verified way to add regions and
  refresh more often. **Not authorised** (owner review, 2026-11-13). Nothing paid is enabled and no
  trial is started.
- **Tennis history:** if the owner can confirm the current location and licence of the Sackmann
  archives, an adapter can follow. The licence was non-commercial.
- **Public database (review item):** whether raw third-party quotes may stay in the public
  `data/sbi.sqlite`. Unresolved; not confirmed as permitted.

## Soccer league expansion 2026-11-13

Issue #18 (phase 2 of #15), revised 2026-11-16 after owner review. Seven lower divisions that are
inside a file Doyen already downloads were validated and given a **monitoring-only** tier.

- **They are not in the public database.** `data/sbi.sqlite` is committed to a public repository, and
  permission to republish football-data.co.uk odds has not been verified (next section). The scheduled
  job fetches and stores the ten active leagues only, exactly as before.
- **Opt-in, local only.** `python -m sbi monitor-leagues` fetches the seven leagues into
  `data/local/monitoring.sqlite`, which is gitignored. Only the owner runs it; the workflow never does.
  The command refuses to run if the target is the public database or a path git would track.
- **Never priced.** No monitoring league is analysed, shown on the site or able to produce a pick.
- **What the quotes are.** Every stored quote for these leagues is **file-published and observed**: a
  snapshot stamped with the file's publication time, collected earlier. It is **not bookmaker-timed and
  not an executable price**.

Evidence: `reports/league_validation.md` (walk-forward, per league) and the *Soccer by league* block of
`python -m sbi coverage`, where each row states whether its data is in the public database, in the
local file, or not stored.

### Source-use and redistribution rights: football-data.co.uk

Checked 2026-11-13 on the England data page, `notes.txt`, the disclaimer page and `robots.txt`. No
page was fetched again for the 2026-11-16 revision.

| Question | What the source says | Status |
|---|---|---|
| May the files be downloaded? | "My data is free". `robots.txt` allows `User-agent: *` on every path | **Stated** |
| For what purpose are they offered? | CSV files "to use for quantitative testing of betting systems in spreadsheet applications like Excel" | **Stated** |
| Is there a licence (for example Creative Commons)? | None found on the pages checked | **Not stated** |
| May the files or the odds in them be republished? | Nothing found that grants it | **Not granted** |
| Whose odds are they? | `notes.txt` credits Betbrain.com, Oddsportal.com and individual bookmakers | Third parties may hold rights that football-data.co.uk cannot pass on |
| Automated access | Named AI-training crawlers and scraping tools are disallowed in `robots.txt` (including Anthropic's) | Applies to those agents; the scheduled Python job is not one |

What follows from that, kept as two separate questions:

1. **Using historical files for local research: supported.** Downloading the files and testing models
   on your own machine is the purpose the site states. The league validation in this PR is that use.
   Its outputs (`reports/league_validation.md`, `data/backtest/league_validation.json`) contain
   aggregate statistics such as log loss and counts, and no bookmaker quotes.
2. **Republishing raw bookmaker odds in a public SQLite file: not verified, treated as not permitted.**
   "Free to download and test with" is not permission to redistribute, and the odds come from third
   parties. No statement was found that allows it.

Consequences applied in this PR:
- No new raw odds enter the public database. The seven monitoring leagues are local-only.
- The test fixture keeps the real column layout with **synthetic prices**
  (`tests/fixtures/football_data/README.md`).
- **Unchanged and still open:** the public database already holds football-data.co.uk quotes for the ten
  active leagues, as it did before this PR. This PR adds none and removes none. Whether they may stay is
  the owner's decision recorded under *Decisions only the owner can make*.
- **To resolve it:** ask the site owner in writing (the site lists its contact on the home page) whether
  odds from the files may be stored in a public repository. Until a written yes exists, keep the
  monitoring leagues local, and consider moving the active-league quotes out of the public file too.

### What was verified

| Check | Finding (2026-11-13) |
|---|---|
| Which extra divisions are in `fixtures.csv` | E2, E3, EC, SC1, SC2, SC3, SP2: 51 fixtures in the snapshot published 14:16 GMT. No other division was in that snapshot (international break: none of the ten active leagues either) |
| Other football-data divisions (D2, I2, F2, G1, T1 and the 16 "extra" countries) | Not in the fetched snapshot, so **not added**. The extra-country files carry closing odds only |
| Access | `robots.txt`: `User-agent: *` is allowed everywhere. Named AI-training crawlers and scraping tools are disallowed (GPTBot, ChatGPT-User, Google-Extended, Anthropic-AI, Claude-Web, ClaudeBot, PerplexityBot, Applebot-Extended, CCBot, Meta-ExternalAgent, Diffbot, Omgilibot). Doyen's job is a Python script with its own User-Agent and trains nothing. See *Open points* below |
| Licence | The site says "My data is free" and offers the files "for quantitative testing of betting systems". **No licence or redistribution terms were found** on the data pages, `notes.txt` or the disclaimer. Personal research use is the only use claimed here. The open question about republishing quotes (see the 2026-11-13 audit) is unchanged |
| Identifiers | Division code in `Div`, season from the kick-off date (July to June). Event id `football:{div}:{UK date}:{home}:{away}`, unchanged for existing leagues |
| Shape and history | Ten seasons (2017-18 to 2026-27) for each division: 70 files, 23,978 matches, no unparseable date, no duplicate match, no near-duplicate team spelling. Columns grew from 54–65 to 112–133; 2019-20 and 2020-21 are short seasons (Covid) |
| Kick-off times | `notes.txt` says only "Time of match kick off". Doyen reads it as UK local time for every country; Leganes v Burgos is listed at 19:30, which matches a 20:30 Spanish kick-off. There is no `Time` column before 2019-20, so those matches are stored at 15:00 UK |
| xG | Present in 2026-27 for E2, E3 and SP2 only. **Absent for EC, SC1, SC2 and SC3** and for every earlier season; stored as missing, never filled |
| Bookmakers | Pre-match 1X2: Bet365, Betfred, BetVictor, Bwin, Paddy Power, Sky Bet and Betfair Exchange (plus Max/Avg, which are not bookmakers). O/U 2.5 and Asian handicap: Bet365 and Betfair Exchange only. Pinnacle left the files during 2025-26 |
| Quote time | `notes.txt`: weekend odds are collected on Friday afternoon and midweek odds on Tuesday afternoon. The stored time is the file's publication time, so every quote is older than its timestamp and none is bookmaker-timed |

### Measured before and after

What the opt-in local copy holds, measured once on 2026-11-13 16:55 UTC on a scratch copy by running the
ingest with and without the seven leagues. **The public database gains nothing**: its soccer numbers
stay at the "Before" column. The "After" column is what an owner who opts in sees locally.

| Soccer, next 7 days | Before | After | Change |
|---|---|---|---|
| Scheduled events | 132 | 183 | +51 |
| Events with any quote | 43 | 94 | +51 |
| Observed fresh | 43 | 94 | +51 |
| **Bookmaker-timed fresh** | 26 | 26 | **0** |
| 3+ known operators | 26 | 76 | +50 |
| Sharp reference (Betfair Exchange) | 26 | 75 | +49 |
| Known operators quoting soccer | 7 | 10 | +3 (Bet365, Entain, Flutter) |
| Bookmakers of unknown ownership | 8 | 10 | +2 (Betfred, BetVictor) |
| **Known operators in the whole database** | 10 | 10 | **0** |
| Finished soccer matches stored | 1,114 | 1,968 | +854 |
| Events that can produce a pick | 0 club | 0 club | 0 |

| League | Events | Priced | Markets priced | Usable markets | Known operators | Unknown | Bookmaker-timed | Observed only | Sharp reference | Results stored |
|---|---|---|---|---|---|---|---|---|---|---|
| E2 England League One | 5 | 5 | 15 | 5 | 4 | 2 | 0 | 5 | 5 | 158 |
| E3 England League Two | 10 | 10 | 30 | 10 | 4 | 2 | 0 | 10 | 10 | 164 |
| EC England National League | 11 | 11 | 33 | 11 | 4 | 2 | 0 | 11 | 11 | 189 |
| SC1 Scotland Championship | 4 | 4 | 12 | 4 | 4 | 2 | 0 | 4 | 4 | 69 |
| SC2 Scotland League One | 5 | 5 | 15 | 5 | 4 | 2 | 0 | 5 | 5 | 69 |
| SC3 Scotland League Two | 5 | 5 | 15 | 5 | 4 | 2 | 0 | 5 | 5 | 65 |
| SP2 Spain Segunda Division | 11 | 11 | 31 | 10 | 4 | 2 | 0 | 11 | 9 | 140 |

What this does and does not show:
- **More events, not more independent prices.** The four known operators (Bet365, Entain, Flutter,
  Betfair Exchange) were all in the database already. No new operator was added.
- **Only 1X2 is usable.** A usable market needs fresh quotes for every selection from three known
  operators. 50 of 51 events reach that on 1X2. No O/U or handicap market does: two operators quote them.
- **No quote is bookmaker-timed or executable.** All 51 events are file-published and observed only: a
  snapshot collected the afternoon before publication. That is weaker than The Odds API quotes used for
  internationals.
- **One sharp reference.** With Pinnacle gone, Betfair Exchange is the only one, and lower-division
  exchange markets are thin (2 of 11 SP2 matches had no exchange price).

### Out-of-sample evidence per league

`python -m sbi league-eval`, each league on its own data. Tune 2020-22, validate 2022-24, test 2024-25 to
Nov 2026. Hyperparameters were chosen per league; the setting tuned on the six big leagues was scored
for comparison only.

| League | Test matches | Model log loss | Market log loss | Model − market (95%) | Blend weight | Simulated selections | Return per unit (95%) | Mean CLV (95%) |
|---|---|---|---|---|---|---|---|---|
| E2 | 1,246 | 1.0385 | 1.0183 | +0.011 to +0.030 | 0.06 | 50 | −0.48 to +0.33 | −0.001 to +0.059 |
| E3 | 1,254 | 1.0628 | 1.0465 | +0.007 to +0.027 | 0.05 | 59 | **−0.70 to −0.11** | −0.019 to +0.013 |
| EC | 1,269 | 1.0210 | 1.0021 | +0.010 to +0.028 | 0.22 | 67 | −0.20 to +0.52 | −0.005 to +0.050 |
| SC1 | 422 | 1.0451 | 1.0254 | −0.002 to +0.041 | 0.06 | 29 | −0.53 to +0.43 | −0.051 to +0.056 |
| SC2 | 423 | 1.0576 | 1.0236 | +0.011 to +0.057 | 0.00 | 26 | −0.54 to +0.49 | −0.058 to +0.019 |
| SC3 | 423 | 1.0655 | 1.0529 | −0.008 to +0.034 | 0.12 | 33 | −0.27 to +0.83 | −0.008 to +0.069 |
| SP2 | 1,053 | 1.0457 | 1.0207 | +0.015 to +0.036 | 0.06 | 56 | −0.46 to +0.34 | −0.032 to +0.011 |

- **The market beats the model in every league.** The interval excludes zero in five of seven; in SC1
  and SC3 it includes zero on about 420 matches, which is too few to conclude anything.
- **The deployed rules show no edge anywhere.** Every closing-line-value interval includes zero, and in
  E3 the simulated return was reliably negative.
- **Hyperparameters do not matter much** (test log loss moves by 0.002 to 0.007 across the grid), and the
  big-league setting would have been neither clearly better nor worse. That is a finding about these
  seven leagues, not a licence to reuse it.
- **Verdict: all seven stay monitoring.** Blockers per league are listed in `reports/league_validation.md`.

### What changed in the code

- `sbi/leagues.py`: the allowlist (active and monitoring tiers) and exact, per-division team aliases.
- `sbi/monitoring.py` and `python -m sbi monitor-leagues`: the opt-in local store described above.
- `sbi/pipeline.py`: the scheduled ingest still asks for the ten active leagues only; `analyse` now
  states that rule explicitly and ignores any other division. Pick rules and thresholds are unchanged.
- `sbi/sources/football_data.py`: malformed rows are dropped and counted (bad date, blank or repeated
  team, duplicate match); zero, negative and absurd odds are not prices; an empty file is empty; a
  changed schema raises a clear error that the job records against that provider.
- **Repeat ingestion fix.** Re-reading the same snapshot used to insert every 1X2 price again, because
  SQLite's unique key does not match rows whose `line` is empty. On 2026-11-13 the committed database
  held 57,753 football-data 1X2 rows, of which 2,511 were distinct. New reads no longer add repeats.
  Existing rows are left alone: removing them is a data change for the owner to approve.
- `sbi/coverage.py`: the per-league block, with where each row's data lives, and a per-league comparison
  with the frozen baseline. `data/coverage/baseline_2026-11-13.json` is untouched; measures it did not
  record are shown as `n/r`. A warning appears if a monitoring league is ever found in the public database.

### Open points for the owner

1. **Redistribution permission** (above). It decides whether the monitoring leagues can ever leave the
   local file, and whether the existing active-league quotes should stay public.
2. **robots.txt and AI agents.** The history used for validation (70 season files) was downloaded on
   2026-11-13 from a Claude Code session with the project User-Agent. The file disallows Anthropic's
   crawlers by name. If you read that as covering agent sessions, re-run `python -m sbi league-eval` from
   your own machine and keep agent sessions off that site. No request was made to the site on 2026-11-16.
3. **Promotion.** Nothing here supports promoting a league. A future case needs bookmaker-timed quotes
   from at least three known operators and a closing-line-value interval above zero on more selections.
4. **Old duplicate rows** can be removed in a separate, reviewed change if you want a smaller database.
5. **O/U and handicap freshness.** For those markets an unchanged price in a newer snapshot keeps its
   old timestamp (the unique key does apply there), so it can look stale when it is not. Existing
   behaviour, not changed here because it affects which quotes the pick rules accept.
