"""The job gives a step the tests that the merged plan records (#3490). A person merges the plan,
so the record on the default branch holds what the owner allows under rule 5 of `AGENTS.md`. An
entry that the agent writes in its checkout waives nothing.

The world of the job is the one of `test_roadmap_implement_job.py`: git runs for real, and the
other programs are answered at the process edge.
"""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.roadmap.implement.implement_run import apply_implement
from tests.support.implement_step import WINDOW, write_call
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import (
    BRANCH,
    CHANGE_DIR,
    PROPOSAL,
    JobWorld,
    group_one_calls,
    group_two_calls,
)
from tests.support.roadmap_stage import STAGE_NAME

pytestmark = pytest.mark.usefixtures("keyring_store")

OLD_PATH = "tests/test_old.py"
OLD = "def test_a() -> None: ...\n\n\ndef test_b() -> None: ...\n"
WITHOUT_A = "def test_b() -> None: ...\n"
PROPOSAL_PATH = f"{CHANGE_DIR}/proposal.md"
ENTRY = (
    f"- **`{OLD_PATH}::test_a`**: Stopped: an old form. Safeguard: `test_b` holds the same claim.\n"
)
SECTION = f"\n## Weakened checks\n\n{ENTRY}"
REFUSED = PROPOSAL + "\n## Weakened checks\n\nThe test goes.\n"


def _record(world: JobWorld) -> dict[str, str | None]:
    held = world.store.item(world.number)
    assert held is not None
    return {str(key): value for key, value in held.job_record.items()}


def _removal(*more: tuple[str, dict[str, Any]]) -> ModelScript:
    """A model that removes `test_a` in group 1, and completes group 2."""
    return ModelScript(
        tool_calls(write_call(OLD_PATH, WITHOUT_A), *more, *group_one_calls()),
        say("Group 1 is done."),
        tool_calls(*group_two_calls()),
        say("Group 2 is done."),
    )


def test_a_removal_that_the_merged_plan_records_passes_the_step(planned_world: JobWorld) -> None:
    planned_world.repo.track({OLD_PATH: OLD, PROPOSAL_PATH: PROPOSAL + SECTION})

    applied = planned_world.run(_removal())

    assert (applied.ready, applied.stopped) == ((planned_world.number,), ())


def test_a_removal_that_the_merged_plan_does_not_record_stops_and_waits(
    planned_world: JobWorld,
) -> None:
    planned_world.repo.track({OLD_PATH: OLD})

    applied = planned_world.run(_removal())

    record = _record(planned_world)
    comment = planned_world.issue_comments()[-1]
    assert (applied.stopped, record.get("implement.failure")) == (
        (planned_world.number,),
        "tests_lost",
    )
    assert "Action left: `wait`:" in comment
    assert f"{OLD_PATH}: test_a" in comment


def test_an_entry_that_the_agent_writes_in_its_checkout_waives_nothing(
    planned_world: JobWorld,
) -> None:
    planned_world.repo.track({OLD_PATH: OLD})
    own_entry = write_call(PROPOSAL_PATH, PROPOSAL + SECTION)

    applied = planned_world.run(_removal(own_entry))

    assert applied.stopped == (planned_world.number,)
    assert _record(planned_world).get("implement.failure") == "tests_lost"


def test_a_plan_only_on_its_staged_branch_records_nothing(job_world: JobWorld) -> None:
    """Nobody merged the plan of a Staged item, so its record is the agent's own."""
    job_world.repo.track({OLD_PATH: OLD})
    repo = job_world.repo
    repo.git("switch", "-q", "-c", BRANCH, f"origin/{BRANCH}")
    (repo.clone / PROPOSAL_PATH).write_text(PROPOSAL + SECTION, encoding="utf-8")
    repo.git("add", "-A")
    repo.git("-c", f"user.name={STAGE_NAME}", "commit", "-q", "--amend", "-m", "fix(roadmap): plan")
    repo.git("push", "-q", "--force", "origin", BRANCH)
    repo.git("switch", "-q", "main")
    repo.git("branch", "-q", "-D", BRANCH)

    applied = job_world.run(_removal())

    assert applied.stopped == (job_world.number,)
    assert _record(job_world).get("implement.failure") == "tests_lost"


def test_a_section_that_the_reader_refuses_leaves_the_item_out_of_the_plan(
    planned_world: JobWorld,
) -> None:
    planned_world.repo.track({PROPOSAL_PATH: REFUSED})

    plan = planned_world.plan()

    assert plan.selected == ()
    assert "The test goes." in plan.left_out[0].reason


def test_a_section_that_the_reader_refuses_after_the_plan_stops_the_item_as_a_plan_defect(
    planned_world: JobWorld,
) -> None:
    """The default branch moves between the plan of the run and the step. The job fetches it."""
    plan = planned_world.plan()
    planned_world.repo.track({PROPOSAL_PATH: REFUSED})

    applied = apply_implement(
        planned_world.store,
        plan,
        source=planned_world.repo.clone,
        model=ModelScript().model(),
        window=WINDOW,
    )

    record = _record(planned_world)
    comment = planned_world.issue_comments()[-1]
    assert (applied.stopped, record.get("implement.failure")) == (
        (planned_world.number,),
        "plan_defect",
    )
    assert "The test goes." in comment
