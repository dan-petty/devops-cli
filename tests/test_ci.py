"""Tests for devops ci command group."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from devops_cli.commands.ci import CheckResult, app

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


def test_ci_python_version_check_failure(monkeypatch) -> None:
    monkeypatch.setattr(sys, "version_info", (3, 12, 0))

    result = runner.invoke(app, ["typecheck"])
    assert result.exit_code == 1
    assert "Strict Python 3.14+ requirement failed" in result.output


def test_ci_all_checks_includes_audit_coverage_and_security() -> None:
    called: list[list[str]] = []

    async def mock_exec(
        name: str,
        display_title: str,
        cmd: list[str],
        span_name: str,
        metric_step: str,
        timeout: float = 600.0,
    ) -> CheckResult:
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
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "audit" in result.output
        assert "coverage" in result.output
        assert "security" in result.output
        assert "actionlint" in result.output
        assert any("audit" in c for c in called)
        assert any("bandit" in c for c in called)
        assert any("actionlint" in c for c in called)
        # Default fix=True automatically runs format and lint fix
        assert any("ruff" in c and "format" in c and "--check" not in c for c in called)
        assert any("ruff" in c and "check" in c and "--fix" in c for c in called)


def test_ci_all_checks_with_check_flag() -> None:
    called: list[list[str]] = []

    async def mock_exec(
        name: str,
        display_title: str,
        cmd: list[str],
        span_name: str,
        metric_step: str,
        timeout: float = 600.0,
    ) -> CheckResult:
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
        result = runner.invoke(app, ["--check"])
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
        assert res_audit_fail.exit_code == 1

        res_sec_fail = runner.invoke(app, ["security"])
        assert res_sec_fail.exit_code == 1

        res_lint_fail = runner.invoke(app, ["lint"])
        assert res_lint_fail.exit_code == 1

        res_type_fail = runner.invoke(app, ["typecheck"])
        assert res_type_fail.exit_code == 1

        res_doc_fail = runner.invoke(app, ["docs"])
        assert res_doc_fail.exit_code == 1


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
    with patch("devops_cli.commands.ci._ROOT", tmp_path):
        _clean_coverage_artifacts()
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
    _clean_coverage_artifacts()

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

    async def mock_execute(name, title, cmd, span, metric, timeout=None):
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
        jobs = content.get("jobs", {})
        for job_name, job_data in jobs.items():
            steps = job_data.get("steps", []) if isinstance(job_data, dict) else []
            for step in steps:
                if not isinstance(step, dict):
                    continue
                uses = str(step.get("uses", ""))
                context_tag = f"{wf_file.name}:{job_name}:{step.get('name', 'unnamed')}"
                if "astral-sh/setup-uv" in uses:
                    _validate_setup_uv_step(step, context_tag)
                elif "devcontainers/ci" in uses:
                    _validate_devcontainer_step(step, context_tag)


def test_ci_workflow_has_tooling_cache_step() -> None:
    """Validate that ci.yml includes tooling cache for mypy, ruff, and pytest with stable key."""
    import yaml

    ci_file = Path(".github/workflows/ci.yml")
    assert ci_file.is_file()
    content = yaml.safe_load(ci_file.read_text(encoding="utf-8")) or {}
    steps = content["jobs"]["validate"]["steps"]
    cache_steps = [
        s for s in steps if isinstance(s, dict) and "actions/cache" in str(s.get("uses", ""))
    ]
    assert len(cache_steps) >= 1
    cache_with = cache_steps[0].get("with", {})
    assert isinstance(cache_with, dict)
    cache_paths = str(cache_with.get("path", ""))
    assert ".mypy_cache" in cache_paths
    assert ".ruff_cache" in cache_paths
    assert ".pytest_cache" in cache_paths
    cache_key = str(cache_with.get("key", ""))
    assert "tooling-cache-" in cache_key
    assert "hashFiles" in cache_key
    assert "github.sha" not in cache_key
