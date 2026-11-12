# Sports Betting Doyen — Phase 1 — Feasibility under a zero-additional-cost constraint

*Verified 2026-11-12 from this cloud session (HTTP checks) and the official Claude Code docs.*

## 1. What Claude Max covers (and what it does not)

| Capability | Covered by Max? | Notes / source |
|---|---|---|
| Claude Code (CLI, desktop, web at claude.ai/code) | **Yes** | Draws on the subscription's shared usage pool: rolling 5-hour session limit + weekly limit. Anthropic publishes no fixed numbers; check `/usage`. <https://code.claude.com/docs/en/costs.md> |
| Claude Code **scheduled tasks** (cloud) | **Yes** (research preview) | Run on the subscription and count toward its limits. Most frequent schedule is hourly; scheduled runs are capped at 100/hour per account. <https://code.claude.com/docs/en/routines.md> |
| Headless `claude -p` on your own machine (cron) | **Yes** | Uses your `/login` subscription. Do **not** use `--bare` (that requires an API key). <https://code.claude.com/docs/en/headless.md> |
| Claude Code GitHub Action | **Yes, with caveats** | `claude setup-token` creates a 1-year OAuth token (`CLAUDE_CODE_OAUTH_TOKEN`). It is intended for ordinary individual use; Anthropic recommends API keys for high-volume automation. <https://code.claude.com/docs/en/github-actions.md> |
| Anthropic **API** (Messages API, SDK calls from Python) | **No — metered separately** | The platform therefore makes **no** API calls. If `ANTHROPIC_API_KEY` is set, Claude Code bills that key instead of the subscription. Keep it unset everywhere. <https://code.claude.com/docs/en/authentication.md> |

**Design consequence.** All numerical work (ingestion, modelling, EV, settlement, backtests,
reports, dashboard) is deterministic Python with no LLM calls. Claude is used only for
(a) development and (b) contextual research run as a Claude Code session or scheduled task
on the subscription (`automation/claude_research_routine.md`).

## 2. What runs unattended at zero cost

| Step | Mechanism | Unattended? |
|---|---|---|
| Discover fixtures + current odds, ingest results | GitHub Actions cron → `python -m sbi daily` | **Yes** |
| Model, EV, rank, publish report + dashboard, record predictions | same job | **Yes** |
| Settle results, closing line value, performance | same job | **Yes** |
| Contextual research (team news, lineups, injuries) | Claude Code scheduled task (subscription) | **Yes**, within Max usage limits. Research-preview feature, so availability may change. |
| Dashboard hosting | GitHub Pages (`/docs`) or local `python -m sbi serve` | Pages is free for **public** repos only. For a private repo, open it locally or make a public mirror. |
| Placing bets | — | **Never.** Paper trading only, by design. |

**Remaining manual items.** (1) Merge this branch to the default branch so the scheduled
workflow runs, because GitHub only runs cron workflows from the default branch. (2) Create the
Claude scheduled task once, with the prompt in `automation/`. (3) Optionally enable GitHub Pages.
(4) Optionally get a free The Odds API key for wider odds coverage (not required).

**Constraints to know.**
- GitHub disables scheduled workflows in public repos after 60 days without repository activity. The bot's daily commits count as activity.
- Private repos get 2,000 free Actions minutes per month. This job uses about 3 minutes × 2 runs × 30 days ≈ 180 minutes.
- Claude scheduled tasks share your Max usage pool with your interactive use. Keep the routine short: it only researches open selections.

## 3. Data access reality (tested from this environment)

| Source | Result | Decision |
|---|---|---|
| football-data.co.uk (results, stats, **xG from 2026-27**, multi-bookmaker pre + closing odds, upcoming `fixtures.csv` with odds) | 200 OK | **Primary football source** |
| ESPN public JSON (`site.api.espn.com`) fixtures/scores | 200 OK, undocumented | Possible fallback for fixtures and results (not yet wired) |
| Understat | 200 OK | Candidate xG source. Terms unclear, so it is not scraped. football-data now carries xG. |
| Forebet | **403** (bot protection) | Not automated. We do not bypass protections. Manual reference only. |
| FBref / Sports-Reference | **403**. Its bot policy restricts automation | Not used |
| The Odds API | 401 without a key. Free tier needs a key (about 500 credits/month) | Optional connector (Phase 2b) |
| Open-Meteo (weather) | 429 from the shared sandbox IP. Free for non-commercial use | Use from GitHub Actions / locally |
| MLB Stats API, NHL `api-web.nhle.com` | 200 OK | Phase 8 sources |
| NBA `stats.nba.com` / `cdn.nba.com` | 403 from this cloud IP | Use Basketball-Reference CSV exports manually, or run from a home IP |
| Jeff Sackmann tennis (GitHub), tennis-data.co.uk | Blocked by this sandbox's proxy / 403 | Re-verify from GitHub Actions in Phase 8 |

**Verdict:** a football-first platform is fully feasible at zero additional cost. Basketball
and tennis are feasible with caveats on data access (Phase 8).
