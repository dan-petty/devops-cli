"""The implement task (#2664): the model and the window that serve one step of
`devops roadmap implement`, and the pydantic-ai model `get_task_model` builds for it."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic_ai.models import Model
from pydantic_ai.models.function import FunctionModel

from devops_cli.ai.client import factory
from devops_cli.config.settings import load_settings

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_the_implement_task_defaults_to_the_coder_route_and_its_window() -> None:
    task = load_settings().ai.for_task("implement")

    assert (task.model, task.context_window, task.task_name) == (
        "devops-coder",
        128000,
        "implement",
    )


def test_a_window_in_the_config_file_keeps_the_coder_model(config: Callable[..., Path]) -> None:
    config(ai={"tasks": {"implement": {"context_window": 64000}}})

    task = load_settings().ai.for_task("implement")

    assert (task.model, task.context_window) == ("devops-coder", 64000)


def test_the_task_model_of_implement_is_a_pydantic_ai_model_named_for_the_route() -> None:
    model = factory.get_task_model("implement")

    assert (isinstance(model, Model), model.model_name) == (True, "devops-coder")


def test_the_task_model_is_the_client_override_when_it_is_a_pydantic_ai_model() -> None:
    fake = FunctionModel(lambda messages, info: None)  # type: ignore[arg-type,return-value]
    factory.set_llm_client_override(fake)

    assert factory.get_task_model("implement") is fake
