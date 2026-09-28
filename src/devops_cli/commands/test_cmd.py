"""Test suite orchestration, git-diff aware test selector, and load testing."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Annotated

import typer

from devops_cli.config.commands import BIN_K6, build_k6_cmd
from devops_cli.config.constants import CONST_CURRENT_DIR
from devops_cli.config.defaults import DEFAULT_SANDBOX_NETWORK
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import find_worktree_root
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.lang import ERRORS, HELP, MESSAGES
from devops_cli.output import (
    format_duration,
    print_error,
    print_info,
    print_muted,
    print_success,
    print_warning,
    write_stderr,
    write_stdout,
)
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.telemetry.memory_profiler import (
    MemoryProfileReport,
    MemoryProfilerError,
    run_memory_profiler,
)
from devops_cli.telemetry.tracer import record_metric, trace_span

app = new_typer(help=HELP.test.app, no_args_is_help=False)


def find_changed_test_files(repo_root: Path, base_ref: str = "main") -> list[Path]:
    """Find test files corresponding to modified source files via git diff."""
    clean_ref = base_ref.strip()
    if clean_ref.startswith("-") or not re.match(r"^[a-zA-Z0-9_\-./~^]+$", clean_ref):
        clean_ref = "main"

    changed_files: set[str] = set()

    # 1. Diff against base ref (or HEAD~1 if base ref unavailable)
    diff_proc = run_subprocess(
        ["git", "diff", "--name-only", f"{clean_ref}...HEAD"],
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
    repo_root = find_worktree_root()
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


_ALLOWED_NETWORK_MODES: frozenset[str] = frozenset(
    {
        "isolated",
        "sandbox_namespace",
        "public_whitelist",
        "local_whitelist",
        "bridge",
        "none",
    }
)


def _parse_whitelist(raw: str | None, name: str = "public") -> list[str]:
    """Parse comma-separated whitelist tokens without restricting valid URL formats."""
    if not raw:
        return []
    items: list[str] = []
    for token in raw.split(","):
        cleaned = token.strip()
        if not cleaned:
            continue
        if " " in cleaned:
            raise typer.BadParameter(f"Invalid {name} whitelist entry: '{cleaned}'")
        items.append(cleaned)
    return items


def _validate_sandbox_network(
    network_mode: str | None,
    network: str,
    public_whitelist: str | None,
    local_whitelist: str | None,
) -> tuple[str, list[str], list[str]]:
    """Validate network mode and whitelist tokens, warning on bridge mode."""
    mode = (network_mode or network).strip().lower()
    if mode not in _ALLOWED_NETWORK_MODES:
        allowed = ", ".join(sorted(_ALLOWED_NETWORK_MODES))
        raise typer.BadParameter(f"Invalid network mode '{mode}'. Allowed: {allowed}")
    if mode == "bridge":
        print_warning(
            "Security warning: 'bridge' network mode exposes sandbox container to host network. "
            "Prefer 'isolated' mode."
        )
    return (
        mode,
        _parse_whitelist(public_whitelist, "public"),
        _parse_whitelist(local_whitelist, "local"),
    )


@app.command("sandbox")
def test_sandbox(
    command: Annotated[
        list[str],
        typer.Argument(help="Test command to execute inside container sandbox"),
    ],
    image: Annotated[
        str,
        typer.Option("--image", "-i", help="Docker container image to execute command within"),
    ] = "python:3.14-slim",
    workspace: Annotated[
        Path,
        typer.Option("--workspace", "-w", help="Workspace directory to bind mount"),
    ] = Path(CONST_CURRENT_DIR),
    memory: Annotated[
        str,
        typer.Option("--memory", "-m", help="Memory constraint limit (e.g. 2g, 512m)"),
    ] = "2g",
    cpus: Annotated[
        float,
        typer.Option("--cpus", "-c", help="CPU quota limit"),
    ] = 2.0,
    network: Annotated[
        str,
        typer.Option(
            "--network",
            "-n",
            help="Network mode: isolated | sandbox_namespace | public_whitelist | local_whitelist | bridge",
        ),
    ] = DEFAULT_SANDBOX_NETWORK,
    network_mode: Annotated[
        str | None,
        typer.Option(
            "--network-mode",
            help="Multi-tier network mode: isolated | sandbox_namespace | public_whitelist | local_whitelist | bridge",
        ),
    ] = None,
    public_whitelist: Annotated[
        str | None,
        typer.Option(
            "--public-whitelist", help="Comma-separated public domains/IPs allowed for egress"
        ),
    ] = None,
    local_whitelist: Annotated[
        str | None,
        typer.Option("--local-whitelist", help="Comma-separated local URLs/IPs allowed for egress"),
    ] = None,
    read_only: Annotated[
        bool,
        typer.Option("--read-only", help="Mount workspace as read-only"),
    ] = False,
    rootless: Annotated[
        bool,
        typer.Option("--rootless/--root", help="Run container with host user UID/GID"),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.test.dry_run),
    ] = False,
) -> None:
    """Execute test command inside an isolated, disposable Docker container sandbox."""
    from devops_cli.docker.sandbox import WorkloadSandboxConfig, WorkloadSandboxRunner

    effective_mode, pub_list, loc_list = _validate_sandbox_network(
        network_mode=network_mode,
        network=network,
        public_whitelist=public_whitelist,
        local_whitelist=local_whitelist,
    )

    try:
        cfg = WorkloadSandboxConfig(
            workspace_dir=workspace,
            command=command,
            image=image,
            read_only=read_only,
            memory_limit=memory,
            cpu_limit=cpus,
            network_mode=effective_mode,
            public_whitelist=pub_list,
            local_whitelist=loc_list,
            rootless=rootless,
        )
    except ValueError as err:
        raise typer.BadParameter(str(err)) from err
    sandbox_runner = WorkloadSandboxRunner(cfg)

    if dry_run or is_dry_run():
        render_dry_run_result(
            command=f"devops test sandbox {' '.join(command)}",
            action="docker_workload_sandbox",
            details=sandbox_runner.build_dry_run_details(),
        )
        return

    print_info(f"Running command in sandbox ({mask_secrets(image)}, network={cfg.network_mode})...")
    res = sandbox_runner.run()
    if res.stdout:
        write_stdout(mask_secrets(res.stdout))
    if res.stderr:
        write_stderr(mask_secrets(res.stderr))

    if res.exit_code != 0:
        raise typer.Exit(res.exit_code)
    print_success(f"✓ Sandbox workload completed in {format_duration(res.duration_seconds)}")


def _render_memory_report(report: MemoryProfileReport) -> None:
    """Render memory profile summary and top allocation table using output subsystem."""
    from devops_cli.output import print_key_values, print_table

    status_str = "[green]PASSED[/green]" if report.passed else "[red]FAILED[/red]"
    leak_str = (
        f"[red]{report.socket_leak_count}[/red]"
        if report.socket_leak_count > 0
        else "[green]0[/green]"
    )
    summary_items = [
        ("Target", str(report.target)),
        ("Duration", f"{report.duration_seconds:.3f}s"),
        ("Current Heap", f"{report.current_kb:.2f} KB"),
        ("Peak Heap", f"{report.peak_kb:.2f} KB ({report.peak_kb / 1024.0:.2f} MB)"),
        ("Max Peak Threshold", f"{report.max_peak_mb:.2f} MB"),
        ("Net Delta", f"{report.total_allocated_kb:.2f} KB"),
        ("Sockets (Init/Final)", f"{report.initial_sockets} / {report.final_sockets}"),
        ("Socket Leak Count", leak_str),
        ("Overall Result", status_str),
    ]

    print_key_values(f"Memory Profiling Report: {report.target}", summary_items)

    for warn in report.warnings:
        print_error(f"Warning: {warn}", prefix=False)

    if report.top_allocations:
        columns = ["Rank", "Source Location", "Size", "Count"]
        rows = [
            [
                str(idx),
                f"{item.filename}:{item.line_number}",
                item.size_human,
                str(item.count),
            ]
            for idx, item in enumerate(report.top_allocations, start=1)
        ]
        print_table(columns=columns, rows=rows, title="Top Memory Allocations")


@app.command("profile-memory")
def test_profile_memory(
    target: Annotated[
        str,
        typer.Argument(help=HELP.test.profile_target),
    ] = "http-pool",
    iterations: Annotated[
        int,
        typer.Option("--iterations", "-i", help=HELP.test.profile_iterations),
    ] = 10,
    top: Annotated[
        int,
        typer.Option("--top", "-t", help=HELP.test.profile_top),
    ] = 10,
    max_peak_mb: Annotated[
        float,
        typer.Option("--max-peak-mb", help=HELP.test.profile_max_peak_mb),
    ] = 50.0,
    fail_on_leak: Annotated[
        bool,
        typer.Option("--fail-on-leak/--ignore-leak", help=HELP.test.profile_fail_on_leak),
    ] = True,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help=HELP.test.profile_output),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.test.json),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.test.dry_run),
    ] = False,
) -> None:
    """Deterministic async memory and connection pool profiler using tracemalloc."""
    if dry_run or is_dry_run():
        render_dry_run_result(
            command=f"devops test profile-memory {target}",
            action="profile_async_memory",
            details={
                "target": target,
                "iterations": iterations,
                "top": top,
                "max_peak_mb": max_peak_mb,
                "fail_on_leak": fail_on_leak,
                "output": str(output) if output else None,
            },
        )
        return

    with trace_span("test.profile_memory", attributes={"target": target, "iterations": iterations}):
        try:
            report = run_memory_profiler(
                target=target,
                iterations=iterations,
                top_n=top,
                max_peak_mb=max_peak_mb,
            )
        except (MemoryProfilerError, ValueError) as exc:
            print_error(str(exc)[:256], prefix=False)
            raise typer.Exit(1) from exc

        record_metric("test.profile_memory.invocations", 1.0, attributes={"target": target})
        record_metric(
            "test.profile_memory.duration_seconds",
            report.duration_seconds,
            unit="s",
            attributes={"target": target},
        )
        record_metric(
            "test.profile_memory.peak_kb",
            report.peak_kb,
            unit="By",
            attributes={"target": target},
        )

        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
            if not json_output:
                print_success(f"Report written to {output}")

        if json_output:
            print(report.model_dump_json(indent=2))
        else:
            _render_memory_report(report)

        peak_mb = report.peak_kb / 1024.0
        if peak_mb > report.max_peak_mb:
            raise typer.Exit(1)

        if report.socket_leak_count > 0 and fail_on_leak:
            raise typer.Exit(1)
