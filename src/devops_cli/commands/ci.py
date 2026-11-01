"""Project testing, validation, and code quality checks with async concurrent execution."""

from __future__ import annotations

import asyncio
import contextlib
import functools
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Final

import typer
from pydantic import BaseModel, ConfigDict, Field
from typer.core import TyperGroup

from devops_cli.config.commands import build_npm_audit_cmd
from devops_cli.config.constants import (
    CONST_AST_GREP_SCAN_ARGS,
    CONST_BANDIT_INI_NAME,
    CONST_CI_RUN_STOP_SIGNAL_NAMES,
    CONST_CI_SLOWEST_TESTS_SHOWN,
    CONST_CI_SUBCOMMAND_SHOWS_HELP_META_KEY,
    CONST_CI_TEST_BUDGET_SECONDS,
    CONST_CI_TEST_JOB_NAME,
    CONST_CI_WORKFLOW_FILE,
    CONST_EXIT_CANCELLED,
    CONST_EXIT_FAILURE,
    CONST_GIT_MAIN_BRANCH,
    CONST_PYPROJECT_FILENAME,
    CONST_SOURCE_ROOT_DIR,
    CONST_TESTS_ROOT_DIR,
    CONST_TOOLS_LOCK_REPO_DIR,
)
from devops_cli.config.defaults import (
    DEFAULT_BANDIT_SEVERITY,
    DEFAULT_CI_BANDIT_NICENESS,
    DEFAULT_CI_JOB_TIME_RUNS,
    DEFAULT_CI_MUTATE_TIMEOUT_SECONDS,
    DEFAULT_CI_TEST_NARROWED_WORKERS,
    DEFAULT_CI_TEST_REPEAT_RUNS,
    DEFAULT_CI_TEST_SERIAL_MAX_FILES,
    DEFAULT_PYTHON_VERSION,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.core import clock
from devops_cli.core.cli import new_typer
from devops_cli.core.dependency_audit import AuditVerdict, audit_verdict
from devops_cli.core.process import prepare_tool_cmd, run_subprocess
from devops_cli.dry_run import dry_run_class, is_dry_run, render_dry_run_result, set_dry_run
from devops_cli.dry_run.requests import PlannedRequest, render_request_plan
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    print_error,
    print_info,
    print_muted,
    print_section,
    print_success,
    print_table,
    print_warning,
    write_stderr,
    write_stdout,
)
from devops_cli.telemetry import trace_span
from devops_cli.telemetry.instruments import CI_CHECKS_TOTAL, CI_GATE_SLOT_WAIT, emit

if TYPE_CHECKING:
    from devops_cli.ci.job_time import JobTimeReport
    from devops_cli.ci.mutate import MutationTarget
    from devops_cli.core.test_selection import SuiteImports

_ORIG_RUN_SUBPROCESS = run_subprocess


def _current_run_subprocess() -> Any:
    from devops_cli.core.process import run_subprocess as core_run

    runner = getattr(sys.modules.get(__name__), "run_subprocess", core_run)
    return core_run if runner is _ORIG_RUN_SUBPROCESS else runner


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


app = new_typer(cls=FileOrSubcommandGroup, help=HELP.ci.app)

# The severity the security row scans `src/` at: every Bandit finding in the product needs a fix or
# a reviewed nosec marker that names its rules and a reason (#1538). `tests/` keeps
# DEFAULT_BANDIT_SEVERITY.
_BANDIT_SOURCE_SEVERITY: Final[str] = "low"


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

    print_info(MESSAGES.ci.gate_root.format(root=root), safe=True)
    if is_stale_linked_worktree(root):
        stale = MESSAGES.ci.gate_root_stale.format(root=root, root_arg=shlex.quote(str(root)))
        print_warning(stale, safe=True)
    from devops_cli.ci import diagnostics

    if fstype := diagnostics.slow_mount_fstype(root):
        slow = MESSAGES.ci.gate_root_slow_mount.format(root=root, fstype=fstype)
        print_warning(slow, safe=True)


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
    # Commands the check runs after `cmd`, each as a process of its own and without a shell. The
    # check passes only when `cmd` and every one of these exit 0.
    also_cmds: list[list[str]] = Field(default_factory=list)
    # Whether the commands are dependency audits, whose failure is read by the kind of command
    # (`devops_cli.core.dependency_audit`) and reported as a finding or an audit that did not run.
    dependency_audit: bool = False
    # Whether the check keeps the host's CPUs busy for minutes: a p90 above 200 s in the CI cache
    # of the host (#2336). A run that selects one waits for a gate slot (`_gate_slot`).
    heavy: bool = False

    @property
    def commands(self) -> list[list[str]]:
        """Every command the check runs, in order."""
        return [self.cmd, *self.also_cmds]


# =============================================================================
# Environment & Subprocess Helpers
# =============================================================================


def _verify_python_314_environment() -> bool:
    """Verify runtime environment meets strict Python 3.14+ requirements."""
    import sys

    if sys.version_info < (3, 14):  # noqa: UP036
        ver_str = sys.version.split()[0]
        print_error(
            MESSAGES.ci.python_version_fail.format(
                required=DEFAULT_PYTHON_VERSION, current=ver_str
            ),
            prefix=False,
        )
        return False
    return True


def _with_uv_preview(cmd: Sequence[str]) -> list[str]:
    """`cmd`, with uv's malware-check and check-command preview features on when it starts uv."""
    return prepare_tool_cmd(cmd)


def _planned_request_for_cmd(
    cmd: Sequence[str],
    *,
    env: dict[str, str] | None = None,
    condition: str = "",
    repeat: str = "",
) -> PlannedRequest:
    """Construct a PlannedRequest for a command, inserting uv preview flags when needed."""
    full_cmd = _with_uv_preview(cmd)
    env_tuple = tuple((k, v) for k, v in sorted(env.items())) if env else ()
    return PlannedRequest(
        method="run",
        target=full_cmd[0] if full_cmd else "",
        argv=tuple(full_cmd),
        env=env_tuple,
        condition=condition,
        repeat=repeat,
    )


