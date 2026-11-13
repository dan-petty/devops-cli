"""The kill test of the stage Job (#4559): a kill after each GitHub write of the publish, then the
pod that the Job controller runs again.

A kill before the time budget ends is `evicted`: the check-out stays, and the pod that runs again
in the same Job removes the branch and the draft of the intent mark of the pod before it at once.
The item ends with one open draft, the full stage record and no intent mark, whatever write the
kill came after.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.roadmap.attempt_kill import AttemptKilled
from devops_cli.roadmap.stage import stage as stage_module
from devops_cli.roadmap.stage.stage_job import StageJobExit, recorded_check_in, run_stage_job
from devops_cli.roadmap.stores.store import StageRecordKey
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import API, github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    seed_stageable,
    validate_args,
)

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
JOB = "devops-cli-stage-roadmap-1-0123456789"
BRANCH = "fix/1-the-job-drops-a-comment"
PULLS = f"/repos/{STAGE_REPO}/pulls"
# The draft shares the numbers of the issues: item #1 holds 1, so the draft is #2.
DRAFT = 2
OPENED = github_json({"number": DRAFT, "html_url": f"https://example.com/pull/{DRAFT}"}, status=201)
RECORD = ("stage.branch", "stage.pr", "stage.sha", "stage.groups", "stage.text_hash")


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture
def stageable(
    store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
    model_fake: ModelFake,
    config: Callable[..., Path],
) -> int:
    """One Ready bug that the Service checked out for the Job `JOB`, which this pod runs, and the
    answers of two plans: one for each pod."""
    config(roadmap={"stage": {"job": JOB}})
    number = seed_stageable(store)
    item = store.item(number)
    assert item is not None
    store.set_marks(
        item,
        {
            StageRecordKey.JOB: JOB,
            StageRecordKey.JOB_AT: NOW.isoformat(),
            StageRecordKey.JOB_DEADLINE: (NOW + timedelta(hours=3)).isoformat(),
        },
    )
    github_api.route("POST", PULLS, OPENED)
    github_api.route("PATCH", f"{PULLS}/{DRAFT}", github_json({"number": DRAFT}))
    github_api.route(
        "GET",
        f"{PULLS}/{DRAFT}",
        github_json({"number": DRAFT, "state": "open", "draft": True, "head": {"sha": "a" * 40}}),
    )
    for _ in range(2):
        openspec_fake.script_sequence(validate_args("1-the-job-drops-a-comment"), (0, VALID_REPORT))
    model_fake.answer(make_stage_proposal(), make_stage_proposal())
    return number


def _after_push(store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch) -> None:
    """The kill comes after the push and before the draft."""

    def killed(*_: Any, **__: Any) -> Any:
        raise AttemptKilled

    monkeypatch.setattr(stage_module, "_open_pull", killed)


def _after_draft(store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch) -> None:
    """The kill comes after the create of the draft and before the record write. The store lists
    the draft as GitHub does, as pull request #2."""
    opened = stage_module._open_pull

    def killed(*args: Any, **kwargs: Any) -> Any:
        opened(*args, **kwargs)
        store.seed_pull("plan 1", head_ref=BRANCH, draft=True)
        raise AttemptKilled

    monkeypatch.setattr(stage_module, "_open_pull", killed)


def _after_record(store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch) -> None:
    """The kill comes after the record write and before the labels and the comment."""

    def killed(*_: Any, **__: Any) -> Any:
        raise AttemptKilled

    monkeypatch.setattr(stage_module, "_label_pull", killed)


@pytest.mark.parametrize(
    ("kill", "drafts", "closes"),
    [
        pytest.param(_after_push, 1, 0, id="after-push"),
        pytest.param(_after_draft, 2, 1, id="after-draft"),
        pytest.param(_after_record, 1, 0, id="after-record"),
    ],
)
def test_a_job_killed_after_a_github_write_ends_with_one_draft_and_the_full_record(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    github_api: GitHubApiFake,
    stageable: int,
    monkeypatch: pytest.MonkeyPatch,
    kill: Callable[[InMemoryRoadmapStore, pytest.MonkeyPatch], None],
    drafts: int,
    closes: int,
) -> None:
    with monkeypatch.context() as killing:
        kill(store, killing)
        first = run_stage_job(
            store, repo=STAGE_REPO, item=stageable, source=stage_repo.clone, now=NOW
        )
    again = run_stage_job(
        store,
        repo=STAGE_REPO,
        item=stageable,
        source=stage_repo.clone,
        now=NOW + timedelta(minutes=1),
    )

    item = store.item(stageable)
    assert item is not None
    record = {str(key): value for key, value in item.job_record.items() if value is not None}
    check_in = recorded_check_in(item)
    assert check_in is not None
    assert (
        first.exit_code,
        again.exit_code,
        github_api.requested.count(f"POST {API}{PULLS}") - closes,
        github_api.requested.count(f"PATCH {API}{PULLS}/{DRAFT}"),
        [key for key in RECORD if key not in record],
        "stage.pending" in record,
        "stage.job" in record,
        check_in.job,
        stage_repo.origin_git("branch", "--format=%(refname:short)").split(),
    ) == (
        StageJobExit.EVICTED,
        StageJobExit.RESULT,
        1,
        closes,
        [],
        False,
        False,
        JOB,
        [BRANCH, "main"],
    )
    assert github_api.requested.count(f"POST {API}{PULLS}") == drafts
