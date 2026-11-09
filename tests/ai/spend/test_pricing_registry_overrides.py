"""The setting `ai.price_overrides` prices a model that genai-prices does not know (#4242).

The file `pricing_overrides.json` in the data directory wins over the setting for one model. The
setting and the file merge, and `devops ai cost set-price` never copies a price of the setting
into the file.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Generator
from pathlib import Path

import pytest
from genai_prices.data_snapshot import set_custom_snapshot
from pydantic import ValidationError

from devops_cli.ai.spend.models import ModelPricing
from devops_cli.ai.spend.pricing import PricingRegistry
from devops_cli.config.settings import AIConfig, AIPriceOverride, Settings

CHAT_MODEL = "qwen3.8:27b"
EMBEDDING_MODEL = "qwen/qwen3-embedding-8b"


@pytest.fixture(autouse=True)
def _reset_process_snapshot() -> Generator[None]:
    """Reset the genai-prices snapshot of the process before and after each test."""
    set_custom_snapshot(None)
    yield
    set_custom_snapshot(None)


def _settings(**prices: tuple[float, float]) -> Settings:
    """Settings whose `ai.price_overrides` hold `prices`, as (prompt, completion) USD per million."""
    return Settings(
        ai=AIConfig(
            price_overrides={
                model: AIPriceOverride(
                    prompt_usd_per_million=prompt, completion_usd_per_million=completion
                )
                for model, (prompt, completion) in prices.items()
            }
        )
    )


def _write_file(data_dir: Path, content: dict[str, ModelPricing]) -> None:
    """Write `pricing_overrides.json` as `devops ai cost set-price` writes it."""
    ai_dir = data_dir / "ai"
    ai_dir.mkdir(parents=True, exist_ok=True)
    (ai_dir / "pricing_overrides.json").write_text(
        json.dumps({name: pricing.model_dump() for name, pricing in content.items()}),
        encoding="utf-8",
    )


def test_a_setting_prices_a_model_with_an_empty_data_directory(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A model that genai-prices does not know takes the price of the setting, with no warning."""
    registry = PricingRegistry(data_dir=tmp_path, settings=_settings(**{CHAT_MODEL: (0.035, 1.5)}))

    with caplog.at_level(logging.WARNING):
        pricing = registry.get_pricing(CHAT_MODEL, provider="openai")
        reference = registry.price_reference(
            CHAT_MODEL, setting="ai.reference_model", kind="chat", provider="openai"
        )

    assert (
        pricing.prompt_usd_per_million,
        pricing.completion_usd_per_million,
        reference == pricing,
        caplog.text,
    ) == (0.035, 1.5, True, "")


def test_the_cost_of_a_request_uses_the_price_of_the_setting(tmp_path: Path) -> None:
    """A request of 1 million tokens each way costs the two prices of the setting together."""
    registry = PricingRegistry(
        data_dir=tmp_path, settings=_settings(**{EMBEDDING_MODEL: (0.01, 0.0)})
    )

    cost = registry.calculate_request_cost(
        EMBEDDING_MODEL, 1_000_000, 0, server="https://api.example.com", provider="openai"
    )

    assert cost.cost_usd == 0.01


def test_a_name_in_the_setting_matches_without_regard_to_case(tmp_path: Path) -> None:
    """The registry lower-cases the name of the setting, as it does for the file."""
    registry = PricingRegistry(data_dir=tmp_path, settings=_settings(**{"Qwen3.8:27B": (1.0, 2.0)}))

    assert registry.get_pricing(CHAT_MODEL, provider="openai").prompt_usd_per_million == 1.0


def test_the_file_wins_over_the_setting_for_the_same_model(tmp_path: Path) -> None:
    """A price that `set-price` saved on the volume stays in force over the price of the setting."""
    _write_file(
        tmp_path,
        {CHAT_MODEL: ModelPricing(prompt_usd_per_million=9.0, completion_usd_per_million=8.0)},
    )

    registry = PricingRegistry(data_dir=tmp_path, settings=_settings(**{CHAT_MODEL: (0.035, 1.5)}))

    pricing = registry.get_pricing(CHAT_MODEL, provider="openai")
    assert (pricing.prompt_usd_per_million, pricing.completion_usd_per_million) == (9.0, 8.0)


def test_the_file_and_the_setting_merge_for_different_models(tmp_path: Path) -> None:
    """A model that only the setting names and a model that only the file names are both priced."""
    _write_file(
        tmp_path,
        {"other-model": ModelPricing(prompt_usd_per_million=3.0, completion_usd_per_million=4.0)},
    )

    registry = PricingRegistry(data_dir=tmp_path, settings=_settings(**{CHAT_MODEL: (0.035, 1.5)}))

    assert (
        registry.get_pricing(CHAT_MODEL, provider="openai").prompt_usd_per_million,
        registry.get_pricing("other-model", provider="openai").prompt_usd_per_million,
        {CHAT_MODEL, "other-model"} <= set(registry.list_all_pricing()),
    ) == (0.035, 3.0, True)


def test_set_price_for_another_model_does_not_copy_the_setting_into_the_file(
    tmp_path: Path,
) -> None:
    """`set-price` saves only the prices that a person set, so the repository keeps its prices."""
    registry = PricingRegistry(data_dir=tmp_path, settings=_settings(**{CHAT_MODEL: (0.035, 1.5)}))

    registry.set_custom_pricing("other-model", 3.0, 4.0)

    saved = json.loads((tmp_path / "ai" / "pricing_overrides.json").read_text(encoding="utf-8"))
    assert list(saved) == ["other-model"]


def test_set_price_for_a_model_of_the_setting_wins_and_remove_restores_the_setting(
    tmp_path: Path,
) -> None:
    """A price set by hand beats the setting. Removing it gives back the price of the setting."""
    registry = PricingRegistry(data_dir=tmp_path, settings=_settings(**{CHAT_MODEL: (0.035, 1.5)}))

    registry.set_custom_pricing(CHAT_MODEL, 9.0, 8.0)
    by_hand = registry.get_pricing(CHAT_MODEL, provider="openai").prompt_usd_per_million
    removed = registry.remove_custom_pricing(CHAT_MODEL)
    restored = registry.get_pricing(CHAT_MODEL, provider="openai").prompt_usd_per_million

    assert (by_hand, removed, restored) == (9.0, True, 0.035)


def test_a_registry_with_a_data_directory_and_no_settings_reads_no_setting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A registry that a test builds on a temporary directory does not read the user's settings."""
    monkeypatch.setattr(
        "devops_cli.ai.spend.pricing.load_settings",
        lambda: pytest.fail("the registry must not load settings when it has a data directory"),
    )

    registry = PricingRegistry(data_dir=tmp_path)

    assert CHAT_MODEL not in registry.list_all_pricing()


def test_a_price_below_zero_is_refused() -> None:
    """A negative price is no price: the setting refuses it at load time."""
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        AIPriceOverride(prompt_usd_per_million=-1.0, completion_usd_per_million=0.0)


def test_the_setting_loads_from_a_mapping_of_the_config_file() -> None:
    """The shape of the template: a name maps to a prompt and a completion price."""
    settings = Settings.model_validate(
        {
            "ai": {
                "price_overrides": {
                    CHAT_MODEL: {"prompt_usd_per_million": 0.035, "completion_usd_per_million": 1.5}
                }
            }
        }
    )

    assert settings.ai.price_overrides[CHAT_MODEL] == AIPriceOverride(
        prompt_usd_per_million=0.035, completion_usd_per_million=1.5
    )
