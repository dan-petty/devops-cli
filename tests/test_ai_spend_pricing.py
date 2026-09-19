"""Unit tests for AI open-source pricing registry, matching heuristics, and catalog management."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.ai.spend.models import ModelPricing
from devops_cli.ai.spend.pricing import PricingRegistry


def test_pricing_registry_offline_defaults(tmp_path: Path) -> None:
    """Verify PricingRegistry loads rich offline defaults with 60+ models."""
    registry = PricingRegistry(data_dir=tmp_path)
    catalog = registry.list_all_pricing()

    assert len(catalog) >= 50
    assert ("gpt-4o" in catalog, "claude-3-5-sonnet-20241022" in catalog) == (True, True)


def test_pricing_registry_exact_and_normalized_matching(tmp_path: Path) -> None:
    """Verify exact and normalized model lookup resolution."""
    registry = PricingRegistry(data_dir=tmp_path)

    p_exact = registry.get_pricing("gpt-4o")
    p_ollama = registry.get_pricing("ollama/llama3:8b")
    p_deepseek = registry.get_pricing("deepseek/deepseek-chat")

    assert (
        p_exact.prompt_usd_per_million > 0,
        p_ollama.prompt_usd_per_million > 0,
        p_deepseek.prompt_usd_per_million > 0,
    ) == (
        True,
        True,
        True,
    )


def test_pricing_registry_parameter_bracket_heuristics(tmp_path: Path) -> None:
    """Verify parameter-bracket heuristic pricing for unknown self-hosted models."""
    registry = PricingRegistry(data_dir=tmp_path)

    # Unknown 7B model -> <10B bracket ($0.15 / $0.30)
    p_7b = registry.get_pricing("custom-coder-7b-instruct")
    # Unknown 14B model -> 10B-35B bracket ($0.30 / $0.60)
    p_14b = registry.get_pricing("custom-finance-14b-q4")
    # Unknown 70B model -> 36B-100B bracket ($0.70 / $1.00)
    p_70b = registry.get_pricing("custom-general-70b-v2")
    # Unknown 120B model -> >100B bracket ($1.50 / $3.00)
    p_120b = registry.get_pricing("custom-mega-120b")
    # Generic unknown model without size tag -> default fallback ($0.50 / $1.00)
    p_generic = registry.get_pricing("some-completely-unknown-model")

    assert (
        (p_7b.prompt_usd_per_million, p_7b.completion_usd_per_million),
        (p_14b.prompt_usd_per_million, p_14b.completion_usd_per_million),
        (p_70b.prompt_usd_per_million, p_70b.completion_usd_per_million),
        (p_120b.prompt_usd_per_million, p_120b.completion_usd_per_million),
        (p_generic.prompt_usd_per_million, p_generic.completion_usd_per_million),
    ) == (
        (0.15, 0.30),
        (0.30, 0.60),
        (0.70, 1.00),
        (1.50, 3.00),
        (0.50, 1.00),
    )


def test_pricing_registry_custom_overrides(tmp_path: Path) -> None:
    """Verify custom pricing override setting, persistence, and lookup priority."""
    registry = PricingRegistry(data_dir=tmp_path)

    registry.set_custom_pricing("custom-internal-model", prompt_rate=0.05, completion_rate=0.15)

    # Lookup should return the custom override
    resolved = registry.get_pricing("custom-internal-model")
    assert (
        resolved.prompt_usd_per_million,
        resolved.completion_usd_per_million,
        resolved.source,
    ) == (
        0.05,
        0.15,
        "custom_override",
    )

    # Recreate registry from disk cache to ensure persistence
    reloaded_registry = PricingRegistry(data_dir=tmp_path)
    reloaded = reloaded_registry.get_pricing("custom-internal-model")
    assert (
        reloaded.prompt_usd_per_million,
        reloaded.completion_usd_per_million,
        reloaded.source,
    ) == (
        0.05,
        0.15,
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
    """Verify remote synchronization and parsing of open-source LiteLLM catalog."""
    mock_remote_data = {
        "sample-remote-model": {
            "input_cost_per_token": 0.000003,
            "output_cost_per_token": 0.000015,
            "litellm_provider": "openai",
        },
        "sample-zero-cost": {
            "input_cost_per_token": 0.0,
            "output_cost_per_token": 0.0,
        },
    }

    class MockResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, object]:
            return mock_remote_data

    class MockClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        def __enter__(self) -> MockClient:
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def get(self, url: str) -> MockResponse:
            return MockResponse()

    monkeypatch.setattr("httpx2.Client", MockClient)

    registry = PricingRegistry(data_dir=tmp_path)
    count = registry.update_from_remote()

    assert count == 2
    updated_pricing = registry.get_pricing("sample-remote-model")
    assert (
        updated_pricing.prompt_usd_per_million,
        updated_pricing.completion_usd_per_million,
    ) == (
        3.0,
        15.0,
    )
