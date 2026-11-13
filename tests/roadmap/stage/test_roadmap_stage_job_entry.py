"""The stage Job: `devops roadmap stage --job-item <n>` plans one item in a pod of its own (#5483).

The selection is the normal one, narrowed to the item. The entry point holds one model call
slot, a request budget and a time budget, and ends with the exit code of the Kubernetes Job:
0 for a result, 1 for a failure, 75 for an eviction, which the pod failure policy runs again,
and 143 for the deadline. At its end the Job checks in: it writes its result and clears the
check-out of the Service, only when the check-out names this Job. Then it writes the result line
of its attempt to stderr, only when its check-in found its check-out (#5556).
"""

from __future__ import annotations

import ast
import inspect
import json
import logging
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import ValidationError

from devops_cli.ai.client import network
from devops_cli.config.constants import (
    CONST_GITHUB_APP_PRIVATE_KEY_ENV,
    CONST_ROADMAP_OWNER_SERVICE,
)
from devops_cli.config.settings import RoadmapConfig
from devops_cli.core import clock as clock_seam
from devops_cli.exceptions import GitHubOperationError, RoadmapStageError
from devops_cli.roadmap.attempt_kill import AttemptKill, AttemptKilled
from devops_cli.roadmap.body_hash import body_hashes
from devops_cli.roadmap.job_result import LINE_PREFIX
from devops_cli.roadmap.planned import PlannedChanges
from devops_cli.roadmap.stage import stage_job
from devops_cli.roadmap.stage.stage import parse_filters, select_stageable
from devops_cli.roadmap.stage.stage_change import StageProposal
from devops_cli.roadmap.stage.stage_job import (
    StageJobExit,
    job_time_budget,
    recorded_check_in,
    run_stage_job,
)
from devops_cli.roadmap.stage.stage_left_out import LeftOutKind
from devops_cli.roadmap.stage.stage_rejected import RejectedPlan
from devops_cli.roadmap.stores.store import ItemField, StageRecordKey
from devops_cli.telemetry.instruments import ROADMAP_STAGE_TOTAL
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_job_result import result_lines
from tests.support.roadmap_stage import (
    STAGE_NAME,
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    no_findings,
    seed_stageable,
    validate_args,
)

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake
    from tests.support.fakes.otlp import FakeCollector

pytestmark = pytest.mark.usefixtures("keyring_store")

Cli = Callable[..., Any]

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
JOB = "devops-cli-stage-roadmap-1-0123456789"
OTHER_JOB = "devops-cli-stage-roadmap-1-9876543210"
BRANCH = "fix/1-the-job-drops-a-comment"
PULLS = f"/repos/{STAGE_REPO}/pulls"
OPENED = github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201)
NO_PLANS = PlannedChanges("main", {}, {})
BUDGET = 9000
RESULT_LOGGER = "devops_cli.roadmap.job_result"


class StepClock:
    """The monotonic reading of the clock seam, moved only by the test."""

    def __init__(self) -> None:
        self._now = 0.0

    def monotonic(self) -> float:
        return self._now

    def shift(self, seconds: float) -> None:
        self._now += seconds


@pytest.fixture
def step_clock(monkeypatch: pytest.MonkeyPatch) -> StepClock:
    fake = StepClock()
    monkeypatch.setattr(clock_seam, "monotonic", fake.monotonic)
    return fake


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture(autouse=True)
def valid_openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    openspec_fake.script_sequence(validate_args("1-the-job-drops-a-comment"), (0, VALID_REPORT))
    return openspec_fake


@pytest.fixture
def stageable(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, config: Callable[..., Path]
) -> int:
    """One Ready bug that the Service checked out for the Job `JOB`, which this pod runs."""
    config(roadmap={"stage": {"job": JOB}})
    number = seed_stageable(store)
    _check_out(store, number, JOB)
    github_api.route("POST", PULLS, OPENED)
    return number


def _check_out(store: InMemoryRoadmapStore, number: int, job: str) -> None:
    item = store.item(number)
    assert item is not None
    store.set_marks(
        item,
        {
            StageRecordKey.JOB: job,
            StageRecordKey.JOB_AT: NOW.isoformat(),
            StageRecordKey.JOB_DEADLINE: (NOW + timedelta(hours=3)).isoformat(),
        },
    )


