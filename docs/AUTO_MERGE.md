# Zero-cost auto-merge (issues #29 and #71)

**Status: built, off by default, not yet verified end to end.** Until the owner finishes the
setup below and one real PR has been merged by the gate, no automatic merge is guaranteed.
Every PR still needs a manual merge until then.

## Owner rule (2026-11-16)

> All changes that require no new payment may be approved and merged automatically. Any change
> that would require the owner to pay money (paid API, hosting or service subscription,
> metered usage, billed upgrade, spend of any kind) must **not** be approved, enabled or
> merged automatically. The owner alone approves spending.

## Owner rule restated (2026-11-18, issue #71)

> "if all requirements are met, auto merge. Same thing for deployments."

So the spend gate routes a change to the owner only on a **real spend signal**, not merely
because it touches a data connector or contains a URL. PR #70 (free ESPN club-soccer fixtures)
was zero-cost with green tests but went to the owner only because it touched `sbi/sources/`
and contained `https://` URLs; under the #71 rules it passes.

**Deployments.** The site is served by GitHub Pages from `main` (`docs/`). Pages deploys
automatically on every push to `main`, at no cost on a public repository, so a merged PR is
deployed with no extra step. Changes under `docs/` keep auto-merging like other code. What
still goes to the owner is a new hosting or deployment target that could bill (Vercel,
Netlify, Heroku, AWS, GCP, Azure, Firebase, Cloudflare Workers…, their config files, or a
`CNAME` pointing the site somewhere else).

## How it works

`.github/workflows/auto-merge.yml` runs `automation/auto_merge.py` when:
- the `tests` workflow finishes successfully on a pull request (`workflow_run`), or
- a label is added or removed, or a draft is marked ready (`pull_request_target`).

Both trigger types always run the workflow file and the gate script **from `main`**. The
pull request's own version of either file never runs, and no pull request code is checked
out, imported or executed. The gate uses only the built-in `GITHUB_TOKEN`; no secret, no
personal token, no Claude credential. It is driven entirely by GitHub events: no polling,
no schedule and no Claude usage.

The gate fetches everything fresh from the GitHub API and merges (squash, pinned to the
exact head commit it checked) only if **all** of these hold. Anything missing or unreadable
counts as a failure.

| # | Gate | Fails how |
|---|---|---|
| 1 | Open, non-draft PR to `main`; head branch in **this** repository (no forks) | silent skip |
| 2 | PR author is `juanxmarcos` (Claude's PRs are opened under the owner's account) | silent skip |
| 3 | Branch is `claude/issue-<N>-<description>`, the body says `Closes #N` or `Part of #N` for that same N, and issue N is open, authored by `juanxmarcos`, and carries `ready-for-claude` | silent skip |
| 4 | Opened after the rollout cutoff (2026-11-17 00:00 UTC), or the owner applied `automerge-opt-in` | silent skip |
| 5 | No `do-not-merge` or `hold` label | silent skip |
| 6 | **Spend gate** (below) finds nothing, or the owner applied `owner-approved-spend` | label `needs-owner-decision` + one comment |
| 7 | Strict mode only: the owner applied `zero-cost-approved` | silent skip |
| 8 | Every check on the head commit is green: `pytest` must succeed, every other check run must be success/neutral/skipped, commit statuses must be success | waits, or skips if red |
| 9 | GitHub reports the PR mergeable against the current `main` (no conflicts) | waits, or skips |
| 10 | Since the branch point, `main` changed only scheduled-data paths (`data/`, `reports/`, `ledger/`, `docs/data/`, `docs/dev/`). Any code change on `main` means the branch must merge `main` and re-run tests first | skip with reason |

### Owner labels are checked for who applied them and when

`owner-approved-spend`, `zero-cost-approved` and `automerge-opt-in` count only if:
- the label is on the PR now;
- its latest `labeled` event was made by `juanxmarcos` **directly** (`performed_via_github_app`
  is empty). Labels applied through a GitHub App, which includes AI agents acting through a
  connector under the owner's account, do not count;
- it was applied **after** the first check started on the current head commit (a server
  timestamp). Pushing new commits makes an earlier approval stale.

Text in a PR title, body, commit message, file name or comment never grants anything.

## The spend gate: what it can and cannot do

**Automated code review cannot prove that a change has no financial impact.** A paid service
can be enabled by a line that mentions no price at all. So the gate does not try to *prove*
zero cost. It is a fail-closed router that sends anything that *might* involve money to the
owner, and lets the rest through:

