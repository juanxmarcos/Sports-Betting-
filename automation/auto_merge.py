"""Zero-cost auto-merge gate for Sports Betting Doyen (issue #29).

Run by `.github/workflows/auto-merge.yml` after the `tests` workflow finishes on a pull
request, and when a label changes on a pull request. It decides, from facts fetched fresh
from the GitHub API, whether a pull request may be merged automatically.

Design rules
- Standard library only. It never checks out, imports or runs code from the pull request.
- Fail closed. Anything missing, unknown or unparseable means "do not merge".
- Pull request text (title, body, commit messages) never grants anything. Authority comes
  from: the branch living in this repository, the PR author, the linked issue carrying the
  `ready-for-claude` label, and labels the owner applied directly (not through an app).
- The spend gate cannot prove a change costs nothing. It routes every change that shows a
  real spend signal (billing words, new credentials, new external hosts, higher Odds API
  budget, paid hosting) or touches CI, this policy or dependencies to the owner. All other
  changes are merged once every check is green (unless strict mode is on, see below).
  Owner rule 2026-11-18 (issue #71): "if all requirements are met, auto merge. Same thing
  for deployments." Data connectors under `sbi/sources/` are ordinary code since #71.
- Disabled until the owner sets the repository variable `AUTOMERGE_ENABLED=true`. Until
  then it runs in dry-run mode: it writes its decision to the job summary and changes
  nothing.

The decision logic is the pure function `decide(facts, config)`; `tests/test_auto_merge.py`
exercises it without any network access.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

# ---------------------------------------------------------------------------------------
# Policy (changing anything here is itself a protected change: `automation/` is gated)
# ---------------------------------------------------------------------------------------
REPOSITORY = "juanxmarcos/Sports-Betting-"
OWNER = "juanxmarcos"
TRUSTED_PR_AUTHORS = frozenset({OWNER})
BASE_BRANCH = "main"
BRANCH_RE = re.compile(r"^claude/issue-(\d+)-[a-z0-9][a-z0-9._-]*$")
ISSUE_REF_RE = re.compile(r"\b(?:closes|fixes|resolves|part of)\s+#(\d+)\b", re.IGNORECASE)

AUTH_LABEL = "ready-for-claude"            # on the linked issue (collaborators only)
SPEND_APPROVAL_LABEL = "owner-approved-spend"  # owner approves a spend-gated PR
ZERO_COST_LABEL = "zero-cost-approved"     # strict mode: owner approves each PR
OPT_IN_LABEL = "automerge-opt-in"          # owner opts in a PR opened before the cutoff
NEEDS_OWNER_LABEL = "needs-owner-decision"  # set by this gate on spend-gated PRs
HOLD_LABELS = frozenset({"do-not-merge", "hold"})

# Pull requests opened before this instant are never merged automatically unless the owner
# applies OPT_IN_LABEL. This keeps the rollout from merging the PRs already open.
ROLLOUT_CUTOFF = datetime(2026, 11, 17, 0, 0, tzinfo=timezone.utc)

REQUIRED_CHECKS = frozenset({"pytest"})    # job name in .github/workflows/tests.yml
SELF_CHECK_NAMES = frozenset({"auto-merge-gate"})  # this gate's own job
OK_CONCLUSIONS = frozenset({"success", "neutral", "skipped"})
MERGEABLE_STATES = frozenset({"clean", "unstable", "has_hooks"})  # we verify checks ourselves

# Any change touching these paths (old or new path of a rename) needs the owner.
PROTECTED_PATTERNS = (
    ".github/*",                    # CI, workflows, this policy's workflow, PR template
    "automation/*",                 # agent prompts and this gate
    "requirements*.txt", "*/requirements*.txt", "constraints*.txt",
    "pyproject.toml", "setup.py", "setup.cfg", "Pipfile", "Pipfile.lock", "poetry.lock",
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "pytest.ini", "tox.ini", "conftest.py", "*/conftest.py", ".coveragerc",
    ".env*", "*/.env*", "*.pem", "*.key",
    "Dockerfile", "docker-compose*", "vercel.json", "netlify.toml", "Procfile",
    "CNAME", "*/CNAME", "app.yaml", "fly.toml", "render.yaml",
    "now.json", "app.json", "wrangler.toml", "serverless.yml", "serverless.yaml",
    "firebase.json", ".firebaserc", "amplify.yml", "railway.json", "railway.toml",
    "cloudbuild.yaml", "azure-pipelines.yml", "*.tf", "*.tfvars", "*/.vercel/*", ".vercel/*",
    ".gitattributes", ".gitmodules", ".gitignore",
)

# Generated outputs and prose: not executed, so their *content* is not scanned. Their paths
# are still checked above. (Binary files here, like data/sbi.sqlite, are allowed.)
CONTENT_EXEMPT_PATTERNS = (
    "*.md", "data/*", "reports/*", "ledger/*", "docs/data/*", "docs/dev/*",
)
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp")

# Main may move on after the tests ran. Only commits that touch these (the scheduled data
# job's output) are tolerated; any other change on main means the PR must merge main first.
BOT_DATA_PATTERNS = ("data/*", "reports/*", "ledger/*", "docs/data/*", "docs/dev/*")

# Content signals, checked on added AND removed lines (removing a guard can raise spend).
# Issue #71: only real spend signals. A URL to a host the project already uses is not one.
SPEND_SIGNALS = (
    # Billing words: flagged anywhere, comments included.
    ("money or billing", r"\b(billing|billed|invoice\w*|subscri(be|bed|bes|bing|ption\w*)|"
                         r"paid[ _-]?(plan|tier|api|service|account|version|subscription)s?|"
                         r"pricing[ _-]?(tier|plan)s?|premium[ _-]?(plan|tier|account)s?|metered|"
                         r"overage\w*|payment\w*|checkout|stripe|paypal|credit[ _-]?cards?|"
                         r"purchas\w*|upgrad(e|es|ed|ing))\b"),
    ("credentials or secrets", r"(secrets\.|\bsecret\b|api[_-]?key|apikey|access[_-]?token|"
                               r"\btoken\b|authorization|bearer\s|password|client[_-]?secret|"
                               r"os\.environ|getenv|process\.env)"),
    ("process or shell execution", r"(\bsubprocess\b|os\.system|os\.popen|\bcurl\b|\bwget\b)"),
    ("Odds API call or credit accounting", r"(odds[_-]?api|the-odds-api|x-requests)"),
    ("paid hosting or deployment target", r"\b(vercel|netlify|heroku\w*|amazonaws|aws|gcp|gcloud|"
                                          r"google[ _-]?cloud|cloud\.google|azure\w*|firebase\w*|"
                                          r"fly\.io|flyctl|render\.com|railway|digitalocean|"
                                          r"cloudflare[ _-]?(workers|pages)|wrangler)\b"),
)
# Metering words: flagged in code only (the part of a line before a # or // comment), so a
# comment explaining how credits are shared is not a signal but `credits_used += 3` is.
METERING_SIGNAL = ("metered usage in code", re.compile(
    r"\b(costs?|credits?|quota\w*|spend\w*|usage[ _-]?(credits|based)|bill(s)?|buy(ing)?)\b", re.IGNORECASE))

# Hosts the project already uses (code and site on main, 2026-11-18) plus free public
# endpoints. URLs to any other host, with a placeholder host, or with credentials in the URL
# go to the owner. Exact host names only: no wildcard subdomains.
KNOWN_HOSTS = frozenset({
    # this project
    "github.com", "juanxmarcos.github.io", "raw.githubusercontent.com", "localhost", "127.0.0.1",
    # free public data and site assets
    "site.api.espn.com", "site.web.api.espn.com", "sports.core.api.espn.com", "www.espn.com",
    "espnpressroom.com", "www.football-data.co.uk", "football-data.co.uk", "huggingface.co",
    "fonts.googleapis.com", "fonts.gstatic.com", "cdnjs.cloudflare.com", "creativecommons.org",
    "claude.ai",
    # The Odds API: its spend is governed by the budget constants below and the
    # "Odds API call or credit accounting" signal, not by the host name.
    "api.the-odds-api.com", "the-odds-api.com",
    # reference links already in the code (documentation and press, not fetched)
    "bettingdataapi.com", "cdcgaming.com", "developer.opticodds.com", "docs.kalshi.com",
    "docs.polymarket.com", "docs.smarkets.com", "entreprise.pmu.fr", "europeangaming.eu",
    "flutter.com", "footballanalytics.pro", "gamingandco.substack.com", "group.banijay.com",
    "igamingbusiness.com", "igamingfuture.com", "kansspelautoriteit.nl", "lgcb.dps.louisiana.gov",
    "live.euronext.com", "mfn.se", "polymarket.com", "rubypayeur.com", "sbcamericas.com",
    "sbcnews.co.uk", "skorbot.live", "sportsapis.dev", "sportsgameodds.com",
    "support.developer.betfair.com", "theopenmodel.com", "www.betssonab.com",
    "www.boardroomalpha.com", "www.evokeplc.com", "www.fdjunited.com", "www.fox2detroit.com",
    "www.gambling.com", "www.gamblingcommission.gov.uk", "www.inderes.fi",
    "www.legalsportsreport.com", "www.lobbyregister.bundestag.de", "www.pinnacle.com", "www.sec.gov",
})
URL_RE = re.compile(r"\b(?:https?|wss?|ftp)://([^/?#\s\"'<>)`\]]*)", re.IGNORECASE)
HOST_RE = re.compile(r"^[a-z0-9.-]+$")

# The Odds API budget (sbi/sources/odds_api.py). Direction +1: a higher value spends more;
# -1: a lower value spends more (the reserve kept back). Any change that raises spend, any
# change whose direction cannot be read, and any edit inside budget() goes to the owner.
BUDGET_CONSTANTS = {"MAX_CREDITS_PER_RUN": 1, "MAX_CREDITS_PER_DAY": 1, "UNKNOWN_REMAINING_CAP": 1,
                    "MORNING_SHARE": 1, "RESERVE": -1}
BUDGET_FUNCTIONS = frozenset({"budget"})
_CONST_RE = re.compile(r"\b(" + "|".join(BUDGET_CONSTANTS) + r")\b")
_ASSIGN_RE = re.compile(r"^\s*(?:[A-Za-z_][\w.]*\.)?(" + "|".join(BUDGET_CONSTANTS) +
                        r")\s*(?::[^=]+)?=(?!=)\s*([^#]*?)\s*(?:#.*)?$")
_TOPLEVEL_DEF_RE = re.compile(r"^(?:async\s+)?def\s+(\w+)")
_HUNK_RE = re.compile(r"^@@[^@]*@@\s?(.*)$")
TEST_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+(test_\w+)")

OWN_URL_RE = re.compile(r"https://(github\.com/juanxmarcos/Sports-Betting-|"
                        r"juanxmarcos\.github\.io/Sports-Betting-)(?=[/\"'#)\s]|$)[^\s\"'<>)]*")
TEST_WEAKENING = re.compile(
    r"(pytest\.mark\.(skip|skipif|xfail)|pytest\.(skip|xfail|importorskip)\s*\(|unittest\.skip|"
    r"__test__\s*=\s*False|collect_ignore|addopts|-p\s+no:)")
_SPEND_RES = tuple((name, re.compile(rx, re.IGNORECASE)) for name, rx in SPEND_SIGNALS)

# Which content signals apply where. Tests run only in CI (no secrets, nothing billed), so
# only check-lowering edits matter there. Site files can only cost money by calling out to
# an external host or embedding a credential, so prose about money is not flagged there.
SITE_SIGNALS = frozenset({"credentials or secrets"})


def _signals_for(path: str):
    """(word signals, check metering words, check URL hosts) for a path."""
    if path.startswith("tests/"):
        return (), False, False
    if path.startswith("docs/"):
        return tuple((n, rx) for n, rx in _SPEND_RES if n in SITE_SIGNALS), False, True
    return _SPEND_RES, True, True


def url_flags(text: str) -> list[str]:
    """Reasons a line's URLs need the owner: unknown host, placeholder host or credentials."""
    out = []
    for m in URL_RE.finditer(text):
        authority = m.group(1)
        if "@" in authority:
            out.append("credentials embedded in a URL")
            continue
        host = authority.lower().rsplit(":", 1)[0] if authority.count(":") == 1 else authority.lower()
        host = host.rstrip(".")
        if not host or not HOST_RE.match(host):
            out.append("URL with an unreadable or computed host")
        elif host not in KNOWN_HOSTS:
            out.append(f"new external host {host}")
    return out


