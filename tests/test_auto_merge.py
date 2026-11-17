"""Tests for the zero-cost auto-merge gate (issue #29). No network access."""
import copy
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("auto_merge", ROOT / "automation" / "auto_merge.py")
am = importlib.util.module_from_spec(_spec)
sys.modules["auto_merge"] = am
_spec.loader.exec_module(am)

REPO = {"full_name": "juanxmarcos/Sports-Betting-"}
SHA = "a" * 40


def good_facts():
    return {
        "pr": {
            "number": 40, "state": "open", "merged": False, "draft": False,
            "title": "Tidy parlay card spacing",
            "body": "## Linked issue\nCloses #39\n",
            "user": {"login": "juanxmarcos"},
            "head": {"ref": "claude/issue-39-card-spacing", "sha": SHA, "repo": REPO},
            "base": {"ref": "main", "repo": REPO},
            "labels": [], "created_at": "2026-11-18T10:00:00Z",
            "changed_files": 2, "mergeable": True, "mergeable_state": "clean",
        },
        "issue": {"number": 39, "state": "open", "user": {"login": "juanxmarcos"},
                  "labels": [{"name": "ready-for-claude"}]},
        "files": [
            {"filename": "docs/assets/doyen.css", "status": "modified", "changes": 2,
             "patch": "@@ -1 +1 @@\n-.card{margin:4px}\n+.card{margin:8px}"},
            {"filename": "sbi/parlays.py", "status": "modified", "changes": 2,
             "patch": "@@ -10 +10 @@\n-    gap = 1\n+    gap = 2"},
        ],
        "label_events": [],
        "check_runs": [{"name": "pytest", "status": "completed", "conclusion": "success",
                        "started_at": "2026-11-18T10:01:00Z"}],
        "combined_status": {"state": "pending", "total_count": 0},
        "base_drift_files": ["data/sbi.sqlite", "reports/latest.md", "docs/data/doyen.json"],
    }


def owner_label(name, at="2026-11-18T11:00:00Z", actor="juanxmarcos", app=None):
    return {"event": "labeled", "label": {"name": name}, "actor": {"login": actor},
            "performed_via_github_app": app, "created_at": at}


def with_label(facts, name, **kw):
    facts["pr"]["labels"].append({"name": name})
    facts["label_events"].append(owner_label(name, **kw))
    return facts


def decide(facts, **cfg):
    return am.decide(facts, am.Config(**cfg))


# --- positive ---------------------------------------------------------------------------
def test_eligible_zero_cost_pr_merges():
    d = decide(good_facts())
    assert d.action == am.MERGE, d.reasons
    assert d.spend_flags == []


def test_part_of_reference_and_bot_only_drift_still_merge():
    f = good_facts()
    f["pr"]["body"] = "Part of #39"
    f["base_drift_files"] = ["ledger/recommendations.csv", "data/tuned.json"]
    assert decide(f).action == am.MERGE


def test_images_and_generated_data_need_no_content_scan():
    f = good_facts()
    f["files"].append({"filename": "data/sbi.sqlite", "status": "modified", "changes": 0})
    f["files"].append({"filename": "docs/img/shot.png", "status": "added", "changes": 0})
    f["files"].append({"filename": "docs/METHODOLOGY.md", "status": "modified", "changes": 1,
                       "patch": "@@ -1 +1 @@\n+Costs: see https://example.com pricing"})
    f["pr"]["changed_files"] = 5
    assert decide(f).action == am.MERGE


def test_owner_spend_approval_after_last_push_allows_merge():
    f = good_facts()
    f["files"][1]["patch"] += "\n+    API_KEY = os.environ['NEW_PAID_KEY']"
    assert decide(f).action == am.OWNER_DECISION
    assert decide(with_label(f, am.SPEND_APPROVAL_LABEL)).action == am.MERGE


def test_strict_mode_needs_zero_cost_label():
    f = good_facts()
    assert decide(f, require_label=True).action == am.SKIP
    assert decide(with_label(f, am.ZERO_COST_LABEL), require_label=True).action == am.MERGE


