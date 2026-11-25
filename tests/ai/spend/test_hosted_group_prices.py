"""Each hosted gateway group has a price, and cached prompt tokens cost the cached input rate.

The Service sends every chat slot to a hosted gateway group. A group that nothing prices records
its calls at $0, so the spend counters, `devops ai cost` and the spend alerts cannot see them
(#4403). The price must not depend on a hand-set ConfigMap or file, so these tests build the
registry with no settings and no file.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from genai_prices.data_snapshot import set_custom_snapshot

from devops_cli.ai.spend.pricing import PricingRegistry
from devops_cli.config.settings import AIConfig, AIPriceOverride, Settings

# A call to the gateway in the cluster: the host is local, so only the reply names make it hosted.
_GATEWAY_CALL: dict[str, Any] = {
    "server": "llm-gateway.llm.svc.cluster.local:4000",
    "provider": "gateway",
}
# Below the 100,000-token tier of Claude Haiku 5.5, which the gateway does not price. Of the
# prompt tokens, 6,000 are cache reads and 2,000 are cache writes (#3658).
_PROMPT, _CACHED, _WRITTEN, _COMPLETION = 10_000, 6_000, 2_000, 1_000


@pytest.fixture(autouse=True)
def _reset_process_snapshot() -> Generator[None]:
    """Reset the genai-prices snapshot of the process before and after each test."""
    set_custom_snapshot(None)
    yield
    set_custom_snapshot(None)


def test_a_price_with_a_cached_input_rate_prices_cached_prompt_tokens_at_that_rate(
    tmp_path: Path,
) -> None:
    """Of 1,000,000 prompt tokens, 400,000 are new at 1.00 USD per million and 600,000 come from
    the cache of the provider at 0.10 USD per million."""
    settings = Settings(
        ai=AIConfig(
            price_overrides={
                "cached-model": AIPriceOverride(
                    prompt_usd_per_million=1.0,
                    completion_usd_per_million=2.0,
                    cache_read_usd_per_million=0.1,
                )
            }
        )
    )
    registry = PricingRegistry(data_dir=tmp_path, settings=settings)

    cost = registry.calculate_request_cost(
        "cached-model",
        1_000_000,
        0,
        cache_read_tokens=600_000,
        server="https://api.example.com",
        provider="openai",
    )

    assert cost.cost_usd == 0.46


def test_a_price_with_no_cached_input_rate_prices_cached_prompt_tokens_at_the_prompt_rate(
    tmp_path: Path,
) -> None:
    """A price that names no cached input rate keeps the prompt rate for every prompt token."""
    settings = Settings(
        ai=AIConfig(
            price_overrides={
                "plain-model": AIPriceOverride(
                    prompt_usd_per_million=1.0, completion_usd_per_million=2.0
                )
            }
        )
    )
    registry = PricingRegistry(data_dir=tmp_path, settings=settings)

    cost = registry.calculate_request_cost(
        "plain-model",
        1_000_000,
        0,
        cache_read_tokens=600_000,
        server="https://api.example.com",
        provider="openai",
    )

    assert cost.cost_usd == 1.0


def test_a_setting_for_a_hosted_group_wins_over_the_built_in_price(tmp_path: Path) -> None:
    """A person can set another price for a group in `ai.price_overrides`, as for any model."""
    settings = Settings(
        ai=AIConfig(
            price_overrides={
                "deepseek-v4.1-flash-1017": AIPriceOverride(
                    prompt_usd_per_million=1.0, completion_usd_per_million=1.0
                )
            }
        )
    )
    registry = PricingRegistry(data_dir=tmp_path, settings=settings)

    cost = registry.calculate_request_cost(
        "deepseek-v4.1-flash-1017",
        1_000_000,
        0,
        served_model="deepseek-v4.1-flash-1017",
        **_GATEWAY_CALL,
    )

    assert (cost.cost_usd, cost.pricing_source) == (1.0, "settings:ai.price_overrides")
