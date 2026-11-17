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
from devops_cli.roadmap.stage.plan_state import event_key, state_key
from devops_cli.roadmap.stage.stage_eval_cases import DefectType, Severity
from devops_cli.roadmap.stage.stage_toolbox import ToolboxModel
from devops_cli.roadmap.stage.stage_verify import (
    FIX_PLAN_LABEL,
    PlanPart,
    Verification,
)
from devops_cli.roadmap.steps.fix_plan import (
    FixPlanResult,
    FixPlanRun,
    comment_open_findings,
    plan_comment,
    render_fix_plan,
    run_fix_plan,
)
from tests.support.builders import make_stage_proposal
from tests.support.fakes.model import ModelFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.paths import FIXTURES
from tests.support.roadmap_fix_plan import (
    ISSUE_QUOTE,
    PLAN_BRANCH,
    REPAIRED_WHY,
    SAMPLE_QUOTE,
    finding,
    needs_fix_plan,
    place,
    planner_requests,
    stage_comment,
    state_comment,
    valid_changes,
)
from tests.support.roadmap_job_result import result_fields
from tests.support.roadmap_stage import GONE, HOLDS, STAGE_REPO, StageRepo, later_review

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

# A real stage comment. Each finding line names its place as `<part> (<section>)` (#5410).
STAGE_COMMENT = (FIXTURES / "roadmap_fix_plan" / "stage_comment.txt").read_text(encoding="utf-8")
# The plan pull request that the real stage comment names.
STAGE_COMMENT_PULL = 4980


@pytest.fixture(autouse=True)
def openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    valid_changes(openspec_fake)
    return openspec_fake


def test_the_reader_reads_the_open_findings_of_a_real_stage_comment() -> None:
    (read,) = comment_open_findings(STAGE_COMMENT)

    assert (read.type, read.where) == (
        DefectType.CRITERION_DROPPED,
        place("spec", "Readiness reads the file list at the merge base"),
    )
    assert read.problem.startswith("The issue's criterion that no request path")
    assert read.quote.startswith("No request path of the readiness run ends with")


def test_a_line_from_before_5411_names_no_severity_and_reads_as_major() -> None:
    """The real stage comment names no severity: each open finding of that release kept the
    draft, so it reads as a major finding (#5411)."""
    (read,) = comment_open_findings(STAGE_COMMENT)

    assert "- `criterion_dropped` at spec" in STAGE_COMMENT
    assert read.severity is Severity.MAJOR


def test_the_reader_reads_back_each_open_finding_and_no_point() -> None:
    open_ = [
        finding(DefectType.TASK_ORDER, severity=Severity.BLOCKER),
        finding(DefectType.CRITERION_DROPPED, quote="", where=place("issue", ISSUE_QUOTE)),
        finding(
            DefectType.SPEC_DELTA_WRONG,
            where=place("spec", "A release (of a claim) keeps it", "a/b"),
        ),
    ]
    point = finding(DefectType.OTHER, where=place("tasks", "2"))

    assert comment_open_findings(stage_comment(5, open_, [point])) == tuple(open_)


def test_the_reader_reads_back_a_section_with_brackets_and_no_capability() -> None:
    open_ = [
        finding(DefectType.FALSE_PREMISE, where=place("proposal", "what_changes (item 2)")),
        finding(DefectType.CRITERION_DROPPED, where=place("issue", "The row runs (fast): yes")),
        finding(DefectType.OTHER, where=place("spec", "A release (of a claim)", "a/b")),
    ]

    assert comment_open_findings(stage_comment(5, open_)) == tuple(open_)


def test_the_reader_reads_a_finding_line_of_the_old_form() -> None:
    order = finding(DefectType.TASK_ORDER)
    body = (
        stage_comment(5, [order])
        .replace(
            "at tasks (1):",
            "at group 3 (and group 1):",
        )
        .replace(
            "`task_order`",
            "`other`",
        )
    )
    (read,) = comment_open_findings(body)

    assert (read.type, read.severity, read.where.part, read.where.section) == (
        DefectType.OTHER,
        Severity.MAJOR,
        PlanPart.TASKS,
        "group 3 (and group 1)",
    )


def test_the_reader_leaves_out_a_line_whose_place_names_no_part(
    caplog: pytest.LogCaptureFixture,
) -> None:
    kept = finding(DefectType.TASK_ORDER)
    body = stage_comment(5, [kept]).replace(
        "\n- major `task_order`",
        "\n- major `other` at unknown (the dry run): The dry run lists no read.\n"
        "- major `task_order`",
    )

    with caplog.at_level(logging.WARNING):
        read = comment_open_findings(body)

    assert read == (kept,)
    assert "read 1 of the 2 lines" in caplog.text


