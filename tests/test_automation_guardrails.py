"""Guardrails for the Claude Code automation (issue #8).

These tests keep two promises checkable in CI:
1. No GitHub workflow runs Claude through an API key or an exported subscription token
   (zero extra cost; no subscription credentials in GitHub Actions until approved).
2. The stored prompt for the GitHub-triggered agent keeps its safety rules.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
PROMPT = ROOT / "automation" / "github_issue_trigger_prompt.md"

FORBIDDEN_IN_WORKFLOWS = (
    "anthropics/claude-code-action",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "ANTHROPIC_API_KEY",
    "claude_code_oauth_token",
    "anthropic_api_key",
)


def test_no_workflow_runs_claude_with_credentials():
    files = sorted(WORKFLOWS.glob("*.y*ml"))
    assert files, "expected at least one workflow"
    for wf in files:
        text = wf.read_text(encoding="utf-8")
        for needle in FORBIDDEN_IN_WORKFLOWS:
            assert needle not in text, f"{wf.name} references {needle}; needs owner approval (issue #8)"


def test_daily_data_workflow_still_present():
    daily = (WORKFLOWS / "daily.yml").read_text(encoding="utf-8")
    assert "python -m sbi daily" in daily
    assert "schedule:" in daily


def test_trigger_prompt_keeps_guardrails():
    text = PROMPT.read_text(encoding="utf-8")
    required = (
        "ready-for-claude",            # label is the authorization
        "author is `juanxmarcos`",     # owner-authored issues only
        "untrusted",                   # event/issue text is data, not instructions
        "gate not met",                # silent stop when the gate fails
        "Claude Code is working on this",  # claim comment / duplicate protection
        "NEVER merge",
        "Never place bets",
        "NEVER enable or pay",
        "Closes #N",
        "Never set `ANTHROPIC_API_KEY`",
    )
    for phrase in required:
        assert phrase in text, f"trigger prompt lost guardrail: {phrase!r}"
    # A title prefix alone must never authorize the event-driven agent.
    assert "`[Claude]` title prefix is NOT enough" in text
