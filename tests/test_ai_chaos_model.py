"""Unit and integration tests for Model Dependency Chaos Engineering Suite (devops ai chaos-model)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.chaos import (
    ChaosConfig,
    ChaosFaultResult,
    ChaosMode,
    ChaosStatus,
    ModelChaosInjector,
    ModelChaosReport,
)
from devops_cli.commands.ai import app as ai_app
from devops_cli.exceptions import ValidationError
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from devops_cli.telemetry.tracer import get_tracer, reset_tracer


@pytest.fixture(autouse=True)
def clean_telemetry(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    """Reset tracer and metric counters before each test."""
    reset_tracer()
    sent_payloads: list[tuple[str, dict[str, Any]]] = []
    tracer = get_tracer()
    monkeypatch.setattr(tracer, "_send_payload", lambda path, p: sent_payloads.append((path, p)))
    return sent_payloads


# ── 1. Data Models and Enums ──────────────────────────────────────────────────


def test_chaos_enums_and_config() -> None:
    """Validate enum values and default configuration model."""
    assert ChaosMode.LATENCY.value == "latency"
    assert ChaosMode.RATE_LIMIT.value == "rate-limit"
    assert ChaosMode.TIMEOUT.value == "timeout"
    assert ChaosMode.MALFORMED_JSON.value == "malformed-json"
    assert ChaosMode.ALL.value == "all"

    assert ChaosStatus.INJECTED.value == "injected"
    assert ChaosStatus.RECOVERED.value == "recovered"
    assert ChaosStatus.FAILED.value == "failed"
    assert ChaosStatus.SKIPPED.value == "skipped"

    cfg = ChaosConfig()
    assert cfg.mode == ChaosMode.ALL
    assert cfg.latency_ms == 500
    assert cfg.error_rate == 1.0
    assert cfg.primary_provider == "openai"
    assert cfg.primary_model == "gpt-4o"
    assert cfg.fallback_provider == "ollama"
    assert cfg.fallback_model == "qwen2.5-coder:7b"
    assert cfg.dry_run is False


def test_chaos_report_model() -> None:
    """Validate report serialization and calculated properties."""
    result = ChaosFaultResult(
        mode=ChaosMode.RATE_LIMIT,
        primary_provider="openai",
        primary_model="gpt-4o",
        fault_injected="HTTP 429 Too Many Requests rate limit exceeded",
        fault_latency_ms=12.5,
        fallback_engaged=True,
        fallback_provider="ollama",
        fallback_model="qwen2.5-coder:7b",
        status=ChaosStatus.RECOVERED,
        recovery_response="def test_health(): return True",
    )
    report = ModelChaosReport(
        summary="Chaos testing passed",
        total_faults=1,
        recovered_faults=1,
        failed_faults=0,
        results=[result],
        all_passed=True,
    )
    assert report.all_passed is True
    assert len(report.results) == 1
    assert report.results[0].status == ChaosStatus.RECOVERED


# ── 2. Fault Injection & Fallback Recovery Unit Tests ─────────────────────────


def test_injector_latency_mode() -> None:
    """Verify synthetic network latency injection and measurement."""
    config = ChaosConfig(
        mode=ChaosMode.LATENCY,
        latency_ms=50,
        dry_run=True,
    )
    injector = ModelChaosInjector(config)
    report = injector.execute()

    assert report.total_faults == 1
    assert report.recovered_faults == 1
    assert report.all_passed is True
    res = report.results[0]
    assert res.mode == ChaosMode.LATENCY
    assert res.status == ChaosStatus.RECOVERED
    assert res.fault_latency_ms >= 0


def test_injector_rate_limit_mode() -> None:
    """Verify HTTP 429 rate limit emulation, metrics recording, and fallback recovery."""
    config = ChaosConfig(
        mode=ChaosMode.RATE_LIMIT,
        dry_run=True,
        fallback_model="granite3.1-dense:8b",
    )
    injector = ModelChaosInjector(config)
    report = injector.execute()

    assert report.total_faults == 1
    assert report.recovered_faults == 1
    assert report.all_passed is True
    res = report.results[0]
    assert res.mode == ChaosMode.RATE_LIMIT
    assert "429" in res.fault_injected
    assert res.fallback_engaged is True
    assert res.fallback_model == "granite3.1-dense:8b"
    assert res.status == ChaosStatus.RECOVERED

    # Verify Prometheus counters
    metrics = GLOBAL_METRICS.get_metrics_snapshot()
    assert metrics["counters"].get("devops_cli_ai_chaos_injections_total", 0) >= 1
    assert metrics["counters"].get("devops_cli_ai_chaos_recoveries_total", 0) >= 1


def test_injector_timeout_mode() -> None:
    """Verify connection timeout and socket error emulation with fallback recovery."""
    config = ChaosConfig(
        mode=ChaosMode.TIMEOUT,
        dry_run=True,
    )
    injector = ModelChaosInjector(config)
    report = injector.execute()

    assert report.total_faults == 1
    assert report.recovered_faults == 1
    res = report.results[0]
    assert res.mode == ChaosMode.TIMEOUT
    assert "timeout" in res.fault_injected.lower() or "socket" in res.fault_injected.lower()
    assert res.fallback_engaged is True
    assert res.status == ChaosStatus.RECOVERED


def test_injector_malformed_json_mode() -> None:
    """Verify mid-stream truncation and malformed JSON response recovery."""
    config = ChaosConfig(
        mode=ChaosMode.MALFORMED_JSON,
        dry_run=True,
    )
    injector = ModelChaosInjector(config)
    report = injector.execute()

    assert report.total_faults == 1
    assert report.recovered_faults == 1
    res = report.results[0]
    assert res.mode == ChaosMode.MALFORMED_JSON
    assert "json" in res.fault_injected.lower() or "truncat" in res.fault_injected.lower()
    assert res.fallback_engaged is True
    assert res.status == ChaosStatus.RECOVERED


def test_injector_all_modes_cascade() -> None:
    """Verify that mode=ALL executes all 4 failure modes in sequence and aggregates results."""
    config = ChaosConfig(
        mode=ChaosMode.ALL,
        dry_run=True,
    )
    injector = ModelChaosInjector(config)
    report = injector.execute()

    assert report.total_faults == 4
    assert report.recovered_faults == 4
    assert report.failed_faults == 0
    assert report.all_passed is True
    modes = [r.mode for r in report.results]
    assert ChaosMode.LATENCY in modes
    assert ChaosMode.RATE_LIMIT in modes
    assert ChaosMode.TIMEOUT in modes
    assert ChaosMode.MALFORMED_JSON in modes


def test_injector_fallback_failure_handling() -> None:
    """Verify that if fallback provider also fails, report marks status as FAILED."""
    config = ChaosConfig(
        mode=ChaosMode.RATE_LIMIT,
        dry_run=False,
    )
    injector = ModelChaosInjector(config)

    # Patch client to fail both primary and fallback
    with patch.object(
        injector, "_invoke_model_fallback", side_effect=RuntimeError("Local Ollama down")
    ):
        report = injector.execute()
        assert report.total_faults == 1
        assert report.recovered_faults == 0
        assert report.failed_faults == 1
        assert report.all_passed is False
        assert report.results[0].status == ChaosStatus.FAILED
        assert "Local Ollama down" in report.results[0].error


# ── 3. CLI Command Tests ──────────────────────────────────────────────────────


def test_cli_chaos_model_dry_run_table() -> None:
    """Verify CLI devops ai chaos-model in dry-run mode with table output."""
    runner = CliRunner()
    result = runner.invoke(ai_app, ["chaos-model", "--dry-run"])

    assert result.exit_code == 0
    assert "model dependency chaos" in result.output.lower() or "chaos" in result.output.lower()
    assert "recovered" in result.output.lower()


def test_cli_chaos_model_single_mode_json() -> None:
    """Verify CLI devops ai chaos-model with specific mode and JSON output."""
    runner = CliRunner()
    result = runner.invoke(
        ai_app,
        ["chaos-model", "--mode", "rate-limit", "--format", "json", "--dry-run"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["total_faults"] == 1
    assert payload["results"][0]["mode"] == "rate-limit"
    assert payload["all_passed"] is True


def test_cli_chaos_model_custom_models() -> None:
    """Verify CLI options for primary and fallback models."""
    runner = CliRunner()
    result = runner.invoke(
        ai_app,
        [
            "chaos-model",
            "--mode",
            "timeout",
            "--primary-provider",
            "claude",
            "--primary-model",
            "claude-3-7-sonnet",
            "--fallback-provider",
            "ollama",
            "--fallback-model",
            "granite3.1-dense:8b",
            "--dry-run",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["results"][0]["primary_provider"] == "claude"
    assert payload["results"][0]["fallback_model"] == "granite3.1-dense:8b"


def test_cli_chaos_model_invalid_mode() -> None:
    """Verify CLI rejection of invalid chaos mode."""
    runner = CliRunner()
    result = runner.invoke(ai_app, ["chaos-model", "--mode", "unsupported-mode"])
    assert result.exit_code != 0


def test_injector_spans_and_max_retries(clean_telemetry: list[tuple[str, dict[str, Any]]]) -> None:
    """Verify child ai.chaos.inject spans and max_retries forwarding to AIConfig."""
    config = ChaosConfig(
        mode=ChaosMode.RATE_LIMIT,
        dry_run=True,
        max_retries=3,
    )
    injector = ModelChaosInjector(config)
    report = injector.execute()
    assert report.all_passed is True

    trace_payloads = [p for path, p in clean_telemetry if path == "/v1/traces"]
    span_names = [
        s["name"] for p in trace_payloads for s in p["resourceSpans"][0]["scopeSpans"][0]["spans"]
    ]
    assert "ai.chaos.run" in span_names
    assert "ai.chaos.inject" in span_names

    # Test non-dry-run max_retries forwarding to AIConfig & chat
    real_config = ChaosConfig(mode=ChaosMode.RATE_LIMIT, dry_run=False, max_retries=4)
    real_injector = ModelChaosInjector(real_config)
    with patch("devops_cli.ai.client.unified.LLMClient") as mock_client_cls:
        mock_instance = mock_client_cls.return_value
        mock_instance.chat.return_value = MagicMock(content="ok")
        real_injector.execute()
        ai_cfg_call = mock_client_cls.call_args[1]["config"]
        assert ai_cfg_call.max_retries == 4
        mock_instance.chat.assert_called_with(system="", user=real_config.prompt, max_retries=4)


def test_injector_error_rate_thresholding() -> None:
    """Verify that error_rate=0.0 skips fault injection."""
    config = ChaosConfig(
        mode=ChaosMode.ALL,
        error_rate=0.0,
        dry_run=True,
    )
    injector = ModelChaosInjector(config)
    report = injector.execute()

    assert report.total_faults == 4
    for res in report.results:
        assert res.status == ChaosStatus.SKIPPED
        assert "skipped" in res.fault_injected.lower()


def test_cli_and_config_validation_bounds() -> None:
    """Verify bounds validation on latency_ms and error_rate."""
    from pydantic import ValidationError as PydanticValidationError

    # Model validation
    with pytest.raises(PydanticValidationError):
        ChaosConfig(latency_ms=-10)

    with pytest.raises(PydanticValidationError):
        ChaosConfig(error_rate=1.5)

    with pytest.raises(PydanticValidationError):
        ChaosConfig(error_rate=-0.1)

    # CLI validation
    runner = CliRunner()
    res_lat = runner.invoke(ai_app, ["chaos-model", "--latency-ms", "-50"])
    assert res_lat.exit_code != 0
    assert "invalid --latency-ms" in res_lat.output.lower()

    res_err = runner.invoke(ai_app, ["chaos-model", "--error-rate", "1.5"])
    assert res_err.exit_code != 0
    assert "invalid --error-rate" in res_err.output.lower()


# ── 4. FastMCP Tool Contract Tests ────────────────────────────────────────────


def test_fastmcp_ai_chaos_model_tool() -> None:
    """Verify FastMCP ai_chaos_model tool function signature, execution, and validation."""
    from devops_cli.ai.mcp.server import ai_chaos_model

    # Valid dry-run call
    with patch(
        "devops_cli.ai.mcp.server._run_mcp_cmd", return_value="Chaos suite passed"
    ) as mock_run:
        res = ai_chaos_model(mode="rate-limit", fallback_model="qwen2.5-coder:7b", dry_run=True)
        assert res == "Chaos suite passed"
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "chaos-model" in cmd
        assert "--mode" in cmd
        assert "rate-limit" in cmd
        assert "--dry-run" in cmd

    # Argument validation against flag injection
    with pytest.raises(ValidationError):
        ai_chaos_model(mode="--malicious-flag")

    with pytest.raises(ValidationError):
        ai_chaos_model(fallback_model="--injected")
