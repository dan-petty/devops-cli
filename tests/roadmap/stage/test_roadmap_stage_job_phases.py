"""The stage Job on the phases `prepare`, `agent` and `publish` of one run folder (#6813).

`run_stage_job` runs the three phases in one process, as `--phase all` does. A run of each phase in
turn on one run folder pushes the same plan commit and opens the same plan pull request. The agent
phase holds the model key only, and `publish` reads the files of the run as data, as the phases
of the implement and fix-checks jobs do (#3702, #6601).
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.config.constants import (
    CONST_GITHUB_AGENT_REFUSED_ENV,
    CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
    CONST_ROADMAP_PHASE_OUTCOME_FILE,
    CONST_ROADMAP_PHASE_STATE_FILE,
)
from devops_cli.exceptions import RoadmapStageError
from devops_cli.exceptions.roadmap import PhaseOutputError
from devops_cli.roadmap.phases.files import RunFolders
from devops_cli.roadmap.stage.stage_job import (
    StageJobExit,
    prepare_stage_job,
    publish_stage_job,
    recorded_check_in,
    run_stage_agent,
    run_stage_job,
)
from devops_cli.roadmap.stores.store import ItemField, StageRecordKey
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    no_findings,
    seed_stageable,
    validate_args,
)

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

Cli = Callable[..., Any]

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
JOB = "devops-cli-stage-roadmap-1-0123456789"
BRANCH = "fix/1-the-job-drops-a-comment"
PULLS = f"/repos/{STAGE_REPO}/pulls"
OPENED = github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201)


@pytest.fixture(autouse=True)
def valid_openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    openspec_fake.script_sequence(validate_args("1-the-job-drops-a-comment"), (0, VALID_REPORT))
    return openspec_fake


@pytest.fixture
def job(github_api: GitHubApiFake, config: Callable[..., Path]) -> str:
    """The stage Job that this pod runs, and GitHub, which opens each plan pull request."""
    config(roadmap={"stage": {"job": JOB}})
    github_api.route("POST", PULLS, OPENED, OPENED)
    return JOB


def _stageable(store: InMemoryRoadmapStore) -> int:
    """One Ready bug that the Service checked out for the Job `JOB`."""
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
    return number


def _published(
    store: InMemoryRoadmapStore, repo: StageRepo, github_api: GitHubApiFake, number: int
) -> tuple[Any, ...]:
    """What a run published for item `number`: the tree, the author and the message of the plan
    commit, the request that opened the plan pull request, the record of the item, and the
    comments of the item and of the pull request."""
    item = store.item(number)
    assert item is not None
    check_in = recorded_check_in(item)
    opened = [r for r in github_api.sent if r.method == "POST" and r.url.path == PULLS]
    record = {key: item.job_record.get(key) for key in (StageRecordKey.PR, StageRecordKey.BRANCH)}
    return (
        repo.origin_git("rev-parse", f"{BRANCH}^{{tree}}"),
        repo.origin_git("log", "-1", "--format=%an <%ae>%n%B", BRANCH),
        json.loads(opened[-1].content),
        record,
        None if check_in is None else check_in.result,
        [comment.body for comment in store.comments_on(number)],
        [comment.body for comment in store.comments_on(5)],
    )


def _phases_in_turn(
    store: InMemoryRoadmapStore, repo: StageRepo, folders: RunFolders, number: int
) -> Any:
    """`prepare`, `agent` and `publish` of item `number`, each in turn on the run folder
    `folders`, as the three containers of a Job run them."""
    assert (
        prepare_stage_job(store, folders, repo=STAGE_REPO, item=number, source=repo.clone, now=NOW)
        is None
    )
    run_stage_agent(folders, now=NOW)
    return publish_stage_job(
        store, folders, repo=STAGE_REPO, item=number, source=repo.clone, now=NOW
    )


def test_the_phases_in_turn_on_one_run_folder_publish_the_plan_of_phase_all(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    job: str,
    tmp_path: Path,
) -> None:
    together = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = _stageable(together)
    model_fake.answer(make_stage_proposal())
    all_run = run_stage_job(
        together, repo=STAGE_REPO, item=number, source=stage_repo.clone, now=NOW
    )
    expected = _published(together, stage_repo, github_api, number)
    stage_repo.origin_git("branch", "-q", "-D", BRANCH)

    apart = InMemoryRoadmapStore(repo=STAGE_REPO)
    assert _stageable(apart) == number
    model_fake.answer(make_stage_proposal())
    run = _phases_in_turn(apart, stage_repo, RunFolders(tmp_path / "run"), number)

    assert (
        (run.exit_code, run.result)
        == (all_run.exit_code, all_run.result)
        == (
            StageJobExit.RESULT,
            "staged",
        )
    )
    assert _published(apart, stage_repo, github_api, number) == expected


@pytest.mark.parametrize("name", CONST_GITHUB_AGENT_REFUSED_ENV)
def test_the_agent_phase_refuses_to_start_with_the_app_key_or_a_github_token(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    job: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = _stageable(store)
    folders = RunFolders(tmp_path / "run")
    prepare_stage_job(
        store, folders, repo=STAGE_REPO, item=number, source=stage_repo.clone, now=NOW
    )
    monkeypatch.setenv(name, "held")

    with pytest.raises(RoadmapStageError, match=name):
        run_stage_agent(folders, now=NOW)

    assert (folders.out.exists(), model_fake.sent) == (False, [])


def test_the_agent_phase_refuses_an_output_folder_that_is_there_before_its_outputs(
    stage_repo: StageRepo, model_fake: ModelFake, job: str, tmp_path: Path
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = _stageable(store)
    folders = RunFolders(tmp_path / "run")
    prepare_stage_job(
        store, folders, repo=STAGE_REPO, item=number, source=stage_repo.clone, now=NOW
    )
    folders.out.mkdir()

    with pytest.raises(PhaseOutputError, match="output folder of the run is there"):
        run_stage_agent(folders, now=NOW)

    assert (os.listdir(folders.out), model_fake.sent) == ([], [])


def _link_outcome(folders: RunFolders) -> None:
    outcome = folders.out / CONST_ROADMAP_PHASE_OUTCOME_FILE
    (folders.root / "other.json").write_bytes(outcome.read_bytes())
    outcome.unlink()
    outcome.symlink_to(folders.root / "other.json")


def _fifo_outcome(folders: RunFolders) -> None:
    outcome = folders.out / CONST_ROADMAP_PHASE_OUTCOME_FILE
    outcome.unlink()
    os.mkfifo(outcome)


def _long_outcome(folders: RunFolders) -> None:
    outcome = folders.out / CONST_ROADMAP_PHASE_OUTCOME_FILE
    outcome.write_bytes(b" " * (CONST_ROADMAP_PHASE_JSON_MAX_BYTES + 1))


def _link_state(folders: RunFolders) -> None:
    state = folders.state / CONST_ROADMAP_PHASE_STATE_FILE
    (folders.root / "other.json").write_bytes(state.read_bytes())
    state.unlink()
    state.symlink_to(folders.root / "other.json")


def _file_outside_the_change(folders: RunFolders) -> None:
    outcome = folders.out / CONST_ROADMAP_PHASE_OUTCOME_FILE
    data = json.loads(outcome.read_bytes())
    data["planned"]["ready"][0]["files"]["src/devops_cli/sample.py"] = "print('the agent')\n"
    outcome.write_text(json.dumps(data), encoding="utf-8")


def _not_of_the_model(folders: RunFolders) -> None:
    outcome = folders.out / CONST_ROADMAP_PHASE_OUTCOME_FILE
    outcome.write_text(json.dumps({"end": "planned", "extra": 1}), encoding="utf-8")


@pytest.mark.parametrize(
    ("tamper", "refusal"),
    [
        pytest.param(_link_outcome, "Cannot open the file `outcome.json`", id="outcome-link"),
        pytest.param(_fifo_outcome, "`outcome.json` is not a regular file", id="outcome-fifo"),
        pytest.param(_long_outcome, "`outcome.json` holds more than", id="outcome-over-limit"),
        pytest.param(_not_of_the_model, "is not of its model", id="outcome-not-of-model"),
        pytest.param(_file_outside_the_change, "outside its folder", id="file-outside-change"),
        pytest.param(_link_state, "Cannot open the file `state.json`", id="state-link"),
    ],
)
def test_publish_reads_only_the_files_of_the_run_as_data(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    job: str,
    tmp_path: Path,
    tamper: Callable[[RunFolders], None],
    refusal: str,
) -> None:
    """The agent phase can write each file of a run folder that it shares with `publish`, so
    `publish` refuses a link, a FIFO, a file over its limit, an outcome that is not of its model
    and a change with a file outside its change folder, and pushes nothing."""
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = _stageable(store)
    folders = RunFolders(tmp_path / "run")
    model_fake.answer(make_stage_proposal())
    prepare_stage_job(
        store, folders, repo=STAGE_REPO, item=number, source=stage_repo.clone, now=NOW
    )
    run_stage_agent(folders, now=NOW)
    tamper(folders)

    with pytest.raises(PhaseOutputError, match=re.escape(refusal)):
        publish_stage_job(
            store, folders, repo=STAGE_REPO, item=number, source=stage_repo.clone, now=NOW
        )

    pushed = stage_repo.origin_git("branch", "--format=%(refname:short)").split()
    assert (pushed, [r for r in github_api.sent if r.method == "POST"]) == (["main"], [])


def test_publish_refuses_the_state_file_of_another_item(
    stage_repo: StageRepo, model_fake: ModelFake, job: str, tmp_path: Path
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = _stageable(store)
    other = _stageable(store)
    folders = RunFolders(tmp_path / "run")
    model_fake.answer(make_stage_proposal())
    prepare_stage_job(
        store, folders, repo=STAGE_REPO, item=number, source=stage_repo.clone, now=NOW
    )
    run_stage_agent(folders, now=NOW)

    with pytest.raises(PhaseOutputError, match="another item"):
        publish_stage_job(
            store, folders, repo=STAGE_REPO, item=other, source=stage_repo.clone, now=NOW
        )


def test_a_prepare_that_ends_the_run_gives_publish_its_end(
    stage_repo: StageRepo, model_fake: ModelFake, job: str, tmp_path: Path
) -> None:
    """An item that the round leaves out ends in `prepare`, which checks in and writes the end in
    the state file. The agent phase then plans nothing, and `publish` ends with the same end and
    writes nothing more."""
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = _stageable(store)
    item = store.item(number)
    assert item is not None
    store.set_field(item, ItemField.STATUS, "New")
    folders = RunFolders(tmp_path / "run")

    prepared = prepare_stage_job(
        store, folders, repo=STAGE_REPO, item=number, source=stage_repo.clone, now=NOW
    )
    run_stage_agent(folders, now=NOW)
    published = publish_stage_job(
        store, folders, repo=STAGE_REPO, item=number, source=stage_repo.clone, now=NOW
    )

    assert prepared is not None
    assert (
        (prepared.exit_code, prepared.result)
        == (published.exit_code, published.result)
        == (
            StageJobExit.RESULT,
            "skipped",
        )
    )
    assert (folders.out.exists(), model_fake.sent) == (False, [])


def test_an_agent_phase_past_its_time_budget_ends_in_the_deadline_of_publish(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    job: str,
    tmp_path: Path,
    config: Callable[..., Path],
) -> None:
    """The agent phase reads the time that is left at its own start. With none left, it plans
    nothing and writes the deadline end, and `publish` checks in with the deadline, as a stage Job
    in one process does."""
    config(roadmap={"stage": {"job": JOB, "job_deadline": (NOW + timedelta(hours=1)).isoformat()}})
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = _stageable(store)
    folders = RunFolders(tmp_path / "run")
    prepare_stage_job(
        store, folders, repo=STAGE_REPO, item=number, source=stage_repo.clone, now=NOW
    )

    run_stage_agent(folders, now=NOW + timedelta(hours=2))
    run = publish_stage_job(
        store, folders, repo=STAGE_REPO, item=number, source=stage_repo.clone, now=NOW
    )

    item = store.item(number)
    assert item is not None
    check_in = recorded_check_in(item)
    assert check_in is not None
    assert (run.exit_code, check_in.result, model_fake.sent) == (
        StageJobExit.DEADLINE,
        "deadline",
        [],
    )


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(("--job-item", "1", "--confirm", "--phase", "agent"), id="no-work"),
        pytest.param(("--job-item", "1", "--phase", "prepare", "--work", "run"), id="no-confirm"),
        pytest.param(("--confirm", "--phase", "publish", "--work", "run"), id="no-job-item"),
    ],
)
def test_a_phase_of_the_stage_job_needs_its_job_item_confirm_and_a_run_folder(
    cli: Cli, args: tuple[str, ...]
) -> None:
    result = cli("roadmap", "stage", "--repo", STAGE_REPO, *args)

    assert (result.exit_code, "--work" in result.output) == (1, True)


def test_each_phase_of_the_cli_runs_in_turn_on_one_run_folder(
    cli: Cli,
    roadmap_store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    job: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each phase clears the dumpable flag of its process first, as the phases of the implement
    job do (#3702). The spy replaces the kernel call, which would change the test run. `prepare`
    hands the run on with exit 0, and `publish` ends with the exit code of the end."""
    from devops_cli.core import process_hardening

    seen: list[str] = []
    monkeypatch.setattr(
        process_hardening, "deny_environment_reads", lambda: seen.append("unreadable")
    )
    number = _stageable(roadmap_store)
    no_findings(model_fake)
    model_fake.answer(make_stage_proposal())
    base = (
        "roadmap",
        "stage",
        "--repo",
        STAGE_REPO,
        "--source",
        str(stage_repo.clone),
        "--job-item",
        str(number),
        "--confirm",
        "--work",
        str(tmp_path / "run"),
    )

    codes = [cli(*base, "--phase", phase).exit_code for phase in ("prepare", "agent", "publish")]

    item = roadmap_store.item(number)
    assert item is not None
    assert (codes, seen, item.job_record.get(StageRecordKey.PR)) == (
        [0, 0, 0],
        ["unreadable"] * 3,
        "5",
    )
