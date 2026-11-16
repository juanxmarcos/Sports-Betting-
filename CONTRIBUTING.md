# Contributing to Sports Betting Doyen

All development follows the issue → branch → PR → review loop described in
**[docs/DEVELOPMENT_WORKFLOW.md](docs/DEVELOPMENT_WORKFLOW.md)**.

Short version:
1. Every task starts as a GitHub issue with **Goal**, **Scope**, **Acceptance criteria** and **Constraints**.
2. Branch from the latest `main` as `claude/issue-<number>-<short-description>`.
3. Run `python -m pytest -q` (and the site checks for visual or data changes), then open a PR to `main` that links the issue.
4. Feedback goes in PR reviews. Zero-cost PRs with all checks green are merged by the GitHub Actions auto-merge gate once the owner enables it ([docs/AUTO_MERGE.md](docs/AUTO_MERGE.md)); anything that might cost money waits for the owner.

Never commit secrets, never invent data or results, keep published picks immutable, and add no paid services.

## Requesting a Doyen improvement

- Put every development request in a **GitHub Issue**, not in chat. Give it four sections: **Goal**, **Scope**, **Acceptance criteria** and **Constraints**.
- To make an issue eligible for automatic pickup by the scheduled Claude Code agent, start its title with **`[Claude]`** or add the **`ready-for-claude`** label. The agent takes the oldest unclaimed eligible issue, comments that it is working on it, and opens a linked PR.
- Claude submits pull requests but **never merges them**. Merges are done by the owner, or by the GitHub Actions gate for zero-cost PRs. Spending always needs the owner.
- The full process, rules and automation details are in **[docs/DEVELOPMENT_WORKFLOW.md](docs/DEVELOPMENT_WORKFLOW.md)**.
