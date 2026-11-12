# Sports Betting Doyen — Architecture

```
                 ┌──────────────── GitHub Actions cron (free) ────────────────┐
                 │ python -m sbi daily  (deterministic, no LLM, no API keys)  │
football-data ──►│ ingest ─► settle ─► analyse (DC model + EV) ─► publish     │──► reports/YYYY-MM-DD.md
fixtures.csv  ──►│   │          │            │                       │        │──► docs/dashboard/ (static)
season CSVs   ──►│   ▼          ▼            ▼                       ▼        │──► ledger/recommendations.csv
                 │            data/sbi.sqlite (single file, committed)        │
                 └────────────────────────────────────────────────────────────┘
                                   ▲  research notes (risk flags only)
                 ┌─────────────────┴──────────────────────────────────────────┐
                 │ Claude Code scheduled task (Max subscription)              │
                 │ brief → web research → `sbi note` → `sbi report` → push    │
                 └────────────────────────────────────────────────────────────┘
```

## Modules (`sbi/`)

| Module | Responsibility |
|---|---|
| `config.py` | Leagues, selection rules, model settings, paths, timezone (env `SBI_TIMEZONE`) |
| `db.py` | SQLite schema, immutability triggers, job and provider logging |
| `sources/http.py` | Polite fetch: cache, retry/backoff, stale-cache fallback, stop on 401/403/429 |
| `sources/football_data.py` | CSV parsing (results, xG, odds in long format), event/odds upserts |
| `models/dixon_coles.py` | Time-weighted Dixon-Coles MLE with analytic gradient and a Fisher-information covariance |
| `models/elo.py` | Elo + ordered-logit baseline (benchmark only) |
| `markets.py` | Score matrix → 1X2/DC/OU/BTTS/AH outcome shares (quarter lines, pushes) and settlement |
| `ev.py` | De-vigging (power method), sanity filter, consensus, best price, exchange commission, blending |
| `engine.py` | `price_event` + `select`, shared by live and backtest (identical rules) |
| `pipeline.py` | Daily orchestration and evidence assembly |
| `settle.py` | Settlement, P/L, closing line value |
| `performance.py` | ROI, yield CI, drawdown, CLV, Brier/log loss, breakdowns, calibration |
| `backtest.py` | Walk-forward evaluation, hyperparameter and blend-weight fitting |
| `report.py`, `dashboard.py`, `templates/` | Markdown report, static dashboard + `data.json`, CSV ledger |
| `research.py` | Research brief and evidence-graded notes (Claude interface) |

## Database (SQLite, `data/sbi.sqlite`)

| Table | Purpose | Key columns |
|---|---|---|
| `events` | Fixtures and results | event_id (`football:E0:20261121:arsenal:chelsea`), kickoff_utc, scores, xG, source_url |
| `odds` | Append-only odds snapshots | event_id, bookmaker, market, selection, line, price, kind (pre/closing), retrieved_at |
| `model_runs` | One row per fit | model_version, league, trained_through, params |
| `predictions` | Every model probability for every analysed fixture (bet or not) | model_prob, prob_sd, market_prob, final_prob |
| `recommendations` | **Immutable** published paper selections | odds, probabilities, EV, evidence_json, source_urls; settlement columns only are mutable |
| `research_notes` | Claude's findings | category, claim, evidence_type (verified_fact/interpretation/speculation), direction, source_url |
| `job_runs`, `provider_status` | Operations | status, errors, last success |
| `backtest_results` | Versioned evaluation reports | metrics_json |

Immutability is enforced in the database itself: triggers abort any UPDATE of published
fields and any DELETE on `recommendations`.

Storage policy: closing odds are stored only for events we predicted, and full history is
re-derivable from the source CSVs. This keeps the committed DB small, at roughly a few MB
per season.

## Why not Next.js + FastAPI (yet)?
A static page fed by `data.json` needs no server, works offline, and can be hosted free on
GitHub Pages. It does everything the dashboard needs today. FastAPI or Next.js become
worthwhile only if interactive write operations are needed. That is an easy later swap,
because `data.json` is already an API-shaped contract.
