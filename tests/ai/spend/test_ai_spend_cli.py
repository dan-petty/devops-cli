"""Unit and CLI integration tests for devops ai cost and spend commands."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx2
import pytest

from devops_cli.ai.client import LLMClient
from devops_cli.ai.spend.ledger import SpendLedger, get_spend_ledger, reset_spend_ledger
from devops_cli.ai.spend.pricing import (
    reset_pricing_registry,
)
from devops_cli.config.settings import AIConfig
from tests.support.fakes.http import WebFake


@pytest.fixture
def mock_spend_env(isolate_data_dir: Path) -> Iterator[SpendLedger]:
    """Fixture initializing isolated temporary SpendLedger and PricingRegistry."""
    reset_spend_ledger()
    reset_pricing_registry()
    ledger = get_spend_ledger()

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
    yield ledger
    reset_spend_ledger()
    reset_pricing_registry()


def test_ai_cost_report_table_and_json(
    cli: Callable[..., Any], mock_spend_env: SpendLedger
) -> None:
    """Verify devops ai cost report in table and json formats."""
    # Test JSON report
    res_json = cli("ai", "cost", "report", "--json")
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
    res_table = cli("ai", "cost", "report", "--by", "model")
    assert (res_table.exit_code, "llama3:8b" in res_table.stdout) == (0, True)


def test_ai_spend_alias_report(cli: Callable[..., Any], mock_spend_env: SpendLedger) -> None:
    """Verify devops ai spend alias executes cost report successfully."""
    res = cli("ai", "spend", "report", "--json")
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert data["total_requests"] == 1


def test_ai_cost_list_pricing(cli: Callable[..., Any], mock_spend_env: SpendLedger) -> None:
    """Verify devops ai cost list-pricing outputs catalog in json, yaml, and table with base rate captions."""
    import yaml

    res_json = cli("ai", "cost", "list-pricing", "--json")
    assert res_json.exit_code == 0
    catalog = json.loads(res_json.stdout)
    assert len(catalog) >= 50

    # YAML output format
    res_yaml = cli("ai", "cost", "list-pricing", "--format", "yaml")
    assert (res_yaml.exit_code, yaml.safe_load(res_yaml.stdout) == catalog) == (0, True)

    # Table output with search, column headers, and caption
    res_table = cli("ai", "cost", "list-pricing", "--search", "llama")
    assert (
        res_table.exit_code,
        "llama" in res_table.stdout.lower(),
        "Base Prompt USD / 1M" in res_table.stdout,
        "Base Completion USD / 1M" in res_table.stdout,
        "base-tier rates for a small call at current time" in res_table.stdout.lower(),
    ) == (0, True, True, True, True)

    # Help text states base-tier rates
    res_help = cli("ai", "cost", "list-pricing", "--help")
    assert (res_help.exit_code, "base-tier rates" in res_help.stdout.lower()) == (0, True)


def test_ai_cost_set_price(cli: Callable[..., Any], mock_spend_env: SpendLedger) -> None:
    """Verify devops ai cost set-price creates custom override."""
    res = cli("ai", "cost", "set-price", "custom-model", "0.25", "0.75")
    assert (res.exit_code, "Configured custom pricing" in res.stdout) == (0, True)

    # Verify override is active in json listing
    res_list = cli("ai", "cost", "list-pricing", "--json")
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
    mock_spend_env: SpendLedger, cli: Callable[..., Any], web: WebFake
) -> None:
    """Verify devops ai cost update-pricing triggers registry update and reports model counts."""
    raw = [
        {
            "id": "mock-provider",
            "name": "Mock Provider",
            "api_pattern": ".*",
            "model_match": {"contains": "mock"},
            "models": [
                {
                    "id": "mock-custom-model",
                    "name": "Mock Custom Model",
                    "match": {"equals": "mock-custom-model"},
                    "prices": {"input_mtok": 4.0, "output_mtok": 12.0},
                }
            ],
        }
    ]
    web.serve(lambda request: httpx2.Response(200, json=raw))

    res = cli("ai", "cost", "update-pricing")
    assert (
        res.exit_code,
        "1 models supplied" in res.stdout,
    ) == (0, True)


def test_ai_cost_update_pricing_reset(cli: Callable[..., Any], isolate_data_dir: Path) -> None:
    """Verify devops ai cost update-pricing --reset clears snapshot and caches."""
    reset_pricing_registry()

    # Exits 0 if file is absent
    res_absent = cli("ai", "cost", "update-pricing", "--reset")
    assert (
        res_absent.exit_code,
        "Successfully reset pricing snapshot" in res_absent.stdout,
    ) == (0, True)

    # When file exists, deletes it and exits 0
    snap_file = isolate_data_dir / "ai" / "pricing_snapshot.json"
    snap_file.parent.mkdir(parents=True, exist_ok=True)
    snap_file.write_text("{}", encoding="utf-8")
    assert snap_file.exists()

    res_present = cli("ai", "cost", "update-pricing", "--reset")
    assert (
        res_present.exit_code,
        snap_file.exists(),
        "Successfully reset pricing snapshot" in res_present.stdout,
    ) == (0, False, True)


def test_ai_cost_update_pricing_reset_and_source_conflict(
    cli: Callable[..., Any], mock_spend_env: SpendLedger
) -> None:
    """Verify combining --reset with --source raises a usage error."""
    res = cli(
        "ai", "cost", "update-pricing", "--reset", "--source", "https://example.com/pricing.json"
    )
    assert (res.exit_code, "Cannot combine --reset with --source" in res.output) == (2, True)


def test_ai_cost_reset(cli: Callable[..., Any], mock_spend_env: SpendLedger) -> None:
    """Verify devops ai cost reset clears ledger when confirmed."""
    # Reset with --yes
    res = cli("ai", "cost", "reset", "--yes")
    assert (res.exit_code, "cleared" in res.stdout.lower()) == (0, True)

    # Verify report is now empty
    res_report = cli("ai", "cost", "report", "--json")
    data = json.loads(res_report.stdout)
    assert data["total_requests"] == 0


def test_ai_cost_report_counterfactual_and_hardware_payoff(
    cli: Callable[..., Any], mock_spend_env: SpendLedger
) -> None:
    """Verify devops ai cost report displays counterfactual pricing and hardware payoff."""
    res_table = cli(
        "ai", "cost", "report", "--reference-model", "gpt-4o", "--hardware-cost", "200.0"
    )
    res_json = cli(
        "ai", "cost", "report", "--reference-model", "gpt-4o", "--hardware-cost", "200.0", "--json"
    )
    data = json.loads(res_json.stdout)

    assert (
        res_table.exit_code,
        "Local Calls Hosted Equivalent" in res_table.stdout,
        "All-Hosted Counterfactual Spend" in res_table.stdout,
        "Estimated Cloud Spend Avoided" in res_table.stdout,
        "Local Hardware Investment & Cloud Savings Pay-Off" in res_table.stdout,
        res_json.exit_code,
        data["reference_model"],
        data["hardware_cost_usd"],
        data["hardware_payoff"] is not None,
    ) == (
        0,
        True,
        True,
        True,
        True,
        0,
        "gpt-4o",
        200.0,
        True,
    )


def test_ai_cost_roi_reports_hardware_payoff(
    cli: Callable[..., Any], mock_spend_env: SpendLedger
) -> None:
    """Verify devops ai cost roi outputs hardware payoff in table and json formats."""
    res_table = cli("ai", "cost", "roi", "--hardware-cost", "1500.0")
    res_json = cli("ai", "cost", "roi", "--hardware-cost", "1500.0", "--json")
    data = json.loads(res_json.stdout)

    res_payoff = cli("ai", "cost", "payoff", "--hardware-cost", "1500.0", "--json")
    res_payback = cli("ai", "cost", "payback", "--hardware-cost", "1500.0", "--json")

    assert (
        res_table.exit_code,
        "Local Hardware Investment & Cloud Savings Pay-Off" in res_table.stdout,
        res_json.exit_code,
        data["hardware_cost_usd"],
        data["is_paid_off"],
        res_payoff.exit_code,
        res_payback.exit_code,
    ) == (
        0,
        True,
        0,
        1500.0,
        False,
        0,
        0,
    )


def test_spend_report_counts_a_cache_hit_as_a_cached_request_and_no_backend(
    cli: Callable[..., Any],
    web: WebFake,
    spend_ledger: SpendLedger,
) -> None:
    """Verify one dispatch and one reply the cache answered report 2 requests, 1 cached, and
    one backend server, overall and for the provider; the cache ran no local model (#816)."""
    reply = json.dumps(
        {
            "message": {"role": "assistant", "content": "ok"},
            "prompt_eval_count": 100,
            "eval_count": 20,
        }
    )
    web.serve(lambda request: httpx2.Response(200, content=reply.encode()))
    client = LLMClient(
        AIConfig(provider="ollama", model="llama3:8b", ollama_urls=["http://localhost:11434"])
    )
    for _ in range(2):
        client.chat("system", "user", use_cache=True)

    res = cli("ai", "spend", "report", "--json")
    data = json.loads(res.stdout)

    assert (
        res.exit_code,
        (data["total_requests"], data["cached_requests"], data["active_servers_count"]),
        [(p["provider"], p["request_count"], p["server_count"]) for p in data["providers"]],
        data["local_requests"],
    ) == (0, (2, 1, 1), [("ollama", 2, 1)], 1)


def test_ai_cost_report_reasoning_share_columns(
    cli: Callable[..., Any], mock_spend_env: SpendLedger
) -> None:
    """Verify devops ai cost report shows reasoning share column in server and backend tables."""
    # Seed request with reasoning tokens
    mock_spend_env.record_request(
        provider="gateway",
        server="gateway.local:8000",
        model="deepseek-r1",
        prompt_tokens=1000,
        completion_tokens=500,
        reasoning_tokens=250,
        cost_usd=0.001,
        served_by="http://worker-node-1:8000",
        duration_seconds=2.0,
    )

    # Default report (server breakdown)
    res_default = cli("ai", "cost", "report")
    assert res_default.exit_code == 0
    assert "Reasoning Share" in res_default.stdout
    assert "50.0%" in res_default.stdout

    # Backend breakdown
    res_backend = cli("ai", "cost", "report", "--by", "backend")
    assert res_backend.exit_code == 0
    assert "Reasoning Share" in res_backend.stdout
    assert "50.0%" in res_backend.stdout

    # JSON report includes reasoning tokens
    res_json = cli("ai", "cost", "report", "--json")
    assert res_json.exit_code == 0
    data = json.loads(res_json.stdout)
    assert data["total_reasoning_tokens"] == 250
    assert any(b.get("reasoning_tokens") == 250 for b in data["backends"])


def test_ai_cost_report_since_until_by_week_json(
    cli: Callable[..., Any], mock_spend_env: SpendLedger
) -> None:
    """Verify cost report with --since, --until, and --by week produces 3 rows whose sums equal
    the ungrouped report of the range (#2193)."""
    # Clear and seed test records across October 2026
    mock_spend_env.reset()
    records = [
        # Week 1: 2026-10-01 to 2026-10-08
        ("2026-10-02T10:00:00+00:00", 1000, 500, 0.0001),
        # Week 2: 2026-10-08 to 2026-10-15
        ("2026-10-10T14:00:00+00:00", 2000, 1000, 0.0002),
        # Week 3: 2026-10-15 to 2026-10-22
        ("2026-10-20T16:00:00+00:00", 3000, 1500, 0.0003),
    ]
    for ts, prompt, comp, cost in records:
        mock_spend_env.record_request(
            provider="ollama",
            server="localhost:11434",
            model="llama3:8b",
            prompt_tokens=prompt,
            completion_tokens=comp,
            cost_usd=cost,
            timestamp=ts,
        )

    res = cli(
        "ai",
        "cost",
        "report",
        "--since",
        "2026-10-01",
        "--until",
        "2026-10-22",
        "--by",
        "week",
        "--json",
    )
    assert res.exit_code == 0
    weekly_rows = json.loads(res.stdout)
    assert len(weekly_rows) == 3
    assert [r["period"] for r in weekly_rows] == ["2026-10-01", "2026-10-08", "2026-10-15"]
    assert [r["requests"] for r in weekly_rows] == [1, 1, 1]

    # Compare with ungrouped report for the same range
    res_ungrouped = cli(
        "ai", "cost", "report", "--since", "2026-10-01", "--until", "2026-10-22", "--json"
    )
    assert res_ungrouped.exit_code == 0
    ungrouped = json.loads(res_ungrouped.stdout)

    assert sum(r["requests"] for r in weekly_rows) == ungrouped["total_requests"]
    assert sum(r["local_tokens"] for r in weekly_rows) == ungrouped["local_tokens"]
    assert round(sum(r["actual_spend"] for r in weekly_rows), 6) == round(
        ungrouped["total_spend_usd"], 6
    )
    assert round(sum(r["local_cost_equivalent"] or 0.0 for r in weekly_rows), 6) == round(
        ungrouped["local_cost_equivalent_usd"] or 0.0, 6
    )
    assert round(sum(r["cloud_spend_avoided"] or 0.0 for r in weekly_rows), 6) == round(
        ungrouped["counterfactual_savings_usd"] or 0.0, 6
    )


def test_ai_cost_roi_since_until_by_week_json(
    cli: Callable[..., Any], mock_spend_env: SpendLedger
) -> None:
    """Verify cost roi with --since, --until, and --by week returns expected columns and grouping (#2193)."""
    mock_spend_env.reset()
    mock_spend_env.record_request(
        provider="ollama",
        server="localhost:11434",
        model="llama3:8b",
        prompt_tokens=1000,
        completion_tokens=500,
        cost_usd=0.0001,
        timestamp="2026-10-05T10:00:00+00:00",
    )
    mock_spend_env.record_request(
        provider="ollama",
        server="localhost:11434",
        model="llama3:8b",
        prompt_tokens=2000,
        completion_tokens=1000,
        cost_usd=0.0002,
        timestamp="2026-10-18T10:00:00+00:00",
    )

    res = cli(
        "ai",
        "cost",
        "roi",
        "--since",
        "2026-10-01",
        "--until",
        "2026-10-22",
        "--by",
        "week",
        "--json",
    )
    assert res.exit_code == 0
    rows = json.loads(res.stdout)
    assert len(rows) == 3
    for row in rows:
        assert "requests" in row
        assert "local_tokens" in row
        assert "actual_spend" in row
        assert "local_cost_equivalent" in row
        assert "cloud_spend_avoided" in row

    assert [r["requests"] for r in rows] == [1, 0, 1]


def test_ai_cost_days_is_short_form_of_since(
    cli: Callable[..., Any], mock_spend_env: SpendLedger
) -> None:
    """Verify --days N is equivalent to --since set to N days ago (#2193)."""
    from datetime import UTC, datetime, timedelta

    mock_spend_env.reset()
    now = datetime.now(UTC)
    mock_spend_env.record_request(
        provider="ollama",
        server="localhost:11434",
        model="llama3:8b",
        prompt_tokens=100,
        completion_tokens=50,
        cost_usd=0.0001,
        timestamp=(now - timedelta(days=2)).isoformat(),
    )
    mock_spend_env.record_request(
        provider="ollama",
        server="localhost:11434",
        model="llama3:8b",
        prompt_tokens=200,
        completion_tokens=100,
        cost_usd=0.0002,
        timestamp=(now - timedelta(days=12)).isoformat(),
    )

    since_ts = (now - timedelta(days=7)).isoformat()
    res_days = cli("ai", "cost", "report", "--days", "7", "--json")
    res_since = cli("ai", "cost", "report", "--since", since_ts, "--json")

    assert res_days.exit_code == 0
    assert res_since.exit_code == 0
    data_days = json.loads(res_days.stdout)
    data_since = json.loads(res_since.stdout)
    assert data_days["total_requests"] == data_since["total_requests"] == 1


def test_ai_cost_conflicting_days_and_since(
    cli: Callable[..., Any], mock_spend_env: SpendLedger
) -> None:
    """Verify combining --days and --since raises a usage error (#2193)."""
    res = cli("ai", "cost", "report", "--days", "7", "--since", "2026-10-01")
    assert res.exit_code == 2
    assert "Cannot combine --days with --since" in res.output


def test_ai_cost_report_and_roi_table_period_output(
    cli: Callable[..., Any], mock_spend_env: SpendLedger
) -> None:
    """Verify table format output with --by week for report and roi (#2193)."""
    mock_spend_env.reset()
    mock_spend_env.record_request(
        provider="ollama",
        server="localhost:11434",
        model="llama3:8b",
        prompt_tokens=1000,
        completion_tokens=500,
        cost_usd=0.0001,
        timestamp="2026-10-05T10:00:00+00:00",
    )

    res_report = cli(
        "ai", "cost", "report", "--since", "2026-10-01", "--until", "2026-10-22", "--by", "week"
    )
    assert res_report.exit_code == 0
    assert "AI Spend & ROI by Week" in res_report.stdout
    assert "Local Tokens" in res_report.stdout
    assert "Cloud Spend Avoided" in res_report.stdout

    res_roi = cli(
        "ai", "cost", "roi", "--since", "2026-10-01", "--until", "2026-10-22", "--by", "week"
    )
    assert res_roi.exit_code == 0
    assert "AI Spend & ROI by Week" in res_roi.stdout


def test_ai_cost_range_validation_cli_errors(
    cli: Callable[..., Any], mock_spend_env: SpendLedger
) -> None:
    """Verify validation of malformed and inverted range parameters (#2193)."""
    res_bad_since = cli("ai", "cost", "report", "--since", "not-a-date")
    assert res_bad_since.exit_code == 2
    assert "Invalid ISO date or datetime" in res_bad_since.output

    res_bad_until = cli("ai", "cost", "report", "--until", "not-a-date")
    assert res_bad_until.exit_code == 2
    assert "Invalid ISO date or datetime" in res_bad_until.output

    res_inverted = cli("ai", "cost", "report", "--since", "2026-10-20", "--until", "2026-10-10")
    assert res_inverted.exit_code == 2
    assert "--until cannot be earlier than --since" in res_inverted.output

    res_bad_roi_by = cli("ai", "cost", "roi", "--by", "month")
    assert res_bad_roi_by.exit_code == 2
    assert "Invalid grouping 'month' for roi" in res_bad_roi_by.output


def test_ai_cost_period_formats_and_aliases(
    cli: Callable[..., Any], mock_spend_env: SpendLedger
) -> None:
    """Verify period reports across output formats and command aliases (#2193)."""
    mock_spend_env.reset()
    # Empty period table output when no spend records exist
    res_empty_table = cli("ai", "cost", "report", "--by", "day")
    assert res_empty_table.exit_code == 0
    assert "No spend records found" in res_empty_table.stdout

    mock_spend_env.record_request(
        provider="ollama",
        server="localhost:11434",
        model="llama3:8b",
        prompt_tokens=500,
        completion_tokens=250,
        cost_usd=0.0001,
        timestamp="2026-10-05T10:00:00+00:00",
    )

    # YAML format on report
    res_yaml = cli(
        "ai",
        "cost",
        "report",
        "--since",
        "2026-10-01",
        "--until",
        "2026-10-22",
        "--by",
        "week",
        "--format",
        "yaml",
    )
    assert res_yaml.exit_code == 0
    assert "period: '2026-10-01'" in res_yaml.stdout or "period: 2026-10-01" in res_yaml.stdout

    # devops ai cost (cost_default) with period breakdown
    res_default = cli(
        "ai", "cost", "--since", "2026-10-01", "--until", "2026-10-22", "--by", "week", "--json"
    )
    assert res_default.exit_code == 0
    assert len(json.loads(res_default.stdout)) == 3

    # devops ai cost payoff with period breakdown
    res_payoff = cli(
        "ai",
        "cost",
        "payoff",
        "--since",
        "2026-10-01",
        "--until",
        "2026-10-22",
        "--by",
        "week",
        "--json",
    )
    assert res_payoff.exit_code == 0
    assert len(json.loads(res_payoff.stdout)) == 3

    # devops ai cost payback with period breakdown
    res_payback = cli(
        "ai",
        "cost",
        "payback",
        "--since",
        "2026-10-01",
        "--until",
        "2026-10-22",
        "--by",
        "week",
        "--json",
    )
    assert res_payback.exit_code == 0
    assert len(json.loads(res_payback.stdout)) == 3
