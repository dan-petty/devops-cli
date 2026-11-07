"""The step classes of the implement ladder (#4036): a class exists only when a step reads it.

`StepClass` holds `EDIT` (a group of a change) and `REPAIR` (the fix of a failed check). The
constant, the default ladder and the example ConfigMap name the same two classes, and a ladder with
any other key is refused.
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_STEP_CLASSES
from devops_cli.config.settings import RoadmapImplementConfig, Settings
from devops_cli.roadmap.implement.implement_step import StepClass
from tests.support.paths import REPO_ROOT

EXAMPLE_CONFIGMAP = REPO_ROOT / "k8s" / "devops" / "configmap.example.yaml"


def _example_settings() -> Any:
    document = yaml.safe_load(EXAMPLE_CONFIGMAP.read_text(encoding="utf-8"))
    return yaml.safe_load(document["data"]["devops-cli.yaml"])


def test_step_class_has_exactly_edit_and_repair() -> None:
    assert {member.name: member.value for member in StepClass} == {
        "EDIT": "edit",
        "REPAIR": "repair",
    }


def test_the_ladder_constant_names_exactly_edit_and_repair() -> None:
    assert CONST_ROADMAP_IMPLEMENT_STEP_CLASSES == ("edit", "repair")


def test_the_default_ladder_holds_exactly_edit_and_repair() -> None:
    assert sorted(RoadmapImplementConfig().ladder) == ["edit", "repair"]


def test_the_example_configmap_ladder_holds_exactly_edit_and_repair() -> None:
    raw_ladder = _example_settings()["roadmap"]["implement"]["ladder"]

    assert sorted(raw_ladder) == ["edit", "repair"]
    assert sorted(Settings.model_validate(_example_settings()).roadmap.implement.ladder) == [
        "edit",
        "repair",
    ]


@pytest.mark.parametrize("dead_class", ["plan", "review"])
def test_a_ladder_with_a_removed_class_is_refused_with_a_message(dead_class: str) -> None:
    with pytest.raises(ValidationError, match=f"the ladder names no step class {dead_class}"):
        RoadmapImplementConfig(ladder={dead_class: ["devops-coder"]})


def test_the_ladder_setting_describes_the_two_classes() -> None:
    description = RoadmapImplementConfig.model_fields["ladder"].description or ""

    assert "(`edit`, `repair`)" in description
    assert "`plan`" not in description
    assert "`review`" not in description
