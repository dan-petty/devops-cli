"""Unit and integration tests for AI spend Prometheus metrics exporter and /metrics endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from devops_cli.ai.spend.ledger import SpendLedger
from devops_cli.ai.spend.prometheus import export_ai_spend_prometheus
from devops_cli.commands.ai_cost import app as cost_app
from devops_cli.server.app import create_app

runner = CliRunner()


@pytest.fixture
def seeded_ledger(tmp_path: Path) -> SpendLedger:
    """Fixture initializing a temporary SpendLedger with known test records."""
    db_path = tmp_path / "spend.db"
    ledger = SpendLedger(db_path=db_path)

    ledger.record_request(
        provider="ollama",
        server="localhost:11434",
        model="llama3:8b",
        prompt_tokens=1000,
        completion_tokens=500,
        cost_usd=0.00025,
        duration_seconds=1.2,
    )
    ledger.record_request(
        provider="openai",
        server="example.com",
        model="gpt-4o",
        prompt_tokens=2000,
        completion_tokens=1000,
        cost_usd=0.015,
        duration_seconds=0.8,
    )
    return ledger


def test_export_ai_spend_prometheus_empty_ledger(tmp_path: Path) -> None:
    """Verify Prometheus export on empty ledger produces valid header gauges."""
    db_path = tmp_path / "spend.db"
    ledger = SpendLedger(db_path=db_path)

    text = export_ai_spend_prometheus(ledger)
    assert (
        "devops_cli_ai_active_servers 0" in text,
        "devops_cli_ai_active_models 0" in text,
    ) == (
        True,
        True,
    )


def test_export_ai_spend_prometheus_with_records(seeded_ledger: SpendLedger) -> None:
    """Verify Prometheus export formats spend counters, token counters, and gauges."""
    text = export_ai_spend_prometheus(seeded_ledger)

    assert (
        "devops_cli_ai_active_servers 2" in text,
        "devops_cli_ai_active_models 2" in text,
        'devops_cli_ai_spend_usd_total{model="llama3:8b",provider="ollama"}' in text,
        'devops_cli_ai_requests_total{model="gpt-4o",provider="openai"} 1' in text,
        'devops_cli_ai_tokens_total{model="gpt-4o",provider="openai",type="total"} 3000' in text,
        'devops_cli_ai_server_spend_usd{provider="openai",server="example.com"}' in text,
    ) == (
        True,
        True,
        True,
        True,
        True,
        True,
    )


def test_ai_cost_cli_prometheus_format(
    seeded_ledger: SpendLedger, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify CLI commands support exporting Prometheus exposition format."""
    monkeypatch.setattr("devops_cli.commands.ai_cost.get_spend_ledger", lambda: seeded_ledger)

    res_report = runner.invoke(cost_app, ["report", "--format", "prometheus"])
    res_cmd = runner.invoke(cost_app, ["prometheus"])

    assert (
        res_report.exit_code,
        res_cmd.exit_code,
        "devops_cli_ai_active_servers 2" in res_report.stdout,
        "devops_cli_ai_active_servers 2" in res_cmd.stdout,
    ) == (
        0,
        0,
        True,
        True,
    )


def test_server_metrics_endpoint_includes_ai_spend(
    seeded_ledger: SpendLedger, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify FastAPI /metrics endpoint integrates AI spend metrics."""
    monkeypatch.setattr("devops_cli.ai.spend.ledger.get_spend_ledger", lambda: seeded_ledger)

    app = create_app()
    client = TestClient(app)
    response = client.get("/metrics")

    assert (
        response.status_code,
        "devops_cli_info" in response.text,
        "devops_cli_ai_active_servers" in response.text,
        "devops_cli_ai_spend_usd_total" in response.text,
    ) == (
        200,
        True,
        True,
        True,
    )