def _stop_signals_to_handle() -> list[signal.Signals]:
    """The stop signals a run may take over: none off the main thread, which cannot set signal
    handlers, and none this process ignores, as under `nohup`, where the ignore stands."""
    if threading.current_thread() is not threading.main_thread():
        return []
    present = [
        getattr(signal, name) for name in CONST_CI_RUN_STOP_SIGNAL_NAMES if hasattr(signal, name)
    ]
    return [sig for sig in present if signal.getsignal(sig) is not signal.SIG_IGN]


@contextlib.contextmanager
def _cancelled_by_stop_signals(
    loop: asyncio.AbstractEventLoop, cancel: Callable[[], object]
) -> Iterator[None]:
    """While it lasts, Ctrl-C's SIGINT, SIGTERM and SIGHUP call `cancel` on `loop`, and the
    previous handlers come back after; one set outside Python, which Python cannot put back, comes
    back as the default.

    `loop.add_signal_handler` writes each signal to the loop's own pipe, so the signal wakes the
    loop wherever it lands. A handler that `signal.signal` sets runs only when the main thread runs
    bytecode again: a signal that came just before the loop started to wait, or that the kernel
    handed to another thread, was handled only when the child exited (#2092). Each signal only
    cancels the run's task and raises nothing, so the stop takes a second signal at its next wait
    and still sends its SIGKILL. `asyncio.run`'s own Ctrl-C handler raised KeyboardInterrupt at a
    second Ctrl-C between any two bytecodes, also before the stop's `try` (#2069)."""
    previous: dict[signal.Signals, Any] = {}
    try:
        for sig in _stop_signals_to_handle():
            previous[sig] = signal.getsignal(sig)
            loop.add_signal_handler(sig, cancel)
        yield
    finally:
        for sig, handler in previous.items():
            loop.remove_signal_handler(sig)
            signal.signal(sig, signal.SIG_DFL if handler is None else handler)


async def _run_in_own_session(
    cmd: list[str], root: Path, timeout: float, capture_output: bool, env: dict[str, str] | None
) -> subprocess.CompletedProcess[str]:
    """Run `cmd` in a session of its own, which a timeout, Ctrl-C, SIGTERM or SIGHUP stops as a
    whole process group."""
    task = asyncio.current_task()

    def cancel() -> None:
        if task is not None:
            task.cancel()

    from devops_cli.core.process import run_subprocess_async

    with _cancelled_by_stop_signals(asyncio.get_running_loop(), cancel):
        result: subprocess.CompletedProcess[str] = await run_subprocess_async(
            cmd, cwd=root, timeout=timeout, capture_output=capture_output, env=env
        )
    return result


def _session_returncode(
    cmd: list[str], root: Path, timeout: float, capture_output: bool, env: dict[str, str] | None
) -> int:
    """The exit code of `cmd` run in a session of its own (#1669). A timeout of `subprocess.run`
    kills only `uv`, which left pytest running; stopping the session's whole group stops pytest
    and its workers with it. A run past `timeout` fails, naming the command and timeout; one
    stopped by Ctrl-C, SIGTERM or SIGHUP exits as cancelled."""
    try:
        result = asyncio.run(_run_in_own_session(cmd, root, timeout, capture_output, env))
    except subprocess.TimeoutExpired:
        timed_out = MESSAGES.ci.run_timed_out.format(
            command=shlex.join(cmd), timeout=f"{timeout:g}s"
        )
        print_error(timed_out, prefix=False, safe=True)
        return CONST_EXIT_FAILURE
    except asyncio.CancelledError:
        raise typer.Exit(CONST_EXIT_CANCELLED) from None
    return int(result.returncode)


def _returncode(
    cmd: list[str],
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    capture_output: bool = False,
    env: dict[str, str] | None = None,
    *,
    own_session: bool = False,
) -> int:
    """Run a CI check subprocess synchronously and return its exit code; 0 in a dry run. With
    `own_session`, the command runs in a session of its own and is stopped as a whole process
    group."""
    if is_dry_run():
        req = _planned_request_for_cmd(cmd, env=env)
        render_request_plan(MESSAGES.ci.ci_dry_run_heading, [req])
        return 0
    root = _get_project_root()
    full_cmd = _with_uv_preview(cmd)
    if own_session:
        return _session_returncode(full_cmd, root, timeout, capture_output, env)
    result = _current_run_subprocess()(
        full_cmd, cwd=root, timeout=timeout, capture_output=capture_output, env=env
    )
    return int(result.returncode)


def _run(
    cmd: list[str],
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    capture_output: bool = False,
    env: dict[str, str] | None = None,
    *,
    own_session: bool = False,
) -> bool:
    """Run a CI check subprocess synchronously; whether it passed."""
    code = _returncode(
        cmd, timeout=timeout, capture_output=capture_output, env=env, own_session=own_session
    )
    return code == 0


def _audit_failure_line(cmd: Sequence[str], run: subprocess.CompletedProcess[str]) -> str | None:
    """What a run of an audit command says went wrong, read by the kind of command; None when the
    audit was clean."""
    verdict = audit_verdict(cmd, run.returncode, run.stdout or "")
    if verdict is AuditVerdict.CLEAN:
        return None
    template = (
        MESSAGES.ci.audit_vulnerable
        if verdict is AuditVerdict.VULNERABLE
        else MESSAGES.ci.audit_not_run
    )
    return template.format(code=run.returncode, tool=cmd[0])


def _report_audit(cmd: list[str]) -> bool:
    """Run one audit command with its output captured, which its verdict reads. When it was not
    clean, show the output and say why; whether it was clean."""
    run: subprocess.CompletedProcess[str] = _current_run_subprocess()(
        _with_uv_preview(cmd),
        cwd=_get_project_root(),
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        capture_output=True,
    )
    failure = _audit_failure_line(cmd, run)
    if failure is not None:
        _write_process_output(run.stdout, run.stderr)
        print_error(failure, prefix=False)
    return failure is None


