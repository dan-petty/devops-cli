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
    DEFAULT_CI_TEST_REPEAT_RUNS,
    DEFAULT_PYTHON_VERSION,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run, render_dry_run_result, set_dry_run
from devops_cli.dry_run.requests import PlannedRequest, render_request_plan
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, print_info, print_success


def _asks_for_help(ctx: Any, args: list[str]) -> bool:
    """Whether a subcommand's arguments ask for its help, which Click prints without running it.

    Arguments after `--` are positional, so a path spelled like a help option does not count.
    """
    options = args[: args.index("--")] if "--" in args else args
    return not set(options).isdisjoint(ctx.help_option_names)


class FileOrSubcommandGroup(TyperGroup):
    """Custom TyperGroup tracking help requests on subcommands."""

    def invoke(self, ctx: Any) -> Any:
        if ctx._protected_args:
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
    dry_run: bool = False
    requests: tuple[PlannedRequest, ...] = ()


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


def _planned_request_for_cmd(
    cmd: Sequence[str],
    *,
    env: dict[str, str] | None = None,
    condition: str = "",
    repeat: str = "",
) -> PlannedRequest:
    """Construct a PlannedRequest for a command, inserting uv preview flags when needed."""
    full_cmd = list(cmd)
    if full_cmd and full_cmd[0] == "uv" and "--preview-features" not in full_cmd:
        full_cmd[1:1] = ["--preview-features", "malware-check,check-command"]
    env_tuple = tuple((k, v) for k, v in sorted(env.items())) if env else ()
    return PlannedRequest(
        method="run",
        target=full_cmd[0] if full_cmd else "",
        argv=tuple(full_cmd),
        env=env_tuple,
        condition=condition,
        repeat=repeat,
    )


