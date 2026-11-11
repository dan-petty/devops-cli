"""The verify screen, the decision point `stage.verify_screen` before the model review of a plan
(#4282, ADR 0019, ADR 0020): the digest that code builds, the band from fitted cuts, the modes of
the point, its records, and the fail-open rule."""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.config.constants import CONST_AI_JEV_MODEL
from devops_cli.config.settings import Settings
from devops_cli.roadmap.decision_point import (
    DecisionPoint,
    DecisionRecord,
    Mode,
    OutcomeRecord,
    ResolverChain,
    parse_record,
)
from devops_cli.roadmap.decision_registry import REGISTRY
from devops_cli.roadmap.decision_step import Band
from devops_cli.roadmap.stage.stage import StagePlan, parse_filters, plan_stage
from devops_cli.roadmap.stage.stage_jev_screen import (
    CUTS_FILE,
    QUESTIONS,
    VERIFY_SCREEN,
    ScreenCase,
    cuts,
    digest,
    request_of,
    screen_of,
)
from devops_cli.roadmap.stage.stage_toolbox import ToolboxModel
from devops_cli.roadmap.stage.stage_verify import Verification, VerificationInput
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
    from collections.abc import Callable, Mapping

    from tests.support.fakes.jev import JevFake
    from tests.support.fakes.openspec import OpenSpecFake
    from tests.support.fakes.otlp import FakeCollector

pytestmark = pytest.mark.usefixtures("keyring_store")

CHANGE = "1-the-job-drops-a-comment"
COUNTER = "devops_cli_decision_point_total"
BODY = "Part of a tracker.\n\n### Acceptance criteria\n\n- [ ] The job keeps the last comment.\n"
PLAN: dict[str, Any] = {
    "summary": "Keep the last comment",
    "feasibility": ["The job drops the comment in `src/job.py`."],
    "specs": [{"capability": "job", "added": [{"name": "keeps-comment"}], "modified": []}],
    "groups": [
        {
            "title": "Keep the comment",
            "kind": "behavior",
            "reads": ["src/gone.py"],
            "changes": ["src/job.py", "tests/test_job.py"],
            "creates": ["tests/new.py"],
            "test": "Write a test " + "x" * 400,
            "implementation": "Change the job. " + "y" * 400,
            "verify": "uv run devops ci test tests/test_job.py",
        },
        {
            "title": "Write the docs",
            "kind": "documentation",
            "reads": ["tests/new.py"],
            "changes": ["docs/job.md"],
            "verify": "uv run devops ci docs",
        },
    ],
}
KNOWN = {"src/job.py", "tests/test_job.py", "docs/job.md"}


def _given(plan: Mapping[str, Any] | None = None) -> VerificationInput:
    return VerificationInput.of(
        number=7,
        title="fix(roadmap): the job drops a comment",
        body=BODY,
        plan=PLAN if plan is None else plan,
        source=Path("/nonexistent"),
    )


@pytest.fixture
def point(tmp_path: Path) -> DecisionPoint[ScreenCase]:
    """The point of the screen with cuts of 0.3 and 0.8 for each question, so a test does not
    follow the fitted values of the repository."""
    path = tmp_path / "cuts.json"
    path.write_text(
        json.dumps(
            {
                "step": "stage.verify_screen",
                "model": CONST_AI_JEV_MODEL,
                "fitted": "2026-11-10",
                "cases": 2,
                "cuts": {name: {"continue_below": 0.3, "flag_at": 0.8} for name in QUESTIONS},
                "report": {},
            }
        ),
        encoding="utf-8",
    )
    return replace(VERIFY_SCREEN, cuts=path)


def _screen(
    point: DecisionPoint[ScreenCase], jev: JevFake, mode: Mode = Mode.ON
) -> ResolverChain[ScreenCase]:
    return ResolverChain(point, mode, model_name=CONST_AI_JEV_MODEL, model=jev.model)


def _records(caplog: pytest.LogCaptureFixture) -> list[DecisionRecord | OutcomeRecord]:
    found = [parse_record(record.getMessage()) for record in caplog.records]
    return [record for record in found if record is not None]


