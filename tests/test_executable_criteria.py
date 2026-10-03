"""Unit and integration tests for executable verification criteria and bounded sandbox."""

from __future__ import annotations

import json
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
    """Verify that criterion stdout is truncated and process killed when exceeding size cap."""
    result = execute_criterion_command(
        "python -c 'print(\"A\" * 10000)'",
        cwd=tmp_path,
        max_output_bytes=256,
    )
    assert (
        result.passed,
        len(result.stdout) <= 256,
        "Output exceeded maximum limit" in str(result.error),
    ) == (False, True, True)


def _app(tmp_path: Path) -> Path:
    """A project whose `app.py` holds `f`, which adds one, at line 2."""
    (tmp_path / "app.py").write_text("\ndef f(x):\n    return x + 1\n", encoding="utf-8")
    return tmp_path


def _replaying(monkeypatch: pytest.MonkeyPatch, results: list[CriterionExecutionResult]) -> None:
    """Serve each criterion the result recorded for its command instead of running it."""
    by_command = {r.command: r for r in results}
    monkeypatch.setattr(
        "devops_cli.ai.review.review_environment.execute_criterion_command",
        lambda command, cwd, **_: by_command[command],
    )


def _passed(command: str) -> CriterionExecutionResult:
    return CriterionExecutionResult(
        command=command, description=command, executable=True, exit_code=0, passed=True
    )


def _verdict(finding: Finding) -> tuple[str, bool, bool, str | None, float | None]:
    return (
        finding.status,
        finding.verified,
        finding.reportable,
        finding.verified_by,
        finding.confidence_score,
    )


def test_assertions_over_no_cited_code_do_not_verify(tmp_path: Path) -> None:
    """Passing assertions that import nothing the finding cites are recorded but prove nothing."""
    finding = Finding(
        title="Insecure call",
        location="app.py:2",
        severity="HIGH",
        verification_criteria=[
            "python -c 'x = 1; assert x == 1'",
            "python -c 'y = 2; assert y == 2'",
        ],
    )

    updated = execute_finding_criteria(finding, repo_root=_app(tmp_path))

    assert (
        _verdict(updated),
        [r.passed for r in updated.criteria_execution_results],
        updated.verified_criteria_matched,
    ) == (("UNVERIFIED", False, True, None, None), [True, True], [])


def test_an_assertion_over_the_cited_code_verifies(tmp_path: Path) -> None:
    """A command that imports the cited module and asserts its outcome settles VERIFIED."""
    command = "python -c 'from app import f; assert f(1) == 2'"
    finding = Finding(
        title="f adds one",
        location="app.py:2",
        severity="LOW",
        verification_criteria=[command],
    )

    updated = execute_finding_criteria(finding, repo_root=_app(tmp_path))

    assert (_verdict(updated), updated.verified_criteria_matched) == (
        ("VERIFIED", True, True, "criteria", 1.0),
        [command],
    )


def test_finding_criteria_partial_pass_derives_partial_confidence(tmp_path: Path) -> None:
    """One of two assertions over the cited code passing verifies at half confidence."""
    finding = Finding(
        title="Partial defect",
        location="app.py:2",
        severity="MEDIUM",
        verification_criteria=[
            "python -c 'from app import f; assert f(1) == 2'",
            "python -c 'from app import f; assert f(1) == 3'",
        ],
    )

    updated = execute_finding_criteria(finding, repo_root=_app(tmp_path))

    assert (_verdict(updated), len(updated.verified_criteria_matched)) == (
        ("VERIFIED", True, True, "criteria", 0.5),
        1,
    )


def test_an_assertion_over_no_cited_code_does_not_invalidate(tmp_path: Path) -> None:
    """A passing invalidation criterion that asserts arithmetic leaves the finding for the model."""
    finding = Finding(
        title="False defect",
        location="app.py:2",
        severity="HIGH",
        invalidation_criteria=["python -c 'assert 1 + 1 == 2'"],
    )

    updated = execute_finding_criteria(finding, repo_root=_app(tmp_path))

    assert (
        _verdict(updated),
        updated.invalidation_reason,
        updated.invalidated_criteria_matched,
    ) == (("UNVERIFIED", False, True, None, None), None, [])