def _code_part(line: str) -> str:
    """The line before a trailing # or // comment (a rough cut; strings with # are rare)."""
    for marker in ("#", "//"):
        i = line.find(marker)
        if i >= 0 and not line[max(0, i - 1):i + 3].startswith((":/", "://")):
            line = line[:i]
    return line


def _num(value: str):
    try:
        return float(value.replace("_", ""))
    except ValueError:
        return None


def budget_flags(path: str, patch: str) -> list[str]:
    """Flags for edits that could raise The Odds API spend (issue #71)."""
    flags: list[str] = []
    old: dict[str, list] = {}
    new: dict[str, list] = {}
    func = None
    for line in patch.splitlines():
        if line.startswith(("+++", "---")):
            continue
        h = _HUNK_RE.match(line)
        if h:
            d = _TOPLEVEL_DEF_RE.match(h.group(1))
            func = d.group(1) if d else None
            continue
        if not line[:1] in {"+", "-", " "}:
            continue
        body = line[1:]
        if body[:1].strip() and not body.startswith(("#", ")", "]", "}")):
            d = _TOPLEVEL_DEF_RE.match(body)  # a top-level statement ends the current function
            func = d.group(1) if d else None
        if line[0] == " " or not body.strip():
            continue
        if func in BUDGET_FUNCTIONS and _code_part(body).strip():
            flags.append(f"{path}: {func}() changed (Odds API budget formula: owner decides)")
        a = _ASSIGN_RE.match(body)
        if a:
            (new if line[0] == "+" else old).setdefault(a.group(1), []).append(_num(a.group(2)))
        elif _CONST_RE.search(_code_part(body)):
            flags.append(f"{path}: use of {_CONST_RE.search(_code_part(body)).group(1)} changed "
                         "(Odds API budget: owner decides)")
    for name in sorted(old.keys() | new.keys()):
        o, n, sign = old.get(name, []), new.get(name, []), BUDGET_CONSTANTS[name]
        if not n:
            flags.append(f"{path}: {name} removed (Odds API budget cap)")
        elif not o:
            flags.append(f"{path}: {name} set (Odds API budget cap: owner decides)")
        elif None in o or None in n:
            flags.append(f"{path}: {name} changed to a value the gate cannot read")
        elif (sign > 0 and max(n) > min(o)) or (sign < 0 and min(n) < max(o)):
            flags.append(f"{path}: {name} raises Odds API spend ({min(o) if sign > 0 else max(o):g} -> "
                         f"{max(n) if sign > 0 else min(n):g})")
    return flags


