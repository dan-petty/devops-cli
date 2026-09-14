"""Tests for deterministic async memory and connection pool profiler."""

from __future__ import annotations

import asyncio
import json
import socket
import tracemalloc
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.test_cmd import app
from devops_cli.telemetry.memory_profiler import (
    MemoryAllocationItem,
    MemoryProfiler,
    MemoryProfileReport,
    MemoryProfilerError,
    count_open_sockets,
    profile_custom_callable,
    profile_fastmcp_workload,
    profile_http_pool_workload,
    run_memory_profiler,
)

runner = CliRunner()


def test_memory_allocation_item_model() -> None:
    item = MemoryAllocationItem(
        filename="src/app.py",
        line_number=42,
        size_kb=1024.5,
        size_human="1.00 MB",
        count=10,
    )
    assert item.filename == "src/app.py"
    assert item.line_number == 42
    assert item.size_kb == 1024.5
    assert item.count == 10


def test_memory_profile_report_model() -> None:
    report = MemoryProfileReport(
        target="test-target",
        duration_seconds=1.23,
        current_kb=500.0,
        peak_kb=2048.0,
        total_allocated_kb=1548.0,
        initial_sockets=3,
        final_sockets=3,
        socket_leak_count=0,
        top_allocations=[],
        max_peak_mb=50.0,
        passed=True,
        warnings=[],
    )
    assert report.target == "test-target"
    assert report.passed is True
    assert report.socket_leak_count == 0


def test_count_open_sockets_basic() -> None:
    initial = count_open_sockets()
    assert isinstance(initial, int)
    assert initial >= 0

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        after_open = count_open_sockets()
        assert after_open >= initial
    finally:
        s.close()

    after_close = count_open_sockets()
    assert after_close <= after_open


def test_count_open_sockets_proc_fallback() -> None:
    with patch("pathlib.Path.exists", return_value=False):
        count = count_open_sockets()
        assert isinstance(count, int)
        assert count >= 0


def test_memory_profiler_lifecycle() -> None:
    profiler = MemoryProfiler(target="sample-test")
    profiler.start()

    # Allocate some memory
    data = [bytearray(10000) for _ in range(50)]
    assert len(data) == 50

    report = profiler.stop(top_n=5, max_peak_mb=100.0)
    assert report.target == "sample-test"
    assert report.duration_seconds >= 0.0
    assert report.peak_kb > 0.0
    assert report.passed is True
    assert len(report.warnings) == 0


def test_memory_profiler_peak_threshold_failure() -> None:
    profiler = MemoryProfiler(target="threshold-test")
    profiler.start()

    # Allocate memory
    data = [bytearray(1024 * 1024) for _ in range(3)]
    assert len(data) == 3

    # Set threshold very low (e.g. 0.001 MB)
    report = profiler.stop(top_n=5, max_peak_mb=0.001)
    assert report.passed is False
    assert any("Peak memory" in w for w in report.warnings)


def test_memory_profiler_socket_leak_detection() -> None:
    profiler = MemoryProfiler(target="socket-leak-test")

    with patch(
        "devops_cli.telemetry.memory_profiler.count_open_sockets",
        side_effect=[5, 8],
    ):
        profiler.start()
        report = profiler.stop(top_n=5, max_peak_mb=100.0)

    assert report.initial_sockets == 5
    assert report.final_sockets == 8
    assert report.socket_leak_count == 3
    assert report.passed is False
    assert any("Detected 3 unclosed socket(s)" in w for w in report.warnings)


def test_profile_http_pool_workload() -> None:
    report = profile_http_pool_workload(iterations=3, top_n=5, max_peak_mb=100.0)
    assert report.target == "http-pool"
    assert report.duration_seconds >= 0.0
    assert isinstance(report.top_allocations, list)


def test_profile_fastmcp_workload() -> None:
    report = profile_fastmcp_workload(iterations=2, top_n=5, max_peak_mb=100.0)
    assert report.target == "fastmcp"
    assert report.duration_seconds >= 0.0
    assert isinstance(report.top_allocations, list)