def test_the_digest_holds_the_facts_that_tools_found() -> None:
    first, second = digest(_given(), KNOWN)["groups"]

    assert first["paths_not_found_in_repo"] == ["src/gone.py"]
    assert first["verify_names_a_test_file_of_the_group"] is True
    assert second["paths_not_found_in_repo"] == []
    assert second["verify_names_a_test_file_of_the_group"] is False


def test_the_digest_cuts_each_piece_to_its_limit() -> None:
    first = digest(_given(), KNOWN)["groups"][0]

    assert len(first["test_task"]) <= 220
    assert len(first["work"]) <= 260
    assert digest(_given(), KNOWN)["acceptance_criteria"] == ["The job keeps the last comment."]


def test_a_plan_that_is_not_well_formed_gives_a_digest_and_never_fails() -> None:
    odd = {"groups": ["x", {"changes": [1, "a.py"], "creates": None}], "specs": "x"}

    assert len(digest(_given(odd), KNOWN)["groups"]) == 1


def test_the_request_has_the_same_nine_questions_for_two_plans() -> None:
    one = request_of(_given(), KNOWN)
    two = request_of(_given({"groups": []}), KNOWN)

    assert list(one.questions) == list(two.questions) == list(QUESTIONS)
    assert len(QUESTIONS) == 9


def test_the_cuts_are_data_with_the_model_and_the_cases_of_their_fit() -> None:
    fitted = cuts()

    assert CUTS_FILE.is_file()
    assert set(fitted.cuts) == set(QUESTIONS)
    assert (fitted.step, fitted.model) == ("stage.verify_screen", "typesafe/jev-1.14")
    assert fitted.cases > 0


def test_the_screen_is_the_registered_point_with_the_cuts_of_its_data_file() -> None:
    settings = Settings(
        ai={"decision_model": CONST_AI_JEV_MODEL},
        roadmap={"decisions": {"stage.verify_screen": "shadow"}},
    )

    screen = screen_of(settings)

    assert REGISTRY.point("stage.verify_screen") is VERIFY_SCREEN
    assert (VERIFY_SCREEN.cuts, VERIFY_SCREEN.cuts.is_file(), VERIFY_SCREEN.rule) == (
        CUTS_FILE,
        True,
        None,
    )
    assert screen is not None
    assert (screen.point, screen.mode) == (VERIFY_SCREEN, Mode.SHADOW)


@pytest.mark.parametrize(
    ("picks", "band"),
    [
        ({}, Band.CONTINUE),
        ({"false_premise": 0.3}, Band.REVIEW),
        ({"false_premise": 0.8}, Band.FLAG),
    ],
)
def test_the_questions_give_the_band(
    point: DecisionPoint[ScreenCase], jev: JevFake, picks: dict[str, float], band: Band
) -> None:
    jev.picks = dict(picks)

    decision = _screen(point, jev).decide(ScreenCase(_given(), KNOWN), subject=7)

    assert decision.band is band
    assert jev.asked == [list(QUESTIONS)]


def test_a_model_error_gives_no_band_and_is_logged(
    point: DecisionPoint[ScreenCase], jev: JevFake, caplog: pytest.LogCaptureFixture
) -> None:
    jev.fail(503)

    with caplog.at_level(logging.WARNING):
        decision = _screen(point, jev).decide(ScreenCase(_given(), KNOWN), subject=7)

    assert (decision.band, decision.acts) == (None, False)
    assert "current behavior runs" in caplog.text


def test_a_digest_with_a_secret_goes_to_no_request_and_the_review_runs(
    point: DecisionPoint[ScreenCase], jev: JevFake, caplog: pytest.LogCaptureFixture
) -> None:
    secret = {**PLAN, "summary": "Use ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"}

    with caplog.at_level(logging.WARNING):
        decision = _screen(point, jev).decide(ScreenCase(_given(secret), KNOWN), subject=7)

    assert (decision.band, jev.requests) == (None, [])
    assert "holds a secret" in caplog.text


def test_the_point_is_off_by_default_and_gives_no_screen() -> None:
    assert Settings().roadmap.decisions == {}
    assert screen_of(Settings()) is None