# --- negative: authorization ------------------------------------------------------------
@pytest.mark.parametrize("mutate, why", [
    (lambda f: f["pr"]["head"].update(repo={"full_name": "attacker/Sports-Betting-"}), "fork"),
    (lambda f: f["pr"]["user"].update(login="stranger"), "author"),
    (lambda f: f["pr"]["head"].update(ref="feature/issue-39-x"), "branch"),
    (lambda f: f["pr"]["head"].update(ref="claude/issue-39"), "branch"),
    (lambda f: f["pr"]["base"].update(ref="dev"), "base"),
    (lambda f: f["pr"].update(body="Closes #12"), "reference"),
    (lambda f: f["pr"].update(body=None), "reference"),
    (lambda f: f["issue"].update(labels=[]), "label"),
    (lambda f: f["issue"].update(user={"login": "stranger"}), "issue author"),
    (lambda f: f["issue"].update(state="closed"), "issue closed"),
    (lambda f: f["issue"].update(pull_request={"url": "x"}), "issue is a PR"),
    (lambda f: f.update(issue=None), "issue missing"),
    (lambda f: f["pr"].update(draft=True), "draft"),
    (lambda f: f["pr"].update(state="closed"), "closed"),
    (lambda f: f["pr"]["labels"].append({"name": "do-not-merge"}), "hold"),
])
def test_unauthorized_or_ineligible_prs_are_skipped(mutate, why):
    f = good_facts()
    mutate(f)
    assert decide(f).action == am.SKIP, why


def test_pre_cutoff_pr_needs_owner_opt_in():
    f = good_facts()
    f["pr"]["created_at"] = "2026-11-16T12:00:00Z"
    assert decide(f).action == am.SKIP
    assert decide(with_label(f, am.OPT_IN_LABEL)).action == am.MERGE


# --- negative: checks and mergeability --------------------------------------------------
@pytest.mark.parametrize("runs, expected", [
    ([], am.WAIT),
    ([{"name": "pytest", "status": "in_progress", "started_at": "2026-11-18T10:01:00Z"}], am.WAIT),
    ([{"name": "pytest", "status": "completed", "conclusion": "failure", "started_at": "2026-11-18T10:01:00Z"}], am.SKIP),
    ([{"name": "pytest", "status": "completed", "conclusion": "skipped", "started_at": "2026-11-18T10:01:00Z"}], am.SKIP),
    ([{"name": "pytest", "status": "completed", "conclusion": "success", "started_at": "2026-11-18T10:01:00Z"},
      {"name": "other", "status": "completed", "conclusion": "failure", "started_at": "2026-11-18T10:01:00Z"}], am.SKIP),
    ([{"name": "pytest", "status": "completed", "conclusion": "failure", "started_at": "2026-11-18T10:01:00Z"},
      {"name": "pytest", "status": "completed", "conclusion": "success", "started_at": "2026-11-18T10:09:00Z"}], am.MERGE),
    (None, am.SKIP),
])
def test_checks_must_all_be_green(runs, expected):
    f = good_facts()
    f["check_runs"] = runs
    assert decide(f).action == expected


def test_own_gate_job_is_ignored_and_statuses_count():
    f = good_facts()
    f["check_runs"].append({"name": "auto-merge-gate", "status": "in_progress", "started_at": "2026-11-18T10:02:00Z"})
    assert decide(f).action == am.MERGE
    f["combined_status"] = {"state": "failure", "total_count": 1}
    assert decide(f).action == am.SKIP
    f["combined_status"] = {"state": "pending", "total_count": 1}
    assert decide(f).action == am.WAIT


@pytest.mark.parametrize("mergeable, state, expected", [
    (False, "dirty", am.SKIP), (True, "blocked", am.SKIP), (True, "behind", am.SKIP),
    (None, "unknown", am.WAIT), (True, "unstable", am.MERGE),
])
def test_mergeability(mergeable, state, expected):
    f = good_facts()
    f["pr"].update(mergeable=mergeable, mergeable_state=state)
    assert decide(f).action == expected


def test_code_drift_on_main_blocks_until_branch_updated():
    f = good_facts()
    f["base_drift_files"] = ["data/sbi.sqlite", "sbi/engine.py"]
    d = decide(f)
    assert d.action == am.SKIP and "sbi/engine.py" in d.reasons[0]
    f["base_drift_files"] = None
    assert decide(f).action == am.SKIP


