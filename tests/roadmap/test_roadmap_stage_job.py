"""The `stage` row of the Service's model lane: a round plans with the settings, writes, counts
each item once by its result, and fails for the items that failed (#2659)."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from devops_cli.exceptions import GitOperationError, RoadmapStageError
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.run import MODEL_LANE_ROWS, JobOutcome
from devops_cli.roadmap.stage_change import StageSplit
from devops_cli.roadmap.store import ItemField
from devops_cli.telemetry.instruments import ROADMAP_STAGE_TOTAL
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json
from tests.support.roadmap_implement import merge_plan
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    heavy_group,
    seed_stageable,
    validate_args,
)

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake
    from tests.support.fakes.otlp import FakeCollector

pytestmark = pytest.mark.usefixtures("keyring_store")

STAGE_ROW = next(row for row in MODEL_LANE_ROWS if row.name == "stage")
OPENED = github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201)


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture(autouse=True)
def valid_openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    for name in ("1-the-job-drops-a-comment", "2-the-job-drops-a-label", "3-the-job-drops-a-tag"):
        openspec_fake.script_sequence(validate_args(name), (0, VALID_REPORT))
    return openspec_fake


def _round(store: InMemoryRoadmapStore, repo: StageRepo) -> JobOutcome:
    """One round of the row, as the Service runs it in its model clone."""
    return STAGE_ROW.runner(store=store, repo=STAGE_REPO, clone_path=repo.clone)


def _counted(otlp: FakeCollector) -> list[tuple[str, float]]:
    """Each point of the stage counter as (result, value), by result."""
    return sorted(
        (attrs["result"], value) for attrs, value in otlp.points(ROADMAP_STAGE_TOTAL.name)
    )


def _pushed(repo: StageRepo) -> list[str]:
    return repo.origin_git("branch", "--format=%(refname:short)").split()


def test_the_row_follows_refine_runs_on_a_clone_and_is_due_every_37_minutes_and_on_a_first_run() -> (
    None
):
    names = [row.name for row in MODEL_LANE_ROWS]
    assert (
        names[names.index("refine") + 1],
        STAGE_ROW.needs_clone,
        STAGE_ROW.first_run_due,
        STAGE_ROW.interval,
        STAGE_ROW.cross_job_predicate is not None,
    ) == ("stage", True, True, timedelta(minutes=37), True)


def test_the_cross_job_rule_follows_the_set_ready_of_refine() -> None:
    rule = STAGE_ROW.cross_job_predicate
    assert rule is not None
    assert (
        rule({"refine": JobOutcome(set_ready=True)}),
        rule({"refine": JobOutcome()}),
        rule({"intake": JobOutcome(placed_critical_or_p0=True)}),
        rule({}),
    ) == (True, False, False, False)


def test_a_round_stages_the_items_the_settings_name_and_counts_each_once(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    otlp: FakeCollector,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    github_api.route("POST", f"/repos/{STAGE_REPO}/pulls", OPENED)
    seed_stageable(store)
    store.seed_issue(
        "feat(roadmap): the job drops a label",
        labels=("type/feature",),
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_FILTER", "status=ready,type=feature")
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_LIMIT", "1")
    model_fake.answer(make_stage_proposal())

    outcome = _round(store, stage_repo)

    assert outcome == JobOutcome()
    assert _pushed(stage_repo) == ["feat/2-the-job-drops-a-label", "main"]
    assert _counted(otlp) == [("staged", 1.0)]


def test_a_round_counts_staged_needs_split_failed_and_skipped_items_once_each(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    otlp: FakeCollector,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    github_api.route("POST", f"/repos/{STAGE_REPO}/pulls", OPENED)
    seed_stageable(store)
    seed_stageable(store, "fix(roadmap): the job drops a label")
    seed_stageable(store, "fix(roadmap): the job drops a tag")
    seed_stageable(store, "wip: no type")
    heavy = heavy_group(stage_repo)
    stuck = make_stage_proposal(groups=[heavy])
    model_fake.answer(
        make_stage_proposal(),
        stuck,
        StageSplit(groups=[heavy]),
        make_stage_proposal(pull_request_body="Closes #12 when it merges."),
    )
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_STEP_TOKENS", "6000")
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_LIMIT", "4")

    with pytest.raises(RoadmapStageError) as failed:
        _round(store, stage_repo)

    assert list(failed.value.failed_items) == [3]
    assert _pushed(stage_repo) == ["fix/1-the-job-drops-a-comment", "main"]
    assert _counted(otlp) == [
        ("failed", 1.0),
        ("needs_split", 1.0),
        ("skipped", 1.0),
        ("staged", 1.0),
    ]


def test_a_round_with_nothing_to_stage_counts_nothing(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, otlp: FakeCollector
) -> None:
    assert _round(store, stage_repo) == JobOutcome()
    assert _counted(otlp) == []


def test_a_round_sets_planned_for_an_item_whose_plan_is_on_the_default_branch(
    store: InMemoryRoadmapStore, stage_repo: StageRepo
) -> None:
    """The round reads the plans once for its selection and for the Status of the items (#2920)."""
    number = seed_stageable(store)
    item = store.item(number)
    assert item is not None
    store.set_field(item, ItemField.STATUS, "Ready")
    merge_plan(stage_repo, number)

    outcome = _round(store, stage_repo)

    held = store.item(number)
    assert held is not None
    assert (outcome, held.status) == (JobOutcome(), "Planned")


def test_a_round_without_a_clone_fails_naming_the_job(store: InMemoryRoadmapStore) -> None:
    with pytest.raises(GitOperationError, match="stage"):
        STAGE_ROW.runner(store=store, repo=STAGE_REPO, clone_path=None)
