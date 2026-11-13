"""`devops roadmap stage`: the plan that passes the gates is kept as a file with a key of its input,
and a rerun or `--confirm` reads it back instead of asking the planner again (#4064)."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, cast

import pytest

from devops_cli.ai.client.models import AIClientError
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.settings import RoadmapStageConfig
from devops_cli.exceptions import ServiceStoppingError, ended_by_stop
from devops_cli.exceptions.roadmap import RoadmapStageError
from devops_cli.roadmap.service_stop import begin_service_stop
from devops_cli.roadmap.stage import stage as stage_module
from devops_cli.roadmap.stage import stage_plan_record
from devops_cli.roadmap.stage.stage import StagePlan, parse_filters, plan_item, plan_stage
from devops_cli.roadmap.stage.stage_plan_record import (
    StagePlanRecord,
    plan_key,
    plan_record_path,
    prompt_version,
    read_plan_record,
    refused_record_path,
    write_plan_record,
)
from devops_cli.roadmap.stage.stage_request import StageRequest
from devops_cli.roadmap.stage.stage_toolbox import ToolboxClient, ToolboxModel
from devops_cli.roadmap.stage.stage_verify import Verification
from devops_cli.telemetry.instruments import ROADMAP_STAGE_PLAN_RECORD_TOTAL
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json
from tests.support.fakes.model import ModelFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    apply_stage,
    seed_stageable,
    validate_args,
)
from tests.support.scripted_model import Script, call

if TYPE_CHECKING:
    from pathlib import Path

    from devops_cli.roadmap.stage.stage import StageClient
    from devops_cli.roadmap.stage.stage_change import StageProposal
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.openspec import OpenSpecFake
    from tests.support.fakes.otlp import FakeCollector

pytestmark = pytest.mark.usefixtures("keyring_store")

BRANCH = "fix/1-the-job-drops-a-comment"
PULLS = f"/repos/{STAGE_REPO}/pulls"
OPENED = github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201)
SAMPLE = "src/devops_cli/sample.py"
MISSING = "tests/test_missing.py"
REFINE_START = "<!-- devops-roadmap-refine:start -->"
REFINE_END = "<!-- devops-roadmap-refine:end -->"
INPUT = {
    "number": 1,
    "title": "fix(roadmap): the job drops a comment",
    "body": "The job drops the last comment of a thread.",
    "model": "model-a",
    "toolset": "base",
    "prompt_version": "a" * 64,
}


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    seed_stageable(store)
    store.seed_file(
        ".github/labels.yml",
        '- name: "type/docs"\n  color: "0075ca"\n- name: "scope/openspec"\n  color: "0e8a16"\n',
    )
    for i in range(2, 5):
        store.seed_issue(f"placeholder {i}")
    store.seed_pull("staging PR", head_ref=BRANCH, draft=True)
    return store


@pytest.fixture(autouse=True)
def valid_openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    """OpenSpec, found, and valid about the change of #1 for every run of a test."""
    openspec_fake.script_sequence(
        validate_args("1-the-job-drops-a-comment"), *[(0, VALID_REPORT)] * 6
    )
    return openspec_fake


@pytest.fixture
def verifier() -> ModelFake:
    """The model edge of the verification task, apart from the model edge of the planner."""
    return ModelFake()


def _plan(
    store: InMemoryRoadmapStore, repo: StageRepo, *, verifier: ModelFake | None = None
) -> StagePlan:
    return plan_stage(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        filters=parse_filters(()),
        model=cast("StageClient | None", None),
        verifier=ToolboxModel(verifier) if verifier is not None else None,
    )


def _file() -> Path:
    """The plan file of #1."""
    return plan_record_path(STAGE_REPO, 1)


def _key_of_file() -> str:
    return str(json.loads(_file().read_text(encoding="utf-8"))["key"])


def _request() -> StageRequest:
    return StageRequest(
        number=1,
        title=cast("str", INPUT["title"]),
        body=cast("str", INPUT["body"]),
        context="The job reads comments.",
        capabilities=[],
        budget=40_000,
    )


def _record(key: str = "k" * 64) -> StagePlanRecord:
    return StagePlanRecord(key=key, proposal=make_stage_proposal(), request=_request())


# ── The key ───────────────────────────────────────────────────────────────────


def test_the_plan_key_is_a_sha256_that_the_same_input_gives_again() -> None:
    first = plan_key(**INPUT)  # type: ignore[arg-type]

    assert (len(first), first == plan_key(**INPUT)) == (64, True)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("number", 2),
        ("title", "fix(roadmap): another title"),
        ("body", "The job drops the first comment of a thread."),
        ("model", "model-b"),
        ("toolset", "extended"),
        ("prompt_version", "b" * 64),
    ],
)
def test_a_changed_input_gives_a_new_plan_key(name: str, value: object) -> None:
    changed: dict[str, Any] = {**INPUT, name: value}

    assert plan_key(**changed) != plan_key(**INPUT)  # type: ignore[arg-type]


