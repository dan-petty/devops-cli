"""The task `ai.tasks.stage` sets the model of the stage planner (#3207)."""

from __future__ import annotations

import pytest

from devops_cli.config.settings import AIConfig, AITaskOverride, load_settings


def _ai() -> AIConfig:
    ai = AIConfig(provider="ollama", model="base-model", context_window=32768)
    ai.tasks.analysis = AITaskOverride(model="analysis-model", context_window=65536)
    return ai


def test_the_stage_task_sets_a_model_and_the_analysis_task_keeps_its_own() -> None:
    ai = _ai()
    ai.tasks.stage = AITaskOverride(model="stage-model")

    assert (ai.for_task("stage").model, ai.for_task("analysis").model) == (
        "stage-model",
        "analysis-model",
    )


def test_the_stage_task_with_no_model_uses_the_settings_of_the_analysis_task() -> None:
    stage = _ai().for_task("stage")

    assert (stage.model, stage.context_window, stage.task_name) == (
        "analysis-model",
        65536,
        "stage",
    )


def test_the_stage_task_keeps_the_analysis_window_when_it_sets_only_a_model() -> None:
    ai = _ai()
    ai.tasks.stage = AITaskOverride(model="stage-model")

    stage = ai.for_task("stage")

    assert (stage.model, stage.context_window) == ("stage-model", 65536)


def test_a_variable_sets_the_stage_model(monkeypatch: pytest.MonkeyPatch) -> None:
    from devops_cli.config.settings import reset_settings_cache

    monkeypatch.setenv("DEVOPS_CLI_AI_TASK_STAGE_MODEL", "claude-sonnet-5-5")
    reset_settings_cache()
    try:
        assert load_settings().ai.for_task("stage").model == "claude-sonnet-5-5"
    finally:
        reset_settings_cache()