def _record(store: InMemoryRoadmapStore, number: int = 1) -> dict[str, str]:
    item = store.item(number)
    assert item is not None
    return {str(key): value for key, value in item.job_record.items() if value is not None}


def _check_out_marks(store: InMemoryRoadmapStore, number: int = 1) -> list[str]:
    record = _record(store, number)
    return [key for key in ("stage.job", "stage.job_at", "stage.job_deadline") if key in record]


def _pushed(repo: StageRepo) -> list[str]:
    return repo.origin_git("branch", "--format=%(refname:short)").split()


# ── The selection of `--job-item` ─────────────────────────────────────────────


def _selected(store: InMemoryRoadmapStore, number: int, *, named: bool) -> tuple[list[int], dict]:
    selection = select_stageable(
        store,
        filters=parse_filters(()),
        holder_of=lambda _issue, _branch: None,
        planned=NO_PLANS,
        item_number=number,
        named=named,
        limit=5,
        planned_limit=20,
        now=NOW,
    )
    return (
        [target.item.number for target in selection.selected],
        {left.number: left.kind for left in selection.left_out},
    )


def _mark(store: InMemoryRoadmapStore, number: int, marks: dict[StageRecordKey, str]) -> None:
    item = store.item(number)
    assert item is not None
    store.set_marks(item, marks)


def _rejected(store: InMemoryRoadmapStore, number: int) -> dict[StageRecordKey, str]:
    item = store.item(number)
    assert item is not None
    rejected = RejectedPlan(
        pull=9, text_hash=body_hashes(item.body)[0], closed_at=NOW - timedelta(days=1)
    )
    return {StageRecordKey.REJECTED: rejected.record}


def _failed_lately(_store: InMemoryRoadmapStore, _number: int) -> dict[StageRecordKey, str]:
    return {
        StageRecordKey.FAILED_AT: (NOW - timedelta(minutes=5)).isoformat(),
        StageRecordKey.FAILED_ERROR: "AIClientError",
    }


def _split(_store: InMemoryRoadmapStore, _number: int) -> dict[StageRecordKey, str]:
    from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS

    return {
        StageRecordKey.NEEDS_SPLIT: "group 1 holds 90000 tokens",
        StageRecordKey.FILE_CAP: str(CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS),
    }


@pytest.mark.parametrize(
    ("marks", "kind"),
    [
        pytest.param(_rejected, LeftOutKind.REJECTED, id="rejected-plan"),
        pytest.param(_failed_lately, LeftOutKind.FAILED_LATELY, id="failure-wait"),
        pytest.param(_split, LeftOutKind.RECORDED_SPLIT, id="recorded-split"),
    ],
)
def test_the_job_item_keeps_every_rule_of_the_normal_selection_and_a_named_item_overrules_them(
    store: InMemoryRoadmapStore,
    marks: Callable[[InMemoryRoadmapStore, int], dict[StageRecordKey, str]],
    kind: LeftOutKind,
) -> None:
    number = seed_stageable(store)
    _mark(store, number, marks(store, number))

    assert (
        _selected(store, number, named=False),
        _selected(store, number, named=True),
    ) == (([], {number: kind}), ([number], {}))


def test_the_job_item_takes_a_ready_item_with_no_mark(store: InMemoryRoadmapStore) -> None:
    number = seed_stageable(store)

    assert _selected(store, number, named=False) == ([number], {})


# ── The entry point ───────────────────────────────────────────────────────────


def test_a_normal_end_stages_the_item_writes_the_result_and_clears_the_check_out(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    stageable: int,
) -> None:
    model_fake.answer(make_stage_proposal())

    run = run_stage_job(store, repo=STAGE_REPO, item=stageable, source=stage_repo.clone, now=NOW)

    item = store.item(stageable)
    assert item is not None
    check_in = recorded_check_in(item)
    assert check_in is not None
    assert (
        run.exit_code,
        run.result,
        _check_out_marks(store),
        (check_in.job, check_in.result),
        _record(store)["stage.pr"],
    ) == (StageJobExit.RESULT, "staged", [], (JOB, "staged"), "5")


