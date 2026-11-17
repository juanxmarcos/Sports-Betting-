# Sports Betting Doyen — Data source register

> **Latest audit: 2026-11-13** (issue #15, phase 1). The measured baseline, the provider checks and the
> prioritised next steps are in [Source audit 2026-11-13](#source-audit-2026-11-13) at the end of this
> file. The numbers come from `python -m sbi coverage` (`reports/source_coverage.md`).

> **Tennis history** (issue #45): Jeff Sackmann's ATP/WTA archives from an unofficial mirror, research only.
> See [Tennis history](#tennis-history-sackmann-archive-from-an-unofficial-mirror-issue-45-owner-decision-on-39).

> **Third-party forecast sites** (The Open Model, Football Analytics, Skorbot) were audited on
> 2026-11-16 (issue #23). None is ingested. See [FORECAST_SOURCES.md](FORECAST_SOURCES.md).

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

1. **NFL practice and injury reports from nflverse** (free, no key): **done as an opt-in adapter in
   issue #17** (see the nflverse injury reports section above). Stored as context only. Any model use
   needs a walk-forward test first.
2. **Lower divisions from football-data.co.uk** (free, already downloaded): ingest fixtures and odds
   for E2, E3, EC, SP2 and SC1–SC3; publish nothing until each division passes its own backtest.
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

## Tennis history: Sackmann archive from an unofficial mirror (issue #45, owner decision on #39)

> **Label: unofficial mirror; original repositories withdrawn by the author (404 since about 2026-11-02); integrity not verified against the original.**

- **What:** Jeff Sackmann's tour-level singles match results (`atp_matches_YYYY.csv`, `wta_matches_YYYY.csv`), seasons 2010–2026.
  The mirror's last match is in the week of 2026-05-25.
- **Originals (withdrawn):** `github.com/JeffSackmann/tennis_atp` and `github.com/JeffSackmann/tennis_wta`, both 404 since about
  2026-11-02 (see #39). The author has not named a new location.
- **Mirror used:** Hugging Face dataset [`Aneeshers/tennis-sackmann-archive`](https://huggingface.co/datasets/Aneeshers/tennis-sackmann-archive), labelled `cc-by-nc-sa-4.0`,
  pinned to revision `8ac86f7c62889b5d5c4cfec4c6403edcb8c5d993` (dataset last modified 2026-06-25). Files downloaded 2026-11-17T15:23:23+00:00 from
  `https://huggingface.co/datasets/Aneeshers/tennis-sackmann-archive/resolve/<revision>/<path>`. The mirror's own README says it
  redistributes Sackmann's data unchanged and keeps his original READMEs as `UPSTREAM_README.md`. The mirror's author is not
  connected to Sackmann, and nothing shows that Sackmann endorses the mirror.
- **Licence and attribution:** CC BY-NC-SA 4.0 (https://creativecommons.org/licenses/by-nc-sa/4.0/). Data compiled by
  **Jeff Sackmann / Tennis Abstract**. Doyen is non-commercial (owner decision on #15). Doyen's derived files from this data
  (`data/tennis_sackmann/*.csv`, `coverage.json`) carry the same licence and attribution.
- **What is and is not verified:** the bytes Doyen uses are pinned. Every file must match the SHA-256 below, and
  `python -m sbi tennis-history --download` refuses any file that does not. That proves the files are the ones recorded here.
  It does **not** prove they match Sackmann's originals, which can no longer be checked.
- **Where the files live:** raw CSVs are **not committed**. They are downloaded on request into `data/local/tennis_sackmann/`,
  which git ignores. Committed: `data/tennis_sackmann/manifest.json` (provenance and checksums), `player_map.csv`
  (Sackmann player ID ↔ ESPN name), `tournament_map.csv`, `match_links.csv` (Sackmann match ID ↔ ESPN match ID) and
  `coverage.json`. The report is `reports/tennis_history.md`.
- **Sanity check against Doyen's ESPN results (2024-01-01 to 2026-05-25):** 12,035 matches linked
  (85.1% of mirror matches). Winners disagree on 10
  (0.083%), below the 1% stop threshold. They are listed in the report and were not corrected.
- **Use:** research only. The walk-forward (log loss 0.63461 → 0.63261 on
  11,637 matches) gives a small gain over the live model. But only 7 finished tennis events have stored multi-bookmaker odds,
  so no gain against the market can be shown, and **the live tennis model is unchanged**.

| File | Bytes | SHA-256 |
|---|---|---|
| `LICENSE` | 913 | `d128251e9a3725f694c97a6761df96610481f92a6a69ab936174acb0c4be0589` |
| `README.md` | 2,035 | `56179e411714701330792fed236094cc7634c2e77c37ef0e2a799082b46b23ac` |
| `atp/UPSTREAM_README.md` | 4,673 | `80fd5a50ba020fd306890d31142187bb737627ba468d3e36faabe92d48ab5083` |
| `atp/atp_matches_2010.csv` | 614,299 | `135a4a1e2ab69c33318b6e5ad59efc67cc5358629b15bf28fb2f905d48f7aeb0` |
| `atp/atp_matches_2011.csv` | 611,939 | `8e91e4b680f0b4e9605a3c71b4c676b55e2a102de8544a7d3b2fbaca5977575a` |
| `atp/atp_matches_2012.csv` | 610,116 | `03f03612691af370c9c47939dde4202d9858e05ea044367388115e627d4d13f3` |
| `atp/atp_matches_2013.csv` | 596,714 | `9e1e3b124ac22c1b840118f78475a910cb2ea68684289581f70b54a022f2832c` |
| `atp/atp_matches_2014.csv` | 589,216 | `7c102ee3b0da1fee59edc6a5f280eb0784ac0bad69988583f65791dcb7084177` |
| `atp/atp_matches_2015.csv` | 594,438 | `20c1f723df86b367f3ec205bbda3d8a7163fa6d4e46dcfda15095e24965bc5ed` |
| `atp/atp_matches_2016.csv` | 617,660 | `86dda3871cb79d3226a047774c8fc97b86267cfe96709dea832a347dfbf81684` |
| `atp/atp_matches_2017.csv` | 611,380 | `4bb295788c37487b120cd39171d413cef0ebc6f4c2d9fa40b7261f5143f3719f` |
| `atp/atp_matches_2018.csv` | 608,903 | `0363dc6012190f337fcf34b4ca443634f192c4670cc6c14c94342a54b9adf7eb` |
| `atp/atp_matches_2019.csv` | 586,071 | `7f1a21451ff622bb0c6a09690898db46d51e59dcdf08086d369753822e1d5478` |
| `atp/atp_matches_2020.csv` | 307,277 | `985a917b72d5efb7dd5ef9df8ecc58c637ed6b88561ccad364653af71ac12da0` |
| `atp/atp_matches_2021.csv` | 573,056 | `b9b1d31a4b0b9273b8f338cbb1347c5a847ad2361334ec760a286f5990fba347` |
| `atp/atp_matches_2022.csv` | 608,789 | `7190042565ab8400e74f44fda60700acb36ddf3c82d393f331a07589e05b5f52` |
| `atp/atp_matches_2023.csv` | 625,341 | `9b9671aa7c8156e74c2e4466675b7ed4e762bb8a58b7237a30daefd84ffceff5` |
| `atp/atp_matches_2024.csv` | 650,136 | `73aec32247a0db68d8aa8fd8003eefea132905177f1cb145502d9215b53311be` |
| `atp/atp_matches_2025.csv` | 617,154 | `78c356ef9328b89ae58a17564d61c02cdad2a3a007f6b8af5cfc17992b11bb2d` |
| `atp/atp_matches_2026.csv` | 300,795 | `ceb157ae698f79f4148f7bb6253bbcf6a8c8eb9ff94670dd83aa0428802cfd59` |
| `atp/matches_data_dictionary.txt` | 3,758 | `b4b525ad8163f9ee2ffde3ab7108924ec1385ef7d2fddf828c1fc096fcaafee4` |
| `wta/UPSTREAM_README.md` | 3,607 | `f34402380f3c84f7c7d9f6156225603ef917bb2b2d6d18676a234fb5323b13c9` |
| `wta/wta_matches_2010.csv` | 572,925 | `05b980e28398ae13e6e0edae544a060b59571cf977623ad0db727d6de3527627` |
| `wta/wta_matches_2011.csv` | 575,703 | `ea0afb5d5e5a1fd230860f722de4f79578f7bd39949358a8b66480f2cae6e101` |
| `wta/wta_matches_2012.csv` | 584,181 | `a8e7f92534df31293a5574db3406e6a0d1c2d956ba63610c44c7bb6f3f09f52d` |
| `wta/wta_matches_2013.csv` | 559,834 | `0d31dde39e721a683b158c30ffbe612293b06bd2386dfeec47ae28e9bad8d93c` |
| `wta/wta_matches_2014.csv` | 574,337 | `4cb59debfa4cbf079c550ee7dfc0ee098237af33376701cd340e112b917f8176` |
| `wta/wta_matches_2015.csv` | 550,360 | `9332d0d470c378c8d439553ed7d81379eb3596d04babf39bee7021edae316130` |
| `wta/wta_matches_2016.csv` | 602,004 | `17145270279d6bf5d1abec4038d51d6af3aa71a7b40421b9f175205fafa075f7` |
| `wta/wta_matches_2017.csv` | 593,130 | `eae2de68b2e87fcac7e2ff1f6168c78d1baba91fb0ffecda455aa329a81437c8` |
| `wta/wta_matches_2018.csv` | 572,565 | `6ccfc04baabe536e4260083c2e299c8c36668a8e8276dfc309219df23bf9ea38` |
| `wta/wta_matches_2019.csv` | 567,137 | `da251744c6ece2cab4b94df659ee38a81bb4aa50cf532d48f1a6eb0cc66726d4` |
| `wta/wta_matches_2020.csv` | 266,525 | `bcbb285ee8a743ce117952bbb99cfe816bfc685412aa3adc7a9913e7799cd70c` |
| `wta/wta_matches_2021.csv` | 531,828 | `3f4b865fe9f68aedb3d51597740cf658cf805f676bae652f2bc93cbab4f6e99f` |
| `wta/wta_matches_2022.csv` | 530,984 | `f638cf65efefb01a1a10368c1d5217d5f90981fb76193ca3a9c3773c2abc2ba7` |
| `wta/wta_matches_2023.csv` | 569,610 | `b73bf74928155b858cdb7045f6334246336cef604286cb361e695df26911ad18` |
| `wta/wta_matches_2024.csv` | 542,425 | `d9bba2a0b3793f63c737ef62a809b82b56b3ad0ee94e1f95e78cecfac7615ed2` |
| `wta/wta_matches_2025.csv` | 565,244 | `e4eb002bc6d828b0bd21e04ed286e68722ddc8ccbbb27ea980bf62e938377f96` |
| `wta/wta_matches_2026.csv` | 255,577 | `8fea203e3f4e731308b9ed2845059818d400aa6176c801279b24e846569e9d97` |
