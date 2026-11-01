"""`devops roadmap stage`: a task group has a kind, and the kind decides its tasks (#3005)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from devops_cli.roadmap.stage_change import StageGroup

BEHAVIOR: dict[str, Any] = {
    "title": "Keep the last comment",
    "kind": "behavior",
    "reads": ["src/devops_cli/sample.py"],
    "changes": ["src/devops_cli/sample.py", "tests/test_sample.py"],
    "creates": ["tests/test_sample.py"],
    "test": "Write `test_the_job_keeps_the_last_comment` in `tests/test_sample.py`",
    "implementation": "Keep the last comment in `src/devops_cli/sample.py`",
    "documentation": None,
    "verify": "uv run devops ci test tests/test_sample.py",
}
OTHER: dict[str, Any] = {
    "title": "Delete the dead property",
    "kind": "other",
    "reads": [],
    "changes": ["src/devops_cli/ai/client/streaming.py"],
    "creates": [],
    "test": None,
    "implementation": "Delete `thinking_detected` from `StreamingTokenProcessor`",
    "documentation": None,
    "verify": "! git grep -n -w thinking_detected src/ tests/ docs/",
}


def _problem(group: dict[str, Any]) -> str:
    """The text that the schema gives back to the model for `group`."""
    with pytest.raises(ValidationError) as raised:
        StageGroup.model_validate(group)
    return str(raised.value)


def test_a_behavior_group_with_a_test_and_a_source_path_is_valid() -> None:
    assert StageGroup.model_validate(BEHAVIOR).kind == "behavior"


def test_an_other_group_with_a_verify_and_no_test_is_valid() -> None:
    group = StageGroup.model_validate(OTHER)

    assert (group.kind, group.test, group.process) == ("other", None, None)


def test_an_other_group_with_a_process_and_no_command_is_valid() -> None:
    steps = "Open the report. Check that each file has a row."
    group = StageGroup.model_validate({**OTHER, "verify": None, "process": steps})

    assert group.process == steps


@pytest.mark.parametrize(
    ("update", "fragment"),
    [
        ({"test": None}, "has the kind behavior, and it has no test"),
        ({"verify": None}, "has the kind behavior, and it has no verify"),
        ({"process": "Look at the output."}, "has a process"),
        ({"changes": ["docs/TESTING.md"], "creates": []}, "changes no path under src/"),
        ({"kind": "mixed"}, "Input should be 'behavior' or 'other'"),
    ],
)
def test_a_behavior_group_that_breaks_a_rule_is_refused_with_the_problem(
    update: dict[str, Any], fragment: str
) -> None:
    assert fragment in _problem({**BEHAVIOR, **update})


@pytest.mark.parametrize(
    ("update", "fragment"),
    [
        ({"test": "Write a test"}, "has the kind other, and it has a test"),
        ({"verify": None}, "has neither verify nor process"),
        ({"process": "Look at the output."}, "has both verify and process"),
    ],
)
def test_an_other_group_that_breaks_a_rule_is_refused_with_the_problem(
    update: dict[str, Any], fragment: str
) -> None:
    assert fragment in _problem({**OTHER, **update})


def test_a_group_that_breaks_two_rules_names_both_in_one_problem() -> None:
    problem = _problem({**OTHER, "test": "Write a test", "verify": None})

    assert "has a test" in problem
    assert "has neither verify nor process" in problem
