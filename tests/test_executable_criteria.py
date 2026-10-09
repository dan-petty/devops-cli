"""Unit tests for the criteria command allowlist and the criterion models."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.review.review_environment import (
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
def test_pytest_rg_and_file_criteria_are_rejected(command: str, reason: str) -> None:
    """pytest in the forms the validator reads, rg and file are refused (#847).

    `python -m pytest` and `pytest.main` run the project's real tests, and a `pytest.main` whose
    status is discarded passes whatever the tests do. `_pytest` is pytest's own package, and
    `find -exec` runs pytest from the repository's `.venv/bin`.
    """
    valid, error, _ = validate_criteria_command(command)
    criterion = VerificationCriterion.model_validate(command)
    assert (valid, reason in str(error), criterion.executable) == (False, True, False)


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
        ("python -m socket -c pass", (False, _FORBIDDEN_MODULE)),
        ("python -m http.server 8000", (False, _FORBIDDEN_MODULE)),
        (
            "python -Bc \"import subprocess; subprocess.run(['id', '-u'])\" -c pass",
            (False, _PYTHON_SHAPE_REFUSED),
        ),
        (
            "python -B -c 'from app import f; assert f(1) == 2'",
            (False, _PYTHON_SHAPE_REFUSED),
        ),
        ("python -cpass", (False, _PYTHON_SHAPE_REFUSED)),
        ("python -c", (False, _PYTHON_SHAPE_REFUSED)),
        ("python -c 'import sys' -m socket", (True, None)),
    ],
)
def test_python_criterion_runs_only_the_c_or_m_its_first_argument_names(
    command: str, expected: tuple[bool, str | None]
) -> None:
    """Python reads its own options up to the first `-c` or `-m`, inside a cluster such as `-Bc`
    too, and passes the rest to the script or module. A python criterion is accepted only with
    `-c` or `-m` as its first argument, so the script or module checked is the one that runs:
    `-Bc <script> -c pass` ran the first script unchecked, and a `-c` after `-m` does not hide the
    module (#847)."""
    assert validate_criteria_command(command)[:2] == expected


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
def test_a_find_criterion_that_runs_or_writes_is_rejected(command: str) -> None:
    """`find` may search, but not run a command (`-exec`, which reaches any binary, not only the
    allowlisted ones) or write and delete files (#847)."""
    valid, error, _ = validate_criteria_command(command)
    assert (valid, _FIND_ACTION_REFUSED in str(error)) == (False, True)


@pytest.mark.parametrize("prompt", ["review.md", "review_output_instruction.md"])
def test_criteria_rule_in_the_prompts_offers_no_pytest_command(prompt: str) -> None:
    """The reviewer is not invited to write a pytest criterion the validator refuses (#847)."""
    tasks = Path(__file__).resolve().parents[1] / "src" / "devops_cli" / "ai" / "tasks"
    rule = next(
        line
        for line in (tasks / prompt).read_text(encoding="utf-8").splitlines()
        if "imports the cited code" in line
    )
    assert ("`python -c`" in rule, "pytest" in rule) == (True, False)
