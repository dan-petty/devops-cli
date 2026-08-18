import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.rule import Rule
from rich.table import Table

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.config.defaults import (
    DEFAULT_PYTHON_VERSION,
    DEFAULT_REMOTE_CI_POLL_INTERVAL_SECONDS,
    DEFAULT_REMOTE_CI_TIMEOUT_SECONDS,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.core.process import run_subprocess
from devops_cli.lang import MESSAGES

app = typer.Typer(help="Run tests, linting, formatting, and type-checks.")
remote_app = typer.Typer(
    help="Inspect, monitor, and triage remote GitHub Actions CI workflows.",
    no_args_is_help=False,
)
app.add_typer(remote_app, name="remote")
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
    result = subprocess.run(full_cmd, cwd=_ROOT, timeout=timeout, capture_output=False)
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


def _run_all_checks(*, lint_fix: bool, format_fix: bool) -> list[tuple[str, bool]]:
    checks: list[tuple[str, bool]] = []
    _clean_coverage_artifacts()

    _section("python version check (3.14+)")
    checks.append(("python_version", _verify_python_314_environment()))

    _section("pytest & coverage")
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

    _section(f"mypy (py{DEFAULT_PYTHON_VERSION.replace('.', '')} strict)")
    checks.append(
        (
            "typecheck",
            _run(
                [
                    "uv",
                    "run",
                    "mypy",
                    "--python-version",
                    DEFAULT_PYTHON_VERSION,
                    "--strict",
                    "src",
                ]
            ),
        )
    )

    _section("uv audit")
    checks.append(("audit", _run(["uv", "audit"])))

    _section("bandit security scan")
    checks.append(("security", _run(["uv", "run", "bandit", "-r", "src", "-ll", "-s", "B608"])))

    _section("actionlint (github workflows)")
    checks.append(("actionlint", _run(["uv", "run", "actionlint"])))

    _section("docs validation")
    checks.append(("docs", _run(["uv", "run", "devops", "docs", "check"])))

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


def _get_current_git_branch() -> str:
    res = run_subprocess(["git", "branch", "--show-current"], check=False, quiet=True)
    if res.returncode == 0 and res.stdout and res.stdout.strip():
        return str(res.stdout.strip())
    return "main"


@remote_app.command("status")
def remote_status(
    branch: Annotated[
        str | None,
        typer.Option("--branch", "-b", help="Target branch (defaults to current branch)"),
    ] = None,
    pr: Annotated[
        int | None,
        typer.Option("--pr", "-p", help="Pull request number to inspect checks for"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Number of workflow runs to display"),
    ] = 5,
) -> None:
    """Show status of remote GitHub Actions CI workflow runs or PR checks."""
    if not shutil.which(CONST_GH_CLI):
        rprint(f"[red]{MESSAGES.pr.gh_cli_required}[/red]")
        raise typer.Exit(1)

    if pr is not None:
        rprint(f"[cyan]{MESSAGES.remote_ci.fetching_runs} (PR #{pr})[/cyan]")
        res = run_subprocess([CONST_GH_CLI, "pr", "checks", str(pr)], check=False)
        if res.returncode != 0:
            if not res.stdout.strip() and not res.stderr.strip():
                rprint(f"[yellow]{MESSAGES.remote_ci.no_checks_found.format(number=pr)}[/yellow]")
            raise typer.Exit(res.returncode)
        return

    target_branch = branch or _get_current_git_branch()
    rprint(
        f"[cyan]{MESSAGES.remote_ci.fetching_runs} (branch: [bold]{target_branch}[/bold])[/cyan]"
    )
    res = run_subprocess(
        [
            CONST_GH_CLI,
            "run",
            "list",
            "--branch",
            target_branch,
            "--limit",
            str(limit),
            "--json",
            "databaseId,name,status,conclusion,event,url,updatedAt",
        ],
        check=False,
    )
    if res.returncode != 0:
        rprint(f"[red]Failed to fetch remote runs: {res.stderr}[/red]")
        raise typer.Exit(res.returncode)

    try:
        runs = json.loads(res.stdout) if res.stdout.strip() else []
    except json.JSONDecodeError:
        runs = []

    if not runs:
        rprint(f"[yellow]{MESSAGES.remote_ci.no_runs_found}[/yellow]")
        return

    table = Table(title=f"GitHub Actions CI Runs — {target_branch}", title_style="bold")
    table.add_column("ID", style="dim")
    table.add_column("Workflow", style="cyan")
    table.add_column("Event", style="magenta")
    table.add_column("Status")
    table.add_column("Conclusion")
    table.add_column("Updated", style="dim")
    table.add_column("URL", overflow="fold")

    for run_item in runs:
        run_id = str(run_item.get("databaseId", ""))
        name = str(run_item.get("name", ""))
        event = str(run_item.get("event", ""))
        status = str(run_item.get("status", ""))
        conclusion = str(run_item.get("conclusion", "")) or "-"
        updated = str(run_item.get("updatedAt", ""))[:19].replace("T", " ")
        url = str(run_item.get("url", ""))

        if conclusion == "success":
            conclusion_str = "[green]✓ success[/green]"
        elif conclusion == "failure":
            conclusion_str = "[red]✗ failure[/red]"
        elif conclusion == "cancelled":
            conclusion_str = "[yellow]cancelled[/yellow]"
        else:
            conclusion_str = f"[dim]{conclusion}[/dim]"

        status_str = (
            "[green]completed[/green]" if status == "completed" else f"[yellow]{status}[/yellow]"
        )
        table.add_row(run_id, name, event, status_str, conclusion_str, updated, url)

    console.print(table)


@remote_app.command("logs")
def remote_logs(
    run_id: Annotated[
        str | None,
        typer.Option("--run-id", "-r", help="Workflow run ID to inspect"),
    ] = None,
    job: Annotated[
        str | None,
        typer.Option("--job", "-j", help="Specific job ID to view logs for"),
    ] = None,
    failed: Annotated[
        bool,
        typer.Option("--failed/--all", help="Show only failed step logs or complete logs"),
    ] = True,
) -> None:
    """Fetch and display logs from remote GitHub Actions workflow runs."""
    if not shutil.which(CONST_GH_CLI):
        rprint(f"[red]{MESSAGES.pr.gh_cli_required}[/red]")
        raise typer.Exit(1)

    if job:
        cmd = [CONST_GH_CLI, "run", "view", f"--job={job}"]
        if failed:
            cmd.append("--log-failed")
        else:
            cmd.append("--log")
        res = run_subprocess(cmd, check=False)
        if res.returncode != 0:
            raise typer.Exit(res.returncode)
        return

    target_run_id = run_id
    if not target_run_id:
        branch = _get_current_git_branch()
        res = run_subprocess(
            [
                CONST_GH_CLI,
                "run",
                "list",
                "--branch",
                branch,
                "--limit",
                "1",
                "--json",
                "databaseId",
            ],
            check=False,
            quiet=True,
        )
        if res.returncode == 0 and res.stdout.strip():
            try:
                data = json.loads(res.stdout)
                if data and isinstance(data, list):
                    target_run_id = str(data[0].get("databaseId", ""))
            except json.JSONDecodeError:
                pass

    if not target_run_id:
        rprint("[red]Could not determine workflow run ID. Specify with --run-id <id>.[/red]")
        raise typer.Exit(1)

    rprint(f"[cyan]{MESSAGES.remote_ci.fetching_logs.format(run_id=target_run_id)}[/cyan]")
    cmd = [CONST_GH_CLI, "run", "view", target_run_id]
    if failed:
        cmd.append("--log-failed")
    else:
        cmd.append("--log")
    res = run_subprocess(cmd, check=False)
    if res.returncode != 0:
        raise typer.Exit(res.returncode)


@remote_app.command("watch")
def remote_watch(
    pr: Annotated[
        int | None,
        typer.Option("--pr", "-p", help="Pull request number to watch"),
    ] = None,
    branch: Annotated[
        str | None,
        typer.Option("--branch", "-b", help="Branch name to watch"),
    ] = None,
    interval: Annotated[
        float,
        typer.Option("--interval", "-i", help="Polling interval in seconds"),
    ] = DEFAULT_REMOTE_CI_POLL_INTERVAL_SECONDS,
    timeout: Annotated[
        float,
        typer.Option("--timeout", "-t", help="Maximum watch timeout in seconds"),
    ] = DEFAULT_REMOTE_CI_TIMEOUT_SECONDS,
) -> None:
    """Watch remote CI checks until all runs reach completion."""
    if not shutil.which(CONST_GH_CLI):
        rprint(f"[red]{MESSAGES.pr.gh_cli_required}[/red]")
        raise typer.Exit(1)

    target_branch = branch or (_get_current_git_branch() if pr is None else None)
    start_time = time.monotonic()

    if pr is not None:
        rprint(
            f"[cyan]{MESSAGES.remote_ci.watching_ci.format(number=pr, interval=interval)}[/cyan]"
        )
    else:
        rprint(
            f"[cyan]Watching remote CI runs for branch '{target_branch}' "
            f"(poll interval: {interval}s)...[/cyan]"
        )

    while True:
        if (time.monotonic() - start_time) > timeout:
            rprint(f"[red]Watch timed out after {timeout:.0f} seconds.[/red]")
            raise typer.Exit(1)

        if pr is not None:
            res = run_subprocess(
                [CONST_GH_CLI, "pr", "checks", str(pr), "--json", "name,state,bucket,url"],
                check=False,
                quiet=True,
            )
            if res.returncode == 0 and res.stdout.strip():
                try:
                    checks = json.loads(res.stdout)
                    if checks and isinstance(checks, list):
                        all_done = all(
                            c.get("state", "").lower()
                            in ("completed", "success", "failure", "cancelled")
                            for c in checks
                        )
                        failed_count = sum(
                            1
                            for c in checks
                            if c.get("state", "").lower() in ("failure", "cancelled")
                            or c.get("bucket", "") == "fail"
                        )
                        if all_done:
                            if failed_count == 0:
                                rprint(f"[green]{MESSAGES.remote_ci.ci_passed}[/green]")
                                raise typer.Exit(0)
                            else:
                                rprint(f"[red]{MESSAGES.remote_ci.ci_failed}[/red]")
                                raise typer.Exit(1)
                except json.JSONDecodeError:
                    pass
        elif target_branch:
            res = run_subprocess(
                [
                    CONST_GH_CLI,
                    "run",
                    "list",
                    "--branch",
                    target_branch,
                    "--limit",
                    "1",
                    "--json",
                    "status,conclusion,name",
                ],
                check=False,
                quiet=True,
            )
            if res.returncode == 0 and res.stdout.strip():
                try:
                    runs = json.loads(res.stdout)
                    if runs and isinstance(runs, list):
                        latest = runs[0]
                        if latest.get("status") == "completed":
                            conc = latest.get("conclusion")
                            if conc == "success":
                                rprint(f"[green]{MESSAGES.remote_ci.ci_passed}[/green]")
                                raise typer.Exit(0)
                            else:
                                rprint(f"[red]{MESSAGES.remote_ci.ci_failed} ({conc})[/red]")
                                raise typer.Exit(1)
                except json.JSONDecodeError:
                    pass

        time.sleep(interval)
