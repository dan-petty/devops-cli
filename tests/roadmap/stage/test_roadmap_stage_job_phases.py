"""The stage Job on the phases `prepare`, `agent` and `publish` of one run folder (#6813).

`run_stage_job` runs the three phases in one process, as `--phase all` does. A run of each phase in
turn on one run folder pushes the same plan commit and opens the same plan pull request. The agent
phase holds the model key only, and `publish` reads the files of the run as data, as the phases
of the implement and fix-checks jobs do (#3702, #6601).
"""

from __future__ import annotations

import ctypes
import ctypes.util
import json
import logging
import os
import re
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import TypeAdapter

from devops_cli.config.constants import (
    CONST_GITHUB_AGENT_REFUSED_ENV,
    CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
    CONST_ROADMAP_PHASE_OUTCOME_FILE,
    CONST_ROADMAP_PHASE_STATE_FILE,
)
from devops_cli.exceptions import GitHubOperationError, RoadmapStageError
from devops_cli.exceptions.roadmap import PhaseOutputError
from devops_cli.roadmap.agent_run import RunTrace, ToolCallRecord
from devops_cli.roadmap.phases.files import RunFolders
from devops_cli.roadmap.stage.stage_change import pull_request_body, staging_title
from devops_cli.roadmap.stage.stage_job import (
    StageJobExit,
    prepare_stage_job,
    publish_stage_job,
    recorded_check_in,
    run_stage_agent,
    run_stage_job,
)
from devops_cli.roadmap.stage.stage_job_phases import HandedTrace
from devops_cli.roadmap.stage.stage_verify import (
    DefectType,
    Finding,
    Locator,
    PlanPart,
    Severity,
)
from devops_cli.roadmap.stores.store import ItemField, StageRecordKey
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.github_identity import fail_the_github_lookup
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    no_findings,
    seed_stageable,
    validate_args,
    validation_report,
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
CHANGE = "1-the-job-drops-a-comment"
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


def _agent(folders: RunFolders, *, now: datetime = NOW) -> None:
    """The agent phase on `folders`, in a process with no GitHub login, as its container is."""
    with pytest.MonkeyPatch.context() as patch:
        fail_the_github_lookup(patch)
        run_stage_agent(folders, now=now)


def _outcome(folders: RunFolders) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((folders.out / CONST_ROADMAP_PHASE_OUTCOME_FILE).read_bytes())
    return data


def _write_outcome(folders: RunFolders, data: dict[str, Any]) -> None:
    (folders.out / CONST_ROADMAP_PHASE_OUTCOME_FILE).write_text(json.dumps(data), encoding="utf-8")


def _phases_in_turn(
    store: InMemoryRoadmapStore, repo: StageRepo, folders: RunFolders, number: int
) -> Any:
    """`prepare`, `agent` and `publish` of item `number`, each in turn on the run folder
    `folders`, as the three containers of a Job run them."""
    assert (
        prepare_stage_job(store, folders, repo=STAGE_REPO, item=number, source=repo.clone, now=NOW)
        is None
    )
    _agent(folders)
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


@pytest.mark.parametrize("apart", [False, True], ids=["phase-all", "phase-prepare"])
def test_a_failed_github_read_for_the_agent_is_a_failure_of_the_item(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    job: str,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    apart: bool,
) -> None:
    """`prepare` reads the comments of the item, the titles of its dependencies and the paths of
    the open plans for the agent phase. A GitHub error of these reads is a failure of the item, as
    it is in the plan: the record holds its class and its step, the log names the failed item, and
    the Job exits 75, so the pod runs again after the wait of the class."""
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = _stageable(store)
    store.fail_read("comments_on", GitHubOperationError("HTTP 502"))

    with caplog.at_level(logging.INFO, logger="devops_cli.roadmap.round_log"):
        if apart:
            run = prepare_stage_job(
                store,
                RunFolders(tmp_path / "run"),
                repo=STAGE_REPO,
                item=number,
                source=stage_repo.clone,
                now=NOW,
            )
        else:
            run = run_stage_job(
                store, repo=STAGE_REPO, item=number, source=stage_repo.clone, now=NOW
            )

    item = store.item(number)
    assert item is not None
    assert run is not None
    assert (
        run.exit_code,
        run.plan is not None,
        item.job_record.get(StageRecordKey.FAILED_CLASS),
        item.job_record.get(StageRecordKey.FAILED_STEP),
        model_fake.sent,
    ) == (StageJobExit.EVICTED, True, "ci_infra", "plan", [])
    assert [m for m in caplog.messages if "stage item failed" in m and "class=ci_infra" in m]


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
        _agent(folders)

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
        _agent(folders)

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


