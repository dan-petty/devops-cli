"""Unit and integration tests for executable verification criteria and bounded sandbox."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from devops_cli.ai.client import LLMResponse
from devops_cli.ai.review.criteria_evidence import counts_as_evidence
from devops_cli.ai.review.review_environment import (
    execute_criterion_command,
    execute_finding_criteria,
    validate_criteria_command,
)
from devops_cli.ai.review.verification import _validate_segment_findings
from devops_cli.ai.review_schema import (
    CriterionExecutionResult,
    Finding,
    ReviewResult,
    VerificationCriterion,
)
from devops_cli.config.defaults import DEFAULT_CRITERIA_EXECUTION_TIMEOUT_SECONDS
from devops_cli.sandbox.host import HostSandboxResult


def _recording_sandbox() -> MagicMock:
    """A sandbox stand-in that records each execution and reports it passed."""
    sandbox = MagicMock()
    sandbox.is_available.return_value = True
    sandbox.execute.return_value = HostSandboxResult(
        exit_code=0, stdout="", stderr="", duration_seconds=0.01, passed=True
    )
    return sandbox


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
        "find src -name '*.py' -type f -newer src/file.py",
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
    assert (
        result.executable,
        result.exit_code,
        result.passed,
        result.error,
        result.timed_out,
    ) == (True, 42, False, None, False)


def test_sandbox_bounds_timeout_and_terminates_process_group(tmp_path: Path) -> None:
    """Verify that slow commands time out cleanly without leaking process hierarchies."""
    result = execute_criterion_command(
        "python -c 'import time; time.sleep(10)'",
        cwd=tmp_path,
        timeout=0.2,
    )
    assert (
        result.executable,
        result.exit_code,
        result.passed,
        "timed out" in str(result.error),
        result.timed_out,
    ) == (True, -1, False, True, True)


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
        result.timed_out,
    ) == (False, True, True, False)


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


def test_an_assertion_over_the_cited_code_leaves_the_finding_for_the_verifier(
    tmp_path: Path,
) -> None:
    """A passing verification command that imports the cited module and asserts its outcome is
    recorded as matched, and the finding stays unverified for the verifier: the evidence rule
    cannot tell which side of the claim a pass supports (#1043)."""
    command = "python -c 'from app import f; assert f(1) == 2'"
    finding = Finding(
        title="f adds one",
        location="app.py:2",
        severity="LOW",
        verification_criteria=[command],
    )

    updated = execute_finding_criteria(finding, repo_root=_app(tmp_path))

    assert (_verdict(updated), updated.verified_criteria_matched) == (_NO_VERDICT, [command])


def test_verification_criteria_that_pass_in_part_give_no_confidence(tmp_path: Path) -> None:
    """One of two assertions over the cited code passing is recorded as matched, and the
    criteria give the finding no confidence (#1043). It verified at half confidence before."""
    passing = "python -c 'from app import f; assert f(1) == 2'"
    finding = Finding(
        title="Partial defect",
        location="app.py:2",
        severity="MEDIUM",
        verification_criteria=[passing, "python -c 'from app import f; assert f(1) == 3'"],
    )

    updated = execute_finding_criteria(finding, repo_root=_app(tmp_path))

    assert (_verdict(updated), updated.verified_criteria_matched) == (_NO_VERDICT, [passing])


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
    evidence: the command is recorded as matched, and the verifier judges the finding (#1043)."""
    _replaying(monkeypatch, [_passed(command)])
    finding = Finding(title="Defect", location=location, verification_criteria=[command])

    updated = execute_finding_criteria(finding, repo_root=tmp_path)

    assert (_verdict(updated), updated.verified_criteria_matched) == (_NO_VERDICT, [command])


_ASSERTS_F = "python -c 'from app import f; assert f(1) == 2'"
_PRINTS_F = "python -c 'from app import f; print(f(1))'"


@pytest.mark.parametrize("side", ["verification_criteria", "invalidation_criteria"])
@pytest.mark.parametrize(
    "command",
    [
        "pytest tests/test_app.py::test_f -q",
        "python -m pytest tests/test_app.py",
        "python -c \"import pytest; pytest.main(['tests/test_app.py'])\"",
    ],
)
def test_a_pytest_criterion_over_a_test_of_the_cited_code_never_runs(
    command: str, side: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pytest run of a test that imports the cited module is refused before it runs, so it
    settles nothing, and the evidence rule has no case for it (#847)."""
    sandbox = _recording_sandbox()
    monkeypatch.setattr("devops_cli.sandbox.host.HostSandbox", lambda: sandbox)
    tests = _app(tmp_path) / "tests"
    tests.mkdir()
    (tests / "test_app.py").write_text(
        "from app import f\n\n\ndef test_f():\n    assert f(1) == 2\n", encoding="utf-8"
    )
    finding = Finding(title="f adds one", location="app.py:2", severity="HIGH", **{side: [command]})

    updated = execute_finding_criteria(finding, repo_root=tmp_path)

    assert (
        [c.executable for c in getattr(updated, side)],
        updated.criteria_execution_results,
        sandbox.execute.called,
        _verdict(updated),
    ) == ([False], [], False, ("UNVERIFIED", False, True, None, None))


# How long the print criterion replayed for #847's merge-order note ran (6.8 s): it timed out at
# the general 5 s limit and passes within the python one.
_SLOW_IMPORT_SECONDS = 6.8


def _sandbox_for_a_run_of(seconds: float) -> MagicMock:
    """A sandbox stand-in for a command that exits 0 after `seconds`: it passes within a time
    limit at least that long and times out at a shorter one."""
    sandbox = MagicMock()
    sandbox.is_available.return_value = True

    def execute(*, timeout: float, **_: object) -> HostSandboxResult:
        if timeout < seconds:
            return HostSandboxResult(
                exit_code=-1,
                stdout="",
                stderr="",
                duration_seconds=timeout,
                passed=False,
                error=f"Execution timed out after {timeout}s",
                timed_out=True,
            )
        return HostSandboxResult(
            exit_code=0, stdout="2\n", stderr="", duration_seconds=seconds, passed=True
        )

    sandbox.execute.side_effect = execute
    return sandbox


_NO_VERDICT = ("UNVERIFIED", False, True, None, None)
_INVALIDATED_BY_CRITERIA = ("INVALIDATED", False, False, "criteria", 0.0)


@pytest.mark.parametrize(
    ("side", "command", "verdict", "matched"),
    [
        ("verification_criteria", _PRINTS_F, _NO_VERDICT, ([], [])),
        ("invalidation_criteria", _PRINTS_F, _NO_VERDICT, ([], [])),
        ("verification_criteria", _ASSERTS_F, _NO_VERDICT, ([_ASSERTS_F], [])),
        ("invalidation_criteria", _ASSERTS_F, _INVALIDATED_BY_CRITERIA, ([], [_ASSERTS_F])),
    ],
    ids=["verify-print", "invalidate-print", "verify-assert", "invalidate-assert"],
)
def test_a_criterion_the_python_limit_lets_finish_counts_only_if_it_asserts(
    side: str,
    command: str,
    verdict: tuple[str, bool, bool, str | None, float | None],
    matched: tuple[list[str], list[str]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A python criterion that timed out at 5 s finishes and passes within the python limit,
    and the evidence rule still decides what it counts for: printing what the cited code
    returns counts for nothing, and asserting over it counts. As an invalidation criterion it
    settles INVALIDATED; as a verification criterion it is recorded as matched and leaves the
    finding to the verifier (#846, #847, #1043).

    The print case stands for the merge-order replay, which on #847 without #846 ended VERIFIED."""
    from devops_cli.config.defaults import DEFAULT_CRITERIA_PYTHON_TIMEOUT_SECONDS

    sandbox = _sandbox_for_a_run_of(_SLOW_IMPORT_SECONDS)
    monkeypatch.setattr("devops_cli.sandbox.host.HostSandbox", lambda: sandbox)
    finding = Finding(title="f adds one", location="app.py:2", severity="HIGH", **{side: [command]})

    updated = execute_finding_criteria(finding, repo_root=_app(tmp_path))

    assert (
        DEFAULT_CRITERIA_EXECUTION_TIMEOUT_SECONDS
        < _SLOW_IMPORT_SECONDS
        <= DEFAULT_CRITERIA_PYTHON_TIMEOUT_SECONDS,
        [call.kwargs["timeout"] for call in sandbox.execute.call_args_list],
        [(r.passed, r.timed_out) for r in updated.criteria_execution_results],
        _verdict(updated),
        (updated.verified_criteria_matched, updated.invalidated_criteria_matched),
    ) == (True, [DEFAULT_CRITERIA_PYTHON_TIMEOUT_SECONDS], [(True, False)], verdict, matched)


def _app_with_its_own_environment(tmp_path: Path) -> Path:
    """`_app`, whose `f` adds `ONE` from `reviewed_dependency`, a module only the project's own
    `.venv` holds, as `uv sync` installs a reviewed project's dependencies there."""
    interpreter = Path(sys.executable).resolve()
    venv = tmp_path / ".venv"
    site_packages = (
        venv / "lib" / f"python{sys.version_info[0]}.{sys.version_info[1]}" / "site-packages"
    )
    site_packages.mkdir(parents=True)
    (site_packages / "reviewed_dependency.py").write_text("ONE = 1\n", encoding="utf-8")
    (venv / "bin").mkdir()
    (venv / "bin" / "python").symlink_to(interpreter)
    (venv / "pyvenv.cfg").write_text(f"home = {interpreter.parent}\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / "app.py").write_text(
        "from reviewed_dependency import ONE\ndef f(x):\n    return x + ONE\n", encoding="utf-8"
    )
    return tmp_path


@pytest.mark.parametrize(
    ("command", "matched"),
    [(_PRINTS_F, []), (_ASSERTS_F, [_ASSERTS_F])],
    ids=["print", "assert"],
)
def test_under_the_project_interpreter_only_an_assertion_counts(
    command: str, matched: list[str], tmp_path: Path
) -> None:
    """Live test: run by the reviewed project's own interpreter, a criterion importing code that
    needs the project's dependencies passes, and only one that asserts over it counts as
    evidence (#846, #847). Neither settles a verdict: a verification criterion leaves the finding
    to the verifier (#1043). Under the system Python both failed on the import."""
    finding = Finding(
        title="f adds one", location="app.py:2", severity="HIGH", verification_criteria=[command]
    )

    updated = execute_finding_criteria(finding, repo_root=_app_with_its_own_environment(tmp_path))

    assert (
        [(r.passed, r.stderr) for r in updated.criteria_execution_results],
        _verdict(updated),
        updated.verified_criteria_matched,
    ) == ([(True, "")], _NO_VERDICT, matched)


# An assertion over the cited code that fails: `f(1)` is 2.
_FALSE_ASSERT_F = "from app import f; assert f(1) == 3"


@pytest.mark.parametrize("side", ["verification_criteria", "invalidation_criteria"])
@pytest.mark.parametrize(
    "command",
    [
        f"python -m this -c '{_FALSE_ASSERT_F}'",
        f"python -m app -c '{_FALSE_ASSERT_F}'",
        f"python -Bc pass -c '{_FALSE_ASSERT_F}'",
    ],
    ids=["module-first", "cited-module-first", "cluster-first"],
)
def test_an_assertion_python_never_runs_settles_no_verdict(
    command: str, side: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Python runs the first `-c` or `-m` it reads, inside a cluster such as `-Bc` too, and passes
    what follows to that script or module. A later `-c` assertion never runs, so the command's
    exit 0, as the stand-in reports it, settles no verdict (#847)."""
    sandbox = _recording_sandbox()
    monkeypatch.setattr("devops_cli.sandbox.host.HostSandbox", lambda: sandbox)
    finding = Finding(title="f adds two", location="app.py:2", severity="HIGH", **{side: [command]})

    updated = execute_finding_criteria(finding, repo_root=_app(tmp_path))

    assert (counts_as_evidence(command, "app.py:2", tmp_path), _verdict(updated)) == (
        False,
        _NO_VERDICT,
    )


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


_DIRECTION = {
    case["id"]: case
    for case in json.loads(
        (Path(__file__).parent / "golden" / "criteria_direction.json").read_text(encoding="utf-8")
    )["cases"]
}


def _golden(case_id: str, root: Path, monkeypatch: pytest.MonkeyPatch) -> Finding:
    """The golden case's finding, with the cited file written at its path under `root`, holding
    the case's lines at their numbers, and its commands replayed with the results they gave."""
    case = _DIRECTION[case_id]
    finding = Finding(**case["finding"])
    lines: dict[str, str] = case["cited_lines"]
    cited = root / finding.location.split(":")[0]
    cited.parent.mkdir(parents=True, exist_ok=True)
    cited.write_text(
        "".join(f"{lines.get(str(n), '')}\n" for n in range(1, max(map(int, lines)) + 1)),
        encoding="utf-8",
    )
    _replaying(monkeypatch, [CriterionExecutionResult(**r) for r in case["results"]])
    return finding


def _verifier(reply: str, finish_reason: str = "stop") -> MagicMock:
    """A verifier client stand-in that gives `reply` and calls no model."""
    client = MagicMock()
    client.chat.return_value = LLMResponse(reply, finish_reason=finish_reason)
    return client


def _shown(client: MagicMock) -> list[list[str]]:
    """The locations of the findings each verifier prompt showed, one list per call."""
    shown = re.compile(r"<untrusted_findings_input>\n```json\n(.*?)\n```", re.DOTALL)
    return [
        [f["location"] for f in json.loads(shown.findall(call.kwargs["user"])[0])]
        for call in client.chat.call_args_list
    ]


def _verify(
    finding: Finding, client: MagicMock, root: Path, monkeypatch: pytest.MonkeyPatch
) -> Finding:
    """The finding after file verification under `root`, the RAG lookup stubbed out."""
    monkeypatch.setattr(
        "devops_cli.ai.review.verification._collect_rag_verification_blocks", lambda _: []
    )
    result, _, _ = _validate_segment_findings(
        ReviewResult(findings=[finding]), ["code"], client, repo_root=root
    )
    return result.findings[0]


# The verifier's refutation of the chunker.py:395 claim, citing the line that calls `full_match`.
_FULL_MATCH_EXISTS = json.dumps(
    [
        {
            "finding_id": 1,
            "status": "INVALIDATED",
            "verified": False,
            "invalidated": True,
            "citation_line": 395,
            "confidence_score": 0.9,
            "reason": "`PurePath.full_match` exists on Python 3.13 and later and the project "
            "requires 3.14, so `posix.full_match(pattern)` raises no AttributeError.",
        }
    ]
)


@pytest.mark.parametrize(
    ("reply", "finish_reason", "outcome"),
    [
        (_FULL_MATCH_EXISTS, "length", ("UNVERIFIED", None, None, "verifier-reply-cut")),
        ("[]", "stop", ("UNVERIFIED", None, None, "verifier-no-verdict")),
        (_FULL_MATCH_EXISTS, "stop", ("INVALIDATED", "llm", 0.9, None)),
    ],
    ids=["cut", "no-verdict", "refuted"],
)
def test_criteria_that_assert_the_opposite_of_the_claim_leave_it_to_the_verifier(
    reply: str,
    finish_reason: str,
    outcome: tuple[str, str | None, float | None, str | None],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Golden S8 chunker.py:395: a false claim that `PurePosixPath` has no `full_match`, whose
    verification criteria assert the function returns the right value and pass. They count as
    evidence and are recorded, and the verifier judges the finding: a cut reply or one without a
    verdict leaves it unverified with that note, and a refutation invalidates it (#1043).

    Before, it ended VERIFIED by criteria at confidence 1.0 and the verifier never saw it."""
    finding = _golden("chunker-full-match", tmp_path, monkeypatch)
    client = _verifier(reply, finish_reason)

    judged = _verify(finding, client, tmp_path, monkeypatch)

    assert (
        _shown(client),
        (judged.status, judged.verified_by, judged.confidence_score, judged.verification_note),
        judged.verified_criteria_matched,
    ) == (
        [[finding.location]],
        outcome,
        [c.command for c in finding.verification_criteria],
    )


def test_a_passing_run_of_the_cited_test_refutes_the_claim_that_it_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Golden S8 test_rag_multi_project_indexer.py:66: the invalidation criterion calls the test
    that spans the cited line, whose own asserts are the check, and it passed. The finding ends
    INVALIDATED by criteria and the verifier is not asked (#1043). Before, the command did not
    count, and the verifier's reply was cut."""
    finding = _golden("test-rag-indexing", tmp_path, monkeypatch)
    command = finding.invalidation_criteria[0].command
    client = _verifier("[]")

    judged = _verify(finding, client, tmp_path, monkeypatch)

    assert (
        client.chat.called,
        _verdict(judged),
        judged.invalidated_criteria_matched,
        judged.invalidation_reason,
    ) == (
        False,
        _INVALIDATED_BY_CRITERIA,
        [command],
        f"Invalidation criterion verified: {command}",
    )


def test_a_passing_run_of_the_cited_test_does_not_confirm_a_claim_against_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Golden tests/test_pipeline_protocol.py:114 (20260928-201857): a claim that the test is
    wrong, whose verification criterion calls that test. The pass counts and is recorded, and
    the finding stays unverified without a note, which leaves it to the verifier; that session
    VERIFIED it by criteria (#1043). At this tip the catalog's masked-secret entry settles the
    finding before its criteria run, so the criteria are replayed on their own."""
    finding = _golden("pipeline-protocol-masking", tmp_path, monkeypatch)

    updated = execute_finding_criteria(finding, repo_root=tmp_path)

    assert (_verdict(updated), updated.verified_criteria_matched, updated.verification_note) == (
        _NO_VERDICT,
        [finding.verification_criteria[0].command],
        None,
    )


_INDEXER_TEST = "from tests.test_rag_multi_project_indexer import"


@pytest.mark.parametrize(
    ("command", "counts"),
    [
        (_DIRECTION["test-rag-indexing"]["finding"]["invalidation_criteria"][0]["command"], True),
        (f"python -c '{_INDEXER_TEST} test_multi_project_indexing as run; run(None)'", True),
        # Another test of the module: the one that spans line 13.
        (
            f"python -c '{_INDEXER_TEST} test_detect_project_name; test_detect_project_name(None)'",
            False,
        ),
        # A failure the script catches, or hands to a function, is not the command's.
        (
            f"python -c '{_INDEXER_TEST} test_multi_project_indexing\\ntry:\\n"
            "    test_multi_project_indexing(None)\\nexcept Exception:\\n    pass'",
            False,
        ),
        (
            f"python -c 'import pytest; {_INDEXER_TEST} test_multi_project_indexing; "
            "pytest.raises(TypeError, test_multi_project_indexing)'",
            False,
        ),
    ],
    ids=["s8", "alias", "another-test", "caught", "handed-on"],
)
def test_a_bare_call_of_the_test_that_spans_the_cited_line_counts(
    command: str, counts: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A `python -c` script that calls, as a statement of its own, the test whose definition
    spans the cited line, imported from the cited test module, checks the cited code: the
    test's asserts fail the command (#1043)."""
    finding = _golden("test-rag-indexing", tmp_path, monkeypatch)

    assert counts_as_evidence(command, finding.location, tmp_path) is counts


@pytest.mark.parametrize(
    ("path", "source", "command"),
    [
        ("app.py", "\ndef f(x):\n    return x + 1\n", "python -c 'from app import f; f(1)'"),
        (
            "app.py",
            "\ndef test_f():\n    assert False\n",
            "python -c 'from app import test_f; test_f()'",
        ),
        (
            "tests/test_app.py",
            "\ndef make_app():\n    assert False\n",
            "python -c 'from tests.test_app import make_app; make_app()'",
        ),
        (
            "tests/test_app.py",
            "\nasync def test_f():\n    assert False\n",
            "python -c 'from tests.test_app import test_f; test_f()'",
        ),
    ],
    ids=["function", "test-named-outside-tests", "helper-of-a-test-module", "async-test"],
)
def test_a_bare_call_of_a_cited_function_that_is_not_a_test_never_counts(
    path: str, source: str, command: str, tmp_path: Path
) -> None:
    """A call that returns shows only that the function did not raise for those inputs. Only a
    test's own asserts make the call a check: not a function of a module pytest does not
    collect, not a test module's helper, and not an async test, whose bare call never runs it
    (#1043)."""
    cited = tmp_path / path
    cited.parent.mkdir(parents=True, exist_ok=True)
    cited.write_text(source, encoding="utf-8")

    assert counts_as_evidence(command, f"{path}:2", tmp_path) is False


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


_NOT_ALLOWLISTED = "is not in allowed criteria binaries"
_PYTEST_MODULE_REFUSED = "Python module pytest runs tests"
_PYTEST_CALL_REFUSED = "Python script runs pytest"
_PYTHON_SHAPE_REFUSED = (
    "A python criterion is `python -c <script>` or `python -m <module>`, "
    "with -c or -m as its first argument"
)
_FIND_ACTION_REFUSED = "runs a command or writes a file"


@pytest.mark.parametrize(
    ("command", "reason"),
    [
        ("pytest tests/test_app.py -k test_page", _NOT_ALLOWLISTED),
        ("rg -n page src", _NOT_ALLOWLISTED),
        ("file src/app.py", _NOT_ALLOWLISTED),
        ("python -m pytest tests/test_app.py -v", _PYTEST_MODULE_REFUSED),
        ("python3 -m pytest.__main__ tests/test_app.py", _PYTEST_MODULE_REFUSED),
        ("python -m pytest -c x tests/test_app.py", _PYTEST_MODULE_REFUSED),
        ("python -m _pytest.config tests/test_app.py", _PYTEST_MODULE_REFUSED),
        ("python -Bm pytest -c pyproject.toml tests/test_app.py", _PYTHON_SHAPE_REFUSED),
        ("python -Im pytest -c x tests/test_app.py", _PYTHON_SHAPE_REFUSED),
        ("python -c \"import pytest; pytest.main(['tests/test_app.py'])\"", _PYTEST_CALL_REFUSED),
        ("python -c 'import pytest as p; p.console_main()'", _PYTEST_CALL_REFUSED),
        ("python -c 'from pytest import main; main([])'", _PYTEST_CALL_REFUSED),
        (
            "python -c \"from _pytest.config import main; raise SystemExit(main(['tests']))\"",
            _PYTEST_CALL_REFUSED,
        ),
        ("python -c 'import _pytest.config; _pytest.config.main([])'", _PYTEST_CALL_REFUSED),
        ("python -c \"__import__('pytest').main(['tests/test_app.py'])\"", _PYTEST_CALL_REFUSED),
        (
            "python -c \"import importlib; importlib.import_module('_pytest.config').main([])\"",
            _PYTEST_CALL_REFUSED,
        ),
        ("find tests -name test_app.py -exec pytest -q {} +", _FIND_ACTION_REFUSED),
    ],
)
def test_pytest_rg_and_file_criteria_are_rejected_without_running(
    tmp_path: Path, command: str, reason: str
) -> None:
    """pytest in the forms the validator reads, rg and file are refused before the sandbox runs
    anything (#847).

    `python -m pytest` and `pytest.main` run the project's real tests under the 30 s python limit,
    and a `pytest.main` whose status is discarded passes whatever the tests do. `_pytest` is
    pytest's own package, and `find -exec` runs pytest from the repository's `.venv/bin`.
    """
    sandbox = _recording_sandbox()
    result = execute_criterion_command(command, cwd=tmp_path, sandbox=sandbox)
    criterion = VerificationCriterion.model_validate(command)
    assert (
        result.executable,
        result.exit_code,
        result.passed,
        reason in str(result.error),
        sandbox.execute.called,
        criterion.executable,
    ) == (False, None, False, True, False, False)


@pytest.mark.parametrize(
    "command",
    [
        "python -c 'import pytest; from app import f; pytest.raises(ValueError, f, -1)'",
        "python -c 'from tests.test_app import test_page; test_page()'",
        "python -c 'import pytest, app; app.main()'",
        "python -c 'import pytest; from app import main; main()'",
        "python -c \"import pytest; __import__('app').main()\"",
    ],
)
def test_python_criterion_may_import_pytest_without_running_it(command: str) -> None:
    """Importing pytest, or a test module that does, stays a valid criterion (#847)."""
    assert validate_criteria_command(command)[:2] == (True, None)


_FORBIDDEN_MODULE = "Forbidden module after -m"


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("python -m socket -c pass", (False, _FORBIDDEN_MODULE, False)),
        ("python -m http.server 8000", (False, _FORBIDDEN_MODULE, False)),
        (
            "python -Bc \"import subprocess; subprocess.run(['id', '-u'])\" -c pass",
            (False, _PYTHON_SHAPE_REFUSED, False),
        ),
        (
            "python -B -c 'from app import f; assert f(1) == 2'",
            (False, _PYTHON_SHAPE_REFUSED, False),
        ),
        ("python -cpass", (False, _PYTHON_SHAPE_REFUSED, False)),
        ("python -c", (False, _PYTHON_SHAPE_REFUSED, False)),
        ("python -c 'import sys' -m socket", (True, None, True)),
    ],
)
def test_python_criterion_runs_only_the_c_or_m_its_first_argument_names(
    tmp_path: Path, command: str, expected: tuple[bool, str | None, bool]
) -> None:
    """Python reads its own options up to the first `-c` or `-m`, inside a cluster such as `-Bc`
    too, and passes the rest to the script or module. A python criterion is accepted only with
    `-c` or `-m` as its first argument, so the script or module checked is the one that runs:
    `-Bc <script> -c pass` ran the first script unchecked, and a `-c` after `-m` does not hide the
    module (#847)."""
    sandbox = _recording_sandbox()
    result = execute_criterion_command(command, cwd=tmp_path, sandbox=sandbox)
    assert (result.executable, result.error, sandbox.execute.called) == expected


@pytest.mark.parametrize(
    "command",
    [
        "find . -name app.py -exec cat {} +",
        "find . -name app.py -execdir cat {} +",
        "find . -name app.py -ok cat {} +",
        "find . -name app.py -okdir cat {} +",
        "find . -name app.py -delete",
        "find . -name app.py -fprint found.txt",
        "find . -name app.py -fprint0 found.txt",
        "find . -name app.py -fprintf found.txt %p",
        "find . -name app.py -fls found.txt",
    ],
)
def test_a_find_criterion_that_runs_or_writes_is_rejected_without_running(
    tmp_path: Path, command: str
) -> None:
    """`find` may search, but not run a command (`-exec`, which reaches any binary, not only the
    allowlisted ones) or write and delete files (#847)."""
    sandbox = _recording_sandbox()
    result = execute_criterion_command(command, cwd=tmp_path, sandbox=sandbox)
    assert (
        result.executable,
        _FIND_ACTION_REFUSED in str(result.error),
        sandbox.execute.called,
    ) == (False, True, False)


def test_python_criteria_get_the_measured_timeout_and_other_commands_keep_five_seconds(
    tmp_path: Path,
) -> None:
    """python and python3 criteria run under their measured limit; grep and git keep 5 s (#847)."""
    from devops_cli.config.defaults import DEFAULT_CRITERIA_PYTHON_TIMEOUT_SECONDS

    sandbox = _recording_sandbox()
    commands = ("python -c pass", "python3 -c pass", "git status", "grep -n page app.py")
    for command in commands:
        execute_criterion_command(command, cwd=tmp_path, sandbox=sandbox)
    execute_criterion_command("python -c pass", cwd=tmp_path, sandbox=sandbox, timeout=0.5)
    timeouts = [call.kwargs["timeout"] for call in sandbox.execute.call_args_list]
    assert (timeouts, DEFAULT_CRITERIA_EXECUTION_TIMEOUT_SECONDS) == (
        [
            DEFAULT_CRITERIA_PYTHON_TIMEOUT_SECONDS,
            DEFAULT_CRITERIA_PYTHON_TIMEOUT_SECONDS,
            5.0,
            5.0,
            0.5,
        ],
        5.0,
    )


@pytest.mark.parametrize("prompt", ["review.md", "review_output_instruction.md"])
def test_criteria_rule_in_the_prompts_offers_no_pytest_command(prompt: str) -> None:
    """The reviewer is not invited to write a pytest criterion the executor refuses (#847)."""
    tasks = Path(__file__).resolve().parents[1] / "src" / "devops_cli" / "ai" / "tasks"
    rule = next(
        line
        for line in (tasks / prompt).read_text(encoding="utf-8").splitlines()
        if "imports the cited code" in line
    )
    assert ("`python -c`" in rule, "pytest" in rule) == (True, False)