def test_with_no_decision_model_the_point_gives_no_screen_in_mode_on() -> None:
    settings = Settings(roadmap={"decisions": {"stage.verify_screen": "on"}})

    assert screen_of(settings) is None


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    seed_stageable(store)
    return store


@pytest.fixture(autouse=True)
def openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    openspec_fake.script_sequence(
        validate_args(CHANGE), (0, VALID_REPORT), (0, VALID_REPORT), (0, VALID_REPORT)
    )
    return openspec_fake


def _plan(
    store: InMemoryRoadmapStore,
    repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    screen: ResolverChain[ScreenCase] | None,
) -> StagePlan:
    model_fake.answer(make_stage_proposal())
    return plan_stage(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        filters=parse_filters(()),
        verifier=ToolboxModel(verifier),
        screen=screen,
    )


def test_the_band_continue_skips_the_reviewer_in_mode_on(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    jev: JevFake,
    point: DecisionPoint[ScreenCase],
) -> None:
    verifier = ModelFake()

    plan = _plan(store, stage_repo, model_fake, verifier, _screen(point, jev))

    assert (verifier.call_count, len(jev.requests), len(plan.ready)) == (0, 1, 1)
    assert plan.ready[0].findings == ()


@pytest.mark.parametrize("pick", [0.3, 0.8])
def test_the_bands_review_and_flag_run_the_reviewer(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    jev: JevFake,
    point: DecisionPoint[ScreenCase],
    pick: float,
) -> None:
    jev.picks = {"false_premise": pick}
    verifier = ModelFake()
    verifier.answer(Verification(findings=[]))

    plan = _plan(store, stage_repo, model_fake, verifier, _screen(point, jev))

    assert (verifier.call_count, len(plan.ready)) == (1, 1)


def test_shadow_runs_the_reviewer_and_records_the_band_beside_its_result(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    jev: JevFake,
    point: DecisionPoint[ScreenCase],
    otlp: FakeCollector,
    caplog: pytest.LogCaptureFixture,
) -> None:
    verifier = ModelFake()
    verifier.answer(Verification(findings=[]))

    with caplog.at_level(logging.INFO):
        plan = _plan(store, stage_repo, model_fake, verifier, _screen(point, jev, Mode.SHADOW))

    assert (verifier.call_count, len(jev.requests), len(plan.ready)) == (1, 1, 1)
    assert otlp.points(COUNTER) == [
        (
            {
                "point": "stage.verify_screen",
                "resolver": "model",
                "band": "continue",
                "mode": "shadow",
            },
            1,
        )
    ]
    decision, outcome = _records(caplog)
    assert isinstance(decision, DecisionRecord)
    assert (decision.subject, decision.band, decision.digest) == ("1", Band.CONTINUE, None)
    assert outcome == OutcomeRecord(
        id=decision.id, point="stage.verify_screen", must_run=False, weight=0, result="clean"
    )


def test_a_model_error_runs_the_reviewer_in_mode_on_and_counts_the_fallback(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    jev: JevFake,
    point: DecisionPoint[ScreenCase],
    otlp: FakeCollector,
) -> None:
    jev.fail(503)
    verifier = ModelFake()
    verifier.answer(Verification(findings=[]))

    plan = _plan(store, stage_repo, model_fake, verifier, _screen(point, jev))

    assert (verifier.call_count, len(plan.ready)) == (1, 1)
    assert otlp.points(COUNTER) == [
        ({"point": "stage.verify_screen", "resolver": "fallback", "band": "none", "mode": "on"}, 1)
    ]


def test_with_no_decision_model_the_stage_job_reviews_as_before_and_counts_nothing(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    jev: JevFake,
    config: Callable[..., Path],
    otlp: FakeCollector,
) -> None:
    config(roadmap={"decisions": {"stage.verify_screen": "on"}})
    verifier = ModelFake()
    verifier.answer(Verification(findings=[]))

    plan = _plan(store, stage_repo, model_fake, verifier, None)

    assert (verifier.call_count, len(jev.requests), len(plan.ready)) == (1, 0, 1)
    assert otlp.points(COUNTER) == []
