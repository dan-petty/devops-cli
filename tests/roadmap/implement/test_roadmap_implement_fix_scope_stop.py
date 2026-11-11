"""A failed check after the push whose log names no path of the plan stops the item with no model
request (#4028). A check on a path of the plan gets a fix turn."""

from __future__ import annotations

import pytest

from tests.support.roadmap_implement import FAIL, PULL, JobWorld, a_fix, two_groups

pytestmark = pytest.mark.usefixtures("keyring_store")

DEPLOY = {**FAIL, "name": "Deploy Preview"}
STATIC = {**FAIL, "name": "Static Analysis"}


def test_a_failed_check_that_names_no_path_of_the_plan_stops_the_item_with_no_model_request(
    job_world: JobWorld,
) -> None:
    job_world.pull.runs = [[DEPLOY]]
    job_world.pull.log = "Process completed with exit code 1."
    script = two_groups()

    applied = job_world.run(script)

    held = job_world.store.item(1)
    assert held is not None
    assert (applied.ready, applied.stopped, held.status) == ((), (1,), "Blocked")
    assert held.job_record.get("implement.stopped") == "checks"
    assert len(script.seen) == 4
    (comment,) = job_world.issue_comments()
    assert "Deploy Preview" in comment
    assert "src/devops_cli/shout.py" in comment
    assert job_world.sent("POST", f"issues/{PULL}/comments") != []


def test_a_failed_check_that_names_a_path_of_the_plan_gets_a_fix_turn(
    job_world: JobWorld,
) -> None:
    job_world.pull.runs = [[STATIC], [{**STATIC, "conclusion": "success"}]]
    job_world.pull.log = "src/devops_cli/shout.py:1:1: E501 line too long"
    script = two_groups(*a_fix())

    applied = job_world.run(script)

    assert applied.ready == (1,)
    assert len(script.seen) == 6
