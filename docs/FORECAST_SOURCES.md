# Third-party soccer forecasts: source audit and shadow benchmark

> **Audit date: 2026-11-16** (issue #23, phase 1). Measured numbers come from
> `python -m sbi forecast-bench` and are in [`reports/forecast_benchmark.md`](../reports/forecast_benchmark.md).
> The per-fixture table is `data/forecast_bench/shadow_benchmark.csv`.

**Status: research only.** No third-party forecast feeds Doyen's probabilities, selection rules,
public site or picks. These forecasts are other people's models. They are not bookmakers, they are not
counted toward the three-bookmaker gate, and they are never averaged into a "consensus of tipsters".

## Result in short

| Source | Free and reusable? | Pre-kick-off proof | Can it be ingested live today? | Measured against the market |
|---|---|---|---|---|
| **The Open Model** | Yes, CC BY 4.0 | Yes, public commits before every kick-off | **No. It stopped publishing on 2026-09-09** | 190 fixtures: too few for a verdict; point estimate worse than the market |
| **Football Analytics** | Yes for the settled file, CC BY 4.0 | **No.** Probabilities are published only after the match | **No. Upcoming probabilities are for paying members** | 767 fixtures: worse than the market and worse than Doyen |
| **Skorbot** | **No open licence** | No (history is in the paid tier) | Not without accepting unclear terms | Not measured |

**No source qualifies for live ingestion (phase 2), so no connector was built.** Each reason is a
blocker the publisher controls, not something to work around:

- The only source with provable pre-kick-off forecasts has been silent for ten weeks.
- The only active, licensed source hides its upcoming probabilities behind a subscription and releases
  them after the result is known.
- The third has no licence that allows storing and republishing its numbers.

On the evidence so far none of them adds information beyond the market: the best in-sample weight on
either measured source, when pooled with the pre-match market, is 0.000.

## What was checked, and how

- **Terms and permissions** were read on each publisher's own pages on 2026-11-16 (links below).
- **Requests made from this audit session**, one each, with a descriptive User-Agent and a pause
  between them: `theopenmodel.com` (robots.txt, the data page, `predictions.csv`, the methodology
  page), `footballanalytics.pro` (robots.txt, the data page, terms, methodology), `skorbot.live`
  (robots.txt, the API page, terms, `llms.txt`, `matches.json`, `track-record.csv`). Nothing was
  fetched from behind a login, a key or a block.
- **The forecasts themselves were read from the publishers' public GitHub repositories**, cloned once
  (`Hicruben/theopenmodel` at commit `a4f1239a2bc8`, `serayd61/football-predictions-open-data` at
  commit `f0a8bf60d787`). The benchmark command makes no request to any forecast site.
- **Doyen and the market** come from the football-data.co.uk season files the daily pipeline already
  downloads (48 files for six seasons of eight leagues, cached).

## Comparison matrix

Fixtures are finished 2026-27 matches in Doyen's football-data leagues.

| | The Open Model | Football Analytics | Skorbot |
|---|---|---|---|
| Publisher's data page | [theopenmodel.com/data](https://theopenmodel.com/data/) | [footballanalytics.pro/en/data](https://footballanalytics.pro/en/data) | [skorbot.live/en/api](https://skorbot.live/en/api/) |
| Public repository | [Hicruben/theopenmodel](https://github.com/Hicruben/theopenmodel) | [serayd61/football-predictions-open-data](https://github.com/serayd61/football-predictions-open-data) (the publisher's own mirror) | none |
| Licence | Data CC BY 4.0, code MIT | CC BY 4.0 (data page, repository `LICENSE`, Zenodo DOI 10.5281/zenodo.24216824) | None. Terms: content "belongs to Skorbot"; individual predictions may be quoted with credit |
| Automated access | Stable file URLs promised; robots.txt allows general agents, blocks named AI-training crawlers, and signals `ai-train=no` | Data page: direct links "may be fetched by scripts". **Site terms §6 forbid scraping and bulk download and limit use to personal, non-commercial.** The two statements conflict; the GitHub mirror with its CC BY licence file is the unambiguous route | Free read-only API; "keep request rates reasonable", own User-Agent, credit required. "We may change, limit or stop the API at any time" |
| Rate or cache limits published | None | None (files regenerate hourly) | None stated; responses carry `max-age` of 60 s to 4 h |
| Cost | Free | Settled file free. **Upcoming probabilities: paid membership** | Current window free. **Archive, filters and change feed: Pro, $10/month** |
| Method | ClubElo ratings → expected goals → Dixon-Coles (fixed ρ = −0.13, +65 Elo home advantage) | Dixon-Coles fitted per league on 540 days of results, 180-day half-life, refitted daily | Undisclosed "AI model", revised until about one hour before kick-off |
| Original or syndicated | Own formula on a third-party rating (ClubElo). Anyone using ClubElo will correlate with it | Own results-only model | Unknown |
| Uses bookmaker odds as input | No (stated) | No (stated) | Not stated |
| Leagues overlapping Doyen | 5: E0, SP1, D1, I1, F1 | 8: E0, E1, SP1, D1, I1, F1, N1, P1 (9 other competitions are outside Doyen) | Several, not mapped |
| 1X2 completeness | 201 of 201 rows are valid distributions | 1,547 of 1,547 | not measured |
| Data vintage | Kick-offs 2026-08-16 to 2026-09-16. **Last commit 2026-09-09**; the site file is byte-identical to that commit | Kick-offs 2026-06-07 to 2026-11-14; mirror refreshed 2026-11-15 | Feed generated 2026-11-05, eleven days before the audit; 86 finished predictions since 2026-10-26 |
| Pre-kick-off timestamp | Daily snapshot file per date, each in a public commit. All 201 forecasts were committed before kick-off (median 10.8 hours for the version scored) | **None for probabilities.** A row enters the file after the final whistle. The pre-kick-off ledger added on 2026-11-14 records the pick only (home, draw or away), and held one line | `updated_at` only, and it is overwritten: a finished match showed an update time after its kick-off |
| Revisions | 147 of 201 forecasts changed between daily versions before kick-off (expected: ratings update). No committed snapshot file was ever edited | No row changed or disappeared across 26 committed versions | Earlier versions are not retrievable in the free tier |
| Backfill and survivorship | None found: every league fixture in the source's date range is present (200 of 200) | **634 of 1,547 rows arrived in one bulk commit on 2026-10-17**, up to 19 weeks after their matches. Of the 783 matched rows only 317 became public within 72 hours of kick-off. 94 of 877 Doyen fixtures in its date range (10.7%) are missing. Postponed or abandoned matches are dropped, not marked | Not assessable |
| Team and league mapping | Exact alias table, 12 entries. 200 of 201 matched; 198 with an identical kick-off time | Exact alias table, 67 entries. 783 of 785 in-scope rows matched; 782 with an identical kick-off time; final scores agree on all 783 | not mapped |
| Left unmatched (never guessed) | 1: Levante v Athletic Bilbao, rescheduled (kick-off 36+ hours apart) | 2: one score differs from football-data (Utrecht v Go Ahead Eagles, 2026-09-08), one fixture football-data does not have (Rayo Vallecano v Athletic Club, 2026-10-10) | not applicable |
| Can Doyen settle it | Yes, from football-data results | Yes | not applicable |
| Fixtures scored (source, both markets and Doyen all present) | 190 | 767 (317 published promptly) | 0 |
| Closeness to Doyen | Probability correlation 0.93; correlation of deviations from the market 0.53 | 0.92; 0.60 | not measured |

**Independence.** Both measured sources are Dixon-Coles or Elo models built on past results, the same
family as Doyen's own model. Their probabilities correlate above 0.9 with Doyen's, and their
disagreements with the market point the same way as Doyen's more often than not. They are a second
opinion from a close relative, not independent evidence, and adding them would add little that
Doyen's model does not already contain.

## Backtest summary

Full tables, calibration and intervals are in `reports/forecast_benchmark.md`. Negative differences
favour the first forecast. Intervals are 95%, resampling whole match days. A verdict needs the interval
to exclude zero **and** at least 300 fixtures; that threshold was fixed before any score was computed.

| Source, fixture set | Fixtures | Source log loss | Market (pre-match) | Doyen | Source minus market | Source minus Doyen |
|---|---|---|---|---|---|---|
| The Open Model, verified before kick-off | 190 | 0.9838 | 0.9660 | 0.9675 | +0.0179 (−0.0001 to +0.0428): **inconclusive** | +0.0163 (−0.0041 to +0.0378): **inconclusive** |
| Football Analytics, all matched | 767 | 0.9993 | 0.9664 | 0.9820 | +0.0330 (+0.0192 to +0.0491): **worse** | +0.0173 (+0.0068 to +0.0294): **worse** |
| Football Analytics, published promptly | 317 | 0.9747 | 0.9491 | 0.9672 | +0.0256 (+0.0048 to +0.0501): **worse** | +0.0075 (−0.0056 to +0.0235): **inconclusive** |

What this does and does not show:

- **The Open Model: inconclusive.** 190 fixtures over 25 match days of one early-season month is a
  short, unrepresentative sample. Against the closing market its interval excludes zero
  (+0.0071 to +0.0506), but the sample is below the threshold, so no verdict is given.
- **Football Analytics: worse than the market**, on both the full set and the promptly published
  subset. The full-set result rests on rows whose pre-kick-off timing cannot be verified; if anything
  that bias would flatter the source, and it still loses.
- **Doyen's own model is also worse than the pre-match market** on the larger set
  (+0.0157, +0.0060 to +0.0254). That matches the existing backtest and is why Doyen's blend weight on
  its model is zero.
- Calibration is acceptable for every forecast (expected calibration error between 0.007 and 0.040);
  the losses come from sharpness, not from systematic bias.

### Limits of the comparison

- **Doyen's side is a reconstruction.** It is the walk-forward model with the live settings (weekly
  refit on earlier matches only). On 2026-11-16 the database held no stored live prediction for a
  finished club match, so a comparison of archived live predictions is not possible yet.
- **Timing is not matched to the hour.** The pre-match odds were collected one to three days before
  kick-off, Doyen refits weekly, Football Analytics refits daily, and The Open Model's scored version
  is a median of 10.8 hours old. The external sources generally see fresher results than Doyen's
  reconstruction does.
- **Commit times are strong but not absolute proof.** A commit's date is written by the machine that
  made it. A publisher who rewrote history could forge it. Only a record Doyen keeps itself, by
  fetching before each kick-off, would be independent. That is what a phase-2 connector would add.
- **Promoted clubs are missing from the scored set**: Doyen prices no match for a team without
  history (10 Open Model and 16 Football Analytics fixtures).
- Football Analytics' file starts on 2026-06-07 although its own pages say the record starts in July.
  Nothing rests on those rows (they are outside Doyen's leagues), but it is an inconsistency.

## Recommendation

1. **Do not ingest any of the three for live use.** None offers free, licensed, pre-kick-off
   probabilities today.
2. **Keep the benchmark as a repeatable check.** If The Open Model resumes, a new clone and one
   command extend its verified sample; about 110 more fixtures would reach the 300 threshold.
3. **A phase-2 connector becomes worthwhile only if** a source publishes probabilities before
   kick-off, free, under an open licence, and does so for long enough to measure. The Open Model's
   repository is the right shape (one dated file per day in a public repository, fetched with a
   single `git fetch`), so the reader in `sbi/forecast_bench.py` is already most of that connector.
   Stored rows would belong in a separate shadow table, apart from ESPN's `external_forecasts`.
4. **Mixing any external forecast into Doyen's probabilities stays out of scope.** It would need a
   preregistered walk-forward study and a model version change, approved separately.
5. **Do not pay for Skorbot Pro or a Football Analytics membership** to obtain the missing data. No
   spending is authorised, and the measured evidence gives no reason to.

## Questions for the owner

- **robots.txt and agent sessions.** `theopenmodel.com` and `football-data.co.uk` allow general
  agents but disallow named AI-training crawlers, Anthropic's among them. This audit made four
  requests to the first and downloaded 48 season files from the second from a Claude Code session,
  identified by its own User-Agent, for research and not for training. If you read those directives as
  covering agent sessions, rerun `python -m sbi forecast-bench` from your machine or from Actions. The
  same question is open on PR #22.
- **Redistribution.** `data/forecast_bench/shadow_benchmark.csv` republishes the two CC BY 4.0
  datasets' probabilities for matched fixtures, with attribution, in this public repository. The
  licence permits it. It also contains de-vigged market probabilities derived from football-data
  odds, whose redistribution terms are still unconfirmed (the open item from PR #16). Say so if you
  would rather keep the per-fixture file out of the repository.

## Running it

```bash
git clone https://github.com/Hicruben/theopenmodel /path/openmodel
git clone https://github.com/serayd61/football-predictions-open-data /path/football-analytics
python -m sbi forecast-bench --openmodel-repo /path/openmodel --football-analytics-repo /path/football-analytics
```

Use full clones: a shallow clone hides early commits and makes forecasts look younger than they are.
The command never opens the database and writes only `reports/forecast_benchmark.md` and
`data/forecast_bench/`. Either repository may be left out.

## Attribution

- Data: The Open Model (theopenmodel.com), CC BY 4.0.
- Data: Football Analytics open data (footballanalytics.pro/data), CC BY 4.0. Football Analytics
  (2026). Settled model predictions dataset: pre-match 1X2 probabilities and results, 17 leagues.
- Team ratings behind The Open Model: ClubElo (clubelo.com). Odds and results: football-data.co.uk.
