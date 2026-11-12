"""`devops roadmap stage`: the repair rounds of the model review are the setting
`roadmap.stage.verify_repair_rounds`, and one more round follows while the count of open findings
drops, up to a hard ceiling and never in a drain of the Service (#5066)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

import pytest
from pydantic import ValidationError

from devops_cli.config.constants import CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS_CEILING
from devops_cli.config.settings import RoadmapStageConfig
from devops_cli.exceptions import ServiceStoppingError, ended_by_stop
from devops_cli.roadmap.service_stop import begin_service_stop
from devops_cli.roadmap.stage.stage import StagePlan, parse_filters, plan_stage
from devops_cli.roadmap.stage.stage_eval_cases import DefectType
from devops_cli.roadmap.stage.stage_toolbox import ToolboxModel
from devops_cli.roadmap.stage.stage_verify import Finding, Verification
from tests.support.builders import make_stage_proposal
from tests.support.fakes.model import ModelFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    seed_stageable,
    validate_args,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from devops_cli.roadmap.stage.stage import StageClient
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

ISSUE_QUOTE = "The job drops the last comment of a thread."


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    seed_stageable(store)
    return store


@pytest.fixture(autouse=True)
def valid_openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    openspec_fake.script_sequence(
        validate_args("1-the-job-drops-a-comment"), *[(0, VALID_REPORT)] * 8
    )
    return openspec_fake


@pytest.fixture
def verifier() -> ModelFake:
    """The model edge of the review, apart from the model edge of the planner."""
    return ModelFake()


def _review(count: int) -> Verification:
    """A review with `count` open findings that return the plan to the planner."""
    return Verification(
        findings=[
            Finding(
                type=DefectType.FALSE_PREMISE,
                where=f"group {number}",
                problem=f"The premise of group {number} is wrong.",
                quote=ISSUE_QUOTE,
            )
            for number in range(1, count + 1)
        ]
    )


def _plan(
    store: InMemoryRoadmapStore, repo: StageRepo, model: ModelFake, verifier: ModelFake
) -> StagePlan:
    return plan_stage(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        filters=parse_filters(()),
        model=cast("StageClient", model),
        verifier=ToolboxModel(verifier),
    )


def _lines(caplog: pytest.LogCaptureFixture, event: str) -> list[str]:
    """The fields of each `event` line, with no version."""
    return [
        r.getMessage().removeprefix(f"{event}: ").rsplit(" version=", 1)[0]
        for r in caplog.records
        if r.getMessage().startswith(f"{event}: ")
    ]


def test_the_setting_sets_the_repair_rounds_of_the_review(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    config: Callable[..., Path],
) -> None:
    config(roadmap={"stage": {"verify_repair_rounds": 1}})
    model_fake.answer(make_stage_proposal())
    verifier.answer(_review(1))

    (change,) = _plan(store, stage_repo, model_fake, verifier).ready

    assert (RoadmapStageConfig().verify_repair_rounds, model_fake.call_count) == (2, 1 + 1)
    assert (verifier.call_count, len(change.open_findings)) == (2, 1)


def test_a_repair_rounds_value_over_the_ceiling_fails_the_settings_load() -> None:
    ceiling = CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS_CEILING
    assert RoadmapStageConfig(verify_repair_rounds=ceiling).verify_repair_rounds == ceiling
    with pytest.raises(ValidationError, match="verify_repair_rounds"):
        RoadmapStageConfig(verify_repair_rounds=ceiling + 1)


def test_a_review_whose_open_count_drops_after_the_last_round_gets_one_more_round(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    model_fake.answer(make_stage_proposal())
    verifier.answer(_review(3), _review(3), _review(2), Verification())

    with caplog.at_level(logging.INFO):
        plan = _plan(store, stage_repo, model_fake, verifier)

    (change,) = plan.ready
    (attempt,) = plan.attempts
    assert (model_fake.call_count, verifier.call_count, change.open_findings) == (4, 4, ())
    # The result line counts each review run, the extended round too. A planner with no trace
    # counts no plan run.
    assert attempt.verify_rounds == 4
    assert _lines(caplog, "stage review extended") == [
        f"repo={STAGE_REPO} item=#1 round=3 before=3 open=2"
    ]
    assert len(_lines(caplog, "stage review round")) == 4


def test_a_review_whose_open_count_stays_gets_no_round_after_the_setting(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    model_fake.answer(make_stage_proposal())
    verifier.answer(_review(3), _review(2), _review(2))

    with caplog.at_level(logging.INFO):
        (change,) = _plan(store, stage_repo, model_fake, verifier).ready

    assert (model_fake.call_count, verifier.call_count, len(change.open_findings)) == (3, 3, 2)
    assert _lines(caplog, "stage review extended") == []


def test_no_item_gets_more_repair_rounds_than_the_ceiling(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    ceiling = CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS_CEILING
    model_fake.answer(make_stage_proposal())
    verifier.answer(*(_review(count) for count in range(ceiling + 3, 0, -1)))

    (change,) = _plan(store, stage_repo, model_fake, verifier).ready

    assert (model_fake.call_count, verifier.call_count) == (1 + ceiling, 1 + ceiling)
    assert len(change.open_findings) == 3


def test_no_repair_round_starts_once_the_service_stops(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    """A repair round is a new planner run that sends model requests. Once the Service stops, no
    round starts: the round ends with the stop and records no failed item (#4925)."""

    def review_in_the_drain(prompt: str) -> Any:
        begin_service_stop()
        return _review(1)

    model_fake.answer(make_stage_proposal())
    verifier.answer(review_in_the_drain)

    with pytest.raises(ServiceStoppingError) as stopped:
        _plan(store, stage_repo, model_fake, verifier)

    assert (ended_by_stop(stopped.value), model_fake.call_count) == (True, 1)
