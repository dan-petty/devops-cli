"""A stage round writes each item when that item is done (#4034).

A kill of the worker or a stop of the Service ends the round and loses at most the item in
progress. The removals and the rejections of the items that the round does not select are written
before the first plan call, a rejection of a selected item between its plan and its publish, and
the moved paths of an item are read just before its publish. A plan with `--plan` writes nothing.

The roadmap is the in-memory store, the model edge is the fake, GitHub is answered at its HTTP edge
and git runs on a temporary repository. The rounds run as `devops roadmap stage --confirm` runs
them (`stage_round`) and through the commands, so no test names a writer.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
    CONST_ROADMAP_STAGE_REJECTED_MARKER,
)
from devops_cli.exceptions import RoadmapStageError, ServiceStoppingError, ended_by_stop
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.body_hash import body_hashes
from devops_cli.roadmap.service_stop import begin_service_stop
from devops_cli.roadmap.stores.store import CloseReason, ItemField, StageRecordKey
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import (
    STAGE_NAME,
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    advance_origin,
    no_findings,
    seed_stageable,
    stage_round,
    validate_args,
)
from tests.support.service_stop import stop_error

if TYPE_CHECKING:
    from pathlib import Path

    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

Cli = Callable[..., Any]

PULLS = f"/repos/{STAGE_REPO}/pulls"
TOPICS = ("comment", "label", "milestone", "assignee", "reviewer")
CLOSED_AT = datetime(2026, 11, 2, 20, 22, 45, tzinfo=UTC)
EVIDENCE = (
    "The premise does not hold: `src/devops_cli/roadmap/runner_tools.py` names `bwrap` in "
    "`NOT_IN_RUNNER`, so the runner can run no review. I ran the command and it failed closed."
)
MOVED = {"src/devops_cli/sample.py": "def keep(comments):\n    return comments\n"}


class WorkerKilled(BaseException):
    """The kill of the worker: a `BaseException`, so no handler of the job catches it."""


def _title(number: int) -> str:
    return f"fix(roadmap): the job drops a {TOPICS[number - 1]}"


def _branch(number: int) -> str:
    return f"fix/{number}-the-job-drops-a-{TOPICS[number - 1]}"


def _opened(number: int) -> Any:
    return github_json(
        {"number": number, "html_url": f"https://example.com/pull/{number}"}, status=201
    )


def _roadmap(count: int, openspec: OpenSpecFake, api: GitHubApiFake) -> InMemoryRoadmapStore:
    """`count` Ready bugs, numbered from 1, and the draft pull request that each one gets. GitHub
    numbers the pull requests after the issues, in the order the round opens them."""
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    store.seed_file(
        ".github/labels.yml",
        '- name: "type/docs"\n  color: "0075ca"\n- name: "scope/openspec"\n  color: "0e8a16"\n',
    )
    for number in range(1, count + 1):
        seed_stageable(store, _title(number))
        openspec.script_sequence(
            validate_args(_branch(number).removeprefix("fix/")), (0, VALID_REPORT)
        )
    pulls = [
        store.seed_pull("staging PR", head_ref=_branch(n), draft=True) for n in range(1, count + 1)
    ]
    api.route("POST", PULLS, *(_opened(pull) for pull in pulls))
    return store


def _round(store: InMemoryRoadmapStore, repo: StageRepo) -> Any:
    return stage_round(store, repo)


def _number_of(prompt: str) -> int | None:
    """The item a planner request is about, and None for the request of the verification pass."""
    request = json.loads(prompt)
    return None if "plan" in request else int(request["number"])


def _pushed(repo: StageRepo) -> list[str]:
    return repo.origin_git("branch", "--format=%(refname:short)").split()


def _record(store: InMemoryRoadmapStore, number: int) -> dict[str, str]:
    item = store.item(number)
    assert item is not None
    return {k.value: v for k, v in item.job_record.items() if v is not None}


def _staged_comments(store: InMemoryRoadmapStore, number: int) -> list[str]:
    return [
        c.body
        for c in store.comments_on(number)
        if c.body.startswith(CONST_ROADMAP_STAGE_COMMENT_MARKER)
    ]


class _Journal(InMemoryRoadmapStore):
    """A store that keeps the order of the writes of a round with the plan calls that the model
    receives: `events` holds ("plan", n) for the plan of item n, ("comment", n, kind) and
    ("marks", n) for the writes the job makes as a job."""

    def __init__(self, **options: Any) -> None:
        super().__init__(**options)
        self.events: list[tuple[Any, ...]] = []

    def comment(self, number: int, body: str) -> None:
        kind = "rejected" if CONST_ROADMAP_STAGE_REJECTED_MARKER in body else "staged"
        self.events.append(("comment", number, kind))
        super().comment(number, body)

    def set_marks(self, item: Any, marks: Any, **options: Any) -> None:
        self.events.append(("marks", item.number))
        super().set_marks(item, marks, **options)

    def set_field(self, item: Any, field: ItemField, value: str | None, **options: Any) -> None:
        self.events.append(("field", item.number))
        super().set_field(item, field, value, **options)


def _journaled(count: int, openspec: OpenSpecFake, api: GitHubApiFake) -> _Journal:
    """The roadmap of `_roadmap` in a store that keeps a journal."""
    store = _Journal(repo=STAGE_REPO)
    store.seed_file(
        ".github/labels.yml",
        '- name: "type/docs"\n  color: "0075ca"\n- name: "scope/openspec"\n  color: "0e8a16"\n',
    )
    for number in range(1, count + 1):
        seed_stageable(store, _title(number))
    for number in range(1, count + 1):
        openspec.script_sequence(
            validate_args(_branch(number).removeprefix("fix/")), (0, VALID_REPORT)
        )
    return store


# ── A kill or a stop of the Service ───────────────────────────────────────────


def test_killed_between_items_the_first_item_is_written_and_the_others_have_nothing(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
) -> None:
    store = _roadmap(3, openspec_fake, github_api)
    no_findings(model_fake)

    def plan(prompt: str) -> Any:
        if _number_of(prompt) == 2:
            raise WorkerKilled("the worker was killed")
        return make_stage_proposal()

    model_fake.answer(plan)

    with pytest.raises(WorkerKilled, match="worker was killed"):
        _round(store, stage_repo)

    assert (
        _pushed(stage_repo),
        [json.loads(r.content)["head"] for r in github_api.sent if r.method == "POST"],
        _record(store, 1).get(StageRecordKey.PR.value),
        len(_staged_comments(store, 1)),
        [_record(store, n).get(StageRecordKey.BRANCH.value) for n in (2, 3)],
        [len(store.comments_on(n)) for n in (2, 3)],
    ) == ([_branch(1), "main"], [_branch(1)], "4", 1, [None, None], [0, 0])


def test_service_stopping_in_item_three_keeps_item_one_and_records_the_failure_of_item_two(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
) -> None:
    """Item 1 is staged, the plan of item 2 breaks a rule of the stage job and so fails that item,
    and the stop of the Service falls in the plan of item 3. Item 4 is never taken."""
    store = _roadmap(4, openspec_fake, github_api)
    no_findings(model_fake)

    def plan(prompt: str) -> Any:
        number = _number_of(prompt)
        if number == 2:
            return make_stage_proposal(pull_request_body="Fixes #4 now.")
        if number == 3:
            raise stop_error()
        return make_stage_proposal()

    model_fake.answer(plan)

    with pytest.raises(ServiceStoppingError) as stopped:
        _round(store, stage_repo)

    assert (
        ended_by_stop(stopped.value),
        _pushed(stage_repo),
        _record(store, 1).get(StageRecordKey.PR.value),
        len(_staged_comments(store, 1)),
        _record(store, 2).get(StageRecordKey.FAILED_ERROR.value),
        [StageRecordKey.FAILED_ERROR.value in _record(store, n) for n in (1, 3, 4)],
        [len(store.comments_on(n)) for n in (2, 3, 4)],
    ) == (
        True,
        [_branch(1), "main"],
        "5",
        1,
        RoadmapStageError.__name__,
        [False, False, False],
        [0, 0, 0],
    )


def test_a_stop_of_the_service_during_item_one_stages_it_and_takes_no_next_item(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
) -> None:
    """The Service gets SIGTERM while it plans item 1. Item 1 runs on to its draft pull request,
    then no next item starts: the round ends with the stop, records no failure, and leaves items
    2 and 3 for the next pod (#4485)."""
    store = _roadmap(3, openspec_fake, github_api)
    no_findings(model_fake)
    planned: list[int] = []

    def plan(prompt: str) -> Any:
        planned.append(_number_of(prompt))
        begin_service_stop()
        return make_stage_proposal()

    model_fake.answer(plan)

    with pytest.raises(ServiceStoppingError) as stopped:
        _round(store, stage_repo)

    assert (
        ended_by_stop(stopped.value),
        planned,
        _pushed(stage_repo),
        len(_staged_comments(store, 1)),
        [StageRecordKey.FAILED_ERROR.value in _record(store, n) for n in (1, 2, 3)],
        [len(store.comments_on(n)) for n in (2, 3)],
    ) == (True, [1], [_branch(1), "main"], 1, [False, False, False], [0, 0])


# ── The order of the writes ───────────────────────────────────────────────────


@pytest.fixture
def service_app(config: Callable[..., object]) -> None:
    """The Service App has the bot login `devops-roadmap[bot]`."""
    config(service={"github_app": {"slug": "devops-roadmap"}})


def _rejected(store: InMemoryRoadmapStore, api: GitHubApiFake, number: int) -> int:
    """Item `number` has a plan pull request that a person closed with no merge and a reason."""
    pull = store.seed_pull("docs(openspec): plan", head_ref=_branch(number))
    item = store.item(number)
    assert item is not None
    store.set_marks(
        item,
        {
            StageRecordKey.BRANCH: _branch(number),
            StageRecordKey.PR: str(pull),
            StageRecordKey.READY: str(pull),
            StageRecordKey.SHA: "abc",
            StageRecordKey.GROUPS: json.dumps([["Group", 100]]),
            StageRecordKey.TEXT_HASH: body_hashes(item.body)[0],
        },
    )
    store.seed_comment(pull, EVIDENCE, author_association="OWNER", author_login="alice")
    api.route(
        "GET",
        f"{PULLS}/{pull}",
        github_json(
            {
                "state": "closed",
                "merged": False,
                "draft": False,
                "closed_at": CLOSED_AT.isoformat(),
                "head": {"sha": "abc", "ref": _branch(number)},
            }
        ),
    )
    return pull


@pytest.mark.usefixtures("service_app")
def test_phase_order_removals_and_rejections_of_unselected_items_come_before_the_first_plan_call(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
) -> None:
    """Item 1 is closed and keeps the record of a branch that is gone: a removal. Item 2 has a plan
    that a person rejected: the round leaves it out. Item 3 is the one item the round plans."""
    store = _journaled(3, openspec_fake, github_api)
    store.seed_pull("staging PR", head_ref=_branch(1))  # pull 4
    store.seed_pull("staging PR", head_ref=_branch(2))  # pull 5
    store.seed_pull("staging PR", head_ref=_branch(3), draft=True)  # pull 6
    one = store.item(1)
    assert one is not None
    store.set_marks(one, {StageRecordKey.BRANCH: _branch(1), StageRecordKey.PR: "4"})
    store.close_by_hand(1, CloseReason.COMPLETED)
    _rejected(store, github_api, 2)
    github_api.route("POST", PULLS, _opened(6))
    store.events.clear()
    no_findings(model_fake)

    def plan(prompt: str) -> Any:
        number = _number_of(prompt)
        store.events.append(("plan", number))
        return make_stage_proposal()

    model_fake.answer(plan)

    _round(store, stage_repo)

    assert store.events == [
        ("marks", 1),
        ("comment", 2, "rejected"),
        ("field", 2),
        ("plan", 3),
        ("marks", 3),  # the intent mark, before the push
        ("marks", 3),  # the record, after the draft
        ("comment", 3, "staged"),
    ]


@pytest.mark.usefixtures("service_app")
def test_phase_order_a_rejection_of_a_selected_item_falls_between_its_plan_and_its_publish(
    cli: Cli,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
    roadmap_store: InMemoryRoadmapStore,
) -> None:
    """A person names the item whose plan they rejected, so the round plans it again. The staged
    branch of the rejected plan goes before the new push and the Status of the item stays Ready."""
    openspec_fake.script_sequence(validate_args(_branch(1).removeprefix("fix/")), (0, VALID_REPORT))
    roadmap_store.seed_file(
        ".github/labels.yml",
        '- name: "type/docs"\n  color: "0075ca"\n- name: "scope/openspec"\n  color: "0e8a16"\n',
    )
    seed_stageable(roadmap_store, _title(1))
    pull = _rejected(roadmap_store, github_api, 1)
    stage_repo.push_branch(_branch(1), author=STAGE_NAME)
    github_api.route("POST", PULLS, _opened(pull + 1))
    roadmap_store.seed_pull("staging PR", head_ref=_branch(1), draft=True)
    order: list[str] = []
    no_findings(model_fake)

    def plan(prompt: str) -> Any:
        order.append(f"plan:{_branch(1) in _pushed(stage_repo)}")
        return make_stage_proposal()

    model_fake.answer(plan)

    result = cli(
        "roadmap", "stage", "--repo", STAGE_REPO, "--source", str(stage_repo.clone),
        "--item", "1", "--confirm",
    )  # fmt: skip

    item = roadmap_store.item(1)
    assert item is not None
    assert result.exit_code == 0, result.output
    assert (
        order,
        item.status,
        _record(roadmap_store, 1).get(StageRecordKey.PR.value),
        StageRecordKey.REJECTED.value in _record(roadmap_store, 1),
        [
            CONST_ROADMAP_STAGE_REJECTED_MARKER in c.body
            for c in roadmap_store.comments_on(1)
            if c.body.startswith(CONST_ROADMAP_STAGE_COMMENT_MARKER)
        ],
    ) == (
        ["plan:True"],
        "Ready",
        str(pull + 1),
        False,
        [True, False],
    )
    assert _pushed(stage_repo) == [_branch(1), "main"]


def test_phase_order_the_moved_paths_are_read_for_each_item_just_before_its_publish(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
    tmp_path: Path,
) -> None:
    """A commit that changes a named path lands on the default branch during the plan of item 2.
    Item 1 was written before it landed, so its comment lists no moved path. Item 2 is written
    after, so its comment does."""
    store = _roadmap(2, openspec_fake, github_api)
    no_findings(model_fake)

    def plan(prompt: str) -> Any:
        if _number_of(prompt) == 2:
            advance_origin(stage_repo, tmp_path, MOVED)
        return make_stage_proposal()

    model_fake.answer(plan)

    _round(store, stage_repo)

    assert [
        MESSAGES.roadmap.stage_comment_moved in _staged_comments(store, n)[0] for n in (1, 2)
    ] == [False, True]


# ── A plan writes nothing ─────────────────────────────────────────────────────


@pytest.mark.usefixtures("service_app")
def test_plan_only_the_command_makes_no_write_for_a_removal_a_rejection_or_a_ready_item(
    cli: Cli,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
    roadmap_store: InMemoryRoadmapStore,
) -> None:
    for number in range(1, 4):
        seed_stageable(roadmap_store, _title(number))
    roadmap_store.seed_pull("staging PR", head_ref=_branch(1))
    roadmap_store.seed_pull("staging PR", head_ref=_branch(2))
    one = roadmap_store.item(1)
    assert one is not None
    roadmap_store.set_marks(one, {StageRecordKey.BRANCH: _branch(1), StageRecordKey.PR: "4"})
    roadmap_store.close_by_hand(1, CloseReason.COMPLETED)
    _rejected(roadmap_store, github_api, 2)
    openspec_fake.script_sequence(validate_args(_branch(3).removeprefix("fix/")), (0, VALID_REPORT))
    before = len(roadmap_store.writes)
    no_findings(model_fake)
    model_fake.answer(make_stage_proposal())

    result = cli(
        "roadmap", "stage", "--repo", STAGE_REPO, "--source", str(stage_repo.clone), "--plan"
    )

    assert result.exit_code == 0, result.output
    assert (
        roadmap_store.writes[before:],
        [r.method for r in github_api.sent if r.method != "GET"],
        _pushed(stage_repo),
        [item.status for item in map(roadmap_store.item, (2, 3)) if item],
    ) == ([], [], ["main"], ["Ready", "Ready"])
    assert "# Stage plan for example/roadmap" in result.output
