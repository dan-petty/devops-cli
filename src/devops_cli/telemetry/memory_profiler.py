"""Deterministic async memory and connection pool profiler for devops-cli.

Leverages Python tracemalloc and socket lifecycle introspection to detect memory
bloat, peak allocation spikes, and connection leaks across async daemons, FastMCP
servers, and client connection brokers.
"""

from __future__ import annotations

import asyncio
import gc
import importlib
import inspect
import os
import socket
import time
import tracemalloc
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.constants import CONST_EXIT_FAILURE
from devops_cli.exceptions import DevOpsCLIError


class MemoryProfilerError(DevOpsCLIError, ValueError):
    """Domain exception raised when memory profiling target resolution or execution fails."""

    def __init__(
        self,
        message: str,
        *,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = "PROFILER_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=details)


class MemoryAllocationItem(BaseModel):
    """Represents a discrete memory allocation site on a specific source line."""

    model_config = ConfigDict(frozen=True)

    filename: str = Field(..., description="Source code file path where allocation originated.")
    line_number: int = Field(..., description="1-indexed source code line number.")
    size_kb: float = Field(..., description="Net allocation delta in kilobytes.")
    size_human: str = Field(..., description="Human-readable formatted allocation size.")
    count: int = Field(..., description="Number of allocated blocks or objects.")


class MemoryProfileReport(BaseModel):
    """Comprehensive diagnostic memory and connection pool profile report."""

    model_config = ConfigDict(frozen=True)

    target: str = Field(..., description="Profiled workload target identifier.")
    duration_seconds: float = Field(..., description="Total sample duration in seconds.")
    current_kb: float = Field(
        ..., description="Current memory allocated in kilobytes at completion."
    )
    peak_kb: float = Field(..., description="Peak memory allocated in kilobytes during profiling.")
    total_allocated_kb: float = Field(..., description="Calculated memory delta in kilobytes.")
    initial_sockets: int = Field(..., description="Active socket descriptor count at start.")
    final_sockets: int = Field(..., description="Active socket descriptor count at completion.")
    socket_leak_count: int = Field(..., description="Net unclosed socket count delta.")
    top_allocations: list[MemoryAllocationItem] = Field(
        default_factory=list, description="Top source code allocation sites."
    )
    max_peak_mb: float = Field(..., description="Configured peak memory threshold in megabytes.")
    passed: bool = Field(..., description="Whether profiling satisfied all threshold criteria.")
    warnings: list[str] = Field(
        default_factory=list, description="Diagnostic warnings or threshold violations."
    )


def count_open_sockets() -> int:
    """Inspect and count currently open socket descriptors across the process."""
    try:
        fd_dir = Path("/proc/self/fd")
        if fd_dir.exists():
            return _count_proc_sockets(fd_dir)
    except Exception:
        pass

    return _count_gc_sockets()


def _count_proc_sockets(fd_dir: Path) -> int:
    """Count open sockets via Linux /proc/self/fd inspection."""
    count = 0
    for entry in fd_dir.iterdir():
        try:
            target = os.readlink(entry)
            if target.startswith("socket:["):
                count += 1
        except OSError:
            continue
    return count


def _count_gc_sockets() -> int:
    """Fallback: Count active unclosed socket objects via Python garbage collector."""
    open_count = 0
    for obj in gc.get_objects():
        if isinstance(obj, socket.socket):
            try:
                if obj.fileno() != -1:
                    open_count += 1
            except Exception:
                pass
    return open_count


class MemoryProfiler:
    """Deterministic heap and socket profiler managing tracemalloc and connection state."""

    def __init__(self, target: str) -> None:
        self.target = target
        self._start_time: float = 0.0
        self._initial_sockets: int = 0
        self._start_traced_bytes: int = 0
        self._owns_tracemalloc: bool = False
        self._snapshot_start: tracemalloc.Snapshot | None = None

    def start(self) -> None:
        """Initialize garbage collection, socket baseline, and tracemalloc tracking."""
        gc.collect()
        self._initial_sockets = count_open_sockets()
        if not tracemalloc.is_tracing():
            tracemalloc.start(25)
            self._owns_tracemalloc = True
        else:
            self._owns_tracemalloc = False

        self._start_traced_bytes = tracemalloc.get_traced_memory()[0]
        self._snapshot_start = tracemalloc.take_snapshot()
        self._start_time = time.perf_counter()

    def stop(self, top_n: int = 10, max_peak_mb: float = 100.0) -> MemoryProfileReport:
        """Halt profiling, diff memory snapshots, evaluate thresholds, and emit report."""
        duration = max(0.0, time.perf_counter() - self._start_time)
        current_bytes, peak_bytes = tracemalloc.get_traced_memory()
        snapshot_stop = tracemalloc.take_snapshot()

        if self._owns_tracemalloc and tracemalloc.is_tracing():
            tracemalloc.stop()
        gc.collect()
        final_sockets = count_open_sockets()

        current_kb = round(current_bytes / 1024.0, 2)
        peak_kb = round(peak_bytes / 1024.0, 2)
        total_allocated_kb = round((current_bytes - self._start_traced_bytes) / 1024.0, 2)
        socket_leak_count = max(0, final_sockets - self._initial_sockets)

        top_allocations = self._extract_top_allocations(snapshot_stop, self._snapshot_start, top_n)

        passed, warnings = self._evaluate_thresholds(
            peak_bytes, max_peak_mb, socket_leak_count, self._initial_sockets, final_sockets
        )

        return MemoryProfileReport(
            target=self.target,
            duration_seconds=round(duration, 3),
            current_kb=current_kb,
            peak_kb=peak_kb,
            total_allocated_kb=total_allocated_kb,
            initial_sockets=self._initial_sockets,
            final_sockets=final_sockets,
            socket_leak_count=socket_leak_count,
            top_allocations=top_allocations,
            max_peak_mb=max_peak_mb,
            passed=passed,
            warnings=warnings,
        )

    def _evaluate_thresholds(
        self,
        peak_bytes: int,
        max_peak_mb: float,
        socket_leak_count: int,
        initial_sockets: int,
        final_sockets: int,
    ) -> tuple[bool, list[str]]:
        """Evaluate peak memory limits and socket leak constraints."""
        passed = True
        warnings: list[str] = []

        peak_mb = peak_bytes / (1024.0 * 1024.0)
        if peak_mb > max_peak_mb:
            passed = False
            warnings.append(
                f"Peak memory ({peak_mb:.2f} MB) exceeded threshold ({max_peak_mb:.2f} MB)"
            )

        if socket_leak_count > 0:
            warnings.append(
                f"Detected {socket_leak_count} unclosed socket(s) (initial: {initial_sockets}, final: {final_sockets})"
            )
            passed = False

        return passed, warnings

    def _extract_top_allocations(
        self,
        snapshot_stop: tracemalloc.Snapshot,
        snapshot_start: tracemalloc.Snapshot | None,
        top_n: int,
    ) -> list[MemoryAllocationItem]:
        """Diff snapshots and extract top source code allocation sites."""
        stats: Sequence[tracemalloc.Statistic | tracemalloc.StatisticDiff] = (
            snapshot_stop.compare_to(snapshot_start, "lineno")
            if snapshot_start is not None
            else snapshot_stop.statistics("lineno")
        )

        items: list[MemoryAllocationItem] = []
        for stat in stats[:top_n]:
            frame = stat.traceback[0]
            size_diff = getattr(stat, "size_diff", getattr(stat, "size", 0))
            size_kb = round(size_diff / 1024.0, 2)
            count = getattr(stat, "count_diff", getattr(stat, "count", 0))
            items.append(
                MemoryAllocationItem(
                    filename=frame.filename,
                    line_number=frame.lineno,
                    size_kb=size_kb,
                    size_human=self._format_human_size(size_kb),
                    count=count,
                )
            )
        return items

    @staticmethod
    def _format_human_size(size_kb: float) -> str:
        """Format kilobyte allocation size into human-readable representation."""
        if abs(size_kb) >= 1024.0:
            return f"{size_kb / 1024.0:.2f} MB"
        return f"{size_kb:.2f} KB"


async def _exercise_http_pool(iterations: int) -> None:
    """Perform deterministic async HTTP connection pool requests against in-memory transport."""
    try:
        import httpx2 as httpx
    except ImportError:
        import httpx  # type: ignore[no-redef]
    from devops_cli.http.broker import HttpClientBroker

    async def _dummy_app(scope: Any, receive: Any, send: Any) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"text/plain"]],
            }
        )
        await send({"type": "http.response.body", "body": b"OK"})

    broker = HttpClientBroker(allow_private_networks=True)
    client = await broker.get_async_client()
    client._transport = httpx.ASGITransport(app=cast(Any, _dummy_app))

    for _ in range(iterations):
        resp = await broker.arequest("GET", "http://localhost:8080/health")
        _ = resp.status_code

    await broker.aclose()
    broker.close()


