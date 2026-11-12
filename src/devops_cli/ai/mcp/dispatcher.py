"""FastMCP in-process command dispatcher and resource subscriptions."""

from __future__ import annotations

import logging
import os
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, Protocol

from devops_cli.config.constants import CONST_MCP_DISPATCH_THREAD_NAME
from devops_cli.config.defaults import (
    DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
)
from devops_cli.dry_run.state import (
    in_dry_run_invocation,
    is_dry_run_requested,
    mark_dry_run_invocation,
)
from devops_cli.exceptions import ValidationError
from devops_cli.lang import ERRORS

logger = logging.getLogger(__name__)


# Nothing derived from a dispatched command reaches a log record here. This dispatcher
# runs arbitrary `devops` command lines and some carry a credential as an argument --
# `gh secret set NAME VALUE`, a token passed as a flag -- so logging the argument list
# wrote that credential out in clear text. CodeQL reported it as three high-severity
# `py/clear-text-logging-sensitive-data` alerts, and they blocked the v0.2.22 release.
#
# Masking the values first did not resolve it and made it worse: the sanitizer is not a
# barrier CodeQL recognises, so each masked argument became another flagged expression and
# three alerts became six. An exception's class and a duration carry the diagnostic weight
# -- which site failed, what kind of failure, how long it took -- without carrying data
# that came from the caller.


# ── Resource Subscriptions ───────────────────────────────────────────────────


