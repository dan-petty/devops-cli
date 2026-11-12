"""The step `fix-plan` gives the planner the open findings that the last plan comment of the item
lists (#5061): the stage comment, or the comment of an attempt that kept the label. The count of
the comment comes from an earlier review, so the step compares the revision with its own review of
the head (#5150)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_FIX_PLAN_COMMENT_MARKER,
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
)
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.stage.stage_eval_cases import DefectType
from devops_cli.roadmap.stage.stage_toolbox import ToolboxModel
from devops_cli.roadmap.stage.stage_verify import (
    PLAN_NEEDS_FIX_LABEL,
    Finding,
    Verification,
    findings_section,
    open_findings_section,
)
from devops_cli.roadmap.steps.fix_plan import (
    FixPlanResult,
    FixPlanRun,
    comment_open_findings,
    render_fix_plan,
    run_fix_plan,
)
from tests.support.builders import make_stage_proposal
from tests.support.fakes.model import ModelFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.paths import FIXTURES
from tests.support.roadmap_fix_plan import (
    PLAN_BRANCH,
    REPAIRED_WHY,
    SAMPLE_QUOTE,
    finding,
    needs_fix_plan,
    planner_requests,
    valid_changes,
)
from tests.support.roadmap_job_result import result_fields
from tests.support.roadmap_stage import STAGE_REPO, StageRepo

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

STAGE_COMMENT = (FIXTURES / "roadmap_fix_plan" / "stage_comment.txt").read_text(encoding="utf-8")
# The plan pull request that the real stage comment names.
STAGE_COMMENT_PULL = 4980


@pytest.fixture(autouse=True)
def openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    valid_changes(openspec_fake)
    return openspec_fake


def _comment(pull: int, open_: list[Finding], other: list[Finding] | None = None) -> str:
    """A stage comment of the plan pull request `pull`, in the form that the stage job writes."""
    return (
        f"{CONST_ROADMAP_STAGE_COMMENT_MARKER}\nStaged: branch `fix/1-x`, draft pull request "
        f"#{pull}." + open_findings_section(open_) + findings_section(other or [])
    )


def test_the_reader_reads_the_open_findings_of_a_real_stage_comment() -> None:
    (read,) = comment_open_findings(STAGE_COMMENT)

    assert (read.type, read.where) == (
        DefectType.CRITERION_DROPPED,
        "specs (Readiness reads the file list at the merge base)",
    )
    assert read.problem.startswith("The issue's criterion that no request path")
    assert read.quote.startswith("No request path of the readiness run ends with")


def test_the_reader_reads_back_each_open_finding_and_no_point() -> None:
    open_ = [
        finding(DefectType.TASK_ORDER),
        finding(DefectType.CRITERION_DROPPED, quote="", where="criteria (criterion 2)"),
    ]
    point = finding(DefectType.OTHER, where="group 2")

    assert comment_open_findings(_comment(5, open_, [point])) == tuple(open_)


@pytest.mark.parametrize(
    "body",
    [
        f"{CONST_ROADMAP_STAGE_COMMENT_MARKER}\nStaged: draft pull request #5.",
        _comment(5, [], [finding(DefectType.OTHER)]),
        f"{CONST_ROADMAP_FIX_PLAN_COMMENT_MARKER}\nThe pull request loses the label.",
    ],
)
def test_a_comment_with_no_open_findings_section_gives_none(body: str) -> None:
    assert comment_open_findings(body) == ()


def _run(store: InMemoryRoadmapStore, repo: StageRepo, verifier: ModelFake) -> FixPlanRun:
    return run_fix_plan(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        confirm=True,
        verifier=ToolboxModel(verifier),
    )


def _real_comment(pull: int) -> str:
    """The real stage comment of the plan of #2530, with its one open finding, for the plan pull
    request `pull`."""
    return STAGE_COMMENT.replace(f"#{STAGE_COMMENT_PULL}", f"#{pull}")


def test_the_revision_is_compared_with_a_review_of_the_head_and_not_with_the_comment(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    verifier = ModelFake()
    plan = needs_fix_plan(store, stage_repo, github_api)
    store.seed_comment(plan.number, _real_comment(plan.pull))
    dropped = finding(DefectType.CRITERION_DROPPED)
    order = finding(DefectType.TASK_ORDER, SAMPLE_QUOTE)
    verifier.answer(Verification(findings=[dropped, order]), Verification(findings=[dropped]))
    model_fake.answer(make_stage_proposal(why=REPAIRED_WHY))

    with caplog.at_level(logging.INFO):
        run = _run(store, stage_repo, verifier)

    assert run.attempt is not None
    assert (run.attempt.result, run.attempt.before, run.attempt.after) == (
        FixPlanResult.REVISED,
        2,
        1,
    )
    assert run.attempt.comment == 1
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) != plan.head
    (line,) = result_fields(caplog)
    assert (line["comment"], line["before"], line["after"]) == ("1", "2", "1")
    shown = MESSAGES.roadmap.fix_plan_attempt.format(
        pull=plan.pull, number=plan.number, result="revised", before=2, after=1, comment=1
    )
    assert shown in render_fix_plan(run)


def test_the_planner_gets_the_open_findings_of_the_comment_and_of_the_review_of_the_head(
    stage_repo: StageRepo, model_fake: ModelFake, github_api: GitHubApiFake
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    verifier = ModelFake()
    plan = needs_fix_plan(store, stage_repo, github_api)
    store.seed_comment(plan.number, _real_comment(plan.pull))
    order = finding(DefectType.TASK_ORDER, SAMPLE_QUOTE)
    verifier.answer(Verification(findings=[order]), Verification())
    model_fake.answer(make_stage_proposal(why=REPAIRED_WHY))

    run = _run(store, stage_repo, verifier)

    (request,) = planner_requests(model_fake)
    assert "The issue's criterion that no request path" in request["problem"]
    assert "Problem of task_order." in request["problem"]
    assert verifier.call_count == 2
    assert run.attempt is not None
    assert (run.attempt.result, run.attempt.before, run.attempt.after) == (
        FixPlanResult.CLEARED,
        1,
        0,
    )
    assert PLAN_NEEDS_FIX_LABEL not in store._roadmap.issues[plan.pull].labels


def test_a_head_that_its_review_finds_clean_loses_the_label_though_the_comment_lists_a_finding(
    stage_repo: StageRepo, model_fake: ModelFake, github_api: GitHubApiFake
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    verifier = ModelFake()
    plan = needs_fix_plan(store, stage_repo, github_api)
    store.seed_comment(plan.number, _real_comment(plan.pull))
    verifier.answer(Verification())

    run = _run(store, stage_repo, verifier)

    assert model_fake.call_count == 0
    assert run.attempt is not None
    assert (run.attempt.result, run.attempt.before, run.attempt.after) == (
        FixPlanResult.CLEARED,
        0,
        0,
    )
    assert run.attempt.comment == 1
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) == plan.head
    assert PLAN_NEEDS_FIX_LABEL not in store._roadmap.issues[plan.pull].labels


@pytest.mark.parametrize(
    ("pull", "association"), [(4, "OWNER"), (5, "NONE")], ids=["other pull", "untrusted"]
)
def test_a_comment_of_another_pull_request_or_an_untrusted_author_is_not_read(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    pull: int,
    association: str,
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    verifier = ModelFake()
    plan = needs_fix_plan(store, stage_repo, github_api)
    store.seed_comment(
        plan.number,
        _comment(pull, [finding(DefectType.CRITERION_DROPPED)]),
        author_association=association,
    )
    verifier.answer(Verification(findings=[finding(DefectType.TASK_ORDER, SAMPLE_QUOTE)]))
    model_fake.answer(make_stage_proposal(why=REPAIRED_WHY))

    run = _run(store, stage_repo, verifier)

    (first, *_) = planner_requests(model_fake)
    assert "Problem of task_order." in first["problem"]
    assert "criterion_dropped" not in first["problem"]
    assert run.attempt is not None
    assert run.attempt.comment == 0
