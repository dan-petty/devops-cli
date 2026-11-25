"""`devops roadmap stage`: scaffold integration, branch preservation and resume (#5499)."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_STATUS_NEW,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.roadmap.stage import stage as stage_module
from devops_cli.roadmap.stage.stage import parse_filters, plan_stage
from devops_cli.roadmap.stage.stage_change import StageSplit
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
    heavy_group,
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
    github_api.route(
        "POST",
        f"{PULLS}/5/requested_reviewers",
        github_json({"requested_reviewers": []}),
    )
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
        labels=("type/bug",),
        fields={ItemField.STATUS: CONST_ROADMAP_STATUS_READY, ItemField.PRIORITY: "P1-High"},
    )
    item = store.item(number)
    assert item is not None
    mark = json.dumps({"branch": BRANCH, "time": (NOW - timedelta(hours=3)).isoformat()})
    store.set_marks(
        item,
        {
            StageRecordKey.PENDING: mark,
            StageRecordKey.BRANCH: BRANCH,
            StageRecordKey.TEXT_HASH: "old-hash",
        },
    )
    stage_repo.push_branch(BRANCH, author=STAGE_NAME)

    plan = plan_stage(
        store,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        filters=parse_filters(("type=feature",)),
        now=NOW,
    )
    applied = apply_stage(store, plan, source=stage_repo.clone, now=NOW)

    assert applied.removed == (number,)
    assert BRANCH in _pushed(stage_repo)
    found = store.item(number)
    assert found is not None
    assert found.job_record.get(StageRecordKey.PENDING) == mark
    assert found.job_record.get(StageRecordKey.BRANCH) is None
    assert found.job_record.get(StageRecordKey.TEXT_HASH) is None


def test_next_stage_round_resumes_and_stages_after_orphan_cleanup_kept_branch(
    staging: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
) -> None:
    item = staging.item(1)
    assert item is not None
    mark = json.dumps({"branch": BRANCH, "time": (NOW - timedelta(hours=3)).isoformat()})
    staging.set_marks(item, {StageRecordKey.PENDING: mark})
    stage_repo.push_branch(BRANCH, author=STAGE_NAME)

    cleanup_plan = plan_stage(
        staging,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        filters=parse_filters(("type=feature",)),
        now=NOW,
    )
    cleanup_applied = apply_stage(staging, cleanup_plan, source=stage_repo.clone, now=NOW)
    assert (cleanup_applied.removed, cleanup_applied.staged, BRANCH in _pushed(stage_repo)) == (
        (1,),
        (),
        True,
    )
    held = staging.item(1)
    assert held is not None
    assert held.job_record.get(StageRecordKey.PENDING) == mark

    model_fake.answer(make_stage_proposal())
    _plan2, staged, removed, failed = _stage_round(staging, stage_repo, now=NOW)

    record = staging.item(1)
    assert record is not None
    assert (failed, staged, removed, _pushed(stage_repo)) == (
        (),
        (1,),
        (1,),
        [BRANCH, "main"],
    )
    assert record.job_record.get(StageRecordKey.PR) == "5"
    assert record.job_record.get(StageRecordKey.PENDING) is None
    assert github_api.requested == [
        *OPEN_STEP_READS,
        f"POST {API}{PULLS}",
        f"POST {API}{PULLS}/5/requested_reviewers",
    ]


def test_orphan_cleanup_clears_pending_when_branch_is_deleted_or_gone(
    stage_repo: StageRepo,
    github_api: GitHubApiFake,
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    non_ready = store.seed_issue(
        "fix(roadmap): the job drops a comment",
        fields={ItemField.STATUS: CONST_ROADMAP_STATUS_NEW, ItemField.PRIORITY: "P1-High"},
    )
    gone_ready = store.seed_issue(
        "fix(roadmap): keep the last comment",
        fields={ItemField.STATUS: CONST_ROADMAP_STATUS_READY, ItemField.PRIORITY: "P1-High"},
    )
    mark = json.dumps({"branch": BRANCH, "time": (NOW - timedelta(hours=3)).isoformat()})
    missing_mark = json.dumps(
        {
            "branch": "fix/2-keep-the-last-comment",
            "time": (NOW - timedelta(hours=3)).isoformat(),
        }
    )
    for num, item_mark in ((non_ready, mark), (gone_ready, missing_mark)):
        held = store.item(num)
        assert held is not None
        store.set_marks(held, {StageRecordKey.PENDING: item_mark})
    stage_repo.push_branch(BRANCH, author=STAGE_NAME)

    plan = plan_stage(
        store,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        filters=parse_filters(("type=feature",)),
        now=NOW,
    )
    applied = apply_stage(store, plan, source=stage_repo.clone, now=NOW)

    assert sorted(applied.removed) == sorted([non_ready, gone_ready])
    assert BRANCH not in _pushed(stage_repo)
    for num in (non_ready, gone_ready):
        updated = store.item(num)
        assert updated is not None
        assert updated.job_record.get(StageRecordKey.PENDING) is None


def test_budget_stop_on_kept_branch_clears_stage_pending(
    staging: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
) -> None:
    item = staging.item(1)
    assert item is not None
    mark = json.dumps({"branch": BRANCH, "time": (NOW - timedelta(hours=3)).isoformat()})
    staging.set_marks(item, {StageRecordKey.PENDING: mark})
    stage_repo.push_branch(BRANCH, author=STAGE_NAME)
    heavy = heavy_group(stage_repo)
    model_fake.answer(make_stage_proposal(groups=[heavy]), StageSplit(groups=[heavy]))

    plan = plan_stage(
        staging,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        filters=parse_filters(()),
        step_tokens=6000,
        now=NOW,
    )
    applied = apply_stage(staging, plan, source=stage_repo.clone, now=NOW)

    stopped_item = staging.item(1)
    assert stopped_item is not None
    assert applied.stopped == (1,)
    assert stopped_item.job_record.get(StageRecordKey.NEEDS_SPLIT)
    assert stopped_item.job_record.get(StageRecordKey.FILE_CAP)
    assert stopped_item.job_record.get(StageRecordKey.PENDING) is None

    next_plan = plan_stage(
        staging,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        filters=parse_filters(()),
        now=NOW + timedelta(hours=3),
    )
    assert next_plan.removals == ()


def test_a_push_url_in_the_clone_of_the_job_changes_nothing(
    staging: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    tmp_path: Path,
) -> None:
    """`publish` pushes the plan commit from a new repository to the repository on GitHub, so
    the configuration of the clone that the planner reads never reaches the push (#6704)."""
    stage_repo.git("config", "remote.origin.pushurl", str(tmp_path / "elsewhere.git"))
    model_fake.answer(make_stage_proposal())

    plan, staged, _removed, failed = _stage_round(staging, stage_repo, now=NOW)

    assert (failed, staged) == ((), (1,))
    assert stage_repo.origin_git("log", "--format=%an|%s|%b", f"main..{BRANCH}").split("\n")[
        :1
    ] == [f"{STAGE_NAME}|{plan.ready[0].title}|Plans #1."]


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
    assert github_api.requested == [
        *OPEN_STEP_READS,
        f"POST {API}{PULLS}",
        f"POST {API}{PULLS}/5/requested_reviewers",
    ]
