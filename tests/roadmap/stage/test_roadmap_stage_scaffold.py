"""`devops roadmap stage`: scaffold integration, branch preservation and resume (#5499)."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from devops_cli.config.constants import CONST_ROADMAP_STATUS_READY
from devops_cli.roadmap.stage import stage as stage_module
from devops_cli.roadmap.stage.stage import parse_filters, plan_stage
from devops_cli.roadmap.stores.store import ItemField, StageRecordKey
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import API, github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import (
    OPEN_STEP_READS,
    STAGE_NAME,
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    apply_stage,
    seed_stageable,
    validate_args,
)

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.fixture(autouse=True)
def service_app(config: Callable[..., object]) -> None:
    """The Service App has the bot login `devops-roadmap[bot]`."""
    config(service={"github_app": {"slug": "devops-roadmap"}})


NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=2)
BRANCH = "fix/1-the-job-drops-a-comment"
PULLS = f"/repos/{STAGE_REPO}/pulls"
OPENED = github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201)


@pytest.fixture
def staging(
    roadmap_store: InMemoryRoadmapStore, github_api: GitHubApiFake, openspec_fake: OpenSpecFake
) -> InMemoryRoadmapStore:
    seed_stageable(roadmap_store)
    roadmap_store.seed_file(".github/labels.yml", '- name: "type/docs"\n  color: "0075ca"\n')
    github_api.route("POST", PULLS, OPENED)
    openspec_fake.script_sequence(validate_args("1-the-job-drops-a-comment"), (0, VALID_REPORT))
    return roadmap_store


class Killed(BaseException):
    """The death of the worker: no handler of the job catches it."""


def _pushed(repo: StageRepo) -> list[str]:
    return repo.origin_git("branch", "--format=%(refname:short)").split()


def _stage_round(
    store: InMemoryRoadmapStore, repo: StageRepo, *, now: datetime = NOW
) -> tuple[Any, tuple[int, ...], tuple[int, ...], Any]:
    plan = plan_stage(store, repo=STAGE_REPO, source=repo.clone, filters=parse_filters(()), now=now)
    applied = apply_stage(store, plan, source=repo.clone, now=now)
    return plan, applied.staged, applied.removed, applied.failed


def test_stage_orphan_cleanup_keeps_app_only_branch_of_ready_item(
    stage_repo: StageRepo,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = store.seed_issue(
        "fix(roadmap): the job drops a comment",
        fields={ItemField.STATUS: CONST_ROADMAP_STATUS_READY, ItemField.PRIORITY: "P1-High"},
    )
    item = store.item(number)
    assert item is not None
    mark = json.dumps({"branch": BRANCH, "time": (NOW - timedelta(hours=3)).isoformat()})
    store.set_marks(item, {StageRecordKey.PENDING: mark})
    stage_repo.push_branch(BRANCH, author=STAGE_NAME)

    _plan, _, _, _ = _stage_round(store, stage_repo, now=NOW)

    assert BRANCH in _pushed(stage_repo)
    found = store.item(number)
    assert found is not None
    assert not found.job_record.get(StageRecordKey.PENDING)


def test_a_stage_round_killed_after_checkpoint_push_resumes_with_zero_planner_calls(
    staging: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
) -> None:
    model_fake.answer(make_stage_proposal())
    plan = plan_stage(
        staging, repo=STAGE_REPO, source=stage_repo.clone, filters=parse_filters(()), now=NOW
    )
    with (
        patch.object(stage_module, "_open_pull", side_effect=Killed),
        pytest.raises(Killed) as exc_info,
    ):
        apply_stage(staging, plan, source=stage_repo.clone, now=NOW)
    assert exc_info.type is Killed

    assert _pushed(stage_repo) == [BRANCH, "main"]
    assert len(model_fake.calls) == 1

    # Round 2: worker runs again on the same item with no local kept-plan file on disk
    # Model fake has no more queued answers, so any planner call would fail or record a call
    model_fake.sent.clear()
    model_fake.calls.clear()
    openspec_fake.script_sequence(validate_args("1-the-job-drops-a-comment"), (0, VALID_REPORT))

    with patch("devops_cli.roadmap.stage.stage.read_plan_record", return_value=None):
        _plan2, staged, removed, failed = _stage_round(staging, stage_repo, now=LATER)

    assert failed == ()
    assert staged == (1,)
    assert removed == (1,)
    assert _pushed(stage_repo) == [BRANCH, "main"]
    assert github_api.requested == [*OPEN_STEP_READS, f"POST {API}{PULLS}"]
