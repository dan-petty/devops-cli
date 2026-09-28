"""Regression tests for Batch 2 review and AI response repair defect fixes (#656 - #660, #664)."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from pydantic import BaseModel, Field

from devops_cli.ai.agents.agent import PydanticAgent
from devops_cli.ai.client import LLMClient
from devops_cli.ai.client.models import LLMResponse, is_reasoning_model
from devops_cli.ai.response_repair import _parse_schema_model, repair_json_string
from devops_cli.ai.review.construct_validator import is_absence_finding
from devops_cli.ai.review.defects import _SCRIPT_DOWNLOAD, _pipe_downloaded_script
from devops_cli.ai.review.mitigations import resolve_ledger_path
from devops_cli.ai.review.review_environment import _reconcile_finding_from_criteria
from devops_cli.ai.review.runner import _materialize_pr_head, format_pr_review_comment
from devops_cli.ai.review.verification import (
    _apply_single_finding_verification,
    _match_verdict_by_positional_oracle,
)
from devops_cli.ai.review_schema import (
    CriterionExecutionResult,
    Finding,
    ReviewResult,
    SavedFinding,
    VerificationCriterion,
    _parse_location,
    canonicalize_finding_location,
    reset_verification_state,
)
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage

# =============================================================================
# Issue #656 Tests: AI Response Repair & Plaintext Agent Outputs
# =============================================================================


def test_response_repair_nested_fence_in_fix() -> None:
    """Fenced json containing nested code blocks preserves all findings and full fix."""
    raw = (
        "```json\n"
        "[\n"
        '  {"title": "Bug 1", "fix": "```python\\ndef foo():\\n    pass\\n```"},\n'
        '  {"title": "Bug 2", "fix": "clean up"},\n'
        '  {"title": "Bug 3", "fix": "done"}\n'
        "]\n"
        "```"
    )
    repaired = repair_json_string(raw)
    assert (
        isinstance(repaired, list),
        len(repaired) if isinstance(repaired, list) else 0,
        repaired[0].get("fix") if isinstance(repaired, list) and repaired else "",
    ) == (True, 3, "```python\ndef foo():\n    pass\n```")


def test_response_repair_write_file_inner_fence() -> None:
    """Tool-call arguments containing inner code fences arrive intact."""
    raw = '{"command": "write_file", "path": "test.md", "content": "```yaml\\nkey: value\\n```"}'
    repaired = repair_json_string(raw)
    assert (
        isinstance(repaired, dict),
        repaired.get("command") if isinstance(repaired, dict) else "",
        repaired.get("content") if isinstance(repaired, dict) else "",
    ) == (True, "write_file", "```yaml\nkey: value\n```")


class _CountModel(BaseModel):
    count: int = Field(description="Must be valid integer")


def test_parse_schema_model_reports_field_error_over_json_error() -> None:
    """Schema reflection prioritizes field-level validation errors over generic JSON errors."""
    data = {"count": "not_an_integer"}
    raw_content = '{"count": "not_an_integer" defective}'
    model, err_summary, report, notes = _parse_schema_model(_CountModel, data, raw_content)
    assert (
        model is None,
        "count" in (err_summary or "").lower(),
        report is not None,
    ) == (True, True, True)


def test_plain_text_agent_makes_one_call_without_retry() -> None:
    """An agent configured with str output returns text without schema retry errors."""
    mock_client = MagicMock()
    mock_client.chat_messages.return_value = LLMResponse(
        content="Plain text response without JSON schema"
    )
    mock_client.model = "test-model"
    agent: PydanticAgent[str, None] = PydanticAgent(
        client=mock_client,
        output_type=str,
        system_prompt="Return plain text.",
    )
    result = agent.run("Hello world")
    assert (
        result.output,
        mock_client.chat_messages.call_count,
    ) == ("Plain text response without JSON schema", 1)


# =============================================================================
# Issue #657 Tests: PR Review Comment Format & Analyzers
# =============================================================================


def test_orchestrated_review_comment_includes_verified_high_finding() -> None:
    """PR review comment extracted from report_markdown renders verified findings."""
    finding = Finding(
        severity="HIGH",
        title="SQL Injection in auth",
        location="src/auth.py:42",
        description="User input concatenated into SQL query.",
        verified=True,
    )
    report_md = (
        "# Review Report\n\n"
        "## Detailed Findings\n\n"
        "### [HIGH] SQL Injection in auth\n"
        "**Location:** `src/auth.py:42`\n"
        "User input concatenated into SQL query.\n"
    )
    res = ReviewResult(
        findings=[finding],
        report_markdown=report_md,
        static_analyzers={"Bandit": "ran"},
    )
    mock_persona = MagicMock()
    mock_persona.title = "Security Architect"

    comment = format_pr_review_comment(
        reviews=[(mock_persona, res)],
        files=["src/auth.py"],
        static_analyzers={"Bandit": "ran"},
    )
    assert (
        "Zero findings identified." in comment,
        "SQL Injection in auth" in comment,
        "## Review by Security Architect" in comment,
    ) == (False, True, True)


def test_format_pr_review_comment_no_static_scanners_empty() -> None:
    """When no static scanners ran, comment reports Analyzers: None without PATH fallback."""
    mock_persona = MagicMock()
    mock_persona.title = "QA Engineer"
    res = ReviewResult(findings=[], summary="All tests pass.")

    comment = format_pr_review_comment(
        reviews=[(mock_persona, res)],
        files=["src/app.py"],
        static_analyzers={},
    )
    assert (
        "- **Analyzers:** None" in comment,
        "Gitleaks" in comment,
    ) == (True, False)


# =============================================================================
# Issue #658 Tests: Project Convention Loading from Base Ref
# =============================================================================


def test_pr_review_conventions_loaded_from_base_ref(tmp_path: Path) -> None:
    """Base branch conventions take precedence over PR head convention files."""
    mock_gh = MagicMock()
    mock_gh.get_file_at.side_effect = lambda repo, path, ref: (
        "BASE CONVENTIONS" if path == "AGENTS.md" else None
    )

    pull_mock = MagicMock()
    pull_mock.head.repo.full_name = "fork/repo"
    pull_mock.head.ref = "feature"
    pull_mock.base.repo.full_name = "org/repo"
    pull_mock.base.ref = "main"
    pull_mock.base.sha = "base123"
    pull_mock.get_files.return_value = [
        MagicMock(filename="AGENTS.md", status="modified"),
        MagicMock(filename=".devops/review.md", status="added"),
        MagicMock(filename="src/foo.py", status="modified"),
    ]

    dest_dir = tmp_path / "target"
    dest_dir.mkdir()
    empty_cwd = tmp_path / "empty_cwd"
    empty_cwd.mkdir()

    with patch("pathlib.Path.cwd", return_value=empty_cwd):
        _materialize_pr_head(mock_gh, "org/repo", pull_mock, dest_dir)

    assert (
        (dest_dir / "AGENTS.md").read_text(encoding="utf-8"),
        (dest_dir / ".devops/review.md").exists(),
    ) == ("BASE CONVENTIONS", False)


# =============================================================================
# Issue #659 Tests: Absence Findings & Location Canonicalization
# =============================================================================


def test_absence_findings_identified_correctly() -> None:
    """Findings describing missing features or absent defenses match absence markers."""
    f1 = Finding(title="Missing timeout on outbound HTTP request", location="net.py:10")
    f2 = Finding(title="Endpoint lacks @login_required check", location="auth.py:20")
    f3 = Finding(title="SQL Injection via string formatting", location="db.py:30")
    assert (
        is_absence_finding(f1),
        is_absence_finding(f2),
        is_absence_finding(f3),
    ) == (True, True, False)


def test_parse_location_preserves_path_case() -> None:
    """Path case is preserved during location parsing and relocation."""
    parsed_case = _parse_location("Pkg/Handler.py:11", preserve_case=True)
    parsed_lower = _parse_location("Pkg/Handler.py:11", preserve_case=False)
    assert (
        parsed_case,
        parsed_lower,
    ) == (("Pkg/Handler.py", 11, 11), ("pkg/handler.py", 11, 11))


def test_location_canonicalization_drops_surrounding_prose() -> None:
    """Surrounding conversational prose is stripped from canonical locations."""
    loc1 = canonicalize_finding_location("src/app.py:42 in get_user")
    loc2 = canonicalize_finding_location("See src/app.py:42")
    loc3 = canonicalize_finding_location("src/app.py:10-20 (auth check)")
    assert (loc1, loc2, loc3) == ("src/app.py:42", "src/app.py:42", "src/app.py:10-20")


def test_synthetic_script_download_preserves_curl_dash_o() -> None:
    """Treat -O as a flag without argument preserving target URL in synthetic defect."""
    cmd = "curl -fsSL -O https://example.com/install.sh"
    injected = re.sub(_SCRIPT_DOWNLOAD, _pipe_downloaded_script, cmd)
    assert (
        injected,
        "-O" not in injected,
    ) == ("curl -fsSL https://example.com/install.sh | sh", True)


# =============================================================================
# Issue #660 Tests: Positional Oracle & Degraded Mitigations
# =============================================================================


def test_degraded_mitigation_retains_reportable_true() -> None:
    """Mitigation with placeholder mechanism degrades to UNVERIFIED with reportable=True."""
    f = Finding(
        title="Unbounded channel",
        location="ch.py:5",
        mitigating_mechanism="none",
        perimeter_files=["n/a"],
    )
    res = _apply_single_finding_verification(
        f,
        {"status": "MITIGATED", "mitigating_mechanism": "none", "perimeter_files": ["n/a"]},
        "2026-09-28T00:00:00Z",
    )
    assert (
        res.status,
        res.reportable,
        res.mitigated,
    ) == ("UNVERIFIED", True, False)


def test_positional_oracle_rejects_incompatible_title() -> None:
    """Positional oracle rejects binding when finding titles are completely incompatible."""
    unverified = [
        SavedFinding(
            finding_id="f-1",
            title="SQL Injection in auth",
            location="auth.py:10",
            status="UNVERIFIED",
        )
    ]
    raw_verdict = {
        "finding_id": "f-1",
        "title": "Unused import os in test helper",
        "status": "INVALIDATED",
        "reason": "Harmless import",
    }
    matched = _match_verdict_by_positional_oracle(unresolved=unverified, bound={}, item=raw_verdict)
    assert matched is None


def test_conflicting_criteria_leaves_finding_unverified() -> None:
    """When both invalidation and verification criteria pass, finding remains UNVERIFIED."""
    crit_ver = VerificationCriterion(command="git grep -q timeout", executable=True)
    f = SavedFinding(
        title="Flaky timeout",
        location="net.py:15",
        status="UNVERIFIED",
        verification_criteria=[crit_ver],
    )
    exec_res = [
        CriterionExecutionResult(
            command="git grep -q timeout",
            exit_code=0,
            passed=True,
            duration_seconds=0.1,
        )
    ]
    reconciled = _reconcile_finding_from_criteria(
        finding=f,
        exec_results=exec_res,
        matched_ver=["git grep -q timeout"],
        matched_inv=["test_inv.sh"],
    )
    assert (
        reconciled.status,
        reconciled.verified_by,
        reconciled.confidence_score,
    ) == ("UNVERIFIED", None, 1.0)


def test_null_location_treated_as_unchanged() -> None:
    """Verifier returning location null or None leaves finding location unchanged."""
    f = Finding(title="Race condition", location="thread.py:88")
    verified = _apply_single_finding_verification(
        f,
        {"status": "VERIFIED", "location": None},
        "2026-09-28T00:00:00Z",
    )
    assert verified.location == "thread.py:88"


def test_reset_verification_state_clears_finding_id() -> None:
    """reset_verification_state clears persona-provided finding_id to prevent collision."""
    f = Finding(
        finding_id="persona-chosen-id-99",
        title="Buffer overflow",
        location="buf.c:12",
        status="VERIFIED",
    )
    cleared = reset_verification_state(f)
    assert (
        cleared.finding_id,
        cleared.status,
    ) == (None, "UNVERIFIED")


def test_mitigations_ledger_resolves_under_data_dir() -> None:
    """resolve_ledger_path resolves ledger file under the data directory."""
    ledger = resolve_ledger_path()
    assert (
        ledger.name,
        ".data" in str(ledger) or "test" in str(ledger),
    ) == ("mitigated_findings.json", True)


# =============================================================================
# Issue #664 Tests: Shared Agent Memory Isolation & Reasoning Model Tokens
# =============================================================================


def test_shared_agent_skips_memory_when_history_empty() -> None:
    """When message_history=[] is provided, agent skips recording interaction to memory."""
    mock_client = MagicMock()
    mock_client.chat_messages.return_value = LLMResponse(content="Isolated response")
    mock_client.model = "test-model"
    agent: PydanticAgent[str, None] = PydanticAgent(client=mock_client, output_type=str)
    agent.run("Review isolated file content", message_history=[])
    assert len(agent.memory.entries) == 0


def test_reasoning_models_use_max_completion_tokens() -> None:
    """Reasoning model families utilize max_completion_tokens and reasoning_effort."""
    models_to_test = [
        "gpt-5",
        "gpt-5-mini",
        "vendor/deepseek-r1-distill",
        "vendor/qwq-32b",
    ]
    for m in models_to_test:
        provider = LLMClient(
            config=AIConfig(
                provider="openai",
                model=m,
                max_tokens=4096,
                reasoning_effort="high",
            )
        )
        payload = provider._build_compat_payload(
            system="system prompt",
            messages=[ChatMessage(role="user", content="hello")],
        )
        assert (
            is_reasoning_model(m),
            "max_completion_tokens" in payload,
            "max_tokens" not in payload,
            payload.get("reasoning_effort"),
        ) == (True, True, True, "high")