def test_a_job_that_the_check_out_does_not_name_writes_no_check_in(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    stageable: int,
) -> None:
    _check_out(store, stageable, OTHER_JOB)
    model_fake.answer(make_stage_proposal())

    run = run_stage_job(store, repo=STAGE_REPO, item=stageable, source=stage_repo.clone, now=NOW)

    record = _record(store)
    assert (run.exit_code, record["stage.job"], "stage.job_result" in record) == (
        StageJobExit.RESULT,
        OTHER_JOB,
        False,
    )


def test_a_failed_plan_exits_1_and_checks_in_with_the_failure(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    stageable: int,
) -> None:
    model_fake.answer("no plan at all")

    run = run_stage_job(store, repo=STAGE_REPO, item=stageable, source=stage_repo.clone, now=NOW)

    item = store.item(stageable)
    assert item is not None
    check_in = recorded_check_in(item)
    assert check_in is not None
    assert (run.exit_code, check_in.result, _check_out_marks(store)) == (
        StageJobExit.FAILURE,
        "failed",
        [],
    )
    assert "stage.failed_at" in _record(store)


# ── The result line of the Job ────────────────────────────────────────────────


class CheckInAtLine(logging.Handler):
    """The result of each result line, and whether the record of the item held the check-in of
    the Job when the line was logged."""

    def __init__(self, store: InMemoryRoadmapStore, number: int) -> None:
        super().__init__(logging.INFO)
        self.store, self.number = store, number
        self.lines: list[tuple[str, bool]] = []

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        if not message.startswith(LINE_PREFIX):
            return
        fields = dict(field.split("=", 1) for field in message.removeprefix(LINE_PREFIX).split())
        item = self.store.item(self.number)
        self.lines.append((fields["result"], item is not None and bool(recorded_check_in(item))))


@pytest.fixture
def check_in_at_line(store: InMemoryRoadmapStore, stageable: int) -> Iterator[CheckInAtLine]:
    handler = CheckInAtLine(store, stageable)
    logger = logging.getLogger(RESULT_LOGGER)
    level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        logger.setLevel(level)


def test_a_normal_end_logs_one_result_line_after_its_check_in(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    stageable: int,
    check_in_at_line: CheckInAtLine,
) -> None:
    """The actor that writes the check-in of an attempt writes its result line, so the Job and
    the recovery of the Service never both count one attempt (#5556)."""
    model_fake.answer(make_stage_proposal())

    run_stage_job(store, repo=STAGE_REPO, item=stageable, source=stage_repo.clone, now=NOW)

    assert check_in_at_line.lines == [("staged", True)]


