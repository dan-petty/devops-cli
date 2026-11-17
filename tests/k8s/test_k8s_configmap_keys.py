"""The walk that finds the keys of a settings mapping that no settings model declares (#4093).

Most models of `Settings` set `extra="ignore"`, so a key that a change removes from a model loads
with no error. `unknown_setting_keys` names such a key by its dotted path, and the ConfigMap render
refuses a template that holds one (`tests/k8s/test_k8s_configmap.py`). These tests give the walk a
mapping that they build, not the committed template.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from devops_cli.config.setting_keys import unknown_setting_keys
from devops_cli.config.settings import Settings


def _config() -> dict[str, Any]:
    """A settings mapping that holds only keys that the models declare."""
    return {
        "ai": {"model": "devops-background", "tasks": {"chat": {"model": "devops-background"}}},
        "roadmap": {"implement": {"repair_rounds": 2}},
        "service": {"repos": ["example-org/repo"]},
    }


def test_a_mapping_of_declared_keys_has_no_unknown_key() -> None:
    config = _config()

    Settings.model_validate(config)

    assert unknown_setting_keys(config) == []


@pytest.mark.parametrize(
    ("path", "reported"),
    [
        (("roadmap", "implement", "not_a_setting"), "roadmap.implement.not_a_setting"),
        (("not_a_section",), "not_a_section"),
    ],
)
def test_an_unknown_key_is_reported_by_its_full_path(path: tuple[str, ...], reported: str) -> None:
    """A key that no model declares is reported with its full path, though the load accepts it."""
    config = _config()
    section = config
    for part in path[:-1]:
        section = section[part]
    section[path[-1]] = 1

    Settings.model_validate(config)

    assert unknown_setting_keys(config) == [reported]


def test_a_key_of_a_price_is_checked_and_a_model_name_is_not() -> None:
    """The name of a model under `ai.price_overrides` is a key of the user. The fields of its
    price are keys of a model, so a misspelled field is reported (#4242)."""
    config = _config()
    config["ai"]["price_overrides"] = {"example-model": {"prompt_usd_per_milion": 1.0}}

    assert unknown_setting_keys(config) == [
        "ai.price_overrides.example-model.prompt_usd_per_milion"
    ]


def test_an_unknown_ladder_step_class_fails_to_load() -> None:
    """The ladder refuses a step class that no step has: the load catches this one already."""
    config = _config()
    config["roadmap"]["implement"]["ladder"] = {"plan": ["devops-coder"]}

    with pytest.raises(ValidationError, match="the ladder names no step class"):
        Settings.model_validate(config)
