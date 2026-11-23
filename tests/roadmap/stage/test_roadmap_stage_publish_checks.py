"""The checks of `publish` of the stage Job before its one push (#6705).

`publish` reads the outputs of the agent phase as data. It allows only the files of a plan, then
runs the checks in `before_push` of its one `publish_patch`: the secret scan, the date of the
change, `devops openspec check`, `openspec validate --strict` and the recheck with the base. A fixed
list of findings ends as `ci_infra`; a plan whose only finding is `group-over-budget` stops with
the owner question of the budget; each other finding ends as `plan_defect`. A refused plan pushes
no branch.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_PHASE_PATCH_MAX_BYTES,
    CONST_ROADMAP_PHASE_STATE_FILE,
    CONST_ROADMAP_STAGE_PLAN_PATCH_FILE,
)
from devops_cli.openspec.scaffold import scaffold_proposal
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.stage.stage_job import StageJobExit, StageJobRun
from devops_cli.roadmap.stage.stage_job_phases import publish_stage_job
from devops_cli.roadmap.stores.store import StageRecordKey
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    heavy_group,
    validate_args,
    validation_report,
)
from tests.support.roadmap_stage_phases import (
    PHASE_CHANGE,
    PHASE_ROOT,
    gate_files,
    hand_over,
    lockfile,
    plan_files,
    prepare_run,
)

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

BRANCH = "fix/1-the-job-drops-a-comment"
SECRET = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"
CANDIDATE = "# Keep the last comment\n\nThe job keeps the last comment of a thread.\n"


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture
def gate_repo(
    stage_repo: StageRepo, openspec_fake: OpenSpecFake, github_api: GitHubApiFake
) -> StageRepo:
    """A stage repository that the OpenSpec gate reads as sound, and GitHub that opens a draft."""
    stage_repo.track(gate_files(openspec_fake.version))
    openspec_fake.script(validate_args(PHASE_CHANGE), 0, VALID_REPORT)
    github_api.route(
        "POST",
        f"/repos/{STAGE_REPO}/pulls",
        github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201),
    )
    return stage_repo


def _publish(
    store: InMemoryRoadmapStore,
    repo: StageRepo,
    tmp_path: Path,
    files: dict[str, str | bytes | None] | Callable[[datetime], dict[str, Any]],
    **outputs: Any,
) -> tuple[StageJobRun, int]:
    now = datetime.now(UTC)
    folders, number = prepare_run(store, repo, tmp_path, now=now)
    given = files(now) if callable(files) else files
    hand_over(folders, given, candidate=outputs.pop("candidate", CANDIDATE), **outputs)
    return publish_stage_job(store, folders, repo=STAGE_REPO, item=number, now=now), number


def _ended(store: InMemoryRoadmapStore, repo: StageRepo, number: int) -> tuple[Any, ...]:
    """The class that the item records, its Status, and the branches of `origin`."""
    item = store.item(number)
    assert item is not None
    return (
        item.job_record.get(StageRecordKey.FAILED_CLASS),
        item.status,
        repo.origin_git("branch", "--format=%(refname:short)").split(),
    )


def _plan(now: datetime) -> dict[str, Any]:
    return dict(plan_files(now.date()))


# The end of a refused plan: exit 1, the class `plan_defect`, the Status as it was, and no branch.
REFUSED = (StageJobExit.FAILURE, (FailureClass.PLAN_DEFECT.value, "Ready", ["main"]))


def _end(
    run: StageJobRun, store: InMemoryRoadmapStore, repo: StageRepo, number: int
) -> tuple[Any, ...]:
    return (run.exit_code, _ended(store, repo, number))


def test_a_plan_that_passes_each_check_is_pushed_once(
    store: InMemoryRoadmapStore, gate_repo: StageRepo, tmp_path: Path
) -> None:
    run, number = _publish(store, gate_repo, tmp_path, _plan)

    assert run.exit_code is StageJobExit.RESULT, run
    assert _ended(store, gate_repo, number) == (None, "Ready", [BRANCH, "main"])


def test_a_path_outside_the_change_folder_is_a_plan_defect(
    store: InMemoryRoadmapStore, gate_repo: StageRepo, tmp_path: Path
) -> None:
    run, number = _publish(
        store,
        gate_repo,
        tmp_path,
        lambda now: {**_plan(now), "src/devops_cli/sample.py": "VALUE = 1\n"},
    )

    assert _end(run, store, gate_repo, number) == REFUSED


def test_a_link_in_the_change_folder_is_a_plan_defect_and_not_ci_infra(
    store: InMemoryRoadmapStore, gate_repo: StageRepo, tmp_path: Path
) -> None:
    run, number = _publish(
        store, gate_repo, tmp_path, _plan, links={f"{PHASE_ROOT}/notes.md": "/proc/self/environ"}
    )

    assert _end(run, store, gate_repo, number) == REFUSED


def test_a_mode_other_than_100644_is_a_plan_defect(
    store: InMemoryRoadmapStore, gate_repo: StageRepo, tmp_path: Path
) -> None:
    run, number = _publish(
        store, gate_repo, tmp_path, _plan, modes={f"{PHASE_ROOT}/design.md": 0o755}
    )

    assert _end(run, store, gate_repo, number) == REFUSED


def test_a_file_that_is_not_utf8_is_a_plan_defect(
    store: InMemoryRoadmapStore, gate_repo: StageRepo, tmp_path: Path
) -> None:
    run, number = _publish(
        store,
        gate_repo,
        tmp_path,
        lambda now: {**_plan(now), f"{PHASE_ROOT}/design.md": b"# Design\n\n\xff\xfe\n"},
    )

    assert _end(run, store, gate_repo, number) == REFUSED


def test_a_secret_in_a_plan_file_is_a_plan_defect(
    store: InMemoryRoadmapStore, gate_repo: StageRepo, tmp_path: Path
) -> None:
    def files(now: datetime) -> dict[str, Any]:
        plan = _plan(now)
        design = f"{PHASE_ROOT}/design.md"
        plan[design] = plan[design].replace("It is the simplest fix.", f"It uses {SECRET}.")
        return plan

    run, number = _publish(store, gate_repo, tmp_path, files)

    assert _end(run, store, gate_repo, number) == REFUSED


def test_another_date_of_the_change_is_a_plan_defect(
    store: InMemoryRoadmapStore, gate_repo: StageRepo, tmp_path: Path
) -> None:
    run, number = _publish(
        store, gate_repo, tmp_path, lambda _now: dict(plan_files(datetime(2026, 1, 2).date()))
    )

    assert _end(run, store, gate_repo, number) == REFUSED


def test_a_scaffold_marker_is_a_plan_defect(
    store: InMemoryRoadmapStore, gate_repo: StageRepo, tmp_path: Path
) -> None:
    run, number = _publish(
        store,
        gate_repo,
        tmp_path,
        lambda now: {**_plan(now), f"{PHASE_ROOT}/proposal.md": scaffold_proposal(1)},
    )

    assert _end(run, store, gate_repo, number) == REFUSED


def test_a_refusal_of_openspec_validate_is_a_plan_defect(
    store: InMemoryRoadmapStore,
    gate_repo: StageRepo,
    tmp_path: Path,
    openspec_fake: OpenSpecFake,
) -> None:
    openspec_fake.script(
        validate_args(PHASE_CHANGE),
        1,
        validation_report(("ERROR", "A requirement has no scenario"), valid=False),
    )

    run, number = _publish(store, gate_repo, tmp_path, _plan)

    assert _end(run, store, gate_repo, number) == REFUSED


def test_an_overlap_of_two_changes_is_a_plan_defect(
    store: InMemoryRoadmapStore,
    gate_repo: StageRepo,
    tmp_path: Path,
    openspec_fake: OpenSpecFake,
) -> None:
    other = "9-keep-the-thread"
    openspec_fake.script(
        ("list", "--json"), 0, json.dumps({"changes": [{"name": PHASE_CHANGE}, {"name": other}]})
    )
    delta = {
        "deltas": [
            {
                "spec": "comment-thread",
                "operation": "MODIFIED",
                "requirement": {"name": "The job keeps every comment"},
            }
        ]
    }
    for change in (PHASE_CHANGE, other):
        openspec_fake.script(("show", change, "--json", "--deltas-only"), 0, json.dumps(delta))

    run, number = _publish(store, gate_repo, tmp_path, _plan)

    assert _end(run, store, gate_repo, number) == REFUSED


@pytest.mark.parametrize("end", ["ended", "unverified"])
def test_a_folder_that_the_recheck_refuses_is_a_plan_defect(
    store: InMemoryRoadmapStore, gate_repo: StageRepo, tmp_path: Path, end: str
) -> None:
    group = make_stage_proposal().groups[0].model_copy(update={"reads": ["src/devops_cli/gone.py"]})

    run, number = _publish(
        store,
        gate_repo,
        tmp_path,
        lambda now: dict(plan_files(now.date(), make_stage_proposal(groups=[group]))),
        outcome={"end": end},
    )

    assert _end(run, store, gate_repo, number) == REFUSED


@pytest.mark.parametrize(
    "outcome",
    [{"end": "premise_false"}, {"end": "ended", "trace": "the tools that the agent ran"}],
)
def test_an_outcome_outside_its_model_is_a_plan_defect_that_returns_no_item(
    store: InMemoryRoadmapStore, gate_repo: StageRepo, tmp_path: Path, outcome: dict[str, str]
) -> None:
    run, number = _publish(store, gate_repo, tmp_path, _plan, outcome=outcome)

    assert _end(run, store, gate_repo, number) == REFUSED


def test_a_patch_over_its_limit_is_a_plan_defect(
    store: InMemoryRoadmapStore, gate_repo: StageRepo, tmp_path: Path
) -> None:
    now = datetime.now(UTC)
    folders, number = prepare_run(store, gate_repo, tmp_path, now=now)
    hand_over(folders, _plan(now), candidate=CANDIDATE)
    (folders.out / CONST_ROADMAP_STAGE_PLAN_PATCH_FILE).write_bytes(
        b"x" * (CONST_ROADMAP_PHASE_PATCH_MAX_BYTES + 1)
    )

    run = publish_stage_job(store, folders, repo=STAGE_REPO, item=number, now=now)

    assert _end(run, store, gate_repo, number) == REFUSED


def test_a_state_of_another_item_is_a_plan_defect(
    store: InMemoryRoadmapStore, gate_repo: StageRepo, tmp_path: Path
) -> None:
    now = datetime.now(UTC)
    folders, number = prepare_run(store, gate_repo, tmp_path, now=now)
    hand_over(folders, _plan(now), candidate=CANDIDATE)
    path = folders.state / CONST_ROADMAP_PHASE_STATE_FILE
    state = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps({**state, "item": number + 1}), encoding="utf-8")

    run = publish_stage_job(store, folders, repo=STAGE_REPO, item=number, now=now)

    assert _end(run, store, gate_repo, number) == REFUSED


def test_an_openspec_off_its_pin_is_ci_infra(
    store: InMemoryRoadmapStore, gate_repo: StageRepo, tmp_path: Path
) -> None:
    gate_repo.track({"package-lock.json": lockfile("0.0.1")})

    run, number = _publish(store, gate_repo, tmp_path, _plan)

    assert run.exit_code is StageJobExit.EVICTED
    assert _ended(store, gate_repo, number) == (FailureClass.CI_INFRA.value, "Ready", ["main"])


def test_a_missing_tool_is_ci_infra(
    store: InMemoryRoadmapStore,
    gate_repo: StageRepo,
    tmp_path: Path,
    openspec_fake: OpenSpecFake,
) -> None:
    now = datetime.now(UTC)
    folders, number = prepare_run(store, gate_repo, tmp_path, now=now)
    hand_over(folders, _plan(now), candidate=CANDIDATE)
    openspec_fake.installed = False

    run = publish_stage_job(store, folders, repo=STAGE_REPO, item=number, now=now)

    assert run.exit_code is StageJobExit.EVICTED
    assert _ended(store, gate_repo, number) == (FailureClass.CI_INFRA.value, "Ready", ["main"])


def test_a_group_over_the_budget_stops_with_the_owner_question(
    store: InMemoryRoadmapStore,
    gate_repo: StageRepo,
    tmp_path: Path,
    config: Callable[..., Path],
) -> None:
    config(roadmap={"stage": {"step_tokens": 1000}})
    group = heavy_group(gate_repo)

    run, number = _publish(
        store,
        gate_repo,
        tmp_path,
        lambda now: dict(plan_files(now.date(), make_stage_proposal(groups=[group]))),
    )

    assert run.exit_code is StageJobExit.RESULT
    item = store.item(number)
    assert item is not None
    assert item.job_record.get(StageRecordKey.NEEDS_SPLIT)
    assert item.job_record.get(StageRecordKey.FAILED_CLASS) is None
    assert item.job_record.get(StageRecordKey.PENDING) is None
    assert gate_repo.origin_git("branch", "--format=%(refname:short)").split() == ["main"]