- **Protected paths, any change (including a rename from or to them):** `.github/` (CI,
  workflows, this gate's workflow) and `automation/` (agent prompts, this gate), because a PR
  must not be able to weaken the gate or CI itself; dependency and test-config files
  (`requirements*.txt`, `pyproject.toml`, `conftest.py`, `pytest.ini`…); deployment and
  secret files (`.env*`, `Dockerfile`, `vercel.json`, `netlify.toml`, `wrangler.toml`,
  `firebase.json`, `*.tf`, `CNAME`…) and `.gitignore`/`.gitattributes`.
  **`sbi/sources/` is no longer protected (#71):** connectors are treated like other code.
- **Content signals on added *and* removed lines** of code (removing a guard can raise spend):
  - money and billing words, also in comments: billing, invoice, subscription, paid
    plan/tier/API, pricing tier, premium plan, metered, overage, payment, checkout, Stripe,
    PayPal, credit card, purchase, upgrade;
  - metering words **in code only** (not in `#`/`//` comments): cost, credits, quota, spend,
    usage-based. `credits_used += 3` is flagged; a comment explaining how credits are shared
    is not;
  - credentials: `secrets.`, API keys, tokens, `authorization`, passwords, `os.environ`,
    `getenv`;
  - **URLs only to new hosts (added lines):** a URL to a host the project already uses or a
    free public endpoint (`site.api.espn.com`, `www.espn.com`, `raw.githubusercontent.com`,
    `github.com`, `www.football-data.co.uk`, Google Fonts, cdnjs…; the full list is
    `KNOWN_HOSTS` in `automation/auto_merge.py`) is not a signal, and neither is an HTTP
    library call (`urllib`, `requests`) by itself. A URL to any other host, a computed host
    (`https://{host}/…`) or a URL with embedded credentials goes to the owner. Adding a host
    to the list changes `automation/`, so the owner decides;
  - process or shell execution (`subprocess`, `os.system`, `curl`, `wget`);
  - The Odds API: any line naming it (`odds_api`, `the-odds-api`) or its credit headers
    (`x-requests-*`);
  - **The Odds API budget:** a change to `MAX_CREDITS_PER_RUN`, `MAX_CREDITS_PER_DAY`,
    `UNKNOWN_REMAINING_CAP` or `MORNING_SHARE` that raises the value, a change to `RESERVE`
    that lowers it, a value the gate cannot read as a number, a removed cap, any other changed
    line that uses one of these constants, and any code edit inside `budget()`. Lowering a cap
    (or raising the reserve) passes;
  - paid hosting or deployment targets (Vercel, Netlify, Heroku, AWS, GCP, Azure, Firebase,
    Fly.io, Render, Railway, DigitalOcean, Cloudflare Workers/Pages).

  Identifiers are also split (`remainingCredits`, `extra_usage_credits`) so naming style
  can't dodge the check.
- **Site files (`docs/`)** are checked only for credentials and URLs to new hosts, since text
  on a page can't bill anyone. Site changes otherwise keep auto-merging.
- **Tests (`tests/`)** run only in CI with no secrets, so their content is checked only for
  edits that lower checks: new `skip`/`skipif`/`xfail`, `__test__ = False`, `collect_ignore`,
  `addopts`, and a file that ends up with fewer `test_` functions than before (renaming or
  rewriting a test is fine). Deleting a test file or moving it out of `tests/` also goes to
  the owner.
- **Fail closed:** binary or oversized diffs outside generated data, unknown change types, an
  incomplete file list, or a file count that doesn't match GitHub's all go to the owner.
- **Not scanned:** Markdown and generated outputs (`data/`, `reports/`, `ledger/`,
  `docs/data/`, `docs/dev/`), which are not executed. Their paths are still checked.

Replayed on the diffs of 13 earlier `claude/issue-*` branches (spend gate only, 2026-11-16):
- **Pass:** the docs-only branches for issues #5 and #11.
- **Owner, correctly:** the workflow, prompt and template branches (#1, #3, #8), and every
  data-source or connector branch (#15, #17, #18, #19, #24).
- **Owner, false positive:** the site branches for issues #6, #7 and #27, because each adds the
  `needs_node = pytest.mark.skipif(...)` line used by browser tests. The owner clears these
  with `owner-approved-spend`. (Links to this repository's own GitHub pages are not counted as
  network calls.)

Replayed on recent merged PRs with the #71 rules (spend gate only, 2026-11-18, squash diffs
from `main`):
- **#62 (free ESPN future odds, `claude/issue-61-future-odds`): passes** (before #71: owner,
  for `sbi/sources/` paths and an `urllib` import).
- **#70 (free ESPN club-soccer fixtures, `claude/issue-66-club-soccer-fixtures`): passes**
  (before #71: owner, for `sbi/sources/` paths, ESPN URLs and the word "credits" in a comment).
- #56, #60, #67 and #69 pass, as before.
- #64 (two daily runs) and #55 (daily refresh) still go to the owner, correctly: both change
  `.github/workflows/` and The Odds API budget (#55 raised `MAX_CREDITS_PER_RUN` 12 → 40).
- #59 still goes to the owner for a new `skipif` in a browser test (known false positive).

**What it cannot catch.** A change that raises cost through ordinary-looking logic (for
example, a loop that calls an existing free connector more often, or code that spends
leftover Odds API credits that used to go unused, as #70 does within the unchanged daily
allowance) could pass. The daily and per-run caps and `budget()` are what bound Odds API
spend, which is why any change that loosens them is gated. So could a test edit that weakens an assertion
without skipping it. Running the scheduled job more often needs a `.github/` change, which is
always gated. The existing free-plan setup also limits the damage: The Odds API key is on the
free tier (requests past the quota are refused, not billed), and Actions minutes are free on
a public repository. The owner should keep it that way: no card on The Odds API, usage
credits off on Claude.

**Stricter option.** If that residual risk is not acceptable, set the repository variable
`AUTOMERGE_REQUIRE_LABEL=true`. Then nothing merges until the owner applies
`zero-cost-approved` directly on GitHub after the last push. That is one click per PR instead
of a merge, and it moves the cost judgement fully to the owner. The default is off because
the owner asked for no separate approval on non-payment changes.

## Owner setup (one time, $0)

Nothing here needs a token to be copied or printed.

1. **Merge this PR by hand.** It changes `.github/` and `automation/`, so the gate would never
   merge it, and it was opened before the cutoff anyway.
2. **Create the labels** (Issues → Labels → New label): `owner-approved-spend`,
   `zero-cost-approved`, `automerge-opt-in`, `needs-owner-decision`, `do-not-merge`.
   (The gate can create `needs-owner-decision` itself; creating it first keeps the colour you
   choose.)
3. **Actions permissions** (Settings → Actions → General):
   - "Allow all actions" or at least GitHub-authored actions (`actions/checkout`) stays as now.
   - Workflow permissions: leave the default. The workflow requests exactly what it needs.
   - "Allow GitHub Actions to create and approve pull requests" is **not** needed; leave it off.
4. **Dry run first.** Leave `AUTOMERGE_ENABLED` unset. On the next Claude PR, open the
   `auto-merge` run in the Actions tab and read its summary: it states what it *would* do and
   why. Check one PR that should merge and one that should go to the owner.
5. **Turn it on:** Settings → Secrets and variables → Actions → **Variables** → New repository
   variable `AUTOMERGE_ENABLED` = `true`. (A variable, not a secret.)
6. **Optional strict mode:** variable `AUTOMERGE_REQUIRE_LABEL` = `true`.
7. **Optional hardening (recommended, $0 on a public repo):** a ruleset on `main` that blocks
   force-pushes and deletion. Don't add "Require a pull request" or "Require status checks"
   without a bypass for GitHub Actions: they would block the scheduled data commits (see
   DEVELOPMENT_WORKFLOW.md). Native GitHub "auto-merge" (the PR button) is not used and need
   not be enabled.

**Pause at any time:** set `AUTOMERGE_ENABLED` to anything other than `true`, or disable the
`auto-merge` workflow in the Actions tab. To stop a single PR, add `do-not-merge`.

## Cost of the gate itself

- GitHub Actions is free on public repositories for standard runners. The gate uses
  `ubuntu-latest`, Python's standard library, no `pip install`, and one run takes about
  15 seconds. It runs once per finished `tests` run and once per label change.
- If the repository were made private, those runs would count against the free 2,000
  minutes a month (each run is billed as 1 minute). At ~10 PR pushes and label changes a day
  that would be about 300 minutes a month, still inside the free allowance. Paid minutes need
  a payment method and a spending limit above $0, which this repository does not have.
- No API, service or subscription is involved. No Claude usage: Claude does not poll PRs.

## Relationship to the Claude agents

The stored prompts for the GitHub-triggered agent and the 2-hour scheduled agent say
"NEVER merge a PR, enable auto-merge". That stays correct and was **not** edited (the stored
prompt lives in claude.ai and cannot be changed from this repository). Claude still never
merges: GitHub Actions does, under the rules above, after Claude has opened the PR.