def test_a_job_that_the_check_out_does_not_name_logs_no_result_line(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    stageable: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """While the Job plans, the Service ends its attempt, writes the line of a failed end, and
    checks the item out for a new Job. The Job writes no second line."""

    def recovered(_prompt: str) -> StageProposal:
        _check_out(store, stageable, OTHER_JOB)
        return make_stage_proposal()

    model_fake.answer(recovered)

    with caplog.at_level(logging.INFO, logger=RESULT_LOGGER):
        run_stage_job(store, repo=STAGE_REPO, item=stageable, source=stage_repo.clone, now=NOW)

    assert result_lines(caplog) == []


def test_the_counter_counts_the_item_also_when_the_job_logs_no_result_line(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    stageable: int,
    otlp: FakeCollector,
) -> None:
    """Only the result line waits for the check-in. `devops_cli_roadmap_stage_total` counts the
    item of the plan before the check-in, as a round does, and the recovery of the Service adds
    to another counter (#5556)."""

    def recovered(_prompt: str) -> StageProposal:
        _check_out(store, stageable, OTHER_JOB)
        return make_stage_proposal()

    model_fake.answer(recovered)

    run_stage_job(store, repo=STAGE_REPO, item=stageable, source=stage_repo.clone, now=NOW)

    assert [(attrs["result"], value) for attrs, value in otlp.points(ROADMAP_STAGE_TOTAL.name)] == [
        ("staged", 1.0)
    ]


def test_a_failed_check_in_logs_no_result_line(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    stageable: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The check-out stays, so the recovery of the Service checks in for the `failed` end of the
    Job and writes its line."""
    item = store.item(stageable)
    assert item is not None
    store.set_field(item, ItemField.OWNER, CONST_ROADMAP_OWNER_SERVICE)
    store.fail_write(write="set_field", item=stageable)
    model_fake.answer(make_stage_proposal())

    with (
        caplog.at_level(logging.INFO, logger=RESULT_LOGGER),
        pytest.raises(GitHubOperationError, match="HTTP 502"),
    ):
        run_stage_job(store, repo=STAGE_REPO, item=stageable, source=stage_repo.clone, now=NOW)

    assert (result_lines(caplog), _check_out_marks(store)[:1]) == ([], ["stage.job"])


def test_the_entry_holds_one_model_call_slot(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    stageable: int,
) -> None:
    model_fake.answer(make_stage_proposal())

    run_stage_job(store, repo=STAGE_REPO, item=stageable, source=stage_repo.clone, now=NOW)

    slots = network.get_model_call_limit()
    assert slots is not None
    assert (slots.acquire(blocking=False), slots.acquire(blocking=False)) == (True, False)


@pytest.mark.parametrize(
    "scoped",
    [pytest.param(None, id="no-token-repository"), pytest.param("example/other", id="other-repo")],
)
def test_a_job_that_acts_as_the_app_without_a_token_for_its_repository_runs_nothing(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    stageable: int,
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
    scoped: str | None,
) -> None:
    """A pod that holds the private key of the App plans only with a token for the one repository
    of the item: else the token covers every repository of the installation (#2667)."""
    monkeypatch.setenv(CONST_GITHUB_APP_PRIVATE_KEY_ENV, "app-key")
    config(service={"github_app": {"token_repository": scoped}})
    model_fake.answer(make_stage_proposal())

    with pytest.raises(RoadmapStageError, match=r"service\.github_app\.token_repository"):
        run_stage_job(store, repo=STAGE_REPO, item=stageable, source=stage_repo.clone, now=NOW)

    assert (model_fake.call_count, _check_out_marks(store)) == (
        0,
        ["stage.job", "stage.job_at", "stage.job_deadline"],
    )


def test_a_token_for_the_repository_of_the_job_passes_in_any_case(
    config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(CONST_GITHUB_APP_PRIVATE_KEY_ENV, "app-key")
    config(service={"github_app": {"token_repository": STAGE_REPO.upper()}})

    assert stage_job.require_job_token_scope(STAGE_REPO) is None


def test_a_person_without_the_app_key_runs_with_their_own_token(
    config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(CONST_GITHUB_APP_PRIVATE_KEY_ENV, raising=False)
    config(service={"github_app": {"token_repository": None}})

    assert stage_job.require_job_token_scope(STAGE_REPO) is None


@pytest.mark.usefixtures("step_clock")
def test_sigterm_before_the_budget_ends_exits_75_and_keeps_the_check_out(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    stageable: int,
) -> None:
    """An eviction or a drain: the Job controller runs the pod again, and the check-out stays."""
    model_fake.answer(AttemptKilled())

    run = run_stage_job(store, repo=STAGE_REPO, item=stageable, source=stage_repo.clone, now=NOW)

    record = _record(store)
    assert (
        run.exit_code,
        run.kill,
        _check_out_marks(store),
        "stage.job_result" in record,
        "stage.failed_at" in record,
    ) == (
        StageJobExit.EVICTED,
        AttemptKill.EVICTED,
        ["stage.job", "stage.job_at", "stage.job_deadline"],
        False,
        False,
    )


def test_sigterm_after_the_budget_exits_143_records_the_deadline_and_checks_in(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    step_clock: StepClock,
    stageable: int,
    config: Callable[..., Path],
) -> None:
    config(roadmap={"stage": {"job": JOB, "time_budget_seconds": BUDGET}})

    def slow_plan(_prompt: str) -> object:
        step_clock.shift(BUDGET + 1)
        return AttemptKilled()

    model_fake.answer(slow_plan)

    run = run_stage_job(store, repo=STAGE_REPO, item=stageable, source=stage_repo.clone, now=NOW)

    item = store.item(stageable)
    assert item is not None
    check_in = recorded_check_in(item)
    assert check_in is not None
    record = _record(store)
    assert (
        run.exit_code,
        run.kill,
        check_in.result,
        _check_out_marks(store),
        record["stage.failed_class"],
        record["stage.failed_at"],
        record["stage.plan_defects"],
    ) == (
        StageJobExit.DEADLINE,
        AttemptKill.DEADLINE,
        "deadline",
        [],
        "timeout",
        NOW.isoformat(),
        "1",
    )


def test_a_job_with_no_time_left_before_its_deadline_makes_no_model_call(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    stageable: int,
    config: Callable[..., Path],
) -> None:
    deadline = NOW + timedelta(seconds=600)
    config(roadmap={"stage": {"job": JOB, "job_deadline": deadline.isoformat()}})

    run = run_stage_job(store, repo=STAGE_REPO, item=stageable, source=stage_repo.clone, now=NOW)

    item = store.item(stageable)
    assert item is not None
    check_in = recorded_check_in(item)
    assert check_in is not None
    assert (run.exit_code, check_in.result, model_fake.call_count) == (
        StageJobExit.DEADLINE,
        "deadline",
        0,
    )


@pytest.mark.parametrize(
    ("deadline", "expected"),
    [
        pytest.param(None, BUDGET, id="no-deadline"),
        pytest.param(timedelta(seconds=10800), BUDGET, id="full-deadline"),
        pytest.param(timedelta(seconds=3000), 1200, id="retried-pod"),
        pytest.param(timedelta(seconds=1000), 0, id="no-time-left"),
    ],
)
def test_the_time_budget_is_the_setting_cut_to_the_deadline_less_the_margin(
    deadline: timedelta | None, expected: int
) -> None:
    """tool < step < Job deadline: the budget ends 1800 s before the deadline of the Job, which
    counts across the pods of the Job, so a pod that runs again gets the time that is left."""
    assert job_time_budget(BUDGET, None if deadline is None else NOW + deadline, NOW) == expected


@pytest.mark.parametrize(
    "roadmap",
    [
        pytest.param({"stage": {"time_budget_seconds": 9001}}, id="budget-past-the-deadline"),
        pytest.param(
            {"stage": {"time_budget_seconds": 30}, "mcp": {"timeout_seconds": 30}},
            id="budget-not-past-a-tool-call",
        ),
    ],
)
def test_the_settings_refuse_a_budget_that_breaks_the_nested_timeouts(
    roadmap: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError, match="time_budget_seconds"):
        RoadmapConfig.model_validate(roadmap)


def test_the_settings_of_the_stage_job_have_their_defaults() -> None:
    stage = RoadmapConfig().stage

    assert (
        stage.time_budget_seconds,
        stage.github_requests_per_hour,
        stage.job,
        stage.job_deadline,
    ) == (BUDGET, 1000, None, None)


def test_a_retried_pod_removes_its_own_orphan_and_stages_the_item_in_the_same_run(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    stageable: int,
) -> None:
    """The pod before was killed after its push: the mark of this Job names the branch. The mark
    is young, but the check-out names this Job, so no other run publishes the item."""
    _mark(
        store,
        stageable,
        {
            StageRecordKey.PENDING: json.dumps(
                {"branch": BRANCH, "time": (NOW - timedelta(minutes=2)).isoformat()}
            )
        },
    )
    stage_repo.push_branch(BRANCH, author=STAGE_NAME)
    model_fake.answer(make_stage_proposal())

    run = run_stage_job(store, repo=STAGE_REPO, item=stageable, source=stage_repo.clone, now=NOW)

    record = _record(store)
    assert run.applied is not None
    assert (
        run.exit_code,
        run.applied.removed,
        run.applied.staged,
        record["stage.pr"],
        "stage.pending" in record,
        _pushed(stage_repo),
    ) == (StageJobExit.RESULT, (stageable,), (stageable,), "5", False, [BRANCH, "main"])
    assert github_api.requested.count(f"POST https://api.github.com{PULLS}") == 1


def test_a_young_mark_of_another_job_keeps_the_age_rule(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    stageable: int,
) -> None:
    _check_out(store, stageable, OTHER_JOB)
    _mark(
        store,
        stageable,
        {
            StageRecordKey.PENDING: json.dumps(
                {"branch": BRANCH, "time": (NOW - timedelta(minutes=2)).isoformat()}
            )
        },
    )
    stage_repo.push_branch(BRANCH, author=STAGE_NAME)

    run = run_stage_job(store, repo=STAGE_REPO, item=stageable, source=stage_repo.clone, now=NOW)

    assert run.plan is not None
    assert (
        run.result,
        run.plan.removals,
        [left.kind for left in run.plan.left_out],
        model_fake.call_count,
    ) == ("skipped", (), [LeftOutKind.HELD], 0)


def test_the_entry_installs_a_request_budget_of_the_setting(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    stageable: int,
    config: Callable[..., Path],
) -> None:
    """Every GitHub request of the Job takes a place in the budget of the pod. The pull request of
    the draft is one such request, and at the limit the next request waits."""
    config(roadmap={"stage": {"job": JOB, "github_requests_per_hour": 1}})
    model_fake.answer(make_stage_proposal())

    run = run_stage_job(store, repo=STAGE_REPO, item=stageable, source=stage_repo.clone, now=NOW)

    assert (run.budget.limit, run.budget.spent(), run.budget.holds()) == (1, 1, True)


# ── The command ───────────────────────────────────────────────────────────────


def _stage(cli: Cli, repo: StageRepo, *args: str) -> Any:
    return cli("roadmap", "stage", "--repo", STAGE_REPO, "--source", str(repo.clone), *args)


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(("--job-item", "1", "--item", "1", "--confirm"), id="with-item"),
        pytest.param(("--job-item", "1", "--plan"), id="plan"),
        pytest.param(("--job-item", "1"), id="no-mode"),
    ],
)
def test_the_job_item_needs_confirm_and_no_item(
    cli: Cli, stage_repo: StageRepo, model_fake: ModelFake, args: tuple[str, ...]
) -> None:
    result = _stage(cli, stage_repo, *args)

    assert (result.exit_code, model_fake.call_count) == (1, 0)
    assert "--job-item" in result.output


def test_the_command_exits_with_the_code_of_the_job(
    cli: Cli,
    roadmap_store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
) -> None:
    config(roadmap={"stage": {"job": JOB}})
    github_api.route("POST", PULLS, OPENED)
    number = seed_stageable(roadmap_store)
    _check_out(roadmap_store, number, JOB)
    model_fake.answer(AttemptKilled())

    result = _stage(cli, stage_repo, "--job-item", str(number), "--confirm")

    assert result.exit_code == StageJobExit.EVICTED, result.output
    assert "evicted" in result.output


def test_the_command_writes_the_result_line_to_stderr(
    cli: Cli,
    roadmap_store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
) -> None:
    """The log of the pod is what the command writes, and Loki reads the plain line on stderr
    (#5556)."""
    config(roadmap={"stage": {"job": JOB}})
    github_api.route("POST", PULLS, OPENED)
    number = seed_stageable(roadmap_store)
    _check_out(roadmap_store, number, JOB)
    no_findings(model_fake)
    model_fake.answer(make_stage_proposal())

    result = _stage(cli, stage_repo, "--job-item", str(number), "--confirm")

    assert result.exit_code == StageJobExit.RESULT, result.output
    lines = [line for line in result.stderr.splitlines() if line.startswith(LINE_PREFIX)]
    assert [line.removeprefix(LINE_PREFIX).split()[:4] for line in lines] == [
        ["job=stage", f"repo={STAGE_REPO}", f"item=#{number}", "result=staged"]
    ]


# ── The structure of the entry point ──────────────────────────────────────────


def test_the_entry_module_calls_the_plan_and_the_writer_of_the_service_and_pushes_nothing() -> None:
    """The Job plans with `plan_stage` and publishes with `StageWriter`, the code of the Service,
    and holds no push or rebase of its own: the shared push step changes `StageWriter` later."""
    tree = ast.parse(inspect.getsource(stage_job))
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    words = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }

    assert ({"plan_stage", "StageWriter"} <= called, words & {"push", "rebase"}) == (True, set())
