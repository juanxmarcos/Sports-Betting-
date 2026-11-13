# Sports Betting Doyen — Recommended Parlays of the Day (staged; nothing published yet)

**Status: stage 0.** The homepage has a "Recommended Parlays of the Day" section, and it says
**"No verified parlays today"**. Doyen publishes no parlays, because two things a trustworthy
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

1. **Legs:** 2 or 3. Each is already a published straight pick, status `active`, starting today
   (local calendar day), with a quote inside the freshness limit in `sbi/odds_policy.py`.
   No leg is added, and no threshold is lowered, to make a parlay possible.
2. **No known link between legs:** different games, no shared team or player, different
   competitions. Same-game parlays are excluded outright. Passing this screen means "no known
   link", which is weaker than proof of independence.
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
| 1 | **Shadow ledger.** Store every combination that passes the leg screens in an append-only table, unpublished, at the product of one bookmaker's leg prices. Settle them. Measure hit rate against the multiplied probabilities. | Owner approval; enough straight picks to produce combinations | Proposed |
| 2 | **Combined-price source.** A zero-cost, permitted way to confirm a bookmaker's quote for the combination. | A data source. None of the current free feeds has one; scraping bet slips is not acceptable | Blocked |
| 3 | **Publication.** Cards, expanded details and immutable snapshots, only for combinations that meet every rule in §3. | Stages 1 and 2, with evidence reviewed by the owner | Not started |

Stage 2 may never be possible at zero cost. If so, the alternative is an owner decision to show
combinations as **"illustrative, not a bookmaker quote"** once stage 1 has evidence. That is a
product decision, not something this code should assume.

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