def test_a_changed_refine_section_of_the_body_gives_a_new_plan_key() -> None:
    body = INPUT["body"]
    first = {**INPUT, "body": f"{body}\n{REFINE_START}\nOne note.\n{REFINE_END}"}
    second = {**INPUT, "body": f"{body}\n{REFINE_START}\nAnother note.\n{REFINE_END}"}

    assert plan_key(**first) != plan_key(**second)  # type: ignore[arg-type]


def test_the_prompt_version_follows_the_text_of_a_prompt_and_the_toolset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = prompt_version("base")
    monkeypatch.setattr(
        stage_plan_record, "load_task_prompt", lambda name: f"{load_task_prompt(name)}\nA new rule."
    )

    assert (len(base), base == prompt_version("base")) == (64, False)
    monkeypatch.undo()
    assert (base == prompt_version("base"), base == prompt_version("extended")) == (True, False)
    assert prompt_version("research") not in (prompt_version("base"), prompt_version("extended"))


# ── The file ──────────────────────────────────────────────────────────────────


def test_the_plan_file_of_an_item_is_under_the_stage_folder_of_the_data_directory(
    isolate_data_dir: Path,
) -> None:
    assert plan_record_path(STAGE_REPO, 1) == (
        isolate_data_dir / "roadmap" / "stage" / "example" / "roadmap" / "1.json"
    )


def test_a_written_plan_file_reads_back_and_leaves_no_temporary_file() -> None:
    path = _file()
    record = _record()

    write_plan_record(path, record)

    assert read_plan_record(path, record.key) == record
    assert [entry.name for entry in path.parent.iterdir()] == ["1.json"]


def test_a_missing_plan_file_reads_as_none() -> None:
    assert read_plan_record(_file(), "k" * 64) is None


def test_a_plan_file_of_another_key_reads_as_a_miss_whatever_else_it_holds() -> None:
    path = _file()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"key": "old", "proposal": "of a schema that is gone"}))

    assert read_plan_record(path, "k" * 64) is None


@pytest.mark.parametrize(
    "text",
    ["not json at all", "[]", "{}", '{"key": "kkkk"}'],
    ids=["not-json", "not-an-object", "no-key", "wrong-schema-with-the-key"],
)
def test_an_unreadable_plan_file_raises_an_error_that_names_the_file(text: str) -> None:
    path = _file()
    path.parent.mkdir(parents=True)
    path.write_text(text)

    with pytest.raises(RoadmapStageError) as raised:
        read_plan_record(path, "kkkk")

    assert str(path) in str(raised.value)


