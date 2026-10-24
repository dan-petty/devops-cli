"""Unit and integration tests for AI spend Prometheus metrics exporter and /metrics endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from prometheus_client.parser import text_string_to_metric_families
from typer.testing import CliRunner

from devops_cli.ai.spend.ledger import SpendLedger
from devops_cli.ai.spend.prometheus import export_ai_spend_prometheus
from devops_cli.commands.ai_cost import app as cost_app
from devops_cli.config.constants import CONST_RESPONSE_CACHE_SERVER
from devops_cli.telemetry.instruments import INSTRUMENTS

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
        "devops_cli_ai_ledger_active_servers 0.0" in text,
        "devops_cli_ai_ledger_active_models 0.0" in text,
    ) == (
        True,
        True,
    )


def test_export_ai_spend_prometheus_with_records(seeded_ledger: SpendLedger) -> None:
    """Verify Prometheus export formats the ledger's spend, requests, tokens and totals."""
    text = export_ai_spend_prometheus(seeded_ledger)

    assert (
        "devops_cli_ai_ledger_active_servers 2.0" in text,
        "devops_cli_ai_ledger_active_models 2.0" in text,
        'devops_cli_ai_ledger_spend_usd{model="llama3:8b",provider="ollama"}' in text,
        'devops_cli_ai_ledger_requests{model="gpt-4o",provider="openai"} 1.0' in text,
        'devops_cli_ai_ledger_tokens{model="gpt-4o",provider="openai",type="prompt"} 2000.0'
        in text,
        'devops_cli_ai_ledger_server_spend_usd{provider="openai",server="example.com"}' in text,
        "devops_cli_ai_ledger_local_cost_equivalent_usd" in text,
        "devops_cli_ai_ledger_counterfactual_spend_usd" in text,
        "devops_cli_ai_ledger_counterfactual_savings_usd" in text,
    ) == (
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
    )


def test_the_ledger_exposition_shares_no_name_with_an_otlp_instrument(
    seeded_ledger: SpendLedger,
) -> None:
    """Verify every family the ledger exposes is a gauge under its own name, and no token sample
    is a total of the others, so a dashboard that sums an OTLP counter by name never adds a
    ledger snapshot to it (#1631)."""
    families = list(
        text_string_to_metric_families(
            export_ai_spend_prometheus(seeded_ledger, hardware_cost_usd=100.0)
        )
    )
    sent = {instrument.name for instrument in INSTRUMENTS}

    assert (
        sorted({family.type for family in families}),
        sorted(
            sample.name
            for family in families
            for sample in family.samples
            if sample.name in sent or not sample.name.startswith("devops_cli_ai_ledger_")
        ),
        sorted(
            {
                sample.labels["type"]
                for f in families
                for sample in f.samples
                if "type" in sample.labels
            }
        ),
    ) == (["gauge"], [], ["completion", "prompt"])


def test_an_unpriced_reference_exposes_no_savings_gauge(seeded_ledger: SpendLedger) -> None:
    """Verify a reference model that genai-prices does not know leaves the savings and
    counterfactual gauges out, so a scrape reads no savings rather than $0 (#1672)."""
    names = {
        family.name
        for family in text_string_to_metric_families(
            export_ai_spend_prometheus(seeded_ledger, reference_model="gpt-4o-mni")
        )
    }

    assert sorted(name for name in names if "counterfactual" in name or "equivalent" in name) == []


def test_the_exported_request_count_counts_only_requests_sent_to_a_model(
    seeded_ledger: SpendLedger,
) -> None:
    """Verify a reply the response cache answered adds no request to the exported request
    count, whose help text counts requests executed, and no active server (#816)."""
    seeded_ledger.record_request(
        provider="openai",
        server=CONST_RESPONSE_CACHE_SERVER,
        model="gpt-4o",
        prompt_tokens=0,
        completion_tokens=0,
        cost_usd=0.0,
        cached=True,
    )

    lines = export_ai_spend_prometheus(seeded_ledger).splitlines()

    assert (
        'devops_cli_ai_ledger_requests{model="gpt-4o",provider="openai"} 1.0' in lines,
        "devops_cli_ai_ledger_active_servers 2.0" in lines,
    ) == (True, True)


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
        "devops_cli_ai_ledger_active_servers 2.0" in res_report.stdout,
        "devops_cli_ai_ledger_active_servers 2.0" in res_cmd.stdout,
    ) == (
        0,
        0,
        True,
        True,
    )


def test_server_metrics_endpoint_includes_ai_spend(
    seeded_ledger: SpendLedger, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify FastAPI /metrics endpoint integrates the ledger's gauges, under no OTLP counter's
    name (#1631)."""
    monkeypatch.setattr("devops_cli.ai.spend.ledger.get_spend_ledger", lambda: seeded_ledger)

    from fastapi.testclient import TestClient

    from devops_cli.server.app import create_app

    app = create_app()
    client = TestClient(app)
    response = client.get("/metrics")

    assert (
        response.status_code,
        "devops_cli_info" in response.text,
        "devops_cli_ai_ledger_active_servers" in response.text,
        "devops_cli_ai_ledger_spend_usd" in response.text,
        "devops_cli_ai_spend_usd_total" in response.text,
    ) == (
        200,
        True,
        True,
        True,
        False,
    )
