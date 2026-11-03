"""The implement task (#2664): the model and the window that serve one step of
`devops roadmap implement`, and the pydantic-ai model `get_task_model` builds for it."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic_ai.models import Model

from devops_cli.ai.client import factory
from devops_cli.config.settings import load_settings
from tests.support.model_script import ModelScript, say

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

    assert model.model_name == "devops-coder"
    assert isinstance(model, Model)


def test_the_task_model_is_the_client_override_when_it_is_a_pydantic_ai_model() -> None:
    fake = ModelScript(say("Done.")).model()
    factory.set_llm_client_override(fake)

    assert factory.get_task_model("implement") is fake


def test_the_tier_model_of_a_local_group_goes_to_the_gateway(
    config: Callable[..., Path],
) -> None:
    """A local tier reaches the gateway whatever `ai.provider` is (#3060)."""
    config(ai={"provider": "gateway", "gateway_url": "https://gateway.example.com"})

    model = factory.get_tier_model("devops-coder")

    assert model.model_name == "devops-coder"
    assert isinstance(model, Model)


def test_the_tier_model_of_an_ollama_tag_is_the_local_model(config: Callable[..., Path]) -> None:
    config(ai={"provider": "ollama"})

    model = factory.get_tier_model("ollama:qwen3-coder:30b")

    assert model.model_name == "qwen3-coder:30b"
    assert isinstance(model, Model)


def test_the_tier_model_is_the_client_override_when_it_is_a_pydantic_ai_model() -> None:
    fake = ModelScript(say("Done.")).model()
    factory.set_llm_client_override(fake)

    assert factory.get_tier_model("devops-coder") is fake