def _run_audits() -> bool:
    """Run every command of the `audit` check, as one plan in a dry run; whether all were clean.
    A command that fails does not stop the ones after it, so one run reports every failure."""
    commands = get_check_spec("audit").commands
    if is_dry_run():
        render_request_plan(
            MESSAGES.ci.ci_dry_run_heading, [_planned_request_for_cmd(cmd) for cmd in commands]
        )
        return True
    return all([_report_audit(cmd) for cmd in commands])


def _section(title: str) -> None:
    print_section(f" {title} ", style="cyan")


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
    """Clean up residual `.coverage.*` worker files from the checked tree and .data/.

    The combined `.data/.coverage` stays: `devops ci coverage --build-index` and CI's
    `coverage xml` read it after the gate (#1743).
    """
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
            for path in target_dir.glob(".coverage.*"):
                _unlink_coverage_path(path, force=force)


def _format_process_output(raw: str | bytes | None) -> str:
    """Safely decode raw subprocess output to string."""
    if not raw:
        return ""
    if isinstance(raw, str):
        return raw
    return raw.decode("utf-8", errors="replace")


def _write_process_output(stdout: str | bytes | None, stderr: str | bytes | None) -> None:
    """Write what a process printed, each stream to its own, when it printed anything."""
    if out := _format_process_output(stdout):
        write_stdout(out.rstrip() + "\n")
    if err := _format_process_output(stderr):
        write_stderr(err.rstrip() + "\n")


def _format_check_badge(passed: bool) -> str:
    """Format rich terminal badge for check status."""
    return "[green]✓ pass[/green]" if passed else "[bold red]✗ fail[/bold red]"


def _planned_requests(spec: CheckSpec) -> tuple[PlannedRequest, ...]:
    """The request each command of the check would make."""
    return tuple(_planned_request_for_cmd(cmd) for cmd in spec.commands)


def _merged_run(
    earlier: subprocess.CompletedProcess[str], later: subprocess.CompletedProcess[str]
) -> subprocess.CompletedProcess[str]:
    """One run for two: the first non-zero exit code, else 0, and the output of both in order."""
    return subprocess.CompletedProcess(
        earlier.args,
        earlier.returncode or later.returncode,
        (earlier.stdout or "") + (later.stdout or ""),
        (earlier.stderr or "") + (later.stderr or ""),
    )


def _with_audit_failure_line(
    cmd: Sequence[str], run: subprocess.CompletedProcess[str]
) -> subprocess.CompletedProcess[str]:
    """`run` of an audit command, with what it says went wrong at the end of its error output."""
    failure = _audit_failure_line(cmd, run)
    if failure is None:
        return run
    return subprocess.CompletedProcess(
        run.args, run.returncode, run.stdout, (run.stderr or "") + failure + "\n"
    )


async def _run_check_commands(
    spec: CheckSpec, root: Path, timeout: float, capture_output: bool
) -> subprocess.CompletedProcess[str]:
    """Run each command of the check in turn, even after one fails, and answer as a single run.
    A dependency audit is run with its output captured, which its verdict reads, and a failed one
    says what went wrong, as `devops ci audit` does."""
    from devops_cli.core.process import run_subprocess_async

    runs = [
        await run_subprocess_async(
            _with_uv_preview(cmd),
            cwd=root,
            timeout=timeout,
            capture_output=capture_output or spec.dependency_audit,
        )
        for cmd in spec.commands
    ]
    if spec.dependency_audit:
        runs = [
            _with_audit_failure_line(cmd, run) for cmd, run in zip(spec.commands, runs, strict=True)
        ]
    first, *rest = runs
    return functools.reduce(_merged_run, rest, first)


