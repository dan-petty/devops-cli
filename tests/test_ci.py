"""Tests for devops ci command group."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import typer
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
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import find_top_level_repo_root
from devops_cli.lang import MESSAGES

runner = CliRunner()


def test_ci_audit_command(monkeypatch) -> None:
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", mock_run)

    result = runner.invoke(app, ["audit"])
    assert result.exit_code == 0
    assert any("uv" in c and "audit" in c for c in called)


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
    assert result.exit_code == 0
    assert any("bandit" in c and "-lll" in c for c in called)


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
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", mock_run)

    result = runner.invoke(app, ["test", "-v", "-k", "unit"])
    assert result.exit_code == 0
    assert any("pytest" in c and "-v" in c and "-k" in c for c in called)


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


def test_ci_lockfile_command(monkeypatch) -> None:
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", mock_run)

    result = runner.invoke(app, ["lockfile"])
    assert (result.exit_code, any("lock" in c and "--check" in c for c in called)) == (0, True)


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
        assert (
            result.exit_code == 0
            and "audit" in result.output
            and "coverage" in result.output
            and "security" in result.output
            and "actionlint" in result.output
            and ("uv-check" in result.output.lower() or "uv_check" in result.output.lower())
            and "lockfile" in result.output.lower()
            and "outdated" in result.output.lower()
        )
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

    monkeypatch.setattr("subprocess.run", mock_run)

    # 1. format --fix
    res_fmt_fix = runner.invoke(app, ["format", "--fix"])
    assert res_fmt_fix.exit_code == 0
    assert any("ruff" in c and "format" in c and "--check" not in c for c in called)

    # 2. test subcommand
    res_test = runner.invoke(app, ["test", "-n", "2"])
    assert res_test.exit_code == 0
    assert any("pytest" in c and "-n" in c for c in called)

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


def test_ci_helpers_and_edge_cases(tmp_path: Path) -> None:
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

    with patch("devops_cli.commands.ci.run_subprocess", side_effect=mock_run):
        res_sec_low = runner.invoke(app, ["security", "-s", "low"])
        assert res_sec_low.exit_code == 0
        assert any("-l" in c for c in called)

        res_sec_med = runner.invoke(app, ["security", "-s", "medium"])
        assert res_sec_med.exit_code == 0
        assert any("-ll" in c for c in called)

        # test with -x and -v
        res_test_xv = runner.invoke(app, ["test", "-x", "-v"])
        assert res_test_xv.exit_code == 0
        assert any("-x" in c and "-v" in c for c in called)

        # coverage default options
        res_cov = runner.invoke(app, ["coverage"])
        assert res_cov.exit_code == 0


def test_ci_clean_coverage_and_extended_options(tmp_path: Path) -> None:
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

    with patch("devops_cli.commands.ci.run_subprocess", side_effect=mock_run):
        res_cov_html = runner.invoke(app, ["coverage", "--html"])
        assert res_cov_html.exit_code == 0
        assert any("--cov-report=html" in c for c in called)

        res_test_k = runner.invoke(app, ["test", "-k", "unit_test"])
        assert res_test_k.exit_code == 0
        assert any("-k" in c and "unit_test" in c for c in called)

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


def _validate_devcontainer_step(step: dict[str, object], source: str) -> None:
    with_args = step.get("with", {})
    assert isinstance(with_args, dict), f"{source}: 'with' block must be a dict"
    assert "cacheFrom" in with_args, f"{source}: devcontainers/ci missing cacheFrom"
    assert with_args["cacheFrom"] == "${{ steps.image_repo.outputs.name }}:latest", (
        f"{source}: devcontainers/ci cacheFrom must be '${{{{ steps.image_repo.outputs.name }}}}:latest'"
    )


def test_github_workflows_caching_configuration() -> None:
    """Validate that GitHub workflows configure optimized caching for uv and devcontainers."""
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
            if "astral-sh/setup-uv" in uses:
                _validate_setup_uv_step(step, context_tag)
            elif "devcontainers/ci" in uses:
                _validate_devcontainer_step(step, context_tag)


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


def test_changed_line_coverage_step_is_advisory_on_pull_requests() -> None:
    """Pull requests get an advisory diff-cover report against their own base branch (#850).

    The step reads the coverage.xml the gate already wrote, runs only on pull requests,
    takes the base ref through env rather than an inline expression, and stays advisory
    (no --fail-under). It is never part of the pre-push gate, so no check row runs it.
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
        "GITHUB_STEP_SUMMARY" in run and "pragma: no cover" in run,
        "--fail-under" in run,
        "${{" in run,
        checkout.get("with", {}).get("fetch-depth"),
        any("diff-cover" in " ".join(s.cmd) for s in get_check_specs()),
    ) == (
        True,
        "github.event_name == 'pull_request'",
        {"BASE_REF": "${{ github.base_ref }}"},
        True,
        True,
        False,
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


def test_devcontainer_image_publishes_only_for_main_targeted_pull_requests() -> None:
    """The PR image is built only for pull requests targeting main.

    Release branches are what merge into main, so this confines image publishing to the
    release path instead of rebuilding an identical image on every feature pull request.
    """
    import yaml

    ci = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8")) or {}
    condition = str(ci["jobs"]["devcontainer"].get("if", ""))

    assert "github.base_ref == 'main'" in condition
    assert "github.event_name == 'pull_request'" in condition


def test_service_image_ci_job_invariants() -> None:
    """The CI service-image job runs for PRs to main or dispatch, pushes nothing, and avoids ${{ in scripts."""
    import yaml

    ci = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8")) or {}
    job = ci["jobs"]["service-image"]
    condition = str(job.get("if", ""))

    assert (
        "github.base_ref == 'main'" in condition,
        "github.event_name == 'pull_request'" in condition,
        "github.event_name == 'workflow_dispatch'" in condition,
        job.get("permissions"),
    ) == (True, True, True, {"contents": "read"})
    # Every pull request into main builds here, the release pull request included: release.yml
    # publishes the image only after the merge (#1486).
    assert ("release/v" in condition, "head.repo.full_name" in condition) == (False, False)

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
    """release.yml publishes the Service image only from main, after the release job (#1486).

    It builds, smoke-tests and scans the image, pushes it by digest and attests it, and only then
    tags it `vX.Y.Z` and `latest`, so a tag never names an unattested image. No release branch
    publishes it, and no plan decides whether to build: Image Updater rolls the cluster onto the
    digest `latest` moves to.
    """
    import yaml

    release_wf = (
        yaml.safe_load(Path(".github/workflows/release.yml").read_text(encoding="utf-8")) or {}
    )
    job = release_wf["jobs"]["service-image"]
    steps = job["steps"]

    assert (
        "release/v*" in release_wf[True]["push"]["branches"],
        job["if"],
        job.get("needs"),
        job.get("permissions"),
        "SERVICE_IMAGE_INPUTS" in job.get("env", {}),
    ) == (
        False,
        "github.ref == 'refs/heads/main'",
        "release",
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
        ["type=raw,value=v${{ needs.release.outputs.version }}", "type=raw,value=latest"],
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

    def mock_get_ok(key: str) -> Any:
        if key == "trace_span":
            return dummy_span
        if key == "run_subprocess_async":
            return AsyncMock(return_value=mock_proc_ok)
        return lambda *a, **kw: None

    with patch("devops_cli.commands.ci._get", side_effect=mock_get_ok):
        res_ok = await _execute_check_async(
            "test_step", "Test Step", ["echo", "hello"], "span.test", "metric.test"
        )

    def mock_get_fail(key: str) -> Any:
        if key == "trace_span":
            return dummy_span
        if key == "run_subprocess_async":
            return AsyncMock(return_value=mock_proc_fail)
        return lambda *a, **kw: None

    with patch("devops_cli.commands.ci._get", side_effect=mock_get_fail):
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
        assert mock_save.called

    with (
        patch("devops_cli.commands.ci._try_save_ci_cache") as mock_try_save,
        patch("devops_cli.commands.ci.is_dry_run", return_value=False),
    ):
        _handle_ci_results(results, root=tmp_path, ci_options={})
        assert mock_try_save.called

    fail_results = [CheckResult(name="t", display_title="T", passed=False, duration_seconds=1.0)]
    with (
        patch("devops_cli.ci.cache.clear_ci_cache") as mock_clear,
        pytest.raises(typer.Exit),
    ):
        _handle_ci_results(fail_results, root=tmp_path, ci_options={})
        assert mock_clear.called


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
    assert mock_save.called


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

    workflow = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text(
            encoding="utf-8"
        )
    )
    step = next(
        s for s in workflow["jobs"]["devcontainer"]["steps"] if s.get("id") == "image_changes"
    )

    with tempfile.NamedTemporaryFile("w", suffix=".out", delete=False) as handle:
        output_file = handle.name

    env = {
        **os.environ,
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
    assert (
        res_wt_fail.exit_code != 0
        and str(nested_wt.resolve()) in res_wt_fail.output
        and all(c == nested_wt.resolve() for c in called_cwds)
    )

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
    with patch.object(ci_module, "run_subprocess", record):
        result = runner.invoke(ci_module.app, ["test", "src/pkg/widget.py"])

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


def test_help_after_the_separator_is_a_path_and_the_check_names_its_root(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify `devops ci test -- --help`, where `--help` follows `--` and so is a path rather
    than the help option, runs the check instead of printing help, and names the gate root."""
    _, nested = nested_worktree
    announced: list[str] = []
    monkeypatch.chdir(nested)
    monkeypatch.setattr(ci_module, "print_info", lambda message, **_kw: announced.append(message))
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

    def mock_get(key: str) -> Any:
        if key == "trace_span":
            return dummy_span
        if key == "run_subprocess_async":
            return mock_subprocess_async
        return lambda *a, **kw: None

    with patch("devops_cli.commands.ci._get", side_effect=mock_get):
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
            "devcontainer",
            "Set Image Repository Name",
        ): "Setting lowercase GHCR repository name output",
        (
            "devcontainer",
            "Check PR Open Status Prior to Publishing Image",
        ): "GitHub CLI check for PR state",
        (
            "service-image",
            "Detect Image Content Changes",
        ): "Git diff to check changed service image sources",
        ("service-image", "Run Service Image Smoke Test"): "Docker container curl/smoke tests",
        (
            "test",
            "Changed-Line Coverage",
        ): "Advisory diff-cover report in the job summary, never a check table row",
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
