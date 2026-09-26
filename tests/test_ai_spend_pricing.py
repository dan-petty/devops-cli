"""Unit tests for AI open-source pricing registry, matching heuristics, and catalog management."""

from __future__ import annotations

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

    p_exact = registry.get_pricing("gpt-4o")
    p_claude = registry.get_pricing("claude-3-5-sonnet-20241022")
    p_deepseek = registry.get_pricing("deepseek/deepseek-chat")

    assert (
        (p_exact.prompt_usd_per_million, p_exact.completion_usd_per_million),
        (p_claude.prompt_usd_per_million, p_claude.completion_usd_per_million),
        (p_deepseek.prompt_usd_per_million, p_deepseek.completion_usd_per_million),
    ) == (
        (2.5, 10.0),
        (3.0, 15.0),
        (0.135, 0.55),
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