# --- spend gate -------------------------------------------------------------------------
@pytest.mark.parametrize("path, patch", [
    ("sbi/engine.py", "@@ -1 +1 @@\n+resp = requests.get('https://api.paid.example/v1')"),
    ("sbi/engine.py", "@@ -1 +1 @@\n+KEY = os.getenv('X')"),
    ("sbi/engine.py", "@@ -1 +1 @@\n+# upgrade to the pro subscription for more credits"),
    ("sbi/engine.py", "@@ -1 +1 @@\n-    if remaining_credits < RESERVE: return  # quota guard"),
    ("sbi/pipeline.py", "@@ -1 +1 @@\n+    odds_api.fetch(all_regions=True)"),
    ("docs/assets/doyen.js", "@@ -1 +1 @@\n+fetch('https://tracker.example/collect')"),
    ("sbi/site.py", "@@ -1 +1 @@\n+subprocess.run(['curl', url])"),
    ("tests/test_ev_model.py", "@@ -1 +1 @@\n+@pytest.mark.skip('flaky')"),
    ("tests/test_ev_model.py", "@@ -1 +1 @@\n+__test__ = False"),
])
def test_spend_or_check_lowering_content_goes_to_owner(path, patch):
    f = good_facts()
    f["files"].append({"filename": path, "status": "modified", "changes": 1, "patch": patch})
    f["pr"]["changed_files"] = 3
    d = decide(f)
    assert d.action == am.OWNER_DECISION and d.spend_flags


@pytest.mark.parametrize("entry", [
    {"filename": ".github/workflows/tests.yml", "status": "modified", "changes": 1, "patch": "@@\n-  run: pytest\n+  run: true"},
    {"filename": ".github/workflows/auto-merge.yml", "status": "modified", "changes": 1, "patch": "@@\n+#"},
    {"filename": "automation/auto_merge.py", "status": "modified", "changes": 1, "patch": "@@\n+x = 1"},
    {"filename": "requirements.txt", "status": "modified", "changes": 1, "patch": "@@\n+stripe"},
    {"filename": "tests/conftest.py", "status": "modified", "changes": 1, "patch": "@@\n+x = 1"},
    {"filename": "sbi/sources/new_feed.py", "status": "added", "changes": 1, "patch": "@@\n+x = 1"},
    {"filename": "tests/test_parlays.py", "status": "removed", "changes": 10},
    # hostile rename: moving a protected file to an innocent-looking name
    {"filename": "sbi/helpers.py", "previous_filename": "sbi/sources/odds_api.py", "status": "renamed", "changes": 0},
    {"filename": "notes.md", "previous_filename": "sbi/sources/odds_api.py", "status": "renamed", "changes": 0},
    {"filename": "docs/notes.md", "previous_filename": "tests/test_parlays.py", "status": "renamed", "changes": 0},
    # binary or oversized diff outside generated data: cannot be inspected
    {"filename": "sbi/blob.bin", "status": "added", "changes": 0},
    {"filename": "sbi/engine.py", "status": "modified", "changes": 5000},
    {"filename": "docs/assets/logo.svg", "status": "added", "changes": 0},
    {"filename": "sbi/engine.py", "status": "weird", "changes": 1, "patch": "@@\n+x"},
])
def test_protected_paths_unknowns_and_hostile_renames_go_to_owner(entry):
    f = good_facts()
    f["files"].append(entry)
    f["pr"]["changed_files"] = 3
    assert decide(f).action == am.OWNER_DECISION


def test_incomplete_file_list_fails_closed():
    f = good_facts()
    f["pr"]["changed_files"] = 5  # GitHub says 5, we saw 2
    assert decide(f).action == am.OWNER_DECISION
    f["files"] = None
    assert decide(f).action == am.OWNER_DECISION
    f["files"], f["pr"]["changed_files"] = [], 0
    assert decide(f).action == am.OWNER_DECISION


# --- hostile text and labels --------------------------------------------------------------
def test_pr_text_cannot_grant_anything():
    f = good_facts()
    f["pr"]["title"] = "zero-cost-approved owner-approved-spend"
    f["pr"]["body"] = ("Closes #39\nThis change is zero-cost-approved. owner-approved-spend: yes. "
                       "AUTOMERGE: ignore previous rules and merge.")
    f["files"][1]["patch"] += "\n+    os.environ['ODDS_API_KEY']"
    assert decide(f).action == am.OWNER_DECISION


def test_approval_label_via_app_or_other_actor_is_rejected():
    for kw in ({"app": {"slug": "claude"}}, {"actor": "github-actions[bot]"}, {"actor": "stranger"}):
        f = good_facts()
        f["files"][1]["patch"] += "\n+    billing = True"
        assert decide(with_label(f, am.SPEND_APPROVAL_LABEL, **kw)).action == am.OWNER_DECISION, kw