def test_profile_custom_callable() -> None:
    def my_workload() -> None:
        _ = [x * 2 for x in range(1000)]

    report = profile_custom_callable(
        func=my_workload,
        name="my_workload",
        iterations=5,
        top_n=5,
        max_peak_mb=50.0,
    )
    assert report.target == "my_workload"
    assert report.passed is True


def test_run_memory_profiler_dispatch() -> None:
    report_http = run_memory_profiler(target="http-pool", iterations=2, top_n=5)
    assert report_http.target == "http-pool"

    report_mcp = run_memory_profiler(target="fastmcp", iterations=2, top_n=5)
    assert report_mcp.target == "fastmcp"


def test_run_memory_profiler_custom_import() -> None:
    report = run_memory_profiler(
        target="time:perf_counter",
        iterations=5,
        top_n=5,
    )
    assert report.target == "time:perf_counter"
    assert report.passed is True


def test_profile_custom_async_callable() -> None:
    async def async_workload() -> None:
        await asyncio.sleep(0.001)

    report = profile_custom_callable(
        func=async_workload,
        name="async_workload",
        iterations=2,
    )
    assert report.target == "async_workload"
    assert report.passed is True


def test_run_memory_profiler_workload_exception_propagates() -> None:
    with patch("importlib.import_module") as mock_import:
        mock_mod = MagicMock()
        mock_mod.fail_fn.side_effect = RuntimeError("Original workload error")
        mock_import.return_value = mock_mod

        with pytest.raises(RuntimeError) as exc_info:
            run_memory_profiler(target="fake_mod:fail_fn", iterations=1)
        assert "Original workload error" in str(exc_info.value)


def test_memory_profiler_ownership_preservation() -> None:
    if not tracemalloc.is_tracing():
        tracemalloc.start()
    try:
        profiler = MemoryProfiler(target="nested-test")
        profiler.start()
        assert profiler._owns_tracemalloc is False
        _ = profiler.stop(top_n=2)
        assert tracemalloc.is_tracing() is True
    finally:
        if tracemalloc.is_tracing():
            tracemalloc.stop()


def test_run_memory_profiler_invalid_target() -> None:
    with pytest.raises(MemoryProfilerError) as exc_info:
        run_memory_profiler(target="nonexistent_module:func", iterations=1)
    assert "Unable to resolve target" in str(exc_info.value)
    assert isinstance(exc_info.value, ValueError)


# -----------------------------------------------------------------------------
# CLI Subcommand Tests: devops test profile-memory
# -----------------------------------------------------------------------------


@patch("devops_cli.commands.test_cmd.run_memory_profiler")
def test_cli_profile_memory_http_pool(mock_run: MagicMock) -> None:
    mock_run.return_value = MemoryProfileReport(
        target="http-pool",
        duration_seconds=0.45,
        current_kb=120.0,
        peak_kb=512.0,
        total_allocated_kb=392.0,
        initial_sockets=2,
        final_sockets=2,
        socket_leak_count=0,
        top_allocations=[
            MemoryAllocationItem(
                filename="src/devops_cli/http/broker.py",
                line_number=88,
                size_kb=256.0,
                size_human="256.00 KB",
                count=4,
            )
        ],
        max_peak_mb=50.0,
        passed=True,
        warnings=[],
    )

    res = runner.invoke(app, ["profile-memory", "http-pool", "-i", "5"])
    assert res.exit_code == 0
    assert "Memory Profiling Report" in res.stdout
    assert "http-pool" in res.stdout
    assert "PASSED" in res.stdout


