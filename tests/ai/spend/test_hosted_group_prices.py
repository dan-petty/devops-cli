"""Each hosted gateway group has a price, and cached prompt tokens cost the cached input rate.

The Service sends every chat slot to a hosted gateway group. A group that nothing prices records
its calls at $0, so the spend counters, `devops ai cost` and the spend alerts cannot see them
(#4403). The price must not depend on a hand-set ConfigMap or file, so these tests build the
registry with no settings and no file.
"""

from __future__ import annotations

import functools
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
import yaml
from genai_prices.data_snapshot import set_custom_snapshot

from devops_cli.ai.spend.pricing import PricingRegistry
from devops_cli.config.constants import CONST_PRICING_SOURCE_LOCAL, CONST_PRICING_SOURCE_UNKNOWN
from devops_cli.config.settings import AIConfig, AIPriceOverride, AITasksConfig, Settings
from tests.support.paths import REPO_ROOT

_GATEWAY_CONFIG = REPO_ROOT / "k8s" / "llm" / "gateway" / "config.yaml"
_SERVICE_CONFIGMAP = REPO_ROOT / "k8s" / "devops" / "configmap.example.yaml"
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


@functools.cache
def _gateway_groups() -> dict[str, tuple[dict[str, Any], ...]]:
    """The deployments of each group of the gateway config, by group name."""
    config = yaml.safe_load(_GATEWAY_CONFIG.read_text(encoding="utf-8"))
    groups: dict[str, list[dict[str, Any]]] = {}
    for entry in config["model_list"]:
        groups.setdefault(entry["model_name"], []).append(entry)
    return {name: tuple(entries) for name, entries in groups.items()}


def _is_hosted(group: str) -> bool:
    """A hosted group sends its calls to a provider: no deployment of it names an API base."""
    return all("api_base" not in d["litellm_params"] for d in _gateway_groups()[group])


def _hosted_deployments() -> list[tuple[str, dict[str, Any]]]:
    return [
        (group, deployment)
        for group, deployments in _gateway_groups().items()
        if _is_hosted(group)
        for deployment in deployments
    ]


def _service_models() -> set[str]:
    """Every chat and embedding model that the Service template names: `ai.model`, the model of
    each task and each tier of the implement ladder."""
    raw = yaml.safe_load(_SERVICE_CONFIGMAP.read_text(encoding="utf-8"))
    settings = Settings.model_validate(yaml.safe_load(raw["data"]["devops-cli.yaml"]))
    tasks = {settings.ai.for_task(name).model for name in AITasksConfig.model_fields}
    ladder = {tier for step in settings.roadmap.implement.ladder.values() for tier in step}
    return {settings.ai.model, *tasks, *ladder}


def test_every_hosted_gateway_group_is_priced_by_its_route_name_and_its_deployment_model(
    tmp_path: Path,
) -> None:
    """An agent run names the route name of the group, which the gateway writes in the reply
    body, and a chat call names the deployment model of the reply header. Both are priced, with
    no setting and no file."""
    registry = PricingRegistry(data_dir=tmp_path)

    unpriced = [
        (group, served)
        for group, deployment in _hosted_deployments()
        for served in (group, deployment["litellm_params"]["model"])
        if registry.calculate_request_cost(
            group, 1_000_000, 1_000_000, served_model=served, **_GATEWAY_CALL
        ).pricing_source
        == CONST_PRICING_SOURCE_UNKNOWN
    ]

    assert unpriced == []


def test_every_model_of_the_service_template_is_a_gateway_group_that_is_priced_or_local(
    tmp_path: Path,
) -> None:
    """A model that the Service uses is a group of the gateway. A hosted group costs money and a
    local group costs nothing, so no call of the Service records the source `unknown`."""
    registry = PricingRegistry(data_dir=tmp_path)
    groups = _gateway_groups()
    models = _service_models()

    def source(model: str) -> str:
        served_by = groups[model][0]["litellm_params"].get("api_base")
        return registry.calculate_request_cost(
            model, 1_000_000, 1_000_000, served_model=model, served_by=served_by, **_GATEWAY_CALL
        ).pricing_source

    sources = {model: source(model) for model in sorted(models & groups.keys())}

    assert (
        sorted(models - groups.keys()),
        {m: s for m, s in sources.items() if s == CONST_PRICING_SOURCE_UNKNOWN},
        {m for m, s in sources.items() if s == CONST_PRICING_SOURCE_LOCAL}
        == {m for m in sources if not _is_hosted(m)},
    ) == ([], {}, True)


def test_the_client_price_of_a_hosted_group_is_the_price_in_the_gateway_config(
    tmp_path: Path,
) -> None:
    """The gateway config sets the input, cached input, cache write and output price of a group
    that the cost map of LiteLLM does not price right. The client prices a call of the group at
    the same rates, so the spend of the client and the spend of the gateway agree. A group that
    sets no cache write price costs a cache write at the input price (#3658)."""
    registry = PricingRegistry(data_dir=tmp_path)
    priced = [
        (group, deployment)
        for group, deployment in _hosted_deployments()
        if "input_cost_per_token" in deployment.get("model_info", {})
    ]

    def gateway_cost(info: dict[str, Any]) -> float:
        cached_rate = float(info.get("cache_read_input_token_cost", info["input_cost_per_token"]))
        write_rate = float(
            info.get("cache_creation_input_token_cost", info["input_cost_per_token"])
        )
        return round(
            (_PROMPT - _CACHED - _WRITTEN) * float(info["input_cost_per_token"])
            + _CACHED * cached_rate
            + _WRITTEN * write_rate
            + _COMPLETION * float(info["output_cost_per_token"]),
            6,
        )

    costs = {
        group: (
            registry.calculate_request_cost(
                group,
                _PROMPT,
                _COMPLETION,
                cache_read_tokens=_CACHED,
                cache_write_tokens=_WRITTEN,
                served_model=deployment["litellm_params"]["model"],
                **_GATEWAY_CALL,
            ).cost_usd,
            gateway_cost(deployment["model_info"]),
        )
        for group, deployment in priced
    }

    assert (
        {"deepseek-v4.1-flash-1017", "claude-sonnet-5-5", "claude-haiku-5-5"} <= costs.keys(),
        {group: pair for group, pair in costs.items() if pair[0] != pytest.approx(pair[1])},
    ) == (True, {})


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
