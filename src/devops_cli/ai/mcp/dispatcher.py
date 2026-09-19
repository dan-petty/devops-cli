"""FastMCP in-process command dispatcher, lazy domain schema hydrator, and resource subscriptions."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from devops_cli.config.constants import CONST_MCP_DOMAINS
from devops_cli.config.defaults import (
    DEFAULT_MCP_SCHEMA_CACHE_MAX_ENTRIES,
    DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
)
from devops_cli.core.process import run_subprocess

logger = logging.getLogger(__name__)


# ── Domain Schema Hydration ───────────────────────────────────────────────────


_PREFIX_TO_DOMAIN: dict[str, str] = {
    "review": "review",
    "k8s": "k8s",
    "argo": "argo",
    "docker": "docker",
    "gh": "github",
    "pr": "github",
    "branches": "github",
    "repos": "github",
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
                logger.error("Error notifying subscriber for %s: %s", resource_uri, exc)
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


class InProcessDispatcher:
    """Direct in-process execution engine for devops-cli tools eliminating subshell spawning."""

    def __init__(self) -> None:
        self._functional_handlers: dict[tuple[str, ...], Callable[..., tuple[int, str]]] = {}
        self._hydrator = DomainSchemaHydrator()
        self._subscriptions = ResourceSubscriptionManager()
        self._lock = threading.Lock()

    @property
    def hydrator(self) -> DomainSchemaHydrator:
        return self._hydrator

    @property
    def subscriptions(self) -> ResourceSubscriptionManager:
        return self._subscriptions

    def register_handler(
        self,
        command_path: tuple[str, ...],
        handler: Callable[..., tuple[int, str]],
    ) -> None:
        """Register a direct Python functional handler for a command path."""
        with self._lock:
            self._functional_handlers[command_path] = handler

    def dispatch(
        self,
        cmd: list[str],
        timeout: float = DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        env: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        """Execute a command in-process when matching devops CLI or fallback to subprocess."""
        sub_args = _extract_devops_sub_args(cmd)
        if sub_args is None:
            return self._dispatch_subprocess(cmd, timeout=timeout, env=env)

        # Check registered functional handlers
        handler_result = self._check_functional_handlers(sub_args)
        if handler_result is not None:
            return handler_result

        # In-process Typer execution via CliRunner
        return self._dispatch_typer(sub_args, env=env)

    def _check_functional_handlers(self, sub_args: list[str]) -> tuple[int, str] | None:
        """Attempt lookup and execution of registered direct functional handlers."""
        with self._lock:
            handlers_snapshot = dict(self._functional_handlers)

        # Match 2-tuple (e.g. ("config", "show")) or 1-tuple (e.g. ("review",))
        if len(sub_args) >= 2:
            two_key = (sub_args[0], sub_args[1])
            if two_key in handlers_snapshot:
                try:
                    return handlers_snapshot[two_key](*sub_args[2:])
                except Exception as exc:
                    logger.debug("Functional handler %s failed: %s", two_key, exc)

        if len(sub_args) >= 1:
            one_key = (sub_args[0],)
            if one_key in handlers_snapshot:
                try:
                    return handlers_snapshot[one_key](*sub_args[1:])
                except Exception as exc:
                    logger.debug("Functional handler %s failed: %s", one_key, exc)

        return None

    def _dispatch_typer(
        self,
        sub_args: list[str],
        env: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        """Execute command in-process via Typer CliRunner."""
        from typer.testing import CliRunner

        from devops_cli.main import app

        runner = CliRunner()
        try:
            start_t = time.perf_counter()
            res = runner.invoke(app, sub_args, env=env)
            dur_ms = (time.perf_counter() - start_t) * 1000
            logger.debug("In-process dispatch %s finished in %.2fms", sub_args, dur_ms)

            out = (res.output or "").strip()
            if res.stderr and res.stderr.strip():
                out = f"{out}\n{res.stderr.strip()}".strip()
            return res.exit_code, out or "Success"
        except Exception as exc:
            return 1, f"In-process execution error: {exc}"

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
            return proc.returncode, out or "Success"
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
