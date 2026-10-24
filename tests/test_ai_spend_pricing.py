"""Unit tests for AI open-source pricing registry, matching heuristics, and catalog management."""

from __future__ import annotations

import ast
import json
import logging
import re
from collections.abc import Callable, Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from genai_prices.data_snapshot import set_custom_snapshot

from devops_cli.ai.spend.models import ModelPricing
from devops_cli.ai.spend.pricing import (
    PricingRegistry,
    RequestCost,
    _get_installed_genai_prices_version,
)
from devops_cli.config.defaults import DEFAULT_AI_REFERENCE_MODEL
from tests.support.paths import REPO_ROOT


@pytest.fixture(autouse=True)
def _reset_process_snapshot() -> Generator[None]:
    """Reset genai-prices process-wide custom snapshot before and after every test."""
    set_custom_snapshot(None)
    yield
    set_custom_snapshot(None)


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
    """Verify a custom price for a hosted model or server persists and prices its calls."""
    registry = PricingRegistry(data_dir=tmp_path)

    registry.set_custom_pricing("gpt-4o", prompt_rate=0.15, completion_rate=0.30)
    registry.set_custom_pricing("example.com", prompt_rate=0.05, completion_rate=0.10)

    # Model override takes priority over the server's
    resolved_model = registry.get_pricing("gpt-4o", server="example.com", provider="openai")
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
    resolved_server = registry.get_pricing("other-model", server="example.com", provider="openai")
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
    reloaded = reloaded_registry.get_pricing("gpt-4o", server="example.com", provider="openai")
    assert (
        reloaded.prompt_usd_per_million,
        reloaded.completion_usd_per_million,
        reloaded.source,
    ) == (
        0.15,
        0.30,
        "custom_override",
    )


def test_a_custom_price_leaves_a_local_call_at_no_cost(tmp_path: Path) -> None:
    """Verify a custom price for a local model or a local server books no spend, so the call
    stays in local savings (#1631)."""
    registry = PricingRegistry(data_dir=tmp_path)
    registry.set_custom_pricing("qwen2.5-coder:7b", prompt_rate=0.15, completion_rate=0.30)
    registry.set_custom_pricing("http://localhost:11434", prompt_rate=0.05, completion_rate=0.10)

    by_model = registry.get_pricing(
        "qwen2.5-coder:7b", server="http://localhost:11434", provider="ollama"
    )
    by_server = registry.get_pricing("other-model", server="http://localhost:11434")

    assert (
        (by_model.prompt_usd_per_million, by_model.completion_usd_per_million, by_model.source),
        (by_server.prompt_usd_per_million, by_server.completion_usd_per_million, by_server.source),
        registry.calculate_request_cost(
            "qwen2.5-coder:7b", 1_000_000, 1_000_000, server="localhost:11434", provider="ollama"
        ),
        registry.calculate_request_cost(
            "other-model", 1_000_000, 0, server="http://localhost:11434"
        ),
    ) == (
        (0.0, 0.0, "local"),
        (0.0, 0.0, "local"),
        RequestCost(0.0, "local"),
        RequestCost(0.0, "local"),
    )


