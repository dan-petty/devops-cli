"""Test suite orchestration, git-diff aware test selector, and load testing."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated

import typer

from devops_cli.config.commands import BIN_K6, build_k6_cmd
from devops_cli.config.constants import CONST_CURRENT_DIR
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import find_top_level_repo_root
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.lang import ERRORS, HELP, MESSAGES
from devops_cli.output import print_error, print_info, print_muted, print_success
from devops_cli.telemetry.tracer import trace_span

app = new_typer(help=HELP.test.app, no_args_is_help=False)


def find_changed_test_files(repo_root: Path, base_ref: str = "main") -> list[Path]:
    """Find test files corresponding to modified source files via git diff."""
    changed_files: set[str] = set()

    # 1. Diff against base ref (or HEAD~1 if base ref unavailable)
    diff_proc = run_subprocess(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        cwd=repo_root,
        check=False,
    )
    if diff_proc.returncode == 0 and diff_proc.stdout:
        changed_files.update(diff_proc.stdout.strip().splitlines())

    # 2. Unstaged and staged working tree diff
    wt_proc = run_subprocess(["git", "status", "--porcelain"], cwd=repo_root, check=False)
    if wt_proc.returncode == 0 and wt_proc.stdout:
        for line in wt_proc.stdout.strip().splitlines():
            parts = line.strip().split(maxsplit=1)
            if len(parts) == 2:
                file_target = parts[1].strip()
                if " -> " in file_target:
                    file_target = file_target.split(" -> ")[-1].strip()
                changed_files.add(file_target.strip('"'))

    test_files: set[Path] = set()
    all_tests_dir = repo_root / "tests"
    available_tests = (
        {p.name: p for p in all_tests_dir.glob("test_*.py")} if all_tests_dir.exists() else {}
    )

    for path_str in changed_files:
        clean_path = path_str.strip()
        if not clean_path.endswith(".py"):
            continue

        p = repo_root / clean_path
        if clean_path.startswith("tests/") and p.exists():
            test_files.add(p)
            continue

        stem = Path(clean_path).stem
        # Map src/devops_cli/subsystem/name.py -> test_name.py or test_subsystem_name.py
        candidate_names = [
            f"test_{stem}.py",
            f"test_{stem}_cmd.py",
            f"test_commands_{stem}.py",
        ]
        for c_name in candidate_names:
            if c_name in available_tests:
                test_files.add(available_tests[c_name])

    return sorted(test_files)


# =============================================================================
# Command: devops test run
# =============================================================================


@app.command("run")
def run_test_cmd(
    target: Annotated[
        Path | None,
        typer.Argument(help="Target test file or test directory."),
    ] = None,
    changed: Annotated[
        bool,
        typer.Option("--changed", "-c", help=HELP.test.changed),
    ] = False,
    coverage: Annotated[
        bool,
        typer.Option("--cov", help=HELP.test.coverage),
    ] = False,
    fail_fast: Annotated[
        bool,
        typer.Option("--fail-fast", "-x", help=HELP.test.fail_fast),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help=HELP.test.verbose),
    ] = False,
    filter_expr: Annotated[
        str | None,
        typer.Option("-k", help="Filter tests by expression."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.test.dry_run),
    ] = False,
) -> None:
    """Execute pytest test suite with optional git-diff aware test selection."""
    repo_root = find_top_level_repo_root()
    test_args: list[str] = ["pytest"]

    if verbose:
        test_args.append("-vv")
    if fail_fast:
        test_args.append("-x")
    if filter_expr:
        test_args.extend(["-k", filter_expr])
    if coverage:
        test_args.extend(["--cov=src", "--cov-report=term-missing"])

    target_paths: list[str] = []
    if target:
        target_paths.append(str(target))
    elif changed:
        changed_tests = find_changed_test_files(repo_root)
        if not changed_tests:
            print_info(
                "No modified test files or source-associated tests detected. Running full suite."
            )
            target_paths.append("tests")
        else:
            print_info(
                f"Targeting {len(changed_tests)} test file(s) impacted by git modifications:"
            )
            for t in changed_tests:
                print_muted(f"  • {t.relative_to(repo_root)}")
                target_paths.append(str(t.relative_to(repo_root)))
    else:
        target_paths.append("tests")

    test_args.extend(target_paths)

    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops test run",
            action="execute_pytest",
            details={"args": test_args, "targets": target_paths},
        )
        return

    with trace_span("test.pytest", attributes={"targets": ",".join(target_paths)}):
        res = run_subprocess(["uv", "run", *test_args], cwd=repo_root, check=False)
        if res.returncode == 0:
            print_success("✓ Test suite passed cleanly.")
        else:
            print_error(f"Test run failed with exit code {res.returncode}.", prefix=False)
            raise typer.Exit(res.returncode)


# =============================================================================
# Command: devops test load
# =============================================================================


@app.command("load")
def load_test_cmd(
    script_path: Annotated[
        Path,
        typer.Argument(help=HELP.test.script_path),
    ] = CONST_CURRENT_DIR / "tests" / "load" / "smoke_test.js",
    vus: Annotated[
        int,
        typer.Option("--vus", "-u", help=HELP.test.vus),
    ] = 10,
    duration: Annotated[
        str,
        typer.Option("--duration", "-d", help=HELP.test.duration),
    ] = "30s",
    summary_export: Annotated[
        Path | None,
        typer.Option("--summary-export", "-s", help=HELP.test.summary_export),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.test.dry_run),
    ] = False,
) -> None:
    """Execute developer-centric load, spike, and latency tests against services using k6."""
    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops test load",
            action="execute_k6_load_test",
            details={
                "script_path": str(script_path),
                "vus": vus,
                "duration": duration,
                "summary_export": str(summary_export) if summary_export else None,
                "simulated_metrics": {
                    "http_reqs": vus * 50,
                    "http_req_duration_p95_ms": 14.2,
                    "http_req_failed_rate": 0.0,
                },
            },
        )
        return

    with trace_span("test.load", attributes={"vus": vus, "duration": duration}):
        has_k6 = shutil.which(BIN_K6) is not None
        if not has_k6:
            print_error(
                ERRORS.test.k6_not_found,
                prefix=False,
            )
            raise typer.Exit(1)

        print_info(
            MESSAGES.test.starting_load_test.format(
                vus=vus, duration=duration, script_path=script_path
            ),
            prefix=False,
        )
        cmd = build_k6_cmd(
            script_path=script_path.resolve(),
            vus=vus,
            duration=duration,
            summary_export=summary_export.resolve() if summary_export else None,
        )
        res = run_subprocess(cmd, check=False)
        if res.returncode == 0:
            print_success(MESSAGES.test.load_test_success.format(duration=duration, vus=vus))
        else:
            print_error(MESSAGES.test.load_test_failed.format(code=res.returncode), prefix=False)
            raise typer.Exit(res.returncode)
