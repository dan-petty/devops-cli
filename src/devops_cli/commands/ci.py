"""Project testing, validation, and code quality checks."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.rule import Rule
from rich.table import Table

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS

app = typer.Typer(help="Run tests, linting, formatting, and type-checks.")
console = Console()


def _find_root() -> Path:
    cur = Path(__file__).resolve().parent
    while cur != cur.parent:
        if (cur / "pyproject.toml").exists():
            return cur
        cur = cur.parent
    # If pyproject.toml was never found, return the filesystem root as a safe fallback.
    return cur


_ROOT = _find_root()


def _run(cmd: list[str], timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS) -> bool:
    """Run a CI check subprocess, printing stderr output on failure for diagnostics."""
    result = subprocess.run(cmd, cwd=_ROOT, timeout=timeout, capture_output=False)
    return result.returncode == 0


def _section(title: str) -> None:
    console.print(Rule(f" {title} ", style="cyan"))


def _run_all_checks(*, lint_fix: bool, format_fix: bool) -> list[tuple[str, bool]]:
    checks: list[tuple[str, bool]] = []

    _section("pytest")
    checks.append(("test", _run(["uv", "run", "pytest"])))

    _section("ruff check")
    lint_cmd = ["uv", "run", "ruff", "check", "."]
    if lint_fix:
        lint_cmd.append("--fix")
    checks.append(("lint", _run(lint_cmd)))

    _section("ruff format")
    fmt_cmd = ["uv", "run", "ruff", "format"]
    if not format_fix:
        fmt_cmd.append("--check")
    fmt_cmd.append(".")
    checks.append(("format", _run(fmt_cmd)))

    _section("mypy")
    checks.append(("typecheck", _run(["uv", "run", "mypy", "src"])))

    _section("uv audit")
    checks.append(("audit", _run(["uv", "audit"])))

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
    """Run all checks in sequence: test, lint, format, typecheck, audit."""
    if ctx.invoked_subcommand is not None:
        return

    checks = _run_all_checks(lint_fix=False, format_fix=False)
    _print_summary(checks)

    if not all(ok for _, ok in checks):
        raise typer.Exit(1)


@app.command()
def test(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Verbose output")] = False,
    k: Annotated[str | None, typer.Option("-k", help="Filter tests by keyword expression")] = None,
    x: Annotated[bool, typer.Option("-x", help="Stop after first failure")] = False,
) -> None:
    """Run the pytest test suite."""
    cmd = ["uv", "run", "pytest"]
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
def lint(
    fix: Annotated[bool, typer.Option("--fix", help="Auto-fix violations where possible")] = False,
) -> None:
    """Run ruff linter across the project."""
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
    cmd = ["uv", "run", "ruff", "format"]
    if not fix:
        cmd.append("--check")
    cmd.append(".")
    if not _run(cmd):
        raise typer.Exit(1)


@app.command()
def typecheck() -> None:
    """Run mypy static type-checker over src/."""
    if not _run(["uv", "run", "mypy", "src"]):
        raise typer.Exit(1)


@app.command()
def audit() -> None:
    """Run uv audit to check for known package vulnerabilities."""
    if not _run(["uv", "audit"]):
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
