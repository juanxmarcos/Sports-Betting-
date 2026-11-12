# Sports Betting Doyen — development workflow

GitHub is the shared workspace for Sports Betting Doyen. Requirements live in **issues**,
implementation happens in **pull requests**, and feedback happens in **PR reviews and comments**.
The owner no longer needs to paste prompts between tools or send ZIP snapshots.

## Roles

| Who | Does |
|---|---|
| **Owner** | Sets priorities. Approves consequential product, deployment or spending decisions. Merges PRs. |
| **ChatGPT** | Reviews the repository, writes actionable issues, inspects PRs (diffs, tests, screenshots) and leaves review comments. |
| **Claude Code** | Reads issues, implements changes on a task branch, runs tests, opens a PR and responds to review feedback. |
| **GitHub** | Source of truth for requirements, discussion, code, status and results. |

## The loop

```
Issue (Goal / Scope / Acceptance criteria / Constraints)
  → Claude Code: branch from latest main  →  implement  →  test
  → Pull request to main ("Closes #N" or "Part of #N")
  → ChatGPT / owner review comments  →  Claude Code addresses them on the same branch
  → Owner approves and merges
```

### Writing an issue
Each substantive request is its own issue with these four headings:
- **Goal**: what should be true when this is done.
- **Scope**: what is in and what is explicitly out.
- **Acceptance criteria**: how we will know it is done (testable).
- **Constraints**: data, design, cost or safety limits that apply.

If an issue is unclear on a consequential decision, Claude Code asks in an issue comment instead of guessing.

### Branches
- Always branch from the latest `main`.
- Name: `claude/issue-<number>-<short-description>`, for example `claude/issue-1-collaboration-workflow`.
- One issue per branch. Keep changes focused and don't bundle unrelated features.

### Pull requests
Open every PR against `main`, and include in the description:
- The issue link: `Closes #N` when the PR completes the issue, `Part of #N` when it doesn't.
- A short **summary** in plain language.
- **Screenshots** (mobile and desktop) for any visual change.
- **Test evidence**: the exact commands and their results (see below).
- **Risks and known limitations**.

The template in `.github/pull_request_template.md` pre-fills these sections.

### Reviews
- Feedback goes in PR review threads or PR comments.
- Claude Code pushes fixes to the same branch and replies to each thread with what changed.
- **No auto-merge.** Consequential changes are merged only with the owner's approval.

## Checks to run before opening a PR

```bash
python -m pytest -q
```

For changes to the pipeline or site data:

```bash
python -m sbi daily
```

Then serve the site locally and check it on mobile and desktop widths:

```bash
cd docs && python -m http.server 8790
```

GitHub Pages serves the site from `/docs` under the base path `/Sports-Betting-/`. Every asset and data path in `docs/index.html` and `docs/assets/doyen.js` must stay **relative** (`assets/…`, `data/doyen.json`, `#/route`). Never use root-absolute paths (`/assets/…`), which break under the base path.

Report commands and results accurately. If something was not run, the PR says so.

## Project rules (always apply)

- **Truthfulness.** Never invent sports statistics, odds, model performance, results or picks. Don't describe a feature as implemented unless the code and tests or verification support it.
- **Immutable history.** Published recommendations and their original odds are never edited or deleted; status changes are append-only (`rec_updates`).
- **No threshold-tuning for volume.** Don't change betting thresholds just to publish more picks. Rule changes need out-of-sample evidence.
- **Minimal site.** Brief pick cards, with deeper research in Details. Supported sports: Soccer, NFL, NBA and Tennis only.
- **Zero additional recurring cost.** No paid APIs, metered services, new hosting charges or purchases without owner approval. A Claude Max subscription does not necessarily cover unattended API usage.
- **Secrets.** Never commit keys, tokens or credentials. Secrets live only in GitHub Actions secrets, and stored errors are redacted (`sbi.db.redact`).
- **Preserve data and design.** Keep project data, existing functionality and the current Doyen design unless an issue says otherwise.

## Automated commits to `main` (existing behaviour)

The scheduled workflow `.github/workflows/daily.yml` (every 2 hours) commits refreshed data, reports and site files **directly to `main`** as `sbi-bot`. The daily Claude research task does the same. This automated data flow is intentional and stays unchanged. **Code** changes go through PRs.

## Branch protection: recommendation (not enabled)

Requiring pull requests on `main` would **block the automated data commits above**, and the site would stop updating. If the owner wants protection, choose one of:
1. Protect `main` with "Require a pull request" **and** allow `github-actions[bot]` to bypass. This needs a ruleset with a bypass list (available on public repos).
2. Or keep `main` unprotected and rely on this workflow convention (the current setup).

A required status check (for example `pytest`) would need a separate PR-triggered workflow. None exists today. Adding one is a small, free change (GitHub Actions minutes are free for public repos) that can be proposed in its own issue.

## Automatic issue pickup: options assessed (not enabled)

This document sets up a **GitHub-based handoff**, not real-time AI-to-AI chat. ChatGPT and Claude Code don't talk to each other directly; they communicate through issues, PRs and comments, and a person (or an explicitly enabled automation) starts each Claude Code session.

| Option | How it works | Authentication | Cost / limits | Notes |
|---|---|---|---|---|
| **Manual (current)** | Owner asks Claude Code to "work on issue #N" | Existing Claude Code session | Counts toward Claude Max usage limits; no extra cost | Simplest, owner stays in control |
| **Claude Code GitHub Action** (`anthropics/claude-code-action`) | A workflow runs Claude Code when an issue or comment mentions `@claude` | `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token` (subscription), or an API key (**metered: not allowed** under the zero-cost rule) | GitHub Actions minutes are free for public repos; subscription usage counts toward Max limits. Anthropic's terms describe OAuth use as intended for ordinary individual use, so heavy unattended automation should use an API key, which costs money | Needs a workflow file and a secret. Runs unattended, so scope permissions tightly |
| **Claude Code scheduled task** (claude.ai) | A recurring session checks for issues labelled e.g. `ready-for-claude` and opens PRs | Owner's Claude account | Counts toward Max usage limits; hourly at most | Same mechanism as the existing daily research task |

Nothing above is enabled by this document. Enabling any unattended option needs its own issue and the owner's explicit approval after reviewing authentication, usage limits and cost.