class ResourceSubscriptionManager:
    """Observer pattern manager for dynamic MCP resource subscriptions (resource://)."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[Callable[[str, str], None]]] = {}
        self._lock = threading.Lock()

    def subscribe(self, resource_uri: str, listener: Callable[[str, str], None]) -> None:
        """Add a subscriber callback for a specific resource URI."""
        with self._lock:
            if resource_uri not in self._subscribers:
                self._subscribers[resource_uri] = set()
            self._subscribers[resource_uri].add(listener)

    def notify(self, resource_uri: str, content: str) -> int:
        """Publish updated content to all active subscribers for the URI."""
        with self._lock:
            listeners = list(self._subscribers.get(resource_uri, []))

        notified = 0
        for listener in listeners:
            try:
                listener(resource_uri, content)
                notified += 1
            except Exception as exc:
                logger.error("Error notifying subscriber: %s", type(exc).__name__)
        return notified


# ── In-Process Command Dispatcher ─────────────────────────────────────────────


def devops_sub_args(cmd: list[str]) -> list[str]:
    """Return the arguments after `devops` in `cmd` (`uv run devops ...` or `devops ...`).

    The dispatcher runs only the `devops` command line. Any other program is refused and
    nothing starts.
    """
    if len(cmd) >= 3 and cmd[0] == "uv" and cmd[1] == "run" and cmd[2] == "devops":
        return cmd[3:]
    if len(cmd) >= 1 and cmd[0] == "devops":
        return cmd[1:]
    raise ValidationError(
        ERRORS.mcp.not_a_devops_command.format(program=cmd[0] if cmd else ""),
        field="cmd",
    )


_DRY_RUN_LOCK = threading.Lock()
_dry_runs = 0
_invocation_before = False


@contextmanager
def _dry_run_invocation(sub_args: list[str]) -> Iterator[None]:
    """While a dispatched command with its own `--dry-run` runs, the process is a dry run, so
    the command's telemetry is not exported either (#412). The entry point marks this for a
    command line; an in-process dispatch does not pass through it. Other commands dispatched
    meanwhile export nothing until the last dry run ends."""
    global _dry_runs, _invocation_before
    if not is_dry_run_requested(sub_args):
        yield
        return
    with _DRY_RUN_LOCK:
        if not _dry_runs:
            _invocation_before = in_dry_run_invocation()
        _dry_runs += 1
        mark_dry_run_invocation(True)
    try:
        yield
    finally:
        with _DRY_RUN_LOCK:
            _dry_runs -= 1
            if not _dry_runs:
                mark_dry_run_invocation(_invocation_before)


@contextmanager
def _isolate_child_stdio() -> Iterator[tuple[Any, Any]]:
    """Redirect OS file descriptors 1 and 2 to temporary files during in-process execution.

    Under stdio transport, fd 1 is the JSON-RPC channel. Any child process spawned by
    commands with `capture_output=False` or standard descriptor inheritance would otherwise
    write raw terminal output directly to fd 1, corrupting the JSON-RPC protocol stream.
    """
    try:
        sys.stdout.flush()
        sys.stderr.flush()
        saved_stdout = os.dup(1)
        saved_stderr = os.dup(2)
    except OSError:
        yield None, None
        return

    with (
        tempfile.TemporaryFile("w+b") as out_f,
        tempfile.TemporaryFile("w+b") as err_f,
    ):
        os.dup2(out_f.fileno(), 1)
        os.dup2(err_f.fileno(), 2)
        try:
            yield out_f, err_f
        finally:
            try:
                sys.stdout.flush()
                sys.stderr.flush()
            except Exception:
                pass
            try:
                os.dup2(saved_stdout, 1)
                os.close(saved_stdout)
            except OSError:
                pass
            try:
                os.dup2(saved_stderr, 2)
                os.close(saved_stderr)
            except OSError:
                pass


def _read_stream(f: Any) -> str:
    """Read and decode all bytes from a temporary file stream."""
    if f is None:
        return ""
    try:
        f.seek(0)
        content: Any = f.read()
        if isinstance(content, bytes):
            return content.decode("utf-8", errors="replace").strip()
        return str(content).strip()
    except Exception:
        return ""


def _combine_output_parts(*parts: str) -> str:
    """Combine distinct non-empty output strings maintaining order."""
    combined: list[str] = []
    for part in parts:
        cleaned = part.strip()
        if cleaned and cleaned not in combined:
            combined.append(cleaned)
    return "\n".join(combined).strip()


def _invoke_on_thread(
    runner: Any, app: Any, sub_args: list[str], env: dict[str, str] | None, timeout: float
) -> tuple[Any, BaseException | None, bool]:
    """Invoke the CLI app on a daemon thread and wait at most `timeout` seconds for it.

    Return the result, the error the invocation raised, and whether the thread still runs.
    """
    res: Any = None
    worker_exc: BaseException | None = None

    def _worker() -> None:
        # A context variable does not pass to a new thread, so the thread marks its own call.
        from devops_cli.core.caller import mcp_call

        nonlocal res, worker_exc
        try:
            with mcp_call():
                res = runner.invoke(app, sub_args, env=env)
        except (
            RuntimeError,
            ValueError,
            OSError,
            SystemExit,
            KeyError,
            TypeError,
            AttributeError,
            TimeoutError,
        ) as exc:
            worker_exc = exc

    t = threading.Thread(target=_worker, name=CONST_MCP_DISPATCH_THREAD_NAME, daemon=True)
    t.start()
    t.join(timeout=timeout)
    return res, worker_exc, t.is_alive()


class McpDispatcher(Protocol):
    """The seam between an MCP tool and the CLI: one `devops` argv in, an exit code and text out.

    `InProcessDispatcher` is the real one. A test installs a fake with `install_mcp_dispatcher`.
    """

    @property
    def subscriptions(self) -> ResourceSubscriptionManager:
        """The subscribers of the `resource://` URIs that a tool refreshes."""
        ...

    def dispatch(
        self,
        cmd: list[str],
        timeout: float = DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        env: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        """Run the `devops` command line `cmd` and return its exit code and its output."""
        ...


class InProcessDispatcher:
    """Direct in-process execution engine for devops-cli tools eliminating subshell spawning."""

    def __init__(self) -> None:
        self._subscriptions = ResourceSubscriptionManager()
        self._lock = threading.Lock()

    @property
    def subscriptions(self) -> ResourceSubscriptionManager:
        return self._subscriptions

    def dispatch(
        self,
        cmd: list[str],
        timeout: float = DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        env: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        """Run a `devops` command in-process. Any other program raises `ValidationError`."""
        sub_args = devops_sub_args(cmd)
        return self._dispatch_typer(sub_args, env=env, timeout=timeout, cmd=cmd)

    def _dispatch_typer(
        self,
        sub_args: list[str],
        env: dict[str, str] | None = None,
        timeout: float = DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        cmd: list[str] | None = None,
    ) -> tuple[int, str]:
        """Execute command in-process via Typer CliRunner while isolating child stdout."""
        from typer.testing import CliRunner

        from devops_cli.main import app

        with self._lock:
            runner = CliRunner()
            saved_sys_stdout = sys.stdout
            saved_sys_stderr = sys.stderr
            saved_sys_stdin = sys.stdin
            try:
                start_t = time.perf_counter()

                with _isolate_child_stdio() as (out_f, err_f), _dry_run_invocation(sub_args):
                    res, worker_exc, timed_out = _invoke_on_thread(
                        runner, app, sub_args, env, timeout
                    )
                    if timed_out:
                        sys.stdout = saved_sys_stdout
                        sys.stderr = saved_sys_stderr
                        sys.stdin = saved_sys_stdin
                        logger.warning("In-process dispatch timed out after %.2fs", timeout)
                        target = " ".join(cmd) if cmd else f"devops {' '.join(sub_args)}"
                        return 124, f"Command timed out after {timeout} seconds: {target}"

                    child_out = _read_stream(out_f)
                    child_err = _read_stream(err_f)

                if worker_exc is not None:
                    raise worker_exc

                dur_ms = (time.perf_counter() - start_t) * 1000
                logger.debug("In-process dispatch finished in %.2fms", dur_ms)

                res_exit = res.exit_code if res is not None else 1
                res_output = res.output if res is not None else ""
                res_stderr = res.stderr if res is not None else ""

                out = _combine_output_parts(
                    res_output or "",
                    child_out,
                    res_stderr or "",
                    child_err,
                )
                fallback = "Success" if res_exit == 0 else "no output captured"
                return res_exit, out or fallback
            except Exception as exc:
                logger.debug("In-process dispatch failed: %s", type(exc).__name__)
                return 1, f"In-process execution error: {type(exc).__name__}"


# ── Global Dispatcher Singleton ───────────────────────────────────────────────

_DISPATCHER_INSTANCE: McpDispatcher | None = None
_DISPATCHER_LOCK = threading.Lock()


def get_mcp_dispatcher() -> McpDispatcher:
    """Return the installed dispatcher, else the global InProcessDispatcher singleton."""
    global _DISPATCHER_INSTANCE
    with _DISPATCHER_LOCK:
        if _DISPATCHER_INSTANCE is None:
            _DISPATCHER_INSTANCE = InProcessDispatcher()
        return _DISPATCHER_INSTANCE


def install_mcp_dispatcher(dispatcher: McpDispatcher) -> None:
    """Make `dispatcher` the one that every MCP tool uses, until `reset_mcp_dispatcher`."""
    global _DISPATCHER_INSTANCE
    with _DISPATCHER_LOCK:
        _DISPATCHER_INSTANCE = dispatcher


def reset_mcp_dispatcher() -> None:
    """Remove the installed dispatcher and the singleton, and reset the dry-run invocation counters."""
    global _DISPATCHER_INSTANCE, _dry_runs, _invocation_before
    with _DISPATCHER_LOCK:
        _DISPATCHER_INSTANCE = None
    with _DRY_RUN_LOCK:
        _dry_runs = 0
        _invocation_before = False
