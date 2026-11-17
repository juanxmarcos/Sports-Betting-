# Tennis tour labels (issue #49)

Generated 2026-11-17T16:51:07+00:00 by `python -m sbi tennis-tour-audit`. Read-only.

**Rule.** The tour of each match is read from the ESPN draw it belongs to: the grouping slug mens-singles/womens-singles, else the competition type slug, else the grouping or competition name (Men's/Women's), else the scoreboard endpoint (feed_fallback). Before this fix the tour came from the scoreboard endpoint, and ESPN's `atp` scoreboard (read first) also carries the women's draws at combined events.

## Matches whose label changed

- Completed ESPN singles matches since 2024: 29,090; label changed: **6,730** (atp->wta: 6,730).
- Of these, Grand Slam matches: **2,864**, all now best of three (2,864 women's Slam matches no longer get the best-of-five conversion).
- Rule used per completed match: grouping_slug 29,090.
- Not yet completed matches in the fetched window: 79; label changed: 0.

## Stored database rows

- Stored tennis events: 140; with a league different from the corrected tour: **0** (16 could not be checked because their ESPN match is outside the fetched data).
- Published picks on a mislabelled event: **0**.
- From now on `tennis.register` keeps an already stored row's ID (its odds stay linked) and corrects its league, unless a published pick references it, in which case the row is left exactly as it was.

## Walk-forward, live model

Same Elo and the same test matches from 2025-07-01; only the tour label differs. Negative after − before is better after the fix.

| Test set | n | Log loss before | after | after − before (95%) | Brier before | after | after − before (95%) |
|---|---|---|---|---|---|---|---|
| Main (both players 10+ matches) | 11,639 | 0.63460 | 0.63507 | +0.00047 (+0.00004 to +0.00088) | 0.22276 | 0.22288 | +0.00012 (-0.00003 to +0.00027) |
| Main, WTA (corrected label) | 7,112 | 0.63368 | 0.63444 | +0.00077 (+0.00006 to +0.00148) | 0.22224 | 0.22243 | +0.00020 (-0.00006 to +0.00044) |
| Main, label changed | 2,791 | 0.61152 | 0.61347 | +0.00196 (+0.00010 to +0.00369) | 0.21274 | 0.21324 | +0.00051 (-0.00017 to +0.00117) |
| Main, label changed, Grand Slam | 1,189 | 0.59304 | 0.59764 | +0.00459 (+0.00030 to +0.00859) | 0.20525 | 0.20644 | +0.00119 (-0.00038 to +0.00271) |
| All test matches | 14,533 | 0.63770 | 0.63818 | +0.00049 (+0.00012 to +0.00084) | 0.22413 | 0.22426 | +0.00013 (+0.00001 to +0.00025) |

## Walk-forward, live model warm-started with the #46 mirror

Same Elo and the same test matches from 2025-07-01; only the tour label differs. Negative after − before is better after the fix.

| Test set | n | Log loss before | after | after − before (95%) | Brier before | after | after − before (95%) |
|---|---|---|---|---|---|---|---|
| Main (both players 10+ matches) | 11,975 | 0.63239 | 0.63283 | +0.00043 (-0.00005 to +0.00088) | 0.22156 | 0.22168 | +0.00012 (-0.00003 to +0.00028) |
| Main, WTA (corrected label) | 7,338 | 0.62962 | 0.63033 | +0.00071 (-0.00003 to +0.00142) | 0.22027 | 0.22048 | +0.00020 (-0.00006 to +0.00045) |
| Main, label changed | 2,842 | 0.60751 | 0.60933 | +0.00183 (-0.00010 to +0.00365) | 0.21084 | 0.21136 | +0.00052 (-0.00014 to +0.00121) |
| Main, label changed, Grand Slam | 1,210 | 0.58457 | 0.58887 | +0.00429 (-0.00040 to +0.00864) | 0.20117 | 0.20239 | +0.00122 (-0.00026 to +0.00281) |
| All test matches | 14,533 | 0.63287 | 0.63328 | +0.00041 (+0.00002 to +0.00078) | 0.22176 | 0.22188 | +0.00012 (-0.00002 to +0.00025) |

Elo ratings are keyed by player, not by tour, so the label never changed whose rating a match updated; the difference above comes only from dropping the best-of-five conversion on women's Grand Slam matches. A positive difference means the wrong conversion happened to help: it sharpens probabilities, and the Elo is under-confident on these matches. That is a calibration question for a separate, measured change; it is not a reason to keep applying best-of-five maths to best-of-three matches.