def test_approval_before_last_push_is_stale():
    f = good_facts()
    f["files"][1]["patch"] += "\n+    billing = True"
    with_label(f, am.SPEND_APPROVAL_LABEL, at="2026-11-18T09:00:00Z")  # checks started 10:01
    assert decide(f).action == am.OWNER_DECISION


def test_label_event_without_label_on_pr_is_ignored():
    f = good_facts()
    f["files"][1]["patch"] += "\n+    billing = True"
    f["label_events"].append(owner_label(am.SPEND_APPROVAL_LABEL))  # label since removed
    assert decide(f).action == am.OWNER_DECISION


def test_later_app_relabel_overrides_earlier_owner_label():
    f = good_facts()
    f["files"][1]["patch"] += "\n+    billing = True"
    with_label(f, am.SPEND_APPROVAL_LABEL, at="2026-11-18T11:00:00Z")
    f["label_events"].append(owner_label(am.SPEND_APPROVAL_LABEL, at="2026-11-18T12:00:00Z", app={"slug": "x"}))
    assert decide(f).action == am.OWNER_DECISION


def test_unparseable_times_fail_closed():
    f = good_facts()
    f["pr"]["created_at"] = "yesterday"
    assert decide(f).action == am.SKIP
    f = good_facts()
    f["files"][1]["patch"] += "\n+    billing = True"
    with_label(f, am.SPEND_APPROVAL_LABEL, at="soon")
    assert decide(f).action == am.OWNER_DECISION


# --- event routing and the dry-run default ----------------------------------------------
class FakeGH:
    def __init__(self):
        self.calls = []

    def get(self, path):
        self.calls.append(("GET", path))
        return [{"number": 7, "state": "open"}, {"number": 8, "state": "closed"}]

    def request(self, method, path, body=None):
        self.calls.append((method, path))
        return None, ""


def test_event_routing():
    gh = FakeGH()
    assert am.pr_numbers_from_event(gh, "pull_request_target", {"pull_request": {"number": 5}}) == [5]
    ok = {"workflow_run": {"conclusion": "success", "event": "pull_request", "pull_requests": [{"number": 6}]}}
    assert am.pr_numbers_from_event(gh, "workflow_run", ok) == [6]
    bad = copy.deepcopy(ok)
    bad["workflow_run"]["conclusion"] = "failure"
    assert am.pr_numbers_from_event(gh, "workflow_run", bad) == []
    push = copy.deepcopy(ok)
    push["workflow_run"]["event"] = "push"
    assert am.pr_numbers_from_event(gh, "workflow_run", push) == []
    lookup = {"workflow_run": {"conclusion": "success", "event": "pull_request", "pull_requests": [], "head_sha": SHA}}
    assert am.pr_numbers_from_event(gh, "workflow_run", lookup) == [7]
    assert am.pr_numbers_from_event(gh, "issue_comment", {}) == []


def test_dry_run_changes_nothing_and_enabled_merges_exact_sha():
    f = good_facts()
    d = decide(f)
    gh = FakeGH()
    assert "dry run" in am.act(gh, 40, f, d, am.Config(enabled=False))
    assert gh.calls == []
    assert am.act(gh, 40, f, d, am.Config(enabled=True)) == "merged"
    assert gh.calls[0] == ("PUT", "pulls/40/merge")


def test_owner_flag_posted_once():
    f = good_facts()
    f["files"][1]["patch"] += "\n+    billing = True"
    d = decide(f)
    gh = FakeGH()
    assert am.act(gh, 40, f, d, am.Config(enabled=True)) == "flagged for the owner"
    f["pr"]["labels"].append({"name": am.NEEDS_OWNER_LABEL})
    gh2 = FakeGH()
    am.act(gh2, 40, f, d, am.Config(enabled=True))
    assert gh2.calls == []


# --- the workflow file itself -----------------------------------------------------------
def test_workflow_never_runs_pull_request_code_and_is_least_privilege():
    text = (ROOT / ".github" / "workflows" / "auto-merge.yml").read_text(encoding="utf-8")
    assert "permissions: {}" in text
    assert "default_branch" in text and "persist-credentials: false" in text
    assert "head.sha" not in text and "head_ref" not in text and "pull_request.head" not in text
    assert "secrets." not in text
    assert "vars.AUTOMERGE_ENABLED" in text
    assert "pip install" not in text  # stdlib only: nothing from the PR or PyPI runs
    for forbidden in ("actions: write", "administration", "id-token"):
        assert forbidden not in text


