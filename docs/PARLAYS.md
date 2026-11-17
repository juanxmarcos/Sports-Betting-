# Sports Betting Doyen — Recommended Parlays of the Day (strict path gated; labelled estimates shown)

**Update, issue #47 (2026-11-17): estimated mode.** The owner approved showing up to five clearly
labelled *estimated* parlays a day alongside the strict path below, which is unchanged. See
[section 11](#11-estimated-parlays-of-the-day-issue-47). When neither a verified nor an estimated
parlay qualifies, the homepage says so in one line.

**Status: stage 1 (issue #33).** The backend can now publish a real parlay, but only when every
gate in section 7 passes for that exact combination. Today two gates are closed (no free source of
combined bookmaker prices; joint-calibration evidence too small), so the homepage still says
"No verified parlays today". Sections 1–6 are the stage-0 record (#7, #27) and still apply.

**Stage 0 record.** Since issue #27 the homepage *is* "Recommended Parlays of the Day" (single picks
moved to `#/picks`), and it says **"No verified parlays today."** Doyen publishes no parlays, because two things a trustworthy
parlay needs do not exist yet. This document records the audit behind that, the rules a parlay
would have to meet, and the plan for getting there.

## 1. Feasibility audit (2026-11-13)

| Question | Finding |
|---|---|
| Is there a bookmaker-quoted parlay price? | **No.** The Odds API (free tier), ESPN and football-data.co.uk return single-market prices per event. None returns a price for a combination, or says whether a bookmaker accepts one. |
| Can one bookmaker be shown to price every leg? | **Partly.** Each pick stores every bookmaker's quote for its market (`evidence_json.all_prices`), so a bookmaker common to all legs can be found. Only the pick's own best price has a timestamp in the export; per-bookmaker timestamps are in the `odds` table. |
| Is the leg identity reliable? | **Yes.** Each pick has a stable `rec_id` and `event_id`, teams, market, selection and line. |
| Is there a joint-probability model? | **No.** Doyen has one probability per selection. Nothing models how outcomes in different games move together. |
| Are the leg probabilities proven live? | **Not yet.** The live record has 3 published picks and 0 settled. Backtests support the price-versus-sharp-consensus method for single club-soccer bets, not for combinations. |
| Is there a multi-leg track record? | **No.** No parlay has been paper-traded, so no joint calibration can be measured. |
| How often would legs even exist? | **Rarely.** On the audit date there were 2 active picks, on different days, in the same competition, with best prices at two different bookmakers. |

One structural point matters more than the rest. A Doyen pick is a pick **at one bookmaker's
price**: the edge is that this quote is longer than the sharp, margin-free consensus. A parlay
is one bet slip at one bookmaker. The other legs would be taken at that bookmaker's price, which
is usually not the best one and usually below fair value. So a parlay built from good straight
picks is often a worse bet than the picks themselves.

## 2. The arithmetic (`sbi/parlays.py`, unit-tested)

For legs that are **independent** and priced at **one** bookmaker:

- Combined decimal odds = product of the leg odds.
- `P(all legs win)` = product of the leg probabilities.
- `EV per unit = P(all legs win) × parlay odds − 1`.

Leg EVs are never multiplied or added. Two legs at +10% and +8% give a parlay EV of +18.8%
(`1.10 × 1.08 − 1`), not 0.8% and not 18%. Two negative-EV legs always give a negative-EV parlay.

The independence assumption is the weak point. If the legs are positively related, the true
joint probability differs from the product, and the bookmaker either refuses the combination or
prices it below the product. The same goes for error: if each leg's probability is 3% too high,
a three-leg joint probability is about 9% too high.

## 3. What a published parlay would have to satisfy

1. **Legs:** 2 to 6 (issue #27; was 2 or 3). Each is already a published straight pick, status `active`, starting today
   (local calendar day), with a quote inside the freshness limit in `sbi/odds_policy.py`.
   No leg is added, and no threshold is lowered, to make a parlay possible.
2. **No known link between legs:** different games, no shared team or player, different
   competitions. Same-game parlays are excluded outright. This is a temporary safety filter.
   Passing it means "no known link", not that the legs are independent: outcomes in different
   competitions can still be related, and the screen is no evidence that they are not.
3. **One bookmaker:** the same bookmaker (not just the same owner group) quotes every leg's exact
   selection. Legs priced at different bookmakers are never combined.
4. **A real combined price:** that bookmaker's own quote for the combination. *Not available.*
5. **A supported joint probability:** calibration evidence for multiplied leg probabilities, or a
   joint model. *Not available.*
6. **Positive value at the combined price**, using 4 and 5. High combined odds alone are never a reason.
7. **Volume:** at most 1–2 per day. Zero is the normal result.

Rules 1–3 and the value check at the product of one bookmaker's leg prices are implemented as
screens. Each run counts what was checked and why it was excluded, and writes that to the
`parlays` block of `docs/data/doyen.json`:

```json
{"date": "2026-11-13", "status": "not_published", "headline": "No verified parlays today",
 "recommendations": [],
 "blockers": [{"key": "combined_quote", "text": "…"}, {"key": "joint_calibration", "text": "…"}],
 "audit": {"straight_picks_seen": 2, "usable_legs_today": 0, "combinations_checked": 0,
           "passed_leg_screens": 0, "excluded": {"leg: not scheduled today": 1}}}
```

`recommendations` is always empty in stage 0, even when a combination passes every screen. The
block carries counts only: no legs, bookmakers, odds or probabilities. The front end has no
parlay card renderer, so nothing in the data file can make a recommendation appear.

## 4. Staged plan

| Stage | What | Needs | Status |
|---|---|---|---|
| 0 | Honest empty state, audit counts, tested arithmetic and leg screens, this document | — | **Done** (issue #7) |
| 1 | **Shadow ledger.** Store every combination that passes the leg screens in an append-only table, unpublished, at the product of one bookmaker's leg prices. Settle them. Measure hit rate against the multiplied probabilities. | First, a written evaluation plan (how calibration will be estimated, the sample size needed, what result would count as support); owner approval; no added cost | Proposed, not started |
| 2 | **Combined-price source.** A zero-cost, permitted way to confirm a bookmaker's quote for the combination. | A data source. None of the current free feeds has one; scraping bet slips is not acceptable | Blocked |
| 3 | **Publication.** Cards, expanded details and immutable snapshots, only for combinations that meet every rule in §3. | Stages 1 and 2, with evidence reviewed by the owner | Not started |

Stage 2 may never be possible at zero cost. **Owner decision (PR #14 review, 2026-11-13):**
Doyen does not publish illustrative parlays as recommendations, and never presents a computed
product of leg prices as an executable bookmaker quote. A product-of-legs price may be used
only inside an unpublished shadow ledger, labelled as computed.

## 5. Snapshot design for stage 3 (not built)

Published parlays would follow the same rules as straight picks: never edited, never deleted.

- `parlays`: `parlay_id`, `published_at`, `date`, `bookmaker`, `parlay_odds`, `parlay_odds_retrieved_at`,
  `parlay_odds_source`, `joint_prob`, `joint_method`, `ev`, `method_version`, `is_paper`.
- `parlay_legs`: `parlay_id`, `rec_id`, `event_id`, `market`, `selection`, `line`, `leg_odds`,
  `leg_odds_retrieved_at`, `leg_prob`, `kickoff_utc`.
- `parlay_updates` (append-only): `parlay_id`, `checked_at`, `status` (`active`, `leg_stale`,
  `leg_withdrawn`, `withdrawn`, `settled`), `note`.

A parlay with a withdrawn or stale leg is marked, not rewritten or replaced. The same set of
legs is never published twice on one day.

## 6. Risk wording

Parlays are higher-variance and win less often than single picks. Every leg has to win, the
bookmaker's margin is paid on every leg, and a small error in each probability compounds. Any
parlay Doyen ever shows would be paper-traded research, never a guarantee and never a reason
to stake more.


## 5. Homepage card contract (issue #27)

The homepage shows at most 5 parlay cards for the current **America/New_York** day. A card is
rendered only when **all** of the following hold. The rules live in `sbi/parlays.py`
(`card_problem`, `shown_cards`) and are applied again in the browser (`parlayProblem` in
`docs/assets/doyen.js`); `tests/test_parlay_cards.py` checks that both sides agree case by case.

- The `parlays` block has `status: "published"`, `blockers: []` and today's date. In stage 0 the
  block always has blockers, so the homepage shows the one-line empty state.
- Each recommendation: `parlay_id`, `date` (today), `status: "active"`, `bookmaker`, 2–6 `legs`.
- Each leg: unique `event_id`, `title`, `selection`, sport in Soccer/NFL/NBA/Tennis,
  `status: "active"`, a timezone-aware `start_utc` on today's date that has not started yet.
- `quote`: `kind: "bookmaker_combined"` (one bookmaker's own price for the whole combination, never a
  product of best prices from different books), the same `bookmaker`, a non-empty `source`,
  `decimal_odds > 1` and a timezone-aware `quoted_at` no more than 150 minutes old (one site refresh plus
  build time; section 7.4, changed from 30 minutes in issue #37).
- Anything missing, unknown, or flagged `mock`/`test` is rejected. Mock fixtures render only in tests
  that set `window.__DOYEN_ALLOW_MOCK`, and each such card is labelled "Mock data · testing only".

Each card shows the legs (game, market, selection, start time), the bookmaker, the combined odds,
a **$10 illustrative bet amount** (editable; nothing is placed or paid) and the **potential payout =
stake × combined decimal odds, including the stake**, rounded to the cent. It is not expected value
and not a probability; net profit, if ever shown, is stake × (odds − 1) and labelled separately.

The homepage loads only `docs/data/parlays.json` (about 1 KB, written by `site.build` with the
same block as `doyen.json`); other routes load the full research file on demand.


## 7. Stage 1: gates, fallback path and freshness (issue #33)

Run `python -m sbi parlay-research` for the current numbers (writes `reports/parlay_research.md`
and `data/analysis/parlay_calibration.json`; read-only, no network).

### 7.1 Combined-price sources (pages read 2026-11-16)

| Source | Combined price? | Cost / status |
|---|---|---|
| The Odds API (in use) | No. Single-market endpoints only; no parlay or bet-builder endpoint | free plan in use |
| ESPN, football-data.co.uk (in use) | No | free |
| OpticOdds Parlay API (`POST /parlay/odds`) | Yes, across sportsbooks | licence via sales; no public price or free tier found. **Not enabled** |
| OddsBlaze same-game-parlay endpoint | Yes, per sportsbook (US books) | from $299/month per a third-party review, "no free tier". **Not enabled** |
| SportsGameOdds | No (client multiplies leg odds) | n/a |
| A bookmaker's own bet slip | Yes | free, **manual owner entry only**; never scraped |

No legally usable, no-cost source qualifies. The paid options are listed for the owner's
information; enabling one needs the owner's separate approval and is not done here.

### 7.2 Gates (all must pass, per combination)

1. **Leg screens** (unchanged, section 3): 2–6 active published picks starting later today, fresh
   prices, different events, competitions and teams, one bookmaker prices every leg, positive value.
2. **Verified combined quote** (`sbi/parlay_quotes.py`): the owner records the price shown on that
   bookmaker's bet slip with
   `python -m sbi parlay-quote --bookmaker Unibet --odds 5.10 --legs <id>,<id> --source "Unibet bet slip"`
   (`--dry-run` verifies without recording; pick ids are listed in `reports/parlay_research.md`).
   It is accepted only if every leg is a current usable pick, the bookmaker quotes every leg in
   Doyen's stored prices, the combined odds are within 0.85–1.02 × the product of that bookmaker's
   leg prices (outside that band: wrong legs, a boost or correlation pricing, so it is rejected for
   review), and `quoted_at` is timezone-aware and at most 150 minutes old (section 7.4). Records in
   `data/parlay_quotes.json` are append-only.
3. **Joint calibration** (`sbi/parlay_calibration.py`, criteria fixed in code before any result):
   at least 200 disjoint settled two-leg combinations, observed joint wins within the 95% band of the
   multiplied probabilities (|z| ≤ 1.96), legs calibrated too, and the evidence must cover each leg's
   competition and the number of legs. **Current evidence:** walk-forward test-season selections
   (`data/backtest/bets_test.csv`) give 66 combinations, 6 joint wins against 6.52 predicted
   (z = −0.22, phi = −0.04): consistent with independence, far too few, six club leagues only,
   two legs only. Live picks so far are all UEFA Nations League, which it does not cover.
4. **Positive value at the quoted price**, and the card contract (section 5 of #27).
5. **Exposure:** a straight pick appears in at most one published parlay (best value first); at most 5.

When a gate is closed, `blockers` names it and `audit.excluded` counts where each combination stopped.

### 7.3 Shadow ledger

Every combination that passes the leg screens is appended by the scheduled run to
`ledger/parlay_shadow.csv` (first sighting per day, legs and bookmaker; never edited), with the
product of that bookmaker's leg prices labelled `computed_product_not_a_quote`. It is not shown on
the site. Its settled rows are the live record that can, over time, add to the calibration evidence.

**Evaluation plan.** Shadow and backtest combinations are scored with the same test as gate 3. The
gate opens only when the pre-registered criteria pass on settled combinations that cover the leagues
and leg counts being published. Changing a criterion needs new out-of-sample evidence and owner review.

### 7.4 Freshness

- **Rule (issue #37):** a combined quote counts for `MAX_QUOTE_AGE_MINUTES = 150` minutes after
  `quoted_at`: one site refresh (`SITE_REFRESH_MINUTES = 120`, the `15 */2 * * *` cron in `daily.yml`)
  plus a 30-minute allowance for the job's runtime and the Pages deploy. The browser uses the same value
  (`PC.maxQuoteMin` in `docs/assets/doyen.js`). `tests/test_parlay_freshness.py` fails if the cron, the
  Python constant and the browser constant drift apart.
- **Why it changed.** With 30 minutes the site, which only changes when a build is committed, hid a
  verified quote for about 90 of every 120 minutes (noted on #27). With 150 minutes, a quote recorded
  just after a build is still inside the limit when the next scheduled build re-verifies it.
- **What did not change.** Every build re-runs `quote_problem`: the legs must still be current published
  picks that have not started, and the combined odds must still sit inside 0.85–1.02 × that bookmaker's
  stored leg prices. The card shows the time the slip was read ("quoted 14:05"), so a 2-hour-old price is
  never presented as live. A quote is never re-stamped or relabelled as fresh; after 150 minutes it stops
  counting and the browser hides the card.
- **Trade-off.** Bet-slip prices can move within 150 minutes. Shortening the limit again would need a more
  frequent zero-cost refresh, which the current schedule and Odds API budget do not allow.
- Leg prices keep their source-specific limits in `sbi/odds_policy.py` (up to 6 hours near the start
  for The Odds API). They are used only to check the quote's consistency, never displayed as the
  combined price.

### 7.5 Scarcity (measured 2026-11-16)

All 16 published straight picks to date are UEFA Nations League, so the same-competition screen
leaves zero eligible pairs every day (the report also shows the counterfactual if that screen were
relaxed: 15 pairs on 2026-11-16). The 3–5 daily target is structurally out of reach until picks come
from several competitions on the same day. Options needing an owner decision, not enabled here:
relax the same-competition screen for international fixtures (needs its own evidence); a paid
combined-price source (7.1); recording slip prices manually each day.

## 8. Full-slate candidate engine, shadow only (issue #35, PR A)

`sbi/parlay_engine.py` (`python -m sbi parlay-candidates`, and the `parlay-candidates` job in the
daily run) widens the leg pool from published straight picks to **every scheduled, same-day
(America/New_York) event** in Soccer, NFL, NBA and Tennis. It reads only stored events, stored
predictions and fresh stored quotes. It makes no network request and spends no API credit.

**Leg screens** (research screens, not betting thresholds; no straight-pick rule changes):

| Screen | Rule |
|---|---|
| Market | Result market only: 1X2 (soccer), moneyline (NFL, NBA, tennis). Totals and handicaps are out until their calibration is measured |
| Freshness | Same source- and time-specific limits as straight picks (`odds_policy`) |
| Independent bookmakers | At least `RULES.min_bookmakers` (3) owner groups. Same-owner brands count once |
| Consensus probability | 0.30 to 0.85: no long shots and no blind heavy favourites |
| Model check | If Doyen stored a model probability in the last 36 h, it must be within 0.12 of the market consensus. Tennis stores none, so no check applies |
| Availability | No open `injury` or `lineup` research note on the event |
| Value at the slip | Each bookmaker B is valued against a leave-one-out consensus that excludes B and its owner group. A leg joins a combination at B only if B's price is at or above that fair value. Exchanges count toward consensus but are never parlay bookmakers |

**Combinations.** One selection per event (the one with the best value), at most 30 legs, then a beam
search for each bookmaker: 2 to 6 legs, top 150 per size, at most 250,000 evaluations. The stage-1
link screens apply unchanged: no same game, no shared team or player, and no two legs from one
competition. Different names are not taken as proof of independence. The shortlist holds at most 5
combinations. Each event appears in at most one, and an identical leg set is kept only at its best
bookmaker. **0 is a normal result.**

**Output, developer-only.** `reports/parlay_candidates.md` and `data/analysis/parlay_candidates.json`
show coverage by sport, combinations evaluated and kept by leg count, quota use read from the job log,
the shortlist and a plain "why not 3–5 today" list. The baseline column is the stage-1 straight-pick
view. The daily run appends the shortlist to `ledger/parlay_candidates_shadow.csv`. That file is
append-only, and it is settled read-only from final scores (a void leg makes the row void).

**Never published by this engine.** Every price is `computed_product_not_a_quote`. Each shortlisted
row lists its production blockers: no verified bookmaker combined quote, and joint calibration not
met. The homepage still comes only from `sbi.parlays.build` and its stage-1 gates (section 7).

**First real-data reading (2026-11-16).** At 14:00 UTC: 15 events today, 8 with candidate legs,
4 legs at or above fair value at some bookmaker, 1 combination evaluated, 0 kept. At 22:04 UTC:
12 events and 0 legs, because 10 events had too few fresh independent bookmakers. The Odds API quotes
from the 09:51 run were more than 6 hours old for games within 10 hours, so only one ESPN price was
left. The binding constraints are therefore (a) the timing of the multi-bookmaker refresh relative
to evening games, (b) the one-leg-per-competition screen on an NBA-heavy slate and (c) no bookmaker
offering value on two unlinked legs at once. Thresholds were not relaxed to change this.

**Still open (PR B and later):** walk-forward validation of multi-leg candidates (now section 9; log loss, Brier,
calibration, confidence intervals by sport, market, league and leg count) from permitted historical
data. A source for real single-bookmaker combined quotes (see section 7 and `reports/parlay_research.md`).
Aligning a free-quota The Odds API refresh with evening start times without exceeding the budget.

## 9. Walk-forward validation of joint probabilities, shadow only (issue #38, PR B of #35)

`sbi/parlay_walkforward.py` (`python -m sbi parlay-walkforward`; read-only on the database, no network,
no API credit) writes `reports/parlay_walkforward.md` and `data/analysis/parlay_walkforward.json`.

**Point-in-time replay.** For every recorded run of the daily job (`job_runs`, job `publish`) the database
is rebuilt in memory as it was at that moment: only events later that New York day, only `pre` quotes
retrieved by then, only predictions and research notes created by then, scores removed. The live engine
(`parlay_engine.build_pool`, `search`, `shortlist`) runs on that snapshot unchanged. Legs are then settled
from final scores; void and postponed legs are not scored.

**Samples.** Each event's first sighting as a screened leg; disjoint 2–6-leg combinations of those legs per
day that pass the live link screens; the engine's shortlisted candidates (first sighting, event-disjoint
per day); and, separately, the straight-pick backtest selections (`data/backtest/bets_test.csv`, club soccer).

**Scoring.** Log loss, Brier score (bootstrap 95% intervals), reliability by probability bucket with Wilson
intervals, and observed versus expected joint wins (z) for each leg count. Predictors: the independence
product of de-vigged market probabilities; the product of stored model probabilities where every leg has
one; for shortlisted candidates, the product of the slip bookmaker's implied probabilities. Correlation
risk: residual covariance of same-day leg pairs, split by same competition and different competition.

**Pre-registered criteria** (`CRITERIA`, fixed before the first scoring run): per leg count at least 200
disjoint settled combinations and |z| ≤ 1.96; at least 500 settled legs with |z| ≤ 1.96; at least 200
different-competition pairs whose residual-covariance interval includes 0. A leg count counts as
"calibrated" only if all of these hold. Changing them needs new out-of-sample evidence and owner review.

**First reading (replay of 34 recorded runs, 2026-11-12 to 2026-11-17 04:32 UTC).** Verdict: **not fit to
back a recommendation**. 71 settled legs (wins 45 against 42.1 expected, z +0.74); disjoint replay
combinations: 30 two-leg, 11 three-leg, 3 four-leg, none with 5 or 6 legs. Nothing contradicts the
independence product so far (2 legs: 14 joint wins against 10.6 expected, z +1.35), but every leg count is
far below 200 combinations. At the observed rate that is roughly a month of data for 2 legs, about three
months for 3 legs and close to a year for 4 legs. The backtest sample adds 66/23/5 club-soccer combinations
and does not cover NBA, NFL, tennis or international soccer.

**Correlation.** 201 same-competition and 406 different-competition same-day pairs show no detectable
dependence, but they come from 5 days and share legs. That neither justifies nor refutes the
same-competition exclusion, so it stays.

**The 0-candidate day (2026-11-16).** At 09:51 UTC, 21 of 42 events failed the bookmaker screen and none of
those 21 had 3 independent bookmakers at any age (coverage). The 3 pool legs were all NBA, so the
same-competition screen left nothing. At 21:40 UTC all 13 events failed on prices; 9 of them had 3+
bookmakers whose quotes were too old (timing). Labelled counterfactuals (never used live) give at most 1
shortlisted candidate per run that day even with all quotes treated as fresh *and* the same-competition
screen removed. Across the 5 replayed days the best single run gave 0–1 live candidates, and at most 2
with both counterfactuals. **The 3–5 daily target is not attainable on current data without lowering
thresholds**, and thresholds were not lowered.

**Ledger.** `--record` appends replayed shortlist rows to `ledger/parlay_walkforward_shadow.csv`
(append-only, `origin=walk_forward_replay`, historical decision time, `computed_product_not_a_quote`). It is
kept separate from the live `ledger/parlay_candidates_shadow.csv` so replayed rows are never mistaken for
live sightings. No homepage, pick, price or threshold changes.

## 10. Combined-quote source audit (issue #37, PR B of #27)

**Verdict: not feasible at zero cost today.** No legally usable, no-cost provider returns a
bookmaker's own combined price for a multi-leg slip on Soccer, NFL, NBA or Tennis that Doyen may
show on a public site. No adapter was built, because building one would mean inventing quotes or
relabelling products of leg prices. The owner bet-slip path (section 7.2) remains the only
compliant source of a real combined quote.

Pages were read on 2026-11-17 with an automated fetch tool, one request per page. Nothing behind
a login, paywall, 401/403/429 or anti-bot check was attempted. Quoted terms are short fragments,
not a legal review.

### 9.1 Candidates

| Source (official page) | Own combined price for 2–6 legs? | Free? | Same book / freshness / coverage | Terms for public display | Verdict |
|---|---|---|---|---|---|
| The Odds API, in use ([v4 guide](https://the-odds-api.com/liveapi/guides/v4/), [terms](https://the-odds-api.com/terms-and-conditions.html)) | **No.** The 11 documented endpoints are single-market odds, events, scores, markets and participants. The guide never mentions parlays, accumulators or bet builders. `includeLinks` returns "bookmaker links to events, markets, and betslips if available": a deep link, not a combined price | $0 Starter, 500 credits/month; key needed (already configured) | Per-book single-market prices; refreshed every 2 h within budget; all four sports | Store and display allowed; no standalone redistribution | **Not a source.** `includeLinks` could make owner entry faster (follow-up, not built) |
| ESPN scoreboard (in use) | No. Single-market DraftKings lines per game | Free, keyless | One book | Unofficial endpoint; no licence | Not a source |
| football-data.co.uk (in use) | No. Per-match 1X2/OU/AH snapshots | Free | Files, not live | Research use; no republication licence (#18, #22) | Not a source |
| Sources assessed in #15, #16, #24, #25 (Betting Data API, Polymarket, Kalshi, Betfair Exchange, Pinnacle, Smarkets, football-data.org, BALLDONTLIE, SportsDataIO, API-Football and others; see `docs/DATA_SOURCES.md`) | No. None documents a multi-leg price. Exchanges and prediction markets do not offer parlays as one priced contract | Mixed; the free ones are single-market | n/a | Several restrict automated collection (Polymarket §4.2) | Not a source |
| TheRundown ([pricing](https://therundown.io/pricing)) | Not on the pricing page for any plan, including Free | Free: BetMGM, DraftKings, FanDuel; 5-minute delay; pre-match full-game markets; 200,000 data points/month | 3 US books, US sports focus | Free is "for internal or personal use"; commercial display starts at Pro; stored data must be deleted on cancel | **Blocked:** no documented combined price, and the free tier forbids public display |
| ParlayAPI ([parlay-api.com](https://parlay-api.com/), via [sportsapis.dev review](https://sportsapis.dev/apis/parlayapi)) | **No:** "No SGP pricing or correlation data" | $0, 1,000 credits/month | Single-leg markets | Not checked (no combined price) | Not a source |
| OddsPapi ([blog post](https://oddspapi.io/blog/?p=3131)) | **No:** the client multiplies leg odds ("Combining a parlay is just multiplying the decimal odds") | Free key, limits not stated | Single-leg | Not checked | Not a source (a product of legs is not a quote) |
| SportsGameOdds ([parlay builder page](https://sportsgameodds.com/use-cases/parlay-builder-api)) | No: client-side product of leg odds (also in section 7.1) | n/a | n/a | n/a | Not a source |
| OddsBlaze BlazeBuilder ([docs](https://oddsblaze-docs.pages.dev/endpoints/same_game_parlay)) | Yes, per sportsbook, but **same-game parlays only** (Doyen excludes same-game combinations) | No free tier found; API key "Get access at oddsblaze.com"; from $299/month per a third-party review (section 7.1) | US books | Not checked | **Paid; owner approval needed; wrong product (same-game)** |
| OpticOdds Parlay API ([`POST /parlay/odds`](https://developer.opticodds.com/reference/post_parlay-odds)) | Yes, keyed by sportsbook; can also return a price "computed by applying OpticOdds correlation strengths", which would not be the book's own quote | No free tier found; licence via account manager | Many books | Licence terms not public | **Paid; owner approval needed** |
| A bookmaker's own bet slip, read by the owner | Yes | Free | Exactly one book, real time | Owner's own observation | **Only compliant zero-cost path** (section 7.2) |

### 9.2 Shortest compliant path

1. **Now, zero cost:** the owner reads a slip and runs `python -m sbi parlay-quote ...` (section 7.2).
   With the 150-minute rule a recorded quote survives until the next scheduled build.
2. **Optional follow-up, zero cost:** request `includeLinks=true` on the existing Odds API call so
   the research report can list a deep link to each leg's market. The guide says links are returned
   "if available", and their availability and credit cost on the free plan were not measured. This
   saves the owner time; it is still not a combined quote.
3. **Owner decision, not activated:** a paid combined-price licence (OpticOdds, or OddsBlaze for
   same-game only). Either would need its terms checked for public display and Doyen's
   no-same-game rule reconsidered or kept. Nothing was signed up for, trialled or enabled.

### 9.3 How many combinations a day could yield (point-in-time replay)

The shadow engine (section 8) was replayed every 2 hours from 2026-11-12 10:30 to 2026-11-17 04:30
UTC (58 snapshots) on a scratch copy of `data/sbi.sqlite`. At each time, quotes, predictions and
research notes stored later were removed and finished events were treated as scheduled, so nothing
later leaked in. No thresholds were changed and no network request was made.

| New York day | Events today (max) | Events with a candidate leg (max) | Legs at or above fair value (max) | Combinations kept (max) |
|---|---|---|---|---|
| 2026-11-12 | 40 | 4 | 2 | 1 (2 legs) |
| 2026-11-13 | 54 | 15 | 4 | 0 |
| 2026-11-14 | 25 | 9 | 2 | 0 |
| 2026-11-15 | 37 | 27 | 4 | 0 |
| 2026-11-16 | 42 | 15 | 3 | 1 (2 legs) |

- 3 of 58 snapshots had any combination; never more than 1 per day, never more than 2 legs.
  **Against the 3–5 daily target the result is 0–1, even before the combined-quote gate.**
- Event exclusions summed over all snapshots: no fresh result-market price 671, too few
  independent bookmakers 263, probability outside the research band 61, model–market disagreement
  7, open injury/lineup note 12. Legs with no bookmaker at or above fair value: 218.
- **The scarcity is structural.** The free Odds API budget refreshes multi-book prices about once
  every few hours, so most evening games have no fresh multi-book price. The one-leg-per-competition
  screen is binding on slates dominated by one league. Few bookmakers offer value on two unrelated
  legs at the same time.
- Limits of the replay: the odds table keeps the first time each distinct price was seen, as the live
  run does. Five days in the international break are not a typical season. The replay counts shadow
  candidates only and says nothing about whether any would have won.

### 9.4 Options that need owner approval (none activated)

- A paid combined-price licence (9.2 step 3).
- A paid Odds API plan for more frequent refreshes (from $30/month, `docs/DATA_SOURCES.md`). This
  would ease the freshness exclusions but still give no combined quote.
- Relaxing the one-leg-per-competition screen. This is a research-screen change that needs its own
  evidence, and it is not a betting threshold.

## 11. Estimated parlays of the day (issue #47)

**Owner decision (2026-11-17).** Doyen is a small personal, non-commercial, paper-trading project.
The owner wants parlays on the homepage now, will not pay for data, and approved an estimated mode
alongside the strict path (sections 7–10), which keeps its gates. Code: `sbi/parlay_estimated.py`;
browser mirror: `estProblem` in `docs/assets/doyen.js`; tests: `tests/test_parlay_estimated.py`.

### 11.1 What is shown
- Up to **5** cards under "Estimated parlays of the day", earliest kickoff first. Fewer, or none, is
  normal: legs and cards are never forced.
- Each card: 2–6 legs (game, selection, start time), one bookmaker, **estimated odds**, an editable
  $10 stake, gross payout = stake × estimated odds (to the cent), an **Estimate** badge, and the line
  *"Estimated price: product of [bookmaker]'s single-game odds, not a bet-slip quote. Your slip may
  pay less."* It may also show "Estimated hit chance N% (model estimate, unvalidated)".
- A strict card (owner-recorded verified combined quote, section 7) is shown first with a
  **Verified bookmaker quote** badge, and no estimate reuses any of its games.
- Empty state (one line): *"No parlays today: no verified quotes, and no games later today meet the
  estimate rules."*
- The footer shows *"Estimated parlays record: W–L, paper P/L"*, linking to `#/parlays`, where the
  rules below are summarised.

### 11.2 Rules
| Rule | Implementation |
|---|---|
| Sports | Soccer, NFL, NBA, Tennis only (result market: 1X2 / moneyline). |
| Games | Start later today (New York date) and have not started; status `scheduled`. |
| One bookmaker | Every leg priced by that bookmaker; exchanges excluded (no accumulator slip). |
| Fresh prices | Issue #51: that bookmaker's **latest stored price retrieved on the same New York day and before the game starts** (replaces the 150-minute limit). Checked when built and again in the browser; a leg drops out as soon as its game starts. The card shows "Prices read at HH:MM". |
| Estimated price | Product of that bookmaker's own single-leg prices. Data kind `estimated_product`; the `bookmaker_combined` kind stays reserved for real quotes. |
| Bookmakers per game | Issue #51: **1** is enough, the one pricing the parlay. |
| Leg probability | Doyen's stored model probability (Soccer, NFL, NBA). Where Doyen stores none (Tennis): the de-vigged consensus of the *other* bookmakers when it exists, otherwise (#51) the de-vigged consensus of at least **2** independent bookmakers including the pricing one. A leg with neither is skipped. |
| Parlay value | Issue #51 removed the per-leg rule (probability × price > 1 at every leg). The **whole parlay** must have positive estimated value: joint probability × estimated odds > 1. A parlay starts from a positive-value pair and no further leg may lower its value (probability × price ≥ 1), so at most one leg sits below Doyen's probability, and only if it forms a positive pair with the parlay's strongest leg. Legs are never forced. |
| Leg screens | Estimated-mode screen `parlay_estimated.screen_event` (the shadow engine's `parlay_engine.screen_event` is unchanged): market consensus probability 0.30–0.85 (one bookmaker de-vigged when it is the only one), model within 0.12 of the market (data sanity), no open injury/lineup note. |
| Combinations | At most one leg per game. Same-game combinations and legs sharing a team or player are out. Different games in one competition are **allowed** in this mode. |
| Ranking | Score = estimated joint probability × estimated value, where joint = product of leg probabilities (independence assumed) and value = joint × estimated odds − 1. Ties go to fewer legs. Each game appears in at most one card. |

No single-pick threshold is read or changed. The run makes no network request and spends no API
credit: it reads prices the 2-hourly `daily.yml` job already stored, and writes
`docs/data/parlays.json` (block `estimated_parlays`) and `docs/data/doyen.json`.

### 11.3 Tracking
- Every estimate shown by the scheduled run is appended to `ledger/estimated_parlays.csv` with its
  first-shown legs, bookmaker, prices, estimated odds, estimated hit chance and $10 stake. Rows are
  never edited or removed; if the same parlay is shown later at a different price, the first one counts.
- Settlement is computed read-only from final scores on every run: any lost leg loses the parlay;
  otherwise a void or postponed leg voids it (stake returned, P/L 0; bookmaker void-leg rules differ
  and are not modelled); otherwise it stays open. Paper P/L uses the $10 stake and the estimated
  price, so a real slip may have paid less.
- The record (with expected wins among settled rows) is the input #41's calibration work can use.

### 11.4 Limits
- **Not a quote.** A bookmaker may price a combination below the product of its single prices, or
  refuse it.
- **Unvalidated joint probability.** Multiplying leg probabilities assumes independence and
  calibrated legs; same-competition legs can be correlated. Nothing here has passed the
  joint-calibration criteria of section 7.
- **Cards change during the day** as prices move; a card is hidden in the browser once any leg has
  started or a price is not from today (New York). Since #51 a price can be several hours old;
  the card shows when the prices were read.
- **Weaker evidence per leg since #51.** One bookmaker can price a leg, and a tennis leg's
  probability can come from a consensus that includes the pricing bookmaker itself, which pulls
  its estimated value towards zero. The parlay-level value check is the only value gate.
- **Thin coverage.** Many games lack prices from today on the free Odds API quota, so several
  days may show few or no cards. Since #51 the 2-hourly ingest buys competitions with a game later
  today (New York) first, inside the unchanged per-day budget and quota safeguards (#25); its run
  output reports `planned_today_first` and `today` (events in the responses / events priced). The
  block's `coverage` reports `events_today`, `events_with_fresh_prices` and `legs`.

