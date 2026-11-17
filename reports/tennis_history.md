# Tennis history from the Sackmann mirror (issue #45)

Generated 2026-11-17T15:29:48+00:00 by `python -m sbi tennis-history`. Research only: the database and the live tennis model are not changed.

## Provenance

- **Label: unofficial mirror; original repositories withdrawn by the author (404 since about 2026-11-02); integrity not verified against the original.**
- Mirror: https://huggingface.co/datasets/Aneeshers/tennis-sackmann-archive (revision `8ac86f7c62889b5d5c4cfec4c6403edcb8c5d993`), downloaded 2026-11-17T15:23:23+00:00.
- Licence: CC BY-NC-SA 4.0. Tennis match data compiled by Jeff Sackmann / Tennis Abstract (originally github.com/JeffSackmann/tennis_atp and tennis_wta), licensed CC BY-NC-SA 4.0 (https://creativecommons.org/licenses/by-nc-sa/4.0/). Read from an unofficial mirror; original repositories withdrawn by the author (404 since about 2026-11-02); integrity not verified against the original.
- Checksums (SHA-256, per file, in `data/tennis_sackmann/manifest.json`): verified (39 files).

## Coverage

- Mirror: 34 files, 90,888 tour-level singles matches, 2010-01-03 to 2026-05-25 (rows dropped as unreadable: 0).
- Players: 3,525 in the mirror; 1,103 matched to an ESPN name used by Doyen (exact: 1060, initial+surname: 43); 2,422 unmatched, of whom 313 played a mirror match since 2024 (the rest last appear earlier). Ambiguous names are left unmatched, never guessed.
- ESPN players seen since 2024: 1,102 of 1,916 have a mirror ID. ESPN also carries Challenger and WTA 125 events, which the tour-level mirror files do not.
- Players in Doyen's stored tennis events (by Doyen's ESPN tour label) with a mirror ID: ATP 28 of 29, WTA 45 of 51.

| Season | ATP matches | WTA matches |
|---|---|---|
| 2010 | 3,030 | 2,781 |
| 2011 | 3,015 | 2,804 |
| 2012 | 3,094 | 2,940 |
| 2013 | 2,944 | 2,714 |
| 2014 | 2,816 | 2,694 |
| 2015 | 2,943 | 2,651 |
| 2016 | 2,941 | 2,923 |
| 2017 | 2,911 | 2,862 |
| 2018 | 2,982 | 2,847 |
| 2019 | 2,721 | 2,652 |
| 2020 | 1,462 | 1,276 |
| 2021 | 2,733 | 2,597 |
| 2022 | 2,917 | 2,594 |
| 2023 | 2,986 | 2,810 |
| 2024 | 3,158 | 2,792 |
| 2025 | 2,862 | 2,692 |
| 2026 | 1,449 | 1,295 |

## Sanity check against Doyen's ESPN results

Mirror tournaments starting 2024-01-01 to 2026-05-25 (the mirror's last week), against ESPN matches up to 2026-06-08.

- Mirror matches in the window (walkovers excluded): 14,149; ESPN completed matches: 23,852.
- Linked (same two players, ESPN date within the tournament window, same tournament as the rest of that tournament's links): **12,035**, i.e. 85.1% of mirror matches and 50.5% of ESPN matches (ESPN includes lower-tier events the mirror files omit).
- 3 candidate pairings were dropped because the ESPN match belonged to a different tournament from the rest of that mirror tournament's links (the same two players met in two nearby events).
- Winner disagreements: **10** (0.083% of linked; stop threshold 1%). Listed below. Which source is right was not checked, and neither was corrected.

**Found in Doyen's own data (not changed here):** 5,950 completed ESPN matches labelled `atp` are between two WTA players (women's draws at combined events such as the Slams, Indian Wells, Miami and Madrid). 2,523 of them are Grand Slam matches, which the live model converts to best of five sets although women play best of three. This affects the live model, so it needs its own issue.

| Date | Tour | Mirror tournament | Mirror winner | ESPN winner | Retired |
|---|---|---|---|---|---|
| 2024-06-23 | ATP | Eastbourne | Aleksandar Vukic | Yoshihito Nishioka | no |
| 2024-09-28 | ATP | Davis Cup Finals RR: CZE vs ESP | Roberto Bautista Agut | Jiri Lehecka | no |
| 2024-09-26 | ATP | Davis Cup Finals RR: AUS vs CZE | Alexei Popyrin | Tomas Machac | yes |
| 2024-09-24 | WTA | Beijing | Kamilla Rakhimova | Kimberly Birrell | no |
| 2024-10-20 | WTA | Tokyo | Kyoka Okamura | Hailey Baptiste | no |
| 2025-01-08 | ATP | Next Gen Finals | Alex Michelsen | Nishesh Basavareddy | no |
| 2025-02-23 | ATP | Dubai | Luca Nardi | Marton Fucsovics | no |
| 2025-09-24 | ATP | Beijing | Arthur Rinderknech | David Goffin | no |
| 2025-11-02 | ATP | Metz | Vitaliy Sachko | Clement Tabur | no |
| 2026-05-17 | ATP | Hamburg | Aleksandar Kovacevic | Arthur Gea | no |

## Walk-forward evaluation

A = live model (surface Elo, w_surface 0.15, K scale 0.6) on 29,088 ESPN matches from 2024. B = the same, warm-started with 76,174 mirror matches before 2024-01-01. Both predict each ESPN match from 2025-07-01 before seeing its result. Negative B − A is better for B.

| Test set | n | Log loss A | Log loss B | B − A (95%) | Brier A | Brier B | B − A (95%) |
|---|---|---|---|---|---|---|---|
| Main: both players 10+ matches in A | 11,637 | 0.63461 | 0.63261 | -0.00376 to -0.00033 | 0.22277 | 0.22169 | -0.00179 to -0.00031 |
| All test matches | 14,531 | 0.63771 | 0.63288 | -0.00648 to -0.00310 | 0.22413 | 0.22176 | -0.00314 to -0.00157 |
| Thin history in A | 2,894 | 0.65014 | 0.63394 | -0.02108 to -0.01149 | 0.22962 | 0.22205 | -0.00983 to -0.00535 |
| Thin in A, 10+ in B | 336 | 0.61473 | 0.62515 | -0.01479 to +0.03615 | 0.21257 | 0.21706 | -0.00646 to +0.01629 |
| Main, ATP | 7,318 | 0.62670 | 0.62657 | -0.00248 to +0.00229 | 0.21945 | 0.21917 | -0.00132 to +0.00075 |
| Main, WTA | 4,319 | 0.64803 | 0.64285 | -0.00746 to -0.00284 | 0.22839 | 0.22597 | -0.00349 to -0.00139 |

### Against the market

7 finished tennis events have stored match-winner odds from 3+ bookmakers before the start (median 18 bookmakers). The mirror has no odds, and Doyen has no older tennis odds.

| | Log loss | Brier |
|---|---|---|
| De-vigged median market | 0.49960 | 0.16319 |
| A (live model) | 0.52690 | 0.17359 |
| B (with mirror) | 0.53522 | 0.17773 |

With 7 events this says nothing reliable either way.

## Decision

Pre-registered rule: adopt B only if its log-loss gain over A has a 95% interval below zero on the main set **and** at least 200 priced events show B no worse than the market.

- Gain over the live model: **yes**.
- Market criterion met: **no**.
- **Live model changed: no, the mirror data stays research-only.**
  - only 7 finished events have stored multi-bookmaker tennis odds (criterion: 200), so no gain against the market can be shown.
