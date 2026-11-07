"""The tokens and the spend of a live run of the golden set (#3207)."""

from __future__ import annotations

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