MERGE, OWNER_DECISION, WAIT, SKIP = "merge", "owner", "wait", "skip"


@dataclass
class Config:
    enabled: bool = False          # repository variable AUTOMERGE_ENABLED == "true"
    require_label: bool = False    # repository variable AUTOMERGE_REQUIRE_LABEL == "true"


@dataclass
class Decision:
    action: str
    reasons: list[str] = field(default_factory=list)
    spend_flags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------------------
def parse_time(value) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else None


def _match(path: str, patterns) -> bool:
    return any(fnmatch.fnmatchcase(path, p) for p in patterns)


def owner_applied_label(label: str, current_labels, label_events, not_before) -> bool:
    """True only if `label` is on the PR now, and its most recent `labeled` event was made by
    the owner directly (not through a GitHub App such as an AI agent's connector) at or after
    `not_before` (when the current head commit was first checked). Fail closed."""
    if label not in current_labels or not_before is None:
        return False
    latest = None
    for ev in label_events or ():
        if ev.get("event") == "labeled" and (ev.get("label") or {}).get("name") == label:
            t = parse_time(ev.get("created_at"))
            if t is None:
                return False
            if latest is None or t >= latest[0]:
                latest = (t, ev)
    if latest is None:
        return False
    t, ev = latest
    actor = (ev.get("actor") or {}).get("login")
    return actor == OWNER and ev.get("performed_via_github_app") is None and t >= not_before