def profile_http_pool_workload(
    iterations: int = 10,
    top_n: int = 10,
    max_peak_mb: float = 100.0,
) -> MemoryProfileReport:
    """Profile HttpClientBroker connection pool lifecycle and socket recycling."""
    profiler = MemoryProfiler(target="http-pool")
    profiler.start()

    asyncio.run(_exercise_http_pool(iterations))

    return profiler.stop(top_n=top_n, max_peak_mb=max_peak_mb)


def profile_fastmcp_workload(
    iterations: int = 5,
    top_n: int = 10,
    max_peak_mb: float = 100.0,
) -> MemoryProfileReport:
    """Profile FastMCP server tool schema generation and registration allocations."""
    profiler = MemoryProfiler(target="fastmcp")
    profiler.start()

    from devops_cli.ai.mcp.server import list_mcp_tools

    for _ in range(iterations):
        _ = list_mcp_tools()

    return profiler.stop(top_n=top_n, max_peak_mb=max_peak_mb)


def profile_custom_callable(
    func: Callable[..., Any],
    name: str = "custom",
    iterations: int = 5,
    top_n: int = 10,
    max_peak_mb: float = 100.0,
) -> MemoryProfileReport:
    """Profile memory and socket retention for an arbitrary Python sync or async callable."""
    profiler = MemoryProfiler(target=name)
    profiler.start()

    for _ in range(iterations):
        res = func()
        if inspect.isawaitable(res):
            asyncio.run(res)

    return profiler.stop(top_n=top_n, max_peak_mb=max_peak_mb)


