"""Tests for devops ci command group."""

from __future__ import annotations

import asyncio
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast

import pytest
import typer
from typer.testing import CliRunner

from devops_cli.ci.cache import (
    compute_workspace_fingerprint,
    get_ci_cache,
    resolve_ci_cache_path,
)
from devops_cli.ci.diagnostics import gate_root_warnings
from devops_cli.commands import ci as ci_module
from devops_cli.commands.ci import (
    app,
    get_check_spec,
    get_check_specs,
    resolve_selected_specs,
    resolve_step_rows,
)
from devops_cli.config.constants import (
    CONST_BANDIT_INI_NAME,
    CONST_CI_TEST_BUDGET_SECONDS,
    CONST_EXIT_CANCELLED,
)
from devops_cli.config.defaults import (
    DEFAULT_CI_BANDIT_NICENESS,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.core.process import prepare_tool_cmd, run_subprocess
from devops_cli.core.repo import find_top_level_repo_root, find_worktree_root
from devops_cli.lang import MESSAGES
from devops_cli.output import format_duration, print_muted
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.hung_children import (
    fake_program,
    hung_with_grandchild,
    interrupted_like_pytest,
    mark_second_signal,
    records_after_second_signal,
    records_stop_signals,
    watching,
)
from tests.support.paths import REPO_ROOT
from tests.support.session_spawns import RecordedSpawn, record_spawns
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS, wait_until, wait_while_running

pytestmark = pytest.mark.usefixtures("refuse_nested_test_runs")

runner = CliRunner()

_NO_SUCH_PID = 99999999
"""A process id above the highest one Linux gives, so no live worker holds a file named by it."""


def _make_old(path: Path) -> None:
    """Age a worker data file past the minute in which the gate leaves a file alone."""
    two_hours_ago = time.time() - 7200
    os.utime(path, (two_hours_ago, two_hours_ago))


def _started(process_fake: ProcessFake) -> list[list[str]]:
    """The argument list of each program the command started, in order."""
    return [list(call.argv) for call in process_fake.calls]


def test_ci_audit_command(process_fake: ProcessFake) -> None:
    result = runner.invoke(app, ["audit"])
    called = _started(process_fake)
    assert result.exit_code == 0
    assert [cmd[0] for cmd in called] == ["uv", "osv-scanner"]
    assert any("uv" in c and "audit" in c for c in called)


def test_the_audit_check_audits_uv_and_each_npm_lockfile_without_a_shell() -> None:
    """One check carries both audits as argument lists, each started on its own: `uv audit` of
    `uv.lock`, and `osv-scanner` of the `package-lock.json` at the root, which pins OpenSpec and Style
    Dictionary (#6409, #6419) and needs no install. The devtools image audits the locks of its tools
    (#4363)."""
    assert get_check_spec("audit").commands == [
        ["uv", "audit"],
        ["osv-scanner", "scan", "source", "--lockfile", "package-lock.json"],
    ]


@pytest.mark.parametrize("failing", ["uv", "osv-scanner"])
def test_the_audit_command_fails_when_either_audit_fails_and_still_runs_the_other(
    process_fake: ProcessFake, failing: str
) -> None:
    """A vulnerable pin fails the command, and a vulnerable Python dependency does not hide it."""
    process_fake.answer(failing, ProcessAnswer(returncode=1))

    result = runner.invoke(app, ["audit"])

    assert (result.exit_code, [argv[0] for argv in _started(process_fake)]) == (
        1,
        ["uv", "osv-scanner"],
    )


_OSV_AUDIT_READINGS = [
    (1, "found vulnerabilities (osv-scanner audit exited 1)", "could not run"),
    (2, "could not run (osv-scanner audit exited 2)", "found vulnerabilities"),
]


@pytest.mark.parametrize(("code", "reported", "not_reported"), _OSV_AUDIT_READINGS)
def test_the_audit_command_says_whether_osv_scanner_found_vulnerabilities_or_could_not_run(
    process_fake: ProcessFake, code: int, reported: str, not_reported: str
) -> None:
    """The command reads osv-scanner's exit code, so an error or missing binary is not reported as
    a vulnerable pin."""
    process_fake.answer("osv-scanner", ProcessAnswer(returncode=code))

    result = runner.invoke(app, ["audit"])

    said = " ".join(result.output.split())
    assert (result.exit_code, reported in said, not_reported in said) == (1, True, False)


@pytest.mark.parametrize(("code", "reported", "not_reported"), _OSV_AUDIT_READINGS)
@pytest.mark.usefixtures("ci_root")
def test_the_gate_row_of_the_audit_check_reads_osv_scanner_as_the_audit_command_does(
    process_fake: ProcessFake, code: int, reported: str, not_reported: str
) -> None:
    """A single check run, `devops ci --only audit`, fails its row and gives the same reading
    under the check's output."""
    process_fake.answer("osv-scanner", ProcessAnswer(returncode=code))

    result = runner.invoke(app, ["--only", "audit", "--check", "--no-cache"])

    said = " ".join(result.output.split())
    assert (result.exit_code, reported in said, not_reported in said) == (1, True, False)


def test_the_audit_command_plans_both_audits_in_a_dry_run(process_fake: ProcessFake) -> None:
    """`--dry-run` lists both commands as one plan and starts neither."""
    result = runner.invoke(app, ["audit", "--dry-run"])

    assert (
        result.exit_code,
        "1. UV_MALWARE_CHECK=0 uv --preview-features" in result.output,
        "2. UV_MALWARE_CHECK=0 osv-scanner scan source --lockfile package-lock.json"
        in result.output,
        process_fake.calls,
    ) == (
        0,
        True,
        True,
        [],
    )


@pytest.mark.usefixtures("ci_root")
def test_a_check_with_two_commands_runs_both_and_fails_when_either_fails(
    process_fake: ProcessFake,
) -> None:
    """The gate's row passes only when every command of its check exits 0, and reports the output
    of all of them in the order they ran."""

    def scans(target: str) -> Callable[[ProcessCall], bool]:
        return lambda call: "-r" in call.argv and call.argv[call.argv.index("-r") + 1] == target

    process_fake.answer(
        scans("src"), ProcessAnswer(returncode=0, stdout="src out\n", stderr="src err\n")
    )
    process_fake.answer(
        scans("tests"), ProcessAnswer(returncode=1, stdout="tests out\n", stderr="tests err\n")
    )

    result = runner.invoke(app, ["--only", "security", "--check", "--no-cache"])

    said = " ".join(result.output.split())
    assert (
        result.exit_code,
        [argv[argv.index("-r") + 1] for argv in _started(process_fake) if "-r" in argv],
        "src out tests out src err tests err" in said,
    ) == (1, ["src", "tests"], True)


def test_ci_coverage_command(process_fake: ProcessFake) -> None:
    result = runner.invoke(app, ["coverage", "--html"])
    called = _started(process_fake)
    assert result.exit_code == 0
    assert any("--cov=src" in c and "--cov-report=html" in c for c in called)


def test_ci_security_command(process_fake: ProcessFake) -> None:
    result = runner.invoke(app, ["security", "-s", "high"])
    called = _started(process_fake)
    bandit_runs = [c[c.index("bandit") :] for c in called if "bandit" in c]
    assert (result.exit_code, bandit_runs) == (
        0,
        [
            ["bandit", "-r", "src", "--ini", CONST_BANDIT_INI_NAME, "--severity-level", "low"],
            ["bandit", "-r", "tests", "--ini", CONST_BANDIT_INI_NAME, "--severity-level", "high"],
        ],
    )


@pytest.mark.usefixtures("ci_root")
def test_the_gate_starts_bandit_below_the_test_row_s_priority(process_fake: ProcessFake) -> None:
    """The test row is the full gate's critical path, so the gate starts Bandit, which runs beside
    its workers, under `nice`, and the test row at normal priority (#1725). `devops ci security`
    runs the same row (`test_subcommand_dispatches_exact_table_row_cmd`)."""
    runner.invoke(app, ["--only", "security,test", "--check", "--no-cache"])

    started = _started(process_fake)
    gate_security = [argv for argv in started if "bandit" in argv]
    gate_test = next(argv for argv in started if "pytest" in argv)
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


def test_ci_security_runs_every_command_of_its_row(process_fake: ProcessFake) -> None:
    """`devops ci security` runs both Bandit runs of the row, and the second after a failed
    first, so one run shows every finding (#1538)."""
    process_fake.answer("uv", ProcessAnswer(returncode=1))

    result = runner.invoke(app, ["security"])
    expected = [prepare_tool_cmd(cmd) for cmd in get_check_spec("security").commands]
    assert (result.exit_code, [c for c in _started(process_fake) if "bandit" in c]) == (
        1,
        expected,
    )


def test_ci_actionlint_command(process_fake: ProcessFake) -> None:
    result = runner.invoke(app, ["actionlint"])
    called = _started(process_fake)
    assert result.exit_code == 0
    assert any("actionlint" in c for c in called)


def test_ci_actionlint_not_on_path(monkeypatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)
    result = runner.invoke(app, ["actionlint"])
    assert result.exit_code == 1
    assert "actionlint" in result.output
    assert "devcontainer" in result.output


def test_ci_lint_command(process_fake: ProcessFake) -> None:
    # By default, lint applies autofixes
    result = runner.invoke(app, ["lint"])
    assert result.exit_code == 0
    assert any("ruff" in c and "check" in c and "--fix" in c for c in _started(process_fake))

    # With --check, lint verifies without applying fixes
    process_fake.reset()
    result_check = runner.invoke(app, ["lint", "--check"])
    assert result_check.exit_code == 0
    assert any("ruff" in c and "check" in c and "--fix" not in c for c in _started(process_fake))


def test_ci_format_command(process_fake: ProcessFake) -> None:
    # By default, format formats in-place
    result = runner.invoke(app, ["format"])
    assert result.exit_code == 0
    assert any("ruff" in c and "format" in c and "--check" not in c for c in _started(process_fake))

    # With --check, format verifies without modifying
    process_fake.reset()
    result_check = runner.invoke(app, ["format", "--check"])
    assert result_check.exit_code == 0
    assert any("ruff" in c and "format" in c and "--check" in c for c in _started(process_fake))


def test_ci_typecheck_command(process_fake: ProcessFake) -> None:
    result = runner.invoke(app, ["typecheck"])
    called = _started(process_fake)
    assert result.exit_code == 0
    assert any("mypy" in c and "--python-version" in c for c in called)


def test_ci_test_command(monkeypatch) -> None:
    spawns = record_spawns(monkeypatch)

    result = runner.invoke(app, ["test", "-v", "-k", "unit"])
    assert result.exit_code == 0
    assert any("pytest" in s.argv and "-v" in s.argv and "-k" in s.argv for s in spawns)


def test_ci_docs_command(process_fake: ProcessFake) -> None:
    result = runner.invoke(app, ["docs"])
    called = _started(process_fake)
    assert result.exit_code == 0
    assert any("devops" in c and "docs" in c and "check" in c for c in called)


def test_ci_uv_check_command(process_fake: ProcessFake) -> None:
    result = runner.invoke(app, ["uv-check"])
    called = _started(process_fake)
    assert (result.exit_code, any("uv" in c and "check" in c for c in called)) == (0, True)


def test_ci_lockfile_command(process_fake: ProcessFake) -> None:
    result = runner.invoke(app, ["lockfile"])
    called = _started(process_fake)
    assert (result.exit_code, any("lock" in c and "--check" in c for c in called)) == (0, True)


def test_the_gate_builds_the_wheel_and_sdist_beside_the_lock_check() -> None:
    """A green gate means the package builds and the lock matches, so the release pull request,
    whose only change is the version, cannot merge a tree that does not build."""
    rows = [spec.name for spec in get_check_specs()]
    assert (get_check_spec("build").cmd, rows.index("build") - rows.index("lockfile")) == (
        ["uv", "build", "--quiet"],
        1,
    )


def test_the_git_row_records_the_transcripts_again_with_the_real_git() -> None:
    """The row runs `main(["--check"])` of the recorder in a process of its own, outside pytest,
    so a transcript that the real git no longer gives fails the gate (#2146). It is no heavy row:
    it takes seconds."""
    spec = get_check_spec("git")

    assert (
        spec.cmd[:4],
        "tests.support.git_recording" in spec.cmd[4],
        "--check" in spec.cmd[4],
    ) == (
        ["uv", "run", "python", "-c"],
        True,
        True,
    )
    assert spec.heavy is False


def test_ci_outdated_command(process_fake: ProcessFake) -> None:
    result = runner.invoke(app, ["outdated"])
    called = _started(process_fake)
    assert (result.exit_code, any("tree" in c and "--outdated" in c for c in called)) == (0, True)


def test_ci_test_settings_command(process_fake: ProcessFake) -> None:
    result = runner.invoke(app, ["test-settings"])
    called = _started(process_fake)
    assert (result.exit_code, any("check_test_settings" in " ".join(c) for c in called)) == (
        0,
        True,
    )


def test_ci_uv_check_and_lockfile_failures(process_fake: ProcessFake) -> None:
    process_fake.answer(lambda call: True, ProcessAnswer(returncode=1, stderr="failed"))

    res_uv = runner.invoke(app, ["uv-check"])
    res_lock = runner.invoke(app, ["lockfile"])
    res_outdated = runner.invoke(app, ["outdated"])
    res_settings = runner.invoke(app, ["test-settings"])
    assert (
        res_uv.exit_code,
        res_lock.exit_code,
        res_outdated.exit_code,
        res_settings.exit_code,
    ) == (1, 1, 1, 1)


def test_ci_python_version_check_failure(monkeypatch) -> None:
    monkeypatch.setattr(sys, "version_info", (3, 12, 0))

    result = runner.invoke(app, ["typecheck"])
    assert result.exit_code == 1
    assert "Strict Python 3.14+ requirement failed" in result.output

    res_settings = runner.invoke(app, ["test-settings"])
    assert res_settings.exit_code == 1
    assert "Strict Python 3.14+ requirement failed" in res_settings.output


@pytest.mark.usefixtures("ci_root", "ci_head")
def test_ci_all_checks_includes_audit_coverage_and_security(process_fake: ProcessFake) -> None:
    result = runner.invoke(app, ["--no-cache"])
    called = _started(process_fake)

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


@pytest.mark.usefixtures("ci_root", "ci_head")
def test_ci_all_checks_with_check_flag(process_fake: ProcessFake) -> None:
    result = runner.invoke(app, ["--check", "--no-cache"])
    called = _started(process_fake)

    assert result.exit_code == 0
    # In check-only mode, in-place format_fix and lint_fix are not run
    format_or_lint_fixes = [
        c
        for c in called
        if ("format" in c and "--check" not in c) or ("check" in c and "--fix" in c)
    ]
    assert len(format_or_lint_fixes) == 0


def test_ci_failure_branches_and_filters(process_fake: ProcessFake) -> None:
    """Verify non-zero returncode handling for each check."""
    process_fake.answer(lambda call: True, ProcessAnswer(returncode=1, stderr="failed"))
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


@pytest.mark.usefixtures("ci_root", "ci_head")
def test_ci_additional_subcommands(process_fake: ProcessFake) -> None:
    """Verify ci run, ci test, ci format --fix, and ci version."""
    # 1. test subcommand, whose pytest starts in a session of its own
    res_test = runner.invoke(app, ["test", "-n", "2"])
    assert res_test.exit_code == 0
    assert any("pytest" in argv and "-n" in argv for argv in _started(process_fake))

    # 2. format --fix
    process_fake.reset()
    res_fmt_fix = runner.invoke(app, ["format", "--fix"])
    assert res_fmt_fix.exit_code == 0
    assert any("ruff" in c and "format" in c and "--check" not in c for c in _started(process_fake))

    # 3. docs subcommand
    res_docs = runner.invoke(app, ["docs"])
    assert res_docs.exit_code == 0

    # 4. gate with --fix
    process_fake.reset()
    res_run_fix = runner.invoke(app, ["--fix"])
    assert res_run_fix.exit_code == 0
    assert any("generate" in c for c in _started(process_fake))


def test_ci_helpers_and_edge_cases(ci_root: Path, process_fake: ProcessFake) -> None:
    """Verify the gate's clean-up, its failure and summary output, and option parsing."""
    # 1. the gate removes the worker data files of an earlier run from its own root
    cov_file = ci_root / ".coverage.test1"
    cov_file.write_text("test", encoding="utf-8")
    _make_old(cov_file)
    runner.invoke(app, ["--only", "lint", "--check", "--no-cache"])
    assert not cov_file.exists()

    # 2. a failed check prints its title and output, and the summary follows
    process_fake.answer(
        ("uv", "--preview-features", "malware-check,check-command", "run", "pytest"),
        ProcessAnswer(returncode=1, stdout="AssertionError in test_x", stderr="Traceback..."),
    )
    res_failed = runner.invoke(app, ["--only", "test,lint", "--check", "--no-cache"])
    said = " ".join(res_failed.output.split())
    assert (
        res_failed.exit_code,
        MESSAGES.ci.pytest_coverage in said,
        "AssertionError in test_x" in said,
        "Traceback..." in said,
        "Total Elapsed:" in said,
    ) == (1, True, True, True, True)

    # 3. the gate executes every check and gives one status
    process_fake.reset()
    res_run = runner.invoke(app, ["--no-fix"])
    assert (res_run.exit_code, len(process_fake.calls) >= 1) == (0, True)

    # 4. test command with invalid -k filter
    res_bad_k = runner.invoke(app, ["test", "-k", "-invalid"])
    assert res_bad_k.exit_code == 1

    # 5. security with low and medium severity
    process_fake.reset()
    res_sec_low = runner.invoke(app, ["security", "-s", "low"])
    assert res_sec_low.exit_code == 0
    assert any(c[-2:] == ["--severity-level", "low"] for c in _started(process_fake))

    res_sec_med = runner.invoke(app, ["security", "-s", "medium"])
    assert res_sec_med.exit_code == 0
    assert any(c[-2:] == ["--severity-level", "medium"] for c in _started(process_fake))

    # test with -x and -v
    res_test_xv = runner.invoke(app, ["test", "-x", "-v"])
    assert res_test_xv.exit_code == 0
    assert any("-x" in argv and "-v" in argv for argv in _started(process_fake))

    # coverage default options
    res_cov = runner.invoke(app, ["coverage"])
    assert res_cov.exit_code == 0


def test_ci_clean_coverage_and_extended_options(ci_root: Path, process_fake: ProcessFake) -> None:
    """Verify the clean-up of worker data files, coverage --html, and the docs fix."""
    # 1. the gate removes the worker data files under .data/ of an earlier run
    fake_data = ci_root / ".data"
    fake_data.mkdir(parents=True, exist_ok=True)
    fake_cov = fake_data / ".coverage.sample"
    fake_cov.write_text("sample", encoding="utf-8")
    _make_old(fake_cov)
    runner.invoke(app, ["--only", "lint", "--check", "--no-cache"])
    assert not fake_cov.exists()

    # 2. coverage --html
    process_fake.reset()
    res_cov_html = runner.invoke(app, ["coverage", "--html"])
    assert res_cov_html.exit_code == 0
    assert any("--cov-report=html" in c for c in _started(process_fake))

    res_test_k = runner.invoke(app, ["test", "-k", "unit_test"])
    assert res_test_k.exit_code == 0
    assert any("-k" in argv and "unit_test" in argv for argv in _started(process_fake))

    # docs with --fix
    process_fake.reset()
    res_docs_fix = runner.invoke(app, ["docs", "--fix"])
    assert res_docs_fix.exit_code == 0
    assert any("generate" in c for c in _started(process_fake))
    assert any("check" in c for c in _started(process_fake))


@pytest.mark.usefixtures("ci_root", "ci_head")
def test_ci_run_docs_fix_when_needed(process_fake: ProcessFake) -> None:
    """Verify that CI fix pipeline triggers doc generation when docs check fails."""
    result = runner.invoke(app, ["--fix"])

    called = _started(process_fake)
    assert result.exit_code == 0
    assert any("generate" in cmd for cmd in called)
    assert "docs" in result.output


def test_gate_test_step_argv_is_unchanged() -> None:
    """Verify that the gate's test step argv remains unchanged and does not pass --cov-context."""
    spec = get_check_spec("test")
    assert (
        "--cov-context=test" in spec.cmd,
        any("COVERAGE_CORE" in c for c in spec.cmd),
    ) == (
        False,
        False,
    )


def test_a_gate_row_line_keeps_the_row_name_that_rich_would_consume(capsys: Any) -> None:
    """Rich reads `[format]` as a style tag, so the row line escapes the name (#5033)."""
    print_muted(ci_module._check_row_line("[green]✓ pass[/green]", "format", "ruff format (1s)"))
    assert "[format] ruff format (1s)" in capsys.readouterr().out


def test_a_gate_row_line_escapes_markup_in_the_name(capsys: Any) -> None:
    print_muted(ci_module._check_row_line("–", "a[b]", "skipped"))
    assert "[a[b]] skipped" in capsys.readouterr().out


def test_the_gate_test_row_writes_the_term_report_and_no_xml_report() -> None:
    """Verify the gate's test row prints the term report and writes no XML report (#1743).

    Only CI's changed-line coverage step reads coverage.xml, and it writes the file itself from
    the combined data, so the gate spends no serial report pass on it.
    """
    cmd = get_check_spec("test").cmd
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


def test_pytest_worker_arguments_consistency(ci_root: Path, process_fake: ProcessFake) -> None:
    """Verify bare pytest gate row and `devops ci test` without explicit -n carry no worker args."""
    gate_cmd = get_check_spec("test").cmd
    result = runner.invoke(app, ["test", "--repeat", "0"])
    cli_test_cmd = next(argv for argv in _started(process_fake) if "pytest" in argv)

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

    assert (result.exit_code, gate_worker_args, cli_worker_args) == (0, [], [])


@pytest.mark.usefixtures("ci_root")
def test_coverage_row_carries_no_duplicated_duration(process_fake: ProcessFake) -> None:
    """Verify virtual coverage check carries no duration and does not duplicate test step duration."""
    result = runner.invoke(app, ["--only", "lint,test", "--check", "--no-cache"])

    rows = [line.split() for line in result.output.splitlines()]
    assert (result.exit_code, ["coverage", "✓", "pass", "-"] in rows) == (0, True)


@pytest.mark.usefixtures("ci_root")
def test_a_check_passes_when_its_command_exits_zero_and_fails_when_it_does_not(
    process_fake: ProcessFake,
) -> None:
    """Verify a check run reports the exit code of its command, with the output of a failure."""
    process_fake.answer(
        lambda call: "ruff" in call.argv, ProcessAnswer(returncode=0, stdout="success output")
    )
    res_ok = runner.invoke(app, ["--only", "lint", "--check", "--no-cache"])
    process_fake.answer(
        lambda call: "ruff" in call.argv, ProcessAnswer(returncode=1, stderr="failure output")
    )
    res_fail = runner.invoke(app, ["--only", "lint", "--check", "--no-cache"])

    assert (
        res_ok.exit_code,
        "✓ pass" in res_ok.output,
        "failure output" in res_ok.output,
        res_fail.exit_code,
        "✗ fail" in res_fail.output,
        "failure output" in res_fail.output,
    ) == (0, True, False, 1, True, True)


def _cached_verdict(root: Path, *, fix: bool = False, check: bool = True) -> bool:
    """Whether the gate cache holds a passing verdict for the tree at `root` as it stands now."""
    options = {"fix": fix, "check": check}
    fingerprint = compute_workspace_fingerprint(root=root, options=options)
    assert fingerprint is not None
    return get_ci_cache(fingerprint=fingerprint[0], options=options, root=root) is not None


def test_a_passing_gate_records_its_verdict_and_a_failing_gate_clears_it(
    ci_root: Path, ci_head: ProcessFake
) -> None:
    """Verify CI cache save and result handling logic."""
    passed = runner.invoke(app, ["--check"])
    recorded = _cached_verdict(ci_root)

    ci_head.answer(lambda call: "ruff" in call.argv, ProcessAnswer(returncode=1))
    failed = runner.invoke(app, ["--check", "--no-cache"])

    assert (passed.exit_code, recorded, failed.exit_code, _cached_verdict(ci_root)) == (
        0,
        True,
        1,
        False,
    )


def test_a_no_cache_run_still_records_its_result(ci_root: Path, ci_head: ProcessFake) -> None:
    """`--no-cache` decides whether an existing entry may be trusted, not whether a fresh
    one is worth keeping.

    The run has done the full work and proved the tree. Discarding that made the next
    ordinary run repeat all of it, so a single `--no-cache` cost two full runs.
    """
    result = runner.invoke(app, ["--check", "--no-cache"])

    assert (result.exit_code, _cached_verdict(ci_root)) == (0, True)


def test_a_no_cache_run_does_not_read_an_existing_entry(
    ci_root: Path, ci_head: ProcessFake
) -> None:
    """Recording a result must not turn `--no-cache` back into a cached run."""
    runner.invoke(app, ["--check"])
    ci_head.calls.clear()

    result = runner.invoke(app, ["--check", "--no-cache"])

    assert (
        result.exit_code,
        MESSAGES.ci.cache_hit in " ".join(result.output.split()),
        any("ruff" in call.argv for call in ci_head.calls),
    ) == (0, False, True)


def test_a_dry_run_records_nothing(ci_root: Path, ci_head: ProcessFake) -> None:
    """A preview has not run the checks, so it has no verdict to record."""
    result = runner.invoke(app, ["--check", "--dry-run"])

    assert (result.exit_code, resolve_ci_cache_path(ci_root).is_file()) == (0, False)


def test_gate_checks_nested_worktree_not_main_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ci_head: ProcessFake
) -> None:
    """A gate run from a nested linked worktree checks that worktree, not the main checkout (#582).

    A lint error present only in the worktree fails the gate, and one present
    only in the main checkout passes the gate. The resolved root is also printed in the header,
    and a passing run caches its verdict under that root.
    """
    main = tmp_path / "main_repo"
    main.mkdir(parents=True, exist_ok=True)
    (main / ".git").mkdir(parents=True, exist_ok=True)
    (main / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (main / ".gitignore").write_text(".claude/\n", encoding="utf-8")
    (main / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    (main / "src").mkdir(parents=True, exist_ok=True)
    (main / "src" / "valid.py").write_text("VALID = 1\n", encoding="utf-8")

    nested_wt = main / ".claude" / "worktrees" / "branch-1"
    nested_wt.parent.mkdir(parents=True, exist_ok=True)
    nested_wt.mkdir(parents=True, exist_ok=True)
    (nested_wt / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    (nested_wt / "src").mkdir(parents=True, exist_ok=True)
    (nested_wt / "src" / "valid.py").write_text("VALID = 1\n", encoding="utf-8")
    wt_git = main / ".git" / "worktrees" / "branch-1"
    wt_git.mkdir(parents=True, exist_ok=True)
    (nested_wt / ".git").write_text(f"gitdir: {wt_git}\n", encoding="utf-8")
    (wt_git / "gitdir").write_text(f"{nested_wt / '.git'}\n", encoding="utf-8")
    (wt_git / "commondir").write_text("../..\n", encoding="utf-8")
    (wt_git / "HEAD").write_text("ref: refs/heads/branch-1\n", encoding="utf-8")

    # 1. Project root resolution
    monkeypatch.chdir(nested_wt)
    assert (find_worktree_root(), find_top_level_repo_root(nested_wt)) == (
        nested_wt.resolve(),
        main.resolve(),
    )

    called_cwds: list[Path] = []

    def check_the_tree(call: ProcessCall) -> ProcessAnswer:
        cwd_path = Path(call.cwd) if call.cwd else Path.cwd()
        called_cwds.append(cwd_path)
        has_error = (cwd_path / "src" / "error.py").exists()
        return ProcessAnswer(
            returncode=1 if has_error else 0,
            stdout="" if not has_error else "SyntaxError: invalid syntax",
        )

    ci_head.answer(lambda call: call.argv[0] != "git", check_the_tree)

    # 2. Error present ONLY in the worktree fails the gate
    (nested_wt / "src" / "error.py").write_text("def broken(:\n", encoding="utf-8")
    res_wt_fail = runner.invoke(app, ["--no-cache"])
    assert res_wt_fail.exit_code != 0
    assert str(nested_wt.resolve()) in "".join(res_wt_fail.output.split())
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
        resolve_ci_cache_path(nested_wt).is_file(),
        resolve_ci_cache_path(main).is_file(),
    ) == (0, True, {nested_wt.resolve()}, True, False)


# #582: from a worktree nested under `<checkout>/.claude/worktrees/`, single checks, the cached
# gate and coverage clean-up verify that worktree, name it before a cached verdict is reused, and
# warn when git no longer knows it.


_UNUSED_IMPORT = "import os\n"


def _lint_from(
    worktree: Path, monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> tuple[int, list[Path]]:
    """Run `devops ci lint --check` from `worktree`, where ruff finds an error in the directory
    that holds `broken.py`; the exit code and the directories the lint ran in."""
    cwds: list[Path] = []

    def ruff_reads_its_directory(call: ProcessCall) -> ProcessAnswer:
        cwds.append(Path(call.cwd))
        return ProcessAnswer(returncode=1 if (Path(call.cwd) / "broken.py").exists() else 0)

    process_fake.answer(lambda call: "ruff" in call.argv, ruff_reads_its_directory)
    monkeypatch.chdir(worktree)
    result = runner.invoke(app, ["lint", "--check"])
    return result.exit_code, cwds


@pytest.fixture
def nested_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """Provide a nested worktree without starting git processes."""
    main = tmp_path / "main"
    main.mkdir(parents=True, exist_ok=True)
    (main / ".git").mkdir(parents=True, exist_ok=True)
    (main / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (main / ".gitignore").write_text(".claude/\n", encoding="utf-8")
    (main / "pyproject.toml").write_text(
        '[project]\nname = "main"\n\n[tool.ruff.lint]\nselect = ["F401"]\n',
        encoding="utf-8",
    )
    nested = main / ".claude" / "worktrees" / "wt"
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.mkdir(parents=True, exist_ok=True)
    (nested / ".gitignore").write_text(".claude/\n", encoding="utf-8")
    (nested / "pyproject.toml").write_text(
        '[project]\nname = "main"\n\n[tool.ruff.lint]\nselect = ["F401"]\n',
        encoding="utf-8",
    )
    wt_git = main / ".git" / "worktrees" / "wt"
    wt_git.mkdir(parents=True, exist_ok=True)
    (nested / ".git").write_text(f"gitdir: {wt_git}\n", encoding="utf-8")
    (wt_git / "gitdir").write_text(f"{nested / '.git'}\n", encoding="utf-8")
    (wt_git / "commondir").write_text("../..\n", encoding="utf-8")
    (wt_git / "HEAD").write_text("ref: refs/heads/nested\n", encoding="utf-8")
    return main, nested


def test_lint_fails_on_an_error_only_the_worktree_has(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> None:
    """Verify a broken worktree fails the gate although the main checkout is clean."""
    _, nested = nested_worktree
    (nested / "broken.py").write_text(_UNUSED_IMPORT, encoding="utf-8")

    exit_code, cwds = _lint_from(nested, monkeypatch, process_fake)

    assert (exit_code, set(cwds)) == (1, {nested.resolve()})


def test_lint_ignores_an_error_only_the_main_checkout_has(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> None:
    """Verify a clean worktree passes the gate although the main checkout is broken."""
    main, nested = nested_worktree
    (main / "broken.py").write_text(_UNUSED_IMPORT, encoding="utf-8")

    exit_code, cwds = _lint_from(nested, monkeypatch, process_fake)

    assert (exit_code, set(cwds)) == (0, {nested.resolve()})


def _gate_from_the_cache(
    worktree: Path, monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> tuple[str, list[ProcessCall]]:
    """Run `devops ci --check` from `worktree` twice, the second time on the verdict the first
    recorded; what the second run printed and the programs it started."""
    monkeypatch.chdir(worktree)
    runner.invoke(app, ["--check"])
    started = len(process_fake.calls)
    result = runner.invoke(app, ["--check"])
    assert result.exit_code == 0
    return " ".join(result.output.split()), process_fake.calls[started:]


def test_a_cached_gate_verdict_names_the_worktree(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, ci_head: ProcessFake
) -> None:
    """Verify a cache hit is looked up for, and announced with, the worktree's root."""
    _, nested = nested_worktree

    said, started = _gate_from_the_cache(nested, monkeypatch, ci_head)

    assert (
        " ".join(MESSAGES.ci.cache_hit.split()) in said,
        " ".join(MESSAGES.ci.gate_root.format(root=nested.resolve()).split()) in said,
        [call.argv[0] for call in started if call.argv[0] != "git"],
        " ".join(_stale_warning(nested).split()) in said,
    ) == (True, True, [], False)


def test_the_gate_warns_from_a_workspace_on_a_slow_host_share(
    nested_worktree: tuple[Path, Path],
) -> None:
    """Verify the gate names a 9p host-share workspace as the reason its checks run slowly."""
    _, nested = nested_worktree
    mounts = f"drvfs {nested.resolve().parent} 9p rw,noatime 0 0\n"

    assert gate_root_warnings(nested.resolve(), mounts) == [
        MESSAGES.ci.gate_root_slow_mount.format(root=nested.resolve(), fstype="9p")
    ]


def _budget_output(duration: float, process_fake: ProcessFake, clock: ClockFake) -> str:
    """Run the gate with a test step of `duration` seconds; what it printed, on one line."""
    report = (
        "=== slowest 10 durations ===\n"
        "120.22s call     tests/test_secops.py::test_trivy_dry_run\n"
        "\n"
        "=== 6250 passed ===\n"
    )
    process_fake.answer(
        lambda call: "ruff" in call.argv and "check" in call.argv, ProcessAnswer(delay=900.0)
    )
    process_fake.answer(
        lambda call: "pytest" in call.argv, ProcessAnswer(stdout=report, delay=duration)
    )
    result = runner.invoke(app, ["--only", "lint,test", "--check", "--no-cache"])
    assert result.exit_code == 0
    return " ".join(result.output.split())


@pytest.mark.usefixtures("ci_root")
def test_a_test_step_over_budget_names_the_slowest_tests(
    process_fake: ProcessFake, clock: ClockFake
) -> None:
    """Verify a test step over the budget warns and lists pytest's slowest tests."""
    said = _budget_output(CONST_CI_TEST_BUDGET_SECONDS + 1, process_fake, clock)

    warning = MESSAGES.ci.test_budget_exceeded.format(
        duration=format_duration(CONST_CI_TEST_BUDGET_SECONDS + 1),
        budget=format_duration(CONST_CI_TEST_BUDGET_SECONDS),
    )
    assert (
        " ".join(warning.split()) in said,
        "120.22s call tests/test_secops.py::test_trivy_dry_run" in said,
    ) == (True, True)


@pytest.mark.usefixtures("ci_root")
def test_a_test_step_within_budget_is_quiet(process_fake: ProcessFake, clock: ClockFake) -> None:
    """Verify a test step inside the budget prints nothing, whatever other checks took."""
    said = _budget_output(CONST_CI_TEST_BUDGET_SECONDS, process_fake, clock)

    assert (
        "Slowest tests:" in said,
        "120.22s call" in said,
    ) == (False, False)


def _stale_warning(worktree: Path) -> str:
    """The warning the gate gives for a stale worktree, its repair command shell-quoted."""
    root = worktree.resolve()
    return MESSAGES.ci.gate_root_stale.format(root=root, root_arg=shlex.quote(str(root)))


def test_the_gate_warns_from_a_stale_worktree(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, ci_head: ProcessFake
) -> None:
    """Verify a worktree whose git directory was pruned is checked itself, with a warning."""
    main, nested = nested_worktree
    shutil.rmtree(main / ".git" / "worktrees" / "wt")

    said, started = _gate_from_the_cache(nested, monkeypatch, ci_head)

    assert (
        " ".join(MESSAGES.ci.gate_root.format(root=nested.resolve()).split()) in said,
        " ".join(_stale_warning(nested).split()) in said,
        [call.argv[0] for call in started if call.argv[0] != "git"],
    ) == (True, True, [])


def test_the_stale_worktree_warning_repairs_a_worktree_whose_checkout_moved(
    nested_worktree: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    ci_head: ProcessFake,
) -> None:
    """Verify the repair command the gate's warning gives, pasted into a shell in the main
    checkout as it says, reconnects a nested worktree that moved along with its main
    checkout, even to a path a shell would split."""
    main, _ = nested_worktree
    moved = main.rename(main.with_name("moved checkout; $HOME"))
    nested = moved / ".claude" / "worktrees" / "wt"
    monkeypatch.chdir(nested)
    result = runner.invoke(app, ["--check"])
    commands = re.findall(r"`(git worktree repair\b[^`]*)`", " ".join(result.output.split()))

    for command in commands:
        cmd = shlex.split(command)[1:]
        if len(cmd) >= 3 and cmd[0] == "worktree" and cmd[1] == "repair":
            target = Path(cmd[2])
            wt_git = moved / ".git" / "worktrees" / target.name
            (target / ".git").write_text(f"gitdir: {wt_git}\n", encoding="utf-8")
            (wt_git / "gitdir").write_text(f"{target / '.git'}\n", encoding="utf-8")

    worktree_git = run_subprocess(["git", "-C", str(nested), "status"], check=False)
    assert (len(commands), worktree_git.returncode) == (1, 0)


def test_staged_sources_select_the_worktrees_tests(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
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
    monkeypatch.chdir(nested)

    result = runner.invoke(app, ["test", "src/pkg/widget.py"])

    runs = [
        call
        for call in process_fake.calls
        if "pytest" in call.argv and "--collect-only" not in call.argv
    ]
    assert (
        result.exit_code,
        [("tests/test_widget.py" in call.argv, call.cwd) for call in runs],
        " ".join(MESSAGES.ci.gate_root.format(root=nested.resolve()).split())
        in " ".join(result.output.split()),
    ) == (0, [(True, nested.resolve())], True)


def test_the_gate_header_prints_a_bracketed_root_literally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ci_head: ProcessFake
) -> None:
    """Verify square brackets in the checked root are printed, not parsed as markup."""
    main = tmp_path / "main"
    main.mkdir(parents=True, exist_ok=True)
    (main / ".git").mkdir(parents=True, exist_ok=True)
    (main / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    bracketed = main / ".claude" / "worktrees" / "[bold]wt"
    bracketed.parent.mkdir(parents=True, exist_ok=True)
    bracketed.mkdir(parents=True, exist_ok=True)
    wt_git = main / ".git" / "worktrees" / "[bold]wt"
    wt_git.mkdir(parents=True, exist_ok=True)
    (bracketed / ".git").write_text(f"gitdir: {wt_git}\n", encoding="utf-8")
    (wt_git / "gitdir").write_text(f"{bracketed / '.git'}\n", encoding="utf-8")
    (wt_git / "commondir").write_text("../..\n", encoding="utf-8")
    (wt_git / "HEAD").write_text("ref: refs/heads/bracketed\n", encoding="utf-8")
    monkeypatch.chdir(bracketed)

    result = runner.invoke(app, ["--check"])

    assert (result.exit_code, "[bold]wt" in "".join(result.output.split())) == (0, True)


def test_a_single_check_warns_from_a_stale_worktree(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> None:
    """Verify `devops ci lint` from a pruned worktree names it and warns that git fails there."""
    main, nested = nested_worktree
    shutil.rmtree(main / ".git" / "worktrees" / "wt")
    monkeypatch.chdir(nested)

    result = runner.invoke(app, ["lint", "--check"])

    said = " ".join(result.output.split())
    assert (
        result.exit_code,
        [call.cwd for call in process_fake.calls],
        said.count(" ".join(_stale_warning(nested).split())),
    ) == (0, [nested.resolve()], 1)


def test_coverage_clean_up_follows_the_directory_the_gate_runs_in(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> None:
    """Verify a gate that runs in a nested worktree cleans the worktree it runs in and leaves
    the checkout around it alone."""
    main, nested = nested_worktree
    for tree in (main, nested):
        (tree / ".coverage.worker").write_text("", encoding="utf-8")
        _make_old(tree / ".coverage.worker")
    monkeypatch.chdir(nested)

    runner.invoke(app, ["--only", "lint", "--check", "--no-cache"])

    assert [(tree / ".coverage.worker").exists() for tree in (main, nested)] == [True, False]


def test_the_coverage_clean_up_keeps_the_files_of_a_live_worker_and_a_fresh_file(
    ci_root: Path, process_fake: ProcessFake
) -> None:
    """Verify the clean-up leaves a worker data file named by the pid of a running process, and a
    file written in the last minute, which a run in progress may still be writing."""
    live = ci_root / f".coverage.host.pid{os.getpid()}.Xabcdef"
    fresh = ci_root / ".coverage.fresh"
    for path in (live, fresh):
        path.write_text("", encoding="utf-8")
    _make_old(live)

    runner.invoke(app, ["--only", "lint", "--check", "--no-cache"])

    assert (live.exists(), fresh.exists()) == (True, True)


def test_the_coverage_clean_up_keeps_the_combined_data_file(
    ci_root: Path, process_fake: ProcessFake
) -> None:
    """Verify the clean-up removes the worker data files and keeps the combined data (#1743).

    `devops ci coverage --build-index` and CI's `coverage xml` read the combined
    `.data/.coverage` after the gate, so the clean-up must not remove it, whatever its age.
    """
    data = ci_root / ".data"
    data.mkdir(exist_ok=True)
    combined = data / ".coverage"
    workers = [
        data / f".coverage.host.pid{_NO_SUCH_PID}.Xabcdef",
        ci_root / f".coverage.host.pid{_NO_SUCH_PID}.Xabcdeg",
    ]
    for path in (combined, *workers):
        path.write_text("", encoding="utf-8")
        _make_old(path)

    runner.invoke(app, ["--only", "lint", "--check", "--no-cache"])

    assert (combined.exists(), [path.exists() for path in workers]) == (True, [False, False])


@pytest.mark.parametrize("check", ["test", "lint"])
def test_a_single_checks_help_does_not_name_the_gate_root(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, check: str
) -> None:
    """Verify `devops ci <check> --help`, which runs no check, prints only its help, without
    the gate-root header or the stale-worktree warning."""
    main, nested = nested_worktree
    shutil.rmtree(main / ".git" / "worktrees" / "wt")
    monkeypatch.chdir(nested)

    result = runner.invoke(app, [check, "--help"])

    said = " ".join(result.output.split())
    assert (
        result.exit_code,
        "Usage:" in result.output,
        " ".join(MESSAGES.ci.gate_root.format(root=nested.resolve()).split()) in said,
        " ".join(_stale_warning(nested).split()) in said,
    ) == (0, True, False, False)


def test_help_after_the_separator_is_a_path_and_the_check_names_its_root(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> None:
    """Verify `devops ci test -- --help`, where `--help` follows `--` and so is a path rather
    than the help option, runs the check instead of printing help, and names the gate root. The
    path is not there, so the run is refused and names it (#2868)."""
    _, nested = nested_worktree
    monkeypatch.chdir(nested)

    result = runner.invoke(app, ["test", "--", "--help"])

    assert (
        result.exit_code,
        "Usage:" in result.output,
        " ".join(MESSAGES.ci.gate_root.format(root=nested.resolve()).split())
        in " ".join(result.output.split()),
        process_fake.calls,
    ) == (1, False, True, [])


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
        ("test-settings", "test-settings"),
    ],
)
def test_subcommand_dispatches_exact_table_row_cmd(
    subcmd: str, expected_row: str, process_fake: ProcessFake
) -> None:
    """Verify each CLI subcommand executes the exact check argv defined in the check table."""
    spec = get_check_spec(expected_row)
    args = [subcmd]
    if subcmd in ("lint", "format"):
        args.append("--check")
    result = runner.invoke(app, args)
    spec_cmd = list(spec.cmd)
    if spec_cmd and spec_cmd[0] == "uv" and "--preview-features" not in spec_cmd:
        spec_cmd[1:1] = ["--preview-features", "malware-check,check-command"]
    assert (result.exit_code, any(c == spec_cmd for c in _started(process_fake))) == (0, True)


@pytest.mark.parametrize(
    "subcmd,flag,expected_row",
    [
        ("lint", None, "lint"),
        ("format", None, "format"),
        ("docs", "--fix", "docs"),
    ],
)
def test_subcommand_dispatches_exact_table_row_fix_cmd(
    subcmd: str, flag: str | None, expected_row: str, process_fake: ProcessFake
) -> None:
    """Verify CLI subcommands in fix mode execute the exact fix argv defined in the check table."""
    spec = get_check_spec(expected_row)
    args = [subcmd]
    if flag:
        args.append(flag)
    result = runner.invoke(app, args)
    assert spec.fix_cmd is not None
    spec_fix_cmd = list(spec.fix_cmd)
    if spec_fix_cmd and spec_fix_cmd[0] == "uv" and "--preview-features" not in spec_fix_cmd:
        spec_fix_cmd[1:1] = ["--preview-features", "malware-check,check-command"]
    assert (result.exit_code, any(c == spec_fix_cmd for c in _started(process_fake))) == (0, True)


def test_coverage_subcommand_maps_to_test_row() -> None:
    """Verify coverage maps to the test row in step row resolution."""
    assert resolve_step_rows("devops ci coverage") == ["test"]


@pytest.mark.usefixtures("ci_root")
def test_ci_fix_execution_order(process_fake: ProcessFake) -> None:
    """Verify in-place fixes run in strict sequence: format, then lint, before checks."""
    result = runner.invoke(app, ["--no-cache"])

    started = _started(process_fake)

    def at(row: str, *, fix: bool = False) -> int:
        spec = get_check_spec(row)
        return started.index(prepare_tool_cmd((spec.fix_cmd if fix else spec.cmd) or []))

    assert (
        result.exit_code,
        at("format", fix=True) < at("lint", fix=True),
        at("lint", fix=True) < at("lint"),
        at("lint", fix=True) < at("format"),
        at("docs", fix=True) < at("docs"),
    ) == (0, True, True, True, True)


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
        "Unknown check row: 'invalid_gate'" in res_invalid_only.output,
        res_invalid_skip.exit_code,
        "Unknown check row: 'invalid_gate'" in res_invalid_skip.output,
    ) == (2, True, 2, True, 2, True)


@pytest.mark.usefixtures("ci_root")
def test_ci_single_row_streaming_capture_output(process_fake: ProcessFake) -> None:
    """Verify single-row run sets capture_output=False for live streaming, while multi-row sets capture_output=True."""
    runner.invoke(app, ["--only", "lint", "--check", "--no-cache"])
    single_row_flag = [call.capture_output for call in process_fake.calls]

    process_fake.reset()
    runner.invoke(app, ["--only", "lint,format", "--check", "--no-cache"])
    multi_row_flags = [call.capture_output for call in process_fake.calls]

    assert (set(single_row_flag), set(multi_row_flags)) == ({False}, {True})


@pytest.mark.usefixtures("ci_root")
def test_a_check_that_times_out_fails_and_says_so(process_fake: ProcessFake) -> None:
    """Verify TimeoutExpired turns into a failed check that names its timeout."""
    process_fake.answer(
        lambda call: "ruff" in call.argv,
        ProcessAnswer(side_effect=subprocess.TimeoutExpired(cmd=["ruff"], timeout=12.5)),
    )

    result = runner.invoke(app, ["--only", "lint", "--check", "--no-cache"])

    said = " ".join(result.output.split())
    assert (
        result.exit_code,
        "fail (timed out after 12.5s)" in said,
        "Check 'lint' timed out after 12.5s." in said,
    ) == (1, True, True)


def test_ci_narrowed_runs_isolate_cache(ci_root: Path, ci_head: ProcessFake) -> None:
    """Verify --only and --skip runs neither read nor populate the gate cache."""
    only = runner.invoke(app, ["--only", "lint", "--check"])
    skip = runner.invoke(app, ["--skip", "test", "--check"])
    left_nothing = not _cached_verdict(ci_root)

    runner.invoke(app, ["--check"])
    ci_head.calls.clear()
    narrowed = runner.invoke(app, ["--only", "lint", "--check"])
    ran_again = any("ruff" in call.argv for call in ci_head.calls)

    assert (only.exit_code, skip.exit_code, left_nothing, narrowed.exit_code, ran_again) == (
        0,
        0,
        True,
        0,
        True,
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
    result = runner.invoke(app, ["test", "-n", "2", "tests/test_x.py"])

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
    return runner.invoke(app, ["test", "-n", "2", "tests/test_x.py"]).exit_code, during


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


def _devops_ci_test(
    project: Path,
    fake_uv: Path,
    log: Path,
    args: tuple[str, ...] = ("test", "-n", "2", "tests/test_x.py"),
) -> subprocess.Popen[bytes]:
    """`devops ci` with `args`, `test -n 2 tests/test_x.py` by default, the real command in a process
    of its own, with `fake_uv` first on PATH and telemetry off, so it opens no socket; its output
    goes to `log`. The tree under test's `src` leads its PYTHONPATH, so it runs that tree's
    devops-cli, not whichever the console script's install points at, as a replay on another tree
    would (#1669)."""
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
            [str(devops), "ci", *args],
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


@pytest.mark.live("devops")
@pytest.mark.real_sleep
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


@pytest.mark.live("devops")
@pytest.mark.real_sleep
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


@pytest.mark.usefixtures("narrowed_project", "default_signal_dispositions")
def test_a_stop_signal_cancels_the_gate_and_the_running_row_names_itself(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In process: a Ctrl-C while a row waits for its child cancels the gate. The child is
    stopped, the row prints its stopped line, and the gate exits as cancelled, 130 (#4775). The
    test raises the Ctrl-C itself with `signal.raise_signal`. The double's pid is 0, which the
    group stop refuses to signal, so the stop kills the double alone."""

    async def ctrl_c_then_hang(_spawn: RecordedSpawn) -> None:
        signal.raise_signal(signal.SIGINT)
        await asyncio.sleep(DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)

    spawns = record_spawns(monkeypatch, on_communicate=ctrl_c_then_hang)
    # A KeyboardInterrupt that escapes would end the whole session, so the test catches it.
    try:
        result = runner.invoke(app, ["--check", "--only", "format", "--no-cache"])
        outcome: object = (
            result.exit_code,
            [
                line.strip().partition(" (stopped after ")[0]
                for line in result.output.splitlines()
                if "stopped after" in line
            ],
        )
    except KeyboardInterrupt:
        outcome = "KeyboardInterrupt"

    assert (outcome, [spawn.killed for spawn in spawns]) == (
        (CONST_EXIT_CANCELLED, [f"✗ fail [format] {MESSAGES.ci.ruff_format}"]),
        [True],
    )


@pytest.mark.live("devops")
@pytest.mark.real_sleep
@pytest.mark.usefixtures("default_signal_dispositions")
def test_a_sigterm_to_the_gate_stops_the_group_of_each_running_row_and_names_it(
    narrowed_project: Path, tmp_path: Path
) -> None:
    """coreutils `timeout` ends a run of `devops ci` with SIGTERM, as a pre-push hook does at its
    limit. The gate stops the process group of each row that still runs, names the row, and
    exits as cancelled, 130 (#4775). The row's `uv` is a fake on PATH that starts a grandchild in
    its group and hangs."""
    log = tmp_path / "devops.log"
    with watching(tmp_path / "pids") as watch:
        fake_uv = fake_program(tmp_path / "bin" / "uv", watch.pid_file)
        driver = _devops_ci_test(
            narrowed_project, fake_uv, log, ("--check", "--only", "format", "--no-cache")
        )
        try:
            started = wait_while_running(watch.started, driver)
            driver.send_signal(signal.SIGTERM)
            driver.wait()
        finally:
            _stop_driver(driver)

        stopped_line = [
            line for line in log.read_text(encoding="utf-8").splitlines() if "stopped after" in line
        ]
        assert (
            started,
            driver.returncode,
            wait_until(watch.stopped),
            [MESSAGES.ci.ruff_format in line for line in stopped_line],
        ) == (True, CONST_EXIT_CANCELLED, True, [True])


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
    real_killpg = os.killpg
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

        def second_ctrl_c_once_the_child_has_the_sigint(pgid: int, sig: int) -> None:
            real_killpg(pgid, sig)
            if sig == signal.SIGINT:
                interrupted.append(
                    wait_until(lambda: signals.is_file() and "int" in signals.read_text())
                )
                mark_second_signal(signals)
                signal.raise_signal(signal.SIGINT)

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn_then_ctrl_c)
        monkeypatch.setattr(os, "killpg", second_ctrl_c_once_the_child_has_the_sigint)
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
