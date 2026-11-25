"""The setting `tf.stacks` and `tf.github_reader`: agent access levels for `tf/github` stacks (#5320)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from devops_cli.config.settings import TFConfig, load_settings, reset_settings_cache
from devops_cli.exceptions import ConfigurationError
from devops_cli.tf.access import TFAccessLevel


def test_tf_github_stack_without_agent_access_defaults_to_plan(
    config: Callable[..., Path],
) -> None:
    config(tf={"stacks": [{"path": "tf/github/dan-petty"}]})

    entry = load_settings().tf.stacks[0]

    assert (entry.path, entry.agent_access) == ("tf/github/dan-petty", TFAccessLevel.PLAN)


def test_tf_github_stack_with_apply_access_keeps_apply(config: Callable[..., Path]) -> None:
    config(tf={"stacks": [{"path": "tf/github/retric-ai", "agent_access": "apply"}]})

    assert load_settings().tf.stacks[0].agent_access is TFAccessLevel.APPLY


def test_tf_github_stack_refuses_invalid_agent_access_value(
    isolate_devops_cli_config: Path,
) -> None:
    isolate_devops_cli_config.write_text(
        "tf:\n  stacks:\n    - path: tf/github/dan-petty\n      agent_access: full\n",
        encoding="utf-8",
    )
    reset_settings_cache()

    with pytest.raises(ConfigurationError) as caught:
        load_settings()

    text = str(caught.value)
    assert "tf.stacks[].agent_access" in text
    assert "plan" in text
    assert "apply" in text


def test_tf_config_refuses_invalid_and_duplicate_stacks() -> None:
    with pytest.raises(ValidationError) as invalid_access:
        TFConfig.model_validate(
            {"stacks": [{"path": "tf/github/dan-petty", "agent_access": "full"}]}
        )
    assert "tf.stacks[].agent_access" in str(invalid_access.value)

    with pytest.raises(ValidationError) as duplicate_stack:
        TFConfig.model_validate(
            {
                "stacks": [
                    {"path": "tf/github/dan-petty"},
                    {"path": "./tf/github/dan-petty/"},
                ]
            }
        )
    assert "stacks" in str(duplicate_stack.value)
