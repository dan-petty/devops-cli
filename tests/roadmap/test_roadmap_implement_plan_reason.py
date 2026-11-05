"""`devops roadmap explain` and the report of `devops roadmap implement` name the first problem of
the plan that the implement job leaves out (#3393). Git runs for real on a clone with an `origin`,
and GitHub is faked."""

from __future__ import annotations

import pytest

from devops_cli.roadmap.explain import JobVerdict, explain_item
from devops_cli.roadmap.implement import parse_implement_filters, render_implement_plan
from devops_cli.roadmap.stage import parse_filters
from tests.support.roadmap_implement import TASKS, JobWorld
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
