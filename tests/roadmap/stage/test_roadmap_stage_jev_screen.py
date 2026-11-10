"""The Jev screen before the model review of a plan (#4282, ADR 0019): the digest that code
builds, the band from fitted cuts, the three modes of the setting, and the fail-open rule."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.config.settings import Settings
from devops_cli.roadmap.decision_step import Band, Cut, Thresholds
from devops_cli.roadmap.stage.stage import StagePlan, parse_filters, plan_stage
from devops_cli.roadmap.stage.stage_jev_screen import (
    CUTS_FILE,
    QUESTIONS,
    JevScreener,
    ScreenMode,
    cuts,
    digest,
    request_of,
    screener_of,
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
    from collections.abc import Mapping

    from devops_cli.config.defaults import JevMode
    from tests.support.fakes.jev import JevFake
    from tests.support.fakes.openspec import OpenSpecFake
    from tests.support.fakes.otlp import FakeCollector

pytestmark = pytest.mark.usefixtures("keyring_store")

CHANGE = "1-the-job-drops-a-comment"
FITTED = Thresholds(
    step="verify_screen",
    model="typesafe/jev-1.14",
    fitted="2026-11-10",
    cases=2,
    cuts={name: Cut(continue_below=0.3, flag_at=0.8) for name in QUESTIONS},
    report={},
)
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


def _screener(jev: JevFake, mode: ScreenMode = ScreenMode.ON) -> JevScreener:
    return JevScreener(mode, fitted=FITTED, model=jev.model)


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
    assert fitted.model == "typesafe/jev-1.14"
    assert fitted.cases > 0


@pytest.mark.parametrize(
    ("picks", "band"),
    [
        ({}, Band.CONTINUE),
        ({"false_premise": 0.3}, Band.REVIEW),
        ({"false_premise": 0.8}, Band.FLAG),
    ],
)
def test_the_questions_give_the_band(jev: JevFake, picks: dict[str, float], band: Band) -> None:
    jev.picks = dict(picks)

    result = _screener(jev).screen(_given(), KNOWN)

    assert result is not None
    assert result.band is band
    assert jev.asked == [list(QUESTIONS)]


def test_a_jev_error_gives_no_result_and_is_logged(
    jev: JevFake, caplog: pytest.LogCaptureFixture
) -> None:
    jev.fail(503)

    with caplog.at_level(logging.WARNING):
        result = _screener(jev).screen(_given(), KNOWN)

    assert result is None
    assert "existing path runs" in caplog.text


def test_a_digest_with_a_secret_goes_to_no_request_and_the_review_runs(
    jev: JevFake, caplog: pytest.LogCaptureFixture
) -> None:
    secret = {**PLAN, "summary": "Use ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"}

    with caplog.at_level(logging.WARNING):
        result = _screener(jev).screen(_given(secret), KNOWN)

    assert (result, jev.requests) == (None, [])
    assert "holds a secret" in caplog.text


def test_the_setting_is_off_by_default_and_builds_no_screener() -> None:
    assert Settings().roadmap.stage.jev_screen == "off"
    assert screener_of(Settings()) is None


@pytest.mark.parametrize("mode", ["shadow", "on"])
def test_the_setting_shadow_or_on_builds_a_screener(mode: JevMode) -> None:
    settings = Settings()
    settings.roadmap.stage.jev_screen = mode

    screener = screener_of(settings)

    assert isinstance(screener, JevScreener)
    assert screener.skips is (mode == "on")


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
    screener: JevScreener | None,
) -> StagePlan:
    model_fake.answer(make_stage_proposal())
    return plan_stage(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        filters=parse_filters(()),
        verifier=ToolboxModel(verifier),
        screener=screener,
    )


def test_the_band_continue_skips_the_reviewer_in_mode_on(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, jev: JevFake
) -> None:
    verifier = ModelFake()

    plan = _plan(store, stage_repo, model_fake, verifier, _screener(jev))

    assert (verifier.call_count, len(jev.requests), len(plan.ready)) == (0, 1, 1)
    assert plan.ready[0].findings == ()


@pytest.mark.parametrize("pick", [0.3, 0.8])
def test_the_bands_review_and_flag_run_the_reviewer(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    jev: JevFake,
    pick: float,
) -> None:
    jev.picks = {"false_premise": pick}
    verifier = ModelFake()
    verifier.answer(Verification(findings=[]))

    plan = _plan(store, stage_repo, model_fake, verifier, _screener(jev))

    assert (verifier.call_count, len(plan.ready)) == (1, 1)


def test_shadow_mode_runs_the_reviewer_and_counts_the_band_beside_its_result(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    jev: JevFake,
    otlp: FakeCollector,
) -> None:
    verifier = ModelFake()
    verifier.answer(Verification(findings=[]))

    plan = _plan(store, stage_repo, model_fake, verifier, _screener(jev, ScreenMode.SHADOW))

    assert (verifier.call_count, len(jev.requests), len(plan.ready)) == (1, 1, 1)
    (decision,) = otlp.points("devops_cli_roadmap_decision_step_total")
    (outcome,) = otlp.points("devops_cli_roadmap_decision_step_review_total")
    assert decision[0] == {"step": "verify_screen", "mode": "shadow", "band": "continue"}
    assert outcome[0] == {"step": "verify_screen", "band": "continue", "reviewer": "clean"}


def test_a_jev_error_runs_the_reviewer_in_mode_on(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, jev: JevFake
) -> None:
    jev.fail(503)
    verifier = ModelFake()
    verifier.answer(Verification(findings=[]))

    plan = _plan(store, stage_repo, model_fake, verifier, _screener(jev))

    assert (verifier.call_count, len(plan.ready)) == (1, 1)


def test_no_screener_runs_the_reviewer_and_makes_no_jev_request(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    jev: JevFake,
) -> None:
    verifier = ModelFake()
    verifier.answer(Verification(findings=[]))

    plan = _plan(store, stage_repo, model_fake, verifier, None)

    assert (verifier.call_count, len(jev.requests), len(plan.ready)) == (1, 0, 1)