def test_an_assertion_over_the_cited_code_invalidates(tmp_path: Path) -> None:
    """A passing invalidation criterion that runs the cited code still settles INVALIDATED."""
    command = "python -c 'from app import f; assert f(1) == 2'"
    finding = Finding(
        title="f adds two",
        location="app.py:2",
        severity="HIGH",
        invalidation_criteria=[command],
    )

    updated = execute_finding_criteria(finding, repo_root=_app(tmp_path))

    assert (_verdict(updated), updated.invalidation_reason) == (
        ("INVALIDATED", False, False, "criteria", 0.0),
        f"Invalidation criterion verified: {command}",
    )


def test_a_grep_of_the_cited_line_leaves_the_finding_reportable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A finding whose only invalidation criterion greps its own cited line stays reportable."""
    command = "git grep -n os.system app.py"
    _replaying(monkeypatch, [_passed(command)])
    finding = Finding(
        title="Shell command built from input",
        location="app.py:2",
        severity="HIGH",
        invalidation_criteria=[command],
    )

    updated = execute_finding_criteria(finding, repo_root=tmp_path)

    assert (_verdict(updated), [r.command for r in updated.criteria_execution_results]) == (
        ("UNVERIFIED", False, True, None, None),
        [command],
    )


@pytest.mark.parametrize("side", ["verification_criteria", "invalidation_criteria"])
@pytest.mark.parametrize(
    "command",
    [
        "grep -n f app.py",
        "git log --oneline --grep=f",
        "wc -l app.py",
        "cat app.py",
        "head -n 3 app.py",
        "tail -n 3 app.py",
        "find . -name app.py",
        "python -c 'from app import f; print(f(1))'",
        "python -c 'import sys; from app import f; f(1); sys.exit(0)'",
        "python -c \"from app import f; assert hasattr(f, '__call__')\"",
        # A grep written in Python: the cited file's text searched, or only found (#846).
        "python -c \"from pathlib import Path; assert 'return x + 1' in Path('app.py').read_text()\"",
        'python -c "import re; from pathlib import Path; '
        "assert re.search('x [+] 1', Path('app.py').read_text())\"",
        "python -c \"import ast; from pathlib import Path; assert ast.parse(Path('app.py').read_text())\"",
        "python -c \"from pathlib import Path; assert Path('app.py').exists()\"",
        "python -c 'import os; assert os.path.isfile(\"app.py\")'",
        # A check that does not depend on what the cited code does (#846).
        "python -c 'from app import f; print(f); raise SystemExit(0)'",
        "python -c 'import app; assert 1 == 1'",
        "python -c 'import sys; from app import f; sys.exit(f(1))'",
        "python -c 'from app import f; f(1); exit(0)'",
        "python -c 'from app import f; assert f'",
        "python -c 'import app; assert app.f is not None'",
    ],
)
def test_a_command_that_finds_or_prints_code_never_counts(
    command: str, side: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding, counting, printing or reflecting on code settles nothing, however it exits."""
    _replaying(monkeypatch, [_passed(command)])
    finding = Finding(title="f adds one", location="app.py:2", severity="LOW", **{side: [command]})

    updated = execute_finding_criteria(finding, repo_root=_app(tmp_path))

    assert _verdict(updated) == ("UNVERIFIED", False, True, None, None)


