"""Unit tests for AI open-source pricing registry, matching heuristics, and catalog management."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import genai_prices
import pytest
from genai_prices.data_snapshot import DataSnapshot, set_custom_snapshot
from genai_prices.types import _providers_from_raw

from devops_cli.ai.spend.models import ModelPricing
from devops_cli.ai.spend.pricing import PricingRegistry


def test_pricing_registry_offline_defaults(tmp_path: Path) -> None:
    """Verify PricingRegistry loads genai-prices bundled snapshot with 1,000+ models."""
    registry = PricingRegistry(data_dir=tmp_path)
    catalog = registry.list_all_pricing()

    assert (len(catalog) >= 500, "gpt-4o" in catalog, "claude-3-5-sonnet" in catalog) == (
        True,
        True,
        True,
    )


def test_pricing_registry_exact_and_normalized_matching(tmp_path: Path) -> None:
    """Verify exact and normalized model lookup resolution via genai-prices."""
    registry = PricingRegistry(data_dir=tmp_path)
    peak_ts = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    p_exact = registry.get_pricing("gpt-4o", request_timestamp=peak_ts)
    p_claude = registry.get_pricing("claude-3-5-sonnet-20241022", request_timestamp=peak_ts)
    p_deepseek = registry.get_pricing("deepseek/deepseek-chat", request_timestamp=peak_ts)

    assert (
        (p_exact.prompt_usd_per_million, p_exact.completion_usd_per_million),
        (p_claude.prompt_usd_per_million, p_claude.completion_usd_per_million),
        (p_deepseek.prompt_usd_per_million, p_deepseek.completion_usd_per_million),
    ) == (
        (2.5, 10.0),
        (3.0, 15.0),
        (0.27, 1.1),
    )


def test_pricing_registry_local_calls_zero_cost(tmp_path: Path) -> None:
    """Verify local and ollama calls cost nothing unless overridden."""
    registry = PricingRegistry(data_dir=tmp_path)

    p_ollama = registry.get_pricing(
        "qwen2.5-coder:7b", server="http://localhost:11434", provider="ollama"
    )
    p_localhost = registry.get_pricing("gpt-4o", server="http://localhost:11434", provider="ollama")
    p_loopback_ip = registry.get_pricing("custom-model", server="http://127.0.0.1:8000")
    p_direct = registry.get_pricing("llama3:8b", server="direct")
    p_unknown_remote = registry.get_pricing("some-completely-unknown-cloud-model")

    assert (
        (p_ollama.prompt_usd_per_million, p_ollama.completion_usd_per_million, p_ollama.source),
        (
            p_localhost.prompt_usd_per_million,
            p_localhost.completion_usd_per_million,
            p_localhost.source,
        ),
        (
            p_loopback_ip.prompt_usd_per_million,
            p_loopback_ip.completion_usd_per_million,
            p_loopback_ip.source,
        ),
        (p_direct.prompt_usd_per_million, p_direct.completion_usd_per_million, p_direct.source),
        (
            p_unknown_remote.prompt_usd_per_million,
            p_unknown_remote.completion_usd_per_million,
            p_unknown_remote.source,
        ),
    ) == (
        (0.0, 0.0, "local"),
        (0.0, 0.0, "local"),
        (0.0, 0.0, "local"),
        (0.0, 0.0, "local"),
        (0.0, 0.0, "unknown"),
    )


def test_pricing_registry_custom_overrides(tmp_path: Path) -> None:
    """Verify custom pricing override setting, persistence, and lookup priority over local."""
    registry = PricingRegistry(data_dir=tmp_path)

    registry.set_custom_pricing("qwen2.5-coder:7b", prompt_rate=0.15, completion_rate=0.30)
    registry.set_custom_pricing("http://localhost:11434", prompt_rate=0.05, completion_rate=0.10)

    # Model override takes priority even on local server
    resolved_model = registry.get_pricing(
        "qwen2.5-coder:7b", server="http://localhost:11434", provider="ollama"
    )
    assert (
        resolved_model.prompt_usd_per_million,
        resolved_model.completion_usd_per_million,
        resolved_model.source,
    ) == (
        0.15,
        0.30,
        "custom_override",
    )

    # Server override applies when model has no override
    resolved_server = registry.get_pricing(
        "other-model", server="http://localhost:11434", provider="ollama"
    )
    assert (
        resolved_server.prompt_usd_per_million,
        resolved_server.completion_usd_per_million,
        resolved_server.source,
    ) == (
        0.05,
        0.10,
        "custom_override",
    )

    # Recreate registry from disk cache to ensure persistence
    reloaded_registry = PricingRegistry(data_dir=tmp_path)
    reloaded = reloaded_registry.get_pricing(
        "qwen2.5-coder:7b", server="http://localhost:11434", provider="ollama"
    )
    assert (
        reloaded.prompt_usd_per_million,
        reloaded.completion_usd_per_million,
        reloaded.source,
    ) == (
        0.15,
        0.30,
        "custom_override",
    )


def test_pricing_registry_cost_calculation(tmp_path: Path) -> None:
    """Verify exact approximate USD calculation for prompt and completion tokens."""
    pricing = ModelPricing(
        prompt_usd_per_million=2.00,
        completion_usd_per_million=6.00,
    )

    # 1,000,000 prompt tokens ($2.00) + 500,000 completion tokens ($3.00) = $5.00
    cost = pricing.calculate_cost(prompt_tokens=1_000_000, completion_tokens=500_000)
    # 1,000 prompt tokens ($0.002) + 500 completion tokens ($0.003) = $0.005
    cost_small = pricing.calculate_cost(prompt_tokens=1_000, completion_tokens=500)

    assert (cost, cost_small) == (5.0, 0.005)


def test_pricing_registry_remote_catalog_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify remote synchronization using genai-prices updater."""
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
    mock_snapshot = DataSnapshot(_providers_from_raw(raw), from_auto_update=True)

    class MockUpdater:
        def __init__(self, **kwargs: object) -> None:
            self.request_timeout = 15.0

        def fetch(self) -> DataSnapshot:
            return mock_snapshot

    monkeypatch.setattr(genai_prices, "UpdatePrices", MockUpdater)

    try:
        registry = PricingRegistry(data_dir=tmp_path)
        count = registry.update_from_remote()

        assert count == 1
        updated_pricing = registry.get_pricing("mock-custom-model")
        assert (
            updated_pricing.prompt_usd_per_million,
            updated_pricing.completion_usd_per_million,
            updated_pricing.source,
        ) == (
            4.0,
            12.0,
            "genai_prices:mock-provider",
        )
    finally:
        set_custom_snapshot(None)


