"""Project testing, validation, and code quality checks with async concurrent execution."""

from __future__ import annotations

import asyncio
import importlib
import os
import re
import shlex
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any

import click
import typer
from pydantic import BaseModel, ConfigDict
from typer.core import TyperGroup

from devops_cli.config.constants import (
    CONST_CI_SLOWEST_TESTS_SHOWN,
    CONST_CI_SUBCOMMAND_SHOWS_HELP_META_KEY,
    CONST_CI_TEST_BUDGET_SECONDS,
)
from devops_cli.config.defaults import (
    DEFAULT_BANDIT_SEVERITY,
    DEFAULT_PYTEST_NUMPROCESSES,
    DEFAULT_PYTHON_VERSION,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run, render_dry_run_result, set_dry_run
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, print_info, print_success


def _asks_for_help(ctx: Any, args: list[str]) -> bool:
    """Whether a subcommand's arguments ask for its help, which Click prints without running it.

    Arguments after `--` are positional, so a path spelled like a help option does not count.
    """
    options = args[: args.index("--")] if "--" in args else args
    return not set(options).isdisjoint(ctx.help_option_names)


class FileOrSubcommandGroup(TyperGroup):
    """Custom TyperGroup routing non-subcommand arguments to group callback as files."""

    def resolve_command(self, ctx: Any, args: list[str]) -> tuple[str | None, Any, list[str]]:
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            if self.invoke_without_command:
                return None, None, args
            raise

    def invoke(self, ctx: Any) -> Any:
        if not ctx._protected_args:
            return super().invoke(ctx)
        cmd_name = ctx._protected_args[0]
        cmd = self.get_command(ctx, cmd_name)
        if cmd is None:
            ctx.args = [*ctx._protected_args, *ctx.args]
            ctx._protected_args = []
            with ctx:
                if self.callback is not None:
                    return ctx.invoke(self.callback, **ctx.params)
                return None
        ctx.meta[CONST_CI_SUBCOMMAND_SHOWS_HELP_META_KEY] = _asks_for_help(ctx, ctx.args)
        return super().invoke(ctx)


_LAZY_OBJECT_MAPPING: dict[str, tuple[str, str]] = {
    "run_subprocess": ("devops_cli.core.process", "run_subprocess"),
    "run_subprocess_async": ("devops_cli.core.process", "run_subprocess_async"),
    "record_metric": ("devops_cli.telemetry", "record_metric"),
    "trace_span": ("devops_cli.telemetry", "trace_span"),
    "print_error": ("devops_cli.output", "print_error"),
    "print_muted": ("devops_cli.output", "print_muted"),
    "print_warning": ("devops_cli.output", "print_warning"),
    "print_section": ("devops_cli.output", "print_section"),
    "print_table": ("devops_cli.output", "print_table"),
    "write_stderr": ("devops_cli.output", "write_stderr"),
    "write_stdout": ("devops_cli.output", "write_stdout"),
    "is_dry_run": ("devops_cli.dry_run", "is_dry_run"),
    "render_dry_run_result": ("devops_cli.dry_run", "render_dry_run_result"),
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


app = new_typer(cls=FileOrSubcommandGroup, help=HELP.ci.app)


def _get_project_root() -> Path:
    """The worktree the CI checks verify: the nearest linked worktree, else the workspace root.

    It is resolved on every call, from the current directory, so a long-lived process that
    imported this module elsewhere (the in-process MCP server) still checks the right tree.
    """
    from devops_cli.core.repo import find_worktree_root

    return find_worktree_root()


def _announce_gate_root(root: Path) -> None:
    """Name the tree the gate checks, warning when it is a worktree git no longer knows."""
    from devops_cli.core.repo import is_stale_linked_worktree

    _get("print_info")(MESSAGES.ci.gate_root.format(root=root), safe=True)
    if is_stale_linked_worktree(root):
        stale = MESSAGES.ci.gate_root_stale.format(root=root, root_arg=shlex.quote(str(root)))
        _get("print_warning")(stale, safe=True)
    from devops_cli.ci import diagnostics

    if fstype := diagnostics.slow_mount_fstype(root):
        slow = MESSAGES.ci.gate_root_slow_mount.format(root=root, fstype=fstype)
        _get("print_warning")(slow, safe=True)


class CheckResult(BaseModel):
    """Immutable result record for a single CI pipeline check."""

    model_config = ConfigDict(frozen=True)

    name: str
    display_title: str
    passed: bool
    duration_seconds: float
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    timeout_seconds: float | None = None


class CheckSpec(BaseModel):
    """Specification defining an individual CI quality gate check."""

    model_config = ConfigDict(frozen=True)

    name: str
    display_title: str
    cmd: list[str]
    span_name: str
    metric_step: str
    fix_cmd: list[str] | None = None


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
    root = _get_project_root()
    full_cmd = list(cmd)
    if full_cmd and full_cmd[0] == "uv" and "--preview-features" not in full_cmd:
        full_cmd[1:1] = ["--preview-features", "malware-check,check-command"]
    result = _get("run_subprocess")(
        full_cmd, cwd=root, timeout=timeout, capture_output=capture_output
    )
    return bool(result.returncode == 0)


def _section(title: str) -> None:
    _get("print_section")(f" {title} ", style="cyan")


def _is_active_coverage_worker(path: Path) -> bool:
    """Check if a .coverage worker file belongs to an active running process."""
    match = re.search(r"[._]pid(\d+)[._]", path.name)
    if not match:
        return False
    try:
        os.kill(int(match.group(1)), 0)
        return True
    except OSError:
        return False


def _is_recent_coverage_file(path: Path, threshold_seconds: float = 60.0) -> bool:
    """Check if a coverage file was written recently and may be in active use."""
    try:
        return (time.time() - path.stat().st_mtime) < threshold_seconds
    except OSError:
        return False


def _unlink_coverage_path(path: Path, *, force: bool) -> None:
    """Unlink a coverage file if not protected by active process ownership."""
    if not force and (_is_active_coverage_worker(path) or _is_recent_coverage_file(path)):
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _clean_coverage_artifacts(*, force: bool = False) -> None:
    """Clean up residual temporary .coverage.* worker files from the checked tree and .data/."""
    if not force and os.getenv("PYTEST_CURRENT_TEST"):
        return

    current_root = _get_project_root()
    if os.getenv("PYTEST_CURRENT_TEST"):
        workspace_root = Path(__file__).resolve().parent.parent.parent.parent
        if current_root.resolve() == workspace_root.resolve():
            return

    for target_dir in (current_root, current_root / ".data"):
        if target_dir.exists():
            for path in target_dir.glob(".coverage*"):
                _unlink_coverage_path(path, force=force)
    root_coverage_xml = current_root / "coverage.xml"
    if root_coverage_xml.exists():
        try:
            root_coverage_xml.unlink(missing_ok=True)
        except OSError:
            pass


def _format_process_output(raw: str | bytes | None) -> str:
    """Safely decode raw subprocess output to string."""
    if not raw:
        return ""
    if isinstance(raw, str):
        return raw
    return raw.decode("utf-8", errors="replace")


def _format_check_badge(passed: bool) -> str:
    """Format rich terminal badge for check status."""
    return "[green]✓ pass[/green]" if passed else "[bold red]✗ fail[/bold red]"


async def _execute_check_async(
    spec: CheckSpec | str,
    display_title: str | None = None,
    cmd: list[str] | None = None,
    span_name: str | None = None,
    metric_step: str | None = None,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    capture_output: bool = True,
    apply_fix: bool = False,
) -> CheckResult:
    """Execute an individual CI verification step asynchronously and record telemetry."""
    if isinstance(spec, str):
        check_spec = CheckSpec(
            name=spec,
            display_title=display_title or spec,
            cmd=cmd or [],
            span_name=span_name or f"ci.step.{spec}",
            metric_step=metric_step or spec,
        )
    else:
        check_spec = spec

    start_time = time.perf_counter()
    root = _get_project_root()

    if apply_fix and check_spec.fix_cmd and check_spec.name == "docs":
        fix_cmd = list(check_spec.fix_cmd)
        if fix_cmd and fix_cmd[0] == "uv" and "--preview-features" not in fix_cmd:
            fix_cmd[1:1] = ["--preview-features", "malware-check,check-command"]
        await _get("run_subprocess_async")(
            fix_cmd, cwd=root, timeout=timeout, capture_output=capture_output
        )

    full_cmd = list(check_spec.cmd)
    if full_cmd and full_cmd[0] == "uv" and "--preview-features" not in full_cmd:
        full_cmd[1:1] = ["--preview-features", "malware-check,check-command"]

    with _get("trace_span")(check_spec.span_name):
        try:
            proc = await _get("run_subprocess_async")(
                full_cmd,
                cwd=root,
                timeout=timeout,
                capture_output=capture_output,
            )
            passed = proc.returncode == 0
            dur = time.perf_counter() - start_time
            _get("record_metric")(
                "ci.step_pass", 1.0 if passed else 0.0, attributes={"step": check_spec.metric_step}
            )
            from devops_cli.output import format_duration

            badge = _format_check_badge(passed)
            _get("print_muted")(
                f"  {badge} [{check_spec.name}] {check_spec.display_title} ({format_duration(dur)})"
            )
            sys.stdout.flush()
            return CheckResult(
                name=check_spec.name,
                display_title=check_spec.display_title,
                passed=passed,
                duration_seconds=dur,
                stdout=_format_process_output(getattr(proc, "stdout", "")),
                stderr=_format_process_output(getattr(proc, "stderr", "")),
            )
        except subprocess.TimeoutExpired as exc:
            dur = time.perf_counter() - start_time
            _get("record_metric")("ci.step_pass", 0.0, attributes={"step": check_spec.metric_step})
            badge = _format_check_badge(False)
            timeout_val = exc.timeout or timeout
            timeout_str = f"{timeout_val:g}s"
            _get("print_muted")(
                f"  {badge} [{check_spec.name}] {check_spec.display_title} (timed out after {timeout_str})"
            )
            sys.stdout.flush()
            return CheckResult(
                name=check_spec.name,
                display_title=check_spec.display_title,
                passed=False,
                duration_seconds=dur,
                stdout="",
                stderr=f"Check '{check_spec.name}' timed out after {timeout_str}.",
                timed_out=True,
                timeout_seconds=float(timeout_val),
            )


# =============================================================================
# Pipeline Execution
# =============================================================================


def _resolve_pytest_worker_count() -> int:
    """Dynamically determine optimal Pytest xdist worker count based on available CPU cores."""
    cpu_count = os.cpu_count() or 4
    return max(1, min(cpu_count, 8))


def _resolve_pytest_cmd() -> list[str]:
    """Construct check command line arguments for the pytest and coverage row."""
    return [
        "uv",
        "run",
        "pytest",
        "-n",
        "auto",
        f"--maxprocesses={_resolve_pytest_worker_count()}",
        f"--durations={CONST_CI_SLOWEST_TESTS_SHOWN}",
        "--cov=src",
        "--cov-report=term-missing",
        "--cov-report=xml",
    ]


def get_check_specs() -> list[CheckSpec]:
    """Return the single ordered table of CI quality gate check specifications."""
    return [
        CheckSpec(
            name="test",
            display_title=MESSAGES.ci.pytest_coverage,
            cmd=_resolve_pytest_cmd(),
            span_name="ci.step.test_and_coverage",
            metric_step="test",
        ),
        CheckSpec(
            name="lint",
            display_title=MESSAGES.ci.ruff_check,
            cmd=["uv", "run", "ruff", "check", "."],
            span_name="ci.step.lint",
            metric_step="lint",
            fix_cmd=["uv", "run", "ruff", "check", "--fix", "."],
        ),
        CheckSpec(
            name="format",
            display_title=MESSAGES.ci.ruff_format,
            cmd=["uv", "run", "ruff", "format", "--check", "."],
            span_name="ci.step.format",
            metric_step="format",
            fix_cmd=["uv", "run", "ruff", "format", "."],
        ),
        CheckSpec(
            name="typecheck",
            display_title=f"mypy (py{DEFAULT_PYTHON_VERSION.replace('.', '')} strict)",
            cmd=[
                "uv",
                "run",
                "mypy",
                "--python-version",
                DEFAULT_PYTHON_VERSION,
                "--strict",
                "src",
            ],
            span_name="ci.step.typecheck",
            metric_step="typecheck",
        ),
        CheckSpec(
            name="audit",
            display_title=MESSAGES.ci.uv_audit,
            cmd=["uv", "audit"],
            span_name="ci.step.audit",
            metric_step="audit",
        ),
        CheckSpec(
            name="security",
            display_title=MESSAGES.ci.bandit_scan,
            cmd=["uv", "run", "bandit", "-r", "src", "-ll"],
            span_name="ci.step.security",
            metric_step="security",
        ),
        CheckSpec(
            name="actionlint",
            display_title=MESSAGES.ci.actionlint,
            cmd=["uv", "run", "actionlint"],
            span_name="ci.step.actionlint",
            metric_step="actionlint",
        ),
        CheckSpec(
            name="docs",
            display_title=MESSAGES.ci.docs_validation,
            cmd=["uv", "run", "devops", "docs", "check"],
            span_name="ci.step.docs",
            metric_step="docs",
            fix_cmd=["uv", "run", "devops", "docs", "generate", "--sync-readme"],
        ),
        CheckSpec(
            name="uv-check",
            display_title=MESSAGES.ci.uv_check,
            cmd=["uv", "check"],
            span_name="ci.step.uv-check",
            metric_step="uv-check",
        ),
        CheckSpec(
            name="lockfile",
            display_title=MESSAGES.ci.uv_lock,
            cmd=["uv", "lock", "--check"],
            span_name="ci.step.lockfile",
            metric_step="lockfile",
        ),
        CheckSpec(
            name="outdated",
            display_title=MESSAGES.ci.uv_outdated,
            cmd=["uv", "tree", "--outdated", "--depth=1"],
            span_name="ci.step.outdated",
            metric_step="outdated",
        ),
        CheckSpec(
            name="devcontainer",
            display_title=MESSAGES.ci.devcontainer_validation,
            cmd=["uv", "run", "devops", "devcontainer", "validate", "--workspace", "."],
            span_name="ci.step.devcontainer",
            metric_step="devcontainer",
        ),
    ]


def get_check_spec(name: str) -> CheckSpec:
    """Retrieve a single check specification by its canonical row name."""
    for spec in get_check_specs():
        if spec.name == name:
            return spec
    raise KeyError(f"Unknown check spec: {name}")


def _parse_check_names(values: Sequence[str] | None) -> list[str]:
    """Parse comma-separated or repeated check name arguments into a list of names."""
    if not values:
        return []
    names: list[str] = []
    for item in values:
        for part in item.split(","):
            cleaned = part.strip()
            if cleaned:
                names.append(cleaned)
    return names


def resolve_selected_specs(
    only: Sequence[str] | None = None,
    skip: Sequence[str] | None = None,
) -> list[CheckSpec]:
    """Filter check specifications using --only or --skip selection."""
    all_specs = get_check_specs()
    valid_names = [s.name for s in all_specs]

    only_names = _parse_check_names(only)
    skip_names = _parse_check_names(skip)

    if only_names and skip_names:
        valid_list = ", ".join(valid_names)
        _get("write_stderr")(
            f"Cannot combine --only and --skip options. Valid check names: {valid_list}\n"
        )
        raise typer.Exit(2)

    if only_names:
        invalid = [n for n in only_names if n not in valid_names]
        if invalid:
            valid_list = ", ".join(valid_names)
            invalid_list = ", ".join(repr(n) for n in invalid)
            _get("write_stderr")(
                f"Invalid check name(s): {invalid_list}. Valid check names: {valid_list}\n"
            )
            raise typer.Exit(2)
        return [s for s in all_specs if s.name in only_names]

    if skip_names:
        invalid = [n for n in skip_names if n not in valid_names]
        if invalid:
            valid_list = ", ".join(valid_names)
            invalid_list = ", ".join(repr(n) for n in invalid)
            _get("write_stderr")(
                f"Invalid check name(s): {invalid_list}. Valid check names: {valid_list}\n"
            )
            raise typer.Exit(2)
        return [s for s in all_specs if s.name not in skip_names]

    return all_specs


def _find_args_after_devops_ci(tokens: list[str]) -> list[str] | None:
    """Return command line arguments following 'devops ci' if present."""
    for i in range(len(tokens) - 1):
        if tokens[i] == "devops" and tokens[i + 1] == "ci":
            return tokens[i + 2 :]
    return None


def _resolve_subcommand_row(subcmd: str, spec_names: set[str]) -> list[str]:
    """Map a single subcommand to its corresponding check row name."""
    if subcmd == "coverage":
        return ["test"]
    if subcmd in spec_names:
        return [subcmd]
    return []


def _parse_flag_values(tokens: list[str], flag: str) -> list[str]:
    """Extract argument values for --<flag>=val or --<flag> val from tokens."""
    prefix = f"--{flag}="
    flag_arg = f"--{flag}"
    vals: list[str] = []
    for i, tok in enumerate(tokens):
        if tok.startswith(prefix):
            vals.append(tok[len(prefix) :])
        elif tok == flag_arg and i + 1 < len(tokens):
            vals.append(tokens[i + 1])
    return vals


def resolve_step_rows(command_line: str) -> list[str]:
    """Resolve check table row names reached by a given workflow or CLI command line."""
    tokens = shlex.split(command_line.strip())
    rest = _find_args_after_devops_ci(tokens)
    if rest is None:
        return []

    spec_names = {s.name for s in get_check_specs()}
    if rest and not rest[0].startswith("-"):
        return _resolve_subcommand_row(rest[0], spec_names)

    only_vals = _parse_flag_values(rest, "only")
    skip_vals = _parse_flag_values(rest, "skip")
    selected = resolve_selected_specs(
        only=only_vals if only_vals else None,
        skip=skip_vals if skip_vals else None,
    )
    return [s.name for s in selected]


def _run_python_version_step() -> tuple[bool, CheckResult]:
    """Execute python runtime version verification."""
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
    from devops_cli.output import format_duration

    py_badge = "[green]✓ pass[/green]" if py_ok else "[bold red]✗ fail[/bold red]"
    _get("print_muted")(
        f"  {py_badge} [python_version] {py_result.display_title} ({format_duration(py_dur)})"
    )
    sys.stdout.flush()
    return py_ok, py_result


async def _run_pre_fixes_async(
    selected_specs: Sequence[CheckSpec],
    *,
    format_fix: bool,
    lint_fix: bool,
) -> None:
    """Apply in-place modifications first before verification scans."""
    if format_fix:
        fmt_spec = next((s for s in selected_specs if s.name == "format"), None)
        if fmt_spec and fmt_spec.fix_cmd:
            await _execute_check_async(
                CheckSpec(
                    name="format_fix",
                    display_title=MESSAGES.ci.ruff_format,
                    cmd=fmt_spec.fix_cmd,
                    span_name="ci.step.format_fix",
                    metric_step="format_fix",
                )
            )
    if lint_fix:
        lint_spec = next((s for s in selected_specs if s.name == "lint"), None)
        if lint_spec and lint_spec.fix_cmd:
            await _execute_check_async(
                CheckSpec(
                    name="lint_fix",
                    display_title=MESSAGES.ci.ruff_check,
                    cmd=lint_spec.fix_cmd,
                    span_name="ci.step.lint_fix",
                    metric_step="lint_fix",
                )
            )


def _assemble_ci_results(
    py_result: CheckResult,
    selected_specs: Sequence[CheckSpec],
    raw_results: Sequence[CheckResult],
) -> list[CheckResult]:
    """Assemble final results including virtual coverage gate if test check was executed."""
    test_idx = next((i for i, s in enumerate(selected_specs) if s.name == "test"), None)
    if test_idx is None:
        return [py_result, *raw_results]

    test_result = raw_results[test_idx]
    coverage_result = CheckResult(
        name="coverage",
        display_title=MESSAGES.ci.pytest_coverage,
        passed=test_result.passed,
        duration_seconds=test_result.duration_seconds,
        stdout=test_result.stdout,
        stderr=test_result.stderr,
    )
    assembled: list[CheckResult] = [py_result]
    for i, res in enumerate(raw_results):
        assembled.append(res)
        if i == test_idx:
            assembled.append(coverage_result)
    return assembled


async def _run_all_checks_async(
    *,
    lint_fix: bool = False,
    format_fix: bool = False,
    docs_fix: bool = False,
    specs: Sequence[CheckSpec] | None = None,
) -> list[CheckResult]:
    """Execute CI verification gates concurrently using asyncio."""
    _clean_coverage_artifacts()

    py_ok, py_result = _run_python_version_step()
    if not py_ok:
        return [py_result]

    selected_specs = list(specs) if specs is not None else get_check_specs()
    if not selected_specs:
        return [py_result]

    await _run_pre_fixes_async(selected_specs, format_fix=format_fix, lint_fix=lint_fix)

    has_test = any(s.name == "test" for s in selected_specs)
    if has_test:
        _get("print_muted")(f"  ⏳ [test] {MESSAGES.ci.pytest_coverage} running in background...")
        sys.stdout.flush()

    capture_output = len(selected_specs) != 1

    with _get("trace_span")(
        "ci.run_pipeline",
        attributes={"lint_fix": lint_fix, "format_fix": format_fix, "docs_fix": docs_fix},
    ):
        _clean_coverage_artifacts()
        tasks = [
            _execute_check_async(
                spec=spec,
                capture_output=capture_output,
                apply_fix=(docs_fix if spec.name == "docs" else False),
            )
            for spec in selected_specs
        ]

        raw_results = await asyncio.gather(*tasks)
        _clean_coverage_artifacts()
        return _assemble_ci_results(py_result, selected_specs, raw_results)


def _run_all_checks(
    *, lint_fix: bool = True, format_fix: bool = True, docs_fix: bool = False
) -> list[tuple[str, bool]]:
    """Synchronous entrypoint for executing CI pipeline."""
    results = asyncio.run(
        _run_all_checks_async(lint_fix=lint_fix, format_fix=format_fix, docs_fix=docs_fix)
    )
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


def _print_summary(
    results: list[CheckResult], total_elapsed: float, *, cached: bool = False
) -> None:
    """Render the final formatted CI Summary table."""
    from devops_cli.output import format_duration

    rows: list[list[str]] = []
    for res in results:
        if res.timed_out:
            limit_str = f"{res.timeout_seconds:g}s" if res.timeout_seconds else "limit"
            status_text = f"[red]✗ fail (timed out after {limit_str})[/red]"
        elif cached and res.passed:
            status_text = "[green]✓ pass (cached)[/green]"
        elif res.passed:
            status_text = "[green]✓ pass[/green]"
        else:
            status_text = "[red]✗ fail[/red]"
        dur_text = format_duration(res.duration_seconds) if res.duration_seconds > 0 else "<0.01s"
        rows.append([res.name, status_text, dur_text])

    _get("print_table")(
        title=MESSAGES.ci.ci_summary_title,
        columns=[(MESSAGES.ci.col_check, "cyan"), MESSAGES.ci.col_result, ("Duration", "dim")],
        rows=rows,
    )
    mode_text = "cached execution" if cached else "concurrent async execution"
    _get("print_muted")(f"Total Elapsed: {format_duration(total_elapsed)} ({mode_text})\n")


def _collect_ci_target_files(
    opt_files: list[str] | None,
    extra_args: list[str] | None,
) -> list[str] | None:
    """Combine explicit --files options and positional arguments into a clean sorted list."""
    combined = list(opt_files or [])
    if extra_args:
        combined.extend(a for a in extra_args if not a.startswith("-"))
    clean = sorted({f.strip() for f in combined if f.strip()})
    return clean if clean else None


def _try_get_ci_cache(
    root: Path,
    files: list[str] | None,
    ci_options: dict[str, Any],
) -> list[CheckResult] | None:
    """Attempt fast retrieval of passing CI cache entry."""
    from devops_cli.ci.cache import compute_workspace_fingerprint, get_ci_cache

    fp_info = compute_workspace_fingerprint(root=root, options=ci_options)
    if not fp_info:
        return None
    fingerprint, _, _ = fp_info
    entry = get_ci_cache(fingerprint=fingerprint, files=files, options=ci_options, root=root)
    if entry is None:
        return None
    return [
        CheckResult(
            name=c.name,
            display_title=c.display_title,
            passed=c.passed,
            duration_seconds=c.duration_seconds,
            stdout=c.stdout,
            stderr=c.stderr,
        )
        for c in entry.checks
    ]


def _try_save_ci_cache(
    root: Path,
    results: list[CheckResult],
    files: list[str] | None,
    ci_options: dict[str, Any],
) -> None:
    """Persist successful CI run into cache."""
    from devops_cli.ci.cache import (
        CICachedCheck,
        compute_workspace_fingerprint,
        save_ci_cache,
    )

    fp_info = compute_workspace_fingerprint(root=root, options=ci_options)
    if not fp_info:
        return
    fingerprint, head_sha, file_hashes = fp_info
    cached_checks = [
        CICachedCheck(
            name=res.name,
            display_title=res.display_title,
            passed=res.passed,
            duration_seconds=res.duration_seconds,
            stdout=res.stdout,
            stderr=res.stderr,
        )
        for res in results
    ]
    save_ci_cache(
        fingerprint=fingerprint,
        head_sha=head_sha,
        checks=cached_checks,
        file_hashes=file_hashes,
        options=ci_options,
        passed=True,
        root=root,
    )


def _try_fast_cached_ci(
    root: Path,
    files: list[str] | None,
    ci_options: dict[str, Any],
    *,
    cache: bool,
    force: bool,
) -> bool:
    """Attempt fast cached CI execution, rendering summary and returning True on hit."""
    if not cache or force or is_dry_run():
        return False
    cached_results = _try_get_ci_cache(root, files, ci_options)
    if cached_results is None:
        return False
    _get("print_info")(MESSAGES.ci.cache_hit)
    _print_summary(cached_results, total_elapsed=0.005, cached=True)
    return True


def _warn_when_over_budget(results: list[CheckResult]) -> None:
    """Warn when the test step ran past its budget, naming the tests that took longest."""
    test_result = next((res for res in results if res.name == "test"), None)
    if test_result is None or test_result.duration_seconds <= CONST_CI_TEST_BUDGET_SECONDS:
        return
    from devops_cli.ci.diagnostics import slowest_tests
    from devops_cli.output import format_duration

    _get("print_warning")(
        MESSAGES.ci.test_budget_exceeded.format(
            duration=format_duration(test_result.duration_seconds),
            budget=format_duration(CONST_CI_TEST_BUDGET_SECONDS),
        ),
        safe=True,
    )
    if test_result.stdout:
        for entry in slowest_tests(test_result.stdout):
            _get("print_muted")(f"  {entry}")


def _handle_ci_results(
    results: list[CheckResult],
    root: Path,
    all_files: list[str] | None,
    ci_options: dict[str, Any],
    *,
    save_cache: bool = True,
) -> None:
    """Handle post-execution caching or failure exit.

    A passing run is recorded whatever `--cache` said. That flag decides whether an
    existing entry may be *trusted*, not whether a fresh result is worth keeping: a
    `--no-cache` run has done the full work and proved the tree, so discarding the proof
    made the next ordinary run repeat it for no reason.
    """
    if all(res.passed for res in results):
        if save_cache and not is_dry_run():
            _try_save_ci_cache(root, results, all_files, ci_options)
        return

    from devops_cli.ci.cache import clear_ci_cache

    clear_ci_cache(root)
    raise typer.Exit(1)


@app.callback(invoke_without_command=True)
def all_checks(
    ctx: typer.Context,
    fix: Annotated[
        bool,
        typer.Option("--fix/--no-fix", help=HELP.ci.fix_all),
    ] = True,
    check: Annotated[
        bool,
        typer.Option("--check", help=HELP.ci.check_all),
    ] = False,
    cache: Annotated[
        bool,
        typer.Option("--cache/--no-cache", help=HELP.ci.cache),
    ] = True,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help=HELP.ci.force),
    ] = False,
    only: Annotated[
        list[str] | None,
        typer.Option(
            "--only", help="Run only the specified check names (comma-separated or repeated)."
        ),
    ] = None,
    skip: Annotated[
        list[str] | None,
        typer.Option(
            "--skip", help="Skip the specified check names (comma-separated or repeated)."
        ),
    ] = None,
    files: Annotated[
        list[str] | None,
        typer.Option("--files", help=HELP.ci.files),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Run all CI checks concurrently in parallel with non-blocking async execution."""
    root = _get_project_root()
    if not ctx.meta.get(CONST_CI_SUBCOMMAND_SHOWS_HELP_META_KEY):
        _announce_gate_root(root)
    if ctx.invoked_subcommand is not None:
        return
    if dry_run:
        set_dry_run(True)

    selected_specs = resolve_selected_specs(only=only, skip=skip)
    is_narrowed = bool(only or skip)

    effective_fix = fix and not check
    ci_options = {"fix": effective_fix, "check": check}
    all_files = _collect_ci_target_files(files, getattr(ctx, "args", []))

    if not is_narrowed and _try_fast_cached_ci(
        root, all_files, ci_options, cache=cache, force=force
    ):
        return

    start_time = time.perf_counter()
    _get("print_info")("Executing CI quality gates concurrently...")
    sys.stdout.flush()
    results = asyncio.run(
        _run_all_checks_async(
            lint_fix=effective_fix,
            format_fix=effective_fix,
            docs_fix=effective_fix,
            specs=selected_specs,
        )
    )
    _print_failures(results)
    _print_summary(results, total_elapsed=time.perf_counter() - start_time)
    _warn_when_over_budget(results)
    _handle_ci_results(results, root, all_files, ci_options, save_cache=(not is_narrowed))


# =============================================================================
# Individual CI Commands
# =============================================================================


def _report_selection(selection: Any) -> None:
    """Explain which tests were chosen for the supplied files, and which were not."""
    for source, tests in sorted(selection.mapped_sources.items()):
        _get("print_muted")(f"  {source} → {', '.join(tests)}")
    if selection.unmapped_sources:
        _get("print_warning")(
            MESSAGES.ci.no_covering_tests.format(files=", ".join(selection.unmapped_sources))
        )


def _resolve_test_targets(paths: list[Path], fallback: bool) -> list[str] | None:
    """Map changed files onto pytest targets.

    Returns the targets to run, or ``None`` when the caller should run the whole suite.
    Selection never yields an empty run for changed sources: an unmappable source either
    escalates to the full suite or is reported, so a narrowed run can't report a false
    green for code nothing covered.
    """
    from devops_cli.core.test_selection import select_tests_for_sources

    selection = select_tests_for_sources(paths, _get_project_root())
    _report_selection(selection)

    if selection.has_selection:
        return selection.pytest_targets()

    if not selection.unmapped_sources:
        # Only non-source files were supplied (docs, manifests); nothing to verify.
        _get("print_muted")(MESSAGES.ci.no_testable_files)
        return []

    if fallback:
        _get("print_warning")(MESSAGES.ci.selection_fallback)
        return None

    _get("print_error")(MESSAGES.ci.selection_empty, prefix=False)
    raise typer.Exit(1)


def _build_test_cmd(
    numprocesses: str,
    verbose: bool,
    k: str | None,
    x: bool,
    targets: list[str] | None,
) -> list[str]:
    """Build the pytest command line arguments."""
    cmd = ["uv", "run", "pytest", "-n", numprocesses]
    if verbose:
        cmd.append("-v")
    if k:
        cmd.extend(["-k", k])
    if x:
        cmd.append("-x")
    if targets:
        cmd.extend(targets)
    return cmd


@app.command()
def test(
    paths: Annotated[list[Path] | None, typer.Argument(help=HELP.ci.test_paths)] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help=HELP.options.verbose)] = False,
    k: Annotated[str | None, typer.Option("-k", help=HELP.ci.filter_keyword)] = None,
    x: Annotated[bool, typer.Option("-x", help=HELP.ci.stop_fail)] = False,
    numprocesses: Annotated[
        str, typer.Option("-n", "--numprocesses", help=HELP.ci.num_workers)
    ] = DEFAULT_PYTEST_NUMPROCESSES,
    fallback: Annotated[
        bool, typer.Option("--fallback/--no-fallback", help=HELP.ci.selection_fallback)
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Run the test suite, or only the tests covering the given source files.

    Passing paths narrows the run to the tests that import or conventionally cover them,
    which is what makes this usable as a pre-commit hook on staged files.
    """
    if dry_run:
        set_dry_run(True)
    if not _verify_python_314_environment():
        raise typer.Exit(1)

    targets: list[str] | None = None
    if paths:
        targets = _resolve_test_targets(list(paths), fallback)
        if targets == []:
            return

    if k and k.startswith("-"):
        _get("print_error")("Invalid keyword filter expression.", prefix=False)
        raise typer.Exit(1)

    cmd = _build_test_cmd(numprocesses, verbose, k, x, targets)
    if not _run(cmd):
        raise typer.Exit(1)


@app.command()
def coverage(
    html: Annotated[bool, typer.Option("--html", help=HELP.ci.html_report)] = False,
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
    spec = get_check_spec("test")
    cmd = list(spec.cmd)
    if html:
        cmd.append("--cov-report=html")
    if not _run(cmd):
        raise typer.Exit(1)


@app.command()
def lint(
    fix: Annotated[bool, typer.Option("--fix/--no-fix", help=HELP.ci.auto_fix)] = True,
    check: Annotated[
        bool,
        typer.Option("--check", help=HELP.ci.lint_check),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Run ruff linter across the project, automatically applying fixes by default."""
    if dry_run:
        set_dry_run(True)
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    spec = get_check_spec("lint")
    cmd = spec.fix_cmd if (fix and not check and spec.fix_cmd) else spec.cmd
    if not _run(cmd):
        raise typer.Exit(1)


@app.command(name="format")
def fmt(
    check: Annotated[
        bool,
        typer.Option("--check", help=HELP.ci.format_check),
    ] = False,
    fix: Annotated[bool, typer.Option("--fix/--no-fix", help=HELP.ci.format_fix)] = True,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Format codebase with ruff format (or verify in check-only mode with --check)."""
    if dry_run:
        set_dry_run(True)
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    spec = get_check_spec("format")
    cmd = spec.cmd if (check or not fix) else (spec.fix_cmd or spec.cmd)
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
    spec = get_check_spec("typecheck")
    if not _run(spec.cmd):
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
    spec = get_check_spec("audit")
    if not _run(spec.cmd):
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
    spec = get_check_spec("security")
    if severity.lower() == DEFAULT_BANDIT_SEVERITY.lower():
        cmd = list(spec.cmd)
    else:
        level_flag = (
            "-lll" if severity.lower() == "high" else ("-l" if severity.lower() == "low" else "-ll")
        )
        cmd = ["uv", "run", "bandit", "-r", "src", level_flag]
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
    spec = get_check_spec("actionlint")
    if not _run(spec.cmd):
        raise typer.Exit(1)


@app.command()
def docs(
    fix: Annotated[
        bool,
        typer.Option("--fix", help=HELP.docs.sync_readme),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Verify (or update with --fix) that documentation is up to date with CLI commands and configuration."""
    if dry_run:
        set_dry_run(True)
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    spec = get_check_spec("docs")
    if fix and spec.fix_cmd:
        if not _run(spec.fix_cmd):
            raise typer.Exit(1)
    if not _run(spec.cmd):
        raise typer.Exit(1)


@app.command(name="uv-check")
def uv_check(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Run uv check for fast static type checking and project validation."""
    if dry_run:
        set_dry_run(True)
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    spec = get_check_spec("uv-check")
    if not _run(spec.cmd):
        raise typer.Exit(1)


@app.command()
def lockfile(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Verify lockfile consistency and freshness via uv lock --check."""
    if dry_run:
        set_dry_run(True)
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    spec = get_check_spec("lockfile")
    if not _run(spec.cmd):
        raise typer.Exit(1)


@app.command()
def outdated(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Display outdated dependencies and packages via uv tree --outdated."""
    if dry_run:
        set_dry_run(True)
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    spec = get_check_spec("outdated")
    if not _run(spec.cmd):
        raise typer.Exit(1)


@app.command()
def maintain(
    fix: Annotated[
        bool,
        typer.Option("--fix", help=HELP.ci.fix_sync),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Run automated toolchain, dependency freshness, and lockfile maintenance checks."""
    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops ci maintain",
            action="run_maintenance_checks",
            details={
                "lockfile_status": "VALID",
                "dependency_freshness": "UP_TO_DATE",
                "devcontainer_manifest": "VALID",
            },
        )
        return

    if not _verify_python_314_environment():
        raise typer.Exit(1)

    print_info("Running toolchain and dependency maintenance checks...", prefix=False)

    if fix:
        print_info("Synchronizing dependencies and lockfile with 'uv lock'...", prefix=False)
        if not _run(["uv", "lock"]):
            raise typer.Exit(1)

    # 1. Lockfile consistency check
    if not _run(["uv", "lock", "--check"]):
        print_error(
            "Lockfile is out of sync with pyproject.toml. Run 'uv lock' or 'devops ci maintain --fix'.",
            prefix=False,
        )
        raise typer.Exit(1)

    # 2. Dependency security audit
    if not _run(["uv", "run", "pip-audit"]):
        print_error("Dependency audit found vulnerabilities.", prefix=False)
        raise typer.Exit(1)

    print_success("✓ Toolchain and lockfile maintenance checks passed.")


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
    start_time = time.perf_counter()
    results = asyncio.run(_run_all_checks_async(lint_fix=fix, format_fix=fix, docs_fix=fix))
    _print_failures(results)
    _print_summary(results, total_elapsed=time.perf_counter() - start_time)
    if not all(res.passed for res in results):
        raise typer.Exit(1)
