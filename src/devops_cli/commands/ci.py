"""Project testing, validation, and code quality checks."""

from __future__ import annotations

from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.rule import Rule
from rich.table import Table

from devops_cli.config.defaults import (
    DEFAULT_PYTHON_VERSION,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import find_top_level_repo_root
from devops_cli.telemetry import record_metric, trace_span

app = new_typer(help="Run tests, linting, formatting, and type-checks.")
console = Console()

_ROOT = find_top_level_repo_root(__file__)


# =============================================================================
# Environment & Subprocess Helpers
# =============================================================================


def _verify_python_314_environment() -> bool:
    """Verify runtime environment meets strict Python 3.14+ requirements."""
    import sys

    if sys.version_info < (3, 14):  # noqa: UP036
        ver_str = sys.version.split()[0]
        rprint(
            f"[red]Strict Python {DEFAULT_PYTHON_VERSION}+ requirement failed. "
            f"Current: {ver_str}[/red]"
        )
        return False
    return True


def _run(cmd: list[str], timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS) -> bool:
    """Run a CI check subprocess, printing stderr output on failure for diagnostics."""
    full_cmd = list(cmd)
    if full_cmd and full_cmd[0] == "uv" and "--preview-features" not in full_cmd:
        full_cmd[1:1] = ["--preview-features", "malware-check"]
    result = run_subprocess(full_cmd, cwd=_ROOT, timeout=timeout, capture_output=False)
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


# =============================================================================
# Pipeline Execution
# =============================================================================


def _run_all_checks(*, lint_fix: bool, format_fix: bool) -> list[tuple[str, bool]]:
    checks: list[tuple[str, bool]] = []
    _clean_coverage_artifacts()

    with trace_span("ci.run_pipeline", attributes={"lint_fix": lint_fix, "format_fix": format_fix}):
        _section("python version check (3.14+)")
        with trace_span("ci.step.python_version"):
            py_ok = _verify_python_314_environment()
            checks.append(("python_version", py_ok))
            record_metric(
                "ci.step_pass",
                1.0 if py_ok else 0.0,
                attributes={"step": "python_version"},
            )

        _section("pytest & coverage")
        with trace_span("ci.step.test_and_coverage"):
            test_cov_ok = _run(
                [
                    "uv",
                    "run",
                    "pytest",
                    "-n",
                    "auto",
                    "--maxprocesses=4",
                    "--cov=src",
                    "--cov-report=term-missing",
                ]
            )
            _clean_coverage_artifacts()
            checks.append(("test", test_cov_ok))
            checks.append(("coverage", test_cov_ok))
            record_metric("ci.step_pass", 1.0 if test_cov_ok else 0.0, attributes={"step": "test"})

        _section("ruff check")
        with trace_span("ci.step.lint"):
            lint_cmd = ["uv", "run", "ruff", "check", "."]
            if lint_fix:
                lint_cmd.append("--fix")
            lint_ok = _run(lint_cmd)
            checks.append(("lint", lint_ok))
            record_metric("ci.step_pass", 1.0 if lint_ok else 0.0, attributes={"step": "lint"})

        _section("ruff format")
        with trace_span("ci.step.format"):
            fmt_cmd = ["uv", "run", "ruff", "format"]
            if not format_fix:
                fmt_cmd.append("--check")
            fmt_cmd.append(".")
            fmt_ok = _run(fmt_cmd)
            checks.append(("format", fmt_ok))
            record_metric("ci.step_pass", 1.0 if fmt_ok else 0.0, attributes={"step": "format"})

        _section(f"mypy (py{DEFAULT_PYTHON_VERSION.replace('.', '')} strict)")
        with trace_span("ci.step.typecheck"):
            mypy_ok = _run(
                [
                    "uv",
                    "run",
                    "mypy",
                    "--python-version",
                    DEFAULT_PYTHON_VERSION,
                    "--strict",
                    "src",
                ]
            )
            checks.append(("typecheck", mypy_ok))
            record_metric("ci.step_pass", 1.0 if mypy_ok else 0.0, attributes={"step": "typecheck"})

        _section("uv audit")
        with trace_span("ci.step.audit"):
            audit_ok = _run(["uv", "audit"])
            checks.append(("audit", audit_ok))
            record_metric("ci.step_pass", 1.0 if audit_ok else 0.0, attributes={"step": "audit"})

        _section("bandit security scan")
        with trace_span("ci.step.security"):
            sec_ok = _run(["uv", "run", "bandit", "-r", "src", "-ll", "-s", "B608"])
            checks.append(("security", sec_ok))
            record_metric("ci.step_pass", 1.0 if sec_ok else 0.0, attributes={"step": "security"})

        _section("actionlint (github workflows)")
        with trace_span("ci.step.actionlint"):
            act_ok = _run(["uv", "run", "actionlint"])
            checks.append(("actionlint", act_ok))
            record_metric("ci.step_pass", 1.0 if act_ok else 0.0, attributes={"step": "actionlint"})

        _section("docs validation")
        with trace_span("ci.step.docs"):
            docs_ok = _run(["uv", "run", "devops", "docs", "check"])
            checks.append(("docs", docs_ok))
            record_metric("ci.step_pass", 1.0 if docs_ok else 0.0, attributes={"step": "docs"})

    return checks


def _print_summary(checks: list[tuple[str, bool]]) -> None:
    table = Table(title="CI Summary", title_style="bold")
    table.add_column("Check", style="cyan")
    table.add_column("Result")
    for name, ok in checks:
        table.add_row(name, "[green]✓ pass[/green]" if ok else "[red]✗ fail[/red]")
    console.print(table)


@app.callback(invoke_without_command=True)
def all_checks(ctx: typer.Context) -> None:
    """Run all checks in sequence: version, test, coverage, lint, format, typecheck, audit.

    Also includes security scan checks.
    """
    if ctx.invoked_subcommand is not None:
        return

    checks = _run_all_checks(lint_fix=False, format_fix=False)
    _print_summary(checks)

    if not all(ok for _, ok in checks):
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
            rprint("[red]Invalid keyword filter expression.[/red]")
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
    checks = _run_all_checks(lint_fix=fix, format_fix=fix)
    _print_summary(checks)
    if not all(ok for _, ok in checks):
        raise typer.Exit(1)