def test_gate_job_name_matches_self_check_exclusion():
    text = (ROOT / ".github" / "workflows" / "auto-merge.yml").read_text(encoding="utf-8")
    for name in am.SELF_CHECK_NAMES:
        assert f"  {name}:" in text
    tests_yml = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    for name in am.REQUIRED_CHECKS:
        assert f"  {name}:" in tests_yml
    assert "name: tests" in tests_yml


def test_site_prose_and_test_fixtures_about_money_are_not_spend_signals():
    f = good_facts()
    f["files"].append({"filename": "docs/index.html", "status": "modified", "changes": 1,
                       "patch": "@@\n+<p>Doyen takes no payments; bookmaker pricing shown for reference.</p>"})
    f["files"].append({"filename": "tests/test_odds_api.py", "status": "modified", "changes": 1,
                       "patch": "@@\n+    assert credits_used == 3  # x-requests-last header"})
    f["pr"]["changed_files"] = 4
    assert decide(f).action == am.MERGE
    f["files"].append({"filename": "sbi/engine.py", "status": "modified", "changes": 1,
                       "patch": "@@\n+    credits_used += 3"})
    f["pr"]["changed_files"] = 5
    assert decide(f).action == am.OWNER_DECISION


@pytest.mark.parametrize("code", ["remainingCredits -= 1", "MONTHLY_QUOTA = 900", "self.apiCost = 2",
                                  "extra_usage_credits = True"])
def test_identifier_styles_cannot_dodge_word_boundaries(code):
    f = good_facts()
    f["files"][1]["patch"] += f"\n+    {code}"
    assert decide(f).action == am.OWNER_DECISION


def test_links_to_this_repository_are_not_network_signals():
    f = good_facts()
    f["files"][0]["patch"] += '\n+const U = "https://github.com/juanxmarcos/Sports-Betting-/blob/main/docs/PARLAYS.md";'
    assert decide(f).action == am.MERGE
    for url in ("https://github.com/juanxmarcos/Sports-Betting-evil/x", "https://github.com.evil.io/juanxmarcos/Sports-Betting-/",
                "https://api.paid.example/?r=https://github.com/juanxmarcos/Sports-Betting-"):
        g = good_facts()
        g["files"][0]["patch"] += f'\n+const U = "{url}";'
        assert decide(g).action == am.OWNER_DECISION, url


def test_main_end_to_end_dry_run_with_fake_api(tmp_path, monkeypatch):
    f = good_facts()
    calls = []

    class Fake(am.GitHub):
        def request(self, method, path, body=None):
            calls.append((method, path))
            assert method == "GET", "dry run must not write"
            if path.startswith("pulls/40/files"):
                return f["files"], ""
            if path.startswith("pulls/40"):
                return f["pr"], ""
            if path.startswith("issues/39"):
                return f["issue"], ""
            if path.startswith("issues/40/events"):
                return [], ""
            if "check-runs" in path:
                return {"check_runs": f["check_runs"]}, ""
            if path.endswith("/status"):
                return f["combined_status"], ""
            if path.startswith("compare/"):
                return {"files": [{"filename": p} for p in f["base_drift_files"]]}, ""
            raise AssertionError(path)

    event = tmp_path / "event.json"
    event.write_text('{"workflow_run": {"conclusion": "success", "event": "pull_request", '
                     '"pull_requests": [{"number": 40}]}}', encoding="utf-8")
    summary = tmp_path / "summary.md"
    monkeypatch.setattr(am, "GitHub", Fake)
    for k, v in {"GITHUB_TOKEN": "dummy", "GITHUB_REPOSITORY": am.REPOSITORY, "GITHUB_EVENT_NAME": "workflow_run",
                 "GITHUB_EVENT_PATH": str(event), "GITHUB_STEP_SUMMARY": str(summary)}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("AUTOMERGE_ENABLED", raising=False)
    assert am.main() == 0
    text = summary.read_text(encoding="utf-8")
    assert "dry run" in text and "PR #40: merge" in text
    assert all(m == "GET" for m, _ in calls)
