"""Tests for devops ci command group."""

from __future__ import annotations

import asyncio
import configparser
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
import tomllib
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest
import typer
from packaging.requirements import Requirement
from typer.testing import CliRunner

from devops_cli.commands import ci as ci_module
from devops_cli.commands.ci import (
    CheckResult,
    CheckSpec,
    app,
    get_check_spec,
    get_check_specs,
    resolve_selected_specs,
    resolve_step_rows,
)
from devops_cli.config.constants import CONST_BANDIT_INI_NAME, CONST_EXIT_CANCELLED
from devops_cli.config.defaults import (
    DEFAULT_CI_BANDIT_NICENESS,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.core import process as process_module
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import find_top_level_repo_root
from devops_cli.lang import MESSAGES
from tests.support.hung_children import (
    fake_program,
    hung_with_grandchild,
    interrupted_like_pytest,
    mark_second_signal,
    records_after_second_signal,
    records_stop_signals,
    watching,
)
from tests.support.paths import FIXTURES, REPO_ROOT
from tests.support.session_spawns import RecordedSpawn, record_spawns
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS, wait_until, wait_while_running

pytestmark = [
    pytest.mark.usefixtures("refuse_nested_test_runs"),
    pytest.mark.live("devops", "bash", "python", "ruff"),
]

runner = CliRunner()


def test_ci_audit_command(monkeypatch) -> None:
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", mock_run)

    result = runner.invoke(app, ["audit"])
    assert result.exit_code == 0
    assert [cmd[0] for cmd in called] == ["uv", "npm", "npm"]
    assert any("uv" in c and "audit" in c for c in called)


def test_the_audit_check_audits_uv_and_the_lockfile_of_each_node_tool_without_a_shell() -> None:
    """One check carries both audits as argument lists, each started on its own: `uv audit` of
    `uv.lock`, and `npm audit` of the lockfile in the repository's copy of the lock directory,
    which needs no install."""
    assert get_check_spec("audit").commands == [
        ["uv", "audit"],
        [
            "npm",
            "audit",
            "--package-lock-only",
            "--json",
            "--no-update-notifier",
            "--prefix",
            "src/devops_cli/tools_lock/openspec",
        ],
        [
            "npm",
            "audit",
            "--package-lock-only",
            "--json",
            "--no-update-notifier",
            "--prefix",
            "src/devops_cli/tools_lock/devcontainers-cli",
        ],
    ]


@pytest.mark.parametrize("failing", ["uv", "npm"])
def test_the_audit_command_fails_when_either_audit_fails_and_still_runs_the_other(
    monkeypatch: pytest.MonkeyPatch, failing: str
) -> None:
    """A vulnerable pin fails the command, and a vulnerable Python dependency does not hide it."""
    called: list[str] = []

    def run(cmd: list[str], *args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        called.append(cmd[0])
        return subprocess.CompletedProcess(cmd, 1 if cmd[0] == failing else 0, "", "")

    monkeypatch.setattr("subprocess.run", run)

    result = runner.invoke(app, ["audit"])

    assert (result.exit_code, called) == (1, ["uv", "npm", "npm"])


_NPM_AUDIT_READINGS = [
    ("vulnerable", "found vulnerabilities (npm audit exited 1)", "could not run"),
    ("registry_unreachable", "could not run (npm audit exited 1)", "found vulnerabilities"),
    ("advisory_endpoint_missing", "could not run (npm audit exited 1)", "found vulnerabilities"),
]


def _answer_npm_audit_with(monkeypatch: pytest.MonkeyPatch, recording: str) -> None:
    """Answer `npm audit` with exit 1 and a report recorded from npm, every other command with
    success."""
    report = (FIXTURES / "npm_audit" / f"{recording}.json").read_text(encoding="utf-8")

    def run(cmd: list[str], *args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return (
            subprocess.CompletedProcess(cmd, 1, report, "")
            if cmd[0] == "npm"
            else subprocess.CompletedProcess(cmd, 0, "", "")
        )

    monkeypatch.setattr("subprocess.run", run)


@pytest.mark.parametrize(("recording", "reported", "not_reported"), _NPM_AUDIT_READINGS)
def test_the_audit_command_says_whether_npm_audit_found_vulnerabilities_or_could_not_run(
    monkeypatch: pytest.MonkeyPatch, recording: str, reported: str, not_reported: str
) -> None:
    """The command reads npm's report as `devops ci maintain` does, so a registry that cannot be
    reached is not reported as a vulnerable pin."""
    _answer_npm_audit_with(monkeypatch, recording)

    result = runner.invoke(app, ["audit"])

    said = " ".join(result.output.split())
    assert (result.exit_code, reported in said, not_reported in said) == (1, True, False)


@pytest.mark.parametrize(("recording", "reported", "not_reported"), _NPM_AUDIT_READINGS)
def test_the_gate_row_of_the_audit_check_reads_npm_audit_as_the_audit_command_does(
    monkeypatch: pytest.MonkeyPatch, recording: str, reported: str, not_reported: str
) -> None:
    """A single check run, `devops ci --only audit`, fails its row and gives the same reading
    under the check's output."""
    _answer_npm_audit_with(monkeypatch, recording)

    result = runner.invoke(app, ["--only", "audit", "--check", "--no-cache"])

    said = " ".join(result.output.split())
    assert (result.exit_code, reported in said, not_reported in said) == (1, True, False)


def test_the_audit_command_plans_both_audits_in_a_dry_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--dry-run` lists both commands as one plan and starts neither."""
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: pytest.fail("started a process"))

    result = runner.invoke(app, ["audit", "--dry-run"])

    assert (
        result.exit_code,
        "1. uv --preview-features" in result.output,
        "2. npm audit" in result.output,
    ) == (
        0,
        True,
        True,
    )


@pytest.mark.asyncio
async def test_a_check_with_two_commands_runs_both_and_fails_when_either_fails() -> None:
    """The gate's row passes only when every command of its check exits 0, and reports the output
    of all of them in the order they ran."""
    import contextlib

    ran: list[list[str]] = []

    @contextlib.contextmanager
    def dummy_span(*a: Any, **kw: Any) -> Any:
        yield

    async def run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        ran.append(cmd)
        return subprocess.CompletedProcess(
            cmd, 1 if cmd[0] == "npm" else 0, f"{cmd[0]} out\n", f"{cmd[0]} err\n"
        )

    with (
        patch("devops_cli.commands.ci.trace_span", side_effect=dummy_span),
        patch("devops_cli.core.process.run_subprocess_async", side_effect=run),
        patch("devops_cli.commands.ci.print_muted"),
    ):
        result = await ci_module._execute_check_async(
            CheckSpec(
                name="pair",
                display_title="pair",
                cmd=["uv", "one"],
                also_cmds=[["npm", "two"]],
                span_name="ci.step.pair",
                metric_step="pair",
            )
        )

    assert (result.passed, result.stdout, result.stderr, [cmd[0] for cmd in ran]) == (
        False,
        "uv out\nnpm out\n",
        "uv err\nnpm err\n",
        ["uv", "npm"],
    )


def test_ci_coverage_command(monkeypatch) -> None:
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", mock_run)

    result = runner.invoke(app, ["coverage", "--html"])
    assert result.exit_code == 0
    assert any("--cov=src" in c and "--cov-report=html" in c for c in called)


def test_ci_security_command(monkeypatch) -> None:
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", mock_run)

    result = runner.invoke(app, ["security", "-s", "high"])
    bandit_runs = [c[c.index("bandit") :] for c in called if "bandit" in c]
    assert (result.exit_code, bandit_runs) == (
        0,
        [
            ["bandit", "-r", "src", "--ini", CONST_BANDIT_INI_NAME, "--severity-level", "low"],
            ["bandit", "-r", "tests", "--ini", CONST_BANDIT_INI_NAME, "--severity-level", "high"],
        ],
    )


def test_the_gate_starts_bandit_below_the_test_row_s_priority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The test row is the full gate's critical path, so the gate starts Bandit, which runs beside
    its workers, under `nice`, and the test row at normal priority (#1725). `devops ci security`
    runs the same row (`test_subcommand_dispatches_exact_table_row_cmd`)."""
    spawns = record_spawns(monkeypatch)
    for row in ("security", "test"):
        asyncio.run(ci_module._execute_check_async(get_check_spec(row)))

    *gate_security, gate_test = (spawn.argv for spawn in spawns)
    niced = ["nice", "-n", str(DEFAULT_CI_BANDIT_NICENESS)]
    assert (
        [argv[argv.index("run") + 1 : argv.index("bandit")] for argv in gate_security],
        [argv[argv.index("bandit") :] for argv in gate_security],
        "nice" in gate_test,
    ) == (
        [niced, niced],
        [
            ["bandit", "-r", "src", "--ini", CONST_BANDIT_INI_NAME, "--severity-level", "low"],
            ["bandit", "-r", "tests", "--ini", CONST_BANDIT_INI_NAME, "--severity-level", "medium"],
        ],
        False,
    )


def test_the_security_row_scans_the_targets_that_bandit_s_config_names() -> None:
    """The gate names its Bandit targets on the command line, so it holds them to the targets of
    `.bandit`, which `devops scan report` and a person's `bandit -r --ini .bandit` read (#1538)."""
    config = configparser.ConfigParser()
    config.read(REPO_ROOT / CONST_BANDIT_INI_NAME, encoding="utf-8")
    targets = [argv[argv.index("-r") + 1] for argv in get_check_spec("security").commands]
    assert targets == config.get("bandit", "targets").split(",")


def test_bandit_s_config_skips_only_the_low_rules_that_need_no_decision() -> None:
    """B404 and B603 are list-form process calls without a shell, which a CLI that runs tools has;
    the swallowed-failures ratchet counts B110 and B112 through Ruff. All four are low severity, so
    the medium run over `tests/` is the same with or without them (#1538)."""
    config = configparser.ConfigParser()
    config.read(REPO_ROOT / CONST_BANDIT_INI_NAME, encoding="utf-8")
    skips = config.get("bandit", "skips", fallback="")
    assert sorted(rule.strip() for rule in skips.split(",") if rule.strip()) == [
        "B110",
        "B112",
        "B404",
        "B603",
    ]


def test_ci_security_runs_every_command_of_its_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """`devops ci security` runs both Bandit runs of the row, and the second after a failed
    first, so one run shows every finding (#1538)."""
    executed: list[list[str]] = []

    def mock_run(cmd: list[str], *a: Any, **kw: Any) -> subprocess.CompletedProcess[str]:
        executed.append(cmd)
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr(subprocess, "run", mock_run)
    monkeypatch.setattr(ci_module, "run_subprocess", mock_run)

    result = runner.invoke(app, ["security"])
    expected = [ci_module._with_uv_preview(cmd) for cmd in get_check_spec("security").commands]
    assert (result.exit_code, [c for c in executed if "bandit" in c]) == (1, expected)


def test_ci_actionlint_command(monkeypatch) -> None:
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", mock_run)

    result = runner.invoke(app, ["actionlint"])
    assert result.exit_code == 0
    assert any("actionlint" in c for c in called)


def test_ci_lint_command(monkeypatch) -> None:
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", mock_run)

    # By default, lint applies autofixes
    result = runner.invoke(app, ["lint"])
    assert result.exit_code == 0
    assert any("ruff" in c and "check" in c and "--fix" in c for c in called)

    # With --check, lint verifies without applying fixes
    called.clear()
    result_check = runner.invoke(app, ["lint", "--check"])
    assert result_check.exit_code == 0
    assert any("ruff" in c and "check" in c and "--fix" not in c for c in called)


def test_ci_format_command(monkeypatch) -> None:
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", mock_run)

    # By default, format formats in-place
    result = runner.invoke(app, ["format"])
    assert result.exit_code == 0
    assert any("ruff" in c and "format" in c and "--check" not in c for c in called)

    # With --check, format verifies without modifying
    called.clear()
    result_check = runner.invoke(app, ["format", "--check"])
    assert result_check.exit_code == 0
    assert any("ruff" in c and "format" in c and "--check" in c for c in called)


def test_ci_typecheck_command(monkeypatch) -> None:
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", mock_run)

    result = runner.invoke(app, ["typecheck"])
    assert result.exit_code == 0
    assert any("mypy" in c and "--python-version" in c and "3.14" in c for c in called)


def test_ci_test_command(monkeypatch) -> None:
    spawns = record_spawns(monkeypatch)

    result = runner.invoke(app, ["test", "-v", "-k", "unit"])
    assert result.exit_code == 0
    assert any("pytest" in s.argv and "-v" in s.argv and "-k" in s.argv for s in spawns)


def test_ci_docs_command(monkeypatch) -> None:
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", mock_run)

    result = runner.invoke(app, ["docs"])
    assert result.exit_code == 0
    assert any("devops" in c and "docs" in c and "check" in c for c in called)


def test_ci_uv_check_command(monkeypatch) -> None:
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", mock_run)

    result = runner.invoke(app, ["uv-check"])
    assert (result.exit_code, any("uv" in c and "check" in c for c in called)) == (0, True)


def test_ci_uv_check_type_checks_with_the_ty_the_lockfile_pins() -> None:
    """`uv check` runs the exact `ty` that `uv.lock` resolves when `ty` is in the dev group, so a
    new `ty` release cannot fail `main` with no change in the repository (#2281)."""
    dev = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "dependency-groups"
    ]["dev"]
    lock = tomllib.loads((REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))["package"]
    pinned = [str(req.specifier) for req in map(Requirement, dev) if req.name == "ty"]
    locked = [package["version"] for package in lock if package["name"] == "ty"]

    assert pinned == [f"=={version}" for version in locked]
    assert len(locked) == 1


def test_ci_lockfile_command(monkeypatch) -> None:
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", mock_run)

    result = runner.invoke(app, ["lockfile"])
    assert (result.exit_code, any("lock" in c and "--check" in c for c in called)) == (0, True)


def test_the_gate_builds_the_wheel_and_sdist_beside_the_lock_check() -> None:
    """A green gate means the package builds and the lock matches, so the release pull request,
    whose only change is the version, cannot merge a tree that does not build."""
    rows = [spec.name for spec in get_check_specs()]
    assert (get_check_spec("build").cmd, rows.index("build") - rows.index("lockfile")) == (
        ["uv", "build", "--quiet"],
        1,
    )


def test_ci_outdated_command(monkeypatch) -> None:
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", mock_run)

    result = runner.invoke(app, ["outdated"])
    assert (result.exit_code, any("tree" in c and "--outdated" in c for c in called)) == (0, True)


def test_ci_uv_check_and_lockfile_failures(monkeypatch) -> None:
    def mock_run_fail(cmd, *args, **kwargs):
        return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="failed")

    monkeypatch.setattr("subprocess.run", mock_run_fail)

    res_uv = runner.invoke(app, ["uv-check"])
    res_lock = runner.invoke(app, ["lockfile"])
    res_outdated = runner.invoke(app, ["outdated"])
    assert (res_uv.exit_code, res_lock.exit_code, res_outdated.exit_code) == (1, 1, 1)


def test_ci_python_version_check_failure(monkeypatch) -> None:
    monkeypatch.setattr(sys, "version_info", (3, 12, 0))

    result = runner.invoke(app, ["typecheck"])
    assert result.exit_code == 1
    assert "Strict Python 3.14+ requirement failed" in result.output


def test_ci_all_checks_includes_audit_coverage_and_security() -> None:
    called: list[list[str]] = []

    async def mock_exec(spec: CheckSpec | str, *args: Any, **kwargs: Any) -> CheckResult:
        if isinstance(spec, CheckSpec):
            name = spec.name
            display_title = spec.display_title
            cmd = spec.cmd
        else:
            name = spec
            display_title = args[0] if args else kwargs.get("display_title", spec)
            cmd = args[1] if len(args) > 1 else kwargs.get("cmd", [])
        called.append(cmd)
        return CheckResult(
            name=name,
            display_title=display_title,
            passed=True,
            duration_seconds=0.01,
        )

    with (
        patch("devops_cli.commands.ci._execute_check_async", side_effect=mock_exec),
        patch("devops_cli.docs.generator.DocGenerator.check_docs", return_value=(True, [])),
    ):
        result = runner.invoke(app, ["--no-cache"])
        assert result.exit_code == 0
        assert "audit" in result.output
        assert "coverage" in result.output
        assert "security" in result.output
        assert "actionlint" in result.output
        assert "uv-check" in result.output.lower() or "uv_check" in result.output.lower()
        assert "lockfile" in result.output.lower()
        assert "outdated" in result.output.lower()
        assert (
            any("audit" in c for c in called),
            any("bandit" in c for c in called),
            any("actionlint" in c for c in called),
            any("check" in c and "uv" in c for c in called),
            any("lock" in c and "--check" in c for c in called),
            any("tree" in c and "--outdated" in c for c in called),
            any("ruff" in c and "format" in c and "--check" not in c for c in called),
            any("ruff" in c and "check" in c and "--fix" in c for c in called),
        ) == (True, True, True, True, True, True, True, True)


def test_ci_all_checks_with_check_flag() -> None:
    called: list[list[str]] = []

    async def mock_exec(spec: CheckSpec | str, *args: Any, **kwargs: Any) -> CheckResult:
        if isinstance(spec, CheckSpec):
            name = spec.name
            display_title = spec.display_title
            cmd = spec.cmd
        else:
            name = spec
            display_title = args[0] if args else kwargs.get("display_title", spec)
            cmd = args[1] if len(args) > 1 else kwargs.get("cmd", [])
        called.append(cmd)
        return CheckResult(
            name=name,
            display_title=display_title,
            passed=True,
            duration_seconds=0.01,
        )

    with (
        patch("devops_cli.commands.ci._execute_check_async", side_effect=mock_exec),
        patch("devops_cli.docs.generator.DocGenerator.check_docs", return_value=(True, [])),
    ):
        result = runner.invoke(app, ["--check", "--no-cache"])
        assert result.exit_code == 0
        # In check-only mode, in-place format_fix and lint_fix are not run
        format_or_lint_fixes = [
            c
            for c in called
            if ("format" in c and "--check" not in c) or ("check" in c and "--fix" in c)
        ]
        assert len(format_or_lint_fixes) == 0


def test_ci_failure_branches_and_filters() -> None:
    """Verify non-zero returncode handling for each check."""
    mock_fail_proc = subprocess.CompletedProcess(
        args=["uv"], returncode=1, stdout="", stderr="failed"
    )
    with patch("devops_cli.commands.ci.run_subprocess", return_value=mock_fail_proc):
        res_audit_fail = runner.invoke(app, ["audit"])
        res_sec_fail = runner.invoke(app, ["security"])
        res_lint_fail = runner.invoke(app, ["lint"])
        res_type_fail = runner.invoke(app, ["typecheck"])
        res_doc_fail = runner.invoke(app, ["docs"])
        res_uv_check_fail = runner.invoke(app, ["uv-check"])
        res_lockfile_fail = runner.invoke(app, ["lockfile"])
        assert (
            res_audit_fail.exit_code,
            res_sec_fail.exit_code,
            res_lint_fail.exit_code,
            res_type_fail.exit_code,
            res_doc_fail.exit_code,
            res_uv_check_fail.exit_code,
            res_lockfile_fail.exit_code,
        ) == (1, 1, 1, 1, 1, 1, 1)


def test_ci_additional_subcommands(monkeypatch) -> None:
    """Verify ci run, ci test, ci format --fix, and ci version."""
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    # 1. test subcommand, whose pytest starts through asyncio in a session of its own
    spawns = record_spawns(monkeypatch)
    res_test = runner.invoke(app, ["test", "-n", "2"])
    assert res_test.exit_code == 0
    assert any("pytest" in s.argv and "-n" in s.argv for s in spawns)

    monkeypatch.setattr("subprocess.run", mock_run)

    # 2. format --fix
    res_fmt_fix = runner.invoke(app, ["format", "--fix"])
    assert res_fmt_fix.exit_code == 0
    assert any("ruff" in c and "format" in c and "--check" not in c for c in called)

    # 3. docs subcommand
    res_docs = runner.invoke(app, ["docs"])
    assert res_docs.exit_code == 0

    # 4. run subcommand with --fix
    with (
        patch(
            "devops_cli.commands.ci._execute_check_async",
            return_value=CheckResult(
                name="mock",
                display_title="Mock",
                passed=True,
                duration_seconds=0.01,
            ),
        ),
        patch("devops_cli.docs.generator.DocGenerator.check_docs", return_value=(True, [])),
    ):
        res_run_fix = runner.invoke(app, ["run", "--fix"])
        assert res_run_fix.exit_code == 0


def test_ci_helpers_and_edge_cases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _run_all_checks, _print_failures, _clean_coverage_artifacts, and option parsing."""
    from devops_cli.commands.ci import (
        CheckResult,
        _clean_coverage_artifacts,
        _print_failures,
        _print_summary,
        _run_all_checks,
    )

    # 1. _clean_coverage_artifacts
    cov_file = tmp_path / ".coverage.test1"
    cov_file.write_text("test", encoding="utf-8")
    with patch("devops_cli.commands.ci._get_project_root", return_value=tmp_path):
        _clean_coverage_artifacts(force=True)
        assert not cov_file.exists()

    # 2. _print_failures and _print_summary
    results = [
        CheckResult(
            name="test",
            display_title="Unit Tests",
            passed=False,
            duration_seconds=1.5,
            stdout="AssertionError in test_x",
            stderr="Traceback...",
        ),
        CheckResult(
            name="lint",
            display_title="Ruff Lint",
            passed=True,
            duration_seconds=0.5,
        ),
    ]
    _print_failures(results)
    _print_summary(results, total_elapsed=2.0)

    # 3. _run_all_checks synchronous execution
    with patch(
        "devops_cli.commands.ci._execute_check_async",
        return_value=CheckResult(
            name="mock_check",
            display_title="Mock",
            passed=True,
            duration_seconds=0.1,
        ),
    ):
        summary_results = _run_all_checks(lint_fix=False, format_fix=False)
        assert len(summary_results) >= 1

    # 4. test command with invalid -k filter
    res_bad_k = runner.invoke(app, ["test", "-k", "-invalid"])
    assert res_bad_k.exit_code == 1

    # 5. security with low and medium severity
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    spawns = record_spawns(monkeypatch)
    with patch("devops_cli.commands.ci.run_subprocess", side_effect=mock_run):
        res_sec_low = runner.invoke(app, ["security", "-s", "low"])
        assert res_sec_low.exit_code == 0
        assert any(c[-2:] == ["--severity-level", "low"] for c in called)

        res_sec_med = runner.invoke(app, ["security", "-s", "medium"])
        assert res_sec_med.exit_code == 0
        assert any(c[-2:] == ["--severity-level", "medium"] for c in called)

        # test with -x and -v
        res_test_xv = runner.invoke(app, ["test", "-x", "-v"])
        assert res_test_xv.exit_code == 0
        assert any("-x" in s.argv and "-v" in s.argv for s in spawns)

        # coverage default options
        res_cov = runner.invoke(app, ["coverage"])
        assert res_cov.exit_code == 0


def test_ci_clean_coverage_and_extended_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify _clean_coverage_artifacts, coverage --html, and run command."""
    from devops_cli.commands.ci import _clean_coverage_artifacts

    # 1. _clean_coverage_artifacts
    fake_data = tmp_path / ".data"
    fake_data.mkdir(parents=True, exist_ok=True)
    fake_cov = fake_data / ".coverage.sample"
    fake_cov.write_text("sample", encoding="utf-8")
    with patch("devops_cli.commands.ci._get_project_root", return_value=tmp_path):
        _clean_coverage_artifacts(force=True)
        assert not fake_cov.exists()

    # 2. coverage --html
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    spawns = record_spawns(monkeypatch)
    with patch("devops_cli.commands.ci.run_subprocess", side_effect=mock_run):
        res_cov_html = runner.invoke(app, ["coverage", "--html"])
        assert res_cov_html.exit_code == 0
        assert any("--cov-report=html" in c for c in called)

        res_test_k = runner.invoke(app, ["test", "-k", "unit_test"])
        assert res_test_k.exit_code == 0
        assert any("-k" in s.argv and "unit_test" in s.argv for s in spawns)

        # docs with --fix
        called.clear()
        res_docs_fix = runner.invoke(app, ["docs", "--fix"])
        assert res_docs_fix.exit_code == 0
        assert any("generate" in c for c in called)
        assert any("check" in c for c in called)


def test_ci_run_docs_fix_when_needed() -> None:
    """Verify that CI fix pipeline triggers doc generation when docs check fails."""
    import asyncio

    from devops_cli.commands.ci import CheckResult, _run_all_checks_async

    called_cmds = []

    async def mock_execute(spec: CheckSpec | str, *args: Any, **kwargs: Any) -> CheckResult:
        if isinstance(spec, CheckSpec):
            name = spec.name
            title = spec.display_title
            cmd = spec.cmd
            if kwargs.get("apply_fix") and spec.fix_cmd:
                called_cmds.append(spec.fix_cmd)
        else:
            name = spec
            title = args[0] if args else kwargs.get("display_title", spec)
            cmd = args[1] if len(args) > 1 else kwargs.get("cmd", [])
        called_cmds.append(cmd)
        return CheckResult(
            name=name,
            display_title=title,
            passed=True,
            duration_seconds=0.01,
        )

    with (
        patch("devops_cli.commands.ci._execute_check_async", side_effect=mock_execute),
        patch(
            "devops_cli.docs.generator.DocGenerator.check_docs",
            return_value=(False, ["Out of sync"]),
        ),
    ):
        results = asyncio.run(_run_all_checks_async(lint_fix=True, format_fix=True, docs_fix=True))
        assert any("generate" in cmd for cmd in called_cmds)
        assert any(r.name == "docs" for r in results)


def test_gate_test_step_argv_is_unchanged() -> None:
    """Verify that the gate's test step argv remains unchanged and does not pass --cov-context."""
    from devops_cli.commands.ci import _resolve_pytest_cmd, get_check_spec

    spec = get_check_spec("test")
    assert (
        spec.cmd,
        "--cov-context=test" in spec.cmd,
        any("COVERAGE_CORE" in c for c in spec.cmd),
    ) == (
        _resolve_pytest_cmd(),
        False,
        False,
    )


def test_the_gate_test_row_writes_the_term_report_and_no_xml_report() -> None:
    """Verify the gate's test row prints the term report and writes no XML report (#1743).

    Only CI's changed-line coverage step reads coverage.xml, and it writes the file itself from
    the combined data, so the gate spends no serial report pass on it.
    """
    from devops_cli.commands.ci import _resolve_pytest_cmd

    cmd = _resolve_pytest_cmd()
    assert (
        "--cov=src" in cmd,
        "--cov-report=term-missing" in cmd,
        [arg for arg in cmd if arg.startswith("--cov-report=xml")],
    ) == (True, True, [])


def test_gate_deps_step_spec() -> None:
    """Verify that the gate's deps step spec invokes deptry on src."""
    spec = get_check_spec("deps")
    assert (
        spec.cmd,
        spec.metric_step,
        spec.span_name,
    ) == (
        ["uv", "run", "deptry", "src"],
        "deps",
        "ci.step.deps",
    )


def _validate_setup_uv_step(step: dict[str, object], source: str) -> None:
    with_args = step.get("with", {})
    assert isinstance(with_args, dict), f"{source}: 'with' block must be a dict"
    assert with_args.get("enable-cache") is True, f"{source}: missing enable-cache"
    assert with_args.get("cache-python") == "true", f"{source}: missing cache-python: true"
    assert with_args.get("prune-cache") == "true", f"{source}: missing prune-cache: true"
    assert with_args.get("cache-dependency-glob") == "uv.lock", (
        f"{source}: missing uv.lock dependency glob"
    )


def _validate_uncached_setup_uv_step(step: dict[str, object], source: str) -> None:
    with_args = step.get("with", {})
    assert isinstance(with_args, dict), f"{source}: 'with' block must be a dict"
    assert {key: value for key, value in with_args.items() if "cache" in key} == {
        "enable-cache": False
    }, f"{source}: a publishing workflow restores no cache"


def test_github_workflows_caching_configuration() -> None:
    """Every workflow caches uv, except release.yml: it publishes every artifact, so it restores
    no cache that another run could have written (zizmor cache-poisoning, #1895)."""
    import yaml

    workflows_dir = Path(".github/workflows")
    assert workflows_dir.is_dir()

    for wf_file in sorted(workflows_dir.glob("*.yml")):
        content = yaml.safe_load(wf_file.read_text(encoding="utf-8")) or {}
        steps = [
            (job_name, step)
            for job_name, job_data in content.get("jobs", {}).items()
            if isinstance(job_data, dict)
            for step in job_data.get("steps", [])
            if isinstance(step, dict)
        ]
        for job_name, step in steps:
            uses = str(step.get("uses", ""))
            context_tag = f"{wf_file.name}:{job_name}:{step.get('name', 'unnamed')}"
            if "astral-sh/setup-uv" in uses and wf_file.name == "release.yml":
                _validate_uncached_setup_uv_step(step, context_tag)
            elif "astral-sh/setup-uv" in uses:
                _validate_setup_uv_step(step, context_tag)


def _installs_uv(uses: str) -> bool:
    """A step installs uv through setup-uv, directly or through a local composite action."""
    import yaml

    if "astral-sh/setup-uv" in uses:
        return True
    if not uses.startswith("./"):
        return False
    action = yaml.safe_load((Path(uses) / "action.yml").read_text(encoding="utf-8")) or {}
    return any(
        "astral-sh/setup-uv" in str(step.get("uses", "")) for step in action["runs"]["steps"]
    )


def test_github_workflows_name_their_runner_and_use_managed_python() -> None:
    """Every job names its runner image, and uv in CI runs only its own CPython builds.

    A `-latest` label moves to a new image without review, as ubuntu-latest moves to Ubuntu
    26.04 from 2026-10-19. setup-uv exports `UV_PYTHON=3.14`, so on an image whose own Python
    is a 3.14 uv would take that interpreter over the managed build `.python-version` pins
    unless `UV_MANAGED_PYTHON` restricts it (#1494).
    """
    import yaml

    latest_runners: list[str] = []
    uv_workflows: dict[str, bool] = {}
    for wf_file in sorted(Path(".github/workflows").glob("*.yml")):
        workflow = yaml.safe_load(wf_file.read_text(encoding="utf-8")) or {}
        jobs = {name: job for name, job in workflow["jobs"].items() if isinstance(job, dict)}
        latest_runners += [
            f"{wf_file.name}:{name}"
            for name, job in jobs.items()
            if "-latest" in str(job.get("runs-on", ""))
        ]
        if any(
            _installs_uv(str(step.get("uses", "")))
            for job in jobs.values()
            for step in job.get("steps", [])
            if isinstance(step, dict)
        ):
            uv_workflows[wf_file.name] = workflow.get("env", {}).get("UV_MANAGED_PYTHON") == "1"

    assert latest_runners == [], f"jobs on a -latest runner: {latest_runners}"
    # ci.yml reaches setup-uv only through the setup-toolchain composite action.
    assert {"ci.yml", "release.yml"} <= uv_workflows.keys()
    assert [name for name, managed in uv_workflows.items() if not managed] == [], (
        "workflows that run uv must set UV_MANAGED_PYTHON: '1' in their workflow-level env"
    )


def test_the_toolchain_compiles_bytecode_when_it_syncs() -> None:
    """The shared toolchain action's `uv sync` compiles the environment's bytecode once, in
    parallel, so each xdist worker of a fresh runner imports compiled modules instead of
    compiling the same ones itself (#1735)."""
    import yaml

    action = yaml.safe_load(
        Path(".github/actions/setup-toolchain/action.yml").read_text(encoding="utf-8")
    )
    syncs = [
        str(step.get("run", ""))
        for step in action["runs"]["steps"]
        if isinstance(step, dict) and str(step.get("run", "")).startswith("uv sync")
    ]

    assert (len(syncs), all("--compile-bytecode" in sync for sync in syncs)) == (1, True)


def test_ci_workflow_has_tooling_cache_step() -> None:
    """Validate the shared toolchain action caches incremental tool state with a stable key.

    Caching moved out of a single monolithic job into the composite setup action once the
    quality gate was split into parallel jobs, so every job restores the same tool state.
    """
    import yaml

    action_file = Path(".github/actions/setup-toolchain/action.yml")
    assert action_file.is_file()
    action = yaml.safe_load(action_file.read_text(encoding="utf-8")) or {}

    cache_steps = [
        s
        for s in action["runs"]["steps"]
        if isinstance(s, dict) and "actions/cache" in str(s.get("uses", ""))
    ]
    assert len(cache_steps) >= 1

    cache_with = cache_steps[0].get("with", {})
    cache_key = str(cache_with.get("key", ""))
    assert isinstance(cache_with, dict)
    assert "tooling-" in cache_key
    assert "hashFiles" in cache_key
    # A commit-scoped key would miss on every run, defeating the cache entirely.
    assert "github.sha" not in cache_key

    # Default paths cover the incremental type and lint caches; the test job overrides
    # them to cache pytest state instead.
    default_paths = str(action["inputs"]["tooling-cache-paths"]["default"])
    assert ".mypy_cache" in default_paths
    assert ".ruff_cache" in default_paths

    ci = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8")) or {}
    test_steps = ci["jobs"]["test"]["steps"]
    setup = next(s for s in test_steps if "setup-toolchain" in str(s.get("uses", "")))
    assert ".pytest_cache" in str(setup.get("with", {}).get("tooling-cache-paths", ""))


def _job_runs_on_event(workflow: dict[str, Any], job: dict[str, Any], event: str) -> bool:
    """Return True when a workflow triggers on `event` and `job` is not gated off `event`."""
    triggers = workflow.get("on") or workflow.get(True) or {}
    if event not in triggers:
        return False
    job_if = str(job.get("if", ""))
    if "github.event_name == 'schedule'" in job_if:
        return False
    if event == "pull_request" and "github.event_name == 'push'" in job_if:
        return False
    if event == "push" and "github.event_name == 'pull_request'" in job_if:
        return False
    return True


def _step_saves_uv_cache(step: dict[str, Any], default_composite_save: bool) -> bool:
    """Return True when a step invokes setup-uv or setup-toolchain and saves the uv cache."""
    uses = str(step.get("uses", ""))
    with_args = step.get("with") or {}
    if "astral-sh/setup-uv" in uses:
        if not with_args.get("enable-cache"):
            return False
        raw = with_args.get("save-cache", True)
        return str(raw).lower() != "false"
    if uses == "./.github/actions/setup-toolchain":
        raw = with_args.get("save-uv-cache", default_composite_save)
        return str(raw).lower() != "false"
    return False


def test_toolchain_cache_runs_on_node24_and_one_job_per_event_saves_uv_cache() -> None:
    """setup-toolchain pins Node 24 actions/cache v6.1.0, and at most one job per push/PR saves setup-uv cache (#1495)."""
    import yaml

    action = (
        yaml.safe_load(
            Path(".github/actions/setup-toolchain/action.yml").read_text(encoding="utf-8")
        )
        or {}
    )
    steps = action["runs"]["steps"]
    uv_step = next(s for s in steps if "astral-sh/setup-uv" in str(s.get("uses", "")))
    cache_step = next(s for s in steps if "actions/cache" in str(s.get("uses", "")))

    save_input = action.get("inputs", {}).get("save-uv-cache", {})
    default_save = str(save_input.get("default", "true")).lower() != "false"

    writers_by_event: dict[str, list[str]] = {"pull_request": [], "push": []}
    for wf_name in ("ci.yml", "release.yml"):
        wf = yaml.safe_load((Path(".github/workflows") / wf_name).read_text(encoding="utf-8")) or {}
        for job_id, job in wf.get("jobs", {}).items():
            if not isinstance(job, dict):
                continue
            saves = any(
                _step_saves_uv_cache(step, default_save)
                for step in job.get("steps", [])
                if isinstance(step, dict)
            )
            if not saves:
                continue
            for event in writers_by_event:
                if _job_runs_on_event(wf, job, event):
                    writers_by_event[event].append(f"{wf_name}:{job_id}")

    assert (
        cache_step.get("uses"),
        save_input.get("default"),
        uv_step.get("with", {}).get("save-cache"),
        writers_by_event,
    ) == (
        "actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9",
        "true",
        "${{ inputs.save-uv-cache }}",
        {"pull_request": ["ci.yml:static"], "push": ["ci.yml:static"]},
    )


def test_changed_line_coverage_step_fails_a_pull_request_below_ninety_percent() -> None:
    """Pull requests fail when under 90% of their changed lines are covered (#850, #2356).

    The step writes coverage.xml from the combined data that the gate keeps, before diff-cover
    reads it (#1743); the gate itself writes no XML. It runs only on pull requests,
    takes the base ref through env rather than an inline expression, and fails the job
    below 90% of the changed lines. The summary still gets the added `pragma: no cover` lines
    when the figure fails: the step keeps diff-cover's status and exits with it last. It is
    never part of `devops ci`, so no check row runs it.
    """
    import yaml

    ci = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8")) or {}
    steps = ci["jobs"]["test"]["steps"]
    names = [s.get("name") for s in steps]
    step = steps[names.index("Changed-Line Coverage")]
    run = str(step.get("run", ""))
    checkout = next(s for s in steps if "actions/checkout" in str(s.get("uses", "")))

    assert (
        names.index("Changed-Line Coverage") > names.index("Tests & Coverage Quality Gate"),
        step.get("if"),
        step.get("env"),
        "diff-cover .data/coverage.xml" in run and '--compare-branch="origin/${BASE_REF}"' in run,
        0 <= run.find("uv run coverage xml") < run.find("diff-cover .data/coverage.xml"),
        "GITHUB_STEP_SUMMARY" in run and "pragma: no cover" in run,
        "--fail-under 90" in run,
        0 <= run.find("pragma: no cover") < run.find('exit "$status"'),
        "${{" in run,
        checkout.get("with", {}).get("fetch-depth"),
        any("diff-cover" in " ".join(s.cmd) for s in get_check_specs()),
    ) == (
        True,
        "github.event_name == 'pull_request'",
        {"BASE_REF": "${{ github.base_ref }}"},
        True,
        True,
        True,
        True,
        True,
        False,
        0,
        False,
    )


def test_ci_workflow_parallelizes_quality_gates() -> None:
    """Static analysis, tests, and the image build run as independent parallel jobs.

    The image build is roughly half the wall clock but is not a quality gate, so keeping
    it off the critical path is what lets merge feedback arrive quickly.
    """
    import yaml

    ci = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8")) or {}
    jobs = ci["jobs"]

    assert {"static", "test", "devcontainer", "service-image"}.issubset(jobs.keys())
    # No `needs:` between them, so they start concurrently rather than in sequence.
    assert all(
        not jobs[name].get("needs") for name in ("static", "test", "devcontainer", "service-image")
    )


def test_the_devcontainer_image_is_built_for_a_pull_request_or_a_dispatch() -> None:
    """Every pull request targets main, so the job runs on the event alone; its own step skips
    the build when the change alters no image content."""
    import yaml

    ci = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8")) or {}

    assert ci["jobs"]["devcontainer"]["if"] == (
        "github.event_name == 'workflow_dispatch' || github.event_name == 'pull_request'"
    )


def test_service_image_ci_job_invariants() -> None:
    """The CI service-image job runs for every pull request or a dispatch, pushes nothing, and
    avoids ${{ in scripts. The release pull request builds here too: release.yml publishes the
    image only when release-please creates a release (#1486)."""
    import yaml

    ci = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8")) or {}
    job = ci["jobs"]["service-image"]

    assert (job.get("if"), job.get("permissions")) == (
        "github.event_name == 'workflow_dispatch' || github.event_name == 'pull_request'",
        {"contents": "read"},
    )

    build_step = next(s for s in job["steps"] if s.get("name") == "Build and Load Service Image")
    assert (
        build_step.get("with", {}).get("push") in (False, "false"),
        build_step.get("with", {}).get("load") in (True, "true"),
    ) == (True, True)

    interpolated_runs = [s.get("name", "") for s in job["steps"] if "${{" in s.get("run", "")]
    assert not interpolated_runs, (
        f"run: blocks in service-image job must not contain ${{}}: {interpolated_runs}"
    )


def test_service_image_release_job_invariants() -> None:
    """release.yml publishes the Service image only in the run where release-please created a
    release (#1486).

    It builds, smoke-tests and scans the image, pushes it by digest and attests it, and only then
    tags it with the release tag and `latest`, so a tag never names an unattested image. No plan
    decides whether to build: Image Updater rolls the cluster onto the digest `latest` moves to.
    """
    import yaml

    release_wf = (
        yaml.safe_load(Path(".github/workflows/release.yml").read_text(encoding="utf-8")) or {}
    )
    job = release_wf["jobs"]["service-image"]
    steps = job["steps"]

    assert (
        release_wf[True]["push"]["branches"],
        job["if"],
        job.get("needs"),
        job.get("permissions"),
        "SERVICE_IMAGE_INPUTS" in job.get("env", {}),
    ) == (
        ["main"],
        "needs.release-please.outputs.release_created == 'true'",
        "release-please",
        {
            "contents": "read",
            "packages": "write",
            "id-token": "write",
            "attestations": "write",
        },
        False,
    )
    assert (
        [s.get("name") for s in steps if s.get("id") == "plan"],
        [s.get("name") for s in steps if "steps.plan" in str(s.get("if", ""))],
        "Point latest at the Published Service Image" in [s.get("name") for s in steps],
    ) == ([], [], False)

    step_names = [s.get("name", "") for s in steps]
    indices = (
        step_names.index("Build and Load Service Image"),
        step_names.index("Run Service Image Smoke Test"),
        step_names.index("Scan Service Image for Vulnerabilities"),
        step_names.index("Build and Push Service Image"),
        step_names.index("Attest Build Provenance"),
        step_names.index("Tag the Attested Service Image"),
    )
    assert indices == tuple(sorted(indices)), f"Steps out of order: {indices}"

    meta_tags = next(s for s in steps if s.get("id") == "meta")["with"]["tags"]
    push_with = next(s for s in steps if s.get("name") == "Build and Push Service Image")["with"]
    tag_step = next(s for s in steps if s.get("name") == "Tag the Attested Service Image")
    assert (
        [line.strip() for line in meta_tags.splitlines() if line.strip()],
        "push-by-digest=true" in str(push_with.get("outputs", "")),
        "tags" in push_with,
        push_with.get("sbom") in (True, "true"),
        tag_step.get("shell"),
        tag_step["env"]["DIGEST"],
        "imagetools create" in tag_step["run"],
        "refs/heads/release" in tag_step["run"],
    ) == (
        ["type=raw,value=${{ needs.release-please.outputs.tag_name }}", "type=raw,value=latest"],
        True,
        False,
        True,
        "bash",
        "${{ steps.push.outputs.digest }}",
        True,
        False,
    )

    trivy_with = next(
        s for s in steps if s.get("name") == "Scan Service Image for Vulnerabilities"
    ).get("with", {})
    assert (
        trivy_with.get("scanners"),
        trivy_with.get("severity"),
        trivy_with.get("ignore-unfixed"),
        str(trivy_with.get("exit-code")),
    ) == ("vuln", "HIGH,CRITICAL", True, "1")

    interpolated_runs = [s.get("name", "") for s in steps if "${{" in s.get("run", "")]
    assert not interpolated_runs, (
        f"run: blocks in service-image release job must not contain ${{}}: {interpolated_runs}"
    )


_BUILD_ACTION = "./.github/actions/devcontainer-image"
_SMOKE_ACTION = "./.github/actions/devcontainer-smoke"


def _workflow(name: str) -> dict[str, Any]:
    """A workflow of this repository, parsed."""
    import yaml

    parsed: dict[str, Any] = (
        yaml.safe_load((REPO_ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
        or {}
    )
    return parsed


def _step_using(job: dict[str, Any], action: str) -> dict[str, Any]:
    """The job's step that runs `action`."""
    step: dict[str, Any] = next(s for s in job["steps"] if s.get("uses") == action)
    return step


_RELEASE_TAG_SCRIPT = """set -euo pipefail
TAG_ARGS=()
while read -r TAG; do
  if [ -n "$TAG" ]; then TAG_ARGS+=(--tag "$TAG"); fi
done <<< "$TAGS"
docker buildx imagetools create "${TAG_ARGS[@]}" "${DEVCONTAINER_IMAGE}@${DIGEST}"
while read -r TAG; do
  if [ -n "$TAG" ]; then
    test "$(docker buildx imagetools inspect "$TAG" --format '{{json .Manifest}}' | jq -r .digest)" = "$DIGEST"
  fi
done <<< "$TAGS"
"""


def test_the_release_attests_and_tags_only_the_devcontainer_digest_its_smoke_test_started() -> None:
    """release.yml publishes the DevContainer image only in the run where release-please created a
    release, in three jobs (#1895). The first builds the image with the Dev Containers CLI, so the
    features and the user vscode are in it, and pushes it by digest. The second starts that digest
    as vscode in a privileged container, so it holds no write scope and no OIDC token. The third
    attests the digest, tags it with the release tag and latest, and checks that each tag
    resolves to it."""
    jobs = _workflow("release.yml")["jobs"]
    build, smoke, publish = (
        jobs["devcontainer-image"],
        jobs["devcontainer-smoke"],
        jobs["devcontainer"],
    )
    build_steps = {s.get("name", ""): s for s in build["steps"]}
    publish_steps = {s.get("name", ""): s for s in publish["steps"]}

    assert (
        [(job["needs"], job.get("if"), job["permissions"]) for job in (build, smoke, publish)],
        list(build_steps),
        [s.get("name") for s in smoke["steps"]],
        list(publish_steps),
    ) == (
        [
            (
                "release-please",
                "needs.release-please.outputs.release_created == 'true'",
                {"contents": "read", "packages": "write"},
            ),
            (
                ["release-please", "devcontainer-image"],
                None,
                {"contents": "read", "packages": "read"},
            ),
            (
                ["devcontainer-image", "devcontainer-smoke"],
                None,
                {
                    "contents": "read",
                    "packages": "write",
                    "id-token": "write",
                    "attestations": "write",
                },
            ),
        ],
        [
            "Check out repository",
            "Install uv and Python",
            "Synchronize dependencies",
            "Log in to GitHub Container Registry (GHCR)",
            "Extract Metadata for DevContainer Image",
            "Build and Push DevContainer Image by Digest",
        ],
        [
            "Check out repository",
            "Install uv and Python",
            "Synchronize dependencies",
            "Log in to GitHub Container Registry (GHCR)",
            "Start the DevContainer Image as Its Remote User",
        ],
        [
            "Log in to GitHub Container Registry (GHCR)",
            "Set up Docker Buildx",
            "Attest Build Provenance",
            "Tag the Attested DevContainer Image",
        ],
    )

    tag = publish_steps["Tag the Attested DevContainer Image"]
    assert (
        build["outputs"],
        _step_using(build, _BUILD_ACTION)["with"],
        _step_using(smoke, _SMOKE_ACTION)["with"],
        publish_steps["Attest Build Provenance"]["with"]["subject-digest"],
        (tag["shell"], tag["env"], tag["run"]),
    ) == (
        {"digest": "${{ steps.image.outputs.digest }}", "tags": "${{ steps.meta.outputs.tags }}"},
        {
            "image": "${{ env.DEVCONTAINER_IMAGE }}",
            "labels": "${{ steps.meta.outputs.labels }}",
            "cache-from": (
                "type=registry,ref=ghcr.io/${{ github.repository }}/devcontainer:buildcache"
            ),
            "cache-to": (
                "type=registry,ref=ghcr.io/${{ github.repository }}/devcontainer:buildcache,mode=max"
            ),
        },
        {
            "image-ref": (
                "ghcr.io/${{ github.repository }}/devcontainer@"
                "${{ needs.devcontainer-image.outputs.digest }}"
            )
        },
        "${{ needs.devcontainer-image.outputs.digest }}",
        (
            "bash",
            {
                "DIGEST": "${{ needs.devcontainer-image.outputs.digest }}",
                "TAGS": "${{ needs.devcontainer-image.outputs.tags }}",
            },
            _RELEASE_TAG_SCRIPT,
        ),
    )

    labels_text = build_steps["Extract Metadata for DevContainer Image"]["with"]["labels"]
    assert {line.split("=", 1)[0] for line in labels_text.splitlines() if line} == {
        "org.opencontainers.image.title",
        "org.opencontainers.image.description",
        "org.opencontainers.image.licenses",
        "org.opencontainers.image.documentation",
        "org.opencontainers.image.source",
        "org.opencontainers.image.version",
    }


def test_the_pull_request_builds_and_starts_the_devcontainer_image_the_way_the_release_does() -> (
    None
):
    """The pull request job runs the two actions the release runs, so its check builds and starts
    what the release publishes (#1895). It pushes to a registry on the runner and only reads the
    cache the release writes, so it holds no write scope."""
    job = _workflow("ci.yml")["jobs"]["devcontainer"]
    release_build = _step_using(
        _workflow("release.yml")["jobs"]["devcontainer-image"], _BUILD_ACTION
    )

    assert (
        job["permissions"],
        job["services"],
        [s.get("name") for s in job["steps"]],
        _step_using(job, _BUILD_ACTION)["with"],
        _step_using(job, _SMOKE_ACTION)["with"],
    ) == (
        {"contents": "read", "packages": "read"},
        {
            "registry": {
                "image": (
                    "registry:3@sha256:"
                    "01cd312e67026f06f5d89c3e133a4a9adc7cb9eeb9b1194e0b2954dfd770efd2"
                ),
                "ports": ["5000:5000"],
            }
        },
        [
            "Check out repository",
            "Detect Image Content Changes",
            "Set up uv toolchain",
            "Log in to GitHub Container Registry (GHCR)",
            "Extract Metadata for DevContainer Image",
            "Build and Push DevContainer Image by Digest",
            "Start the DevContainer Image as Its Remote User",
        ],
        {
            "image": "localhost:5000/devcontainer",
            "labels": "${{ steps.meta.outputs.labels }}",
            "cache-from": release_build["with"]["cache-from"],
        },
        {"image-ref": "localhost:5000/devcontainer@${{ steps.image.outputs.digest }}"},
    )


def _automation_steps(document: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Each step of a workflow, with its job id, or of a composite action, with `runs`."""
    if "runs" in document:
        return [("runs", step) for step in document["runs"].get("steps", [])]
    return [
        (job_id, step)
        for job_id, job in document.get("jobs", {}).items()
        for step in job.get("steps", [])
    ]


def test_only_the_shared_actions_build_and_start_the_devcontainer_image() -> None:
    """A build of .devcontainer/Dockerfile that bypasses the Dev Containers CLI publishes an image
    without the Dev Container Features and the user vscode, as v0.2.35 to v0.2.38 did (#1895). So
    no step uses devcontainers/ci or names .devcontainer/Dockerfile in its `file` or its script,
    and only the image jobs run the two actions."""
    import yaml

    github = REPO_ROOT / ".github"
    automation = sorted(
        [*(github / "workflows").glob("*.y*ml"), *(github / "actions").glob("*/action.y*ml")]
    )
    steps = [
        (path.relative_to(REPO_ROOT).as_posix(), job_id, step)
        for path in automation
        for job_id, step in _automation_steps(
            yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        )
    ]
    other_builders = [
        f"{path}:{job_id}:{step.get('name', 'unnamed')}"
        for path, job_id, step in steps
        if str(step.get("uses", "")).startswith("devcontainers/ci@")
        or ".devcontainer/Dockerfile" in str(step.get("with", {}).get("file", ""))
        or ".devcontainer/Dockerfile" in str(step.get("run", ""))
    ]
    callers = [
        (path, job_id, step["uses"])
        for path, job_id, step in steps
        if step.get("uses") in (_BUILD_ACTION, _SMOKE_ACTION)
    ]

    assert (other_builders, callers) == (
        [],
        [
            (".github/workflows/ci.yml", "devcontainer", _BUILD_ACTION),
            (".github/workflows/ci.yml", "devcontainer", _SMOKE_ACTION),
            (".github/workflows/release.yml", "devcontainer-image", _BUILD_ACTION),
            (".github/workflows/release.yml", "devcontainer-smoke", _SMOKE_ACTION),
        ],
    )


def test_service_image_smoke_test_parity() -> None:
    """The smoke-test run: block in ci.yml and release.yml must be identical and enforce sandbox flags."""
    import yaml

    ci = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8")) or {}
    rel = yaml.safe_load(Path(".github/workflows/release.yml").read_text(encoding="utf-8")) or {}

    ci_smoke = next(
        s
        for s in ci["jobs"]["service-image"]["steps"]
        if s.get("name") == "Run Service Image Smoke Test"
    )
    rel_smoke = next(
        s
        for s in rel["jobs"]["service-image"]["steps"]
        if s.get("name") == "Run Service Image Smoke Test"
    )

    ci_run = ci_smoke["run"].strip()
    rel_run = rel_smoke["run"].strip()

    assert (
        ci_run == rel_run,
        "--read-only" in ci_run,
        "--cap-drop ALL" in ci_run,
        "no-new-privileges" in ci_run,
    ) == (True, True, True, True)


def test_pytest_worker_arguments_consistency() -> None:
    """Verify bare pytest gate row and _build_test_cmd without explicit -n carry no worker args."""
    from devops_cli.commands.ci import _build_test_cmd, _resolve_pytest_cmd

    gate_cmd = _resolve_pytest_cmd()
    cli_test_cmd = _build_test_cmd(
        numprocesses=None,
        verbose=False,
        k=None,
        x=False,
        targets=None,
    )

    gate_worker_args = [
        arg
        for arg in gate_cmd
        if arg in ("-n", "--numprocesses") or arg.startswith("--maxprocesses")
    ]
    cli_worker_args = [
        arg
        for arg in cli_test_cmd
        if arg in ("-n", "--numprocesses") or arg.startswith("--maxprocesses")
    ]

    assert (gate_worker_args, cli_worker_args) == ([], [])


def test_coverage_row_carries_no_duplicated_duration() -> None:
    """Verify virtual coverage check carries 0.0s duration and does not duplicate test step duration."""
    from devops_cli.commands.ci import (
        CheckResult,
        _assemble_ci_results,
        get_check_spec,
    )

    py_res = CheckResult(
        name="python",
        display_title="Python Check",
        passed=True,
        duration_seconds=0.01,
    )
    test_res = CheckResult(
        name="test",
        display_title="Pytest Suite",
        passed=True,
        duration_seconds=12.5,
    )
    test_spec = get_check_spec("test")

    assembled = _assemble_ci_results(
        py_result=py_res,
        selected_specs=[test_spec],
        raw_results=[test_res],
    )

    cov_res = next(r for r in assembled if r.name == "coverage")
    total_duration = sum(r.duration_seconds for r in assembled)

    assert (cov_res.duration_seconds, total_duration) == (
        0.0,
        py_res.duration_seconds + test_res.duration_seconds,
    )


@pytest.mark.asyncio
async def test_execute_check_async_success_and_failure() -> None:
    """Verify asynchronous check execution with process isolation and metrics."""
    import contextlib
    from unittest.mock import AsyncMock, MagicMock

    from devops_cli.commands.ci import _execute_check_async

    mock_proc_ok = MagicMock(returncode=0, stdout="success output", stderr="")
    mock_proc_fail = MagicMock(returncode=1, stdout="", stderr="failure output")

    @contextlib.contextmanager
    def dummy_span(*a: Any, **kw: Any) -> Any:
        yield

    with (
        patch("devops_cli.commands.ci.trace_span", side_effect=dummy_span),
        patch(
            "devops_cli.core.process.run_subprocess_async", new=AsyncMock(return_value=mock_proc_ok)
        ),
        patch("devops_cli.commands.ci.print_muted"),
    ):
        res_ok = await _execute_check_async(
            "test_step", "Test Step", ["echo", "hello"], "span.test", "metric.test"
        )

    with (
        patch("devops_cli.commands.ci.trace_span", side_effect=dummy_span),
        patch(
            "devops_cli.core.process.run_subprocess_async",
            new=AsyncMock(return_value=mock_proc_fail),
        ),
        patch("devops_cli.commands.ci.print_muted"),
    ):
        res_fail = await _execute_check_async(
            "test_step", "Test Step", ["uv", "run", "fake"], "span.test", "metric.test"
        )

    assert (res_ok.passed, res_ok.name, res_fail.passed, res_fail.name) == (
        True,
        "test_step",
        False,
        "test_step",
    )


def test_try_save_ci_cache_and_handle_results(tmp_path: Path) -> None:
    """Verify CI cache save and result handling logic."""
    import typer

    from devops_cli.commands.ci import CheckResult, _handle_ci_results, _try_save_ci_cache

    results = [CheckResult(name="t", display_title="T", passed=True, duration_seconds=1.0)]
    with (
        patch("devops_cli.ci.cache.compute_workspace_fingerprint", return_value=("fp", "sha")),
        patch("devops_cli.ci.cache.save_ci_cache") as mock_save,
    ):
        _try_save_ci_cache(tmp_path, results, {"fix": True})
        assert mock_save.call_count == 1

    with (
        patch("devops_cli.commands.ci._try_save_ci_cache") as mock_try_save,
        patch("devops_cli.commands.ci.is_dry_run", return_value=False),
    ):
        _handle_ci_results(results, root=tmp_path, ci_options={})
        assert mock_try_save.call_count == 1

    fail_results = [CheckResult(name="t", display_title="T", passed=False, duration_seconds=1.0)]
    with (
        patch("devops_cli.ci.cache.clear_ci_cache") as mock_clear,
        pytest.raises(typer.Exit),
    ):
        _handle_ci_results(fail_results, root=tmp_path, ci_options={})
        assert mock_clear.call_count == 1


def test_a_no_cache_run_still_records_its_result(tmp_path: Path) -> None:
    """`--no-cache` decides whether an existing entry may be trusted, not whether a fresh
    one is worth keeping.

    The run has done the full work and proved the tree. Discarding that made the next
    ordinary run repeat all of it, so a single `--no-cache` cost two full runs.
    """
    from devops_cli.commands.ci import CheckResult, _handle_ci_results

    results = [CheckResult(name="t", display_title="T", passed=True, duration_seconds=1.0)]
    with (
        patch("devops_cli.commands.ci._try_save_ci_cache") as mock_save,
        patch("devops_cli.commands.ci.is_dry_run", return_value=False),
    ):
        _handle_ci_results(results, root=tmp_path, ci_options={})
    assert mock_save.call_count == 1


def test_a_no_cache_run_does_not_read_an_existing_entry(tmp_path: Path) -> None:
    """Recording a result must not turn `--no-cache` back into a cached run."""
    from devops_cli.commands.ci import _try_fast_cached_ci

    with patch("devops_cli.commands.ci._try_get_ci_cache") as mock_get:
        hit = _try_fast_cached_ci(tmp_path, {}, cache=False, force=False)
    assert (hit, mock_get.called) == (False, False)


def test_a_dry_run_records_nothing(tmp_path: Path) -> None:
    """A preview has not run the checks, so it has no verdict to record."""
    from devops_cli.commands.ci import CheckResult, _handle_ci_results

    results = [CheckResult(name="t", display_title="T", passed=True, duration_seconds=1.0)]
    with (
        patch("devops_cli.commands.ci._try_save_ci_cache") as mock_save,
        patch("devops_cli.commands.ci.is_dry_run", return_value=True),
    ):
        _handle_ci_results(results, root=tmp_path, ci_options={})
    assert not mock_save.called


def _run_image_change_detection(repo: Path, base_ref: str) -> tuple[int, str, str]:
    """Execute the workflow's image-change detection step verbatim inside a repo.

    Parsing the workflow proves the shell is well-formed, but only running it proves the
    git invocations are valid. An earlier revision passed lint and YAML validation while
    failing at runtime with `fatal: depth 0 is not a positive number`.
    """
    import subprocess
    import tempfile

    import yaml

    workflow = yaml.safe_load((REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    step = next(
        s for s in workflow["jobs"]["devcontainer"]["steps"] if s.get("id") == "image_changes"
    )

    with tempfile.NamedTemporaryFile("w", suffix=".out", delete=False) as handle:
        output_file = handle.name

    env = {
        **os.environ,
        "EVENT_NAME": "pull_request",
        "BASE_REF": base_ref,
        "IMAGE_CONTENT_PATHS": step["env"]["IMAGE_CONTENT_PATHS"],
        "GITHUB_OUTPUT": output_file,
    }
    completed = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", step["run"]],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode, completed.stdout, Path(output_file).read_text(encoding="utf-8")


@pytest.fixture
def image_change_repo(tmp_path: Path) -> Path:
    """Build a repo with an `origin` remote and a branch diverging from main."""
    import subprocess

    def git(*args: str, cwd: Path) -> None:
        subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)

    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(origin)], check=True, capture_output=True
    )

    work = tmp_path / "work"
    work.mkdir()
    git("init", "-b", "main", cwd=work)
    git("config", "user.email", "ci@example.com", cwd=work)
    git("config", "user.name", "CI", cwd=work)
    git("remote", "add", "origin", str(origin), cwd=work)

    (work / "README.md").write_text("# base\n", encoding="utf-8")
    (work / "docs").mkdir()
    (work / "docs" / "guide.md").write_text("base\n", encoding="utf-8")
    git("add", "-A", cwd=work)
    git("commit", "-m", "base", cwd=work)
    git("push", "origin", "main", cwd=work)

    git("checkout", "-b", "feature", cwd=work)
    return work


def test_image_change_detection_flags_source_changes(image_change_repo: Path) -> None:
    """A change under src/ marks the image as needing a rebuild.

    The image packages devops-cli itself, so a source change makes the published image
    stale even when nothing under .devcontainer/ moved.
    """
    import subprocess

    src = image_change_repo / "src" / "devops_cli"
    src.mkdir(parents=True)
    (src / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=image_change_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "change source"],
        cwd=image_change_repo,
        check=True,
        capture_output=True,
    )

    code, stdout, output = _run_image_change_detection(image_change_repo, "main")

    assert (code, "changed=true" in output) == (0, True)
    assert "src/devops_cli/module.py" in stdout


def test_image_change_detection_skips_unrelated_changes(image_change_repo: Path) -> None:
    """A documentation-only change leaves the published image untouched."""
    import subprocess

    (image_change_repo / "docs" / "guide.md").write_text("updated\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=image_change_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "docs only"],
        cwd=image_change_repo,
        check=True,
        capture_output=True,
    )

    code, _, output = _run_image_change_detection(image_change_repo, "main")

    assert (code, "changed=false" in output) == (0, True)


def test_gate_checks_nested_worktree_not_main_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A gate run from a nested linked worktree checks that worktree, not the main checkout (#582).

    A lint error present only in the worktree fails the gate, and one present
    only in the main checkout passes the gate. The resolved root is also printed in the header,
    and a passing run caches its verdict under that root.
    """
    from devops_cli.commands.ci import _get_project_root

    main = tmp_path / "main_repo"
    main.mkdir()
    subprocess.run(
        [
            "git",
            "-C",
            str(main),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "init",
            "--quiet",
        ],
        check=True,
        capture_output=True,
    )
    (main / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    (main / "src").mkdir()
    (main / "src" / "valid.py").write_text("VALID = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(main), "add", "."], check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(main),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "commit",
            "--quiet",
            "-m",
            "initial",
        ],
        check=True,
        capture_output=True,
    )

    nested_wt = main / ".claude" / "worktrees" / "branch-1"
    subprocess.run(
        ["git", "-C", str(main), "worktree", "add", "--quiet", "-b", "branch-1", str(nested_wt)],
        check=True,
        capture_output=True,
    )

    # 1. Project root resolution
    monkeypatch.chdir(nested_wt)
    assert (_get_project_root(), find_top_level_repo_root(nested_wt)) == (
        nested_wt.resolve(),
        main.resolve(),
    )

    called_cwds: list[Path] = []

    async def mock_run_async(cmd, cwd=None, **kwargs):
        cwd_path = Path(cwd) if cwd else Path.cwd()
        called_cwds.append(cwd_path)
        has_error = (cwd_path / "src" / "error.py").exists()
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=1 if has_error else 0,
            stdout="" if not has_error else "SyntaxError: invalid syntax",
            stderr="",
        )

    saved_roots: list[Path] = []

    def record_saved_root(root: Path, *_args: object, **_kwargs: object) -> None:
        saved_roots.append(root)

    monkeypatch.setattr("devops_cli.core.process.run_subprocess_async", mock_run_async)
    monkeypatch.setattr("devops_cli.commands.ci._verify_python_314_environment", lambda: True)
    monkeypatch.setattr("devops_cli.commands.ci._try_save_ci_cache", record_saved_root)

    # 2. Error present ONLY in the worktree fails the gate
    (nested_wt / "src" / "error.py").write_text("def broken(:\n", encoding="utf-8")
    res_wt_fail = runner.invoke(app, ["--no-cache"])
    assert res_wt_fail.exit_code != 0
    assert str(nested_wt.resolve()) in res_wt_fail.output
    assert all(c == nested_wt.resolve() for c in called_cwds)

    # 3. Error present ONLY in the main checkout passes the gate when run from the worktree
    (nested_wt / "src" / "error.py").unlink()
    (main / "src" / "error.py").write_text("def broken(:\n", encoding="utf-8")
    called_cwds.clear()

    res_wt_pass = runner.invoke(app, ["--no-cache"])
    assert (
        res_wt_pass.exit_code,
        str(nested_wt.resolve()) in "".join(res_wt_pass.output.split()),
        set(called_cwds),
        saved_roots,
    ) == (0, True, {nested_wt.resolve()}, [nested_wt.resolve()])


# #582: from a worktree nested under `<checkout>/.claude/worktrees/`, single checks, the cached
# gate and coverage clean-up verify that worktree, name it before a cached verdict is reused, and
# warn when git no longer knows it.


_UNUSED_IMPORT = "import os\n"


def _lint_from(worktree: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[int, list[Path]]:
    """Run `devops ci lint --check` with real ruff from `worktree`; the exit code and cwds."""
    cwds: list[Path] = []

    def run_ruff_directly(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        cwds.append(Path(kwargs["cwd"]))
        rest = cmd[cmd.index("ruff") + 1 :]
        return run_subprocess([sys.executable, "-m", "ruff", *rest], **kwargs)

    monkeypatch.chdir(worktree)
    with patch.object(ci_module, "run_subprocess", run_ruff_directly):
        result = runner.invoke(ci_module.app, ["lint", "--check"])
    return result.exit_code, cwds


def test_lint_fails_on_an_error_only_the_worktree_has(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a broken worktree fails the gate although the main checkout is clean."""
    _, nested = nested_worktree
    (nested / "broken.py").write_text(_UNUSED_IMPORT, encoding="utf-8")

    exit_code, cwds = _lint_from(nested, monkeypatch)

    assert (exit_code, set(cwds)) == (1, {nested.resolve()})


def test_lint_ignores_an_error_only_the_main_checkout_has(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a clean worktree passes the gate although the main checkout is broken."""
    main, nested = nested_worktree
    (main / "broken.py").write_text(_UNUSED_IMPORT, encoding="utf-8")

    exit_code, cwds = _lint_from(nested, monkeypatch)

    assert (exit_code, set(cwds)) == (0, {nested.resolve()})


def _gate_from_the_cache(worktree: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    """Run `devops ci --check` from `worktree` with a cache hit; the roots and messages seen."""
    seen: dict[str, list[Any]] = {"cache_roots": [], "info": [], "warnings": []}

    def cache_hit(root: Path, *_args: Any, **_kwargs: Any) -> bool:
        seen["cache_roots"].append(root)
        return True

    monkeypatch.chdir(worktree)
    monkeypatch.setattr(ci_module, "_try_fast_cached_ci", cache_hit)
    monkeypatch.setattr(
        ci_module, "print_info", lambda message, **_kw: seen["info"].append(message)
    )
    monkeypatch.setattr(
        ci_module,
        "print_warning",
        lambda message, **_kw: seen["warnings"].append(message),
        raising=False,
    )
    result = runner.invoke(ci_module.app, ["--check"])
    assert result.exit_code == 0
    return seen


def test_a_cached_gate_verdict_names_the_worktree(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a cache hit is looked up for, and announced with, the worktree's root."""
    _, nested = nested_worktree

    seen = _gate_from_the_cache(nested, monkeypatch)

    assert (
        seen["cache_roots"],
        MESSAGES.ci.gate_root.format(root=nested.resolve()) in seen["info"],
        seen["warnings"],
    ) == ([nested.resolve()], True, [])


def test_the_gate_warns_from_a_workspace_on_a_slow_host_share(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the gate names a 9p host-share workspace as the reason its checks run slowly."""
    _, nested = nested_worktree
    monkeypatch.setattr("devops_cli.ci.diagnostics.slow_mount_fstype", lambda _root: "9p")

    seen = _gate_from_the_cache(nested, monkeypatch)

    assert seen["warnings"] == [
        MESSAGES.ci.gate_root_slow_mount.format(root=nested.resolve(), fstype="9p")
    ]


def _budget_output(duration: float, monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    """Run the budget check over a test step of `duration` seconds; the messages it printed."""
    seen: dict[str, list[str]] = {"warnings": [], "muted": []}
    monkeypatch.setattr(
        ci_module, "print_warning", lambda msg, **_kw: seen["warnings"].append(msg), raising=False
    )
    monkeypatch.setattr(
        ci_module, "print_muted", lambda msg, **_kw: seen["muted"].append(msg), raising=False
    )
    report = (
        "=== slowest 10 durations ===\n"
        "120.22s call     tests/test_secops.py::test_trivy_dry_run\n"
        "\n"
        "=== 6250 passed ===\n"
    )
    ci_module._warn_when_over_budget(
        [
            CheckResult(name="lint", display_title="lint", passed=True, duration_seconds=900.0),
            CheckResult(
                name="test",
                display_title="tests",
                passed=True,
                duration_seconds=duration,
                stdout=report,
            ),
        ]
    )
    return seen


def test_a_test_step_over_budget_names_the_slowest_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify a test step over the budget warns and lists pytest's slowest tests."""
    from devops_cli.config.constants import CONST_CI_TEST_BUDGET_SECONDS
    from devops_cli.output import format_duration

    seen = _budget_output(CONST_CI_TEST_BUDGET_SECONDS + 1, monkeypatch)

    assert seen == {
        "warnings": [
            MESSAGES.ci.test_budget_exceeded.format(
                duration=format_duration(CONST_CI_TEST_BUDGET_SECONDS + 1),
                budget=format_duration(CONST_CI_TEST_BUDGET_SECONDS),
            )
        ],
        "muted": ["  120.22s call     tests/test_secops.py::test_trivy_dry_run"],
    }


def test_a_test_step_within_budget_is_quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify a test step inside the budget prints nothing, whatever other checks took."""
    from devops_cli.config.constants import CONST_CI_TEST_BUDGET_SECONDS

    assert _budget_output(CONST_CI_TEST_BUDGET_SECONDS, monkeypatch) == {
        "warnings": [],
        "muted": [],
    }


def _stale_warning(worktree: Path) -> str:
    """The warning the gate gives for a stale worktree, its repair command shell-quoted."""
    root = worktree.resolve()
    return MESSAGES.ci.gate_root_stale.format(root=root, root_arg=shlex.quote(str(root)))


def test_the_gate_warns_from_a_stale_worktree(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a worktree whose git directory was pruned is checked itself, with a warning."""
    main, nested = nested_worktree
    shutil.rmtree(main / ".git" / "worktrees" / "wt")

    seen = _gate_from_the_cache(nested, monkeypatch)

    assert (seen["cache_roots"], seen["warnings"]) == (
        [nested.resolve()],
        [_stale_warning(nested)],
    )


def test_the_stale_worktree_warning_repairs_a_worktree_whose_checkout_moved(
    nested_worktree: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    git: Callable[..., None],
) -> None:
    """Verify the repair command the gate's warning gives, pasted into a shell in the main
    checkout as it says, reconnects a nested worktree that moved along with its main
    checkout, even to a path a shell would split."""
    main, _ = nested_worktree
    moved = main.rename(main.with_name("moved checkout; $HOME"))
    nested = moved / ".claude" / "worktrees" / "wt"
    warnings = _gate_from_the_cache(nested, monkeypatch)["warnings"]
    commands = [re.findall(r"`(git worktree repair\b[^`]*)`", warning) for warning in warnings]

    for command in commands:
        git(moved, *shlex.split(command[0])[1:])

    worktree_git = run_subprocess(["git", "-C", str(nested), "status"], check=False)
    assert (len(commands), worktree_git.returncode) == (1, 0)


def test_staged_sources_select_the_worktrees_tests(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify `devops ci test <file>`, as the changed-tests hook runs it, names the worktree
    and maps a worktree-only source onto the worktree's tests."""
    main, nested = nested_worktree
    (nested / "src" / "pkg").mkdir(parents=True)
    (nested / "src" / "pkg" / "widget.py").write_text("SIZE = 1\n", encoding="utf-8")
    (nested / "tests").mkdir()
    (nested / "tests" / "test_widget.py").write_text("def test_size() -> None: ...\n")
    (main / "tests").mkdir()
    (main / "tests" / "test_other.py").write_text("def test_other() -> None: ...\n")
    calls: list[tuple[list[str], Path]] = []

    def record(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((cmd, Path(kwargs["cwd"])))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    messages: list[str] = []
    monkeypatch.chdir(nested)
    monkeypatch.setattr(ci_module, "print_info", lambda message, **_kw: messages.append(message))
    spawns = record_spawns(monkeypatch)
    with patch.object(ci_module, "run_subprocess", record):
        result = runner.invoke(ci_module.app, ["test", "src/pkg/widget.py"])
    calls.extend((spawn.argv, Path(spawn.kwargs["cwd"])) for spawn in spawns)

    assert (
        result.exit_code,
        [("tests/test_widget.py" in cmd, cwd) for cmd, cwd in calls],
        MESSAGES.ci.gate_root.format(root=nested.resolve()) in messages,
    ) == (0, [(True, nested.resolve())], True)


def test_the_gate_header_prints_a_bracketed_root_literally(
    tmp_path: Path, git: Callable[..., None], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify square brackets in the checked root are printed, not parsed as markup."""
    main = tmp_path / "main"
    main.mkdir()
    git(main, "init", "--quiet")
    git(main, "commit", "--quiet", "--allow-empty", "-m", "first")
    bracketed = main / ".claude" / "worktrees" / "[bold]wt"
    git(main, "worktree", "add", "--quiet", "-b", "bracketed", str(bracketed))
    monkeypatch.chdir(bracketed)
    monkeypatch.setattr(ci_module, "_try_fast_cached_ci", lambda *_a, **_kw: True)

    result = runner.invoke(ci_module.app, ["--check"])

    assert (result.exit_code, "[bold]wt" in "".join(result.output.split())) == (0, True)


def test_a_single_check_warns_from_a_stale_worktree(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify `devops ci lint` from a pruned worktree names it and warns that git fails there."""
    main, nested = nested_worktree
    shutil.rmtree(main / ".git" / "worktrees" / "wt")
    cwds: list[Path] = []
    warnings: list[str] = []

    def record(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        cwds.append(Path(kwargs["cwd"]))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.chdir(nested)
    monkeypatch.setattr(
        ci_module, "print_warning", lambda message, **_kw: warnings.append(message), raising=False
    )
    with patch.object(ci_module, "run_subprocess", record):
        result = runner.invoke(ci_module.app, ["lint", "--check"])

    assert (result.exit_code, cwds, warnings) == (
        0,
        [nested.resolve()],
        [_stale_warning(nested)],
    )


def test_coverage_clean_up_follows_the_directory_the_gate_runs_in(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a process that imported the gate elsewhere, such as the in-process MCP server,
    cleans the worktree it now runs in and leaves the checkout around it alone."""
    main, nested = nested_worktree
    for tree in (main, nested):
        (tree / ".coverage.worker").write_text("", encoding="utf-8")
    monkeypatch.chdir(nested)

    ci_module._clean_coverage_artifacts(force=True)

    assert [(tree / ".coverage.worker").exists() for tree in (main, nested)] == [True, False]


def test_the_coverage_clean_up_keeps_the_combined_data_file(tmp_path: Path) -> None:
    """Verify the clean-up removes the worker data files and keeps the combined data (#1743).

    `devops ci coverage --build-index` and CI's `coverage xml` read the combined
    `.data/.coverage` after the gate, so the clean-up must not remove it, whatever its age.
    """
    data = tmp_path / ".data"
    data.mkdir(exist_ok=True)
    combined = data / ".coverage"
    workers = [
        data / ".coverage.host.pid4242.Xabcdef",
        tmp_path / ".coverage.host.pid4243.Xabcdeg",
    ]
    for path in (combined, *workers):
        path.write_text("", encoding="utf-8")
    two_hours_ago = time.time() - 7200
    os.utime(combined, (two_hours_ago, two_hours_ago))

    with patch("devops_cli.commands.ci._get_project_root", return_value=tmp_path):
        ci_module._clean_coverage_artifacts(force=True)

    assert (combined.exists(), [path.exists() for path in workers]) == (True, [False, False])


@pytest.mark.parametrize("check", ["test", "lint"])
def test_a_single_checks_help_does_not_name_the_gate_root(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, check: str
) -> None:
    """Verify `devops ci <check> --help`, which runs no check, prints only its help, without
    the gate-root header or the stale-worktree warning."""
    main, nested = nested_worktree
    shutil.rmtree(main / ".git" / "worktrees" / "wt")
    announced: list[str] = []
    monkeypatch.chdir(nested)
    monkeypatch.setattr(ci_module, "print_info", lambda message, **_kw: announced.append(message))
    monkeypatch.setattr(
        ci_module, "print_warning", lambda message, **_kw: announced.append(message), raising=False
    )

    result = runner.invoke(ci_module.app, [check, "--help"])

    assert (result.exit_code, "Usage:" in result.output, announced) == (0, True, [])


def _refuse_to_start(what: str) -> Callable[..., Any]:
    """A double of `asyncio.create_subprocess_exec` that fails the test if anything starts."""

    async def refuse(*argv: Any, **_kwargs: Any) -> Any:
        raise AssertionError(f"no tests match, yet {what} started: {argv[:6]}")

    return refuse


def test_help_after_the_separator_is_a_path_and_the_check_names_its_root(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify `devops ci test -- --help`, where `--help` follows `--` and so is a path rather
    than the help option, runs the check instead of printing help, and names the gate root."""
    _, nested = nested_worktree
    announced: list[str] = []
    monkeypatch.chdir(nested)
    monkeypatch.setattr(ci_module, "print_info", lambda message, **_kw: announced.append(message))
    monkeypatch.setattr(
        asyncio, "create_subprocess_exec", _refuse_to_start("a run in a session of its own")
    )
    with patch.object(ci_module, "run_subprocess", side_effect=AssertionError("no tests match")):
        result = runner.invoke(ci_module.app, ["test", "--", "--help"])

    assert (
        result.exit_code,
        "Usage:" in result.output,
        MESSAGES.ci.gate_root.format(root=nested.resolve()) in announced,
    ) == (0, False, True)


@pytest.mark.parametrize(
    "subcmd,expected_row",
    [
        ("coverage", "test"),
        ("lint", "lint"),
        ("format", "format"),
        ("typecheck", "typecheck"),
        ("audit", "audit"),
        ("security", "security"),
        ("actionlint", "actionlint"),
        ("docs", "docs"),
        ("uv-check", "uv-check"),
        ("lockfile", "lockfile"),
        ("build", "build"),
        ("outdated", "outdated"),
        ("devcontainer", "devcontainer"),
        ("deps", "deps"),
    ],
)
def test_subcommand_dispatches_exact_table_row_cmd(
    subcmd: str, expected_row: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify each CLI subcommand executes the exact check argv defined in the check table."""
    executed_cmds: list[list[str]] = []

    def mock_run(cmd: list[str], *a: Any, **kw: Any) -> subprocess.CompletedProcess[str]:
        executed_cmds.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", mock_run)
    monkeypatch.setattr(ci_module, "run_subprocess", mock_run)

    spec = get_check_spec(expected_row)
    args = [subcmd]
    if subcmd in ("lint", "format"):
        args.append("--check")
    result = runner.invoke(app, args)
    spec_cmd = list(spec.cmd)
    if spec_cmd and spec_cmd[0] == "uv" and "--preview-features" not in spec_cmd:
        spec_cmd[1:1] = ["--preview-features", "malware-check,check-command"]
    assert (result.exit_code, any(c == spec_cmd for c in executed_cmds)) == (0, True)


@pytest.mark.parametrize(
    "subcmd,flag,expected_row",
    [
        ("lint", None, "lint"),
        ("format", None, "format"),
        ("docs", "--fix", "docs"),
    ],
)
def test_subcommand_dispatches_exact_table_row_fix_cmd(
    subcmd: str, flag: str | None, expected_row: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify CLI subcommands in fix mode execute the exact fix argv defined in the check table."""
    executed_cmds: list[list[str]] = []

    def mock_run(cmd: list[str], *a: Any, **kw: Any) -> subprocess.CompletedProcess[str]:
        executed_cmds.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", mock_run)
    monkeypatch.setattr(ci_module, "run_subprocess", mock_run)

    spec = get_check_spec(expected_row)
    args = [subcmd]
    if flag:
        args.append(flag)
    result = runner.invoke(app, args)
    assert spec.fix_cmd is not None
    spec_fix_cmd = list(spec.fix_cmd)
    if spec_fix_cmd and spec_fix_cmd[0] == "uv" and "--preview-features" not in spec_fix_cmd:
        spec_fix_cmd[1:1] = ["--preview-features", "malware-check,check-command"]
    assert (result.exit_code, any(c == spec_fix_cmd for c in executed_cmds)) == (0, True)


def test_coverage_subcommand_maps_to_test_row() -> None:
    """Verify coverage maps to the test row in step row resolution."""
    assert resolve_step_rows("devops ci coverage") == ["test"]


@pytest.mark.asyncio
async def test_ci_fix_execution_order() -> None:
    """Verify in-place fixes run in strict sequence: format, then lint, before checks."""
    execution_order: list[str] = []

    async def mock_execute(spec: CheckSpec | str, *args: Any, **kwargs: Any) -> CheckResult:
        name = spec.name if isinstance(spec, CheckSpec) else spec
        apply_fix = kwargs.get("apply_fix", False)
        if apply_fix and isinstance(spec, CheckSpec) and spec.fix_cmd:
            execution_order.append(f"{name}_fix")
        execution_order.append(name)
        return CheckResult(
            name=name,
            display_title=name,
            passed=True,
            duration_seconds=0.01,
        )

    with (
        patch("devops_cli.commands.ci._execute_check_async", side_effect=mock_execute),
        patch("devops_cli.commands.ci._verify_python_314_environment", return_value=True),
    ):
        await ci_module._run_all_checks_async(lint_fix=True, format_fix=True, docs_fix=True)

    format_fix_idx = execution_order.index("format_fix")
    lint_fix_idx = execution_order.index("lint_fix")
    lint_check_idx = execution_order.index("lint")
    format_check_idx = execution_order.index("format")
    docs_fix_idx = execution_order.index("docs_fix")
    docs_check_idx = execution_order.index("docs")

    assert (
        format_fix_idx < lint_fix_idx,
        lint_fix_idx < lint_check_idx,
        lint_fix_idx < format_check_idx,
        docs_fix_idx < docs_check_idx,
    ) == (True, True, True, True)


def test_ci_selection_only_and_skip_options() -> None:
    """Verify --only and --skip resolution logic and validation."""
    specs = get_check_specs()
    all_names = [s.name for s in specs]

    only_lint = resolve_selected_specs(only=["lint"])
    assert [s.name for s in only_lint] == ["lint"]

    only_multiple = resolve_selected_specs(only=["lint,typecheck", "audit"])
    assert [s.name for s in only_multiple] == ["lint", "typecheck", "audit"]

    skip_test = resolve_selected_specs(skip=["test,outdated"])
    expected_skip = [name for name in all_names if name not in ("test", "outdated")]
    assert [s.name for s in skip_test] == expected_skip

    with pytest.raises(typer.Exit) as exc_both:
        resolve_selected_specs(only=["lint"], skip=["test"])
    with pytest.raises(typer.Exit) as exc_only:
        resolve_selected_specs(only=["nonexistent"])
    with pytest.raises(typer.Exit) as exc_skip:
        resolve_selected_specs(skip=["nonexistent"])

    assert (exc_both.value.exit_code, exc_only.value.exit_code, exc_skip.value.exit_code) == (
        2,
        2,
        2,
    )


def test_ci_cli_runner_only_and_skip_validation() -> None:
    """Verify CLI error reporting for conflicting or invalid check selections."""
    res_both = runner.invoke(app, ["--only", "lint", "--skip", "test"])
    res_invalid_only = runner.invoke(app, ["--only", "invalid_gate"])
    res_invalid_skip = runner.invoke(app, ["--skip", "invalid_gate"])

    assert (
        res_both.exit_code,
        "Cannot combine --only and --skip" in res_both.output,
        res_invalid_only.exit_code,
        "Invalid check name(s): 'invalid_gate'" in res_invalid_only.output,
        res_invalid_skip.exit_code,
        "Invalid check name(s): 'invalid_gate'" in res_invalid_skip.output,
    ) == (2, True, 2, True, 2, True)


@pytest.mark.asyncio
async def test_ci_single_row_streaming_capture_output() -> None:
    """Verify single-row run sets capture_output=False for live streaming, while multi-row sets capture_output=True."""
    captured_flags: list[bool] = []

    async def mock_execute(spec: CheckSpec | str, *args: Any, **kwargs: Any) -> CheckResult:
        captured_flags.append(kwargs.get("capture_output", True))
        name = spec.name if isinstance(spec, CheckSpec) else spec
        return CheckResult(name=name, display_title=name, passed=True, duration_seconds=0.01)

    with (
        patch("devops_cli.commands.ci._execute_check_async", side_effect=mock_execute),
        patch("devops_cli.commands.ci._verify_python_314_environment", return_value=True),
    ):
        await ci_module._run_all_checks_async(specs=[get_check_spec("lint")])
        single_row_flag = captured_flags.copy()

        captured_flags.clear()
        await ci_module._run_all_checks_async(
            specs=[get_check_spec("lint"), get_check_spec("format")]
        )
        multi_row_flags = captured_flags.copy()

    assert (single_row_flag, multi_row_flags) == ([False], [True, True])


@pytest.mark.asyncio
async def test_execute_check_async_timeout_expired() -> None:
    """Verify TimeoutExpired turns into structured failed CheckResult."""
    import contextlib

    @contextlib.contextmanager
    def dummy_span(*a: Any, **kw: Any) -> Any:
        yield

    async def mock_subprocess_async(*a: Any, **kw: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd=["test_cmd"], timeout=12.5)

    with (
        patch("devops_cli.commands.ci.trace_span", side_effect=dummy_span),
        patch("devops_cli.core.process.run_subprocess_async", side_effect=mock_subprocess_async),
        patch("devops_cli.commands.ci.print_muted"),
    ):
        spec = CheckSpec(
            name="slow_gate",
            display_title="Slow Gate",
            cmd=["sleep", "99"],
            span_name="ci.step.slow_gate",
            metric_step="slow_gate",
        )
        res = await ci_module._execute_check_async(spec, timeout=12.5)

    assert (
        res.passed,
        res.name,
        res.timed_out,
        res.timeout_seconds,
        "timed out" in res.stderr.lower(),
    ) == (False, "slow_gate", True, 12.5, True)


def test_ci_narrowed_runs_isolate_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify --only and --skip runs neither read nor populate the gate cache."""
    cache_read = False
    cache_written = False

    def mock_try_fast(*a: Any, **kw: Any) -> bool:
        nonlocal cache_read
        cache_read = True
        return False

    def mock_save_cache(*a: Any, **kw: Any) -> None:
        nonlocal cache_written
        cache_written = True

    async def mock_run_async(*a: Any, **kw: Any) -> list[CheckResult]:
        return [CheckResult(name="lint", display_title="Lint", passed=True, duration_seconds=0.01)]

    monkeypatch.setattr(ci_module, "_try_fast_cached_ci", mock_try_fast)
    monkeypatch.setattr(ci_module, "_try_save_ci_cache", mock_save_cache)
    monkeypatch.setattr(ci_module, "_run_all_checks_async", mock_run_async)
    monkeypatch.setattr(ci_module, "_clean_coverage_artifacts", lambda **kw: None)

    cache_read = False
    cache_written = False
    result_only = runner.invoke(app, ["--only", "lint", "--check", "--no-cache"])
    only_state = (result_only.exit_code, cache_read, cache_written)

    cache_read = False
    cache_written = False
    result_skip = runner.invoke(app, ["--skip", "test", "--check", "--no-cache"])
    skip_state = (result_skip.exit_code, cache_read, cache_written)

    assert (only_state, skip_state) == ((0, False, False), (0, False, False))


def _collect_ci_workflow_run_steps(workflow_data: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Extract (job_id, step_name, run_cmd) for all steps with a run command."""
    results: list[tuple[str, str, str]] = []
    jobs = workflow_data.get("jobs", {})
    for job_id, job_info in jobs.items():
        for step in job_info.get("steps", []):
            if isinstance(step, dict) and "run" in step:
                results.append((job_id, str(step.get("name", "unnamed")), str(step["run"])))
    return results


def _validate_ci_workflow_parity(workflow_data: dict[str, Any]) -> None:
    """Validate that all workflow run steps run through devops ci and cover all table rows."""
    jobs = workflow_data.get("jobs", {})
    static_job = jobs.get("static", {})
    test_job = jobs.get("test", {})
    assert static_job.get("name") == "Static Analysis", (
        "Pinned job 'Static Analysis' missing or renamed"
    )
    assert test_job.get("name") == "Tests & Coverage", (
        "Pinned job 'Tests & Coverage' missing or renamed"
    )

    allowlist: dict[tuple[str, str], str] = {
        ("devcontainer", "Detect Image Content Changes"): "Git diff to check changed image sources",
        (
            "service-image",
            "Detect Image Content Changes",
        ): "Git diff to check changed service image sources",
        ("service-image", "Run Service Image Smoke Test"): "Docker container curl/smoke tests",
        (
            "test",
            "Changed-Line Coverage",
        ): "Changed-line coverage gate (diff-cover) in the job summary, never a check table row",
        (
            "changed-tests",
            "Detect Changed Test Files",
        ): "Git diff to list the pull request's changed test files",
        (
            "static",
            "Security Scan",
        ): "Runs devops scan report to generate SARIF findings for GitHub code scanning",
        (
            "static",
            "Install OpenSpec",
        ): "Installs the pinned openspec the gate's openspec row runs, with the lock's installer",
        (
            "static",
            "Install Trivy",
        ): "Installs the pinned Trivy that the Security Scan step runs, with the lock's installer",
        (
            "test",
            "Install promtool",
        ): "Installs the pinned promtool that the rule tests of the test row run, with the lock's installer",
        (
            "rule-pack",
            "Detect Changed Rule Pack Files",
        ): "Git diff to check whether src/devops_cli/review/rules/** changed",
        (
            "rule-pack",
            "Run Semgrep Rule Pack Tests",
        ): "Path-filtered Semgrep --test and rules.lock check when rules change",
        (
            "docs-site",
            "Build the Site with the GitHub Pages Builder",
        ): "Path-filtered build of docs/ with the GitHub Pages builder image when the site changes",
        (
            "docs-site",
            "Verify Built Site Pages and Links",
        ): "Path-filtered verification of index.html, no raw markdown, and links with lychee (#2070)",
        (
            "image-pins",
            "Install Helm",
        ): "Installs the pinned helm that renders the chart Applications, with the lock's installer",
        (
            "image-pins",
            "Resolve the Image Pins",
        ): "Path-filtered resolve of each image an Argo CD Application pins when k8s/ changes (#1994)",
    }

    all_specs = get_check_specs()
    all_spec_names = {s.name for s in all_specs}
    covered_rows: set[str] = set()

    for job_id, step_name, run_cmd in _collect_ci_workflow_run_steps(workflow_data):
        if (job_id, step_name) in allowlist:
            continue
        rows = resolve_step_rows(run_cmd)
        assert len(rows) > 0, (
            f"Step '{step_name}' in job '{job_id}' runs raw non-gate command: {run_cmd}"
        )
        covered_rows.update(rows)

    missing = all_spec_names - covered_rows
    assert not missing, (
        f"CI workflow does not cover all check table rows. Missing: {sorted(missing)}"
    )


def test_ci_workflow_parity_with_check_table() -> None:
    """Verify .github/workflows/ci.yml runs all gates through devops ci covering all table rows."""
    import yaml

    ci_yaml_path = Path(".github/workflows/ci.yml")
    assert ci_yaml_path.is_file()
    workflow_data = yaml.safe_load(ci_yaml_path.read_text(encoding="utf-8"))
    _validate_ci_workflow_parity(workflow_data)


def test_ci_workflow_parity_mutations_fail() -> None:
    """Verify parity check catches raw steps, skipped checks, and renamed pinned jobs."""
    import copy

    import yaml

    ci_yaml_path = Path(".github/workflows/ci.yml")
    base_data = yaml.safe_load(ci_yaml_path.read_text(encoding="utf-8"))

    # Mutation 1: Raw ruff check step added to static job
    mut1 = copy.deepcopy(base_data)
    mut1["jobs"]["static"]["steps"].append(
        {
            "name": "Raw Ruff Step",
            "run": "uv run ruff check src",
        }
    )
    with pytest.raises(AssertionError, match="runs raw non-gate command"):
        _validate_ci_workflow_parity(mut1)

    # Mutation 2: Security check skipped in workflow
    mut2 = copy.deepcopy(base_data)
    for step in mut2["jobs"]["static"]["steps"]:
        if "devops ci" in str(step.get("run", "")):
            step["run"] = "uv run devops ci --check --no-cache --skip test,outdated,security"
    with pytest.raises(AssertionError, match="Missing: \\['security'\\]"):
        _validate_ci_workflow_parity(mut2)

    # Mutation 3: Pinned job renamed
    mut3 = copy.deepcopy(base_data)
    mut3["jobs"]["static"]["name"] = "Fast Linting"
    with pytest.raises(AssertionError, match="Pinned job 'Static Analysis' missing or renamed"):
        _validate_ci_workflow_parity(mut3)


def test_ci_workflow_publishes_scanner_sarif_to_code_scanning() -> None:
    """Verify ci.yml static job uploads scanner findings SARIF under category /devops-scan (#419)."""
    import yaml

    ci_yaml_path = Path(".github/workflows/ci.yml")
    assert ci_yaml_path.is_file()
    workflow_data = yaml.safe_load(ci_yaml_path.read_text(encoding="utf-8")) or {}
    static_job = workflow_data.get("jobs", {}).get("static", {})
    permissions = static_job.get("permissions", {})
    steps = static_job.get("steps", [])

    scan_step = next((s for s in steps if s.get("name") == "Security Scan"), {})
    upload_step = next((s for s in steps if s.get("name") == "Upload Security Scan SARIF"), {})

    assert (
        permissions.get("security-events"),
        scan_step.get("run"),
        scan_step.get("if"),
        "upload-sarif" in str(upload_step.get("uses", "")),
        upload_step.get("with", {}).get("sarif_file"),
        upload_step.get("with", {}).get("category"),
        upload_step.get("if"),
    ) == (
        "write",
        "uv run devops scan report --sarif .data/scan.sarif --skip bandit,trivy",
        "always()",
        True,
        ".data/scan.sarif",
        "/devops-scan",
        "always()",
    )


def test_ci_security_scan_installs_the_pinned_trivy_for_its_iac_scan() -> None:
    """Trivy's misconfiguration scan, `trivy-config`, took the place of Checkov in the scanner
    registry (#2214). So the static job installs the pinned Trivy before its security scan, and the
    scan checks the IaC files. The scan skips Trivy's filesystem scan, `trivy`, which took 194 s
    over this tree."""
    import yaml

    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))
    steps = workflow["jobs"]["static"]["steps"]
    runs = [str(step.get("run", "")) for step in steps]
    install = next(
        (i for i, run in enumerate(runs) if "devops install-tools --tool trivy " in run), None
    )
    scan = next(i for i, step in enumerate(steps) if step.get("name") == "Security Scan")

    assert (install is not None and install < scan, runs[scan]) == (
        True,
        "uv run devops scan report --sarif .data/scan.sarif --skip bandit,trivy",
    )


@pytest.fixture
def narrowed_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A checked tree with one test module, the current directory, so `devops ci test` finds it
    as its root and narrows a run to `tests/test_x.py`."""
    project = tmp_path / "project"
    (project / "tests").mkdir(parents=True)
    (project / "tests" / "test_x.py").write_text("def test_x() -> None: ...\n", encoding="utf-8")
    monkeypatch.chdir(project)
    return project


def test_a_test_run_past_its_timeout_fails_naming_its_command_and_timeout(
    narrowed_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A narrowed run whose child outlives the run's timeout, here a double whose output never
    comes, is stopped and fails, naming the command and the 1800 s timeout (#1669). The double's
    pid is 0, which the group stop refuses to signal, so it kills the double alone."""

    async def outlive_the_timeout(_spawn: RecordedSpawn) -> None:
        raise TimeoutError

    spawns = record_spawns(monkeypatch, on_communicate=outlive_the_timeout)
    result = runner.invoke(app, ["test", "tests/test_x.py"])

    timed_out = MESSAGES.ci.run_timed_out.format(
        command=shlex.join(spawns[0].argv), timeout=f"{DEFAULT_SUBPROCESS_TIMEOUT_SECONDS:g}s"
    )
    assert (
        result.exit_code,
        " ".join(timed_out.split()) in " ".join(result.output.split()),
        spawns[0].killed,
    ) == (1, True, True)


def _stop_handlers() -> tuple[Any, Any, Any]:
    return (
        signal.getsignal(signal.SIGINT),
        signal.getsignal(signal.SIGTERM),
        signal.getsignal(signal.SIGHUP),
    )


def _run_recording_handlers(
    monkeypatch: pytest.MonkeyPatch, *, fail: bool = False
) -> tuple[int, list[tuple[Any, Any, Any]]]:
    """`devops ci test tests/test_x.py`'s exit code and the SIGINT, SIGTERM and SIGHUP handlers
    in place while its child ran; with `fail`, the run's child fails to give its output."""
    during: list[tuple[Any, Any, Any]] = []

    async def record_handlers(_spawn: RecordedSpawn) -> None:
        during.append(_stop_handlers())
        if fail:
            raise OSError("the run's output could not be read")

    record_spawns(monkeypatch, on_communicate=record_handlers)
    return runner.invoke(app, ["test", "tests/test_x.py"]).exit_code, during


@pytest.mark.usefixtures("narrowed_project", "default_signal_dispositions")
@pytest.mark.parametrize("fail", [False, True], ids=["run-ends", "run-raises"])
def test_a_run_takes_over_ctrl_c_sigterm_and_sighup_and_hands_them_back(
    monkeypatch: pytest.MonkeyPatch, fail: bool
) -> None:
    """While the run lasts, Ctrl-C's SIGINT, SIGTERM and SIGHUP are its own, so they cancel it;
    after it, ended or raising, the handlers in place before are back (#1669, #2069)."""
    before = _stop_handlers()
    exit_code, during = _run_recording_handlers(monkeypatch, fail=fail)

    assert (
        exit_code,
        [handler is not previous for handler, previous in zip(during[0], before, strict=True)],
        _stop_handlers(),
    ) == (1 if fail else 0, [True, True, True], before)


@pytest.mark.usefixtures("narrowed_project", "default_signal_dispositions")
def test_a_run_off_the_main_thread_sets_no_signal_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    """A run from another thread, as the MCP server's thread pool makes one, completes and leaves
    every handler as it was: only the main thread may set one (#1669)."""
    before = _stop_handlers()
    outcome: list[tuple[int, list[tuple[Any, Any, Any]]]] = []
    worker = threading.Thread(target=lambda: outcome.append(_run_recording_handlers(monkeypatch)))
    worker.start()
    worker.join(THREAD_HANDOFF_BOUND_SECONDS)

    assert (outcome, _stop_handlers()) == ([(0, [before])], before)


@pytest.fixture
def hangup_ignored(default_signal_dispositions: None) -> Iterator[None]:
    """SIGHUP ignored, as `nohup` leaves it, for the test's length."""
    previous = signal.signal(signal.SIGHUP, signal.SIG_IGN)
    try:
        yield
    finally:
        signal.signal(signal.SIGHUP, previous)


@pytest.mark.usefixtures("narrowed_project", "hangup_ignored")
def test_an_ignored_hangup_stays_ignored_through_a_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Under `nohup`, which ignores SIGHUP, a run leaves the ignore alone, so a hangup does not
    cancel it, and takes over SIGINT and SIGTERM alone (#1669)."""
    before = _stop_handlers()
    exit_code, during = _run_recording_handlers(monkeypatch)

    assert (
        exit_code,
        during[0][2],
        [handler is not previous for handler, previous in zip(during[0][:2], before, strict=False)],
        _stop_handlers(),
    ) == (0, signal.SIG_IGN, [True, True], before)


def _devops_ci_test(project: Path, fake_uv: Path, log: Path) -> subprocess.Popen[bytes]:
    """`devops ci test tests/test_x.py`, the real command in a process of its own, with `fake_uv`
    first on PATH and telemetry off, so it opens no socket; its output goes to `log`. The tree
    under test's `src` leads its PYTHONPATH, so it runs that tree's devops-cli, not whichever the
    console script's install points at, as a replay on another tree would (#1669)."""
    python_path = os.pathsep.join(
        filter(None, [str(REPO_ROOT / "src"), os.environ.get("PYTHONPATH")])
    )
    env = {
        **os.environ,
        "PATH": f"{fake_uv.parent}{os.pathsep}{os.environ.get('PATH', '')}",
        "PYTHONPATH": python_path,
        "DEVOPS_CLI_TELEMETRY_ENABLED": "false",
    }
    devops = Path(sys.executable).with_name("devops")
    with log.open("wb") as output:
        return subprocess.Popen(
            [str(devops), "ci", "test", "tests/test_x.py"],
            cwd=project,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
        )


def _stop_driver(driver: subprocess.Popen[bytes]) -> None:
    """Kill the driver, this test's own child, if it outlived the test."""
    if driver.poll() is None:
        driver.kill()
    driver.wait()


# The signals that stop a `devops ci test` run: Ctrl-C's, a supervisor's and a closed terminal's.
STOP_SIGNALS = [signal.SIGINT, signal.SIGTERM, signal.SIGHUP]


@pytest.mark.usefixtures("default_signal_dispositions")
@pytest.mark.parametrize("stop_signal", STOP_SIGNALS, ids=lambda sig: sig.name)
def test_a_signal_to_devops_ci_test_lets_pytest_tear_down_then_stops_its_group(
    narrowed_project: Path, tmp_path: Path, stop_signal: signal.Signals
) -> None:
    """Ctrl-C, SIGTERM or SIGHUP to `devops ci test` forwards SIGINT to the run's group, which is
    in a session of its own, so a pytest there runs its teardown, then stops the whole group,
    and devops exits as cancelled, 130 (#1669). The run's `uv` is a fake on PATH that handles
    SIGINT as pytest does: its teardown records itself and stops the grandchild it started. The
    test waits for the fake's pids, or for devops to exit, with no bound of its own: a loaded host
    stretched the start of a fresh devops past the handoff bound (#2092)."""
    teardown = tmp_path / "teardown"
    with watching(tmp_path / "pids") as watch:
        script = interrupted_like_pytest(teardown)
        fake_uv = fake_program(tmp_path / "bin" / "uv", watch.pid_file, script)
        driver = _devops_ci_test(narrowed_project, fake_uv, tmp_path / "devops.log")
        try:
            started = wait_while_running(watch.started, driver)
            driver.send_signal(stop_signal)
            driver.wait()
        finally:
            _stop_driver(driver)

        assert (started, driver.returncode, wait_until(watch.stopped), teardown.is_file()) == (
            True,
            CONST_EXIT_CANCELLED,
            True,
            True,
        )


@pytest.mark.usefixtures("default_signal_dispositions")
@pytest.mark.parametrize("stop_signal", STOP_SIGNALS, ids=lambda sig: sig.name)
def test_a_second_signal_to_devops_ci_test_cannot_skip_the_sigkill(
    narrowed_project: Path, tmp_path: Path, stop_signal: signal.Signals
) -> None:
    """A second Ctrl-C, SIGTERM or SIGHUP while the stop waits out its grace, which a user or a
    supervisor sends to a run that will not end, kills the group at once rather than leaving it
    running (#1669). The fake `uv` and its grandchild ignore SIGINT and SIGTERM; the fake records
    each SIGINT and SIGTERM it gets, and none of its records after the test marked its second
    signal is a SIGTERM."""
    signals = tmp_path / "signals"
    with watching(tmp_path / "pids") as watch:
        fake_uv = fake_program(
            tmp_path / "bin" / "uv", watch.pid_file, records_stop_signals(signals)
        )
        driver = _devops_ci_test(narrowed_project, fake_uv, tmp_path / "devops.log")
        try:
            started = wait_while_running(watch.started, driver)
            driver.send_signal(stop_signal)
            interrupted = wait_until(lambda: signals.is_file() and "int" in signals.read_text())
            mark_second_signal(signals)
            driver.send_signal(stop_signal)
            driver.wait()
        finally:
            _stop_driver(driver)

        assert (
            started,
            interrupted,
            wait_until(watch.stopped),
            "term" in records_after_second_signal(signals),
        ) == (True, True, True, False)


@pytest.mark.live("sh")
@pytest.mark.usefixtures("default_signal_dispositions")
def test_a_second_ctrl_c_just_after_the_stop_sends_its_sigint_cannot_skip_the_sigkill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second Ctrl-C whose handler runs as soon as the stop has sent the run's group its
    SIGINT still ends in the SIGKILL, and the run exits as cancelled (#2069). A loaded host can
    keep devops off the CPU just after that SIGINT, so the second signal's handler runs there.
    `asyncio.run`'s own handler raised KeyboardInterrupt at that point, before the stop entered
    the `try` whose `finally` sends the SIGKILL. The run takes over Ctrl-C, so the signal only
    cancels the run. The test raises each Ctrl-C itself with `signal.raise_signal`, which runs the
    handler before it returns: the first as the run starts to wait for its child, once the child
    has written its pids, and the second just after the child records the stop's SIGINT. The
    child and its grandchild ignore SIGINT and SIGTERM, so only the SIGKILL stops them, and the
    child records no SIGTERM after the second Ctrl-C."""
    signals = tmp_path / "signals"
    real_spawn = asyncio.create_subprocess_exec
    real_signal_group = process_module._signal_process_group
    interrupted: list[bool] = []

    with watching(tmp_path / "pids") as watch:

        async def spawn_then_ctrl_c(*argv: Any, **kwargs: Any) -> asyncio.subprocess.Process:
            proc = await real_spawn(*argv, **kwargs)
            real_communicate = proc.communicate

            async def communicate() -> tuple[bytes, bytes]:
                assert wait_until(watch.started), "the hung child wrote no pids"
                signal.raise_signal(signal.SIGINT)
                return await real_communicate()

            monkeypatch.setattr(proc, "communicate", communicate)
            return proc

        def second_ctrl_c_once_the_child_has_the_sigint(pgid: int, sig: int) -> bool:
            sent = real_signal_group(pgid, sig)
            if sig == signal.SIGINT:
                interrupted.append(
                    wait_until(lambda: signals.is_file() and "int" in signals.read_text())
                )
                mark_second_signal(signals)
                signal.raise_signal(signal.SIGINT)
            return sent

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn_then_ctrl_c)
        monkeypatch.setattr(
            process_module, "_signal_process_group", second_ctrl_c_once_the_child_has_the_sigint
        )
        hung = hung_with_grandchild(watch.pid_file, records_stop_signals(signals))
        # A KeyboardInterrupt that escapes would end the whole session, so the test catches it.
        try:
            ci_module._session_returncode(
                hung, tmp_path, DEFAULT_SUBPROCESS_TIMEOUT_SECONDS, False, None
            )
            ended: object = "returned"
        except typer.Exit as stop:
            ended = stop.exit_code
        except KeyboardInterrupt:
            ended = "KeyboardInterrupt"

        assert (
            interrupted,
            ended,
            wait_until(watch.stopped),
            "term" in records_after_second_signal(signals),
        ) == ([True], CONST_EXIT_CANCELLED, True, False)


@pytest.mark.live("sh")
@pytest.mark.usefixtures("default_signal_dispositions")
def test_each_stop_signal_cancels_the_run_through_the_event_loop() -> None:
    """The run takes Ctrl-C's SIGINT, SIGTERM and SIGHUP through `loop.add_signal_handler`, and
    puts the previous handlers back after (#2092). That call writes each signal to the loop's own
    pipe, so a signal wakes the waiting loop wherever it lands. A handler that `signal.signal` set
    ran only when the main thread ran bytecode again, so a SIGTERM that came just before the loop
    started to wait was handled only when the child exited, 300 s later."""

    class RecordingLoop:
        def __init__(self) -> None:
            self.added: dict[signal.Signals, Callable[[], object]] = {}
            self.removed: list[signal.Signals] = []

        def add_signal_handler(self, sig: signal.Signals, callback: Callable[[], object]) -> None:
            self.added[sig] = callback

        def remove_signal_handler(self, sig: signal.Signals) -> bool:
            self.removed.append(sig)
            return True

    stop_signals = [signal.SIGINT, signal.SIGTERM, signal.SIGHUP]
    before = {sig: signal.getsignal(sig) for sig in stop_signals}
    loop = RecordingLoop()

    def cancel() -> None:
        """The run's cancel."""

    with ci_module._cancelled_by_stop_signals(cast(asyncio.AbstractEventLoop, loop), cancel):
        taken = dict(loop.added)

    assert (taken, loop.removed, {sig: signal.getsignal(sig) for sig in stop_signals}) == (
        dict.fromkeys(stop_signals, cancel),
        stop_signals,
        before,
    )