@pytest.mark.parametrize(
    ("location", "command"),
    [
        ("app.py:2", "python -c 'import sys; from app import f; sys.exit(f(1) != 2)'"),
        ("app.py:2", "python -c 'from app import f\nif f(1) != 2: raise SystemExit(1)'"),
        ("src/pkg/mod.py:1", "python -c 'from pkg.mod import g; assert g() == 1'"),
        ("src/pkg/mod.py:1", "python -c 'from src.pkg import mod; assert mod.g() == 1'"),
        (
            "app.py:2",
            "python -c 'from app import f\ntry:\n    f(None)\nexcept TypeError:\n    pass\n"
            "else:\n    raise SystemExit(1)'",
        ),
        (
            "k8s/app.yaml:3",
            'python -c "import yaml; from pathlib import Path; '
            "assert yaml.safe_load(Path('k8s/app.yaml').read_text())['privileged'] is True\"",
        ),
        (
            "k8s/app.json:2",
            'python -c "import json; from pathlib import Path; '
            "d = json.loads(Path('k8s/app.json').read_text()); assert d['replicas'] == 1\"",
        ),
    ],
)
def test_a_command_that_runs_the_cited_code_and_asserts_counts(
    location: str, command: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Asserting over what the cited module computes, or over the cited file as parsed, is
    evidence."""
    _replaying(monkeypatch, [_passed(command)])
    finding = Finding(title="Defect", location=location, verification_criteria=[command])

    updated = execute_finding_criteria(finding, repo_root=tmp_path)

    assert _verdict(updated) == ("VERIFIED", True, True, "criteria", 1.0)


def test_pytest_counts_only_on_a_test_that_imports_the_cited_code(tmp_path: Path) -> None:
    """A passing test is evidence only when it imports the module the finding cites."""
    from devops_cli.ai.review.criteria_evidence import counts_as_evidence

    tests = _app(tmp_path) / "tests"
    tests.mkdir()
    (tests / "test_app.py").write_text(
        "from app import f\n\n\ndef test_f():\n    assert f(1) == 2\n", encoding="utf-8"
    )
    (tests / "test_other.py").write_text("def test_nothing():\n    assert True\n", encoding="utf-8")
    commands = (
        "pytest tests/test_app.py::test_f -q",
        "python -m pytest tests/test_app.py",
        "pytest tests/test_other.py",
        "pytest tests",
        "pytest ../outside/test_app.py",
        # Each exits 0 without running a test (#846).
        "pytest --collect-only tests/test_app.py",
        "python -m pytest --co -q tests/test_app.py",
        "python -m pytest --version tests/test_app.py",
        "pytest -qh tests/test_app.py",
        "pytest --setup-plan tests/test_app.py",
        "pytest --fixtures tests/test_app.py",
        "pytest --cache-show=* tests/test_app.py",
    )

    assert tuple(counts_as_evidence(c, "app.py:2", tmp_path) for c in commands) == (
        True,
        True,
        *(False,) * (len(commands) - 2),
    )


_ASSERTS_F = "python -c 'from app import f; assert f(1) == 2'"


@pytest.mark.parametrize(
    ("proves", "refutes"),
    [
        (_ASSERTS_F, "python -c 'from app import f; assert f(2) == 3'"),
        # Either side passing without counting still passed (#846).
        (_ASSERTS_F, "grep -n 'x + 1' app.py"),
        ("grep -n 'x + 1' app.py", _ASSERTS_F),
    ],
    ids=["both-count", "refutation-counts-not", "proof-counts-not"],
)
def test_criteria_that_pass_both_ways_do_not_discriminate(
    proves: str, refutes: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A passing verification and a passing invalidation criterion leave the finding unverified,
    whether or not each counts as evidence."""
    _replaying(monkeypatch, [_passed(proves), _passed(refutes)])
    finding = Finding(
        title="f adds one",
        location="app.py:2",
        verification_criteria=[proves],
        invalidation_criteria=[refutes],
    )

    updated = execute_finding_criteria(finding, repo_root=_app(tmp_path))

    assert (_verdict(updated), updated.verification_note) == (
        ("UNVERIFIED", False, True, None, None),
        "criteria-non-discriminating",
    )


def test_one_command_in_both_lists_never_exceeds_full_confidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A command given as both criteria, passing once per list, cannot raise confidence past 1."""
    command = "python -c \"import re; re.compile('a{1000}b', re.IGNORECASE)\""
    _replaying(monkeypatch, [_passed(command)])
    finding = Finding(
        title="Insecure Regular Expression Compilation",
        location="app.py:2",
        verification_criteria=[command],
        invalidation_criteria=[command],
    )

    updated = execute_finding_criteria(finding, repo_root=_app(tmp_path))

    assert _verdict(updated) == ("UNVERIFIED", False, True, None, None)


_REPLAYED = json.loads(
    (Path(__file__).parent / "golden" / "criteria_replay.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", _REPLAYED["cases"], ids=lambda c: c["id"])
def test_the_sessions_worst_commands_settle_no_verdict(
    case: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Replayed with their recorded results, criteria that verified findings settle nothing."""
    _replaying(monkeypatch, [CriterionExecutionResult(**r) for r in case["results"]])
    finding = Finding(**case["finding"])

    updated = execute_finding_criteria(finding, repo_root=tmp_path)

    assert (
        (case["saved_status"], case["saved_verified_by"]),
        _verdict(updated),
        len(updated.criteria_execution_results),
    ) == (
        ("VERIFIED", "criteria"),
        ("UNVERIFIED", False, True, None, None),
        len(case["results"]),
    )


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
