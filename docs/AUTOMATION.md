# Event-driven Claude Code pickup (issue #8)

**Status: active and verified (2026-11-13).** The owner created the GitHub-triggered task in
claude.ai on 2026-11-13. Dry-run issue #11 was created with the `ready-for-claude` label at
00:47 UTC. The triggered agent claimed it at 00:47:31 UTC and opened PR #12 ("Closes #11") at
00:48:23 UTC, and the PR's `tests` check passed. That is about one minute from label to PR,
with no manual step. No secret was added to GitHub.

## 1. Feasibility and compliance finding

Question: can a GitHub event start Claude Code promptly, using only the owner's existing
Claude Max subscription, with no new charges and within Anthropic's terms?

Two mechanisms were assessed (official sources checked 2026-11-13):

| | **A. Native GitHub-triggered Claude Code task** (recommended) | **B. `anthropics/claude-code-action` in GitHub Actions + subscription OAuth token** (not enabled) |
|---|---|---|
| What it is | A Claude Code scheduled task on claude.ai with a GitHub trigger. Each matching event starts a fresh Claude Code cloud session | A GitHub Actions workflow that runs Claude Code on GitHub's runners |
| Credential | None leaves Anthropic. Uses the Claude GitHub App already used by cloud sessions | A one-year subscription token (`claude setup-token`) stored as a GitHub secret |
| Billing | "Scheduled tasks draw down subscription usage the same way interactive sessions do." Metered overage only if usage credits are turned on | "If you authenticate with an OAuth token, runs use your Claude subscription instead of API billing." GitHub Actions minutes are free on public repos |
| Terms fit | Runs inside Claude Code itself, a native Anthropic application. This is the "ordinary use of Claude Code and other native Anthropic applications" that subscription OAuth is intended for | Documented by Anthropic, but the legal page frames subscription OAuth around ordinary, individual use and points automation builders to API keys. Issue #8 forbids using subscription credentials for GitHub Actions until that is explicitly settled, so it is **not enabled** |
| Gaps | Triggers cover Issue, Pull request and Release events. `issue_comment` and `pull_request_review` are not trigger types (review handling below) | Exporting a long-lived subscription token into a public repo's secrets adds risk |

**Conclusion:** option A is compliant and adds $0 of recurring cost, provided **usage
credits / extra usage stay OFF** on the Claude account. With them off, runs past the
subscription limit are rejected instead of billed. Option B stays documented only as a
fallback the owner may choose after their own review of the terms.

Other limits that apply:
- The feature is a research preview: "Behavior, limits, and the API surface may change."
- Hourly caps apply per task and per account, including for GitHub events. A run over the
  cap waits or fails; nothing is charged.
- Each run uses Max usage the same way an interactive session does. Runs that fail the
  gate (below) stop immediately, so they use very little.

Sources:
- Scheduled tasks and GitHub triggers: https://code.claude.com/docs/en/routines
- Claude Code GitHub Actions (OAuth token billing): https://code.claude.com/docs/en/github-actions
- Authentication and `claude setup-token`: https://code.claude.com/docs/en/authentication
- Credential use terms: https://code.claude.com/docs/en/legal-and-compliance
- GitHub Actions billing (free for public repos): https://docs.github.com/en/billing/concepts/product-billing/github-actions

## 2. How the handoff works once active

