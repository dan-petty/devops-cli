"""`devops roadmap explain` and the report of `devops roadmap implement` name the first problem of
the plan that the implement job leaves out (#3393). Git runs for real on a clone with an `origin`,
and GitHub is faked."""

from __future__ import annotations

import pytest

from devops_cli.roadmap.explain import JobVerdict, explain_item
from devops_cli.roadmap.implement.implement import parse_implement_filters, render_implement_plan
from devops_cli.roadmap.plan_rewrite import rewrite_plan
from devops_cli.roadmap.stage.stage import parse_filters
from devops_cli.roadmap.stage.stage_paths import StagedTree
from tests.support.roadmap_implement import CHANGE_DIR, TASKS, TASKS_PATH, JobWorld
from tests.support.roadmap_stage import STAGE_REPO

pytestmark = pytest.mark.usefixtures("keyring_store")

PLACEHOLDER_TASKS = TASKS.replace("1.1 Add `src/devops_cli/shout.py`", "1.1 x")
FIRST_PROBLEM = (
    "The text of implementation of group 1 has 1 characters, and the least is 10. "
    "Write a real sentence."
)
REFUSED = f"Its plan fails the stage check: {FIRST_PROBLEM}"


@pytest.fixture
def staged_tasks() -> str:
    """The plan of the staged branch holds the placeholder task, so the plan check refuses it."""
    return PLACEHOLDER_TASKS


def test_explain_names_the_first_problem_of_a_refused_staged_plan(job_world: JobWorld) -> None:
    explained = explain_item(
        job_world.store,
        repo=STAGE_REPO,
        source=job_world.repo.clone,
        number=job_world.number,
        stage_filters=parse_filters(()),
        implement_filters=parse_implement_filters(()),
        stage_limit=3,
        implement_limit=1,
    )

    assert explained.implement == JobVerdict(False, REFUSED)


def test_the_report_names_the_first_problem_of_a_refused_staged_plan(job_world: JobWorld) -> None:
    report = render_implement_plan(job_world.plan(item=job_world.number))

    assert REFUSED in report


def _merge_tasks(world: JobWorld, tasks: str) -> None:
    """Replace the `tasks.md` of the merged plan of the Planned item on `main` of `origin`."""
    world.repo.track({TASKS_PATH: tasks})


def test_a_planned_item_with_a_refused_merged_plan_leaves_the_queue_and_explain_names_why(
    planned_world: JobWorld,
) -> None:
    _merge_tasks(planned_world, PLACEHOLDER_TASKS)

    plan = planned_world.plan(item=planned_world.number)
    explained = explain_item(
        planned_world.store,
        repo=STAGE_REPO,
        source=planned_world.repo.clone,
        number=planned_world.number,
        stage_filters=parse_filters(()),
        implement_filters=parse_implement_filters(()),
        stage_limit=3,
        implement_limit=1,
    )

    assert plan.selected == ()
    assert REFUSED in render_implement_plan(plan)
    assert explained.implement == JobVerdict(False, REFUSED)


# A plan that no mechanical rewrite fixes: the first group changes no test file and no document,
# and it has no `Verification:` line, so the plan reader refuses it.
NO_WAY_FORWARD_TASKS = PLACEHOLDER_TASKS.replace("1.1 x", "1.1 Add `src/devops_cli/shout.py`")
NO_WAY_FORWARD_TASKS = NO_WAY_FORWARD_TASKS.replace(", `tests/test_shout.py` (new)", "").replace(
    "\n  - Verification: `$ uv run devops ci test tests/test_shout.py`", ""
)


def test_a_merged_plan_that_the_rewrite_cannot_fix_leaves_the_queue_with_the_same_reason(
    planned_world: JobWorld,
) -> None:
    _merge_tasks(planned_world, NO_WAY_FORWARD_TASKS)
    rewritten = rewrite_plan(CHANGE_DIR, {TASKS_PATH: NO_WAY_FORWARD_TASKS}, StagedTree([]))
    assert rewritten.files[TASKS_PATH] == NO_WAY_FORWARD_TASKS

    plan = planned_world.plan(item=planned_world.number)
    explained = explain_item(
        planned_world.store,
        repo=STAGE_REPO,
        source=planned_world.repo.clone,
        number=planned_world.number,
        stage_filters=parse_filters(()),
        implement_filters=parse_implement_filters(()),
        stage_limit=3,
        implement_limit=1,
    )

    assert plan.selected == ()
    assert explained.implement.takes is False
    assert explained.implement.reason.startswith("The plan reader cannot read ")
    assert explained.implement.reason in render_implement_plan(plan)
