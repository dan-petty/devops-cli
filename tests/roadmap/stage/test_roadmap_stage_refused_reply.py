"""`devops roadmap stage`: a refused reply is kept and logged, and a reply of placeholders ends the
plan run at once as `degenerate` (#4204)."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, cast

import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart

from devops_cli.ai.client.models import AIClientError, StructuredOutputValidationError
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

    from devops_cli.ai.schema_reflection import ViolationText
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


def test_a_plan_that_the_gates_refuse_after_each_return_keeps_each_reply_and_its_problem(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    refused = _missing_path()
    model_fake.answer(refused)

    plan = _plan(store, stage_repo)

    record = _read()
    assert (len(plan.failed), model_fake.call_count, len(record.replies)) == (1, 4, 4)
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


# ── The findings of a refused reply ───────────────────────────────────────────

MISSING_CODE = "stage_problem_path"


def _two_gates() -> Any:
    """A reply that two gates refuse on each try: `paths` for a file that does not exist, and
    `what-changes` for a What Changes item that names a file that no group changes."""
    proposal = _missing_path()
    return proposal.model_copy(
        update={"what_changes": [*proposal.what_changes, "`openspec/config.yaml` states the rule."]}
    )


def _counts(caplog: pytest.LogCaptureFixture, event: str) -> list[str]:
    """The fields of each log line of `event`, with the version cut off."""
    return [
        r.getMessage().removeprefix(f"{event}: ").rsplit(" version=", 1)[0]
        for r in caplog.records
        if r.getMessage().startswith(f"{event}: ")
    ]


def test_the_refused_file_keeps_the_gate_the_code_and_the_path_of_each_finding(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    model_fake.answer(_missing_path())

    _plan(store, stage_repo)

    for entry in _read().replies:
        assert [(f.gate, f.code, f.path) for f in entry.findings] == [
            ("paths", MISSING_CODE, "tests/test_missing.py")
        ]
        assert " ".join(f.text for f in entry.findings) == entry.problem


def test_a_reply_that_two_gates_refuse_keeps_two_findings_and_returns_their_joined_text(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    model_fake.answer(_two_gates())

    _plan(store, stage_repo)

    first = _read().replies[0]
    returned = json.loads(model_fake.calls[1].prompt)["problem"]
    assert ([(f.gate, f.code) for f in first.findings], returned) == (
        [("paths", MISSING_CODE), ("what-changes", "stage_problem_what_changes_path")],
        " ".join(f.text for f in first.findings),
    )


def test_each_return_logs_the_findings_before_and_those_gone_stuck_and_new(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    model_fake.answer(_two_gates(), _missing_path())

    with caplog.at_level(logging.INFO):
        _plan(store, stage_repo)

    assert _counts(caplog, "stage gate findings") == [
        f"repo={STAGE_REPO} item=#1 return=1 in=2 gone=1 stuck=1 new=0",
        f"repo={STAGE_REPO} item=#1 return=2 in=1 gone=0 stuck=1 new=0",
        f"repo={STAGE_REPO} item=#1 return=3 in=1 gone=0 stuck=1 new=0",
    ]
    assert _counts(caplog, "stage gate returns") == [
        f"repo={STAGE_REPO} item=#1 returns=3 result=refused gates=paths:1 codes={MISSING_CODE}:1"
    ]


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


def test_a_reply_that_is_only_in_part_placeholders_goes_back_as_a_refused_reply(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    partly = make_stage_proposal(why="x", feasibility=["x"])
    model_fake.answer(partly)

    plan = _plan(store, stage_repo)

    (failure,) = plan.failed
    assert (model_fake.call_count, failure.error, failure.degenerate) == (
        1 + 3,
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
    finish = client.traces[-1].finish_reason or "none"
    answered = client.traces[-1].answered or "none"
    assert tokens > 0
    assert record.getMessage() == (
        f"stage reply refused: item=#1 request=2 input_tokens={tokens} tools_offered=True "
        f"tool_calls=1 limit=none finish_reason={finish} answered={answered} result=degenerate"
    )


def test_the_log_line_of_a_degenerate_reply_names_the_stop_reason_the_limit_and_the_model(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    caplog: pytest.LogCaptureFixture,
) -> None:
    item = store.item(1)
    assert item is not None
    sha = stage_repo.git("rev-parse", "HEAD")
    reply = ModelResponse(
        parts=[
            ToolCallPart(tool_name="final_result", args=_placeholders().model_dump()),
        ],
        model_name="fallback-model",
        finish_reason="length",
    )
    script = Script(call("list_files", directory="src"), reply, reports_input=True)
    client = ToolboxClient(script.model(), cast("StageClient", object()), stage_repo.clone, sha)

    with (
        caplog.at_level(logging.WARNING),
        pytest.raises(RoadmapStageDegenerateError, match="placeholder"),
    ):
        plan_item(item, client=client, checkout=stage_repo.clone, sha=sha)

    (record,) = [r for r in caplog.records if "stage reply refused" in r.getMessage()]
    assert record.getMessage().endswith(
        "tool_calls=1 limit=none finish_reason=length answered=fallback-model result=degenerate"
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
    assert [line.rsplit(" ", 1)[1] for line in lines] == ["result=refused"] * (1 + 3)
    assert all(
        "item=#1 request=1 input_tokens=0 tools_offered=False tool_calls=0 limit=none "
        "finish_reason=none answered=none result=" in line
        for line in lines
    )


# ── The reply that breaks the schema ──────────────────────────────────────────

SECRET = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"


def _text(*, loc: str, type: str, message: str) -> ViolationText:
    """One violation text. The import is here so that a run on a base without the class fails in
    the call phase of each test and not at the collection of the file."""
    from devops_cli.ai.schema_reflection import ViolationText

    return ViolationText(loc=loc, type=type, message=message)


def _broken(
    *texts: ViolationText, count: int | None = None, stop_reason: str = "validation"
) -> StructuredOutputValidationError:
    """The error of a plan run whose reply broke the schema past its retries."""
    return StructuredOutputValidationError(
        "The plan run stopped before it gave a plan.",
        violations=len(texts) if count is None else count,
        violation_texts=texts,
        stop_reason=stop_reason,
    )


def _two_violations() -> StructuredOutputValidationError:
    return _broken(
        _text(loc="references.0.reason", type="string_too_short", message="Too short"),
        _text(loc="references.1.reason", type="missing", message="Field required"),
    )


def test_a_schema_failure_names_the_violations_the_stop_reason_and_the_count(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    model_fake.answer(_two_violations())

    (failure,) = _plan(store, stage_repo).failed

    assert failure.error == "StructuredOutputValidationError"
    for expected in (
        "2 schema violation(s)",
        "validation",
        "references.0.reason (string_too_short): Too short",
        "references.1.reason (missing): Field required",
    ):
        assert expected in failure.reason


def test_a_model_call_error_names_its_reason_and_its_message(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    model_fake.answer(AIClientError("gateway returned 502", status=502))

    (failure,) = _plan(store, stage_repo).failed

    assert failure.error == "AIClientError"
    assert "HTTP 502" in failure.reason
    assert "gateway returned 502" in failure.reason


def test_a_model_call_error_hides_the_quoted_text_of_the_provider(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    model_fake.answer(AIClientError("Ollama returned HTTP 500. Response: 'the reply of the model'"))

    (failure,) = _plan(store, stage_repo).failed

    assert "the reply of the model" not in failure.reason
    assert "Ollama returned HTTP 500" in failure.reason


def test_a_model_call_error_logs_one_line_with_the_item_and_the_status(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    model_fake.answer(AIClientError("gateway returned 502", status=502))

    with caplog.at_level(logging.WARNING):
        _plan(store, stage_repo)

    (line,) = [r.getMessage() for r in caplog.records if "model call failed" in r.getMessage()]
    assert "item=#1" in line
    assert "status=502" in line


def test_a_schema_failure_names_at_most_three_violations_of_five(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    texts = [_text(loc=f"field_{n}", type="missing", message="m") for n in range(5)]
    model_fake.answer(_broken(*texts, count=5))

    (failure,) = _plan(store, stage_repo).failed

    assert "5 schema violation(s)" in failure.reason
    assert [f"field_{n}" in failure.reason for n in range(5)] == [True] * 3 + [False] * 2


def test_a_schema_failure_cuts_a_message_of_300_characters_at_200(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    model_fake.answer(_broken(_text(loc="a", type="b", message="m" * 300)))

    (failure,) = _plan(store, stage_repo).failed

    assert ("m" * 200 in failure.reason, "m" * 201 in failure.reason) == (True, False)


def test_a_schema_failure_with_a_secret_in_a_message_shows_and_keeps_the_masked_value(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    model_fake.answer(_broken(_text(loc="a", type="b", message=f"bad {SECRET}")))

    (failure,) = _plan(store, stage_repo).failed

    assert SECRET not in failure.reason
    assert SECRET not in _refused_file().read_text(encoding="utf-8")


def test_a_schema_failure_keeps_the_same_fields_in_the_refused_file(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    model_fake.answer(_two_violations())

    _plan(store, stage_repo)

    failure = _read().schema_failure
    assert failure is not None
    assert (failure.stop_reason, failure.count) == ("validation", 2)
    assert [(v.loc, v.type, v.message) for v in failure.violations] == [
        ("references.0.reason", "string_too_short", "Too short"),
        ("references.1.reason", "missing", "Field required"),
    ]
    assert not plan_record_path(STAGE_REPO, 1).exists()


def test_a_schema_failure_after_a_refused_reply_keeps_both(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    refused = _missing_path()
    model_fake.answer(refused, _two_violations())

    _plan(store, stage_repo)

    record = _read()
    assert [e.reply for e in record.replies] == [refused.model_dump()]
    assert record.schema_failure is not None
    assert record.schema_failure.count == 2


def test_a_schema_failure_logs_one_line_with_the_violations(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    model_fake.answer(_two_violations())

    with caplog.at_level(logging.WARNING):
        _plan(store, stage_repo)

    (line,) = [r.getMessage() for r in caplog.records if "schema" in r.getMessage()]
    assert "references.0.reason" in line
    assert "item=#1" in line


def test_a_staged_item_deletes_the_refused_file_of_a_schema_failure(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    github_api.route("POST", PULLS, OPENED)
    model_fake.answer(_two_violations())
    _plan(store, stage_repo)
    assert _refused_file().is_file()
    model_fake.reset()
    model_fake.answer(make_stage_proposal())
    planned = _plan(store, stage_repo)

    applied = apply_stage(store, planned, source=stage_repo.clone)

    assert (applied.staged, _refused_file().exists()) == ((1,), False)