@patch("devops_cli.commands.test_cmd.run_memory_profiler")
def test_cli_profile_memory_json(mock_run: MagicMock) -> None:
    mock_run.return_value = MemoryProfileReport(
        target="http-pool",
        duration_seconds=0.12,
        current_kb=50.0,
        peak_kb=100.0,
        total_allocated_kb=50.0,
        initial_sockets=1,
        final_sockets=1,
        socket_leak_count=0,
        top_allocations=[],
        max_peak_mb=50.0,
        passed=True,
        warnings=[],
    )

    res = runner.invoke(app, ["profile-memory", "http-pool", "--json"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert data["target"] == "http-pool"
    assert data["passed"] is True


@patch("devops_cli.commands.test_cmd.run_memory_profiler")
def test_cli_profile_memory_output_file(mock_run: MagicMock, tmp_path: Path) -> None:
    out_file = tmp_path / "memory_report.json"
    mock_run.return_value = MemoryProfileReport(
        target="fastmcp",
        duration_seconds=0.8,
        current_kb=200.0,
        peak_kb=400.0,
        total_allocated_kb=200.0,
        initial_sockets=0,
        final_sockets=0,
        socket_leak_count=0,
        top_allocations=[],
        max_peak_mb=50.0,
        passed=True,
        warnings=[],
    )

    res = runner.invoke(app, ["profile-memory", "fastmcp", "-o", str(out_file)])
    assert res.exit_code == 0
    assert out_file.exists()
    content = json.loads(out_file.read_text(encoding="utf-8"))
    assert content["target"] == "fastmcp"


def test_cli_profile_memory_dry_run() -> None:
    res = runner.invoke(app, ["profile-memory", "http-pool", "--dry-run"])
    assert res.exit_code == 0
    assert "dry_run" in res.stdout
    assert "profile_async_memory" in res.stdout


@patch("devops_cli.commands.test_cmd.run_memory_profiler")
def test_cli_profile_memory_leak_failure(mock_run: MagicMock) -> None:
    mock_run.return_value = MemoryProfileReport(
        target="http-pool",
        duration_seconds=0.5,
        current_kb=100.0,
        peak_kb=200.0,
        total_allocated_kb=100.0,
        initial_sockets=2,
        final_sockets=4,
        socket_leak_count=2,
        top_allocations=[],
        max_peak_mb=50.0,
        passed=False,
        warnings=["Detected 2 unclosed socket(s)"],
    )

    res = runner.invoke(app, ["profile-memory", "http-pool", "--fail-on-leak"])
    assert res.exit_code == 1
    assert "FAILED" in res.stdout


@patch("devops_cli.commands.test_cmd.run_memory_profiler")
def test_cli_profile_memory_json_and_output(mock_run: MagicMock, tmp_path: Path) -> None:
    out_file = tmp_path / "out.json"
    mock_run.return_value = MemoryProfileReport(
        target="http-pool",
        duration_seconds=0.1,
        current_kb=10.0,
        peak_kb=20.0,
        total_allocated_kb=10.0,
        initial_sockets=0,
        final_sockets=0,
        socket_leak_count=0,
        top_allocations=[],
        max_peak_mb=50.0,
        passed=True,
        warnings=[],
    )
    res = runner.invoke(app, ["profile-memory", "http-pool", "-o", str(out_file), "--json"])
    assert res.exit_code == 0
    parsed = json.loads(res.stdout)
    assert parsed["target"] == "http-pool"
    assert out_file.exists()


@patch("devops_cli.commands.test_cmd.run_memory_profiler")
def test_cli_profile_memory_peak_failure_with_ignore_leak(mock_run: MagicMock) -> None:
    mock_run.return_value = MemoryProfileReport(
        target="http-pool",
        duration_seconds=0.1,
        current_kb=100.0,
        peak_kb=60.0 * 1024.0,
        total_allocated_kb=100.0,
        initial_sockets=0,
        final_sockets=0,
        socket_leak_count=0,
        top_allocations=[],
        max_peak_mb=50.0,
        passed=False,
        warnings=["Peak memory exceeded threshold"],
    )
    res = runner.invoke(app, ["profile-memory", "http-pool", "--ignore-leak"])
    assert res.exit_code == 1


@patch("devops_cli.commands.test_cmd.run_memory_profiler")
def test_cli_profile_memory_leak_ignored(mock_run: MagicMock) -> None:
    mock_run.return_value = MemoryProfileReport(
        target="http-pool",
        duration_seconds=0.1,
        current_kb=10.0,
        peak_kb=20.0,
        total_allocated_kb=10.0,
        initial_sockets=0,
        final_sockets=2,
        socket_leak_count=2,
        top_allocations=[],
        max_peak_mb=50.0,
        passed=False,
        warnings=["Detected 2 unclosed socket(s)"],
    )
    res = runner.invoke(app, ["profile-memory", "http-pool", "--ignore-leak"])
    assert res.exit_code == 0
