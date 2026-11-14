"""The limits that end an attempt of the stage, implement and fix-plan jobs are settings (#5440).

Each limit was a constant, so a person could not change it without a release. Now each one is a
setting of its job section, with the old constant as its default, so the behavior with no
configuration does not change. The settings load refuses a value above 4 times the default, with
the name of the setting, and it refuses a pair of values that breaks the order of an inner limit
and its outer limit.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.settings import Settings, load_settings, setting_default
from devops_cli.exceptions import ConfigurationError

# Each new setting and the value of the constant that it replaces.
OLD_VALUES: dict[str, int] = {
    "roadmap.stage.gate_return_extensions": 1,
    "roadmap.stage.verify_repair_rounds_ceiling": 4,
    "roadmap.stage.plan_defect_limit": 3,
    "roadmap.stage.max_requests": 250,
    "roadmap.stage.max_tool_calls": 200,
    "roadmap.stage.plan_calls_advised": 30,
    "roadmap.stage.plan_calls_notice": 40,
    "roadmap.stage.review_calls_advised": 40,
    "roadmap.stage.review_calls_notice": 60,
    "roadmap.implement.max_requests": 500,
    "roadmap.implement.max_tool_calls": 1500,
    "roadmap.implement.max_refusals": 30,
    "roadmap.implement.max_consecutive_refusals": 3,
    "roadmap.implement.tool_retries": 5,
    "roadmap.implement.model_resends": 1,
    "roadmap.implement.extension_calls": 20,
    "roadmap.implement.extension_max_refused": 3,
    "roadmap.fix_plan.head_attempts": 2,
    "roadmap.fix_plan.revisions": 3,
}
# The highest value of each setting: 4 times its default, and for the repair rounds of the review,
# 4 times the default of their ceiling.
CEILINGS: dict[str, int] = {
    **{path: 4 * value for path, value in OLD_VALUES.items()},
    "roadmap.stage.gate_returns": 12,
    "roadmap.stage.verify_repair_rounds": 16,
}


def _value(settings: Settings, path: str) -> Any:
    found: Any = settings
    for part in path.split("."):
        found = getattr(found, part)
    return found


def _nested(values: dict[str, int]) -> dict[str, Any]:
    """The config sections that set each dotted path of `values`."""
    tree: dict[str, Any] = {}
    for path, value in values.items():
        *sections, leaf = path.split(".")
        node = tree
        for section in sections:
            node = node.setdefault(section, {})
        node[leaf] = value
    return tree


@pytest.mark.parametrize("path", sorted(OLD_VALUES))
def test_each_new_setting_has_the_old_constant_as_its_default(path: str) -> None:
    assert (setting_default(path), _value(load_settings(), path)) == (
        OLD_VALUES[path],
        OLD_VALUES[path],
    )


def test_the_gate_returns_and_the_head_attempts_can_double(config: Callable[..., Path]) -> None:
    config(roadmap={"stage": {"gate_returns": 6}, "fix_plan": {"head_attempts": 4}})

    roadmap = load_settings().roadmap

    assert (roadmap.stage.gate_returns, roadmap.fix_plan.head_attempts) == (6, 4)


def test_every_setting_loads_at_its_ceiling(config: Callable[..., Path]) -> None:
    config(_nested(CEILINGS))

    settings = load_settings()

    assert {path: _value(settings, path) for path in CEILINGS} == CEILINGS


@pytest.mark.parametrize("path", sorted(CEILINGS))
def test_a_value_above_the_ceiling_is_refused_with_the_name_of_the_setting(
    config: Callable[..., Path], path: str
) -> None:
    config(_nested({path: CEILINGS[path] + 1}))

    with pytest.raises(ConfigurationError) as refused:
        load_settings()

    assert path in str(refused.value)


@pytest.mark.parametrize(
    ("values", "inner", "outer"),
    [
        pytest.param(
            {"roadmap.implement.max_refusals": 2},
            "max_consecutive_refusals",
            "max_refusals",
            id="refusals-in-a-row-above-the-total",
        ),
        pytest.param(
            {"roadmap.implement.extension_calls": 2},
            "extension_max_refused",
            "extension_calls",
            id="refused-calls-above-the-window",
        ),
        pytest.param(
            {"roadmap.stage.plan_calls_advised": 41},
            "plan_calls_advised",
            "plan_calls_notice",
            id="plan-advice-above-the-notice",
        ),
        pytest.param(
            {"roadmap.stage.review_calls_notice": 39},
            "review_calls_advised",
            "review_calls_notice",
            id="review-advice-above-the-notice",
        ),
        pytest.param(
            {"roadmap.stage.max_tool_calls": 50},
            "review_calls_notice",
            "max_tool_calls",
            id="notice-above-the-tool-calls",
        ),
        pytest.param(
            {"roadmap.stage.verify_repair_rounds": 5},
            "verify_repair_rounds",
            "verify_repair_rounds_ceiling",
            id="rounds-above-their-ceiling",
        ),
    ],
)
def test_an_inner_limit_above_its_outer_limit_is_refused_with_both_names(
    config: Callable[..., Path], values: dict[str, int], inner: str, outer: str
) -> None:
    config(_nested(values))

    with pytest.raises(ConfigurationError) as refused:
        load_settings()

    assert f"{inner} must not be above {outer}" in str(refused.value)


def test_the_live_doubled_values_load(config: Callable[..., Path]) -> None:
    """The doubled values that the owner set on 2026-11-13, with the doubled limits of this change,
    pass the order checks."""
    config(
        _nested(
            {
                **{path: 2 * value for path, value in OLD_VALUES.items()},
                "roadmap.stage.gate_returns": 6,
                "roadmap.stage.verify_repair_rounds": 4,
            }
        )
    )

    stage = load_settings().roadmap.stage

    assert (stage.verify_repair_rounds, stage.verify_repair_rounds_ceiling) == (4, 8)
