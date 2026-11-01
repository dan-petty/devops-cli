"""Test suite orchestration, git-diff aware test selector, and load testing."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated

import typer

from devops_cli.config.commands import BIN_K6, build_k6_cmd
from devops_cli.config.constants import (
    CONST_CURRENT_DIR,
    CONST_GIT_MAIN_BRANCH,
    CONST_OUTPUT_FORMAT_TABLE,
    CONST_TESTS_ROOT_DIR,
)
from devops_cli.config.defaults import (
    DEFAULT_SANDBOX_NETWORK,
    DEFAULT_TABLE_FORMAT,
)
from devops_cli.core.cli import new_typer
from devops_cli.core.process import prepare_tool_cmd, run_subprocess
from devops_cli.core.repo import find_worktree_root
from devops_cli.core.test_selection import select_tests_for_sources
from devops_cli.dry_run import is_dry_run
from devops_cli.dry_run.decorator import dry_run_class
from devops_cli.dry_run.requests import PlannedRequest, render_request_plan
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
from devops_cli.output.serialization import emit_serialized, resolve_format
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.telemetry.memory_profiler import (
    MemoryProfileReport,
    MemoryProfilerError,
    run_memory_profiler,
)
from devops_cli.telemetry.tracer import trace_span

app = new_typer(help=HELP.test.app, no_args_is_help=False)


def _porcelain_path(entry: str) -> str:
    """The path a `git status --porcelain=v1 -z --no-renames` entry names; empty if none."""
    if len(entry) < 4:
        return ""
    if entry[2] == " ":
        return entry[3:]
    parts = entry.strip().split(maxsplit=1)
    if len(parts) == 2:
        return parts[1].strip().strip('"')
    return ""


def _changed_paths(repo_root: Path) -> list[str]:
    """The files changed since the branch left `main`, committed or not, as git lists them,
    each file of an untracked directory by its own path, and a rename as its old path deleted
    and its new path added, so a helper renamed away reaches what it reached (#1312)."""
    changed: set[str] = set()
    diff_proc = run_subprocess(
        ["git", "diff", "--name-only", "-z", "--no-renames", f"{CONST_GIT_MAIN_BRANCH}...HEAD"],
        cwd=repo_root,
        check=False,
        local_read=True,
    )
    if diff_proc.returncode == 0 and diff_proc.stdout:
        diff_entries = (
            diff_proc.stdout.split("\0")
            if "\0" in diff_proc.stdout
            else diff_proc.stdout.strip().splitlines()
        )
        changed.update(p for p in diff_entries if p)

    status = ["git", "status", "--porcelain=v1", "-z", "--no-renames", "--untracked-files=all"]
    wt_proc = run_subprocess(status, cwd=repo_root, check=False, local_read=True)
    if wt_proc.returncode == 0 and wt_proc.stdout:
        wt_entries = (
            wt_proc.stdout.split("\0")
            if "\0" in wt_proc.stdout
            else wt_proc.stdout.strip().splitlines()
        )
        changed.update(_porcelain_path(entry) for entry in wt_entries if entry)
    return sorted(path for path in changed if path)


def _changed_targets(repo_root: Path) -> list[str]:
    """The pytest targets that cover what changed, as the shared selector maps it, naming
    each changed source no test module covers; the whole suite when nothing maps."""
    selection = select_tests_for_sources(_changed_paths(repo_root), repo_root)
    for source in selection.unmapped_sources:
        print_warning(MESSAGES.test.unmapped_source.format(source=source))
    targets = [target for target in selection.pytest_targets() if (repo_root / target).exists()]
    if not targets:
        print_info(MESSAGES.test.changed_whole_suite)
        return [CONST_TESTS_ROOT_DIR]
    print_info(MESSAGES.test.changed_targets.format(count=len(targets)))
    for target in targets:
        print_muted(f"  • {target}")
    return targets


# =============================================================================
# Command: devops test run
# =============================================================================


def pytest_argv(
    targets: list[str],
    *,
    verbose: bool = False,
    fail_fast: bool = False,
    filter_expr: str | None = None,
    coverage: bool = False,
) -> list[str]:
    """The command of `devops test run`: `uv run pytest` with its options, then the targets."""
    args = ["uv", "run", "pytest"]
    if verbose:
        args.append("-vv")
    if fail_fast:
        args.append("-x")
    if filter_expr:
        args.extend(["-k", filter_expr])
    if coverage:
        args.extend(["--cov=src", "--cov-report=term-missing"])
    return [*args, *targets]


@app.command("run")
@dry_run_class("request-plan")
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
    target_paths: list[str] = []
    if target:
        target_paths.append(str(target))
    elif changed:
        target_paths.extend(_changed_targets(repo_root))
    else:
        target_paths.append(CONST_TESTS_ROOT_DIR)

    cmd = pytest_argv(
        target_paths,
        verbose=verbose,
        fail_fast=fail_fast,
        filter_expr=filter_expr,
        coverage=coverage,
    )

    if dry_run or is_dry_run():
        request = PlannedRequest(
            method="uv", target="run pytest", argv=tuple(prepare_tool_cmd(cmd))
        )
        render_request_plan(MESSAGES.test.run_dry_run_heading, [request])
        return

    with trace_span("test.pytest", attributes={"targets": ",".join(target_paths)}):
        res = run_subprocess(cmd, cwd=repo_root, check=False)
        if res.returncode == 0:
            print_success("Test suite passed cleanly.")
        else:
            print_error(f"Test run failed with exit code {res.returncode}.", prefix=False)
            raise typer.Exit(res.returncode)


# =============================================================================
# Command: devops test load
# =============================================================================


@app.command("load")
@dry_run_class("request-plan")
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
    cmd = build_k6_cmd(
        script_path=script_path.resolve(),
        vus=vus,
        duration=duration,
        summary_export=summary_export.resolve() if summary_export else None,
    )
    if dry_run or is_dry_run():
        request = PlannedRequest(method=BIN_K6, target=str(script_path.resolve()), argv=tuple(cmd))
        render_request_plan(
            MESSAGES.test.load_dry_run_heading, [request], [MESSAGES.test.load_dry_run_note]
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
@dry_run_class("request-plan")
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
    seccomp_profile: Annotated[
        Path | None,
        typer.Option("--seccomp-profile", help=HELP.sandbox.seccomp_profile),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.test.dry_run),
    ] = False,
) -> None:
    """Execute test command inside an isolated, disposable Docker container sandbox."""
    from devops_cli.docker.sandbox import WorkloadSandboxConfig, WorkloadSandboxRunner
    from devops_cli.sandbox.models import container_sandbox_policy

    policy = container_sandbox_policy(seccomp_profile)

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
            policy=policy,
        )
    except ValueError as err:
        raise typer.BadParameter(str(err)) from err
    sandbox_runner = WorkloadSandboxRunner(cfg)

    if dry_run or is_dry_run():
        from devops_cli.docker.docker_plans import plan_docker_sandbox

        plan = plan_docker_sandbox(
            command=command,
            image=image,
            workspace=sandbox_runner._validate_workspace_dir(),
            network_mode=cfg.network_mode,
            read_only=read_only,
            rootless=rootless,
            declared_controls=sandbox_runner.declared_controls(),
            seccomp_profile=policy.seccomp_profile.path if policy.seccomp_profile else None,
        )
        render_request_plan(MESSAGES.test.sandbox_dry_run_heading, plan)
        return

    print_info(f"Running command in sandbox ({mask_secrets(image)}, network={cfg.network_mode})...")
    res = sandbox_runner.run()
    if res.stdout:
        write_stdout(mask_secrets(res.stdout))
    if res.stderr:
        write_stderr(mask_secrets(res.stderr))

    if res.exit_code != 0:
        raise typer.Exit(res.exit_code)
    print_success(f"Sandbox workload completed in {format_duration(res.duration_seconds)}")


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
@dry_run_class("no-external-request")
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
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
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
        messages = MESSAGES.test
        leak_rule = (
            messages.profile_memory_fail_on_leak
            if fail_on_leak
            else messages.profile_memory_ignore_leak
        )
        print_info(
            messages.profile_memory_dry_run.format(
                target=target,
                iterations=iterations,
                max_peak_mb=max_peak_mb,
                leak_rule=leak_rule,
                output=output or messages.profile_memory_no_report,
            ),
            prefix=False,
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

        resolved = resolve_format(output_format, json_output=json_output)
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
            if resolved == CONST_OUTPUT_FORMAT_TABLE:
                print_success(f"Report written to {output}")

        if resolved != CONST_OUTPUT_FORMAT_TABLE:
            emit_serialized(report.model_dump(), resolved)
        else:
            _render_memory_report(report)

        peak_mb = report.peak_kb / 1024.0
        if peak_mb > report.max_peak_mb:
            raise typer.Exit(1)

        if report.socket_leak_count > 0 and fail_on_leak:
            raise typer.Exit(1)
