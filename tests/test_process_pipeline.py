"""Unit tests for universal ProcessExecutionPipeline."""

from __future__ import annotations

import sys

from devops_cli.core.process_pipeline import ProcessExecutionPipeline


def test_process_pipeline_successful_execution() -> None:
    """ProcessExecutionPipeline should execute command and return structured result."""
    pipeline = ProcessExecutionPipeline()
    res = pipeline.run([sys.executable, "-c", "print('hello process pipeline')"])

    assert res.success is True
    assert res.return_code == 0
    assert "hello process pipeline" in res.stdout
    assert res.duration_seconds > 0.0
    assert res.timeout_occurred is False


def test_process_pipeline_timeout_handling() -> None:
    """ProcessExecutionPipeline should catch subprocess timeout and flag timeout_occurred."""
    pipeline = ProcessExecutionPipeline(default_timeout=0.2)
    res = pipeline.run([sys.executable, "-c", "import time; time.sleep(1.0)"])

    assert res.success is False
    assert res.timeout_occurred is True
    assert res.return_code == 124


def test_process_pipeline_error_code() -> None:
    """ProcessExecutionPipeline should capture non-zero return codes."""
    pipeline = ProcessExecutionPipeline()
    res = pipeline.run([sys.executable, "-c", "import sys; sys.exit(7)"])

    assert res.success is False
    assert res.return_code == 7