def _count_check(step: str, *, passed: bool) -> None:
    """Count one check that the gate ran, by its step and outcome."""
    emit(CI_CHECKS_TOTAL, 1.0, {"step": step, "outcome": "pass" if passed else "fail"})


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
        return CheckResult(
            name=check_spec.name,
            display_title=check_spec.display_title,
            passed=False,
            dry_run=True,
            duration_seconds=0.0,
            stdout="",
            stderr="",
            requests=_planned_requests(check_spec),
        )

    start_time = time.perf_counter()
    root = _get_project_root()

    with trace_span(check_spec.span_name):
        try:
            proc = await _run_check_commands(check_spec, root, timeout, capture_output)
            passed = proc.returncode == 0
            dur = time.perf_counter() - start_time
            _count_check(check_spec.metric_step, passed=passed)
            from devops_cli.output import format_duration

            badge = _format_check_badge(passed)
            print_muted(
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
            _count_check(check_spec.metric_step, passed=False)
            badge = _format_check_badge(False)
            timeout_val = exc.timeout or timeout
            timeout_str = f"{timeout_val:g}s"
            print_muted(
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
# Gate Slots
# =============================================================================


@contextlib.contextmanager
def _gate_slot(needed: bool) -> Iterator[None]:
    """Hold one of the host's gate slots for the body when it runs CPU-heavy work (#2336).

    The gates of several agents share one host, and a full-suite pytest starts a worker for each
    CPU, so gates that run at once make each other several times slower. A run that needs a
    slot waits for one and says who holds them. A run that needs none, and a dry run, hold none.
    The wait is recorded and comes before the caller's clock starts.
    """
    if not needed or is_dry_run():
        yield
        return
    from devops_cli.ci.gate_slots import gate_slot, gate_slot_count, gate_slots_directory
    from devops_cli.config.settings import load_settings

    root = _get_project_root()
    slots = gate_slot_count(load_settings().ci.gate_slots)
    with gate_slot(
        gate_slots_directory(root),
        slots,
        holder=f"{os.getpid()} {root}",
        notify=lambda message: print_info(message, safe=True),
    ) as waited:
        emit(CI_GATE_SLOT_WAIT, waited)
        yield


# =============================================================================
# Pipeline Execution
# =============================================================================


def _resolve_pytest_cmd() -> list[str]:
    """Construct check command line arguments for the pytest and coverage row.

    The row prints the term report and writes no XML report: only CI's changed-line coverage
    step reads `coverage.xml`, and it writes the file from the combined data (#1743).
    """
    return [
        "uv",
        "run",
        "pytest",
        f"--durations={CONST_CI_SLOWEST_TESTS_SHOWN}",
        "--cov=src",
        "--cov-report=term-missing",
    ]


def _bandit_cmd(target: str, severity: str) -> list[str]:
    """Bandit over `target`, walking its directories, with the repository's `.bandit` and
    reporting `severity` and above, under `nice`: in the full gate it runs beside the test row's
    workers, the gate's critical path, and takes the CPU they leave idle (#1725). A target on the
    command line replaces the targets of `.bandit`, which still applies its skips."""
    return [
        "uv",
        "run",
        "nice",
        "-n",
        str(DEFAULT_CI_BANDIT_NICENESS),
        "bandit",
        "-r",
        target,
        "--ini",
        CONST_BANDIT_INI_NAME,
        "--severity-level",
        severity.lower(),
    ]


def _bandit_cmds(tests_severity: str) -> list[list[str]]:
    """The security row's Bandit runs: `src` at low severity and above, so a new low finding in
    the product fails the gate, then `tests` at `tests_severity` (#1538). Each file is scanned once,
    as one run over both targets scanned it."""
    return [
        _bandit_cmd(CONST_SOURCE_ROOT_DIR, _BANDIT_SOURCE_SEVERITY),
        _bandit_cmd(CONST_TESTS_ROOT_DIR, tests_severity),
    ]


def _npm_audit_cmds() -> list[list[str]]:
    """`npm audit` of the lockfile of each Node tool in the tools lock, as the repository holds it,
    which needs no install."""
    from devops_cli.tools_lock import load_tools_lock

    return [
        build_npm_audit_cmd(f"{CONST_TOOLS_LOCK_REPO_DIR}/{name}") for name in load_tools_lock().npm
    ]


# The git row records every scenario of the git fake again with the real git, outside pytest, and
# fails when a committed transcript differs (#2146). `git` is on the stock runner.
_GIT_TRANSCRIPTS_SCRIPT = (
    "import sys; from tests.support.git_recording import main; sys.exit(main(['--check']))"
)

# The test-settings row checks pyproject.toml timeout settings and tests/conftest.py environment (#2173).
_TEST_SETTINGS_SCRIPT = (
    "import sys; from tests.support.check_test_settings import main; sys.exit(main())"
)


def get_check_specs() -> list[CheckSpec]:
    """Return the single ordered table of CI quality gate check specifications."""
    from devops_cli.ci.typecheck import TYPECHECK_PATHS, typecheck_argv

    return [
        CheckSpec(
            name="test",
            display_title=MESSAGES.ci.pytest_coverage,
            cmd=_resolve_pytest_cmd(),
            span_name="ci.step.test_and_coverage",
            metric_step="test",
            heavy=True,
        ),
        CheckSpec(
            name="lint",
            display_title=MESSAGES.ci.ruff_check,
            cmd=["uv", "run", "ruff", "check", "--config", CONST_PYPROJECT_FILENAME, "."],
            span_name="ci.step.lint",
            metric_step="lint",
            fix_cmd=[
                "uv",
                "run",
                "ruff",
                "check",
                "--config",
                CONST_PYPROJECT_FILENAME,
                "--fix",
                ".",
            ],
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
            cmd=typecheck_argv(TYPECHECK_PATHS),
            span_name="ci.step.typecheck",
            metric_step="typecheck",
            heavy=True,
        ),
        CheckSpec(
            name="audit",
            display_title=MESSAGES.ci.dependency_audit,
            cmd=["uv", "audit"],
            also_cmds=_npm_audit_cmds(),
            dependency_audit=True,
            span_name="ci.step.audit",
            metric_step="audit",
        ),
        CheckSpec(
            name="security",
            display_title=MESSAGES.ci.bandit_scan,
            cmd=_bandit_cmds(DEFAULT_BANDIT_SEVERITY)[0],
            also_cmds=_bandit_cmds(DEFAULT_BANDIT_SEVERITY)[1:],
            span_name="ci.step.security",
            metric_step="security",
            heavy=True,
        ),
        CheckSpec(
            name="actionlint",
            display_title=MESSAGES.ci.actionlint,
            cmd=["actionlint"],
            span_name="ci.step.actionlint",
            metric_step="actionlint",
        ),
        CheckSpec(
            name="zizmor",
            display_title=MESSAGES.ci.zizmor,
            cmd=["uv", "run", "devops", "scan", "workflows"],
            span_name="ci.step.zizmor",
            metric_step="zizmor",
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
            name="build",
            display_title=MESSAGES.ci.uv_build,
            cmd=["uv", "build", "--quiet"],
            span_name="ci.step.build",
            metric_step="build",
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
            name="constructs",
            display_title=MESSAGES.ci.constructs,
            cmd=["uv", "run", "ast-grep", *CONST_AST_GREP_SCAN_ARGS],
            span_name="ci.step.constructs",
            metric_step="constructs",
        ),
        CheckSpec(
            name="devcontainer",
            display_title=MESSAGES.ci.devcontainer_validation,
            cmd=["uv", "run", "devops", "devcontainer", "validate", "--workspace", "."],
            span_name="ci.step.devcontainer",
            metric_step="devcontainer",
        ),
        CheckSpec(
            name="openspec",
            display_title=MESSAGES.ci.openspec_validation,
            cmd=["uv", "run", "devops", "openspec", "check"],
            span_name="ci.step.openspec",
            metric_step="openspec",
        ),
        CheckSpec(
            name="git",
            display_title=MESSAGES.ci.git_transcripts,
            cmd=["uv", "run", "python", "-c", _GIT_TRANSCRIPTS_SCRIPT],
            span_name="ci.step.git",
            metric_step="git",
        ),
        CheckSpec(
            name="test-settings",
            display_title=MESSAGES.ci.test_settings,
            cmd=["uv", "run", "python", "-c", _TEST_SETTINGS_SCRIPT],
            span_name="ci.step.test_settings",
            metric_step="test_settings",
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
        write_stderr(f"Cannot combine --only and --skip options. Valid check names: {valid_list}\n")
        raise typer.Exit(2)

    if only_names:
        invalid = [n for n in only_names if n not in valid_names]
        if invalid:
            valid_list = ", ".join(valid_names)
            invalid_list = ", ".join(repr(n) for n in invalid)
            write_stderr(
                f"Invalid check name(s): {invalid_list}. Valid check names: {valid_list}\n"
            )
            raise typer.Exit(2)
        return [s for s in all_specs if s.name in only_names]

    if skip_names:
        invalid = [n for n in skip_names if n not in valid_names]
        if invalid:
            valid_list = ", ".join(valid_names)
            invalid_list = ", ".join(repr(n) for n in invalid)
            write_stderr(
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
    _count_check("python_version", passed=py_ok)
    py_result = CheckResult(
        name="python_version",
        display_title=MESSAGES.ci.python_version_check,
        passed=py_ok,
        duration_seconds=py_dur,
    )
    from devops_cli.output import format_duration

    py_badge = "[green]✓ pass[/green]" if py_ok else "[bold red]✗ fail[/bold red]"
    print_muted(
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
    check_requests = [request for s in selected_specs for request in _planned_requests(s)]
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
            requests=_planned_requests(spec),
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
        print_muted(f"  ⏳ [test] {MESSAGES.ci.pytest_coverage} running in background...")
        sys.stdout.flush()

    capture_output = len(selected_specs) != 1

    with trace_span(
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
            _write_process_output(res.stdout, res.stderr)


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

    print_table(
        title=MESSAGES.ci.ci_summary_title,
        columns=[(MESSAGES.ci.col_check, "cyan"), MESSAGES.ci.col_result, ("Duration", "dim")],
        rows=rows,
    )
    mode_text = "cached execution" if cached else "concurrent async execution"
    print_muted(f"Total Elapsed: {format_duration(total_elapsed)} ({mode_text})\n")


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
        print_warning(MESSAGES.ci.cache_tree_changed, safe=True)
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
    print_info(MESSAGES.ci.cache_hit)
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

    print_warning(
        MESSAGES.ci.test_budget_exceeded.format(
            duration=format_duration(test_result.duration_seconds),
            budget=format_duration(CONST_CI_TEST_BUDGET_SECONDS),
        ),
        safe=True,
    )
    if test_result.stdout:
        for entry in slowest_tests(test_result.stdout):
            print_muted(f"  {entry}")


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
@dry_run_class("request-plan")
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

    with _gate_slot(any(spec.heavy for spec in selected_specs)):
        start_time = clock.monotonic()
        if not is_dry_run():
            print_info("Executing CI quality gates concurrently...")
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
        _print_summary(results, total_elapsed=clock.monotonic() - start_time)
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
    return p.as_posix()


def _check_trigger_files(all_paths: set[str], fallback: bool, imports: SuiteImports) -> bool:
    """Check if any trigger files are in the changed path set."""
    from devops_cli.core.test_selection import forces_full_run

    first_trigger = next((p for p in sorted(all_paths) if forces_full_run(p, imports)), None)
    if first_trigger is None:
        return True
    if not fallback:
        print_error(
            MESSAGES.ci.selection_trigger_refusal.format(file=first_trigger),
            prefix=False,
        )
        raise typer.Exit(1)
    print_warning(MESSAGES.ci.selection_trigger_full_run.format(file=first_trigger))
    return False


def _directory_modules(directory: str, root: Path) -> list[str]:
    """The files a directory argument stands for, as sorted repo-relative paths: the test modules
    inside a directory of tests/, and the Python modules inside a directory of src/, at any depth.
    None for a directory elsewhere, and for one that holds no such file (#2868)."""
    from devops_cli.config.constants import (
        CONST_PYTHON_FILE_SUFFIX,
        CONST_SOURCE_ROOT_DIR,
        CONST_TESTS_ROOT_DIR,
    )
    from devops_cli.core.test_selection import is_test_module

    tree = next(iter(Path(os.path.normpath(directory)).parts), "")
    if tree not in (CONST_SOURCE_ROOT_DIR, CONST_TESTS_ROOT_DIR):
        return []
    found = (root / directory).rglob(f"*{CONST_PYTHON_FILE_SUFFIX}")
    return sorted(
        file.relative_to(root).as_posix()
        for file in found
        if file.is_file() and (tree == CONST_SOURCE_ROOT_DIR or is_test_module(file))
    )


def _expand_directories(paths: set[str], root: Path, imports: SuiteImports) -> set[str]:
    """The paths with each directory replaced by the files it stands for. A path that does not
    exist, and a directory that gives no file, are refused with an error that names them: running
    no test must not be a pass. A trigger file that is gone, such as a deleted conftest.py, still
    forces the full run (#2868)."""
    from devops_cli.core.test_selection import forces_full_run

    expanded: set[str] = set()
    for path in paths:
        if not (root / path).exists():
            if not forces_full_run(path, imports):
                print_error(MESSAGES.ci.path_not_found.format(path=path), prefix=False, safe=True)
                raise typer.Exit(1)
            expanded.add(path)
        elif not (root / path).is_dir():
            expanded.add(path)
        else:
            modules = _directory_modules(path, root)
            if not modules:
                print_error(
                    MESSAGES.ci.directory_without_tests.format(directory=path),
                    prefix=False,
                    safe=True,
                )
                raise typer.Exit(1)
            expanded.update(modules)
    return expanded


def _map_test_tree_path(
    path: str,
    root: Path,
    imports: SuiteImports,
    selected_tests: set[str],
    mapped_sources: dict[str, list[str]],
    unmapped_sources: list[str],
    source_selectors: dict[str, str],
) -> None:
    """Handle a path under the tests/ directory: a test module runs itself, and a helper module
    the test modules that import it, directly or through other modules (#1312)."""
    from devops_cli.config.constants import CONST_PYTHON_FILE_SUFFIX
    from devops_cli.core.test_selection import is_test_module

    if is_test_module(path):
        if (root / path).is_file():
            selected_tests.add(path)
            mapped_sources[path] = [path]
            source_selectors[path] = "direct"
        return

    if not (root / path).is_file():
        return

    if path.endswith(CONST_PYTHON_FILE_SUFFIX):
        importing = [str(test) for test in imports.importing_tests(Path(path))]
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
    imports: SuiteImports,
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
                path,
                root,
                imports,
                selected_tests,
                mapped_sources,
                unmapped_sources,
                source_selectors,
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
        print_muted(f"  {source} → {', '.join(tests)}{selector_suffix}")
    if unmapped_sources:
        print_warning(
            MESSAGES.ci.no_covering_tests.format(files=", ".join(sorted(unmapped_sources)))
        )


def _index_drift(index: Any, root: Path, imports: SuiteImports) -> tuple[list[str], bool, set[str]]:
    """The files changed since the coverage index was built; whether the index still maps them:
    not when one of them forces a full run, since that file can change what any test covers, and
    the text selector chooses until the index is rebuilt; and the helper modules under tests/
    among them that are gone, deleted or renamed away, which force the full run themselves
    (#1312)."""
    from devops_cli.ci.cache import compute_worktree_blob_hashes
    from devops_cli.core.coverage_index import compute_index_drift
    from devops_cli.core.test_selection import forces_full_run
    from devops_cli.output import format_duration

    drift_files = compute_index_drift(index, compute_worktree_blob_hashes(root))
    age_seconds = max(0.0, time.time() - index.built_at) if index.built_at > 0 else 0.0
    age_str = format_duration(age_seconds) if age_seconds > 0 else "0s"
    print_muted(MESSAGES.ci.coverage_index_age.format(age=age_str, changed_count=len(drift_files)))
    removed = {path for path in drift_files if imports.is_removed_helper(Path(path))}
    if removed:
        print_warning(MESSAGES.ci.coverage_index_helper_removed.format(file=min(removed)))
        return drift_files, False, removed
    stale = next((path for path in drift_files if forces_full_run(path, imports)), None)
    if stale is None:
        return drift_files, True, set()
    print_warning(MESSAGES.ci.coverage_index_stale.format(file=stale))
    return drift_files, False, set()


def _drift_selection(
    index: Any, root: Path, imports: SuiteImports
) -> tuple[set[str], bool, set[str]]:
    """The files changed since the coverage index was built to select beside the given ones,
    none when the index is absent or stale; whether the index maps sources; and the helper
    modules under tests/ among those files that are gone, deleted or renamed away (#1312)."""
    if index.is_empty:
        print_muted(MESSAGES.ci.coverage_index_missing)
        return set(), False, set()
    drift_files, usable, removed = _index_drift(index, root, imports)
    return (set(drift_files) if usable else set()), usable, removed


def _resolve_test_targets(paths: list[Path], fallback: bool) -> list[str] | None:
    """Map changed files onto pytest targets using coverage index and text fallback. Only a
    trigger among the given files forces a full run; one that changed since the index was built
    makes the index stale, and the text selector maps the given files instead. A helper module
    under tests/ that is gone since then forces a full run too, since what it registered and
    which tests imported it can no longer be read (#1312)."""
    from devops_cli.ci.cache import resolve_coverage_index_path
    from devops_cli.core.coverage_index import load_index
    from devops_cli.core.test_selection import SuiteImports

    root = _get_project_root()
    index = load_index(resolve_coverage_index_path(root))
    imports = SuiteImports(root)
    user_paths = _expand_directories(
        {_normalize_repo_rel_path(p, root) for p in paths}, root, imports
    )
    drift, has_index, removed = _drift_selection(index, root, imports)
    all_paths = user_paths | drift

    if not _check_trigger_files(user_paths | removed, fallback, imports):
        return None

    targets, mapped_sources, unmapped_sources, source_selectors = _map_changed_paths(
        all_paths, root, index, has_index, imports
    )
    _report_selection(mapped_sources, unmapped_sources, source_selectors)

    if targets:
        return targets

    if not unmapped_sources and not mapped_sources:
        print_muted(MESSAGES.ci.no_testable_files)
        return []

    if fallback:
        print_warning(MESSAGES.ci.selection_fallback)
        return None

    print_error(MESSAGES.ci.selection_empty, prefix=False)
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


def _narrowed_workers(targets: list[str] | None) -> str | None:
    """The `-n` of a run given none (#1669): none for the full suite, so addopts' `-n logical`
    applies; serial for a selection of up to DEFAULT_CI_TEST_SERIAL_MAX_FILES test modules,
    where each xdist worker's start-up and collection cost more than it saves; and
    DEFAULT_CI_TEST_NARROWED_WORKERS workers above that."""
    if targets is None:
        return None
    if len(targets) <= DEFAULT_CI_TEST_SERIAL_MAX_FILES:
        return "0"
    return str(DEFAULT_CI_TEST_NARROWED_WORKERS)


def _head_seed(root: Path) -> int:
    """A shuffle seed derived from HEAD: its commit hash's leading eight hex digits."""
    result = _current_run_subprocess()(["git", "rev-parse", "HEAD"], cwd=root, quiet=True)
    if result.returncode != 0:
        print_error(MESSAGES.ci.repeat_seed_unavailable, prefix=False)
        raise typer.Exit(1)
    return int(result.stdout[:8], 16)


def _run_shuffled_repeats(
    base_cmd: list[str], targets: list[str] | None, runs: int, seed: int | None
) -> None:
    """Run the targets `runs` times, one run after another, shuffled by pytest-randomly with
    seeds `seed` to `seed + runs - 1`, stopping at the first failure with its seed and command.
    """
    if targets is None:
        print_error(MESSAGES.ci.repeat_needs_targets, prefix=False)
        raise typer.Exit(1)
    first = _head_seed(_get_project_root()) if seed is None else seed
    for run, run_seed in enumerate(range(first, first + runs), start=1):
        cmd = [*base_cmd, "-p", "randomly", f"--randomly-seed={run_seed}", *targets]
        if not _run(cmd, own_session=True):
            failed = MESSAGES.ci.repeat_failed.format(
                run=run, runs=runs, seed=run_seed, command=shlex.join(cmd)
            )
            print_error(failed, prefix=False, safe=True)
            raise typer.Exit(1)


@app.command()
@dry_run_class("request-plan")
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
        print_error("Invalid keyword filter expression.", prefix=False)
        raise typer.Exit(1)

    if repeat:
        _run_shuffled_repeats(_build_test_cmd("0", verbose, k, x, None), targets, repeat, seed)
        return

    workers = numprocesses if numprocesses is not None else _narrowed_workers(targets)
    cmd = _build_test_cmd(workers, verbose, k, x, targets)
    with _gate_slot(workers is None):
        passed = _run(cmd, own_session=True)
    if not passed:
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
        print_error(
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
    print_info(
        MESSAGES.ci.coverage_index_saved.format(duration=f"{elapsed:.2f}s"),
        safe=True,
    )


@app.command()
@dry_run_class("request-plan")
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
    with _gate_slot(True):
        if build_index:
            _handle_coverage_index_build(cmd)
            return
        passed = _run(cmd)
    if not passed:
        raise typer.Exit(1)


@app.command()
@dry_run_class("request-plan")
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
@dry_run_class("request-plan")
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
@dry_run_class("request-plan")
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
@dry_run_class("request-plan")
def audit(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Run uv audit and npm audit to check for known package vulnerabilities."""
    if dry_run:
        set_dry_run(True)
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    if not _run_audits():
        raise typer.Exit(1)


@app.command()
@dry_run_class("request-plan")
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
    """Run bandit static security analysis over src/ at low severity and over tests/ at --severity."""
    if dry_run:
        set_dry_run(True)
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    passed = [_run(cmd) for cmd in _bandit_cmds(severity)]
    if not all(passed):
        raise typer.Exit(1)


@app.command()
@dry_run_class("request-plan")
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
    if not dry_run and shutil.which("actionlint") is None:
        print_error(
            "actionlint is not on PATH. The devcontainer image provides it. "
            "For other hosts, install it from https://github.com/kjanat/actionlint "
            "or the actionlint install page."
        )
        raise typer.Exit(1)
    spec = get_check_spec("actionlint")
    if not _run(spec.cmd):
        raise typer.Exit(1)


@app.command()
@dry_run_class("request-plan")
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
@dry_run_class("request-plan")
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
@dry_run_class("request-plan")
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
@dry_run_class("request-plan")
def build(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Build the wheel and the sdist via uv build."""
    if dry_run:
        set_dry_run(True)
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    spec = get_check_spec("build")
    if not _run(spec.cmd):
        raise typer.Exit(1)


@app.command()
@dry_run_class("request-plan")
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
@dry_run_class("request-plan")
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
@dry_run_class("request-plan")
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


@app.command(name="test-settings")
@dry_run_class("request-plan")
def test_settings(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Verify test configuration settings and environment variables."""
    if dry_run:
        set_dry_run(True)
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    spec = get_check_spec("test-settings")
    if not _run(spec.cmd):
        raise typer.Exit(1)


@app.command()
@dry_run_class("request-plan")
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

    # 2. Dependency security audit, by the `audit` check's own commands
    if not _run_audits():
        raise typer.Exit(1)

    print_success("Toolchain and lockfile maintenance checks passed.")


@app.command()
@dry_run_class("request-plan")
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


_MUTMUT = ["uv", "run", "mutmut"]
_MUTMUT_RESULTS = [*_MUTMUT, "results", "--all", "true"]


def _capture(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a command in the checked tree as `_run` would, returning its captured output."""
    argv = list(_planned_request_for_cmd(cmd).argv)
    completed: subprocess.CompletedProcess[str] = _current_run_subprocess()(
        argv, cwd=_get_project_root(), capture_output=True
    )
    return completed


def _plan_mutation(run_cmd: list[str]) -> None:
    """The dry run's requests: the mutmut run, its results, and a show for each survivor."""
    requests = [
        _planned_request_for_cmd(run_cmd),
        _planned_request_for_cmd(_MUTMUT_RESULTS),
        _planned_request_for_cmd([*_MUTMUT, "show", "<mutant>"], repeat="each surviving mutant"),
    ]
    render_request_plan(MESSAGES.ci.ci_dry_run_heading, requests)


def _report_mutation(results_text: str, targets: Sequence[MutationTarget]) -> None:
    """Show each surviving mutant of the targets with its diff, then the status counts."""
    from devops_cli.ci.mutate import tally

    report = tally(results_text, targets)
    for mutant, target in report.survivors:
        location = MESSAGES.ci.mutate_survivor.format(
            path=target.path, line=target.line, qualname=target.qualname
        )
        print_warning(location, prefix=False, safe=True)
        write_stdout(_capture([*_MUTMUT, "show", mutant]).stdout)
    counts = ", ".join(f"{status} {count}" for status, count in report.counts.items())
    print_info(MESSAGES.ci.mutate_counts.format(counts=counts), prefix=False, safe=True)


@app.command(help=HELP.ci.mutate)
@dry_run_class("request-plan")
def mutate(
    paths: Annotated[list[Path] | None, typer.Argument(help=HELP.ci.mutate_paths)] = None,
    changed: Annotated[bool, typer.Option("--changed", help=HELP.ci.mutate_changed)] = False,
    base: Annotated[
        str, typer.Option("--base", "-b", help=HELP.options.base_branch)
    ] = CONST_GIT_MAIN_BRANCH,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Mutation-test the selected functions with mutmut and show what survives (#853)."""
    if not (paths or changed):
        print_error(MESSAGES.ci.mutate_needs_target, prefix=False)
        raise typer.Exit(2)
    if dry_run:
        set_dry_run(True)
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    from devops_cli.ci.mutate import select_targets

    targets = select_targets(_get_project_root(), paths or [], changed=changed, base=base)
    if not targets:
        print_muted(MESSAGES.ci.mutate_nothing)
        return
    run_cmd = [*_MUTMUT, "run", *(glob for target in targets for glob in target.run_globs)]
    if is_dry_run():
        _plan_mutation(run_cmd)
        return
    if not _run(run_cmd, timeout=DEFAULT_CI_MUTATE_TIMEOUT_SECONDS):
        raise typer.Exit(1)
    results = _capture(_MUTMUT_RESULTS)
    if results.returncode != 0:
        write_stderr(results.stderr)
        raise typer.Exit(1)
    _report_mutation(results.stdout, targets)


def _append_step_summary(text: str) -> None:
    """Append `text` to `$GITHUB_STEP_SUMMARY` when running in GitHub Actions."""
    if (summary_env := os.environ.get("GITHUB_STEP_SUMMARY")) and (
        summary_path := Path(summary_env)
    ).parent.is_dir():
        with summary_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{text}\n")


@app.command(name="job-time", help=HELP.ci.job_time)
@dry_run_class("request-plan")
def job_time(
    repo: Annotated[str | None, typer.Option("--repo", "-R", help=HELP.ci.job_time_repo)] = None,
    job: Annotated[str, typer.Option("--job", help=HELP.ci.job_time_job)] = CONST_CI_TEST_JOB_NAME,
    workflow: Annotated[
        str, typer.Option("--workflow", help=HELP.ci.job_time_workflow)
    ] = CONST_CI_WORKFLOW_FILE,
    branch: Annotated[
        str, typer.Option("--branch", "-b", help=HELP.ci.job_time_branch)
    ] = CONST_GIT_MAIN_BRANCH,
    runs: Annotated[
        int, typer.Option("--runs", min=1, help=HELP.ci.job_time_runs)
    ] = DEFAULT_CI_JOB_TIME_RUNS,
    limit: Annotated[
        float, typer.Option("--limit", min=1, help=HELP.ci.job_time_limit)
    ] = CONST_CI_TEST_BUDGET_SECONDS,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Fail when the last runs of a CI job averaged more than the limit (#2699)."""
    from devops_cli.core.repo import find_repo_root, get_repo_origin_name

    target = repo or get_repo_origin_name(find_repo_root(Path.cwd()))
    if target is None:
        print_error(MESSAGES.ci.job_time_no_repo)
        raise typer.Exit(1)
    if dry_run or is_dry_run():
        _render_job_time_plan(target, workflow=workflow, branch=branch, job=job, runs=runs)
        return
    from devops_cli.ci.job_time import check_job_time
    from devops_cli.github.session import get_github_session

    report = check_job_time(
        get_github_session().client,
        target,
        workflow=workflow,
        branch=branch,
        job=job,
        wanted=runs,
        limit_seconds=limit,
    )
    _print_job_time_report(report, workflow=workflow, branch=branch)
    if not report.passes:
        raise typer.Exit(1)


def _render_job_time_plan(repo: str, *, workflow: str, branch: str, job: str, runs: int) -> None:
    """List the requests of `job-time` without making them (#412)."""
    base = f"/repos/{repo}/actions"
    render_request_plan(
        MESSAGES.ci.job_time_dry_run_heading.format(job=job, workflow=workflow, branch=branch),
        [
            PlannedRequest(method="GET", target=f"{base}/workflows/{workflow}/runs"),
            PlannedRequest(
                method="GET",
                target=f"{base}/runs/<run_id>/jobs",
                repeat=f"for each run, until {runs} runs hold an ended {job}",
            ),
        ],
    )


def _print_job_time_report(report: JobTimeReport, *, workflow: str, branch: str) -> None:
    """Show the seconds of each run read, then say whether the mean is inside the limit."""
    print_table(
        title=MESSAGES.ci.job_time_title.format(job=report.job, workflow=workflow, branch=branch),
        columns=["Run ID", "Seconds"],
        rows=[[str(run.run_id), f"{run.seconds:.0f}"] for run in report.runs],
    )
    if not report.complete:
        print_error(
            MESSAGES.ci.job_time_short.format(
                found=len(report.runs),
                wanted=report.wanted,
                job=report.job,
                workflow=workflow,
                branch=branch,
            )
        )
        return
    figures = {
        "count": report.wanted,
        "job": report.job,
        "mean": report.mean_seconds,
        "limit": report.limit_seconds,
    }
    if report.passes:
        print_success(MESSAGES.ci.job_time_ok.format(**figures))
    else:
        print_error(MESSAGES.ci.job_time_over.format(**figures))


@app.command(name="fail-to-pass", help=HELP.ci.fail_to_pass)
def fail_to_pass(
    base: Annotated[
        str, typer.Option("--base", "-b", help=HELP.options.base_branch)
    ] = CONST_GIT_MAIN_BRANCH,
    head: Annotated[str, typer.Option("--head", help=HELP.ci.fail_to_pass_head)] = "HEAD",
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Replay changed tests against the merge-base tree to prove a fix's tests fail on base (#844)."""
    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops ci fail-to-pass",
            action="replay_tests_on_base",
            details={"base": base, "head": head},
        )
        return
    if not _verify_python_314_environment():
        raise typer.Exit(1)
    from devops_cli.ci.fail_to_pass import format_fail_to_pass_report, run_fail_to_pass

    report = run_fail_to_pass(_get_project_root(), base=base, head=head)
    output = format_fail_to_pass_report(report)
    _append_step_summary(output)
    if not report.satisfied:
        # Written raw: pytest's output in the report is neither markup nor emoji codes (#1669).
        write_stderr(f"{output}\n")
        raise typer.Exit(1)
    print_info(output, prefix=False, safe=True)
