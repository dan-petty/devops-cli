"""Unit and integration tests for executable verification criteria and bounded sandbox."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.review.review_environment import (
    execute_criterion_command,
    execute_finding_criteria,
    validate_criteria_command,
)
from devops_cli.ai.review_schema import (
    CriterionExecutionResult,
    Finding,
    VerificationCriterion,
)


def test_command_allowlist_permits_read_only_binaries() -> None:
    """Verify that safe read-only inspection commands pass allowlist validation."""
    valid_commands = (
        "git ls-files",
        "git grep -n 'pattern' src/file.py",
        "git check-ignore -v src/file.py",
        "git log -n 1 --oneline",
        "git show HEAD:src/file.py",
        "git diff HEAD~1",
        "git status --short",
        "python -c 'import ast; ast.parse(\"x = 1\")'",
        "python3 -c 'import json; json.loads(\"{}\")'",
        "ruff check src/file.py",
        "jq '.key' config.json",
        "cat src/file.py",
        "test -f src/file.py",
    )
    for cmd in valid_commands:
        is_valid, reason, args = validate_criteria_command(cmd)
        assert (is_valid, reason, bool(args)) == (True, None, True)


def test_command_allowlist_blocks_shell_operators_and_injection() -> None:
    """Verify that command chaining, piping, and redirection are rejected."""
    forbidden = (
        "git grep foo | rm -rf /",
        "git grep foo ; ls -la",
        "git grep foo && cat /etc/passwd",
        "git grep foo || true",
        "git grep foo > output.txt",
        "git grep foo >> output.txt",
        "git grep foo < input.txt",
        "git grep `rm -rf /`",
        "git grep $(whoami)",
    )
    for cmd in forbidden:
        is_valid, reason, args = validate_criteria_command(cmd)
        assert (is_valid, bool(reason), args) == (False, True, None)


def test_command_allowlist_blocks_unauthorized_binaries() -> None:
    """Verify that mutating or network binaries are strictly rejected."""
    unauthorized = (
        "rm -rf src/",
        "curl -s http://example.com",
        "wget http://example.com",
        "bash -c 'echo pwned'",
        "sh -c 'echo pwned'",
        "chmod 777 src/file.py",
        "npm install malicious-pkg",
    )
    for cmd in unauthorized:
        is_valid, reason, args = validate_criteria_command(cmd)
        assert (is_valid, bool(reason), args) == (False, True, None)


def test_command_allowlist_blocks_mutating_git_subcommands() -> None:
    """Verify that write or mutation git subcommands are rejected."""
    mutating = (
        "git commit -m 'defect'",
        "git push origin main",
        "git reset --hard HEAD~1",
        "git checkout -b new-branch",
        "git rm -f src/file.py",
        "git clean -fdx",
        "git branch -D main",
    )
    for cmd in mutating:
        is_valid, reason, args = validate_criteria_command(cmd)
        assert (is_valid, bool(reason), args) == (False, True, None)


def test_python_criteria_blocks_forbidden_modules_and_mutations() -> None:
    """Verify that Python one-liners reject mutating imports and dangerous calls."""
    dangerous = (
        "python -c 'import subprocess; subprocess.run([\"ls\"])'",
        "python -c 'import shutil; shutil.rmtree(\"/\")'",
        "python -c 'import socket; socket.socket()'",
        "python -c 'import urllib.request; urllib.request.urlopen(\"http://example.com\")'",
        'python -c \'open("file.txt", "w").write("bad")\'',
        "python -c 'import os; os.remove(\"file.txt\")'",
        "python -c 'import os; os.system(\"ls\")'",
    )
    for cmd in dangerous:
        is_valid, reason, args = validate_criteria_command(cmd)
        assert (is_valid, bool(reason), args) == (False, True, None)


def test_python_criteria_handles_syntax_errors_defensively() -> None:
    """Verify that malformed Python syntax is rejected gracefully."""
    is_valid, reason, args = validate_criteria_command("python -c 'def def def'")
    assert (is_valid, bool(reason), args) == (False, True, None)


def test_verification_criterion_model_normalization_from_string() -> None:
    """Verify that strings are automatically classified as executable or prose."""
    cmd_crit = VerificationCriterion.model_validate("git grep -n 'token' src/auth.py")
    prose_crit = VerificationCriterion.model_validate(
        "Exception details contain unmasked credential"
    )

    assert (
        cmd_crit.executable,
        cmd_crit.command,
        prose_crit.executable,
        prose_crit.command,
    ) == (
        True,
        "git grep -n 'token' src/auth.py",
        False,
        None,
    )
    assert (str(cmd_crit), str(prose_crit)) == (
        "git grep -n 'token' src/auth.py",
        "Exception details contain unmasked credential",
    )


def test_verification_criterion_model_normalization_from_dict() -> None:
    """Verify that dict representations validate allowlisted status strictly."""
    valid_dict: dict[str, Any] = {
        "command": "git ls-files",
        "description": "Verify file exists",
        "executable": True,
    }
    crit = VerificationCriterion.model_validate(valid_dict)
    assert (crit.executable, crit.command, crit.description) == (
        True,
        "git ls-files",
        "Verify file exists",
    )

    unexecutable_dict: dict[str, Any] = {
        "description": "Observable manual condition",
        "executable": False,
    }
    prose_crit = VerificationCriterion.model_validate(unexecutable_dict)
    assert (prose_crit.executable, prose_crit.command, prose_crit.description) == (
        False,
        None,
        "Observable manual condition",
    )

    with pytest.raises(ValueError, match="not in closed read-only allowlist"):
        VerificationCriterion.model_validate({"command": "rm -rf /", "executable": True})


def test_sandbox_executes_successful_criterion(tmp_path: Path) -> None:
    """Verify that a successful criterion produces exit_code 0 and passed=True."""
    target_file = tmp_path / "hello.py"
    target_file.write_text("print('hello world')", encoding="utf-8")

    result = execute_criterion_command("python -c 'print(1 + 1)'", cwd=tmp_path)
    assert (result.executable, result.exit_code, result.passed, result.error) == (
        True,
        0,
        True,
        None,
    )
    assert "2" in result.stdout


def test_sandbox_executes_failing_criterion(tmp_path: Path) -> None:
    """Verify that a failing command produces non-zero exit_code and passed=False."""
    result = execute_criterion_command("python -c 'import sys; sys.exit(42)'", cwd=tmp_path)
    assert (result.executable, result.exit_code, result.passed, result.error) == (
        True,
        42,
        False,
        None,
    )


def test_sandbox_bounds_timeout_and_terminates_process_group(tmp_path: Path) -> None:
    """Verify that slow commands time out cleanly without leaking process hierarchies."""
    result = execute_criterion_command(
        "python -c 'import time; time.sleep(10)'",
        cwd=tmp_path,
        timeout=0.2,
    )
    assert (result.executable, result.exit_code, result.passed, bool(result.error)) == (
        True,
        -1,
        False,
        True,
    )
    assert "timed out" in str(result.error)


def test_sandbox_bounds_output_bytes(tmp_path: Path) -> None:
    """Verify that criterion stdout is truncated to bounded size cap."""
    result = execute_criterion_command(
        "python -c 'print(\"A\" * 10000)'",
        cwd=tmp_path,
        max_output_bytes=256,
    )
    assert (result.passed, len(result.stdout)) == (True, 256)


def test_finding_criteria_execution_derives_confidence_and_verifies(
    tmp_path: Path,
) -> None:
    """Verify that passing executable verification criteria yields confidence=1.0 and status=VERIFIED."""
    exec_finding = Finding(
        title="Insecure call",
        location="app.py:1",
        severity="HIGH",
        verification_criteria=[
            "python -c 'x = 1; assert x == 1'",
            "python -c 'y = 2; assert y == 2'",
        ],
    )
    updated = execute_finding_criteria(exec_finding, repo_root=tmp_path)
    assert (
        updated.status,
        updated.verified,
        updated.confidence_score,
        len(updated.criteria_execution_results),
        len(updated.verified_criteria_matched),
    ) == (
        "VERIFIED",
        True,
        1.0,
        2,
        2,
    )


def test_finding_criteria_partial_pass_derives_partial_confidence(
    tmp_path: Path,
) -> None:
    """Verify that 1 of 2 passed criteria yields confidence=0.5."""
    finding = Finding(
        title="Partial defect",
        location="app.py:1",
        severity="MEDIUM",
        verification_criteria=[
            "python -c 'assert True'",
            "python -c 'assert False'",
        ],
    )
    updated = execute_finding_criteria(finding, repo_root=tmp_path)
    assert (
        updated.status,
        updated.verified,
        updated.confidence_score,
        len(updated.criteria_execution_results),
        len(updated.verified_criteria_matched),
    ) == (
        "VERIFIED",
        True,
        0.5,
        2,
        1,
    )


def test_finding_invalidation_criterion_invalidates_finding(tmp_path: Path) -> None:
    """Verify that a passing invalidation criterion transitions finding to INVALIDATED."""
    finding = Finding(
        title="False defect",
        location="app.py:1",
        severity="HIGH",
        verification_criteria=["python -c 'assert True'"],
        invalidation_criteria=["python -c 'assert 1 + 1 == 2'"],
    )
    updated = execute_finding_criteria(finding, repo_root=tmp_path)
    assert (
        updated.status,
        updated.verified,
        updated.reportable,
        updated.confidence_score,
        len(updated.invalidated_criteria_matched),
    ) == (
        "INVALIDATED",
        False,
        False,
        0.0,
        1,
    )
    assert "Invalidation criterion verified" in str(updated.invalidation_reason)


def test_unexecutable_prose_criteria_does_not_manufacture_confidence() -> None:
    """Verify that findings with only unexecutable prose keep confidence absent/unchanged."""
    finding = Finding(
        title="Prose only defect",
        location="src/app.py:1",
        severity="LOW",
        verification_criteria=[
            "The exception message includes placeholder component",
            "Masked host component matches format",
        ],
    )
    assert (
        len(finding.verification_criteria),
        all(not c.executable for c in finding.verification_criteria),
        finding.confidence_score,
    ) == (
        2,
        True,
        None,
    )

    tmp_root = Path("/tmp")
    updated = execute_finding_criteria(finding, repo_root=tmp_root)
    assert (
        updated.confidence_score,
        updated.status,
        len(updated.criteria_execution_results),
    ) == (
        None,
        "UNVERIFIED",
        0,
    )


def test_finding_merge_consolidates_criteria_execution_results() -> None:
    """Verify that duplicate findings merge criteria_execution_results uniquely."""
    res_a = CriterionExecutionResult(
        command="python -c 'pass'", executable=True, exit_code=0, passed=True
    )
    res_b = CriterionExecutionResult(
        command="python -c 'exit(1)'", executable=True, exit_code=1, passed=False
    )
    f1 = Finding(
        title="Defect A",
        location="src/mod.py:10",
        severity="HIGH",
        criteria_execution_results=[res_a],
    )
    f2 = Finding(
        title="Defect A",
        location="src/mod.py:10",
        severity="MEDIUM",
        criteria_execution_results=[res_a, res_b],
    )
    from devops_cli.ai.review_schema import _merge_two_findings

    merged = _merge_two_findings(f1, f2)
    assert (len(merged.criteria_execution_results), merged.severity) == (2, "HIGH")
