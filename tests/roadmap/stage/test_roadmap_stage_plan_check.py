"""`devops roadmap stage`: the plan check of CI runs before the push (#4725).

On 2026-11-13 the stage job staged #5136 with no gate return and opened plan pull request #5407.
The `Plan Check` of CI then refused the plan: group 2 changes an existing file, and only a command
span names it, so the group packs no file (`group-no-files`). The stage job now runs the rules of
`devops roadmap plan-check` on the files that it writes. A plan that they refuse goes back to the
planner as a gate return, and a plan that they still refuse after the last return fails the item
with no push and no pull request.
"""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING

import pytest

from devops_cli.config.defaults import DEFAULT_ROADMAP_STAGE_STEP_TOKENS
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.plan_check import PlanFolder, staged_problems
from devops_cli.roadmap.plan_read import read_change
from devops_cli.roadmap.stage.stage import StagePlan, parse_filters, plan_stage
from devops_cli.roadmap.stage.stage_change import (
    StageProposal,
    pull_request_body,
    render_change,
    staging_title,
)
from devops_cli.roadmap.stage.stage_paths import StagedTree
from tests.support.builders import make_stage_proposal
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.paths import FIXTURES
from tests.support.roadmap_fix_plan import head_files
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    apply_stage,
    seed_stageable,
    validate_args,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

CHANGE = "1-the-job-drops-a-comment"
TASKS = f"openspec/changes/{CHANGE}/tasks.md"
CREATED = date(2026, 11, 13)
ITEM_TITLE = "fix(roadmap): the job drops a comment"
ITEM_BODY = "The job drops the last comment of a thread."
# The change folder of the plan pull request #5407 (item #5136) at its head ecc08320bf60.
HEAD_5407 = FIXTURES / "roadmap" / "plan_heads" / "5407-ecc08320bf60"
# The files of the staged commit that the plan of #5407 names. The check measures the groups on
# them, so the test tracks each one in the clone.
NAMED_5407 = (
    ".github/workflows/copilot-setup-steps.yml",
    ".pre-commit-config.yaml",
    "CONTRIBUTING.md",
    "release-please-config.json",
    "src/devops_cli/commands/ci.py",
    "src/devops_cli/config/constants.py",
    "src/devops_cli/git/branch_form.py",
    "tests/git/test_branch_form.py",
    "tests/invariants/test_workflow_contracts.py",
)
# The one problem that the CI job `Plan Check` printed for the head of #5407, word for word.
CI_5407 = (
    "Group 2, `Extend the naming-form and setup-step tests with the copilot names`, packs no file. "
    "No code span in its tasks names a file of the head commit, so the step starts with none of "
    "the files that it changes. Name each file that the group changes in a code span of a task."
)


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    seed_stageable(store)
    return store


@pytest.fixture(autouse=True)
def _openspec(openspec_fake: OpenSpecFake) -> None:
    """OpenSpec, found, and valid about the change of #1 for every reply."""
    openspec_fake.script_sequence(validate_args(CHANGE), *[(0, VALID_REPORT)] * 6)


def _packs_no_file() -> StageProposal:
    """The defect of group 2 of #5407: the group changes `src/devops_cli/sample.py`, which exists,
    and no code span of its tasks names it. Only the verify command names a path, and a command
    span is no file, so the step of the group starts with none of the files that it changes."""
    group = make_stage_proposal().groups[0]
    unnamed = group.model_copy(
        update={
            "test": "Write the test of the last comment",
            "implementation": "Keep the last comment",
        }
    )
    return make_stage_proposal(groups=[unnamed])


def _no_files_line(title: str) -> str:
    """The line that `devops roadmap plan-check` prints for the defect, as the stage job returns it."""
    return MESSAGES.roadmap.plan_check_line.format(
        path=TASKS,
        rule="group-no-files",
        message=MESSAGES.roadmap.plan_check_group_no_files.format(number=1, title=title),
    )


def _plan(store: InMemoryRoadmapStore, repo: StageRepo) -> StagePlan:
    return plan_stage(
        store, repo=STAGE_REPO, source=repo.clone, filters=parse_filters(()), model=None
    )


def test_a_plan_that_the_plan_check_refuses_goes_back_to_the_planner_as_a_gate_return(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    refused = _packs_no_file()
    model_fake.answer(refused, make_stage_proposal())

    plan = _plan(store, stage_repo)

    returned = json.loads(model_fake.calls[1].prompt)
    assert model_fake.call_count == 2
    assert returned["problem"] == _no_files_line(refused.groups[0].title)
    assert [change.proposal for change in plan.ready] == [make_stage_proposal()]
    assert [attempt.gate_returns for attempt in plan.attempts] == [1]


def test_a_plan_that_the_plan_check_refuses_after_each_return_is_never_pushed(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    model_fake.answer(_packs_no_file())

    plan = _plan(store, stage_repo)
    applied = apply_stage(store, plan, source=stage_repo.clone)

    (failure,) = plan.failed
    assert (plan.ready, applied.staged) == ((), ())
    assert failure.failure_class is FailureClass.PLAN_DEFECT
    assert "group-no-files" in failure.reason
    assert stage_repo.origin_git("branch", "--format=%(refname:short)").split() == ["main"]


def _folder(repo: StageRepo, change: str, files: Mapping[str, str]) -> PlanFolder:
    """The change folder `files` of `change` on the clone of `repo`, as the stage job gives it to
    the plan check."""
    return PlanFolder(
        root=f"openspec/changes/{change}",
        files=files,
        checkout=repo.clone,
        tree=StagedTree(repo.git("ls-files").splitlines()).with_files(files),
        known=frozenset({"roadmap-refine"}),
        requirements={},
        base_scenarios={},
        item_title=ITEM_TITLE,
        item_body=ITEM_BODY,
        budget=DEFAULT_ROADMAP_STAGE_STEP_TOKENS,
        registry=(),
    )


def test_the_check_before_the_push_refuses_the_plan_of_5407_as_the_ci_check_did(
    stage_repo: StageRepo,
) -> None:
    (folder,) = HEAD_5407.iterdir()
    files = head_files(folder)
    change = next(iter(files)).split("/")[2]
    stage_repo.track({path: f"The file {path}.\n" for path in NAMED_5407})
    proposal = read_change(files)
    title = staging_title(1, proposal.summary)
    body = pull_request_body(1, change, proposal)

    found = staged_problems(_folder(stage_repo, change, files), number=1, title=title, body=body)

    # The plan's scenarios name no behavior task, which the rule of #3423 now refuses; the
    # finding of the CI check that the fixture records stays the only other problem.
    assert [
        (problem.path, problem.rule, problem.message)
        for problem in found
        if problem.rule != "stage"
    ] == [(f"openspec/changes/{change}/tasks.md", "group-no-files", CI_5407)]


def test_the_check_before_the_push_judges_no_open_dependency(stage_repo: StageRepo) -> None:
    """An open issue in `## Dependencies` holds the merge until it closes. The plan is right to
    name it, so the stage job does not send it back: the check reads no issue."""
    proposal = make_stage_proposal(dependencies=["#3224: the dependency record"])
    files = render_change(CHANGE, proposal, {"roadmap-refine"}, created=CREATED)
    title = staging_title(1, proposal.summary)
    body = pull_request_body(1, CHANGE, proposal)

    found = staged_problems(_folder(stage_repo, CHANGE, files), number=1, title=title, body=body)

    assert found == []
