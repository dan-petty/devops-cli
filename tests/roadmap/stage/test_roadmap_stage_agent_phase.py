"""The agent phase of the stage Job (#6705): no GitHub credential, and only what `publish` reads.

The phase refuses the App key, a GitHub token and a gh login, and an output folder that is there
before its outputs. It runs the stage agent in the clone of `prepare` and writes the patch of the
change folder from the base, the body candidate and a `StageOutcome`, which holds the end, the
failed checks and fixed counts.
"""

from __future__ import annotations

import os
import signal
from datetime import UTC, datetime
from pathlib import Path

import pytest

from devops_cli.config.constants import (
    CONST_GITHUB_AGENT_REFUSED_ENV,
    CONST_ROADMAP_PHASE_OUTCOME_FILE,
    CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME,
    CONST_ROADMAP_STAGE_CANDIDATE_OUT_FILE,
    CONST_ROADMAP_STAGE_PLAN_PATCH_FILE,
)
from devops_cli.exceptions import RoadmapStageError
from devops_cli.exceptions.roadmap import PhaseOutputError
from devops_cli.roadmap.attempt_kill import AttemptKill, AttemptKilled
from devops_cli.roadmap.phases.files import RunFolders
from devops_cli.roadmap.stage.stage_job_phases import (
    StageEnd,
    StageOutcome,
    prepare_stage_job,
    run_stage_agent,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.github_identity import fail_the_github_lookup
from tests.support.model_script import ModelScript, say, tool_call
from tests.support.roadmap_stage import STAGE_REPO, StageRepo, seed_stageable

pytestmark = pytest.mark.usefixtures("keyring_store")

CHANGE = "1-the-job-drops-a-comment"
ROOT = f"openspec/changes/{CHANGE}"
CANDIDATE = "# Keep the last comment\n\nThe job keeps it.\n"


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


def _prepared(
    store: InMemoryRoadmapStore, repo: StageRepo, tmp_path: Path, *, now: datetime | None = None
) -> RunFolders:
    folders = RunFolders(tmp_path / "run").make()
    number = seed_stageable(store)
    run = prepare_stage_job(
        store, folders, repo=STAGE_REPO, item=number, source=repo.clone, now=now
    )
    assert run is None
    return folders


def _agent(folders: RunFolders, script: ModelScript) -> StageOutcome | None:
    """The agent phase on `folders`, in a process with no GitHub login, as its container is."""
    with pytest.MonkeyPatch.context() as patch:
        fail_the_github_lookup(patch)
        return run_stage_agent(folders, model=script.model())


def _clone(folders: RunFolders) -> Path:
    return folders.work / CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME


@pytest.mark.parametrize("name", CONST_GITHUB_AGENT_REFUSED_ENV)
def test_a_credential_in_the_environment_is_refused_before_any_model_call(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    folders = _prepared(store, stage_repo, tmp_path)
    monkeypatch.setenv(name, "secret-value-1")
    script = ModelScript(say("done"))

    with pytest.raises(RoadmapStageError, match=name):
        _agent(folders, script)

    assert (script.seen, folders.out.exists()) == ([], False)


def test_a_gh_login_is_refused_before_any_model_call(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, tmp_path: Path
) -> None:
    """The test floor gives the process a GitHub login with no token variable."""
    folders = _prepared(store, stage_repo, tmp_path)
    script = ModelScript(say("done"))

    with pytest.raises(RoadmapStageError, match="finds a GitHub login"):
        run_stage_agent(folders, model=script.model())

    assert (script.seen, folders.out.exists()) == ([], False)


def test_an_output_folder_that_is_there_is_refused_before_any_model_call(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, tmp_path: Path
) -> None:
    folders = _prepared(store, stage_repo, tmp_path)
    folders.out.mkdir()
    script = ModelScript(say("done"))

    with pytest.raises(PhaseOutputError, match="output folder of the run is there"):
        _agent(folders, script)

    assert (script.seen, list(folders.out.iterdir())) == ([], [])


def test_an_edit_with_no_check_ends_unverified_and_hands_over_the_patch(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, tmp_path: Path
) -> None:
    folders = _prepared(store, stage_repo, tmp_path, now=datetime.now(UTC))
    script = ModelScript(
        tool_call("write_file", path=f"{ROOT}/design.md", content="# Design\n\nKept.\n"),
        say("done"),
    )

    outcome = _agent(folders, script)

    assert outcome is not None
    assert (outcome.end, outcome.failed) == (StageEnd.UNVERIFIED, ())
    assert (outcome.requests, outcome.tool_calls) == (3, 1)
    patch = (folders.out / CONST_ROADMAP_STAGE_PLAN_PATCH_FILE).read_text(encoding="utf-8")
    assert f"b/{ROOT}/design.md" in patch
    assert (
        StageOutcome.model_validate_json(
            (folders.out / CONST_ROADMAP_PHASE_OUTCOME_FILE).read_bytes()
        )
        == outcome
    )


def test_a_script_that_writes_a_plan_file_ends_the_run_and_the_patch_holds_the_file(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, tmp_path: Path
) -> None:
    """The effect stands in for `python3 <file>` in the shell of the agent: a command that no edit
    pattern of `RequireVerification` matches, so the run records no edit."""
    folders = _prepared(store, stage_repo, tmp_path, now=datetime.now(UTC))
    clone = _clone(folders)

    def script_run() -> None:
        (clone / ROOT / "design.md").write_text("# Design\n\nKept.\n", encoding="utf-8")
        (clone / "PLAN_PULL_REQUEST.md").write_text(CANDIDATE, encoding="utf-8")

    outcome = _agent(folders, ModelScript(say("done"), effects={1: script_run}))

    assert outcome is not None
    assert (outcome.end, outcome.requests) == (StageEnd.ENDED, 1)
    patch = (folders.out / CONST_ROADMAP_STAGE_PLAN_PATCH_FILE).read_text(encoding="utf-8")
    assert f"b/{ROOT}/design.md" in patch
    assert "PLAN_PULL_REQUEST.md" not in patch
    assert (folders.out / CONST_ROADMAP_STAGE_CANDIDATE_OUT_FILE).read_text(
        encoding="utf-8"
    ) == CANDIDATE


def test_an_agent_phase_past_its_time_budget_ends_in_timeout_with_no_model_call(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, tmp_path: Path
) -> None:
    folders = _prepared(store, stage_repo, tmp_path, now=datetime(2026, 11, 13, 12, tzinfo=UTC))
    script = ModelScript(say("done"))

    outcome = _agent(folders, script)

    assert outcome is not None
    assert (outcome.end, outcome.requests, script.seen) == (StageEnd.TIMEOUT, 0, [])


def test_a_sigterm_ends_the_phase_with_its_class_and_no_check_in(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, tmp_path: Path
) -> None:
    folders = _prepared(store, stage_repo, tmp_path, now=datetime.now(UTC))
    record = dict(store.item(1).job_record) if store.item(1) is not None else {}
    script = ModelScript(say("done"), effects={1: lambda: os.kill(os.getpid(), signal.SIGTERM)})

    with pytest.raises(AttemptKilled) as killed:
        _agent(folders, script)

    assert (killed.value.kill, killed.value.exit_status) == (AttemptKill.EVICTED, 75)
    item = store.item(1)
    assert item is not None
    assert dict(item.job_record) == record
    assert not (folders.out / CONST_ROADMAP_PHASE_OUTCOME_FILE).exists()


def test_a_run_folder_that_prepare_ended_gets_no_output(tmp_path: Path) -> None:
    folders = RunFolders(tmp_path / "run").make()

    assert _agent(folders, ModelScript(say("done"))) is None
    assert not folders.out.exists()
