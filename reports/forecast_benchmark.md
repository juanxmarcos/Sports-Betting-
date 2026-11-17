# Third-party soccer forecasts: shadow benchmark

Generated 2026-11-16T14:35:07+00:00 by `python -m sbi forecast-bench`. Research only: nothing in this file feeds the model, the selection rules, the public site or any pick. The audit of each source's terms and method is in `docs/FORECAST_SOURCES.md`.

External forecasts belong to their publishers and are shown with attribution. They are not Doyen's, they are not bookmakers, and they are not counted or voted as if they were.

## How to read it

- **Fixtures** are finished 2026-27 matches in Doyen's football-data leagues. A source row is matched only through exact league and team alias tables, with kick-offs within 36 hours and the same final score.
- **Market** is the de-vigged consensus of the football-data odds: pre-match (collected one to three days before) and closing.
- **Doyen** is a walk-forward reconstruction with the live settings (weekly refit on earlier matches only). It is not a record of live predictions: the database holds none for a finished club match yet.
- **Verdict**: better or worse only when the 95% interval excludes zero and there are at least 300 fixtures. Intervals resample whole match days.
- **Timing is not equal.** The sources, the market snapshots and Doyen's weekly refit see information of different ages. The closing market is the latest of all.

## The Open Model

- Source: https://theopenmodel.com/data/ (repository: https://github.com/Hicruben/theopenmodel)
- Licence: CC BY 4.0 (data), MIT (code). Attribution: "Data: The Open Model (theopenmodel.com), CC BY 4.0."
- Method: ClubElo ratings -> Dixon-Coles bivariate Poisson
- Repository state read: commit `a4f1239a2bc8` of 2026-09-09T08:22:05+00:00
- Rows: 201, kick-offs 2026-08-16 to 2026-09-16
- Pre-kick-off evidence: 201 verified pre kickoff
- Matching: 200 matched, 1 kickoff mismatch
- Matched fixtures Doyen could not price (no team history): 10
- Matched rows whose kick-off time equals football-data's exactly: 198 (largest gap 21.5 hours)
- Rows edited after first publication: 0
- Forecast scored: the last version committed before kick-off, public a median of 10.8 hours before it (range 1.1 to 179.1). 147 rows changed between daily versions.
- In-scope rows left unmatched: la-liga 2026-09-16 Levante v Bilbao: kickoff_mismatch

| League | Matched | Doyen fixtures in the source's date range | Doyen fixtures this season | Scored |
|---|---|---|---|---|
| D1 Germany Bundesliga | 27 | 27 | 81 | 24 |
| E0 England Premier League | 40 | 40 | 100 | 38 |
| F1 France Ligue 1 | 36 | 36 | 90 | 34 |
| I1 Italy Serie A | 40 | 40 | 110 | 40 |
| SP1 Spain La Liga | 57 | 57 | 119 | 54 |

#### Verified before kick-off

Same fixtures as "All matched rows".

#### All matched rows

Every matched row, whatever its evidence.

190 fixtures on 25 match days, 2026-08-15 to 2026-09-16. A verdict needs at least 300 fixtures.

| Forecast | Log loss | Brier |
|---|---|---|
| External source | 0.9838 | 0.5859 |
| Market, pre-match | 0.9660 | 0.5744 |
| Market, closing | 0.9583 | 0.5700 |
| Doyen (DC/Elo ensemble) | 0.9675 | 0.5726 |
| Doyen Dixon-Coles only | 0.9718 | 0.5762 |
| Doyen Elo only | 0.9673 | 0.5720 |
| Uniform one third | 1.0986 | 0.6667 |

| Paired difference (negative = first is better) | Log loss (95%) | Brier (95%) | Verdict |
|---|---|---|---|
| External source minus Market, pre-match | +0.0179 (-0.0001 to +0.0428) | +0.0116 (-0.0011 to +0.0291) | inconclusive |
| External source minus Market, closing | +0.0255 (+0.0071 to +0.0506) | +0.0159 (+0.0024 to +0.0337) | inconclusive |
| External source minus Doyen (DC/Elo ensemble) | +0.0163 (-0.0041 to +0.0378) | +0.0134 (-0.0003 to +0.0267) | inconclusive |
| Doyen (DC/Elo ensemble) minus Market, pre-match | +0.0015 (-0.0202 to +0.0270) | -0.0018 (-0.0162 to +0.0155) | inconclusive |

| Dependency | Value |
|---|---|
| Mean absolute probability gap, source vs Doyen | 0.0348 |
| Mean absolute probability gap, source vs market | 0.0426 |
| Mean absolute probability gap, Doyen vs market | 0.0420 |
| Correlation of probabilities, source vs Doyen | 0.927 |
| Correlation of deviations from the market, source vs Doyen | 0.532 |
| In-sample best weight on the source when pooled with the market | 0.000 |
| In-sample best weight on Doyen when pooled with the market | 0.431 |