def classify_files(files, expected_count) -> list[str]:
    """Return the reasons a change set needs the owner (empty list = no spend signal found).
    This is a conservative router, not a proof that a change costs nothing."""
    flags: list[str] = []
    if not isinstance(files, list) or expected_count is None or len(files) != expected_count:
        return ["changed-file list incomplete or unreadable (fail closed)"]
    if not files:
        return ["pull request changes no files (fail closed)"]
    for f in files:
        path = f.get("filename")
        status = f.get("status")
        prev = f.get("previous_filename")
        if not isinstance(path, str) or not path:
            flags.append("file without a name (fail closed)")
            continue
        if status not in {"added", "modified", "removed", "renamed", "copied", "changed"}:
            flags.append(f"{path}: unknown change type {status!r} (fail closed)")
            continue
        for p in filter(None, (path, prev)):
            if _match(p, PROTECTED_PATTERNS):
                flags.append(f"{p}: protected path (CI, policy, dependencies, connectors or deployment)")
        if (status == "removed" and path.startswith("tests/")) or (
                prev and prev.startswith("tests/") and not path.startswith("tests/")):
            flags.append(f"{prev or path}: test file removed or moved out of tests/ (could lower checks)")
        if status == "removed":
            continue  # deleted content cannot run; path rules above still apply
        if _match(path, CONTENT_EXEMPT_PATTERNS) and (prev is None or _match(prev, CONTENT_EXEMPT_PATTERNS)):
            continue
        patch = f.get("patch")
        if patch is None:
            if path.lower().endswith(IMAGE_EXTENSIONS) and (prev is None or prev.lower().endswith(IMAGE_EXTENSIONS)):
                continue
            if status == "renamed" and f.get("changes", 1) == 0:
                continue  # pure rename, path rules above already applied
            flags.append(f"{path}: binary or too-large diff cannot be inspected (fail closed)")
            continue
        signals, metering, hosts = _signals_for(path)
        if not path.startswith(("tests/", "docs/")):
            flags.extend(budget_flags(path, patch))
        removed_tests, added_tests = set(), set()
        for line in patch.splitlines():
            if line.startswith(("+++", "---")) or not line[:1] in {"+", "-"}:
                continue
            kind = "added" if line[0] == "+" else "removed"
            body = OWN_URL_RE.sub("", line[1:])  # links to this repository cost nothing
            # Also scan with identifiers split (remaining_credits, apiCost -> words) so word
            # boundaries cannot be dodged by naming style.
            split = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", body).replace("_", " ")
            for name, rx in signals:
                if rx.search(body) or rx.search(split):
                    flags.append(f"{path}: {name} ({kind} line)")
            if metering:
                code = _CONST_RE.sub("", _code_part(body))  # budget constants: budget_flags()
                code_split = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", code).replace("_", " ")
                if METERING_SIGNAL[1].search(code) or METERING_SIGNAL[1].search(code_split):
                    flags.append(f"{path}: {METERING_SIGNAL[0]} ({kind} line)")
            if hosts and line[0] == "+":
                flags.extend(f"{path}: {why} (added line)" for why in url_flags(body))
            if path.startswith("tests/"):
                t = TEST_DEF_RE.match(body)
                if t:
                    (added_tests if line[0] == "+" else removed_tests).add(t.group(1))
                if line[0] == "+" and TEST_WEAKENING.search(body):
                    flags.append(f"{path}: skips or disables tests (could lower checks)")
        gone, new_tests = removed_tests - added_tests, added_tests - removed_tests
        if len(gone) > len(new_tests):  # renaming or rewriting a test is fine; fewer tests is not
            flags.append(f"{path}: {len(gone) - len(new_tests)} test function(s) deleted, e.g. "
                         f"{sorted(gone)[0]} (could lower checks)")
    return sorted(set(flags))


