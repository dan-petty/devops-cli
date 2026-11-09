"""The example ConfigMap names only settings that `Settings` declares (#4093).

Most models of `Settings` set `extra="ignore"`, so a key that a change removes from a model and
that stays in `k8s/devops/configmap.example.yaml` loads with no error. These tests walk each key of
the rendered example against the fields of the models. A test cannot read the live ConfigMap:
`devops k8s deploy-stack` validates its rendering before it applies it, and covers the cluster.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from devops_cli.config.setting_keys import unknown_setting_keys
from devops_cli.config.settings import GitHubAppConfig, ServiceConfig, Settings
from devops_cli.k8s.configmap import render_active_devops_configmap
from tests.support.paths import REPO_ROOT

APP = GitHubAppConfig(app_id=1001, installation_id=42, slug="devops-roadmap")


def _example_config() -> dict[str, Any]:
    """The settings that the example ConfigMap holds, as a deploy renders them."""
    rendered = render_active_devops_configmap(
        k8s_dir=REPO_ROOT / "k8s",
        settings=Settings(service=ServiceConfig(repos=["example-org/repo"], github_app=APP)),
    )
    config: dict[str, Any] = yaml.safe_load(yaml.safe_load(rendered)["data"]["devops-cli.yaml"])
    return config


def test_every_key_of_the_example_is_a_setting() -> None:
    """No key of the example is unknown, and the whole example loads into `Settings`."""
    config = _example_config()

    Settings.model_validate(config)

    assert unknown_setting_keys(config) == []


@pytest.mark.parametrize(
    ("path", "reported"),
    [
        (("roadmap", "implement", "not_a_setting"), "roadmap.implement.not_a_setting"),
        (("not_a_section",), "not_a_section"),
    ],
)
def test_an_unknown_key_in_a_copy_of_the_example_is_reported(
    path: tuple[str, ...], reported: str
) -> None:
    """A key that no model declares is reported with its full path, though the load accepts it."""
    config = copy.deepcopy(_example_config())
    section = config
    for part in path[:-1]:
        section = section[part]
    section[path[-1]] = 1

    Settings.model_validate(config)

    assert unknown_setting_keys(config) == [reported]


def test_a_key_of_a_price_in_a_copy_of_the_example_is_checked_and_a_model_name_is_not() -> None:
    """The name of a model under `ai.price_overrides` is a key of the user. The fields of its
    price are keys of a model, so a misspelled field is reported (#4242)."""
    config = copy.deepcopy(_example_config())
    config["ai"]["price_overrides"]["qwen3.8:27b"]["prompt_usd_per_milion"] = 1.0

    assert unknown_setting_keys(config) == ["ai.price_overrides.qwen3.8:27b.prompt_usd_per_milion"]


def test_an_unknown_ladder_step_class_in_a_copy_of_the_example_fails_to_load() -> None:
    """The ladder refuses a step class that no step has: the load catches this one already."""
    config = copy.deepcopy(_example_config())
    config["roadmap"]["implement"]["ladder"]["plan"] = ["devops-coder"]

    with pytest.raises(ValidationError, match="the ladder names no step class"):
        Settings.model_validate(config)