def _with_plan(change: Callable[[dict[str, Any]], None]) -> Callable[[RunFolders], None]:
    """A tamper that changes the plan that the outcome hands over."""

    def tamper(folders: RunFolders) -> None:
        data = _outcome(folders)
        change(data["result"]["plan"])
        _write_outcome(folders, data)

    return tamper


def _with_result(result: dict[str, Any]) -> Callable[[RunFolders], None]:
    """A tamper that hands over `result` in place of the result of the plan."""

    def tamper(folders: RunFolders) -> None:
        data = _outcome(folders)
        data["result"] = {**result, "attempt": data["result"]["attempt"]}
        _write_outcome(folders, data)

    return tamper


def _deep_outcome(folders: RunFolders) -> None:
    (folders.out / CONST_ROADMAP_PHASE_OUTCOME_FILE).write_bytes(b"[" * 200_000)


def _two_kinds(folders: RunFolders) -> None:
    data = _outcome(folders)
    data["result"]["blocked"] = ["src/devops_cli/sample.py"]
    _write_outcome(folders, data)


_GROUP_IN_BUDGET = {
    "group": make_stage_proposal().groups[0].model_dump(mode="json"),
    "tokens": 1,
    "files": 0,
}


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
        pytest.param(_deep_outcome, "is not of its model", id="outcome-deep"),
        pytest.param(_link_state, "Cannot open the file `state.json`", id="state-link"),
        pytest.param(
            _with_plan(lambda plan: plan.update(title="docs: Release-As: 9.9.9")),
            "is not of its model",
            id="plan-title",
        ),
        pytest.param(
            _with_plan(lambda plan: plan.update(files={"conftest.py": "import os\n"})),
            "is not of its model",
            id="plan-files",
        ),
        pytest.param(
            _with_plan(
                lambda plan: plan["proposal"].update(pull_request_body="Closes #2 at once.")
            ),
            "A check of the plan refuses it",
            id="plan-closing-keyword",
        ),
        pytest.param(
            _with_result({"blocked": ["src/devops_cli/sample.py"]}),
            "names no path that an open plan creates",
            id="blocked-no-open-plan",
        ),
        pytest.param(
            _with_result({"over_budget": [_GROUP_IN_BUDGET]}),
            "holds no group over the budget",
            id="stop-in-budget",
        ),
        pytest.param(_two_kinds, "is not of its model", id="two-kinds"),
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
    """`publish` reads each file of the run as data, and builds the result from the state of
    `prepare` and what the model made. It refuses a link, a FIFO, a file over its limit, an
    outcome that is not of its model, a plan that a check refuses, a return whose paths no open
    plan creates and a stop with no group over the budget, and pushes nothing."""
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = _stageable(store)
    folders = RunFolders(tmp_path / "run")
    model_fake.answer(make_stage_proposal())
    prepare_stage_job(
        store, folders, repo=STAGE_REPO, item=number, source=stage_repo.clone, now=NOW
    )
    _agent(folders)
    tamper(folders)

    with pytest.raises(PhaseOutputError, match=re.escape(refusal)):
        publish_stage_job(
            store, folders, repo=STAGE_REPO, item=number, source=stage_repo.clone, now=NOW
        )

    pushed = stage_repo.origin_git("branch", "--format=%(refname:short)").split()
    assert (pushed, [r for r in github_api.sent if r.method == "POST"]) == (["main"], [])


def _prepared(store: InMemoryRoadmapStore, repo: StageRepo, folders: RunFolders) -> int:
    """`prepare` of a stageable item on `folders`, and its number."""
    number = _stageable(store)
    prepare_stage_job(store, folders, repo=STAGE_REPO, item=number, source=repo.clone, now=NOW)
    return number