def _run(
    cmd: list[str],
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    capture_output: bool = False,
    env: dict[str, str] | None = None,
) -> bool:
    """Run a CI check subprocess synchronously."""
    if is_dry_run():
        req = _planned_request_for_cmd(cmd, env=env)
        render_request_plan(MESSAGES.ci.ci_dry_run_heading, [req])
        return True
    root = _get_project_root()
    full_cmd = list(cmd)
    if full_cmd and full_cmd[0] == "uv" and "--preview-features" not in full_cmd:
        full_cmd[1:1] = ["--preview-features", "malware-check,check-command"]
    result = _get("run_subprocess")(
        full_cmd, cwd=root, timeout=timeout, capture_output=capture_output, env=env
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
    if is_dry_run():
        return
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

    if is_dry_run():
        req = _planned_request_for_cmd(check_spec.cmd)
        return CheckResult(
            name=check_spec.name,
            display_title=check_spec.display_title,
            passed=False,
            dry_run=True,
            duration_seconds=0.0,
            stdout="",
            stderr="",
            requests=(req,),
        )

    start_time = time.perf_counter()
    root = _get_project_root()

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


def _resolve_pytest_cmd() -> list[str]:
    """Construct check command line arguments for the pytest and coverage row."""
    return [
        "uv",
        "run",
        "pytest",
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
            name="deps",
            display_title=MESSAGES.ci.deps,
            cmd=["uv", "run", "deptry", "src"],
            span_name="ci.step.deps",
            metric_step="deps",
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
    docs_fix: bool = False,
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
    if docs_fix:
        docs_spec = next((s for s in selected_specs if s.name == "docs"), None)
        if docs_spec and docs_spec.fix_cmd:
            await _execute_check_async(
                CheckSpec(
                    name="docs_fix",
                    display_title=MESSAGES.ci.docs_validation,
                    cmd=docs_spec.fix_cmd,
                    span_name="ci.step.docs_fix",
                    metric_step="docs_fix",
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
        duration_seconds=0.0,
        stdout=test_result.stdout,
        stderr=test_result.stderr,
        dry_run=test_result.dry_run,
        requests=test_result.requests,
    )
    assembled: list[CheckResult] = [py_result]
    for i, res in enumerate(raw_results):
        assembled.append(res)
        if i == test_idx:
            assembled.append(coverage_result)
    return assembled


def _collect_fix_requests(
    selected_specs: Sequence[CheckSpec],
    *,
    format_fix: bool,
    lint_fix: bool,
    docs_fix: bool,
) -> list[PlannedRequest]:
    """Collect planned requests for pre-fix steps in execution order."""
    fixes = [
        ("format", format_fix),
        ("lint", lint_fix),
        ("docs", docs_fix),
    ]
    spec_map = {s.name: s for s in selected_specs}
    requests: list[PlannedRequest] = []
    for name, enabled in fixes:
        if not enabled:
            continue
        spec = spec_map.get(name)
        if spec and spec.fix_cmd:
            requests.append(_planned_request_for_cmd(spec.fix_cmd))
    return requests


def _dry_run_all_checks(
    selected_specs: Sequence[CheckSpec],
    *,
    format_fix: bool,
    lint_fix: bool,
    docs_fix: bool,
) -> list[CheckResult]:
    """Handle dry run for all checks: render request plan and return dry-run CheckResults."""
    fix_requests = _collect_fix_requests(
        selected_specs, format_fix=format_fix, lint_fix=lint_fix, docs_fix=docs_fix
    )
    check_requests = [_planned_request_for_cmd(s.cmd) for s in selected_specs]
    render_request_plan(MESSAGES.ci.ci_dry_run_heading, [*fix_requests, *check_requests])
    py_result = CheckResult(
        name="python_version",
        display_title=MESSAGES.ci.python_version_check,
        passed=False,
        dry_run=True,
        duration_seconds=0.0,
    )
    raw_results = [
        CheckResult(
            name=spec.name,
            display_title=spec.display_title,
            passed=False,
            dry_run=True,
            duration_seconds=0.0,
            requests=(_planned_request_for_cmd(spec.cmd),),
        )
        for spec in selected_specs
    ]
    return _assemble_ci_results(py_result, selected_specs, raw_results)


async def _run_all_checks_async(
    *,
    lint_fix: bool = False,
    format_fix: bool = False,
    docs_fix: bool = False,
    specs: Sequence[CheckSpec] | None = None,
) -> list[CheckResult]:
    """Execute CI verification gates concurrently using asyncio."""
    if is_dry_run():
        selected_specs = list(specs) if specs is not None else get_check_specs()
        return _dry_run_all_checks(
            selected_specs,
            format_fix=format_fix,
            lint_fix=lint_fix,
            docs_fix=docs_fix,
        )

    _clean_coverage_artifacts()

    py_ok, py_result = _run_python_version_step()
    if not py_ok:
        return [py_result]

    selected_specs = list(specs) if specs is not None else get_check_specs()
    if not selected_specs:
        return [py_result]

    await _run_pre_fixes_async(
        selected_specs,
        format_fix=format_fix,
        lint_fix=lint_fix,
        docs_fix=docs_fix,
    )

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
    if is_dry_run() or any(res.dry_run for res in results):
        return
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
    if is_dry_run() or any(res.dry_run for res in results):
        return
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
        dur_text = (
            "-"
            if res.name == "coverage"
            else (format_duration(res.duration_seconds) if res.duration_seconds > 0 else "<0.01s")
        )
        rows.append([res.name, status_text, dur_text])

    _get("print_table")(
        title=MESSAGES.ci.ci_summary_title,
        columns=[(MESSAGES.ci.col_check, "cyan"), MESSAGES.ci.col_result, ("Duration", "dim")],
        rows=rows,
    )
    mode_text = "cached execution" if cached else "concurrent async execution"
    _get("print_muted")(f"Total Elapsed: {format_duration(total_elapsed)} ({mode_text})\n")


def _compute_before_fingerprint(
    root: Path,
    ci_options: dict[str, Any],
    *,
    is_narrowed: bool,
) -> str | None:
    """Compute the workspace fingerprint before checks execute, for full non-dry runs."""
    if is_narrowed or is_dry_run():
        return None
    from devops_cli.ci.cache import compute_workspace_fingerprint

    fp_info = compute_workspace_fingerprint(root=root, options=ci_options)
    return fp_info[0] if fp_info else None


def _try_get_ci_cache(
    root: Path,
    ci_options: dict[str, Any],
    *,
    fingerprint: str | None = None,
) -> list[CheckResult] | None:
    """Attempt fast retrieval of passing CI cache entry."""
    from devops_cli.ci.cache import compute_workspace_fingerprint, get_ci_cache

    if fingerprint is None:
        fp_info = compute_workspace_fingerprint(root=root, options=ci_options)
        if not fp_info:
            return None
        fingerprint = fp_info[0]
    entry = get_ci_cache(fingerprint=fingerprint, options=ci_options, root=root)
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
    ci_options: dict[str, Any],
    *,
    before_fingerprint: str | None = None,
) -> None:
    """Persist successful CI run into cache if working tree did not change during the run."""
    from devops_cli.ci.cache import (
        CICachedCheck,
        compute_workspace_fingerprint,
        save_ci_cache,
    )

    fp_info = compute_workspace_fingerprint(root=root, options=ci_options)
    if not fp_info:
        return
    fingerprint, head_sha = fp_info
    if before_fingerprint is not None and fingerprint != before_fingerprint:
        _get("print_warning")(MESSAGES.ci.cache_tree_changed, safe=True)
        return
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
        options=ci_options,
        passed=True,
        root=root,
    )


def _try_fast_cached_ci(
    root: Path,
    ci_options: dict[str, Any],
    *,
    fingerprint: str | None = None,
    cache: bool,
    force: bool,
) -> bool:
    """Attempt fast cached CI execution, rendering summary and returning True on hit."""
    if not cache or force or is_dry_run():
        return False
    cached_results = _try_get_ci_cache(root, ci_options, fingerprint=fingerprint)
    if cached_results is None:
        return False
    _get("print_info")(MESSAGES.ci.cache_hit)
    _print_summary(cached_results, total_elapsed=0.005, cached=True)
    return True


def _warn_when_over_budget(results: list[CheckResult]) -> None:
    """Warn when the test step ran past its budget, naming the tests that took longest."""
    if is_dry_run() or any(res.dry_run for res in results):
        return
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
    ci_options: dict[str, Any],
    *,
    before_fingerprint: str | None = None,
    save_cache: bool = True,
) -> None:
    """Handle post-execution caching or failure exit.

    A passing run is recorded whatever `--cache` said. That flag decides whether an
    existing entry may be *trusted*, not whether a fresh result is worth keeping: a
    `--no-cache` run has done the full work and proved the tree, so discarding the proof
    made the next ordinary run repeat it for no reason.
    """
    if is_dry_run() or any(res.dry_run for res in results):
        return

    if all(res.passed for res in results):
        if save_cache:
            _try_save_ci_cache(root, results, ci_options, before_fingerprint=before_fingerprint)
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
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Run all CI checks concurrently in parallel with non-blocking async execution."""
    if dry_run:
        set_dry_run(True)
    root = _get_project_root()
    if not ctx.meta.get(CONST_CI_SUBCOMMAND_SHOWS_HELP_META_KEY):
        _announce_gate_root(root)
    if ctx.invoked_subcommand is not None:
        return

    selected_specs = resolve_selected_specs(only=only, skip=skip)
    is_narrowed = bool(only or skip)

    effective_fix = fix and not check
    ci_options = {"fix": effective_fix, "check": check}
    before_fingerprint = _compute_before_fingerprint(root, ci_options, is_narrowed=is_narrowed)

    if not is_narrowed and _try_fast_cached_ci(
        root, ci_options, fingerprint=before_fingerprint, cache=cache, force=force
    ):
        return

    start_time = time.perf_counter()
    if not is_dry_run():
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
    _handle_ci_results(
        results,
        root,
        ci_options,
        before_fingerprint=before_fingerprint,
        save_cache=(not is_narrowed),
    )


# =============================================================================
# Individual CI Commands
# =============================================================================


def _normalize_repo_rel_path(path: Path | str, root: Path) -> str:
    """Normalize a path to a repo-relative forward-slash POSIX path."""
    p = Path(path)
    if p.is_absolute():
        try:
            return p.resolve().relative_to(root.resolve()).as_posix()
        except ValueError, OSError:
            return p.as_posix()
    return p.as_posix().lstrip("./")


def _check_trigger_files(all_paths: set[str], fallback: bool) -> bool:
    """Check if any trigger files are in the changed path set."""
    from devops_cli.core.coverage_index import _FULL_RUN_TRIGGERS

    triggers = [p for p in sorted(all_paths) if Path(p).name in _FULL_RUN_TRIGGERS]
    if not triggers:
        return True
    first_trigger = triggers[0]
    if not fallback:
        _get("print_error")(
            MESSAGES.ci.selection_trigger_refusal.format(file=first_trigger),
            prefix=False,
        )
        raise typer.Exit(1)
    _get("print_warning")(MESSAGES.ci.selection_trigger_full_run.format(file=first_trigger))
    return False


def _map_test_tree_path(
    path: str,
    root: Path,
    selected_tests: set[str],
    mapped_sources: dict[str, list[str]],
    unmapped_sources: list[str],
    source_selectors: dict[str, str],
) -> None:
    """Handle a path under the tests/ directory."""
    from devops_cli.config.constants import (
        CONST_PYTHON_FILE_SUFFIX,
        CONST_TEST_FILE_PREFIX,
        CONST_TESTS_ROOT_DIR,
    )
    from devops_cli.core.coverage_index import _find_tests_importing_helper, _is_test_file

    if _is_test_file(path):
        if (root / path).is_file():
            selected_tests.add(path)
            mapped_sources[path] = [path]
            source_selectors[path] = "direct"
        return

    if not (root / path).is_file():
        return

    if path.endswith(CONST_PYTHON_FILE_SUFFIX):
        tests_dir = root / CONST_TESTS_ROOT_DIR
        all_test_files = [
            p.relative_to(root).as_posix()
            for p in tests_dir.rglob(f"{CONST_TEST_FILE_PREFIX}*{CONST_PYTHON_FILE_SUFFIX}")
            if p.is_file()
        ]
        importing = _find_tests_importing_helper(path, root, all_test_files)
        source_selectors[path] = "text-based selector"
        if importing:
            selected_tests.update(importing)
            mapped_sources[path] = sorted(importing)
        else:
            unmapped_sources.append(path)


def _map_src_tree_path(
    path: str,
    root: Path,
    index: Any,
    has_index: bool,
    selected_tests: set[str],
    mapped_sources: dict[str, list[str]],
    unmapped_sources: list[str],
    source_selectors: dict[str, str],
) -> None:
    """Handle a path under the src/ directory."""
    if has_index and path in index.covering_tests:
        covering = index.covering_tests[path]
        selected_tests.update(covering)
        mapped_sources[path] = sorted(covering)
        source_selectors[path] = "coverage index"
        return

    from devops_cli.core.test_selection import select_tests_for_sources

    text_sel = select_tests_for_sources([path], root)
    source_selectors[path] = "text-based selector"
    if text_sel.has_selection:
        targets = text_sel.pytest_targets()
        selected_tests.update(targets)
        mapped_sources[path] = targets
    else:
        unmapped_sources.append(path)


def _map_changed_paths(
    all_paths: set[str],
    root: Path,
    index: Any,
    has_index: bool,
) -> tuple[list[str], dict[str, list[str]], list[str], dict[str, str]]:
    """Map each candidate path under src/ or tests/ onto test targets and selectors."""
    from devops_cli.config.constants import CONST_SOURCE_ROOT_DIR, CONST_TESTS_ROOT_DIR

    selected_tests: set[str] = set()
    mapped_sources: dict[str, list[str]] = {}
    unmapped_sources: list[str] = []
    source_selectors: dict[str, str] = {}

    for raw_path in sorted(all_paths):
        path = raw_path.replace("\\", "/")
        if path.startswith(f"{CONST_TESTS_ROOT_DIR}/"):
            _map_test_tree_path(
                path, root, selected_tests, mapped_sources, unmapped_sources, source_selectors
            )
        elif path.startswith(f"{CONST_SOURCE_ROOT_DIR}/"):
            _map_src_tree_path(
                path,
                root,
                index,
                has_index,
                selected_tests,
                mapped_sources,
                unmapped_sources,
                source_selectors,
            )

    valid_targets = sorted(t for t in selected_tests if (root / t).is_file())
    return valid_targets, mapped_sources, unmapped_sources, source_selectors


def _report_selection(
    mapped_sources: dict[str, list[str]],
    unmapped_sources: list[str],
    source_selectors: dict[str, str],
) -> None:
    """Explain which tests were chosen for the supplied files, and which were not."""
    for source in sorted(mapped_sources):
        tests = mapped_sources[source]
        selector = source_selectors.get(source, "coverage index")
        selector_suffix = "" if selector == "direct" else f" ({selector})"
        _get("print_muted")(f"  {source} → {', '.join(tests)}{selector_suffix}")
    if unmapped_sources:
        _get("print_warning")(
            MESSAGES.ci.no_covering_tests.format(files=", ".join(sorted(unmapped_sources)))
        )


def _resolve_test_targets(paths: list[Path], fallback: bool) -> list[str] | None:
    """Map changed files onto pytest targets using coverage index and text fallback."""
    from devops_cli.ci.cache import compute_worktree_blob_hashes, resolve_coverage_index_path
    from devops_cli.core.coverage_index import (
        compute_index_drift,
        load_index,
    )
    from devops_cli.output import format_duration

    root = _get_project_root()
    index_path = resolve_coverage_index_path(root)
    index = load_index(index_path)
    has_index = not index.is_empty

    user_paths = {_normalize_repo_rel_path(p, root) for p in paths}
    all_paths = set(user_paths)

    if has_index:
        current_hashes = compute_worktree_blob_hashes(root)
        drift_files = compute_index_drift(index, current_hashes)
        all_paths.update(drift_files)
        age_seconds = max(0.0, time.time() - index.built_at) if index.built_at > 0 else 0.0
        age_str = format_duration(age_seconds) if age_seconds > 0 else "0s"
        _get("print_muted")(
            MESSAGES.ci.coverage_index_age.format(age=age_str, changed_count=len(drift_files))
        )
    else:
        _get("print_muted")(MESSAGES.ci.coverage_index_missing)

    if not _check_trigger_files(all_paths, fallback):
        return None

    targets, mapped_sources, unmapped_sources, source_selectors = _map_changed_paths(
        all_paths, root, index, has_index
    )
    _report_selection(mapped_sources, unmapped_sources, source_selectors)

    if targets:
        return targets

    if not unmapped_sources and not mapped_sources:
        _get("print_muted")(MESSAGES.ci.no_testable_files)
        return []

    if fallback:
        _get("print_warning")(MESSAGES.ci.selection_fallback)
        return None

    _get("print_error")(MESSAGES.ci.selection_empty, prefix=False)
    raise typer.Exit(1)


def _build_test_cmd(
    numprocesses: str | None,
    verbose: bool,
    k: str | None,
    x: bool,
    targets: list[str] | None,
) -> list[str]:
    """Build the pytest command line arguments."""
    cmd = ["uv", "run", "pytest"]
    if numprocesses is not None:
        cmd.extend(["-n", numprocesses])
    if verbose:
        cmd.append("-v")
    if k:
        cmd.extend(["-k", k])
    if x:
        cmd.append("-x")
    if targets:
        cmd.extend(targets)
    return cmd


def _head_seed(root: Path) -> int:
    """A shuffle seed derived from HEAD: its commit hash's leading eight hex digits."""
    result = _get("run_subprocess")(["git", "rev-parse", "HEAD"], cwd=root, quiet=True)
    if result.returncode != 0:
        _get("print_error")(MESSAGES.ci.repeat_seed_unavailable, prefix=False)
        raise typer.Exit(1)
    return int(result.stdout[:8], 16)


