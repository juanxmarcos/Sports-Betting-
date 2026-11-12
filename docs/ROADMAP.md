# Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 Feasibility & architecture | Max vs API, scheduling, sources, constraints | **Done** — `FEASIBILITY.md`, `ARCHITECTURE.md`, `DATA_SOURCES.md` |
| 2 Football data foundation | football-data connector (results, xG, multi-book pre/closing odds, fixtures), SQLite schema | **Done** (10 leagues) |
| 3 Prediction engine | Dixon-Coles (time-decay, ridge, parameter covariance), Elo baseline, walk-forward validation | **Done** (v dc-0.1) |
| 4 EV engine | Power de-vig, sharp consensus, best price, commission, push-aware EV for AH/OU, uncertainty-aware filters | **Done** |
| 5 Daily reports | Markdown report incl. "no qualifying opportunities", evidence, risks, near-misses | **Done** |
| 6 Backtesting & paper trading | Walk-forward, tuned hyperparameters and blend weights, ROI/CLV with CIs, static dashboard | **Done** (MVP) |
| 7 Automation | GitHub Actions twice daily; Claude scheduled-task research routine | **Configured** — activate after merge |
| 2c National teams | martj42 history + ESPN fixtures/odds, neutral-venue DC (beats Elo out of sample), live monitoring vs DraftKings | **Done** (monitoring mode) |
| 2b | The Odds API (free key) connector for fresher odds and BTTS/DC markets; ESPN fixtures fallback | Next |
| 3b | xG-based DC variant (football-data xG from 2026-27), evaluated once enough out-of-sample matches exist; lineup-strength features | Next |
| 3c | Probability calibration layer (isotonic/Platt on validation) if reliability diagrams show bias | Next |
| 8a | Basketball: efficiency/pace ratings + rest/travel, moneyline/spread/total | Planned |
| 8b | Tennis: surface Elo + serve/return model, match winner / games totals | Planned (data access to verify) |
| 8c | NHL / MLB (public league APIs accessible), NFL (nflverse) | Planned |

Model change policy: every change gets a new `model_version`. It is evaluated on the same
walk-forward test seasons, and it is adopted only if it improves out-of-sample log loss
and/or CLV beyond bootstrap noise. Results from previously published recommendations are
never used to tune rules.