def _publish(store: InMemoryRoadmapStore, repo: StageRepo, folders: RunFolders, number: int) -> Any:
    return publish_stage_job(
        store, folders, repo=STAGE_REPO, item=number, source=repo.clone, now=NOW
    )


def _texts(store: InMemoryRoadmapStore, number: int) -> list[str]:
    """The comments of item `number` and of its plan pull request 5."""
    return [comment.body for n in (number, 5) for comment in store.comments_on(n)]


def test_the_agent_phase_refuses_to_start_with_a_gh_login(
    stage_repo: StageRepo, model_fake: ModelFake, job: str, tmp_path: Path
) -> None:
    """The test floor gives the process a GitHub login with no token variable, and the token
    lookup of the session finds it."""
    folders = RunFolders(tmp_path / "run")
    _prepared(InMemoryRoadmapStore(repo=STAGE_REPO), stage_repo, folders)

    with pytest.raises(RoadmapStageError, match="finds a GitHub login"):
        run_stage_agent(folders, now=NOW)

    assert (folders.out.exists(), model_fake.sent) == (False, [])


def test_publish_builds_the_texts_of_the_plan_as_phase_all_does(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    job: str,
    tmp_path: Path,
) -> None:
    """`publish` builds the title and the body of the draft from the proposal, as the planner does
    after the model answers, and writes each other text of the agent phase as `safe_text` writes
    it: on one line, with a handle in a code span. The review findings are the review of the agent
    phase, and the person who reviews the plan pull request checks them."""
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    folders = RunFolders(tmp_path / "run")
    proposal = make_stage_proposal()
    model_fake.answer(proposal)
    number = _prepared(store, stage_repo, folders)
    _agent(folders)
    finding = Finding(
        type=DefectType.CRITERION_DROPPED,
        severity=Severity.MAJOR,
        where=Locator(part=PlanPart.ISSUE, section="@someone\n\nsection"),
        problem="@someone\n\nlook",
    ).model_dump(mode="json")
    _with_plan(
        lambda plan: plan.update(
            text="Closes #2 and cc @someone",
            warnings=["@someone\n\nlook"],
            comments=["@someone"],
            findings=[finding],
            open_findings=[finding],
        )
    )(folders)

    _publish(store, stage_repo, folders, number)

    opened = [json.loads(r.content) for r in github_api.sent if r.url.path == PULLS]
    texts = _texts(store, number)
    assert [(pull["title"], pull["body"]) for pull in opened] == [
        (
            staging_title(number, proposal.summary),
            pull_request_body(number, CHANGE, proposal.pull_request_body),
        )
    ]
    assert (
        any("`@someone`" in text for text in texts),
        [text for text in texts if re.search(r"(?<!`)@someone|@someone\n", text)],
    ) == (True, [])


def test_publish_runs_the_checks_of_the_files(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    job: str,
    tmp_path: Path,
    openspec_fake: OpenSpecFake,
) -> None:
    """`publish` validates the change folder that it renders: a refusal of `openspec validate` in
    `publish` refuses the plan, and nothing is pushed."""
    openspec_fake.script_sequence(
        validate_args(CHANGE),
        (0, VALID_REPORT),
        (1, validation_report(("ERROR", "The requirement has no scenario"), valid=False)),
    )
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    folders = RunFolders(tmp_path / "run")
    model_fake.answer(make_stage_proposal())
    number = _prepared(store, stage_repo, folders)
    _agent(folders)

    with pytest.raises(PhaseOutputError, match="A check of the plan refuses it"):
        _publish(store, stage_repo, folders, number)

    assert [r for r in github_api.sent if r.method == "POST"] == []


