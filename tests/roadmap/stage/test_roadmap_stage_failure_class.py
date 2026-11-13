"""`devops roadmap stage`: the failure class and the step of a failed item (#4056).

The job records, with `stage.failed_at` and `stage.failed_error`, the class of the failure
(`stage.failed_class`) and the step that failed (`stage.failed_step`). The class comes from the type
of the exception, by the one table of `roadmap/failure.py`. A staged item and an item stopped on
the budget clear all four keys.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.ai.client.models import AIClientError, StructuredOutputValidationError
from devops_cli.exceptions import GitHubOperationError
from devops_cli.exceptions.roadmap import RoadmapItemChangedError
from devops_cli.roadmap import failure as failure_module
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.stage.stage import (
    StageApplied,
    StageFailure,
    StagePlan,
    parse_filters,
    plan_stage,
)
from devops_cli.roadmap.stage.stage_change import StageSplit
from devops_cli.roadmap.stores.store import StageRecordKey
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    apply_stage,
    heavy_group,
    no_findings,
    seed_stageable,
    stage_round,
    validate_args,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
PULLS = f"/repos/{STAGE_REPO}/pulls"
TITLES = ("fix(roadmap): the job drops a comment", "fix(roadmap): the job drops a label")
BRANCHES = ("1-the-job-drops-a-comment", "2-the-job-drops-a-label")


def _failure_keys() -> tuple[StageRecordKey, ...]:
    """The four keys of a failure. Two of them are new, so a test reads them when it runs."""
    return (
        StageRecordKey.FAILED_AT,
        StageRecordKey.FAILED_ERROR,
        StageRecordKey.FAILED_STEP,
        StageRecordKey.FAILED_CLASS,
    )


class _WriteRefused(InMemoryRoadmapStore):
    """A store whose comment on issue `refused` fails with `error`, as a write fails on GitHub."""

    refused = 0
    error: Exception = GitHubOperationError("comment refused", operation="roadmap.issue.comment")

    def comment(self, number: int, body: str) -> None:
        if number == self.refused:
            raise self.error
        super().comment(number, body)


class _Counting(InMemoryRoadmapStore):
    """A store that keeps the marks of each `set_marks` call."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.mark_calls: list[dict[str, str | None]] = []

    def set_marks(self, item: Any, marks: Mapping[Any, str | None], **kwargs: Any) -> None:
        self.mark_calls.append({key.value: value for key, value in marks.items()})
        super().set_marks(item, marks, **kwargs)


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


def _record(store: InMemoryRoadmapStore, number: int) -> dict[str, str]:
    item = store.item(number)
    assert item is not None
    return {key.value: value for key, value in item.job_record.items() if value is not None}


def _failure_of(store: InMemoryRoadmapStore, number: int) -> tuple[str | None, ...]:
    """The error, the class and the step that the record of item `number` holds."""
    record = _record(store, number)
    return tuple(
        record.get(key.value)
        for key in (
            StageRecordKey.FAILED_ERROR,
            StageRecordKey.FAILED_CLASS,
            StageRecordKey.FAILED_STEP,
        )
    )


def _round(store: InMemoryRoadmapStore, repo: StageRepo) -> Any:
    return stage_round(store, repo)


def _plan_answers(model_fake: ModelFake, failing: Exception | None = None, **proposal: Any) -> None:
    """Answer the planner: item 1 gets `failing` or a proposal with the `proposal` fields, and
    item 2 gets a good plan, so that the round stages one item and does not fail as a whole."""

    def plan(prompt: str) -> Any:
        request = json.loads(prompt)
        if "plan" in request or request["number"] != 1:
            return make_stage_proposal()
        if failing is not None:
            raise failing
        return make_stage_proposal(**proposal)

    no_findings(model_fake)
    model_fake.answer(plan)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (AIClientError("the provider is down"), ("AIClientError", "provider")),
        (
            StructuredOutputValidationError("no answer fits the schema", violations=2),
            ("StructuredOutputValidationError", "parser"),
        ),
    ],
    ids=("provider", "parser"),
)
def test_a_model_error_in_the_plan_records_its_class_and_the_step_plan(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
    error: Exception,
    expected: tuple[str, str],
) -> None:
    store = _two_items(InMemoryRoadmapStore(repo=STAGE_REPO), openspec_fake, github_api)
    _plan_answers(model_fake, error)

    _round(store, stage_repo)

    assert _failure_of(store, 1) == (*expected, failure_module.StepName.PLAN.value)
    assert _failure_of(store, 2) == (None, None, None)