def evaluate_checks(check_runs, combined_status) -> tuple[str, list[str]]:
    """Return (MERGE|WAIT|SKIP, reasons) for the head commit's checks."""
    if not isinstance(check_runs, list):
        return SKIP, ["check runs unreadable (fail closed)"]
    latest: dict[str, dict] = {}
    for run in check_runs:
        name = run.get("name")
        if not name or name in SELF_CHECK_NAMES:
            continue
        t = parse_time(run.get("started_at")) or datetime.min.replace(tzinfo=timezone.utc)
        if name not in latest or t >= (parse_time(latest[name].get("started_at"))
                                       or datetime.min.replace(tzinfo=timezone.utc)):
            latest[name] = run
    missing = sorted(REQUIRED_CHECKS - latest.keys())
    if missing:
        return WAIT, [f"required check not reported yet: {', '.join(missing)}"]
    waiting, failing = [], []
    for name, run in sorted(latest.items()):
        if run.get("status") != "completed":
            waiting.append(name)
        elif run.get("conclusion") not in OK_CONCLUSIONS:
            failing.append(f"{name}={run.get('conclusion')}")
    for name in REQUIRED_CHECKS:
        if latest[name].get("status") == "completed" and latest[name].get("conclusion") != "success":
            failing.append(f"{name} must succeed")
    if not isinstance(combined_status, dict):
        return SKIP, ["commit status unreadable (fail closed)"]
    if combined_status.get("total_count", 0):
        state = combined_status.get("state")
        if state == "pending":
            waiting.append("commit statuses")
        elif state != "success":
            failing.append(f"commit statuses={state}")
    if failing:
        return SKIP, ["checks not green: " + ", ".join(sorted(set(failing)))]
    if waiting:
        return WAIT, ["checks still running: " + ", ".join(waiting)]
    return MERGE, []


