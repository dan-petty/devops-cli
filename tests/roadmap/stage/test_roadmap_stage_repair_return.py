"""`devops roadmap stage`: a revision of a repair round that the checks refuse goes back to the
planner with its problem, as a refused first reply does, and a revision that stays refused is kept
in the refused-reply file and ends the item with its problem (#4348, #4312)."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, cast

import pytest
from pydantic import ValidationError

from devops_cli.config.settings import RoadmapStageConfig
from devops_cli.exceptions import ServiceStoppingError, ended_by_stop
from devops_cli.roadmap.service_stop import begin_service_stop
from devops_cli.roadmap.stage.stage import StagePlan, parse_filters, plan_stage
from devops_cli.roadmap.stage.stage_eval_cases import DefectType
from devops_cli.roadmap.stage.stage_plan_record import RefusedRecord, refused_record_path
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
MISSING = "tests/test_missing.py"


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


def _refused(summary: str = "A plan that names a missing file") -> Any:
    """A reply that the `paths` gate refuses on each try."""
    group = make_stage_proposal().groups[0]
    return make_stage_proposal(
        summary=summary,
        groups=[group.model_copy(update={"changes": [*group.changes, MISSING]})],
    )


def _returns_plan() -> Verification:
    """A review that returns the plan to the planner."""
    return Verification(
        findings=[
            Finding(
                type=DefectType.FALSE_PREMISE,
                where="group 1",
                problem="The premise is wrong.",
                quote=ISSUE_QUOTE,
            )
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


def _refused_record() -> RefusedRecord:
    path = refused_record_path(STAGE_REPO, 1)
    return RefusedRecord.model_validate_json(path.read_text(encoding="utf-8"))


def test_a_revision_that_the_gates_refuse_once_goes_back_and_the_second_revision_passes(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    refused = _refused()
    model_fake.answer(make_stage_proposal(), refused, make_stage_proposal(summary="Repaired"))
    verifier.answer(_returns_plan(), Verification())

    plan = _plan(store, stage_repo, model_fake, verifier)

    (change,) = plan.ready
    asked = [json.loads(call.prompt) for call in model_fake.calls]
    assert (change.proposal.summary, model_fake.call_count, verifier.call_count) == (
        "Repaired",
        3,
        2,
    )
    assert (asked[2]["previous"], MISSING in asked[2]["problem"]) == (refused.model_dump(), True)
    assert "previous" in asked[1]
    assert asked[1]["previous"] != asked[2]["previous"]


def test_a_revision_that_the_gates_accept_gets_no_return(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    model_fake.answer(make_stage_proposal(), make_stage_proposal(summary="Repaired"))
    verifier.answer(_returns_plan(), Verification())

    plan = _plan(store, stage_repo, model_fake, verifier)

    assert (len(plan.ready), model_fake.call_count) == (1, 2)


def test_a_revision_that_the_gates_refuse_after_each_return_ends_the_item_with_the_problem(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    model_fake.answer(make_stage_proposal(), _refused())
    verifier.answer(_returns_plan(), Verification())

    plan = _plan(store, stage_repo, model_fake, verifier)

    (failure,) = plan.failed
    # The first ask, the revision and its three returns, and no further request.
    assert (plan.ready, model_fake.call_count, verifier.call_count) == ((), 5, 1)
    assert failure.error == "RoadmapStageError"
    assert "revision" in failure.reason
    assert MISSING in failure.reason


def test_a_refused_revision_gets_three_returns_by_default(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    """The default of `roadmap.stage.gate_returns` is 3: in 8 of 10 sampled refused items the
    returned reply had fewer problems, so one return stopped a run that made progress (#4802)."""
    model_fake.answer(make_stage_proposal(), _refused())
    verifier.answer(_returns_plan(), Verification())

    _plan(store, stage_repo, model_fake, verifier)

    # The first ask, then the revision and its returns.
    assert (RoadmapStageConfig().gate_returns, model_fake.call_count) == (3, 1 + 1 + 3)


def test_the_returns_of_one_round_follow_the_setting_and_no_more(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    config: Callable[..., Path],
) -> None:
    """`roadmap.stage.gate_returns` sets the returns of a refused reply, so the owner can tune
    them in the ConfigMap (#4802)."""
    config(roadmap={"stage": {"gate_returns": 2}})
    model_fake.answer(make_stage_proposal(), _refused())
    verifier.answer(_returns_plan(), Verification())

    _plan(store, stage_repo, model_fake, verifier)

    assert model_fake.call_count == 1 + 1 + 2


def test_a_gate_returns_value_over_the_ceiling_fails_the_settings_load() -> None:
    """`roadmap.stage.gate_returns` has a hard ceiling of 3: each return is one more planner run,
    so a ConfigMap value cannot give an item more planner calls than the measured cap (#4900)."""
    assert RoadmapStageConfig(gate_returns=3).gate_returns == 3
    with pytest.raises(ValidationError, match="gate_returns"):
        RoadmapStageConfig(gate_returns=4)


def test_a_refused_reply_gets_no_return_once_the_service_stops(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    """A return is a new planner run that sends model requests, and the cut at the end of the
    drain stops only GitHub requests. Once the Service stops, no return starts: the round ends
    with the stop and records no failed item (#4900)."""

    def refused_in_the_drain(prompt: str) -> Any:
        begin_service_stop()
        return _refused()

    model_fake.answer(refused_in_the_drain)

    with pytest.raises(ServiceStoppingError) as stopped:
        _plan(store, stage_repo, model_fake, verifier)

    assert (ended_by_stop(stopped.value), model_fake.call_count) == (True, 1)
    assert refused_record_path(STAGE_REPO, 1).exists() is False


def test_a_revision_that_stays_refused_is_kept_with_its_problem_beside_the_earlier_replies(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    first = _refused("First reply")
    revision = _refused("The revision")
    returned = [_refused(f"Returned revision {n}") for n in range(1, 4)]
    model_fake.answer(first, make_stage_proposal(), revision, *returned)
    verifier.answer(_returns_plan(), Verification())

    plan = _plan(store, stage_repo, model_fake, verifier)

    record = _refused_record()
    assert (len(plan.failed), model_fake.call_count) == (1, 6)
    assert [entry.reply for entry in record.replies] == [
        first.model_dump(),
        revision.model_dump(),
        *(reply.model_dump() for reply in returned),
    ]
    assert all(MISSING in entry.problem for entry in record.replies)


def test_a_revision_that_the_gates_accept_after_a_return_leaves_the_kept_replies_of_the_item(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    model_fake.answer(make_stage_proposal(), _refused(), make_stage_proposal(summary="Repaired"))
    verifier.answer(_returns_plan(), Verification())

    plan = _plan(store, stage_repo, model_fake, verifier)

    assert (len(plan.ready), refused_record_path(STAGE_REPO, 1).exists()) == (1, False)


def test_each_refused_revision_logs_one_line(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    model_fake.answer(make_stage_proposal(), _refused())
    verifier.answer(_returns_plan(), Verification())

    with caplog.at_level(logging.WARNING):
        _plan(store, stage_repo, model_fake, verifier)

    lines = [r.getMessage() for r in caplog.records if "stage reply refused" in r.getMessage()]
    assert [line.rsplit(" ", 1)[1] for line in lines] == ["result=refused"] * (1 + 3)


def _counts(caplog: pytest.LogCaptureFixture, event: str) -> list[str]:
    """The fields of each log line of `event`, with the version cut off (#4535)."""
    return [
        r.getMessage().removeprefix(f"{event}: ").rsplit(" version=", 1)[0]
        for r in caplog.records
        if r.getMessage().startswith(f"{event}: ")
    ]


def test_a_review_round_and_a_pass_after_a_return_each_log_one_line_with_counts(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    model_fake.answer(make_stage_proposal(), _refused(), make_stage_proposal(summary="Repaired"))
    verifier.answer(_returns_plan(), Verification())

    with caplog.at_level(logging.INFO):
        _plan(store, stage_repo, model_fake, verifier)

    assert _counts(caplog, "stage review round") == [
        f"repo={STAGE_REPO} item=#1 round=0 findings=1 returned=1 open=1",
        f"repo={STAGE_REPO} item=#1 round=1 findings=0 returned=0 open=0",
    ]
    assert _counts(caplog, "stage gate returns") == [
        f"repo={STAGE_REPO} item=#1 returns=1 result=passed"
    ]


def test_a_revision_that_stays_refused_logs_its_returns_as_refused(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    model_fake.answer(make_stage_proposal(), _refused(), _refused())
    verifier.answer(_returns_plan(), Verification())

    with caplog.at_level(logging.INFO):
        _plan(store, stage_repo, model_fake, verifier)

    assert _counts(caplog, "stage gate returns") == [
        f"repo={STAGE_REPO} item=#1 returns={RoadmapStageConfig().gate_returns} result=refused"
    ]
