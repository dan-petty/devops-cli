"""The extension of a step budget in the comments and the record of the implement job (#4394).

Git runs for real on a clone with an `origin`. The model is scripted and reports 50 input tokens
for each request and the output tokens of its parts. The first request of group 1 counts 140 new
tokens and the second 171, so a step budget of 220 tokens ends at the second request, and its
extension to 330 at the third. GitHub's REST API and `gh` are faked at their edges.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.roadmap.stores.store import ImplementRecordKey
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import (
    TASKS_PATH,
    JobWorld,
    group_one_calls,
    group_two_calls,
)

pytestmark = pytest.mark.usefixtures("keyring_store")

READ = ("read_file", {"path": TASKS_PATH})
# Group 1 reads 18 times, then writes twice: its last 20 calls hold 2 successful edits.
GROUP_ONE = (tool_calls(*(READ,) * 18), tool_calls(*group_one_calls()))
EXTENDED = (
    "- group 1: 220 to 330 new tokens. Trigger: 2 successful edit(s) and 0 refused "
    "command(s) in the last 20 tool calls."
)


@pytest.fixture
def budget(config: Callable[..., Path]) -> None:
    config(roadmap={"implement": {"step_token_budget": 220}})


@pytest.mark.usefixtures("budget")
def test_the_ready_comment_and_the_record_show_the_extension_of_a_step(
    job_world: JobWorld,
) -> None:
    script = ModelScript(
        *GROUP_ONE,
        say("Group 1 is done."),
        tool_calls(*group_two_calls()),
        say("Group 2 is done."),
    )

    applied = job_world.run(script)

    (comment,) = job_world.issue_comments()
    held = job_world.store.item(1)
    assert held is not None
    spend = json.loads(held.job_record.get(ImplementRecordKey.SPEND) or "{}")
    assert applied.ready == (1,)
    assert EXTENDED in comment
    assert [step.get("extension") for step in spend["steps"]] == [
        {"limit": 220, "budget": 330, "calls": 20, "edits": 2, "refused": 0, "ceiling": False},
        None,
    ]


@pytest.mark.usefixtures("budget")
def test_the_stop_comment_shows_the_extension_that_the_step_spent(job_world: JobWorld) -> None:
    script = ModelScript(*GROUP_ONE, tool_calls(READ), say("Group 1 is done."))

    applied = job_world.run(script)

    (comment,) = job_world.issue_comments()
    assert applied.stopped == (1,)
    assert "Failure class: `limit_reached`." in comment
    assert EXTENDED in comment
    assert "and its one extension to 330 new tokens" in comment


def test_a_comment_of_a_run_with_no_extension_has_no_extension_section(
    job_world: JobWorld,
) -> None:
    script = ModelScript(
        tool_calls(*group_one_calls()),
        say("Group 1 is done."),
        tool_calls(*group_two_calls()),
        say("Group 2 is done."),
    )

    job_world.run(script)

    (comment,) = job_world.issue_comments()
    assert "Budget extensions" not in comment
