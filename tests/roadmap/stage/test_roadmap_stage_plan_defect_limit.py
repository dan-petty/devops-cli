"""`devops roadmap stage`: the limit of refused plans on one body (#4491).

The job counts the `plan_defect` failures of an item on the same body in `stage.plan_defects`, with
the hash of that body in `stage.plan_defects_body`. A body edit starts a new count, and a failure
of another class leaves the count as it is. The failure that reaches
`roadmap.stage.plan_defect_limit` (#5440) returns the item to New with one comment that lists the
problems of the last plan: the problem of each refused reply, and then the reason of the failure
when the checks did not refuse the last reply. It clears the count. A staged item clears the count
too.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.config.constants import CONST_ROADMAP_STAGE_COMMENT_MARKER
from devops_cli.config.settings import load_settings
from devops_cli.exceptions import RoadmapStageError
from devops_cli.roadmap.failure import FailureClass, StepName
from devops_cli.roadmap.run import _run_stage_adapter
from devops_cli.roadmap.stage.stage import StageFailure, StagePlan
from devops_cli.roadmap.stores.store import StageRecordKey
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    apply_stage,
    no_findings,
    seed_stageable,
    validate_args,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

# A time long past, so the wait of each failure has passed when a round of the Service runs.
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


def _limit() -> int:
    """The limit of refused plans: the setting, which a test reads when it runs."""
    return load_settings().roadmap.stage.plan_defect_limit


REASON = (
    "The change still fails its checks after return 3 (no extra return: a finding of the gate "
    "paths stays from the reply before): Group 1 names no test."
)
PROBLEMS = (
    "Group 1 changes `src/devops_cli/lang/en/messages.py` and names no existing test of that module.",
    "The Feasibility section names the tool `references`, but the run did not call it.",
)
# The reason of a plan run that stops after the checks refused a reply (#4491).
STOP = "The plan run stopped: the run reached its request limit of 40."
# A path that the plan changes and that the clone does not hold, so the `paths` gate refuses it.
MISSING = "tests/test_missing.py"


def _record(store: InMemoryRoadmapStore, number: int) -> dict[str, str]:
    item = store.item(number)
    assert item is not None
    return {key.value: value for key, value in item.job_record.items() if value is not None}


def _count(store: InMemoryRoadmapStore, number: int) -> str | None:
    return _record(store, number).get(StageRecordKey.PLAN_DEFECTS.value)


def _status(store: InMemoryRoadmapStore, number: int) -> str | None:
    item = store.item(number)
    assert item is not None
    return item.status


def _fail(
    store: InMemoryRoadmapStore,
    number: int,
    failure_class: FailureClass = FailureClass.PLAN_DEFECT,
    problems: tuple[str, ...] = PROBLEMS,
    *,
    reason: str = REASON,
    stopped_by_checks: bool = True,
) -> None:
    """Write one failure of item `number`, as the job writes the failure of a plan. By default the
    checks refused the last reply, so `reason` is the refusal of the last problem."""
    item = store.item(number)
    assert item is not None
    failure = StageFailure(
        number,
        item.title,
        "RoadmapStageError",
        reason,
        item,
        failure_class=failure_class,
        step=StepName.PLAN,
        problems=problems,
        stopped_by_checks=stopped_by_checks,
    )
    apply_stage(store, StagePlan(STAGE_REPO, failed=(failure,)), source=".", now=NOW)


def _fail_to_the_limit(store: InMemoryRoadmapStore, number: int, *, less: int = 0) -> None:
    for _ in range(_limit() - less):
        _fail(store, number)


def _bullets(comment: str) -> list[str]:
    return [line for line in comment.splitlines() if line.startswith("- ")]


def _stage_comments(store: InMemoryRoadmapStore, number: int) -> list[str]:
    return [
        comment.body
        for comment in store.comments_on(number)
        if CONST_ROADMAP_STAGE_COMMENT_MARKER in comment.body
    ]


def test_the_limit_is_three_refused_plans() -> None:
    # 5 of the 6 plans that staged in 48 hours came after 2 refused plans (#4491).
    assert _limit() == 3


def test_a_refused_plan_counts_one_with_the_hash_of_its_body() -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = seed_stageable(store)

    _fail(store, number)

    record = _record(store, number)
    assert record[StageRecordKey.PLAN_DEFECTS.value] == "1"
    assert len(record[StageRecordKey.PLAN_DEFECTS_BODY.value]) == 64
    assert record[StageRecordKey.FAILED_CLASS.value] == FailureClass.PLAN_DEFECT.value


def test_a_second_refused_plan_on_the_same_body_counts_two() -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = seed_stageable(store)
    _fail(store, number)
    first = _record(store, number)[StageRecordKey.PLAN_DEFECTS_BODY.value]

    _fail(store, number)

    assert _count(store, number) == "2"
    assert _record(store, number)[StageRecordKey.PLAN_DEFECTS_BODY.value] == first
    assert _status(store, number) == "Ready"


def test_a_body_edit_starts_a_new_count() -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = seed_stageable(store)
    _fail_to_the_limit(store, number, less=1)
    store.edit_body_by_hand(
        number, "The job drops the last comment of a thread. It also drops one."
    )

    _fail(store, number)

    assert _count(store, number) == "1"
    assert _status(store, number) == "Ready"
    assert _stage_comments(store, number) == []


@pytest.mark.parametrize(
    "failure_class",
    [FailureClass.PROVIDER, FailureClass.PARSER, FailureClass.CI_INFRA, FailureClass.HEAD_MOVED],
)
def test_a_failure_of_another_class_keeps_the_count_and_its_wait(
    failure_class: FailureClass,
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = seed_stageable(store)
    _fail_to_the_limit(store, number, less=1)

    _fail(store, number, failure_class)

    assert _count(store, number) == str(_limit() - 1)
    assert _record(store, number)[StageRecordKey.FAILED_CLASS.value] == failure_class.value
    assert _status(store, number) == "Ready"


def test_the_refused_plan_at_the_limit_returns_the_item_to_new_with_its_problems() -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = seed_stageable(store)

    _fail_to_the_limit(store, number)

    assert _status(store, number) == "New"
    record = _record(store, number)
    assert StageRecordKey.PLAN_DEFECTS.value not in record
    assert StageRecordKey.PLAN_DEFECTS_BODY.value not in record
    assert record[StageRecordKey.FAILED_CLASS.value] == FailureClass.PLAN_DEFECT.value
    [comment] = _stage_comments(store, number)
    assert f"{_limit()} times" in comment
    assert _bullets(comment) == [f"- {problem}" for problem in PROBLEMS]


def test_the_setting_moves_the_limit_of_refused_plans(config: Callable[..., Path]) -> None:
    """The job reads `roadmap.stage.plan_defect_limit` at each failure (#5440)."""
    config(roadmap={"stage": {"plan_defect_limit": 5}})
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = seed_stageable(store)

    for _ in range(4):
        _fail(store, number)
    held = (_status(store, number), _count(store, number))
    _fail(store, number)

    assert (held, _status(store, number)) == (("Ready", "4"), "New")
    [comment] = _stage_comments(store, number)
    assert "5 times" in comment


def test_a_failure_after_the_refused_replies_gives_its_reason_after_their_problems() -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = seed_stageable(store)
    _fail_to_the_limit(store, number, less=1)

    _fail(store, number, reason=STOP, stopped_by_checks=False)

    [comment] = _stage_comments(store, number)
    assert _bullets(comment) == [*(f"- {problem}" for problem in PROBLEMS), f"- {STOP}"]


def test_a_refused_plan_with_no_kept_problem_gives_its_reason_as_the_evidence() -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = seed_stageable(store)
    _fail_to_the_limit(store, number, less=1)

    _fail(store, number, problems=())

    [comment] = _stage_comments(store, number)
    assert f"- {REASON}" in comment


def test_the_problems_of_the_comment_ping_no_one_and_stay_on_one_line() -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = seed_stageable(store)
    _fail_to_the_limit(store, number, less=1)

    _fail(store, number, problems=("Ask @someone about\nthe test.",))

    [comment] = _stage_comments(store, number)
    assert "- Ask `@someone` about the test." in comment


# ── Through the round of the Service ─────────────────────────────────────────

PULLS = f"/repos/{STAGE_REPO}/pulls"
TITLES = ("fix(roadmap): the job drops a comment", "fix(roadmap): the job drops a label")
BRANCHES = ("1-the-job-drops-a-comment", "2-the-job-drops-a-label")


def _two_items(
    store: InMemoryRoadmapStore, openspec: OpenSpecFake, api: GitHubApiFake
) -> InMemoryRoadmapStore:
    """Two Ready bugs and the draft pull request that each one gets."""
    store.seed_file(
        ".github/labels.yml",
        '- name: "type/docs"\n  color: "0075ca"\n- name: "scope/openspec"\n  color: "0e8a16"\n',
    )
    for title, branch in zip(TITLES, BRANCHES, strict=True):
        seed_stageable(store, title)
        openspec.script_sequence(validate_args(branch), (0, VALID_REPORT))
    pulls = [
        store.seed_pull("staging PR", head_ref=f"fix/{branch}", draft=True) for branch in BRANCHES
    ]
    api.route(
        "POST",
        PULLS,
        *(
            github_json(
                {"number": pull, "html_url": f"https://example.com/pull/{pull}"}, status=201
            )
            for pull in pulls
        ),
    )
    return store


def _plan_answers(model_fake: ModelFake, **proposal: Any) -> None:
    """Item 1 gets a proposal with the `proposal` fields, and item 2 gets a good plan."""

    def plan(prompt: str) -> Any:
        request = json.loads(prompt)
        if "plan" in request or request["number"] != 1:
            return make_stage_proposal()
        return make_stage_proposal(**proposal)

    no_findings(model_fake)
    model_fake.answer(plan)


def test_a_round_returns_an_item_whose_plan_the_checks_refuse_at_the_limit(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
) -> None:
    store = _two_items(InMemoryRoadmapStore(repo=STAGE_REPO), openspec_fake, github_api)
    _fail_to_the_limit(store, 1, less=1)
    _plan_answers(model_fake, pull_request_body="Fixes #4 now.")

    _run_stage_adapter(store, repo=STAGE_REPO, clone_path=stage_repo.clone)

    assert _status(store, 1) == "New"
    [comment] = _stage_comments(store, 1)
    # The problems of the refused replies, not the text of the error.
    problems = _bullets(comment)
    assert problems
    assert all("closing keyword" in line for line in problems)
    assert "still fails its checks" not in comment
    assert StageRecordKey.BRANCH.value in _record(store, 2)


def test_a_round_gives_the_reason_of_a_plan_run_that_stops_after_a_refused_reply(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
) -> None:
    store = _two_items(InMemoryRoadmapStore(repo=STAGE_REPO), openspec_fake, github_api)
    _fail_to_the_limit(store, 1, less=1)

    def plan(prompt: str) -> Any:
        request = json.loads(prompt)
        if "plan" in request or request["number"] != 1:
            return make_stage_proposal()
        if "previous" in request:
            raise RoadmapStageError(STOP)
        group = make_stage_proposal().groups[0]
        return make_stage_proposal(
            groups=[group.model_copy(update={"changes": [*group.changes, MISSING]})]
        )

    no_findings(model_fake)
    model_fake.answer(plan)

    _run_stage_adapter(store, repo=STAGE_REPO, clone_path=stage_repo.clone)

    assert _status(store, 1) == "New"
    [comment] = _stage_comments(store, 1)
    [refused, last] = _bullets(comment)
    assert MISSING in refused
    assert last == f"- {STOP}"


def test_a_staged_item_clears_its_count(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
) -> None:
    store = _two_items(InMemoryRoadmapStore(repo=STAGE_REPO), openspec_fake, github_api)
    _fail_to_the_limit(store, 1, less=1)
    _plan_answers(model_fake)

    _run_stage_adapter(store, repo=STAGE_REPO, clone_path=stage_repo.clone)

    record = _record(store, 1)
    assert StageRecordKey.BRANCH.value in record
    assert StageRecordKey.PLAN_DEFECTS.value not in record
    assert StageRecordKey.PLAN_DEFECTS_BODY.value not in record