def test_a_gateway_call_is_priced_by_the_backend_that_served_it(tmp_path: Path) -> None:
    """Verify a call a hosted API served through a loopback gateway is priced at the model's
    hosted rate, and one a cluster Ollama served through a gateway host nothing configures
    costs nothing (#1631)."""
    registry = PricingRegistry(data_dir=tmp_path)
    peak_ts = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    hosted = registry.calculate_request_cost(
        "gpt-4o",
        1_000_000,
        0,
        server="localhost:4000",
        provider="gateway",
        request_timestamp=peak_ts,
        served_by="https://api.openai.com",
    )
    hosted_rate = registry.get_pricing(
        "gpt-4o", server="localhost:4000", provider="gateway", served_by="https://api.openai.com"
    )
    local = registry.calculate_request_cost(
        "gpt-4o",
        1_000_000,
        0,
        server="example.com:4000",
        provider="gateway",
        request_timestamp=peak_ts,
        served_by="http://ollama-16gib.llm.svc.cluster.local:11434",
    )

    assert (hosted, hosted_rate.prompt_usd_per_million, local) == (
        RequestCost(2.5, "genai_prices:openai"),
        2.5,
        RequestCost(0.0, "local"),
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
    """Verify default remote synchronization fetches via httpx2, writes snapshot, and reloads."""
    import httpx2

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

    class FakeResponse:
        content = json.dumps(raw).encode("utf-8")

        def raise_for_status(self) -> None:
            pass

    monkeypatch.setattr(httpx2, "get", lambda *args, **kwargs: FakeResponse())

    registry = PricingRegistry(data_dir=tmp_path)
    res = registry.update_from_remote()

    snapshot_file = tmp_path / "ai" / "pricing_snapshot.json"
    assert (res.source_model_count, snapshot_file.is_file()) == (1, True)

    # Recreate registry after clearing process snapshot to ensure reload from disk
    set_custom_snapshot(None)
    reloaded = PricingRegistry(data_dir=tmp_path)
    updated_pricing = reloaded.get_pricing("mock-custom-model")
    assert (
        updated_pricing.prompt_usd_per_million,
        updated_pricing.completion_usd_per_million,
        updated_pricing.source,
    ) == (
        4.0,
        12.0,
        "genai_prices:mock-provider",
    )


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
    assert exact_cost == RequestCost(0.09, "genai_prices:anthropic")


def test_pricing_registry_update_from_file_and_persistence(tmp_path: Path) -> None:
    """Verify updating pricing from a local file persists snapshot and reloads on startup."""
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

    registry = PricingRegistry(data_dir=tmp_path)
    res = registry.update_from_remote(source_url=str(file_path))
    assert res.source_model_count == 1

    pricing = registry.get_pricing("file-custom-model")
    assert (pricing.prompt_usd_per_million, pricing.completion_usd_per_million) == (5.0, 15.0)

    # Verify snapshot file exists
    assert (tmp_path / "ai" / "pricing_snapshot.json").is_file()

    # Clear process-wide snapshot before building second registry to verify persistence
    set_custom_snapshot(None)
    reloaded = PricingRegistry(data_dir=tmp_path)
    p_reloaded = reloaded.get_pricing("file-custom-model")
    assert (p_reloaded.prompt_usd_per_million, p_reloaded.completion_usd_per_million) == (
        5.0,
        15.0,
    )


def test_partial_snapshot_merges_onto_bundled_data_and_keeps_prices(tmp_path: Path) -> None:
    """Verify partial snapshot merges onto bundled data, keeps bundled models, and prices file models."""
    custom_data = [
        {
            "id": "custom-unbundled-provider",
            "name": "Custom Provider",
            "api_pattern": ".*",
            "model_match": {"contains": "custom-unbundled"},
            "models": [
                {
                    "id": "custom-unbundled-model",
                    "name": "Custom Model",
                    "match": {"equals": "custom-unbundled-model"},
                    "prices": {"input_mtok": 11.0, "output_mtok": 22.0},
                }
            ],
        }
    ]
    file_path = tmp_path / "partial.json"
    file_path.write_text(json.dumps(custom_data), encoding="utf-8")

    registry = PricingRegistry(data_dir=tmp_path)
    registry.update_from_remote(source_url=str(file_path))

    set_custom_snapshot(None)
    new_reg = PricingRegistry(data_dir=tmp_path)

    # gpt-4o call (provider openai, pinned timestamp) costs same as with no snapshot
    ts = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    cost_4o = new_reg.calculate_request_cost(
        "gpt-4o",
        prompt_tokens=20_000,
        completion_tokens=2_000,
        provider="openai",
        request_timestamp=ts,
    )
    # Bundled gpt-4o price without provider has source genai_prices:openai
    p_bundled = new_reg.get_pricing("gpt-4o", request_timestamp=ts)
    # Custom unbundled model looked up with provider has file price
    p_custom = new_reg.get_pricing("custom-unbundled-model", provider="custom-unbundled-provider")

    assert (
        cost_4o,
        (p_bundled.prompt_usd_per_million, p_bundled.completion_usd_per_million, p_bundled.source),
        (p_custom.prompt_usd_per_million, p_custom.completion_usd_per_million, p_custom.source),
    ) == (
        RequestCost(0.07, "genai_prices:openai"),
        (2.5, 10.0, "genai_prices:openai"),
        (11.0, 22.0, "genai_prices:custom-unbundled-provider"),
    )


def test_provider_fields_merge_one_at_a_time(tmp_path: Path) -> None:
    """Verify provider fields merge one by one, keeping bundled matchers, extractors, and other models."""
    custom_data = [
        {
            "id": "openai",
            "name": "OpenAI",
            "api_pattern": "https://api.openai.com/v1",
            "models": [
                {
                    "id": "gpt-4o",
                    "name": "GPT-4o",
                    "match": {"equals": "gpt-4o"},
                    "prices": {"input_mtok": 99.0, "output_mtok": 199.0},
                }
            ],
        }
    ]
    file_path = tmp_path / "openai_override.json"
    file_path.write_text(json.dumps(custom_data), encoding="utf-8")

    registry = PricingRegistry(data_dir=tmp_path)
    registry.update_from_remote(source_url=str(file_path))

    set_custom_snapshot(None)
    new_reg = PricingRegistry(data_dir=tmp_path)
    ts = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    p_4o_with_prov = new_reg.get_pricing("gpt-4o", provider="openai", request_timestamp=ts)
    p_4o_no_prov = new_reg.get_pricing("gpt-4o", request_timestamp=ts)
    p_mini_with_prov = new_reg.get_pricing("gpt-4o-mini", provider="openai", request_timestamp=ts)
    p_mini_no_prov = new_reg.get_pricing("gpt-4o-mini", request_timestamp=ts)

    assert (
        (p_4o_with_prov.prompt_usd_per_million, p_4o_with_prov.completion_usd_per_million),
        (
            p_4o_no_prov.prompt_usd_per_million,
            p_4o_no_prov.completion_usd_per_million,
            p_4o_no_prov.source,
        ),
        (p_mini_with_prov.prompt_usd_per_million, p_mini_with_prov.completion_usd_per_million),
        (p_mini_no_prov.prompt_usd_per_million, p_mini_no_prov.completion_usd_per_million),
    ) == (
        (99.0, 199.0),
        (99.0, 199.0, "genai_prices:openai"),
        (0.15, 0.6),
        (0.15, 0.6),
    )


def test_token_extraction_survives_partial_snapshot(tmp_path: Path) -> None:
    """Verify pydantic_ai token extraction succeeds under partial snapshots for unbundled and bundled providers."""
    import pydantic_ai.usage

    def _extract_tokens() -> tuple[int, int]:
        usage = pydantic_ai.usage.RequestUsage.extract(
            {
                "model": "gpt-4o",
                "usage": {"prompt_tokens": 20000, "completion_tokens": 2000, "total_tokens": 22000},
            },
            provider="ollama",
            provider_url="http://localhost:11434/v1",
            provider_fallback="openai",
            api_flavor="chat",
        )
        return (usage.input_tokens, usage.output_tokens)

    # 1. Test with unbundled provider
    custom_unbundled = [
        {
            "id": "unbundled-provider",
            "name": "Unbundled Provider",
            "api_pattern": ".*",
            "models": [
                {
                    "id": "m1",
                    "name": "M1",
                    "match": {"equals": "m1"},
                    "prices": {"input_mtok": 1.0, "output_mtok": 2.0},
                }
            ],
        }
    ]
    f1 = tmp_path / "f1.json"
    f1.write_text(json.dumps(custom_unbundled), encoding="utf-8")
    r1 = PricingRegistry(data_dir=tmp_path / "d1")
    r1.update_from_remote(source_url=str(f1))
    tokens1 = _extract_tokens()

    # 2. Test with partial openai provider
    custom_openai = [
        {
            "id": "openai",
            "name": "OpenAI",
            "api_pattern": "https://api.openai.com/v1",
            "models": [
                {
                    "id": "gpt-4o",
                    "name": "GPT-4o",
                    "match": {"equals": "gpt-4o"},
                    "prices": {"input_mtok": 50.0, "output_mtok": 100.0},
                }
            ],
        }
    ]
    f2 = tmp_path / "f2.json"
    f2.write_text(json.dumps(custom_openai), encoding="utf-8")
    r2 = PricingRegistry(data_dir=tmp_path / "d2")
    r2.update_from_remote(source_url=str(f2))
    tokens2 = _extract_tokens()

    assert (tokens1, tokens2) == ((20000, 2000), (20000, 2000))


def test_snapshot_records_version_and_fetch_time_and_ignores_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify snapshot records genai-prices version and fetch time, and ignores version mismatch."""
    import logging

    custom_data = [
        {
            "id": "version-test-provider",
            "name": "Version Test",
            "api_pattern": ".*",
            "models": [
                {
                    "id": "v-model",
                    "name": "V Model",
                    "match": {"equals": "v-model"},
                    "prices": {"input_mtok": 3.0, "output_mtok": 6.0},
                }
            ],
        }
    ]
    f = tmp_path / "v_test.json"
    f.write_text(json.dumps(custom_data), encoding="utf-8")

    registry = PricingRegistry(data_dir=tmp_path)
    registry.update_from_remote(source_url=str(f))

    # Verify snapshot content
    snap_path = tmp_path / "ai" / "pricing_snapshot.json"
    snap_data = json.loads(snap_path.read_text(encoding="utf-8"))
    assert ("genai_prices_version" in snap_data, "fetched_at" in snap_data) == (True, True)

    # Monkeypatch installed version to different version
    monkeypatch.setattr(
        "devops_cli.ai.spend.pricing._get_installed_genai_prices_version",
        lambda: "99.99.99",
    )
    set_custom_snapshot(None)

    with caplog.at_level(logging.WARNING):
        reloaded = PricingRegistry(data_dir=tmp_path)

    # The snapshot should NOT be loaded, prices come from bundled data
    p = reloaded.get_pricing("v-model", provider="version-test-provider")
    warning_text = caplog.text

    assert (
        p.source != "genai_prices:version-test-provider",
        str(snap_path) in warning_text,
        "devops ai cost update-pricing --reset" in warning_text,
    ) == (True, True, True)


def test_old_bare_list_snapshot_format_is_ignored_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify old snapshot format (bare list without version metadata) is ignored with warning."""
    import logging

    ai_dir = tmp_path / "ai"
    ai_dir.mkdir(parents=True, exist_ok=True)
    snap_file = ai_dir / "pricing_snapshot.json"
    # Bare list format written by 9c879ae
    snap_file.write_text(
        json.dumps([{"id": "bare-list-prov", "name": "Bare", "api_pattern": ".*", "models": []}]),
        encoding="utf-8",
    )

    set_custom_snapshot(None)
    with caplog.at_level(logging.WARNING):
        _ = PricingRegistry(data_dir=tmp_path)

    warning_text = caplog.text
    assert (
        str(snap_file) in warning_text,
        "devops ai cost update-pricing --reset" in warning_text,
    ) == (True, True)


def test_loaded_snapshot_passes_recorded_fetch_time_as_auto_update_timestamp(
    tmp_path: Path,
) -> None:
    """Verify loaded snapshot preserves recorded fetch time as auto_update_timestamp."""
    from genai_prices.data_snapshot import get_snapshot

    recorded_time = datetime(2025, 6, 15, 10, 30, tzinfo=UTC)
    snap_payload = {
        "genai_prices_version": _get_installed_genai_prices_version(),
        "fetched_at": recorded_time.isoformat(),
        "providers": [
            {
                "id": "ts-prov",
                "name": "TS Prov",
                "api_pattern": ".*",
                "models": [
                    {
                        "id": "ts-model",
                        "name": "TS Model",
                        "match": {"equals": "ts-model"},
                        "prices": {"input_mtok": 1.0, "output_mtok": 2.0},
                    }
                ],
            }
        ],
    }
    ai_dir = tmp_path / "ai"
    ai_dir.mkdir(parents=True, exist_ok=True)
    (ai_dir / "pricing_snapshot.json").write_text(json.dumps(snap_payload), encoding="utf-8")

    set_custom_snapshot(None)
    PricingRegistry(data_dir=tmp_path)
    current_snapshot = get_snapshot()

    assert current_snapshot.timestamp == recorded_time


def test_full_snapshot_loaded_with_source_works_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify snapshot loaded with --source operates completely offline without network requests."""
    import httpx2

    def fail_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("Network access attempted during offline pricing resolution")

    monkeypatch.setattr(httpx2, "get", fail_network)
    monkeypatch.setattr(httpx2.Client, "request", fail_network)

    custom_data = [
        {
            "id": "offline-prov",
            "name": "Offline Prov",
            "api_pattern": ".*",
            "models": [
                {
                    "id": "offline-model",
                    "name": "Offline Model",
                    "match": {"equals": "offline-model"},
                    "prices": {"input_mtok": 8.0, "output_mtok": 16.0},
                }
            ],
        }
    ]
    f = tmp_path / "offline_prices.json"
    f.write_text(json.dumps(custom_data), encoding="utf-8")

    registry = PricingRegistry(data_dir=tmp_path)
    res = registry.update_from_remote(source_url=str(f))
    assert res.source_model_count == 1

    set_custom_snapshot(None)
    reloaded = PricingRegistry(data_dir=tmp_path)
    p = reloaded.get_pricing("offline-model", provider="offline-prov")
    assert (p.prompt_usd_per_million, p.completion_usd_per_million) == (8.0, 16.0)


def test_is_local_configured_cluster_and_gateway(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify is_local recognizes cluster domain subdomains and configured gateway URLs."""
    from devops_cli.ai.spend.pricing import is_local

    custom_cfg = tmp_path / "config.yaml"
    custom_cfg.write_text(
        "k8s:\n"
        "  domain: example.com\n"
        "cloudflare:\n"
        "  domain: example.com\n"
        "ai:\n"
        "  gateway_url: https://example.com/v1\n"
        "  api_base_url: https://example.com/v1\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(custom_cfg))

    assert (
        is_local("example.com", "gateway"),
        is_local("https://example.com/v1", "gateway"),
        is_local("example.com:8000", "gateway"),
        is_local(None, "gateway"),
        is_local("https://api.openai.com/v1", "openai"),
        is_local("example.com:11434, example.com:11435", "ollama"),
    ) == (
        True,
        True,
        True,
        True,
        False,
        True,
    )


def test_a_gateway_call_is_local_by_the_backend_that_served_it(
    config: Callable[..., Path],
) -> None:
    """Verify the backend a gateway reply names decides whether the call is local: a cluster
    Service or a configured Ollama URL is local behind a gateway host nothing configures, and a
    hosted API is hosted behind a loopback gateway. With no backend named, the host decides
    (#1631)."""
    from devops_cli.ai.spend.pricing import is_local

    config(ai={"ollama_urls": ["http://ollama.example.com:11434"]})
    cluster_ollama = "http://ollama-16gib.llm.svc.cluster.local:11434"

    assert [
        is_local("example.com:4000", "gateway", served_by=cluster_ollama),
        is_local("example.com:4000", "gateway", served_by="http://ollama.example.com:11434"),
        is_local("localhost:4000", "gateway", served_by="https://api.openai.com"),
        is_local("localhost:4000", "gateway"),
        is_local("example.com:4000", "gateway"),
    ] == [True, True, False, True, False]


def test_pricing_local_vs_remote_and_configured_domain_table(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify pricing counts non-public and malformed hosts as local, and matches k8s.domain on DNS labels (#887)."""
    from devops_cli.ai.spend.pricing import _is_local_host, is_local
    from devops_cli.config.settings import reset_settings_cache

    empty_cfg = tmp_path / "empty.yaml"
    empty_cfg.write_text("{}\n", encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(empty_cfg))
    reset_settings_cache()

    empty_results = (
        is_local("grafana.corp"),
        is_local("x.test"),
        is_local("ollama"),
        is_local("x.onion"),
        _is_local_host("a..b.example.com"),
        is_local("8.8.8.8"),
        is_local("example.com"),
    )

    domain_cfg = tmp_path / "domain.yaml"
    domain_cfg.write_text("k8s:\n  domain: example.com\n", encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(domain_cfg))
    reset_settings_cache()

    domain_results = (
        is_local("ai.example.com"),
        is_local("ai.evilexample.com"),
    )

    assert (empty_results, domain_results) == (
        (True, True, True, True, True, False, False),
        (True, False),
    )


def test_an_unknown_hosted_model_is_priced_unknown_and_warns_once(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """genai-prices raises LookupError for a model it does not know. A hosted request for such a
    model costs $0 with the pricing source `unknown`, and the registry logs one warning that names
    the model, however many requests ask for it (#1672). A known model names the genai-prices
    provider that priced it, and a local call is `local`."""
    registry = PricingRegistry(data_dir=tmp_path)
    peak_ts = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    caplog.set_level(logging.WARNING, logger="devops_cli.ai.spend.pricing")

    def price(model: str, server: str, provider: str) -> RequestCost:
        return registry.calculate_request_cost(
            model, 1_000_000, 0, server=server, provider=provider, request_timestamp=peak_ts
        )

    unknown = [price("gpt-9-preview", "example.com", "openai") for _ in range(2)]
    known = price("gpt-4o", "example.com", "openai")
    local = price("qwen3:8b", "localhost:11434", "ollama")

    assert (
        unknown,
        known,
        local,
        [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING],
    ) == (
        [RequestCost(0.0, "unknown")] * 2,
        RequestCost(2.5, "genai_prices:openai"),
        RequestCost(0.0, "local"),
        [
            "genai-prices and the price overrides hold no price for model gpt-9-preview under provider openai. Its requests are recorded at $0 with the pricing source unknown."
        ],
    )


def test_a_gateway_call_is_priced_at_the_litellm_reference_of_its_deployment_model(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The LiteLLM gateway names the deployment model of a call as a LiteLLM model reference,
    such as `openai/gpt-4o`, and genai-prices takes the provider from its prefix. So each hosted
    deployment is priced at the price of its provider, not at the route name `devops-chat` that
    genai-prices does not know. A local backend stays local, and a deployment with no price
    warns once with its own name (#2031)."""
    registry = PricingRegistry(data_dir=tmp_path)
    peak_ts = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    caplog.set_level(logging.WARNING, logger="devops_cli.ai.spend.pricing")

    def price(served_model: str | None, served_by: str = "https://api.openai.com") -> RequestCost:
        return registry.calculate_request_cost(
            "devops-chat",
            1_000_000,
            0,
            server="example.com:4000",
            provider="gateway",
            request_timestamp=peak_ts,
            served_by=served_by,
            served_model=served_model,
        )

    hosted = [
        price(model)
        for model in (
            "openai/gpt-4o",
            "openai/text-embedding-3-small",
            "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0",
            "openrouter/anthropic/claude-3.5-sonnet",
            "openai/gpt-9-preview",
            "openai/gpt-9-preview",
        )
    ]
    local = price("ollama_chat/qwen3.8:27b", "http://ollama-16gib.llm.svc.cluster.local:11434")

    assert (
        hosted,
        local,
        [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING],
    ) == (
        [
            RequestCost(2.5, "genai_prices:openai"),
            RequestCost(0.02, "genai_prices:openai"),
            RequestCost(3.0, "genai_prices:aws"),
            RequestCost(3.0, "genai_prices:openrouter"),
            RequestCost(0.0, "unknown"),
            RequestCost(0.0, "unknown"),
        ],
        RequestCost(0.0, "local"),
        [
            "genai-prices and the price overrides hold no price for model openai/gpt-9-preview under provider litellm. Its requests are recorded at $0 with the pricing source unknown."
        ],
    )


def test_a_price_override_of_the_deployment_model_prices_a_gateway_call(tmp_path: Path) -> None:
    """When a gateway reply names its deployment model, that model is the target of a price
    override, not the route name. A reply that names none takes the price of the route name, as
    the help of `devops ai cost set-price` says (#2031)."""
    registry = PricingRegistry(data_dir=tmp_path)
    registry.set_custom_pricing("gpt-4o", prompt_rate=1.0, completion_rate=2.0)
    registry.set_custom_pricing("devops-chat", prompt_rate=9.0, completion_rate=9.0)

    def price(served_model: str | None) -> RequestCost:
        return registry.calculate_request_cost(
            "devops-chat",
            1_000_000,
            1_000_000,
            server="example.com:4000",
            provider="gateway",
            served_by="https://api.openai.com",
            served_model=served_model,
        )

    assert (price("openai/gpt-4o"), price(None)) == (
        RequestCost(3.0, "custom_override"),
        RequestCost(18.0, "custom_override"),
    )


def _names_the_reference_model(source: str, model: str) -> list[int]:
    """The lines of `source` where a string names `model` as a reference model: the string, or
    the call, keyword, assignment or parameter list that holds it, mentions a reference. A longer
    name such as `<model>-mini`, or a LiteLLM reference such as `openai/<model>`, is another
    model, and another use of the same model, such as a tokenizer default, is no reference."""
    whole_name = re.compile(rf"(?<![\w./:-]){re.escape(model)}(?![\w./:-])")
    tree = ast.parse(source)
    holders = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and whole_name.search(node.value)
        and "reference" in ast.unparse(holders[node]).lower()
    ]


@pytest.mark.parametrize(
    ("source", "lines"),
    [
        ('help="Reference model for counterfactual pricing (default: gpt-4o)."', [1]),
        ('reference_model: str = "gpt-4o"', [1]),
        ('typer.Option("gpt-4o", help="The reference model.")', [1]),
        ('primary_model: str = "gpt-4o"', []),
        ('help="A model reference such as openai/gpt-4o, or gpt-4o-mini."', []),
    ],
)
def test_the_reference_model_check_finds_the_model_only_as_a_reference(
    source: str, lines: list[int]
) -> None:
    """Verify the check below finds a literal reference model, such as the help text that named
    the default before #1672, and not another use of the same model name (#2194)."""
    assert _names_the_reference_model(source, "gpt-4o") == lines


def test_only_the_defaults_name_the_default_reference_model() -> None:
    """The default reference model is named in `config/defaults.py` alone, and other code reads
    `DEFAULT_AI_REFERENCE_MODEL`, so a changed default changes every use (#1672). gpt-4o, the
    default since #2194, is also the model of other settings, which are no reference."""
    source = REPO_ROOT / "src" / "devops_cli"
    defaults = source / "config" / "defaults.py"

    assert [
        f"{path.relative_to(source)}:{line}"
        for path in sorted(source.rglob("*.py"))
        if path != defaults
        for text in [path.read_text(encoding="utf-8")]
        if DEFAULT_AI_REFERENCE_MODEL in text
        for line in _names_the_reference_model(text, DEFAULT_AI_REFERENCE_MODEL)
    ] == []
