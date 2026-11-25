"""The tokens and the spend of a live run of the golden set (#3207)."""

from __future__ import annotations

from devops_cli.ai.spend.pricing import get_pricing_registry
from devops_cli.roadmap.stage.stage_eval_usage import RunUsage


def test_the_tokens_of_the_calls_add_up_and_a_cached_call_adds_none() -> None:
    usage = RunUsage()

    usage.add({"prompt_tokens": 100, "completion_tokens": 10})
    usage.add({"prompt_tokens": 50, "completion_tokens": None})
    usage.add({"prompt_tokens": 9999, "completion_tokens": 999, "cached": True})

    assert (usage.input_tokens, usage.output_tokens) == (150, 10)


def test_the_spend_is_the_hosted_price_of_the_tokens_and_none_for_a_model_with_no_price() -> None:
    usage = RunUsage(input_tokens=1_000_000, output_tokens=100_000)

    assert usage.spend_usd("claude-sonnet-5-5") == 3.0
    assert usage.spend_usd("no-such-model-1") is None


def test_cache_read_and_write_tokens_sum_and_lower_eval_spend() -> None:
    """`RunUsage` sums cache counts across non-cached calls and passes them to pricing (#5578)."""
    usage = RunUsage()
    usage.add(
        {
            "prompt_tokens": 6000,
            "completion_tokens": 500,
            "cache_read_tokens": 5000,
            "cache_write_tokens": 500,
        }
    )
    usage.add(
        {
            "prompt_tokens": 4000,
            "completion_tokens": 500,
            "cache_read_tokens": 3000,
            "cache_write_tokens": 500,
        }
    )
    usage.add(
        {
            "prompt_tokens": 9999,
            "completion_tokens": 999,
            "cache_read_tokens": 9000,
            "cache_write_tokens": 900,
            "cached": True,
        }
    )

    assert (usage.cache_read_tokens, usage.cache_write_tokens) == (8000, 1000)
    expected = get_pricing_registry().calculate_request_cost(
        "claude-sonnet-5-5",
        10_000,
        1_000,
        cache_read_tokens=8_000,
        cache_write_tokens=1_000,
    )
    without_cache = get_pricing_registry().calculate_request_cost(
        "claude-sonnet-5-5",
        10_000,
        1_000,
    )
    spend = usage.spend_usd("claude-sonnet-5-5")
    assert spend == expected.cost_usd
    assert spend is not None
    assert spend < without_cache.cost_usd