@pytest.mark.parametrize(
    "body",
    [
        f"{CONST_ROADMAP_STAGE_COMMENT_MARKER}\nStaged: draft pull request #5.",
        stage_comment(5, [], [finding(DefectType.OTHER)]),
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
    verifier.answer(Verification(findings=[dropped, order]), later_review(HOLDS, GONE))
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
    assert MESSAGES.roadmap.fix_plan_detail_repaired.format(before=2, after=1) in render_fix_plan(
        run
    )
    assert "The last plan comment listed 1 open finding(s)." in render_fix_plan(run)


def test_the_planner_gets_the_open_findings_of_the_comment_and_of_the_review_of_the_head(
    stage_repo: StageRepo, model_fake: ModelFake, github_api: GitHubApiFake
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    verifier = ModelFake()
    plan = needs_fix_plan(store, stage_repo, github_api)
    store.seed_comment(plan.number, _real_comment(plan.pull))
    order = finding(DefectType.TASK_ORDER, SAMPLE_QUOTE)
    verifier.answer(Verification(findings=[order]), later_review(GONE))
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
    assert FIX_PLAN_LABEL not in store._roadmap.issues[plan.pull].labels


def test_a_head_that_its_review_finds_clean_keeps_the_label_when_the_comment_lists_a_finding(
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
        FixPlanResult.UNCHANGED,
        0,
        None,
    )
    assert run.attempt.comment == 1
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) == plan.head
    assert FIX_PLAN_LABEL in store._roadmap.issues[plan.pull].labels


def test_two_lines_the_reader_cannot_read_keep_the_label(
    stage_repo: StageRepo,
    github_api: GitHubApiFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    verifier = ModelFake()
    plan = needs_fix_plan(store, stage_repo, github_api)
    kept = finding(DefectType.TASK_ORDER)
    body = stage_comment(plan.pull, [kept]).replace(
        "\n- major `task_order`",
        "\n- a line that matches no form\n- another line that matches no form",
    )
    store.seed_comment(plan.number, body)

    with caplog.at_level(logging.INFO):
        run = _run(store, stage_repo, verifier)

    assert run.attempt is not None
    assert run.attempt.result.value == "unreadable_findings"
    assert FIX_PLAN_LABEL in store._roadmap.issues[plan.pull].labels
    (line,) = result_fields(caplog)
    assert line["result"] == "unreadable_findings"
    assert line["unreadable"] == "2"


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
        stage_comment(pull, [finding(DefectType.CRITERION_DROPPED)]),
        author_association=association,
    )
    verifier.answer(
        Verification(findings=[finding(DefectType.TASK_ORDER, SAMPLE_QUOTE)]),
        later_review(HOLDS),
    )
    model_fake.answer(make_stage_proposal(why=REPAIRED_WHY))

    run = _run(store, stage_repo, verifier)

    (first, *_) = planner_requests(model_fake)
    assert "Problem of task_order." in first["problem"]
    assert "criterion_dropped" not in first["problem"]
    assert run.attempt is not None
    assert run.attempt.comment == 0


# ── The plan-state comment (#6197) ────────────────────────────────────────────


def _event(pull: int) -> str:
    """A comment of an attempt in the form of #6197: it names the pull request and lists no open
    finding."""
    return (
        f"{CONST_ROADMAP_FIX_PLAN_COMMENT_MARKER}\n{event_key(pull)}\nThe step fix-plan stopped "
        f"before the review of the plan of #{pull}."
    )


def test_the_plan_comment_is_the_state_comment_of_the_pull_request_and_no_newer_comment() -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = store.seed_issue("An item")
    kept = finding(DefectType.CRITERION_DROPPED)
    store.seed_comment(number, state_comment(5, [kept]))
    store.seed_comment(number, state_comment(6, [finding(DefectType.TASK_ORDER)]))
    store.seed_comment(number, stage_comment(5, []))
    store.seed_comment(number, _event(5))

    assert comment_open_findings(plan_comment(store, number, 5)) == (kept,)


def test_with_no_state_comment_the_plan_comment_is_the_newest_legacy_one_and_no_event() -> None:
    """A pull request staged before #6197 has no state comment: the newest legacy plan comment
    holds its findings, and a newer comment of a run lists none, so the read skips it."""
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = store.seed_issue("An item")
    legacy = stage_comment(5, [finding(DefectType.CRITERION_DROPPED)])
    store.seed_comment(number, legacy)
    store.seed_comment(number, _event(5))

    assert plan_comment(store, number, 5) == legacy


def test_an_attempt_edits_the_state_comment_and_its_comment_lists_no_open_finding(
    stage_repo: StageRepo, model_fake: ModelFake, github_api: GitHubApiFake
) -> None:
    """The attempt pushes a revision that keeps 1 of the 2 open findings of the head. The state
    comment of the pull request gets that finding and the groups of the pushed plan in place, and
    the comment of the attempt holds the counts and no list of open findings."""
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    verifier = ModelFake()
    plan = needs_fix_plan(store, stage_repo, github_api)
    dropped = finding(DefectType.CRITERION_DROPPED)
    old_groups = (
        "\n\nThe task groups, with the tokens of the inputs of each step, for a budget of 9 "
        "tokens:\n\n1. An old group: 3 tokens"
    )
    store.seed_comment(plan.number, state_comment(plan.pull, [dropped], groups=old_groups))
    order = finding(DefectType.TASK_ORDER, SAMPLE_QUOTE)
    verifier.answer(Verification(findings=[dropped, order]), later_review(HOLDS, GONE))
    model_fake.answer(make_stage_proposal(why=REPAIRED_WHY))

    run = _run(store, stage_repo, verifier)

    assert run.attempt is not None
    assert run.attempt.result is FixPlanResult.REVISED
    state, event = [comment.body for comment in store.comments_on(plan.number)]
    assert (
        state.startswith(f"{CONST_ROADMAP_STAGE_COMMENT_MARKER}\n{state_key(plan.pull)}\n"),
        comment_open_findings(state) == (dropped,),
        "An old group" in state,
        "1. Keep the last comment:" in state,
        event.startswith(f"{CONST_ROADMAP_FIX_PLAN_COMMENT_MARKER}\n{event_key(plan.pull)}\n"),
        "2 open finding(s) in the plan before the repair and 1 after it" in event,
        comment_open_findings(event) == (),
        "Problem of criterion_dropped." in event,
    ) == (True, True, False, True, True, True, True, False)
