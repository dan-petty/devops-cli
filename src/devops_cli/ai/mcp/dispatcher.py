"""FastMCP in-process command dispatcher, lazy domain schema hydrator, and resource subscriptions."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from devops_cli.config.constants import CONST_MCP_DISPATCH_THREAD_NAME, CONST_MCP_DOMAINS
from devops_cli.config.defaults import (
    DEFAULT_MCP_SCHEMA_CACHE_MAX_ENTRIES,
    DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
)
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.state import (
    in_dry_run_invocation,
    is_dry_run_requested,
    mark_dry_run_invocation,
)

logger = logging.getLogger(__name__)


# Nothing derived from a dispatched command reaches a log record here. This dispatcher
# runs arbitrary `devops` command lines and some carry a credential as an argument --
# `gh secrets set NAME VALUE`, a token passed as a flag -- so logging the argument list
# wrote that credential out in clear text. CodeQL reported it as three high-severity
# `py/clear-text-logging-sensitive-data` alerts, and they blocked the v0.2.22 release.
#
# Masking the values first did not resolve it and made it worse: the sanitizer is not a
# barrier CodeQL recognises, so each masked argument became another flagged expression and
# three alerts became six. An exception's class and a duration carry the diagnostic weight
# -- which site failed, what kind of failure, how long it took -- without carrying data
# that came from the caller.


# ── Domain Schema Hydration ───────────────────────────────────────────────────


_PREFIX_TO_DOMAIN: dict[str, str] = {
    "review": "review",
    "k8s": "k8s",
    "argo": "argo",
    "ci": "ci",
    "docker": "docker",
    "docs": "docs",
    "gh": "github",
    "pr": "github",
    "branches": "github",
    "repos": "github",
    "ssh": "ssh",
    "tf": "tf",
    "vault": "secrets",
    "tls": "secrets",
    "telemetry": "telemetry",
    "grafana": "telemetry",
    "prometheus": "telemetry",
    "config": "config",
    "valkey": "valkey",
    "ai": "ai",
    "rag": "ai",
    "benchmark": "benchmarks",
    "scan": "security",
    "security": "security",
    "sandbox": "security",
    "workspace": "workspace",
    "roadmap": "roadmap",
}


def resolve_tool_domain(tool_name: str) -> str:
    """Classify an MCP tool name into its functional domain using deterministic prefix matching."""
    prefix = tool_name.split("_", 1)[0]
    domain = _PREFIX_TO_DOMAIN.get(prefix, "workspace")
    return domain if domain in CONST_MCP_DOMAINS else "workspace"


class DomainSchemaHydrator:
    """Lazy domain-gated tool schema hydration and caching."""

    def __init__(self, max_cache_entries: int = DEFAULT_MCP_SCHEMA_CACHE_MAX_ENTRIES) -> None:
        self._cache: dict[str, dict[str, Any]] = {}
        self._max_cache_entries = max_cache_entries
        self._lock = threading.Lock()

    def get_cached_schema(self, tool_name: str) -> dict[str, Any] | None:
        """Retrieve pre-hydrated tool schema from memory cache."""
        with self._lock:
            return self._cache.get(tool_name)

    def cache_schema(self, tool_name: str, schema: dict[str, Any]) -> None:
        """Cache hydrated tool schema enforcing maximum capacity."""
        with self._lock:
            if len(self._cache) >= self._max_cache_entries:
                first_key = next(iter(self._cache))
                self._cache.pop(first_key, None)
            self._cache[tool_name] = schema

    def clear(self) -> None:
        """Clear all cached schemas."""
        with self._lock:
            self._cache.clear()


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

    def unsubscribe(self, resource_uri: str, listener: Callable[[str, str], None]) -> None:
        """Remove a subscriber callback for a resource URI."""
        with self._lock:
            if resource_uri in self._subscribers:
                self._subscribers[resource_uri].discard(listener)
                if not self._subscribers[resource_uri]:
                    self._subscribers.pop(resource_uri, None)

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

    def subscriber_count(self, resource_uri: str) -> int:
        """Return the current subscriber count for a resource URI."""
        with self._lock:
            return len(self._subscribers.get(resource_uri, set()))

    def active_resources(self) -> list[str]:
        """List all resource URIs that currently have active subscribers."""
        with self._lock:
            return list(self._subscribers.keys())


# ── In-Process Command Dispatcher ─────────────────────────────────────────────


def _extract_devops_sub_args(cmd: list[str]) -> list[str] | None:
    """Extract sub-command arguments if cmd represents a devops CLI invocation."""
    if len(cmd) >= 3 and cmd[0] == "uv" and cmd[1] == "run" and cmd[2] == "devops":
        return cmd[3:]
    if len(cmd) >= 1 and cmd[0] == "devops":
        return cmd[1:]
    return None


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


class InProcessDispatcher:
    """Direct in-process execution engine for devops-cli tools eliminating subshell spawning."""

    def __init__(self) -> None:
        self._hydrator = DomainSchemaHydrator()
        self._subscriptions = ResourceSubscriptionManager()
        self._lock = threading.Lock()

    @property
    def hydrator(self) -> DomainSchemaHydrator:
        return self._hydrator

    @property
    def subscriptions(self) -> ResourceSubscriptionManager:
        return self._subscriptions

    def dispatch(
        self,
        cmd: list[str],
        timeout: float = DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        env: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        """Execute a command in-process when matching devops CLI or fallback to subprocess."""
        sub_args = _extract_devops_sub_args(cmd)
        if sub_args is None:
            code, out = self._dispatch_subprocess(cmd, timeout=timeout, env=env)
        else:
            code, out = self._dispatch_typer(sub_args, env=env, timeout=timeout, cmd=cmd)

        fallback = "Success" if code == 0 else "no output captured"
        return code, out or fallback

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
                res: Any = None
                worker_exc: BaseException | None = None

                with _isolate_child_stdio() as (out_f, err_f):
                    with _dry_run_invocation(sub_args):

                        def _worker() -> None:
                            nonlocal res, worker_exc
                            try:
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

                        t = threading.Thread(
                            target=_worker, name=CONST_MCP_DISPATCH_THREAD_NAME, daemon=True
                        )
                        t.start()
                        t.join(timeout=timeout)

                        if t.is_alive():
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

    def _dispatch_subprocess(
        self,
        cmd: list[str],
        timeout: float,
        env: dict[str, str] | None,
    ) -> tuple[int, str]:
        """Execute external command via subprocess."""
        try:
            proc = run_subprocess(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            out = (proc.stdout + ("\n" + proc.stderr if proc.stderr else "")).strip()
            fallback = "Success" if proc.returncode == 0 else "no output captured"
            return proc.returncode, out or fallback
        except subprocess.TimeoutExpired:
            return 124, f"Command timed out after {timeout} seconds: {' '.join(cmd)}"
        except Exception as exc:
            return 1, f"Execution failed: {exc}"


# ── Global Dispatcher Singleton ───────────────────────────────────────────────

_DISPATCHER_INSTANCE: InProcessDispatcher | None = None
_DISPATCHER_LOCK = threading.Lock()


def get_mcp_dispatcher() -> InProcessDispatcher:
    """Retrieve or initialize the global InProcessDispatcher singleton."""
    global _DISPATCHER_INSTANCE
    with _DISPATCHER_LOCK:
        if _DISPATCHER_INSTANCE is None:
            _DISPATCHER_INSTANCE = InProcessDispatcher()
        return _DISPATCHER_INSTANCE


def reset_mcp_dispatcher() -> None:
    """Reset the global InProcessDispatcher singleton and dry-run invocation counters."""
    global _DISPATCHER_INSTANCE, _dry_runs, _invocation_before
    with _DISPATCHER_LOCK:
        _DISPATCHER_INSTANCE = None
    with _DRY_RUN_LOCK:
        _dry_runs = 0
        _invocation_before = False
