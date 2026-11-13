# Sports Betting Doyen

**Live site:** https://juanxmarcos.github.io/Sports-Betting-/

An autonomous sports betting research assistant for **soccer, NFL, NBA and tennis**. You open the site, see the day's strongest evidence-based opportunities, why they qualify, and what could go wrong.

> Research and paper trading only. Doyen never places bets. Picks are estimates, never guarantees. Most bets lose, including good ones.

## What you see
- **Picks of the Day:** every pick that currently qualifies today, shown as equal cards with selection, best price, Doyen's probability, expected value, the reasoning, and the main risk. Zero, one or several are all normal; when nothing qualifies the page says so. Tomorrow and This Week have their own headings.
- **Recommended Parlays of the Day:** currently always "No verified parlays today". Doyen has no bookmaker-quoted parlay price and no tested joint probability, so it recommends none. See [docs/PARLAYS.md](docs/PARLAYS.md).
- **Matches Doyen Is Watching:** near-misses and interesting fixtures, clearly *not* recommendations, with what Doyen is waiting for.
- **Upcoming**, **Pick History** (immutable, at original odds), **Watchlist** (stored in your browser), and **Ask Doyen** (opens Claude with your question plus Doyen's data; no embedded AI, no secrets).
- Sport filters (All / Soccer / NFL / NBA / Tennis), date filters (Today / Tomorrow / This Week), and a timezone picker (DST-aware).

## How picks are made (short version)
A pick needs a bookmaker price that beats a **sharp, margin-free market consensus** (Pinnacle / Betfair Exchange / multi-book median) by at least 3%. It also needs odds between 1.30 and 6.00, quotes from at least 3 bookmakers, fresh prices, and enough history on both sides. Each sport has its own model (Dixon-Coles goals; points ratings for NFL/NBA; surface Elo for tennis). A model only gets weight against the market once it has beaten the market out of sample. So far none has, so the models provide context and risk flags rather than the edge. Details: [docs/METHODOLOGY.md](docs/METHODOLOGY.md) and [docs/AUDIT.md](docs/AUDIT.md).

## Running it
```bash
pip install -r requirements.txt
```
```bash
python -m sbi daily        # ingest all sports → settle → model → EV → reassess → site
```
```bash
python -m sbi serve        # diagnostics view (docs/dev) on http://localhost:8000
python -m sbi coverage     # source coverage audit (read-only) → reports/source_coverage.md
python -m sbi independence # bookmaker-independence audit (read-only) → reports/independence_audit.md
```
```bash
python -m pytest -q
```
Automation: `.github/workflows/daily.yml` runs every 2 hours and commits the data, reports and site. A Claude Code scheduled task (`automation/claude_research_routine.md`) adds evidence-graded team-news notes. Optional: the `ODDS_API_KEY` secret enables multi-bookmaker odds (free tier, budgeted per day).

## Docs
[Development workflow](docs/DEVELOPMENT_WORKFLOW.md) · [Audit](docs/AUDIT.md) · [Methodology](docs/METHODOLOGY.md) · [Architecture](docs/ARCHITECTURE.md) · [Data sources](docs/DATA_SOURCES.md) · [Feasibility](docs/FEASIBILITY.md) · [Roadmap](docs/ROADMAP.md)