def first_check_time(check_runs) -> datetime | None:
    """Earliest server-side start time of any check on the head commit: a lower bound for
    when that commit was pushed. Owner labels must be applied after it."""
    times = [parse_time(r.get("started_at")) for r in check_runs or () if r.get("name") not in SELF_CHECK_NAMES]
    times = [t for t in times if t]
    return min(times) if times else None


def decide(facts: dict, config: Config) -> Decision:
    """Decide what to do with one pull request. `facts` keys:
    pr, files, issue, label_events, check_runs, combined_status, base_drift_files."""
    pr = facts.get("pr") or {}
    reasons: list[str] = []

    # 1. Authorization (silent skip: outsiders get no reaction)
    head, base = pr.get("head") or {}, pr.get("base") or {}
    if pr.get("state") != "open" or pr.get("merged"):
        return Decision(SKIP, ["pull request is not open"])
    if (head.get("repo") or {}).get("full_name") != REPOSITORY or (base.get("repo") or {}).get("full_name") != REPOSITORY:
        return Decision(SKIP, ["head or base is not this repository (forks are never merged)"])
    if base.get("ref") != BASE_BRANCH:
        return Decision(SKIP, [f"base branch is not {BASE_BRANCH}"])
    if (pr.get("user") or {}).get("login") not in TRUSTED_PR_AUTHORS:
        return Decision(SKIP, ["pull request author is not trusted"])
    m = BRANCH_RE.match(head.get("ref") or "")
    if not m:
        return Decision(SKIP, ["branch is not claude/issue-<N>-<description>"])
    issue_no = int(m.group(1))
    refs = {int(n) for n in ISSUE_REF_RE.findall(pr.get("body") or "")}
    if issue_no not in refs:
        return Decision(SKIP, [f"PR body does not reference #{issue_no} with Closes/Part of"])
    issue = facts.get("issue") or {}
    if issue.get("number") != issue_no or issue.get("pull_request") is not None:
        return Decision(SKIP, [f"#{issue_no} is not an issue in this repository"])
    if (issue.get("user") or {}).get("login") != OWNER or issue.get("state") != "open":
        return Decision(SKIP, [f"issue #{issue_no} is not an open issue by {OWNER}"])
    if AUTH_LABEL not in {lb.get("name") for lb in issue.get("labels") or ()}:
        return Decision(SKIP, [f"issue #{issue_no} does not carry {AUTH_LABEL}"])

    labels = {lb.get("name") for lb in pr.get("labels") or ()}
    if labels & HOLD_LABELS:
        return Decision(SKIP, ["hold label present"])
    if pr.get("draft"):
        return Decision(SKIP, ["draft pull request"])

    check_runs = facts.get("check_runs")
    pushed = first_check_time(check_runs)
    events = facts.get("label_events")

    # 2. Rollout cutoff
    created = parse_time(pr.get("created_at"))
    if created is None:
        return Decision(SKIP, ["creation time unreadable (fail closed)"])
    if created < ROLLOUT_CUTOFF and not owner_applied_label(OPT_IN_LABEL, labels, events, pushed):
        return Decision(SKIP, [f"opened before the rollout cutoff; owner can opt in with {OPT_IN_LABEL}"])

    # 3. Spend gate (owner decides; this gate never approves spending)
    flags = classify_files(facts.get("files"), pr.get("changed_files"))
    if flags and not owner_applied_label(SPEND_APPROVAL_LABEL, labels, events, pushed):
        return Decision(OWNER_DECISION, ["possible cost, credential, CI or policy impact: owner decides"], flags)
    if config.require_label and not owner_applied_label(ZERO_COST_LABEL, labels, events, pushed):
        return Decision(SKIP, [f"strict mode: waiting for the owner's {ZERO_COST_LABEL} label"], flags)

    # 4. Checks
    state, why = evaluate_checks(check_runs, facts.get("combined_status"))
    if state != MERGE:
        return Decision(state, why, flags)

    # 5. Mergeability against the latest base
    if pr.get("mergeable") is None or pr.get("mergeable_state") == "unknown":
        return Decision(WAIT, ["GitHub has not computed mergeability yet"], flags)
    if pr.get("mergeable") is not True or pr.get("mergeable_state") not in MERGEABLE_STATES:
        return Decision(SKIP, [f"not mergeable (state {pr.get('mergeable_state')!r})"], flags)
    drift = facts.get("base_drift_files")
    if not isinstance(drift, list):
        return Decision(SKIP, ["could not compare with main (fail closed)"], flags)
    code_drift = sorted(p for p in drift if not isinstance(p, str) or not _match(p, BOT_DATA_PATTERNS))
    if code_drift:
        return Decision(SKIP, ["main has code changes the tests did not cover; merge main into the branch: "
                               + ", ".join(map(str, code_drift[:5]))], flags)

    reasons.append("all gates passed")
    return Decision(MERGE, reasons, flags)


