"""`devops roadmap stage`: a revision of a repair round that the checks refuse goes back to the
planner with its problem, as a refused first reply does, and a revision that stays refused is kept
in the refused-reply file and ends the item with its problem (#4348, #4312)."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, cast

import pytest

from devops_cli.config.constants import CONST_ROADMAP_STAGE_GATE_RETURNS
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


def test_a_revision_that_the_gates_refuse_twice_ends_the_item_with_the_problem_and_no_third_call(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    model_fake.answer(make_stage_proposal(), _refused(), _refused())
    verifier.answer(_returns_plan(), Verification())

    plan = _plan(store, stage_repo, model_fake, verifier)

    (failure,) = plan.failed
    assert (plan.ready, model_fake.call_count, verifier.call_count) == ((), 3, 1)
    assert failure.error == "RoadmapStageError"
    assert "revision" in failure.reason
    assert MISSING in failure.reason


def test_the_returns_of_one_round_are_the_constant_and_no_more(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    model_fake.answer(make_stage_proposal(), _refused())
    verifier.answer(_returns_plan(), Verification())

    _plan(store, stage_repo, model_fake, verifier)

    # The first ask, then the revision and its returns.
    assert model_fake.call_count == 1 + 1 + CONST_ROADMAP_STAGE_GATE_RETURNS


def test_a_revision_that_stays_refused_is_kept_with_its_problem_beside_the_earlier_replies(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    first = _refused("First reply")
    revision = _refused("The revision")
    returned = _refused("The returned revision")
    model_fake.answer(first, make_stage_proposal(), revision, returned)
    verifier.answer(_returns_plan(), Verification())

    plan = _plan(store, stage_repo, model_fake, verifier)

    record = _refused_record()
    assert (len(plan.failed), model_fake.call_count) == (1, 4)
    assert [entry.reply for entry in record.replies] == [
        first.model_dump(),
        revision.model_dump(),
        returned.model_dump(),
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
    model_fake.answer(make_stage_proposal(), _refused(), _refused())
    verifier.answer(_returns_plan(), Verification())

    with caplog.at_level(logging.WARNING):
        _plan(store, stage_repo, model_fake, verifier)

    lines = [r.getMessage() for r in caplog.records if "stage reply refused" in r.getMessage()]
    assert [line.rsplit(" ", 1)[1] for line in lines] == ["result=refused", "result=refused"]