def test_a_plan_that_breaks_a_rule_of_the_job_records_the_class_plan_defect(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
) -> None:
    store = _two_items(InMemoryRoadmapStore(repo=STAGE_REPO), openspec_fake, github_api)
    _plan_answers(model_fake, pull_request_body="Fixes #4 now.")

    _round(store, stage_repo)

    assert _failure_of(store, 1) == (
        "RoadmapStageError",
        FailureClass.PLAN_DEFECT.value,
        failure_module.StepName.PLAN.value,
    )


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            GitHubOperationError("comment refused", operation="roadmap.issue.comment"),
            ("GitHubOperationError", FailureClass.CI_INFRA.value),
        ),
        (
            RoadmapItemChangedError("the item changed"),
            ("RoadmapItemChangedError", FailureClass.HEAD_MOVED.value),
        ),
    ],
    ids=("github", "item-changed"),
)
def test_a_write_that_fails_records_its_class_and_the_step_apply(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
    error: Exception,
    expected: tuple[str, str],
) -> None:
    store = _WriteRefused(repo=STAGE_REPO)
    store.refused = 2
    store.error = error
    _two_items(store, openspec_fake, github_api)
    _plan_answers(model_fake)

    _round(store, stage_repo)

    assert _failure_of(store, 2) == (*expected, failure_module.StepName.APPLY.value)
    assert _failure_of(store, 1) == (None, None, None)


def _seed_failure(store: InMemoryRoadmapStore, number: int) -> None:
    item = store.item(number)
    assert item is not None
    store.set_marks(
        item,
        {
            StageRecordKey.FAILED_AT: NOW.isoformat(),
            StageRecordKey.FAILED_ERROR: "AIClientError",
            StageRecordKey.FAILED_STEP: failure_module.StepName.PLAN.value,
            StageRecordKey.FAILED_CLASS: FailureClass.PROVIDER.value,
        },
    )


def test_a_staged_item_clears_the_four_keys_of_its_failure(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
) -> None:
    store = _two_items(InMemoryRoadmapStore(repo=STAGE_REPO), openspec_fake, github_api)
    _seed_failure(store, 1)
    _plan_answers(model_fake)

    _round(store, stage_repo)

    assert StageRecordKey.BRANCH.value in _record(store, 1)
    assert [key.value in _record(store, 1) for key in _failure_keys()] == [False] * 4


def test_an_item_stopped_on_the_budget_clears_the_four_keys_of_its_failure(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = seed_stageable(store)
    _seed_failure(store, number)
    heavy = heavy_group(stage_repo)
    stuck = make_stage_proposal(groups=[heavy])
    model_fake.answer(stuck, StageSplit(groups=[heavy]))
    plan = plan_stage(
        store,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        filters=parse_filters(()),
        step_tokens=6000,
    )

    applied = apply_stage(store, plan, source=stage_repo.clone)

    assert applied.stopped == (number,)
    assert StageRecordKey.NEEDS_SPLIT.value in _record(store, number)
    assert [key.value in _record(store, number) for key in _failure_keys()] == [False] * 4


def test_a_failure_writes_the_four_keys_with_one_write_of_marks() -> None:
    store = _Counting(repo=STAGE_REPO)
    number = seed_stageable(store)
    item = store.item(number)
    assert item is not None
    plan = StagePlan(
        STAGE_REPO,
        failed=(
            StageFailure(
                number,
                item.title,
                "AIClientError",
                "",
                item,
                failure_class=FailureClass.PROVIDER,
                step=failure_module.StepName.PLAN,
            ),
        ),
    )
    store.mark_calls.clear()

    applied = apply_stage(store, plan, source=".", now=NOW)

    assert applied == StageApplied()
    assert store.mark_calls == [
        {
            StageRecordKey.FAILED_AT.value: NOW.isoformat(),
            StageRecordKey.FAILED_ERROR.value: "AIClientError",
            StageRecordKey.FAILED_STEP.value: "plan",
            StageRecordKey.FAILED_CLASS.value: "provider",
        }
    ]
