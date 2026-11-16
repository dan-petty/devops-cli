"""Each roadmap job reads a model setting of its own, so a model trial moves one job (#5903)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from devops_cli.config.settings import AIConfig, load_settings, reset_settings_cache

# The task of each model role of a roadmap job. `implement` has a model of its own by default, so
# it is left out of the fallback to `ai.model`.
JOB_TASKS = (
    "intake",
    "retitle",
    "refine",
    "refine_review",
    "alternatives",
    "consolidate",
    "stage",
    "stage_review",
    "fix_plan",
    "fix_plan_review",
    "implement_split",
    "fix_checks",
)
BASE_MODEL = "base-model"
BASE_WINDOW = 32768


@pytest.fixture
def fresh_settings() -> Iterator[None]:
    reset_settings_cache()
    yield
    reset_settings_cache()


def _models(ai: AIConfig) -> dict[str, str]:
    return {task: ai.for_task(task).model for task in JOB_TASKS}


def test_a_model_set_only_for_refine_moves_refine_alone() -> None:
    ai = AIConfig(model=BASE_MODEL, tasks={"refine": {"model": "refine-model"}})

    assert (
        ai.for_task("refine").model,
        ai.for_task("alternatives").model,
        ai.for_task("consolidate").model,
    ) == ("refine-model", BASE_MODEL, BASE_MODEL)


@pytest.mark.parametrize("task", JOB_TASKS)
def test_the_model_of_one_job_task_reaches_that_task_alone(task: str) -> None:
    ai = AIConfig(model=BASE_MODEL, tasks={task: {"model": "trial-model"}})

    assert _models(ai) == {
        name: "trial-model" if name == task else BASE_MODEL for name in JOB_TASKS
    }


def test_the_fix_checks_task_takes_the_model_of_ai_and_the_window_of_a_step() -> None:
    """The model fix of `devops roadmap step fix-checks` runs a step of the implement job, so its
    task has the window of the implement task until a source sets one (#5971)."""
    ai = AIConfig(model=BASE_MODEL, context_window=BASE_WINDOW)

    task = ai.for_task("fix_checks")

    assert (task.model, task.context_window, task.task_name) == (
        BASE_MODEL,
        128000,
        "fix_checks",
    )


def test_the_stage_task_takes_nothing_from_the_analysis_task() -> None:
    ai = AIConfig(
        model=BASE_MODEL,
        context_window=BASE_WINDOW,
        tasks={"analysis": {"model": "analysis-model", "context_window": 65536}},
    )

    stage = ai.for_task("stage")

    assert (stage.model, stage.context_window, stage.task_name) == (
        BASE_MODEL,
        BASE_WINDOW,
        "stage",
    )


def test_the_old_shared_tasks_still_load_and_no_job_reads_them() -> None:
    ai = AIConfig(
        model=BASE_MODEL,
        tasks={
            "analysis": {"model": "analysis-model"},
            "verification": {"model": "verification-model"},
            "triage": {"model": "triage-model"},
        },
    )

    assert set(_models(ai).values()) == {BASE_MODEL}


@pytest.mark.parametrize("task", JOB_TASKS)
def test_a_variable_sets_the_model_the_window_and_the_reply_limit_of_a_job_task(
    task: str, monkeypatch: pytest.MonkeyPatch, fresh_settings: None
) -> None:
    monkeypatch.setenv(f"DEVOPS_CLI_AI_TASK_{task.upper()}_MODEL", "trial-model")
    monkeypatch.setenv(f"DEVOPS_CLI_AI_TASK_{task.upper()}_CONTEXT_WINDOW", "131072")
    monkeypatch.setenv(f"DEVOPS_CLI_AI_TASK_{task.upper()}_MAX_TOKENS", "8192")
    reset_settings_cache()

    configured = load_settings().ai.for_task(task)

    assert (configured.model, configured.context_window, configured.max_tokens) == (
        "trial-model",
        131072,
        8192,
    )