def test_a_false_premise_of_the_agent_phase_comes_on_one_line(
    stage_repo: StageRepo, model_fake: ModelFake, job: str, tmp_path: Path
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    folders = RunFolders(tmp_path / "run")
    model_fake.answer(make_stage_proposal())
    number = _prepared(store, stage_repo, folders)
    _agent(folders)
    _with_result({"premise": {"evidence": ["@someone says the field\n\nis absent"]}})(folders)

    run = _publish(store, stage_repo, folders, number)

    texts = _texts(store, number)
    assert (run.result, any("`@someone` says the field is absent" in t for t in texts)) == (
        "skipped",
        True,
    )


def test_a_plan_with_200_full_searches_publishes(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    job: str,
    tmp_path: Path,
) -> None:
    """The trace that the agent phase hands over keeps the tool, the argument and the outcome of
    each call, and no answer and no match: a plan run with many full searches fits the outcome,
    and `publish` opens its draft. The whole trace of these 200 searches holds more than the limit
    of the outcome."""
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    folders = RunFolders(tmp_path / "run")
    model_fake.answer(make_stage_proposal())
    number = _prepared(store, stage_repo, folders)
    _agent(folders)
    matches = tuple(f"src/devops_cli/roadmap/stage/stage.py:{line}" for line in range(150))
    trace = RunTrace(
        tool_calls=[
            ToolCallRecord(
                "search_code", json.dumps({"pattern": f"keep_{n}"}), chars=6000, matches=matches
            )
            for n in range(200)
        ],
        requests=200,
        offered=[("search_code",)] * 200,
    )
    data = _outcome(folders)
    data["result"]["plan"]["trace"] = HandedTrace.of(trace).model_dump(mode="json")
    _write_outcome(folders, data)

    run = _publish(store, stage_repo, folders, number)

    outcome = (folders.out / CONST_ROADMAP_PHASE_OUTCOME_FILE).stat().st_size
    assert (
        len(TypeAdapter(RunTrace).dump_json(trace)) > CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
        outcome <= CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
        run.result,
        len([r for r in github_api.sent if r.url.path == PULLS]),
    ) == (True, True, "staged", 1)


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
    _agent(folders)

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
    _agent(folders)
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
    item = store.item(number)
    assert item is not None
    check_in = recorded_check_in(item)
    assert check_in is not None
    assert (check_in.job, check_in.result, folders.out.exists(), model_fake.sent) == (
        JOB,
        "skipped",
        False,
        [],
    )


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

    _agent(folders, now=NOW + timedelta(hours=2))
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


# `PR_SET_DUMPABLE` of <linux/prctl.h>, and the C library of glibc on Linux.
PR_SET_DUMPABLE = 4
LIBC = "libc.so.6"


class _Libc:
    """A C library of the process whose `prctl` the test records and does not call: the edge of
    the hardening of a phase. Each other name is the name of the real library."""

    def __init__(self, library: Any, calls: list[tuple[int, ...]]) -> None:
        self._library = library
        self._calls = calls

    def prctl(self, *args: int) -> int:
        self._calls.append(args)
        return 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._library, name)


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


@pytest.mark.skipif(sys.platform != "linux", reason="prctl is Linux only")
def test_each_phase_of_the_cli_runs_in_turn_on_one_run_folder(
    cli: Cli,
    roadmap_store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    job: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each phase clears the dumpable flag of its process, as the phases of the implement job do
    (#3702). The C library of the test records the `prctl` call and makes no kernel call, which
    would change the test run. `prepare` hands the run on with exit 0, and `publish` ends with the
    exit code of the end."""
    calls: list[tuple[int, ...]] = []
    loaded = ctypes.CDLL
    # `find_library` starts `ldconfig`, so the test names the C library of the platform itself.
    monkeypatch.setattr(ctypes.util, "find_library", lambda _name: LIBC)
    monkeypatch.setattr(
        ctypes, "CDLL", lambda *args, **kwargs: _Libc(loaded(*args, **kwargs), calls)
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

    codes = [cli(*base, "--phase", "prepare").exit_code]
    with pytest.MonkeyPatch.context() as patch:
        fail_the_github_lookup(patch)
        codes.append(cli(*base, "--phase", "agent").exit_code)
    codes.append(cli(*base, "--phase", "publish").exit_code)

    item = roadmap_store.item(number)
    assert item is not None
    assert (codes, calls, item.job_record.get(StageRecordKey.PR)) == (
        [0, 0, 0],
        [(PR_SET_DUMPABLE, 0, 0, 0, 0)] * 3,
        "5",
    )
