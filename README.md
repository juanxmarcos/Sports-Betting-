# SBI — Sports Betting Intelligence (research platform)

An autonomous, statistically rigorous **research and paper-trading** system that looks for
potentially mispriced betting markets, publishes a daily evidence-based report, and measures
its own performance honestly over time.

> **It never places bets.** All tracked results are simulated, fixed-unit paper trades.
> Nothing here is financial advice. Short-term profit is not evidence of an edge.

**Zero additional cost:** Python + SQLite + free data (football-data.co.uk) + GitHub Actions
cron + a static dashboard. Claude is used through your Claude Max subscription (Claude Code
and scheduled tasks) for development and contextual research. The pipeline itself makes no
metered API calls. See [docs/FEASIBILITY.md](docs/FEASIBILITY.md).

## Quick start

```bash
pip install -r requirements.txt
```

```bash
python -m sbi daily        # ingest → settle → model → EV → report → dashboard
```

```bash
python -m sbi serve        # dashboard at http://localhost:8000
```

```bash
python -m sbi backtest     # walk-forward evaluation (~25 min); writes data/tuned.json
```

```bash
python -m pytest -q
```

Other commands: `ingest`, `settle`, `analyse`, `report`, `dashboard`, `brief`, `note`, `status`.

## Outputs
- `reports/YYYY-MM-DD.md`, `reports/latest.md`: the daily intelligence report
- `docs/dashboard/`: static dashboard (open via `sbi serve` or GitHub Pages)
- `ledger/recommendations.csv`: permanent, human-readable record of every published selection
- `data/sbi.sqlite`: full database (published rows are immutable and enforced by triggers)
- `data/backtest/report.json`: latest out-of-sample evaluation

## Automation
1. Merge to the default branch. `.github/workflows/daily.yml` then runs at 06:15 and 16:15 UTC and commits results.
2. Optional: create a Claude Code scheduled task with `automation/claude_research_routine.md` to add evidence-graded team-news flags.
3. Optional: set the repository variable `SBI_TIMEZONE` (IANA name, default `Europe/London`).

## Docs
[Feasibility](docs/FEASIBILITY.md) · [Architecture & DB](docs/ARCHITECTURE.md) ·
[Methodology & results](docs/METHODOLOGY.md) · [Data sources](docs/DATA_SOURCES.md) ·
[Roadmap](docs/ROADMAP.md)
