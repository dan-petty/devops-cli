"""Unit and CLI integration tests for devops ai cost and spend commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.ai.spend.ledger import SpendLedger
from devops_cli.ai.spend.pricing import PricingRegistry
from devops_cli.commands.ai import app as ai_app
from devops_cli.commands.ai_cost import app as cost_app

runner = CliRunner()


@pytest.fixture
def mock_spend_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SpendLedger:
    """Fixture initializing isolated temporary SpendLedger and PricingRegistry."""
    db_path = tmp_path / "spend.db"
    pricing = PricingRegistry(data_dir=tmp_path)
    ledger = SpendLedger(db_path=db_path)

    monkeypatch.setattr("devops_cli.commands.ai_cost.get_spend_ledger", lambda: ledger)
    monkeypatch.setattr("devops_cli.commands.ai_cost.get_pricing_registry", lambda: pricing)

    # Seed test record
    ledger.record_request(
        provider="ollama",
        server="localhost:11434",
        model="llama3:8b",
        prompt_tokens=1000,
        completion_tokens=500,
        cost_usd=0.0002,
        duration_seconds=1.5,
    )
    return ledger


def test_ai_cost_report_table_and_json(mock_spend_env: SpendLedger) -> None:
    """Verify devops ai cost report in table and json formats."""
    # Test JSON report
    res_json = runner.invoke(cost_app, ["report", "--json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.stdout)
    assert (
        data["total_requests"],
        data["total_tokens"],
        len(data["servers"]),
        data["servers"][0]["server"],
    ) == (
        1,
        1500,
        1,
        "localhost:11434",
    )

    # Test Table report
    res_table = runner.invoke(cost_app, ["report", "--by", "model"])
    assert (res_table.exit_code, "llama3:8b" in res_table.stdout) == (0, True)


def test_ai_spend_alias_report(mock_spend_env: SpendLedger) -> None:
    """Verify devops ai spend alias executes cost report successfully."""
    res = runner.invoke(ai_app, ["spend", "report", "--json"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert data["total_requests"] == 1


def test_ai_cost_list_pricing(mock_spend_env: SpendLedger) -> None:
    """Verify devops ai cost list-pricing outputs catalog in json and table."""
    res_json = runner.invoke(cost_app, ["list-pricing", "--json"])
    assert res_json.exit_code == 0
    catalog = json.loads(res_json.stdout)
    assert len(catalog) >= 50

    res_table = runner.invoke(cost_app, ["list-pricing", "--search", "llama"])
    assert (res_table.exit_code, "llama" in res_table.stdout.lower()) == (0, True)


def test_ai_cost_set_price(mock_spend_env: SpendLedger) -> None:
    """Verify devops ai cost set-price creates custom override."""
    res = runner.invoke(
        cost_app,
        ["set-price", "custom-model", "0.25", "0.75"],
    )
    assert (res.exit_code, "Configured custom pricing" in res.stdout) == (0, True)

    # Verify override is active in json listing
    res_list = runner.invoke(cost_app, ["list-pricing", "--json"])
    catalog = json.loads(res_list.stdout)
    custom_entry = catalog.get("custom-model")
    assert custom_entry is not None
    assert (
        custom_entry["prompt_usd_per_million"],
        custom_entry["completion_usd_per_million"],
        custom_entry["source"],
    ) == (
        0.25,
        0.75,
        "custom_override",
    )


def test_ai_cost_update_pricing(
    mock_spend_env: SpendLedger, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify devops ai cost update-pricing triggers registry update."""
    monkeypatch.setattr(
        PricingRegistry, "update_from_remote", lambda self, source_url=None, timeout=15.0: 42
    )

    res = runner.invoke(cost_app, ["update-pricing"])
    assert (res.exit_code, "42 models loaded" in res.stdout) == (0, True)


def test_ai_cost_reset(mock_spend_env: SpendLedger) -> None:
    """Verify devops ai cost reset clears ledger when confirmed."""
    # Reset with --yes
    res = runner.invoke(cost_app, ["reset", "--yes"])
    assert (res.exit_code, "cleared" in res.stdout.lower()) == (0, True)

    # Verify report is now empty
    res_report = runner.invoke(cost_app, ["report", "--json"])
    data = json.loads(res_report.stdout)
    assert data["total_requests"] == 0