| Calibration (all outcomes pooled) | ECE | 0.0-0.2 | 0.2-0.4 | 0.4-0.6 | 0.6-0.8 | 0.8-1.0 |
|---|---|---|---|---|---|---|
| External source: predicted / observed | 0.0198 | 0.13 / 0.11 (n=73) | 0.28 / 0.29 (n=340) | 0.48 / 0.45 (n=116) | 0.67 / 0.80 (n=35) | 0.82 / 0.83 (n=6) |
| Market, pre-match: predicted / observed | 0.0138 | 0.13 / 0.13 (n=106) | 0.29 / 0.29 (n=309) | 0.48 / 0.45 (n=101) | 0.69 / 0.75 (n=44) | 0.85 / 0.90 (n=10) |
| Doyen (DC/Elo ensemble): predicted / observed | 0.0207 | 0.15 / 0.09 (n=76) | 0.28 / 0.27 (n=331) | 0.48 / 0.48 (n=123) | 0.67 / 0.83 (n=36) | 0.85 / 0.75 (n=4) |

#### Published promptly

Same fixtures as "All matched rows".

## Football Analytics

- Source: https://footballanalytics.pro/en/data (repository: https://github.com/serayd61/football-predictions-open-data)
- Licence: CC BY 4.0. Attribution: "Data: Football Analytics open data (footballanalytics.pro/data), CC BY 4.0."
- Method: Dixon-Coles / Poisson attack-defence model, refitted daily (dc-1.0)
- Repository state read: commit `f0a8bf60d787` of 2026-11-15T12:43:50+00:00
- Rows: 1547, kick-offs 2026-06-07 to 2026-11-14
- Pre-kick-off evidence: 1547 claimed pre kickoff
- Matching: 783 matched, 762 league not in doyen, 1 score conflict, 1 no doyen fixture
- Matched fixtures Doyen could not price (no team history): 16
- Matched rows whose kick-off time equals football-data's exactly: 782 (largest gap 24.0 hours)
- Rows edited after first publication: 0
- First public a median of 692 hours AFTER kick-off (range 8 to 3211); 634 rows arrived in the first bulk commit.
- In-scope rows left unmatched: eredivisie 2026-09-08 FC Utrecht v Go Ahead Eagles: score_conflict; la-liga 2026-10-10 Rayo Vallecano v Athletic Club: no_doyen_fixture

| League | Matched | Doyen fixtures in the source's date range | Doyen fixtures this season | Scored |
|---|---|---|---|---|
| D1 Germany Bundesliga | 67 | 81 | 81 | 64 |
| E0 England Premier League | 87 | 100 | 100 | 85 |
| E1 England Championship | 158 | 180 | 180 | 154 |
| F1 France Ligue 1 | 82 | 90 | 90 | 80 |
| I1 Italy Serie A | 98 | 110 | 110 | 98 |
| N1 Netherlands Eredivisie | 90 | 99 | 108 | 90 |
| P1 Portugal Primeira Liga | 93 | 98 | 98 | 91 |
| SP1 Spain La Liga | 108 | 119 | 119 | 105 |

#### Verified before kick-off

Only forecasts in a public commit dated before kick-off. This is the only set free of hindsight risk.

No fixture has a forecast from the source, both markets and Doyen.

#### All matched rows

Every matched row, whatever its evidence.

767 fixtures on 68 match days, 2026-08-07 to 2026-11-08. A verdict needs at least 300 fixtures.

| Forecast | Log loss | Brier |
|---|---|---|
| External source | 0.9993 | 0.5956 |
| Market, pre-match | 0.9664 | 0.5739 |
| Market, closing | 0.9616 | 0.5711 |
| Doyen (DC/Elo ensemble) | 0.9820 | 0.5850 |
| Doyen Dixon-Coles only | 0.9865 | 0.5879 |
| Doyen Elo only | 0.9827 | 0.5853 |
| Uniform one third | 1.0986 | 0.6667 |

| Paired difference (negative = first is better) | Log loss (95%) | Brier (95%) | Verdict |
|---|---|---|---|
| External source minus Market, pre-match | +0.0330 (+0.0192 to +0.0491) | +0.0217 (+0.0127 to +0.0324) | worse |
| External source minus Market, closing | +0.0377 (+0.0231 to +0.0541) | +0.0246 (+0.0148 to +0.0357) | worse |
| External source minus Doyen (DC/Elo ensemble) | +0.0173 (+0.0068 to +0.0294) | +0.0106 (+0.0038 to +0.0186) | worse |
| Doyen (DC/Elo ensemble) minus Market, pre-match | +0.0157 (+0.0060 to +0.0254) | +0.0111 (+0.0046 to +0.0176) | worse |

