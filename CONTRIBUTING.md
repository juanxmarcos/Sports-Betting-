# Contributing to Sports Betting Doyen

All development follows the issue → branch → PR → review loop described in
**[docs/DEVELOPMENT_WORKFLOW.md](docs/DEVELOPMENT_WORKFLOW.md)**.

Short version:
1. Every task starts as a GitHub issue with **Goal**, **Scope**, **Acceptance criteria** and **Constraints**.
2. Branch from the latest `main` as `claude/issue-<number>-<short-description>`.
3. Run `python -m pytest -q` (and the site checks for visual or data changes), then open a PR to `main` that links the issue.
4. Feedback goes in PR reviews. The owner approves and merges; nothing auto-merges.

Never commit secrets, never invent data or results, keep published picks immutable, and add no paid services.