1. ChatGPT (through the owner's account) or the owner creates an issue with Goal / Scope /
   Acceptance criteria / Constraints.
2. The owner's account applies the label **`ready-for-claude`**. This is the authorization.
3. GitHub sends an `issues.labeled` event, and Claude Code starts a fresh session within
   moments, running [`automation/github_issue_trigger_prompt.md`](../automation/github_issue_trigger_prompt.md).
4. The session checks the gate, claims the issue, works on `claude/issue-N-…`, runs the
   tests, opens a PR with "Closes #N", comments the PR link on the issue, and subscribes to
   the PR.
5. ChatGPT reviews the PR. Each review or comment from `juanxmarcos` wakes that session,
   which makes the changes on the same branch and replies.
6. The owner merges. Nothing merges automatically.

## 3. Security model

- **Authorization is the label, not the title.** On GitHub only collaborators with triage
  or higher access can apply labels, and `juanxmarcos` is the only collaborator. A
  `[Claude]` title prefix, which anyone can type on a public repo, does not authorize the
  event-driven agent.
- **The gate is re-checked from GitHub.** The run re-fetches the issue and requires: open,
  authored by `juanxmarcos`, currently labelled `ready-for-claude`, and not already claimed.
  On failure it stops silently, so outsiders can't make it post or work.
- **Untrusted text stays data.** Issue and comment text never overrides the stored prompt.
  Anthropic's runtime also treats triggered input as untrusted and runs the session in auto
  mode, with a classifier that blocks risky actions.
- **No duplicates.** The claim comment, a re-check after claiming, and the check for an
  existing `claude/issue-N-*` branch or PR stop a second run (for example after a label is
  removed and re-added). The 2-hour scheduled agent respects the same claim comment.
- **Least privilege and no secrets.** No GitHub secret, no API key and no workflow file are
  added. Pushes go to `claude/` branches; the prompt forbids pushing to `main`, merging,
  auto-merge, spending and betting. For a hard guarantee, add a ruleset that blocks the
  Claude GitHub App from pushing to `main` (the bot's data commits use `github-actions`, so
  they are unaffected).
- **Budgets.** One issue per run, no retry loops, and Anthropic's hourly caps. Runs past
  the subscription limit are rejected while usage credits are off.
- **`daily.yml` is untouched.** The sports-data publishing workflow and its direct commits
  to `main` don't change.

## 4. Owner setup (one time, about 5 minutes, $0)

You don't need to paste any secret anywhere.

1. **Create the label.** In GitHub, go to Issues → Labels → New label, name it
   `ready-for-claude` and save.
2. **Check billing safety.** In claude.ai settings, confirm that usage credits / extra usage
   are **off**.
3. **Create the task.** Open claude.ai/code/routines → New:
   - Repository: `juanxmarcos/Sports-Betting-`, in the same cloud environment as the
     existing Doyen tasks.
   - Trigger: **GitHub event → Issue: Labeled**. Don't add an `opened` trigger: the dry run
     showed that an issue created with the label already on it still fires `labeled`.
   - Filters (recommended, to save runs): **Labels** contains `ready-for-claude`, and
     **Author** equals `juanxmarcos`. The prompt's gate re-checks both as a second layer.
   - Prompt: everything below the line in
     [`automation/github_issue_trigger_prompt.md`](../automation/github_issue_trigger_prompt.md).
   - If asked, confirm the Claude GitHub App is installed on this repository. Cloud sessions
     already use it.
4. **Dry run.** Ask ChatGPT to create a documentation-only test issue, then apply
   `ready-for-claude`. Expect within minutes: a run in claude.ai/code, a claim comment, a
   `claude/issue-N-…` branch and a PR. Leave the PR on the issue as evidence for #8.

## 5. Pause, disable and roll back

- **Pause:** use the on/off switch at the top of the task in claude.ai/code/routines.
- **Delete:** use the menu next to the task name → Delete.
- **Stop a single issue:** remove the `ready-for-claude` label before it is claimed.
- **Retry a failed issue:** delete the claim comment and apply the label again.
- None of these touch `daily.yml`, the site or data publishing.

## 6. Failure reporting

- A run that fails after claiming comments on the issue with what failed and what is needed.
- Every run is listed with its transcript in claude.ai/code under the task.
- The `tests` check on each PR is the independent pass/fail signal.

## 7. Coexistence with the scheduled agent (issue #5)

- The existing **2-hour scheduled Doyen GitHub agent** keeps running unchanged. It picks up
  `[Claude]` or labelled issues the event path missed and answers review feedback on any
  `claude/issue-*` PR. Both paths honour the same claim comment, so they never work the
  same issue.
- Issue #5 remains the test of the *scheduled* pickup.
- Only after the dry run in section 4 succeeds should the owner decide whether to slow the
  scheduled agent (for example to every 6 hours, as a safety net) or keep it as is.

## 8. Fallbacks

- Manual: tell Claude Code "work on issue #N".
- Scheduled: the 2-hour agent described in [DEVELOPMENT_WORKFLOW.md](DEVELOPMENT_WORKFLOW.md).
- Option B above, only if the owner decides after reviewing Anthropic's terms. It would need
  its own issue, a minimal-permission workflow and the token stored as a GitHub secret by
  the owner.
