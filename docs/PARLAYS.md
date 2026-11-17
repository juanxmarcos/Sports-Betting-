# Sports Betting Doyen — Recommended Parlays of the Day (gated; nothing published yet)

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
  `decimal_odds > 1` and a timezone-aware `quoted_at` no more than 30 minutes old.
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
   review), and `quoted_at` is timezone-aware and at most 30 minutes old. Records in
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

- The scheduled job runs every 2 hours; a combined quote counts for 30 minutes. These are
  consistent only because the job does not invent combined quotes: an owner-recorded quote is used
  if a site build happens within 30 minutes of `quoted_at`. `parlay-quote` rebuilds `docs/data`
  immediately so the owner can commit it; the browser hides the card once the quote is 30 minutes
  old. A quote is never re-stamped or relabelled as fresh.
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

**Still open (PR B and later):** walk-forward validation of multi-leg candidates (log loss, Brier,
calibration, confidence intervals by sport, market, league and leg count) from permitted historical
data. A source for real single-bookmaker combined quotes (see section 7 and `reports/parlay_research.md`).
Aligning a free-quota The Odds API refresh with evening start times without exceeding the budget.