def test_an_unreadable_plan_file_fails_the_item_with_its_name_and_asks_the_planner_nothing(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    path = _file()
    path.parent.mkdir(parents=True)
    path.write_text("not json at all")
    model_fake.answer(make_stage_proposal())

    plan = _plan(store, stage_repo)

    (failure,) = plan.failed
    assert (plan.ready, failure.error, str(path) in failure.reason) == (
        (),
        "RoadmapStageError",
        True,
    )
    assert model_fake.call_count == 0


# ── The planner reads the file ────────────────────────────────────────────────


def test_a_failed_review_and_a_rerun_make_no_planner_request_on_the_rerun(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    model_fake.answer(make_stage_proposal())
    verifier.answer(AIClientError("the review model is down"))

    first = _plan(store, stage_repo, verifier=verifier)

    assert (first.ready, [f.number for f in first.failed], model_fake.call_count) == ((), [1], 1)
    assert _file().is_file()
    verifier.reset()
    verifier.answer(Verification())

    second = _plan(store, stage_repo, verifier=verifier)

    assert (len(second.ready), second.failed, model_fake.call_count) == (1, (), 1)
    assert verifier.call_count == 1


def test_a_plan_that_the_gates_refuse_twice_is_not_kept(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    group = make_stage_proposal().groups[0]
    bad = make_stage_proposal(
        groups=[group.model_copy(update={"changes": [*group.changes, "tests/test_missing.py"]})]
    )
    model_fake.answer(bad)

    plan = _plan(store, stage_repo)

    assert (plan.ready, len(plan.failed), _file().exists()) == ((), 1, False)


def _refused_reply(summary: str = "A plan that names a missing file") -> StageProposal:
    """A reply that the `paths` gate refuses on each try."""
    group = make_stage_proposal().groups[0]
    return make_stage_proposal(
        summary=summary,
        groups=[group.model_copy(update={"changes": [*group.changes, MISSING]})],
    )


def _keep_a_plan_that_the_gates_now_refuse() -> StageProposal:
    """Replace the kept plan of #1 with one that the gates refuse, as a moved commit does to the
    citations of a kept plan, and return it."""
    record = read_plan_record(_file(), _key_of_file())
    assert record is not None
    stale = _refused_reply("The kept plan")
    write_plan_record(_file(), record.model_copy(update={"proposal": stale}))
    return stale


def _gate_returns_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    """The fields of each `stage gate returns:` line, with the version cut off."""
    event = "stage gate returns: "
    return [
        r.getMessage().removeprefix(event).rsplit(" version=", 1)[0]
        for r in caplog.records
        if r.getMessage().startswith(event)
    ]


def test_a_kept_plan_that_the_gates_refuse_uses_no_gate_return(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The kept plan made no model request, and its gates ran on an older commit. So its refusal
    uses no return: the planner gets a new first reply and then all the returns of a refused
    reply, as an item with no kept plan does (#4950)."""
    model_fake.answer(make_stage_proposal())
    _plan(store, stage_repo)
    _keep_a_plan_that_the_gates_now_refuse()
    model_fake.reset()
    model_fake.answer(_refused_reply())

    with caplog.at_level(logging.INFO):
        plan = _plan(store, stage_repo)

    returns = RoadmapStageConfig().gate_returns
    assert (plan.ready, len(plan.failed), model_fake.call_count) == ((), 1, 1 + returns)
    assert _gate_returns_lines(caplog) == [
        f"repo={STAGE_REPO} item=#1 returns={returns} result=refused"
        " gates=paths:1 codes=stage_problem_path:1"
    ]


def test_the_new_first_reply_after_a_refused_kept_plan_gets_the_plan_and_its_problem(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The new first reply is no return, so a reply that passes logs no `stage gate returns:`
    line (#4950)."""
    model_fake.answer(make_stage_proposal())
    _plan(store, stage_repo)
    stale = _keep_a_plan_that_the_gates_now_refuse()
    model_fake.reset()
    model_fake.answer(make_stage_proposal(summary="Planned again"))

    with caplog.at_level(logging.INFO):
        plan = _plan(store, stage_repo)

    (asked,) = [json.loads(call.prompt) for call in model_fake.calls]
    assert ([c.proposal.summary for c in plan.ready], plan.failed) == (["Planned again"], ())
    assert (asked["previous"], MISSING in asked["problem"]) == (stale.model_dump(), True)
    assert _gate_returns_lines(caplog) == []


def test_a_new_plan_after_a_refused_kept_plan_has_no_count_of_plan_calls(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    """The attempt starts from a kept plan, so an earlier attempt made the first plan calls of the
    item. The attempt makes one new plan call after the checks refuse the kept plan, but it cannot
    count all the calls. So its counts hold no `plan_calls`, and the result line leaves the field
    out (#5166)."""
    model_fake.answer(make_stage_proposal())
    (first,) = _plan(store, stage_repo).attempts
    _keep_a_plan_that_the_gates_now_refuse()
    model_fake.reset()
    model_fake.answer(make_stage_proposal(summary="Planned again"))

    plan = _plan(store, stage_repo)

    (attempt,) = plan.attempts
    assert (first.plan_calls, len(plan.ready), model_fake.call_count) == (1, 1, 1)
    assert (attempt.plan_calls, "plan_calls" in attempt.counts()) == (None, False)


def test_a_refused_kept_plan_starts_no_planner_run_once_the_service_stops(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The new first reply is a plan run of model requests, as a return is, so it does not start
    in the drain (#4900)."""
    model_fake.answer(make_stage_proposal())
    _plan(store, stage_repo)
    _keep_a_plan_that_the_gates_now_refuse()
    model_fake.reset()
    model_fake.answer(make_stage_proposal(summary="Planned again"))

    def read_in_the_drain(path: Path, key: str) -> StagePlanRecord | None:
        begin_service_stop()
        return read_plan_record(path, key)

    monkeypatch.setattr(stage_module, "read_plan_record", read_in_the_drain)

    with pytest.raises(ServiceStoppingError) as stopped:
        _plan(store, stage_repo)

    assert (ended_by_stop(stopped.value), model_fake.call_count) == (True, 0)
    assert refused_record_path(STAGE_REPO, 1).exists() is False


def test_a_changed_item_body_gives_a_new_key_and_asks_the_planner_again(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    model_fake.answer(make_stage_proposal())
    _plan(store, stage_repo)
    before = _key_of_file()
    store.write_issue_body(1, "The job drops the first comment of a thread.")

    _plan(store, stage_repo)

    assert (model_fake.call_count, _key_of_file() != before) == (2, True)


def test_a_changed_prompt_text_gives_a_new_key_and_asks_the_planner_again(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, monkeypatch: Any
) -> None:
    model_fake.answer(make_stage_proposal())
    _plan(store, stage_repo)
    before = _key_of_file()
    monkeypatch.setattr(
        stage_plan_record, "load_task_prompt", lambda name: f"{load_task_prompt(name)}\nA new rule."
    )

    _plan(store, stage_repo)

    assert (model_fake.call_count, _key_of_file() != before) == (2, True)


def test_a_moved_staged_commit_keeps_the_key_and_runs_the_measure_again_on_the_new_commit(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    model_fake.answer(make_stage_proposal())
    first = _plan(store, stage_repo)
    before = _key_of_file()
    lines = [f"def function_{i}(value):\n    return value + {i}\n" for i in range(1500)]
    stage_repo.track({SAMPLE: "\n".join(lines)})

    second = _plan(store, stage_repo)

    assert (model_fake.call_count, _key_of_file() == before, second.sha != first.sha) == (
        1,
        True,
        True,
    )
    assert second.ready[0].groups[0].tokens > first.ready[0].groups[0].tokens


def test_plan_then_confirm_send_the_planner_one_request_and_the_plan_makes_no_github_write(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, github_api: Any
) -> None:
    api: GitHubApiFake = github_api
    api.route("POST", PULLS, OPENED)
    model_fake.answer(make_stage_proposal())

    planned = _plan(store, stage_repo)

    writes = [
        request
        for request in api.requested
        if request.startswith(("POST", "PATCH", "PUT", "DELETE")) and "graphql" not in request
    ]
    assert (len(planned.ready), _file().is_file(), writes, store.job_writes()) == (
        1,
        True,
        [],
        [],
    )
    assert stage_repo.origin_git("branch", "--format=%(refname:short)").split() == ["main"]

    confirmed = _plan(store, stage_repo)
    applied = apply_stage(store, confirmed, source=stage_repo.clone)

    assert (applied.staged, model_fake.call_count) == ((1,), 1)


def test_the_golden_set_plan_keeps_no_file_and_asks_the_model_each_time(
    store: InMemoryRoadmapStore, stage_repo: StageRepo
) -> None:
    item = store.item(1)
    assert item is not None
    sha = stage_repo.git("rev-parse", "HEAD")
    script = Script(call("list_files", directory="src"), make_stage_proposal())
    again = Script(call("list_files", directory="src"), make_stage_proposal())

    for each in (script, again):
        client = ToolboxClient(each.model(), cast("StageClient", object()), stage_repo.clone, sha)
        plan_item(item, client=client, checkout=stage_repo.clone, sha=sha)

    assert (len(script.tool_returns()), len(again.tool_returns()), _file().exists()) == (
        1,
        1,
        False,
    )


# ── The file goes ─────────────────────────────────────────────────────────────


def test_a_staged_item_deletes_its_plan_file(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, github_api: Any
) -> None:
    cast("GitHubApiFake", github_api).route("POST", PULLS, OPENED)
    model_fake.answer(make_stage_proposal())
    planned = _plan(store, stage_repo)
    assert _file().is_file()

    applied = apply_stage(store, planned, source=stage_repo.clone)

    assert (applied.staged, _file().exists()) == ((1,), False)


def test_a_write_that_fails_leaves_the_plan_file_for_the_next_run(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, github_api: Any
) -> None:
    cast("GitHubApiFake", github_api).route(
        "POST", PULLS, github_json({"message": "Validation Failed"}, status=422)
    )
    model_fake.answer(make_stage_proposal())
    planned = _plan(store, stage_repo)

    applied = apply_stage(store, planned, source=stage_repo.clone)

    assert (applied.staged, [f.number for f in applied.failed], _file().is_file()) == (
        (),
        [1],
        True,
    )


def test_an_item_that_changes_deletes_the_old_plan_file_before_the_new_plan(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    model_fake.answer(make_stage_proposal())
    _plan(store, stage_repo)
    assert _file().is_file()
    store.write_issue_body(1, "The job drops the first comment of a thread.")
    model_fake.reset()
    model_fake.answer(AIClientError("the model is down"))

    plan = _plan(store, stage_repo)

    assert ([f.number for f in plan.failed], _file().exists()) == ([1], False)


# ── The counter ───────────────────────────────────────────────────────────────


def test_a_miss_a_write_and_a_hit_each_add_one_to_the_counter_with_their_result(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, otlp: FakeCollector
) -> None:
    model_fake.answer(make_stage_proposal())

    _plan(store, stage_repo)
    _plan(store, stage_repo)

    points = sorted(
        (attrs["result"], value)
        for attrs, value in otlp.points(ROADMAP_STAGE_PLAN_RECORD_TOTAL.name)
    )
    assert points == [("hit", 1.0), ("miss", 1.0), ("written", 1.0)]
