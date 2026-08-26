"""Project testing, validation, and code quality checks with async concurrent execution."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Annotated

import typer
from rich.console import Console
from rich.rule import Rule
from rich.table import Table

from devops_cli.config.defaults import (
    DEFAULT_PYTHON_VERSION,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess, run_subprocess_async
from devops_cli.core.repo import find_top_level_repo_root
from devops_cli.lang import HELP, MESSAGES
from devops_cli.telemetry import record_metric, trace_span

app = new_typer(help=HELP.ci.app)
console = Console()

_ROOT = find_top_level_repo_root(__file__)


@dataclass(frozen=True)
class CheckResult:
    name: str
    display_title: str
    passed: bool
    duration_seconds: float
    stdout: str = ""
    stderr: str = ""


# =============================================================================
# Environment & Subprocess Helpers
# =============================================================================


def _verify_python_314_environment() -> bool:
    """Verify runtime environment meets strict Python 3.14+ requirements."""
    import sys

    if sys.version_info < (3, 14):  # noqa: UP036
        ver_str = sys.version.split()[0]
        console.print(
            f"[red]{MESSAGES.ci.python_version_fail.format(required=DEFAULT_PYTHON_VERSION, current=ver_str)}[/red]"
        )
        return False
    return True


def _run(
    cmd: list[str],
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    capture_output: bool = False,
) -> bool:
    """Run a CI check subprocess synchronously."""
    full_cmd = list(cmd)
    if full_cmd and full_cmd[0] == "uv" and "--preview-features" not in full_cmd:
        full_cmd[1:1] = ["--preview-features", "malware-check"]
    result = run_subprocess(full_cmd, cwd=_ROOT, timeout=timeout, capture_output=capture_output)
    return result.returncode == 0


def _section(title: str) -> None:
    console.print(Rule(f" {title} ", style="cyan"))


def _clean_coverage_artifacts() -> None:
    """Clean up residual temporary .coverage.* worker files from root workspace."""
    for path in _ROOT.glob(".coverage*"):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


async def _execute_check_async(
    name: str,
    display_title: str,
    cmd: list[str],
    span_name: str,
    metric_step: str,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
) -> CheckResult:
    """Execute an individual CI verification step asynchronously and record telemetry."""
    t0 = time.perf_counter()
    full_cmd = list(cmd)
    if full_cmd and full_cmd[0] == "uv" and "--preview-features" not in full_cmd:
        full_cmd[1:1] = ["--preview-features", "malware-check"]

    with trace_span(span_name):
        proc = await run_subprocess_async(
            full_cmd,
            cwd=_ROOT,
            timeout=timeout,
            capture_output=True,
        )
        passed = proc.returncode == 0
        dur = time.perf_counter() - t0
        record_metric("ci.step_pass", 1.0 if passed else 0.0, attributes={"step": metric_step})
        stdout_val = getattr(proc, "stdout", "") or ""
        stderr_val = getattr(proc, "stderr", "") or ""
        return CheckResult(
            name=name,
            display_title=display_title,
            passed=passed,
            duration_seconds=dur,
            stdout=stdout_val
            if isinstance(stdout_val, str)
            else stdout_val.decode("utf-8", errors="replace"),
            stderr=stderr_val
            if isinstance(stderr_val, str)
            else stderr_val.decode("utf-8", errors="replace"),
        )


# =============================================================================
# Pipeline Execution
# =============================================================================


async def _run_all_checks_async(*, lint_fix: bool, format_fix: bool) -> list[CheckResult]:
    """Execute all CI verification gates concurrently using asyncio."""
    _clean_coverage_artifacts()

    py_t0 = time.perf_counter()
    py_ok = _verify_python_314_environment()
    py_dur = time.perf_counter() - py_t0
    record_metric("ci.step_pass", 1.0 if py_ok else 0.0, attributes={"step": "python_version"})
    py_result = CheckResult("python_version", MESSAGES.ci.python_version_check, py_ok, py_dur)
    if not py_ok:
        return [py_result]

    # If fixes were requested, apply in-place modifications first before verification scans
    if format_fix:
        await _execute_check_async(
            "format_fix",
            MESSAGES.ci.ruff_format,
            ["uv", "run", "ruff", "format", "."],
            "ci.step.format_fix",
            "format_fix",
        )
    if lint_fix:
        await _execute_check_async(
            "lint_fix",
            MESSAGES.ci.ruff_check,
            ["uv", "run", "ruff", "check", "--fix", "."],
            "ci.step.lint_fix",
            "lint_fix",
        )

    with trace_span("ci.run_pipeline", attributes={"lint_fix": lint_fix, "format_fix": format_fix}):
        tasks = [
            _execute_check_async(
                "test",
                MESSAGES.ci.pytest_coverage,
                [
                    "uv",
                    "run",
                    "pytest",
                    "-n",
                    "auto",
                    "--maxprocesses=4",
                    "--cov=src",
                    "--cov-report=term-missing",
                ],
                "ci.step.test_and_coverage",
                "test",
            ),
            _execute_check_async(
                "lint",
                MESSAGES.ci.ruff_check,
                ["uv", "run", "ruff", "check", "."],
                "ci.step.lint",
                "lint",
            ),
            _execute_check_async(
                "format",
                MESSAGES.ci.ruff_format,
                ["uv", "run", "ruff", "format", "--check", "."],
                "ci.step.format",
                "format",
            ),
            _execute_check_async(
                "typecheck",
                f"mypy (py{DEFAULT_PYTHON_VERSION.replace('.', '')} strict)",
                [
                    "uv",
                    "run",
                    "mypy",
                    "--python-version",
                    DEFAULT_PYTHON_VERSION,
                    "--strict",
                    "src",
                ],
                "ci.step.typecheck",
                "typecheck",
            ),
            _execute_check_async(
                "audit",
                MESSAGES.ci.uv_audit,
                ["uv", "audit"],
                "ci.step.audit",
                "audit",
            ),
            _execute_check_async(
                "security",
                MESSAGES.ci.bandit_scan,
                ["uv", "run", "bandit", "-r", "src", "-ll", "-s", "B608"],
                "ci.step.security",
                "security",
            ),
            _execute_check_async(
                "actionlint",
                MESSAGES.ci.actionlint,
                ["uv", "run", "actionlint"],
                "ci.step.actionlint",
                "actionlint",
            ),
            _execute_check_async(
                "docs",
                MESSAGES.ci.docs_validation,
                ["uv", "run", "devops", "docs", "check"],
                "ci.step.docs",
                "docs",
            ),
        ]

        raw_results = await asyncio.gather(*tasks)
        _clean_coverage_artifacts()

        test_result = raw_results[0]
        coverage_result = CheckResult(
            name="coverage",
            display_title=MESSAGES.ci.pytest_coverage,
            passed=test_result.passed,
            duration_seconds=test_result.duration_seconds,
            stdout=test_result.stdout,
            stderr=test_result.stderr,
        )

        return [py_result, test_result, coverage_result] + list(raw_results[1:])


def _run_all_checks(*, lint_fix: bool, format_fix: bool) -> list[tuple[str, bool]]:
    """Synchronous entrypoint for executing CI pipeline."""
    results = asyncio.run(_run_all_checks_async(lint_fix=lint_fix, format_fix=format_fix))
    _print_failures(results)
    return [(res.name, res.passed) for res in results]


def _print_failures(results: list[CheckResult]) -> None:
    """Print diagnostic failure outputs for failed CI checks."""
    for res in results:
        if not res.passed and (res.stdout or res.stderr):
            _section(res.display_title)
            if res.stdout:
                console.print(res.stdout.rstrip())
            if res.stderr:
                console.print(res.stderr.rstrip(), style="red")


def _print_summary(results: list[CheckResult], total_elapsed: float) -> None:
    """Render the final formatted CI Summary table."""
    table = Table(title=MESSAGES.ci.ci_summary_title, title_style="bold")
    table.add_column(MESSAGES.ci.col_check, style="cyan")
    table.add_column(MESSAGES.ci.col_result)
    table.add_column("Duration", style="dim", justify="right")
    for res in results:
        status_text = "[green]✓ pass[/green]" if res.passed else "[red]✗ fail[/red]"
        dur_text = f"{res.duration_seconds:.2f}s" if res.duration_seconds > 0 else "<0.01s"
        table.add_row(res.name, status_text, dur_text)
    console.print(table)
    console.print(f"[dim]Total Elapsed: {total_elapsed:.2f}s (concurrent async execution)[/dim]\n")


@app.callback(invoke_without_command=True)
def all_checks(ctx: typer.Context) -> None:
    """Run all CI checks concurrently in parallel with non-blocking async execution."""
    if ctx.invoked_subcommand is not None:
        return

    t0 = time.perf_counter()
    results = asyncio.run(_run_all_checks_async(lint_fix=False, format_fix=False))
    _print_failures(results)
    _print_summary(results, total_elapsed=time.perf_counter() - t0)

    if not all(res.passed for res in results):
        raise typer.Exit(1)


# =============================================================================
# Individual CI Commands
# =============================================================================


@app.command()
def test(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Verbose output")] = False,
    k: Annotated[str | None, typer.Option("-k", help="Filter tests by keyword expression")] = None,
    x: Annotated[bool, typer.Option("-x", help="Stop after first failure")] = False,
    numprocesses: Annotated[
        str, typer.Option("-n", "--numprocesses", help="Number of parallel worker processes")
    ] = "auto",
) -> None:
    """Run the pytest test suite in parallel leveraging all CPU cores."""
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    cmd = ["uv", "run", "pytest", "-n", numprocesses]
    if verbose:
        cmd.append("-v")
    if k:
        if k.startswith("-"):
            console.print("[red]Invalid keyword filter expression.[/red]")
            raise typer.Exit(1)
        cmd.extend(["-k", k])
    if x:
        cmd.append("-x")
    if not _run(cmd):
        raise typer.Exit(1)


@app.command()
def coverage(
    html: Annotated[
        bool, typer.Option("--html", help="Generate HTML coverage report in htmlcov/")
    ] = False,
    numprocesses: Annotated[
        str, typer.Option("-n", "--numprocesses", help="Number of parallel worker processes")
    ] = "auto",
) -> None:
    """Run pytest with parallel code coverage analysis over src/."""
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    cmd = [
        "uv",
        "run",
        "pytest",
        "-n",
        numprocesses,
        "--cov=src",
        "--cov-report=term-missing",
    ]
    if html:
        cmd.append("--cov-report=html")
    if not _run(cmd):
        raise typer.Exit(1)


@app.command()
def lint(
    fix: Annotated[bool, typer.Option("--fix", help="Auto-fix violations where possible")] = False,
) -> None:
    """Run ruff linter across the project."""
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    cmd = ["uv", "run", "ruff", "check", "."]
    if fix:
        cmd.append("--fix")
    if not _run(cmd):
        raise typer.Exit(1)


@app.command(name="format")
def fmt(
    fix: Annotated[bool, typer.Option("--fix", help="Apply formatting changes in-place")] = False,
) -> None:
    """Check (or apply) code formatting with ruff format."""
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    cmd = ["uv", "run", "ruff", "format"]
    if not fix:
        cmd.append("--check")
    cmd.append(".")
    if not _run(cmd):
        raise typer.Exit(1)


@app.command()
def typecheck() -> None:
    """Run mypy static type-checker strictly targeting Python 3.14 over src/."""
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    if not _run(
        [
            "uv",
            "run",
            "mypy",
            "--python-version",
            DEFAULT_PYTHON_VERSION,
            "--strict",
            "src",
        ]
    ):
        raise typer.Exit(1)


@app.command()
def audit() -> None:
    """Run uv audit to check for known package vulnerabilities."""
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    if not _run(["uv", "audit"]):
        raise typer.Exit(1)


@app.command()
def security(
    severity: Annotated[
        str,
        typer.Option("--severity", "-s", help="Minimum severity threshold (low, medium, high)"),
    ] = "medium",
) -> None:
    """Run bandit static security vulnerability analysis over src/."""
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    level_flag = (
        "-lll" if severity.lower() == "high" else ("-l" if severity.lower() == "low" else "-ll")
    )
    cmd = ["uv", "run", "bandit", "-r", "src", level_flag, "-s", "B608"]
    if not _run(cmd):
        raise typer.Exit(1)


@app.command()
def actionlint() -> None:
    """Run actionlint to validate GitHub Actions workflows for syntax and schema errors."""
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    if not _run(["uv", "run", "actionlint"]):
        raise typer.Exit(1)


@app.command()
def docs() -> None:
    """Verify that documentation is up to date with CLI commands and configuration."""
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    if not _run(["uv", "run", "devops", "docs", "check"]):
        raise typer.Exit(1)


@app.command()
def run(
    fix: Annotated[
        bool,
        typer.Option("--fix/--no-fix", help="Auto-fix lint/format before reporting status"),
    ] = True,
) -> None:
    """Run full CI and return a single pass/fail status."""
    t0 = time.perf_counter()
    results = asyncio.run(_run_all_checks_async(lint_fix=fix, format_fix=fix))
    _print_failures(results)
    _print_summary(results, total_elapsed=time.perf_counter() - t0)
    if not all(res.passed for res in results):
        raise typer.Exit(1)
