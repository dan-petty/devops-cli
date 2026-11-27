"""`prepare` of the stage Job on its phases (#6705): what needs no model, and the run of the agent.

`prepare` holds the App key and runs no agent. It reads the round of the item, makes the writes of
`StageWriter.begin`, and decides the CI job-time premise, the false premise of the body probe and
the blocker of an open plan. A decision that ends the run checks in. Else it clones the repository
at the tip of the default branch, commits the scaffold of the change folder with its own date, and
writes the state file, the issue listing and the inputs of the agent.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx2
import pytest

from devops_cli.config.constants import (
    CONST_OPENSPEC_SCAFFOLD_MARKER,
    CONST_ROADMAP_PHASE_INPUT_FILE,
    CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
    CONST_ROADMAP_PHASE_STATE_FILE,
    CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME,
    CONST_ROADMAP_STAGE_ISSUES_FILE,
)
from devops_cli.exceptions import GitHubOperationError
from devops_cli.exceptions import git as git_errors
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.roadmap.failure import FailureClass, StepName
from devops_cli.roadmap.phases.files import RunFolders
from devops_cli.roadmap.stage.stage_change import render_change
from devops_cli.roadmap.stage.stage_job import StageJobExit
from devops_cli.roadmap.stage.stage_job_phases import (
    StageAgentInput,
    StageState,
    prepare_stage_job,
)
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from devops_cli.roadmap.stores.store import GitHubState, ItemField, RefineRecordKey
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import RunnerSession, github_json
from tests.support.fakes.github_repository import GitHubFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_implement import merge_plan
from tests.support.roadmap_stage import STAGE_NAME, STAGE_REPO, StageRepo, seed_stageable

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake

pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.fixture(autouse=True)
def _fake_github(github_api: GitHubApiFake) -> None:
    """Provide the fake GitHub API and GraphQL quota for `prepare` snapshot reads (#6831)."""
    get_github_rate_limiter().update_quota(
        "graphql", remaining=5000, limit=5000, reset_epoch=time.time() + 600.0
    )


NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
CHANGE = "1-the-job-drops-a-comment"
FIELDS = {ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"}


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture
def folders(tmp_path: Path) -> RunFolders:
    return RunFolders(tmp_path / "run").make()


def _prepare(store: InMemoryRoadmapStore, repo: StageRepo, folders: RunFolders, item: int):
    return prepare_stage_job(store, folders, repo=STAGE_REPO, item=item, source=repo.clone, now=NOW)


def _state(folders: RunFolders) -> StageState:
    return StageState.model_validate_json(
        (folders.state / CONST_ROADMAP_PHASE_STATE_FILE).read_text(encoding="utf-8")
    )


def _git(path: Path, *args: str) -> str:
    from tests.support.roadmap_stage import run_git

    return run_git(path, *args)


def test_prepare_commits_the_scaffold_with_its_date_and_writes_the_state_and_the_inputs(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, folders: RunFolders
) -> None:
    number = seed_stageable(store)
    store.seed_comment(number, "Keep the newest comment of the thread.")
    store.seed_comment(number, "The fix must also keep the reactions.")
    base = stage_repo.git("rev-parse", "main")

    run = _prepare(store, stage_repo, folders, number)

    assert run is None
    clone = folders.work / CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME
    root = f"openspec/changes/{CHANGE}"
    assert _git(clone, "rev-parse", "HEAD^") == base
    assert _git(clone, "show", f"HEAD:{root}/.openspec.yaml") == (
        "schema: spec-driven\ncreated: 2026-11-13"
    )
    assert CONST_OPENSPEC_SCAFFOLD_MARKER in _git(clone, "show", f"HEAD:{root}/tasks.md")
    assert _git(clone, "log", "-1", "--format=%an") == STAGE_NAME
    state = _state(folders)
    assert (state.repo, state.item, state.ended) == (STAGE_REPO, number, False)
    assert (state.base, state.default, state.lease, state.change) == (base, "main", "", CHANGE)
    assert state.created == NOW.date()
    assert state.deadline > NOW
    inputs = StageAgentInput.model_validate_json(
        (folders.work / CONST_ROADMAP_PHASE_INPUT_FILE).read_text(encoding="utf-8")
    )
    assert inputs.body == "The job drops the last comment of a thread."
    assert [comment.text for comment in inputs.comments] == [
        "Keep the newest comment of the thread.",
        "The fix must also keep the reactions.",
    ]
    assert (inputs.base, inputs.change, inputs.created) == (base, CHANGE, NOW.date())
    listing = json.loads((folders.work / CONST_ROADMAP_STAGE_ISSUES_FILE).read_text("utf-8"))
    assert [record["number"] for record in listing] == [number]


def test_the_listing_of_a_store_over_1_mib_holds_the_item_body_and_the_states_only(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, folders: RunFolders
) -> None:
    large = "x" * 400_000
    others = [
        store.seed_issue(f"fix(roadmap): item {i}", body=large, fields=FIELDS) for i in range(3)
    ]
    closed = store.seed_issue(
        "fix(roadmap): done", body=large, fields=FIELDS, state=GitHubState.CLOSED
    )
    plans: dict[str, str] = {}
    for other in (*others, closed):
        plans |= render_change(
            f"{other}-item", make_stage_proposal(), {"comment-thread"}, created=NOW.date()
        )
    stage_repo.track(plans)
    number = seed_stageable(store)

    assert _prepare(store, stage_repo, folders, number) is None

    data = (folders.state / CONST_ROADMAP_STAGE_ISSUES_FILE).read_bytes()
    assert len(data) < CONST_ROADMAP_PHASE_JSON_MAX_BYTES
    listing = {record["number"]: record for record in json.loads(data)}
    assert sorted(listing) == sorted([*others, closed, number])
    assert {n: (r["body"], r["state"]) for n, r in listing.items() if n != number} == {
        **{other: ("", "open") for other in others},
        closed: ("", "closed"),
    }
    assert listing[number]["body"] == "The job drops the last comment of a thread."


def test_the_listing_leaves_out_the_title_of_an_issue_of_an_outside_account(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, folders: RunFolders
) -> None:
    other = store.seed_issue(
        "fix: a change of an outside account",
        fields=FIELDS,
        state=GitHubState.CLOSED,
        author_association="NONE",
        author_login="a-stranger",
    )
    stage_repo.track(
        render_change(
            f"{other}-item", make_stage_proposal(), {"comment-thread"}, created=NOW.date()
        )
    )
    number = seed_stageable(store)

    assert _prepare(store, stage_repo, folders, number) is None

    data = (folders.work / CONST_ROADMAP_STAGE_ISSUES_FILE).read_bytes()
    listing = {record["number"]: record for record in json.loads(data)}
    assert (listing[other]["title"], listing[other]["state"], listing[number]["title"]) == (
        "(title left out: an account with no write access opened the item)",
        "closed",
        store.item(number).title,
    )


def test_a_failed_read_of_the_comments_fails_the_item_with_ci_infra(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, folders: RunFolders
) -> None:
    number = seed_stageable(store)
    store.fail_read("comments_on", GitHubOperationError("HTTP 502", operation="roadmap.read"))

    run = _prepare(store, stage_repo, folders, number)

    assert run is not None
    assert run.exit_code is StageJobExit.EVICTED
    item = store.item(number)
    assert item is not None
    record = {str(key): value for key, value in item.job_record.items()}
    assert (record["stage.failed_class"], record["stage.failed_step"]) == (
        FailureClass.CI_INFRA.value,
        StepName.PLAN.value,
    )
    state = _state(folders)
    assert (state.ended, state.end) == (True, StageJobExit.EVICTED)
    assert not (folders.work / CONST_ROADMAP_PHASE_INPUT_FILE).exists()


class _ItemLeft(InMemoryRoadmapStore):
    """A store whose read of the comments raises the error of no issue for each number, as the
    GitHub store raises it for an item that left the repository after the Job read it (#7337).
    The class of the error is read from its module when the store raises."""

    def comments_on(self, number: int) -> Any:
        raise git_errors.GitHubNotAnIssueError(STAGE_REPO, number)


def test_prepare_ends_with_no_failure_when_its_item_is_no_issue_of_the_repository(
    stage_repo: StageRepo, folders: RunFolders
) -> None:
    """The item of the Job left the repository after `prepare` selected it. `prepare` ends the
    run with no result of the item: it records no failure class and no failure mark, and it
    writes no inputs for the agent."""
    store = _ItemLeft(repo=STAGE_REPO)
    number = seed_stageable(store)

    run = _prepare(store, stage_repo, folders, number)

    item = store.item(number)
    assert run is not None
    assert item is not None
    record = {str(key): value for key, value in item.job_record.items() if value is not None}
    assert [key for key in record if key.startswith("stage.failed")] == []
    assert _state(folders).ended is True
    assert not (folders.work / CONST_ROADMAP_PHASE_INPUT_FILE).exists()


def _slow_job_runs(api: GitHubApiFake) -> None:
    """Each completed run of the CI workflow ran `Tests & Coverage` for 400 s."""
    started = NOW - timedelta(hours=1)
    job = {
        "name": "Tests & Coverage",
        "conclusion": "success",
        "started_at": started.isoformat(),
        "completed_at": (started + timedelta(seconds=400)).isoformat(),
    }

    def serve(request: httpx2.Request) -> httpx2.Response | None:
        path = request.url.path
        if path.endswith("/actions/workflows/ci.yml/runs"):
            return github_json({"total_count": 1, "workflow_runs": [{"id": 7}]})
        if path.endswith("/actions/runs/7/jobs"):
            return github_json({"total_count": 1, "jobs": [job]})
        return None

    api.serve(serve)


def _returned(store: InMemoryRoadmapStore, number: int) -> tuple[str | None, list[str]]:
    item = store.item(number)
    assert item is not None
    return item.status, [comment.body for comment in store.comments_on(number)]


def test_a_false_job_time_premise_returns_the_item_in_prepare(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    folders: RunFolders,
    github_api: GitHubApiFake,
) -> None:
    _slow_job_runs(github_api)
    body = (
        "Keep the checks fast.\n\n## Acceptance criteria\n\n"
        "- [ ] The `Tests & Coverage` average job duration stays under 300 s.\n"
    )
    number = seed_stageable(store, body=body)

    run = _prepare(store, stage_repo, folders, number)

    assert run is not None
    assert run.exit_code is StageJobExit.RESULT
    status, comments = _returned(store, number)
    assert status == "New"
    assert any("300" in comment for comment in comments)
    assert _state(folders).ended
    assert not (folders.work / CONST_ROADMAP_PHASE_INPUT_FILE).exists()


def test_a_false_premise_of_the_body_returns_the_item_in_prepare(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, folders: RunFolders
) -> None:
    stage_repo.track(
        {
            "src/devops_cli/model.py": (
                "class PullStatus:\n    labels: tuple[str, ...] = ()\n    state: str = ''\n"
            )
        }
    )
    number = seed_stageable(store, body="The issue says `PullStatus.labels` is absent.")

    run = _prepare(store, stage_repo, folders, number)

    assert run is not None
    assert run.exit_code is StageJobExit.RESULT
    status, comments = _returned(store, number)
    assert status == "New"
    assert any("`PullStatus` defines the field `labels`" in comment for comment in comments)
    assert not (folders.work / CONST_ROADMAP_PHASE_INPUT_FILE).exists()


def test_a_blocker_of_an_open_plan_returns_the_item_in_prepare(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    folders: RunFolders,
) -> None:
    blocker = store.seed_issue("feat(roadmap): add the module", fields=FIELDS)
    group = make_stage_proposal().groups[0]
    creates = group.model_copy(
        update={
            "changes": [*group.changes, "src/devops_cli/new_module.py"],
            "creates": [*group.creates, "src/devops_cli/new_module.py"],
            "creates_lines": {**group.creates_lines, "src/devops_cli/new_module.py": 20},
        }
    )
    stage_repo.track(
        render_change(
            f"{blocker}-add-the-module",
            make_stage_proposal(groups=[creates]),
            {"comment-thread"},
            created=NOW.date(),
        )
    )
    number = seed_stageable(store, body="Call `src/devops_cli/new_module.py` from the job.")

    run = _prepare(store, stage_repo, folders, number)

    assert run is not None
    assert run.exit_code is StageJobExit.RESULT
    item = store.item(number)
    assert item is not None
    assert item.status == "New"
    assert item.job_record.get(RefineRecordKey.BLOCKED_BY) == str(blocker)
    assert not (folders.work / CONST_ROADMAP_PHASE_INPUT_FILE).exists()


LEFT_FOLDER_ANSWERS = [
    pytest.param(False, "", id="status-301"),
    pytest.param(True, ": GitHub answers with example/other#9", id="the-issue-at-its-new-place"),
]


@pytest.mark.parametrize(("followed", "place"), LEFT_FOLDER_ANSWERS)
def test_prepare_goes_on_when_the_issue_of_an_active_change_folder_left_the_repository(
    stage_repo: StageRepo,
    folders: RunFolders,
    caplog: pytest.LogCaptureFixture,
    followed: bool,
    place: str,
) -> None:
    """The default branch holds the active change folder of #5, and #5 was transferred to another
    repository (#7337). `prepare` reads the issue of each active change folder for the blockers of
    the item and for the issue listing of the agent. The read of #5 answers 301 when `gh` does not
    follow the redirect, else it answers with the issue at its new place. Both are no issue of the
    repository: the folder of #5 names no open plan and gives no record in the listing, and
    `prepare` goes on with item #6 and with the folder of the open item #4. The store of a Job
    read no listing, and it logs the number that it leaves out one time."""
    labels = ("type/bug", "priority/p1-high")
    github = GitHubFake(STAGE_REPO)
    github.seed_issue(4, "fix(roadmap): the open item", labels=(*labels, "status/planned"))
    github.seed_issue(5, "fix(roadmap): the item that left", labels=(*labels, "status/planned"))
    github.seed_issue(
        6,
        "fix(roadmap): the job drops a comment",
        labels=(*labels, "status/ready"),
        body="The job drops the last comment of a thread.",
        author_association="OWNER",
    )
    merge_plan(stage_repo, 4, slug="the-open-item")
    merge_plan(stage_repo, 5, slug="the-item-that-left")
    github.move_issue(5, to="example/other", as_number=9, followed=followed)
    store = GitHubRoadmapStore(STAGE_REPO, runner=github, session=RunnerSession(github))

    with caplog.at_level(logging.WARNING):
        run = prepare_stage_job(
            store, folders, repo=STAGE_REPO, item=6, source=stage_repo.clone, now=NOW
        )

    listing = json.loads((folders.work / CONST_ROADMAP_STAGE_ISSUES_FILE).read_text("utf-8"))
    assert [text for log in caplog.records if "#5 " in (text := log.getMessage())] == [
        f"#5 is no issue of {STAGE_REPO} now{place}. The store leaves it out."
    ]
    assert run is None
    assert (_state(folders).item, _state(folders).ended) == (6, False)
    assert [record["number"] for record in listing] == [6, 4]