def _run_shuffled_repeats(
    base_cmd: list[str], targets: list[str] | None, runs: int, seed: int | None
) -> None:
    """Run the targets `runs` times, one run after another, shuffled by pytest-randomly with
    seeds `seed` to `seed + runs - 1`, stopping at the first failure with its seed and command.
    """
    if targets is None:
        _get("print_error")(MESSAGES.ci.repeat_needs_targets, prefix=False)
        raise typer.Exit(1)
    first = _head_seed(_get_project_root()) if seed is None else seed
    for run, run_seed in enumerate(range(first, first + runs), start=1):
        cmd = [*base_cmd, "-p", "randomly", f"--randomly-seed={run_seed}", *targets]
        if not _run(cmd):
            failed = MESSAGES.ci.repeat_failed.format(
                run=run, runs=runs, seed=run_seed, command=shlex.join(cmd)
            )
            _get("print_error")(failed, prefix=False, safe=True)
            raise typer.Exit(1)


@app.command()
def test(
    paths: Annotated[list[Path] | None, typer.Argument(help=HELP.ci.test_paths)] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help=HELP.options.verbose)] = False,
    k: Annotated[str | None, typer.Option("-k", help=HELP.ci.filter_keyword)] = None,
    x: Annotated[bool, typer.Option("-x", help=HELP.ci.stop_fail)] = False,
    numprocesses: Annotated[
        str | None, typer.Option("-n", "--numprocesses", help=HELP.ci.num_workers)
    ] = None,
    fallback: Annotated[
        bool, typer.Option("--fallback/--no-fallback", help=HELP.ci.selection_fallback)
    ] = True,
    repeat: Annotated[
        int, typer.Option("--repeat", min=0, help=HELP.ci.repeat)
    ] = DEFAULT_CI_TEST_REPEAT_RUNS,
    seed: Annotated[int | None, typer.Option("--seed", help=HELP.ci.seed)] = None,
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

    if repeat:
        _run_shuffled_repeats(_build_test_cmd("0", verbose, k, x, None), targets, repeat, seed)
        return

    cmd = _build_test_cmd(numprocesses, verbose, k, x, targets)
    if not _run(cmd):
        raise typer.Exit(1)