def test_pricing_registry_tiered_models_rates_and_costs(tmp_path: Path) -> None:
    """Verify tiered models don't get double-priced for base rates and calculate exact costs."""
    registry = PricingRegistry(data_dir=tmp_path)

    # Base rates per million must come from small usage (<200k), not >200k tiered rates
    p_sonnet = registry.get_pricing("claude-sonnet-4-5")
    assert (p_sonnet.prompt_usd_per_million, p_sonnet.completion_usd_per_million) == (3.0, 15.0)

    # Exact call calculation with 20K input and 2K output tokens:
    # 20_000 * 3.0 / 1_000_000 = 0.06
    # 2_000 * 15.0 / 1_000_000 = 0.03
    # Total = 0.09
    exact_cost = registry.calculate_request_cost(
        "claude-sonnet-4-5",
        prompt_tokens=20_000,
        completion_tokens=2_000,
    )
    assert exact_cost == 0.09


def test_pricing_registry_update_from_file_and_persistence(tmp_path: Path) -> None:
    """Verify updating pricing from a local file persists snapshot and reloads on startup."""
    import json

    custom_data = [
        {
            "id": "file-provider",
            "name": "File Provider",
            "api_pattern": ".*",
            "model_match": {"contains": "file"},
            "models": [
                {
                    "id": "file-custom-model",
                    "name": "File Custom Model",
                    "match": {"equals": "file-custom-model"},
                    "prices": {"input_mtok": 5.0, "output_mtok": 15.0},
                }
            ],
        }
    ]
    file_path = tmp_path / "custom_prices.json"
    file_path.write_text(json.dumps(custom_data), encoding="utf-8")

    try:
        registry = PricingRegistry(data_dir=tmp_path)
        count = registry.update_from_remote(source_url=str(file_path))
        assert count == 1

        pricing = registry.get_pricing("file-custom-model")
        assert (pricing.prompt_usd_per_million, pricing.completion_usd_per_million) == (5.0, 15.0)

        # Verify snapshot file exists
        assert (tmp_path / "ai" / "pricing_snapshot.json").is_file()

        # Recreating registry reloads the snapshot from disk
        reloaded = PricingRegistry(data_dir=tmp_path)
        p_reloaded = reloaded.get_pricing("file-custom-model")
        assert (p_reloaded.prompt_usd_per_million, p_reloaded.completion_usd_per_million) == (
            5.0,
            15.0,
        )
    finally:
        set_custom_snapshot(None)
