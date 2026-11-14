"""The settings of the decision points (ADR 0020): `ai.decision_model` names the decision model, and
`roadmap.decisions` holds the mode of each registered point."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from devops_cli.config.settings import RoadmapConfig, RoadmapStageConfig, Settings, load_settings
from devops_cli.exceptions import ConfigurationError
from devops_cli.roadmap.decision_point import chain_of
from devops_cli.roadmap.decision_registry import REGISTRY
from devops_cli.roadmap.stage.stage_jev_screen import VERIFY_SCREEN

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tests.support.fakes.jev import JevFake


def test_no_decision_model_and_no_mode_are_the_defaults() -> None:
    settings = Settings()

    assert (settings.ai.decision_model, settings.roadmap.decisions) == ("", {})


@pytest.mark.parametrize(
    "name",
    [
        "typesafe/jev-1.14",
        "typesafe:jev-1.14",
        "system-one:a-decision-model",
        "litellm:typesafe/jev-1.14",
    ],
)
def test_the_decision_model_takes_the_name_of_a_system_one_model(name: str) -> None:
    assert Settings(ai={"decision_model": name}).ai.decision_model == name


def test_the_decision_model_refuses_a_model_that_writes_text(config: Callable[..., Path]) -> None:
    config(ai={"decision_model": "deepseek-v4.1-flash-1017"})

    with pytest.raises(ConfigurationError, match=r"ai\.decision_model") as refused:
        load_settings()

    assert refused.value.key == "ai.decision_model"


def test_the_variables_set_the_decision_model_and_the_mode_of_a_point(
    monkeypatch: pytest.MonkeyPatch, config: Callable[..., Path]
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_AI_DECISION_MODEL", "typesafe/jev-1.14")
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_DECISIONS", '{"stage.verify_screen": "shadow"}')
    config()

    settings = load_settings()

    assert (settings.ai.decision_model, settings.roadmap.decisions) == (
        "typesafe/jev-1.14",
        {"stage.verify_screen": "shadow"},
    )


def test_a_mode_mapping_that_is_no_json_object_names_the_setting(
    monkeypatch: pytest.MonkeyPatch, config: Callable[..., Path]
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_DECISIONS", "shadow")
    config()

    with pytest.raises(ConfigurationError, match="DEVOPS_CLI_ROADMAP_DECISIONS") as refused:
        load_settings()

    assert (refused.value.key, refused.value.error_code) == (
        "roadmap.decisions",
        "CONFIGURATION_ERROR",
    )


def test_a_key_that_names_no_point_stops_the_load_and_names_the_points(
    config: Callable[..., Path],
) -> None:
    config(roadmap={"decisions": {"stage.verify_scren": "shadow"}})

    with pytest.raises(ConfigurationError, match=r"stage\.verify_scren.*stage\.verify_screen"):
        load_settings()


def test_a_config_that_still_holds_the_old_screen_key_loads_and_the_point_is_off(
    config: Callable[..., Path],
) -> None:
    config(ai={"decision_model": "typesafe/jev-1.14"}, roadmap={"stage": {"jev_screen": "shadow"}})

    settings = load_settings()

    assert "jev_screen" not in RoadmapStageConfig.model_fields
    assert settings.roadmap.decisions == {}
    assert chain_of(VERIFY_SCREEN, settings) is None


@pytest.mark.parametrize("mode", ["off", "shadow", "on"])
def test_the_verify_screen_takes_each_mode_because_its_cuts_are_fitted(mode: str) -> None:
    settings = Settings(roadmap={"decisions": {"stage.verify_screen": mode}})

    assert settings.roadmap.decisions == {"stage.verify_screen": mode}


def test_the_decisions_description_names_the_shadow_rule() -> None:
    description = RoadmapConfig.model_fields["decisions"].description or ""

    assert "`shadow`" in description
    assert "`on`" in description
    assert "needs a cuts file in the repository" in description


def test_a_mode_that_is_not_off_shadow_or_on_is_refused() -> None:
    with pytest.raises(ValidationError, match="decisions"):
        Settings(roadmap={"decisions": {"stage.verify_screen": "always"}})


def test_the_registry_holds_each_point_with_its_fitted_cuts() -> None:
    for name in REGISTRY.names:
        point = REGISTRY.point(name)
        assert point.cuts.is_file()
        assert point.thresholds().step == name
    assert REGISTRY.names == ("stage.verify_screen",)
    assert REGISTRY.series_count == 8


def test_a_point_runs_only_in_shadow_or_on_and_with_a_decision_model(jev: JevFake) -> None:
    def settings(model: str, mode: str | None) -> Settings:
        decisions = {} if mode is None else {"stage.verify_screen": mode}
        return Settings(ai={"decision_model": model}, roadmap={"decisions": decisions})

    assert chain_of(VERIFY_SCREEN, settings("typesafe/jev-1.14", None)) is None
    assert chain_of(VERIFY_SCREEN, settings("typesafe/jev-1.14", "off")) is None
    assert chain_of(VERIFY_SCREEN, settings("", "on"), model=jev.model) is None
    chain = chain_of(VERIFY_SCREEN, settings("typesafe/jev-1.14", "shadow"), model=jev.model)
    assert chain is not None
    assert (chain.point, chain.mode.value) == (VERIFY_SCREEN, "shadow")
    assert jev.requests == []