def _handle_coverage_index_build(cmd: list[str]) -> None:
    """Execute full test suite with coverage contexts and persist coverage reverse index."""
    root = _get_project_root()
    index_cmd = list(cmd)
    index_cmd.append("--cov-context=test")

    if is_dry_run():
        _run(index_cmd, env={"COVERAGE_CORE": "ctrace"})
        return

    from devops_cli.ci.cache import compute_worktree_blob_hashes, resolve_coverage_index_path
    from devops_cli.core.coverage_index import (
        build_index_from_coverage,
        filter_coverage_source_hashes,
        save_index,
    )

    hashes_before = filter_coverage_source_hashes(compute_worktree_blob_hashes(root))
    env = {"COVERAGE_CORE": "ctrace"}
    if not _run(index_cmd, env=env):
        raise typer.Exit(1)

    hashes_after = filter_coverage_source_hashes(compute_worktree_blob_hashes(root))
    if hashes_before != hashes_after:
        all_keys = set(hashes_before.keys()) | set(hashes_after.keys())
        changed = sorted(k for k in all_keys if hashes_before.get(k) != hashes_after.get(k))
        _get("print_error")(
            MESSAGES.ci.coverage_index_tree_changed.format(files=", ".join(changed)),
            prefix=False,
        )
        raise typer.Exit(1)

    t0 = time.perf_counter()
    coverage_db = root / ".data" / ".coverage"
    if not coverage_db.is_file() and (root / ".coverage").is_file():
        coverage_db = root / ".coverage"

    index = build_index_from_coverage(
        coverage_db, root, source_hashes=hashes_after, built_at=time.time()
    )
    destination = resolve_coverage_index_path(root)
    save_index(index, destination)
    elapsed = time.perf_counter() - t0
    _get("print_info")(
        MESSAGES.ci.coverage_index_saved.format(duration=f"{elapsed:.2f}s"),
        safe=True,
    )


@app.command()
def coverage(
    html: Annotated[bool, typer.Option("--html", help=HELP.ci.html_report)] = False,
    build_index: Annotated[
        bool,
        typer.Option("--build-index", help=HELP.ci.build_index),
    ] = False,
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
    if build_index:
        _handle_coverage_index_build(cmd)
        return
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
def devcontainer(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Validate devcontainer manifest configuration syntax."""
    if dry_run:
        set_dry_run(True)
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    spec = get_check_spec("devcontainer")
    if not _run(spec.cmd):
        raise typer.Exit(1)


@app.command()
def deps(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Validate dependency hygiene and imports via deptry."""
    if dry_run:
        set_dry_run(True)
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    spec = get_check_spec("deps")
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
    if not is_dry_run() and not any(res.dry_run for res in results):
        if not all(res.passed for res in results):
            raise typer.Exit(1)
