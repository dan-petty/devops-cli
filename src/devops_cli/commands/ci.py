"""Project testing, validation, and code quality checks with async concurrent execution."""

from __future__ import annotations

import asyncio
import importlib
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.config.defaults import (
    DEFAULT_BANDIT_SEVERITY,
    DEFAULT_PYTEST_NUMPROCESSES,
    DEFAULT_PYTHON_VERSION,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import set_dry_run
from devops_cli.lang import HELP, MESSAGES

_LAZY_OBJECT_MAPPING: dict[str, tuple[str, str]] = {
    "run_subprocess": ("devops_cli.core.process", "run_subprocess"),
    "run_subprocess_async": ("devops_cli.core.process", "run_subprocess_async"),
    "record_metric": ("devops_cli.telemetry", "record_metric"),
    "trace_span": ("devops_cli.telemetry", "trace_span"),
    "print_error": ("devops_cli.output", "print_error"),
    "print_muted": ("devops_cli.output", "print_muted"),
    "print_section": ("devops_cli.output", "print_section"),
    "print_table": ("devops_cli.output", "print_table"),
    "write_stderr": ("devops_cli.output", "write_stderr"),
    "write_stdout": ("devops_cli.output", "write_stdout"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_OBJECT_MAPPING:
        mod_path, obj_name = _LAZY_OBJECT_MAPPING[name]
        module = importlib.import_module(mod_path)
        return getattr(module, obj_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _get(name: str) -> Any:
    mod_dict = sys.modules[__name__].__dict__
    if name in mod_dict:
        return mod_dict[name]
    if name in _LAZY_OBJECT_MAPPING:
        mod_path, obj_name = _LAZY_OBJECT_MAPPING[name]
        module = importlib.import_module(mod_path)
        return getattr(module, obj_name)
    return getattr(sys.modules[__name__], name)


app = new_typer(help=HELP.ci.app)

# Repo root: src/devops_cli/commands/ci.py -> parents[3]
_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class CheckResult:
    """Immutable result record for a single CI pipeline check."""

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
        _get("print_error")(
            MESSAGES.ci.python_version_fail.format(
                required=DEFAULT_PYTHON_VERSION, current=ver_str
            ),
            prefix=False,
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
    result = _get("run_subprocess")(
        full_cmd, cwd=_ROOT, timeout=timeout, capture_output=capture_output
    )
    return bool(result.returncode == 0)


def _section(title: str) -> None:
    _get("print_section")(f" {title} ", style="cyan")


def _clean_coverage_artifacts() -> None:
    """Clean up residual temporary .coverage.* worker files from root workspace and .data/."""
    for target_dir in (_ROOT, _ROOT / ".data"):
        if target_dir.exists():
            for path in target_dir.glob(".coverage*"):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
    root_coverage_xml = _ROOT / "coverage.xml"
    if root_coverage_xml.exists():
        try:
            root_coverage_xml.unlink(missing_ok=True)
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

    with _get("trace_span")(span_name):
        proc = await _get("run_subprocess_async")(
            full_cmd,
            cwd=_ROOT,
            timeout=timeout,
            capture_output=True,
        )
        passed = proc.returncode == 0
        dur = time.perf_counter() - t0
        _get("record_metric")(
            "ci.step_pass", 1.0 if passed else 0.0, attributes={"step": metric_step}
        )
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
    _get("record_metric")(
        "ci.step_pass", 1.0 if py_ok else 0.0, attributes={"step": "python_version"}
    )
    py_result = CheckResult(
        name="python_version",
        display_title=MESSAGES.ci.python_version_check,
        passed=py_ok,
        duration_seconds=py_dur,
    )
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

    with _get("trace_span")(
        "ci.run_pipeline", attributes={"lint_fix": lint_fix, "format_fix": format_fix}
    ):
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
                _get("write_stdout")(res.stdout.rstrip() + "\n")
            if res.stderr:
                _get("write_stderr")(res.stderr.rstrip() + "\n")


def _print_summary(results: list[CheckResult], total_elapsed: float) -> None:
    """Render the final formatted CI Summary table."""
    rows: list[list[str]] = []
    for res in results:
        status_text = "[green]✓ pass[/green]" if res.passed else "[red]✗ fail[/red]"
        dur_text = f"{res.duration_seconds:.2f}s" if res.duration_seconds > 0 else "<0.01s"
        rows.append([res.name, status_text, dur_text])

    _get("print_table")(
        title=MESSAGES.ci.ci_summary_title,
        columns=[(MESSAGES.ci.col_check, "cyan"), MESSAGES.ci.col_result, ("Duration", "dim")],
        rows=rows,
    )
    _get("print_muted")(f"Total Elapsed: {total_elapsed:.2f}s (concurrent async execution)\n")


@app.callback(invoke_without_command=True)
def all_checks(
    ctx: typer.Context,
    fix: Annotated[
        bool,
        typer.Option("--fix/--no-fix", help=HELP.ci.fix_all),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Run all CI checks concurrently in parallel with non-blocking async execution."""
    if ctx.invoked_subcommand is not None:
        return
    if dry_run:
        set_dry_run(True)

    t0 = time.perf_counter()
    results = asyncio.run(_run_all_checks_async(lint_fix=fix, format_fix=fix))
    _print_failures(results)
    _print_summary(results, total_elapsed=time.perf_counter() - t0)

    if not all(res.passed for res in results):
        raise typer.Exit(1)


# =============================================================================
# Individual CI Commands
# =============================================================================


@app.command()
def test(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help=HELP.options.verbose)] = False,
    k: Annotated[str | None, typer.Option("-k", help=HELP.ci.filter_keyword)] = None,
    x: Annotated[bool, typer.Option("-x", help=HELP.ci.stop_fail)] = False,
    numprocesses: Annotated[
        str, typer.Option("-n", "--numprocesses", help=HELP.ci.num_workers)
    ] = DEFAULT_PYTEST_NUMPROCESSES,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Run the pytest test suite in parallel leveraging all CPU cores."""
    if dry_run:
        set_dry_run(True)
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    cmd = ["uv", "run", "pytest", "-n", numprocesses]
    if verbose:
        cmd.append("-v")
    if k:
        if k.startswith("-"):
            _get("print_error")("Invalid keyword filter expression.", prefix=False)
            raise typer.Exit(1)
        cmd.extend(["-k", k])
    if x:
        cmd.append("-x")
    if not _run(cmd):
        raise typer.Exit(1)


@app.command()
def coverage(
    html: Annotated[bool, typer.Option("--html", help=HELP.ci.html_report)] = False,
    xml: Annotated[bool, typer.Option("--xml", help=HELP.ci.xml_report)] = False,
    numprocesses: Annotated[
        str, typer.Option("-n", "--numprocesses", help=HELP.ci.num_workers)
    ] = DEFAULT_PYTEST_NUMPROCESSES,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Run pytest with parallel code coverage analysis over src/."""
    if dry_run:
        set_dry_run(True)
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
    if xml:
        cmd.append("--cov-report=xml")
    if not _run(cmd):
        raise typer.Exit(1)


@app.command()
def lint(
    fix: Annotated[bool, typer.Option("--fix", help=HELP.ci.auto_fix)] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Run ruff linter across the project."""
    if dry_run:
        set_dry_run(True)
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    cmd = ["uv", "run", "ruff", "check", "."]
    if fix:
        cmd.append("--fix")
    if not _run(cmd):
        raise typer.Exit(1)


@app.command(name="format")
def fmt(
    fix: Annotated[bool, typer.Option("--fix", help=HELP.ci.format_fix)] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Check (or apply) code formatting with ruff format."""
    if dry_run:
        set_dry_run(True)
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    cmd = ["uv", "run", "ruff", "format"]
    if not fix:
        cmd.append("--check")
    cmd.append(".")
    if not _run(cmd):
        raise typer.Exit(1)


@app.command()
def typecheck(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Run mypy static type-checker strictly targeting Python 3.14 over src/."""
    if dry_run:
        set_dry_run(True)
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
def audit(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Run uv audit to check for known package vulnerabilities."""
    if dry_run:
        set_dry_run(True)
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    if not _run(["uv", "audit"]):
        raise typer.Exit(1)


@app.command()
def security(
    severity: Annotated[
        str,
        typer.Option("--severity", "-s", help=HELP.ci.min_severity),
    ] = DEFAULT_BANDIT_SEVERITY,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Run bandit static security vulnerability analysis over src/."""
    if dry_run:
        set_dry_run(True)
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    level_flag = (
        "-lll" if severity.lower() == "high" else ("-l" if severity.lower() == "low" else "-ll")
    )
    cmd = ["uv", "run", "bandit", "-r", "src", level_flag, "-s", "B608"]
    if not _run(cmd):
        raise typer.Exit(1)


@app.command()
def actionlint(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Run actionlint to validate GitHub Actions workflows for syntax and schema errors."""
    if dry_run:
        set_dry_run(True)
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    if not _run(["uv", "run", "actionlint"]):
        raise typer.Exit(1)


@app.command()
def docs(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Verify that documentation is up to date with CLI commands and configuration."""
    if dry_run:
        set_dry_run(True)
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    if not _run(["uv", "run", "devops", "docs", "check"]):
        raise typer.Exit(1)


@app.command()
def run(
    fix: Annotated[
        bool,
        typer.Option("--fix/--no-fix", help=HELP.ci.fix_all),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Run full CI and return a single pass/fail status."""
    if dry_run:
        set_dry_run(True)
    t0 = time.perf_counter()
    results = asyncio.run(_run_all_checks_async(lint_fix=fix, format_fix=fix))
    _print_failures(results)
    _print_summary(results, total_elapsed=time.perf_counter() - t0)
    if not all(res.passed for res in results):
        raise typer.Exit(1)
