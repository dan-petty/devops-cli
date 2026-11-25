"""`prepare` of the stage Job on its phases (#6705): what needs no model, and the run of the agent.

`prepare` holds the App key and runs no agent. It reads the round of the item, makes the writes of
`StageWriter.begin`, and decides the CI job-time premise, the false premise of the body probe and
the blocker of an open plan. A decision that ends the run checks in. Else it clones the repository
at the tip of the default branch, commits the scaffold of the change folder with its own date, and
writes the state file, the issue listing and the inputs of the agent.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

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
from devops_cli.roadmap.stores.store import GitHubState, ItemField, RefineRecordKey
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
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