def run_memory_profiler(
    target: str = "http-pool",
    iterations: int = 10,
    top_n: int = 10,
    max_peak_mb: float = 100.0,
) -> MemoryProfileReport:
    """Dispatch memory profiling across standard built-ins or custom module callables."""
    cleaned = target.strip().lower()
    if cleaned in ("http-pool", "http_pool", "http"):
        return profile_http_pool_workload(
            iterations=iterations, top_n=top_n, max_peak_mb=max_peak_mb
        )
    if cleaned in ("fastmcp", "mcp"):
        return profile_fastmcp_workload(iterations=iterations, top_n=top_n, max_peak_mb=max_peak_mb)

    if ":" in target:
        mod_name, func_name = target.split(":", 1)
        try:
            mod = importlib.import_module(mod_name)
            fn = getattr(mod, func_name)
        except Exception as exc:
            msg = f"Unable to resolve target '{target}': {str(exc)[:256]}"
            raise MemoryProfilerError(msg, details={"target": target}) from exc

        return profile_custom_callable(
            fn, name=target, iterations=iterations, top_n=top_n, max_peak_mb=max_peak_mb
        )

    msg = f"Unable to resolve target '{target}': expected 'http-pool', 'fastmcp', or 'module:function'"
    raise MemoryProfilerError(msg, details={"target": target})
