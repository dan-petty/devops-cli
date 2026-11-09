"""`devops roadmap stage`: a refused reply is kept and logged, and a reply of placeholders ends the
plan run at once as `degenerate` (#4204)."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, cast

import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_STAGE_REFUSED_PROBLEM_MAX_CHARS,
    CONST_ROADMAP_STAGE_REFUSED_REPLY_MAX_BYTES,
)
from devops_cli.exceptions.roadmap import RoadmapStageDegenerateError, RoadmapStageError
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.stage.stage import (
    StagePlan,
    StageResult,
    parse_filters,
    plan_item,
    plan_stage,
    stage_results,
)
from devops_cli.roadmap.stage.stage_plan_record import (
    RefusedRecord,
    plan_record_path,
    refused_record_path,
    write_refused_record,
)
from devops_cli.roadmap.stage.stage_toolbox import ToolboxClient
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json
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
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

PULLS = f"/repos/{STAGE_REPO}/pulls"
OPENED = github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201)
KEY = "k" * 64


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    seed_stageable(store)
    store.seed_file(
        ".github/labels.yml",
        '- name: "type/docs"\n  color: "0075ca"\n- name: "scope/openspec"\n  color: "0e8a16"\n',
    )
    store.seed_pull("staging PR", head_ref="fix/1-the-job-drops-a-comment", draft=True)
    return store


@pytest.fixture(autouse=True)
def valid_openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    openspec_fake.script_sequence(
        validate_args("1-the-job-drops-a-comment"), *[(0, VALID_REPORT)] * 6
    )
    return openspec_fake


def _plan(store: InMemoryRoadmapStore, repo: StageRepo) -> StagePlan:
    return plan_stage(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        filters=parse_filters(()),
        model=None,
    )


def _refused_file() -> Path:
    return refused_record_path(STAGE_REPO, 1)


def _read() -> RefusedRecord:
    return RefusedRecord.model_validate_json(_refused_file().read_text(encoding="utf-8"))


def _missing_path() -> Any:
    """A reply that the `paths` gate refuses on each try."""
    group = make_stage_proposal().groups[0]
    return make_stage_proposal(
        groups=[group.model_copy(update={"changes": [*group.changes, "tests/test_missing.py"]})]
    )


def _placeholders() -> Any:
    """A reply as the model sent it on 2026-11-08: `x` or `placeholder` in every text of the plan."""
    group = (
        make_stage_proposal()
        .groups[0]
        .model_copy(
            update={
                "test": "x",
                "implementation": "placeholder",
                "documentation": None,
                "verify": "x",
            }
        )
    )
    return make_stage_proposal(
        why="x", existing_tool="placeholder", feasibility=["x"], groups=[group]
    )


# ── The refused reply file ────────────────────────────────────────────────────


def test_the_refused_file_is_next_to_the_plan_file() -> None:
    assert refused_record_path(STAGE_REPO, 1) == plan_record_path(STAGE_REPO, 1).with_name(
        "1.refused.json"
    )


def test_a_plan_that_the_gates_refuse_twice_keeps_both_replies_and_both_problems(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    refused = _missing_path()
    model_fake.answer(refused)

    plan = _plan(store, stage_repo)

    record = _read()
    assert (len(plan.failed), model_fake.call_count, len(record.replies)) == (1, 2, 2)
    for entry in record.replies:
        assert entry.reply == refused.model_dump()
        assert "tests/test_missing.py" in entry.problem
    assert not plan_record_path(STAGE_REPO, 1).exists()


def test_the_refused_file_holds_the_key_of_the_plan_input(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    model_fake.answer(_missing_path())
    _plan(store, stage_repo)
    first = json.loads(_refused_file().read_text(encoding="utf-8"))["key"]
    store.write_issue_body(1, "The job drops the first comment of a thread.")

    _plan(store, stage_repo)

    second = json.loads(_refused_file().read_text(encoding="utf-8"))["key"]
    assert (len(first), first != second) == (64, True)


def test_a_staged_item_deletes_its_refused_file(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    github_api.route("POST", PULLS, OPENED)
    model_fake.answer(_missing_path())
    _plan(store, stage_repo)
    assert _refused_file().is_file()
    model_fake.reset()
    model_fake.answer(make_stage_proposal())
    planned = _plan(store, stage_repo)

    applied = apply_stage(store, planned, source=stage_repo.clone)

    assert (applied.staged, _refused_file().exists()) == ((1,), False)


def test_a_reply_over_the_size_bound_is_dropped_and_its_size_stays(
    isolate_data_dir: Path,
) -> None:
    big = {"text": "a" * CONST_ROADMAP_STAGE_REFUSED_REPLY_MAX_BYTES}
    long_problem = "p" * (CONST_ROADMAP_STAGE_REFUSED_PROBLEM_MAX_CHARS + 500)

    record = RefusedRecord.of(KEY, [(big, long_problem), ({"text": "small"}, "short")])
    write_refused_record(_refused_file(), record)

    first, second = _read().replies
    assert (first.reply, first.reply_bytes > CONST_ROADMAP_STAGE_REFUSED_REPLY_MAX_BYTES) == (
        None,
        True,
    )
    assert len(first.problem) == CONST_ROADMAP_STAGE_REFUSED_PROBLEM_MAX_CHARS
    assert (second.reply, second.problem) == ({"text": "small"}, "short")


def test_a_problem_text_is_masked_before_it_is_kept(isolate_data_dir: Path) -> None:
    record = RefusedRecord.of(
        KEY, [({"text": "a"}, "token ghp_abcdefghijklmnopqrstuvwxyz0123456789 in the reply")]
    )

    assert "ghp_abcdefghijklmnopqrstuvwxyz0123456789" not in record.replies[0].problem


# ── The reply of placeholders ─────────────────────────────────────────────────


def test_a_reply_of_placeholders_ends_the_plan_after_one_call_and_keeps_the_reply(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    degenerate = _placeholders()
    model_fake.answer(degenerate)

    plan = _plan(store, stage_repo)

    (failure,) = plan.failed
    record = _read()
    assert (model_fake.call_count, failure.error, failure.failure_class) == (
        1,
        "RoadmapStageDegenerateError",
        FailureClass.PLAN_DEFECT,
    )
    assert (failure.degenerate, [e.reply for e in record.replies]) == (
        True,
        [degenerate.model_dump()],
    )


def test_a_reply_that_is_only_in_part_placeholders_goes_back_once_as_before(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    partly = make_stage_proposal(why="x", feasibility=["x"])
    model_fake.answer(partly)

    plan = _plan(store, stage_repo)

    (failure,) = plan.failed
    assert (model_fake.call_count, failure.error, failure.degenerate) == (
        2,
        "RoadmapStageError",
        False,
    )


def test_a_degenerate_item_counts_under_the_result_degenerate_and_a_refused_one_under_failed(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    model_fake.answer(_placeholders())
    degenerate = _plan(store, stage_repo)
    model_fake.reset()
    model_fake.answer(_missing_path())
    refused = _plan(store, stage_repo)

    assert (
        stage_results(degenerate, apply_stage(store, degenerate, source=stage_repo.clone)),
        stage_results(refused, apply_stage(store, refused, source=stage_repo.clone)),
    ) == ({1: StageResult.DEGENERATE}, {1: StageResult.FAILED})
    assert StageResult.DEGENERATE.value == "degenerate"


def test_the_degenerate_error_is_a_stage_error_with_the_code_of_a_stage_error() -> None:
    error = RoadmapStageDegenerateError("every text is a placeholder", failed_items=[1])

    assert (type(error).__bases__, error.error_code, error.failed_items) == (
        (RoadmapStageError,),
        RoadmapStageError.error_code,
        (1,),
    )


# ── The log line ──────────────────────────────────────────────────────────────


def test_a_refused_reply_of_a_plan_run_logs_the_request_size_the_request_number_and_the_tools(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    caplog: pytest.LogCaptureFixture,
) -> None:
    item = store.item(1)
    assert item is not None
    sha = stage_repo.git("rev-parse", "HEAD")
    script = Script(call("list_files", directory="src"), _placeholders(), reports_input=True)
    client = ToolboxClient(script.model(), cast("StageClient", object()), stage_repo.clone, sha)

    with (
        caplog.at_level(logging.WARNING),
        pytest.raises(RoadmapStageDegenerateError, match="placeholder"),
    ):
        plan_item(item, client=client, checkout=stage_repo.clone, sha=sha)

    (record,) = [r for r in caplog.records if "stage reply refused" in r.getMessage()]
    tokens = client.traces[-1].last_input_tokens
    assert tokens > 0
    assert record.getMessage() == (
        f"stage reply refused: item=#1 request=2 input_tokens={tokens} tools_offered=True "
        "result=degenerate"
    )


def test_a_gate_refusal_logs_one_line_for_each_refused_reply(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    model_fake.answer(_missing_path())

    with caplog.at_level(logging.WARNING):
        _plan(store, stage_repo)

    lines = [r.getMessage() for r in caplog.records if "stage reply refused" in r.getMessage()]
    assert [line.rsplit(" ", 1)[1] for line in lines] == ["result=refused", "result=refused"]
    assert all("item=#1 request=1 input_tokens=0 tools_offered=False" in line for line in lines)