# ---------------------------------------------------------------------------------------
# GitHub API (only used inside the workflow)
# ---------------------------------------------------------------------------------------
class GitHub:
    def __init__(self, token: str, repo: str):
        self.token, self.repo = token, repo

    def request(self, method: str, path: str, body=None):
        url = path if path.startswith("https://") else f"https://api.github.com/repos/{self.repo}/{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "doyen-auto-merge-gate",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = resp.read()
            return json.loads(payload) if payload else None, resp.headers.get("Link", "")

    def get(self, path: str):
        return self.request("GET", path)[0]

    def paginate(self, path: str, key: str | None = None, limit: int = 3000) -> list:
        out: list = []
        sep = "&" if "?" in path else "?"
        url = f"{path}{sep}per_page=100"
        while url and len(out) < limit:
            data, link = self.request("GET", url)
            out.extend(data[key] if key else data)
            nxt = re.search(r'<([^>]+)>;\s*rel="next"', link or "")
            url = nxt.group(1) if nxt else None
        return out


def gather(gh: GitHub, number: int) -> dict:
    pr = gh.get(f"pulls/{number}")
    for _ in range(3):  # GitHub computes mergeability lazily
        if pr.get("mergeable") is not None:
            break
        time.sleep(5)
        pr = gh.get(f"pulls/{number}")
    facts: dict = {"pr": pr}
    m = BRANCH_RE.match((pr.get("head") or {}).get("ref") or "")
    if m:
        try:
            facts["issue"] = gh.get(f"issues/{int(m.group(1))}")
        except urllib.error.HTTPError:
            facts["issue"] = None
    sha = pr["head"]["sha"]
    facts["files"] = gh.paginate(f"pulls/{number}/files")
    facts["label_events"] = gh.paginate(f"issues/{number}/events")
    facts["check_runs"] = gh.paginate(f"commits/{sha}/check-runs?filter=all", key="check_runs")
    facts["combined_status"] = gh.get(f"commits/{sha}/status")
    try:
        cmp = gh.get(f"compare/{sha}...{BASE_BRANCH}")
        files = cmp.get("files")
        # The compare API lists at most 300 files; a full page means we cannot see everything.
        facts["base_drift_files"] = None if files is None or len(files) >= 300 else [f.get("filename") for f in files]
    except urllib.error.HTTPError:
        facts["base_drift_files"] = None
    return facts