| Dependency | Value |
|---|---|
| Mean absolute probability gap, source vs Doyen | 0.0386 |
| Mean absolute probability gap, source vs market | 0.0513 |
| Mean absolute probability gap, Doyen vs market | 0.0418 |
| Correlation of probabilities, source vs Doyen | 0.921 |
| Correlation of deviations from the market, source vs Doyen | 0.598 |
| In-sample best weight on the source when pooled with the market | 0.000 |
| In-sample best weight on Doyen when pooled with the market | 0.000 |

| Calibration (all outcomes pooled) | ECE | 0.0-0.2 | 0.2-0.4 | 0.4-0.6 | 0.6-0.8 | 0.8-1.0 |
|---|---|---|---|---|---|---|
| External source: predicted / observed | 0.0067 | 0.14 / 0.16 (n=358) | 0.28 / 0.28 (n=1310) | 0.49 / 0.48 (n=461) | 0.68 / 0.69 (n=153) | 0.84 / 0.89 (n=19) |
| Market, pre-match: predicted / observed | 0.0101 | 0.14 / 0.14 (n=423) | 0.28 / 0.27 (n=1233) | 0.49 / 0.50 (n=439) | 0.68 / 0.72 (n=171) | 0.84 / 0.83 (n=35) |
| Doyen (DC/Elo ensemble): predicted / observed | 0.0142 | 0.14 / 0.12 (n=295) | 0.28 / 0.28 (n=1368) | 0.48 / 0.47 (n=488) | 0.68 / 0.80 (n=131) | 0.84 / 0.84 (n=19) |

#### Published promptly

Rows first made public within 72 hours after kick-off (or verified before it). Excludes bulk backfills, which could have been selected or changed with the results known.

317 fixtures on 23 match days, 2026-10-14 to 2026-11-08. A verdict needs at least 300 fixtures.

| Forecast | Log loss | Brier |
|---|---|---|
| External source | 0.9747 | 0.5785 |
| Market, pre-match | 0.9491 | 0.5600 |
| Market, closing | 0.9468 | 0.5581 |
| Doyen (DC/Elo ensemble) | 0.9672 | 0.5738 |
| Doyen Dixon-Coles only | 0.9673 | 0.5747 |
| Doyen Elo only | 0.9738 | 0.5766 |
| Uniform one third | 1.0986 | 0.6667 |

| Paired difference (negative = first is better) | Log loss (95%) | Brier (95%) | Verdict |
|---|---|---|---|
| External source minus Market, pre-match | +0.0256 (+0.0048 to +0.0501) | +0.0186 (+0.0037 to +0.0354) | worse |
| External source minus Market, closing | +0.0279 (+0.0043 to +0.0534) | +0.0204 (+0.0042 to +0.0382) | worse |
| External source minus Doyen (DC/Elo ensemble) | +0.0075 (-0.0056 to +0.0235) | +0.0048 (-0.0042 to +0.0156) | inconclusive |
| Doyen (DC/Elo ensemble) minus Market, pre-match | +0.0182 (-0.0002 to +0.0349) | +0.0138 (+0.0015 to +0.0255) | inconclusive |

| Dependency | Value |
|---|---|
| Mean absolute probability gap, source vs Doyen | 0.0352 |
| Mean absolute probability gap, source vs market | 0.0493 |
| Mean absolute probability gap, Doyen vs market | 0.0414 |
| Correlation of probabilities, source vs Doyen | 0.949 |
| Correlation of deviations from the market, source vs Doyen | 0.684 |
| In-sample best weight on the source when pooled with the market | 0.000 |
| In-sample best weight on Doyen when pooled with the market | 0.000 |

| Calibration (all outcomes pooled) | ECE | 0.0-0.2 | 0.2-0.4 | 0.4-0.6 | 0.6-0.8 | 0.8-1.0 |
|---|---|---|---|---|---|---|
| External source: predicted / observed | 0.0404 | 0.14 / 0.17 (n=156) | 0.28 / 0.25 (n=531) | 0.49 / 0.56 (n=187) | 0.68 / 0.62 (n=65) | 0.85 / 0.92 (n=12) |
| Market, pre-match: predicted / observed | 0.0274 | 0.15 / 0.14 (n=169) | 0.28 / 0.25 (n=504) | 0.49 / 0.53 (n=198) | 0.68 / 0.76 (n=70) | 0.85 / 0.90 (n=10) |
| Doyen (DC/Elo ensemble): predicted / observed | 0.0256 | 0.15 / 0.13 (n=119) | 0.28 / 0.26 (n=569) | 0.48 / 0.51 (n=201) | 0.67 / 0.76 (n=55) | 0.84 / 1.00 (n=7) |

## Skorbot

- Source: https://skorbot.live/en/api/
- Licence: none published (site terms: content belongs to Skorbot). Attribution: "Skorbot (skorbot.live)"
- Method: undisclosed AI model
- **Not measured.** no open licence; the archive and the change feed needed to prove a pre-kick-off version are in the paid Pro tier; the free feed held 86 finished predictions and was last refreshed on 2026-11-05.