def pr_numbers_from_event(gh: GitHub, event_name: str, event: dict) -> list[int]:
    if event_name == "pull_request_target":
        return [int(event["pull_request"]["number"])]
    if event_name == "workflow_run":
        run = event.get("workflow_run") or {}
        if run.get("conclusion") != "success" or run.get("event") != "pull_request":
            return []
        nums = [int(p["number"]) for p in run.get("pull_requests") or ()]
        if not nums and run.get("head_sha"):
            pulls = gh.get(f"commits/{run['head_sha']}/pulls") or []
            nums = [int(p["number"]) for p in pulls if p.get("state") == "open"]
        return nums
    return []


def act(gh: GitHub, number: int, facts: dict, decision: Decision, config: Config) -> str:
    pr = facts["pr"]
    if not config.enabled:
        return "dry run (AUTOMERGE_ENABLED is not true): nothing changed"
    footer = "\n\n---\n_Posted by the zero-cost auto-merge gate (`.github/workflows/auto-merge.yml`, issue #29)._"
    if decision.action == MERGE:
        gh.request("PUT", f"pulls/{number}/merge", {
            "merge_method": "squash", "sha": pr["head"]["sha"],
            "commit_title": f"{pr.get('title', '').strip()} (#{number})"[:250],
        })
        gh.request("POST", f"issues/{number}/comments", {"body": (
            "Merged automatically: trusted branch, `ready-for-claude` issue, no spend signal found, "
            f"all checks green at `{pr['head']['sha'][:7]}`. The spend gate is a conservative filter, "
            "not a proof of zero cost." + footer)})
        return "merged"
    if decision.action == OWNER_DECISION:
        labels = {lb.get("name") for lb in pr.get("labels") or ()}
        if NEEDS_OWNER_LABEL in labels:
            return "already flagged for the owner"
        gh.request("POST", f"issues/{number}/labels", {"labels": [NEEDS_OWNER_LABEL]})
        listed = "\n".join(f"- {f}" for f in decision.spend_flags[:40])
        more = f"\n- … and {len(decision.spend_flags) - 40} more" if len(decision.spend_flags) > 40 else ""
        gh.request("POST", f"issues/{number}/comments", {"body": (
            "**Not merged automatically: owner decision needed.** This change may affect cost, "
            "credentials, external services, CI or the merge policy itself:\n\n" + listed + more +
            f"\n\nThe owner can merge it by hand, or apply `{SPEND_APPROVAL_LABEL}` directly on GitHub "
            "(not through an app) after the last push; the gate then merges once checks are green." + footer)})
        return "flagged for the owner"
    return "no action"


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or repo != REPOSITORY:
        print("auto-merge gate: missing token or wrong repository; nothing done")
        return 0
    config = Config(enabled=os.environ.get("AUTOMERGE_ENABLED", "").strip().lower() == "true",
                    require_label=os.environ.get("AUTOMERGE_REQUIRE_LABEL", "").strip().lower() == "true")
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as fh:
        event = json.load(fh)
    gh = GitHub(token, repo)
    lines = [f"## Auto-merge gate ({'enabled' if config.enabled else 'dry run'}"
             f"{', strict' if config.require_label else ''})", ""]
    for number in pr_numbers_from_event(gh, os.environ.get("GITHUB_EVENT_NAME", ""), event):
        facts = gather(gh, number)
        decision = decide(facts, config)
        outcome = act(gh, number, facts, decision, config)
        lines.append(f"### PR #{number}: {decision.action} → {outcome}")
        lines += [f"- {r}" for r in decision.reasons]
        if decision.spend_flags:
            lines.append("- spend-gate signals:")
            lines += [f"  - {f}" for f in decision.spend_flags[:60]]
        lines.append("")
    text = "\n".join(lines)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
