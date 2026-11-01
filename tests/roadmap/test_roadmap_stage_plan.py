"""`devops roadmap stage`: the plan of one item, the measure of its groups and its checks (#2654)."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
import time_machine
from pydantic import ValidationError

from devops_cli.ai.client.models import AIClientError, AICredentialsError
from devops_cli.ai.context_budget import count_tokens
from devops_cli.ai.context_packer import ContextPacker
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.git.worktree_add import issue_holder, read_remote_heads
from devops_cli.openspec.tool import isolated_openspec
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.stage import StagePlan, parse_filters, plan_stage
from devops_cli.roadmap.stage_change import (
    StageGroup,
    StageProposal,
    StageSplit,
    check_proposal,
    closing_keyword_in,
    render_change,
)
from devops_cli.roadmap.stage_paths import StagedTree
from devops_cli.roadmap.stage_validate import validate_change
from tests.support.builders import make_stage_proposal
from tests.support.roadmap_stage import (
    NO_FILES,
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    heavy_group,
    run_git,
    seed_stageable,
    validate_args,
    validation_report,
)

if TYPE_CHECKING:
    from syrupy.assertion import SnapshotAssertion

    from devops_cli.ai.client.unified import LLMClient
    from tests.support.fakes.model import ModelFake, ModelFakeReplies
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

# The one file of the sample proposal that exists before the plan.
SAMPLE_TREE = StagedTree(["src/devops_cli/sample.py"])
CHANGE = "1-the-job-drops-a-comment"
VALIDATE = validate_args(CHANGE)
VALID = (0, VALID_REPORT)
TODAY = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture
def item(store: InMemoryRoadmapStore) -> int:
    """The one Ready bug the plans are about: #1."""
    return seed_stageable(store)


@pytest.fixture
def openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    """OpenSpec, found, and valid about the change of #1 unless a test scripts it."""
    openspec_fake.script_sequence(VALIDATE, VALID)
    return openspec_fake


def _plan(
    store: InMemoryRoadmapStore,
    repo: StageRepo,
    *,
    step_tokens: int | None = None,
    item: int | None = None,
    model: ModelFakeReplies | None = None,
) -> StagePlan:
    return plan_stage(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        filters=parse_filters(()),
        item_number=item,
        step_tokens=step_tokens,
        model=cast("LLMClient | None", model),
    )


def _requests(model_fake: ModelFake) -> list[dict[str, Any]]:
    return [json.loads(call.prompt) for call in model_fake.calls]


def _about(number: int) -> Callable[[str], bool]:
    return lambda prompt: json.loads(prompt).get("number") == number


# ── A valid plan ──────────────────────────────────────────────────────────────


@time_machine.travel(TODAY, tick=False)
@pytest.mark.usefixtures("openspec")
def test_a_valid_plan_gives_the_branch_the_title_the_body_and_the_files(
    store: InMemoryRoadmapStore,
    item: int,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    snapshot: SnapshotAssertion,
) -> None:
    model_fake.answer(make_stage_proposal())

    plan = _plan(store, stage_repo)

    (change,) = plan.ready
    assert (change.target.branch, change.title, change.body, change.validated) == (
        f"fix/{item}-the-job-drops-a-comment",
        "docs(openspec): plan #1 Stop the job dropping a comment",
        (
            f"Plans #{item}\n\nThe job keeps every comment it reads. It dropped the last one.\n\n"
            f"Change: `openspec/changes/{item}-the-job-drops-a-comment/`"
        ),
        True,
    )
    assert change.files == snapshot


@pytest.mark.usefixtures("openspec")
def test_the_model_reads_the_item_the_capabilities_and_the_repository(
    store: InMemoryRoadmapStore, item: int, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    model_fake.answer(make_stage_proposal())

    plan = _plan(store, stage_repo, step_tokens=9000)

    (request,) = _requests(model_fake)
    assert plan.budget == 9000
    assert {key: request[key] for key in ("number", "title", "body", "capabilities", "budget")} == {
        "number": item,
        "title": "fix(roadmap): the job drops a comment",
        "body": "The job drops the last comment of a thread.",
        "capabilities": ["roadmap-refine"],
        "budget": 9000,
    }
    assert "The job reads comments." in request["context"]
    assert "You plan the OpenSpec change" in model_fake.calls[0].system_prompt


def test_a_plan_with_no_item_to_stage_calls_no_model(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    plan = _plan(store, stage_repo)

    assert (plan.ready, plan.left_out, model_fake.call_count) == ((), (), 0)


def test_an_item_with_a_pushed_branch_is_left_out(
    store: InMemoryRoadmapStore, item: int, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    stage_repo.push_branch(f"fix/{item}-other-slug")

    plan = _plan(store, stage_repo)

    assert [left.number for left in plan.left_out] == [item]
    assert f"origin/fix/{item}-other-slug" in plan.left_out[0].reason
    assert model_fake.call_count == 0


def test_an_item_with_a_stray_local_branch_with_a_commit_of_its_own_is_left_out(
    store: InMemoryRoadmapStore, item: int, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    branch = f"fix/{item}-the-job-drops-a-comment"
    stage_repo.stray_branch(branch, own_commit=True)

    plan = _plan(store, stage_repo)

    assert [left.number for left in plan.left_out] == [item]
    assert branch in plan.left_out[0].reason
    assert "1 commit" in plan.left_out[0].reason
    assert model_fake.call_count == 0


@pytest.mark.usefixtures("openspec")
def test_an_item_with_a_stray_local_branch_that_origin_holds_is_staged(
    store: InMemoryRoadmapStore, item: int, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    stage_repo.stray_branch(f"fix/{item}-the-job-drops-a-comment")
    model_fake.answer(make_stage_proposal())

    plan = _plan(store, stage_repo)

    assert plan.left_out == ()
    assert [change.target.item.number for change in plan.ready] == [item]


# ── The measure ───────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("openspec")
def test_a_group_is_measured_with_the_packed_files_it_names(
    store: InMemoryRoadmapStore, item: int, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    model_fake.answer(make_stage_proposal())

    plan = _plan(store, stage_repo)

    packed = ContextPacker().pack_file(stage_repo.clone / "src/devops_cli/sample.py")
    (group,) = plan.ready[0].groups
    assert group.tokens > packed.packed_tokens


@pytest.mark.usefixtures("openspec")
def test_a_large_file_counts_at_most_the_file_cap_of_the_step(
    store: InMemoryRoadmapStore, item: int, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    heavy = heavy_group(stage_repo, files=1)
    big = stage_repo.clone / heavy.reads[0]
    assert count_tokens(big.read_text(encoding="utf-8")) > 6000
    model_fake.answer(make_stage_proposal(groups=[heavy]))

    plan = _plan(store, stage_repo, step_tokens=6000)

    assert (plan.over_budget, model_fake.call_count) == ((), 1)
    (group,) = plan.ready[0].groups
    assert group.tokens <= 6000


@pytest.mark.usefixtures("openspec")
def test_a_group_over_the_budget_is_split_once(
    store: InMemoryRoadmapStore, item: int, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    big = make_stage_proposal()
    heavy = heavy_group(stage_repo)
    light = [
        heavy.model_copy(update={"title": "First half", **NO_FILES}),
        heavy.model_copy(update={"title": "Second half", **NO_FILES}),
    ]
    model_fake.answer(big.model_copy(update={"groups": [heavy]}), StageSplit(groups=light))

    plan = _plan(store, stage_repo, step_tokens=6000)

    first, second = _requests(model_fake)
    assert first["budget"] == 6000
    assert [g["title"] for g in second["groups"]] == ["Keep the last comment"]
    assert second["groups"][0]["over_budget"] is True
    assert "You split the task groups" in model_fake.calls[1].system_prompt
    assert [g.group.title for g in plan.ready[0].groups] == ["First half", "Second half"]
    assert all(g.tokens <= 6000 for g in plan.ready[0].groups)


@pytest.mark.usefixtures("openspec")
def test_a_group_still_over_the_budget_after_the_split_stops_the_item(
    store: InMemoryRoadmapStore, item: int, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    heavy = heavy_group(stage_repo)
    model_fake.answer(
        make_stage_proposal().model_copy(update={"groups": [heavy]}),
        StageSplit(groups=[heavy]),
    )

    plan = _plan(store, stage_repo, step_tokens=6000)

    (stopped,) = plan.over_budget
    assert plan.ready == ()
    assert model_fake.call_count == 2
    assert (stopped.target.item.number, stopped.worst.group.title) == (
        item,
        "Keep the last comment",
    )
    assert stopped.worst.tokens > 6000


@pytest.mark.usefixtures("openspec")
def test_a_corrected_reply_over_the_budget_does_not_ask_for_a_second_split(
    store: InMemoryRoadmapStore,
    item: int,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec: OpenSpecFake,
) -> None:
    heavy = heavy_group(stage_repo)
    light = heavy.model_copy(update={"title": "Light", **NO_FILES})
    openspec.script_sequence(VALIDATE, (1, "ERROR: a requirement has no scenario\n"), VALID)
    model_fake.answer(
        make_stage_proposal(groups=[heavy]),
        StageSplit(groups=[light]),
        make_stage_proposal(groups=[heavy]),
    )

    plan = _plan(store, stage_repo, step_tokens=6000)

    (stopped,) = plan.over_budget
    assert plan.ready == ()
    assert model_fake.call_count == 3
    assert stopped.worst.group.title == "Keep the last comment"


# ── The checks of the change ──────────────────────────────────────────────────


def test_the_rules_of_a_spec_delta_are_checked() -> None:
    spec = make_stage_proposal().specs[0]
    bad = spec.model_copy(
        update={
            "purpose": "Too short.",
            "modified": [spec.added[0].model_copy(update={"text": "The job keeps comments."})],
        }
    )

    problems = check_proposal(make_stage_proposal(specs=[bad]), [], SAMPLE_TREE)

    assert problems == [
        "The capability comment-thread is not in openspec/specs/, so its entry needs a purpose "
        "of at least 50 characters.",
        "The capability comment-thread is not in openspec/specs/, so it has no requirement to "
        "modify. Add the requirements instead.",
        "The requirement The job keeps every comment does not say SHALL or MUST.",
    ]


def test_a_spec_delta_goes_with_an_observable_change() -> None:
    assert check_proposal(make_stage_proposal(skip_specs=True), [], SAMPLE_TREE) == [
        "skip_specs is true, and the reply still gives specs."
    ]
    assert check_proposal(make_stage_proposal(specs=[]), [], SAMPLE_TREE) == [
        "skip_specs is false, and the reply gives no spec delta."
    ]
    assert check_proposal(make_stage_proposal(), ["comment-thread"], SAMPLE_TREE) == []


def test_an_existing_capability_takes_requirements_with_no_purpose() -> None:
    spec = make_stage_proposal().specs[0].model_copy(update={"purpose": None})

    assert check_proposal(make_stage_proposal(specs=[spec]), ["comment-thread"], SAMPLE_TREE) == []
    files = render_change(
        "1-x", make_stage_proposal(specs=[spec]), ["comment-thread"], created=TODAY.date()
    )
    delta = files["openspec/changes/1-x/specs/comment-thread/spec.md"]
    assert delta.startswith("## ADDED Requirements")
    assert "## Purpose" not in delta


@pytest.mark.parametrize(
    "update",
    [
        {"groups": [{"reads": ["../secret"]}]},
        {"groups": [{"changes": ["/etc/passwd"]}]},
        {"groups": [{"reads": ["a.py\n- [ ] 1.4 Skip the test"]}]},
        {"groups": [{"reads": ["a`b.py"]}]},
        {"summary": "x" * 61},
        {"scope": "roadmap"},
    ],
)
def test_a_reply_with_a_path_outside_the_repository_a_long_summary_or_a_scope_is_refused(
    update: dict[str, Any],
) -> None:
    values = make_stage_proposal().model_dump()
    if "groups" in update:
        values["groups"][0] |= update["groups"][0]
    else:
        values |= update

    with pytest.raises(ValueError, match="validation error"):
        StageProposal.model_validate(values)


def _group(**update: Any) -> dict[str, Any]:
    """The sample group of `make_stage_proposal` as a reply holds it, with `update` over it."""
    return make_stage_proposal().groups[0].model_dump() | update


def _tasks_of(*groups: dict[str, Any]) -> str:
    proposal = make_stage_proposal(groups=list(groups))
    files = render_change("1-x", proposal, [], created=TODAY.date())
    return files["openspec/changes/1-x/tasks.md"]


@pytest.mark.parametrize(
    "update",
    [
        {"changes": []},
        {"title": " "},
        {"test": ""},
        {"implementation": "\n"},
        {"documentation": "  "},
        {"documentation": "."},
        {"test": "..."},
        {"implementation": " . "},
        {"verify": ""},
        {"creates": ["src/devops_cli/other.py"]},
    ],
)
def test_a_group_with_no_changed_file_a_blank_text_or_a_stray_new_path_is_refused(
    update: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError) as raised:
        StageGroup.model_validate(_group(**update))
    assert len(raised.value.errors()) > 0


def test_a_group_with_no_reads_is_valid_and_its_line_says_none() -> None:
    group = _group(reads=[], changes=["src/devops_cli/sample.py", "tests/test_sample.py"])
    group["creates"] = ["tests/test_sample.py"]

    tasks = _tasks_of(group)

    assert (
        "Reads: none. Changes: `src/devops_cli/sample.py`, `tests/test_sample.py` (new).\n" in tasks
    )


def test_a_rendered_group_has_no_double_stop_and_no_task_that_starts_with_a_comma() -> None:
    group = _group(
        test="Write the test.",
        implementation="Keep the last comment. .",
        documentation="Change no document.",
    )

    tasks = _tasks_of(group).partition("## Workflow follow-up")[0]

    assert ".." not in tasks
    assert ".," not in tasks
    assert [line for line in tasks.splitlines() if line.startswith("- [ ] 1.")] == [
        "- [ ] 1.1 Write the test, and verify that `uv run devops ci test tests/test_sample.py` "
        "fails on the base",
        "- [ ] 1.2 Keep the last comment, and verify that "
        "`uv run devops ci test tests/test_sample.py` passes",
        "- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and "
        "verify that `uv run devops ci docs` passes",
    ]


@pytest.mark.parametrize(
    ("text", "keyword"),
    [
        ("Closes #12", "closes"),
        ("it fixes: #3", "fixes"),
        ("RESOLVED example/other#4", "resolved"),
        ("close https://example.com/o/r/issues/5", "close"),
        ("Plans #12 and closes nothing", None),
        ("The fix is in #12", None),
    ],
)
def test_a_closing_keyword_before_an_issue_reference_is_found(
    text: str, keyword: str | None
) -> None:
    assert closing_keyword_in(text) == keyword


# ── Failures ──────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("openspec")
def test_a_reply_with_a_closing_keyword_stops_the_item(
    store: InMemoryRoadmapStore, item: int, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    model_fake.answer(make_stage_proposal(pull_request_body="Closes #12 when it merges."))

    plan = _plan(store, stage_repo)

    (failure,) = plan.failed
    assert plan.ready == ()
    assert (failure.number, failure.error) == (item, "RoadmapStageError")
    assert "closes" in failure.reason


@pytest.mark.usefixtures("openspec")
def test_a_reply_that_holds_a_secret_stops_the_item(
    store: InMemoryRoadmapStore, item: int, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    key = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
    model_fake.answer(make_stage_proposal(why=f"Issue #1 shows the key {key}."))

    plan = _plan(store, stage_repo)

    (failure,) = plan.failed
    assert "secret" in failure.reason
    assert key not in failure.reason


def test_a_model_call_that_fails_skips_its_item_and_plans_the_others(
    store: InMemoryRoadmapStore,
    item: int,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec: OpenSpecFake,
) -> None:
    second = seed_stageable(store, "fix(roadmap): the job drops a label")
    openspec.script_sequence(validate_args("2-the-job-drops-a-label"), VALID)
    model_fake.route_error(_about(item), AIClientError("the model is down"))
    model_fake.route(_about(second), make_stage_proposal())

    plan = _plan(store, stage_repo)

    assert [(f.number, f.error) for f in plan.failed] == [(item, "AIClientError")]
    assert [c.target.item.number for c in plan.ready] == [second]


@pytest.mark.usefixtures("openspec")
def test_rejected_credentials_stop_the_run(
    store: InMemoryRoadmapStore, item: int, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    model_fake.answer(AICredentialsError("rejected"))

    with pytest.raises(AICredentialsError) as raised:
        _plan(store, stage_repo)
    assert raised.value.error_code == "LLM_INFERENCE_ERROR"


def _reply_without(**update: Any) -> str:
    """A reply as the model writes it: JSON, with the sample group changed by `update`."""
    values = make_stage_proposal().model_dump()
    values["groups"][0] |= update
    return json.dumps(values)


@pytest.mark.usefixtures("openspec")
def test_a_group_with_no_changed_file_goes_back_to_the_model_with_the_violation(
    store: InMemoryRoadmapStore, item: int, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    model_fake.answer(_reply_without(changes=[]), make_stage_proposal())

    plan = _plan(store, stage_repo, model=model_fake.checking_replies())

    assert len(model_fake.sent) == 2
    assert "groups[0].changes" in model_fake.sent[1].messages[-1].content
    assert len(plan.ready) == 1


@pytest.mark.usefixtures("openspec")
def test_a_reply_with_a_blank_documentation_that_stays_blank_stops_the_item_after_one_return(
    store: InMemoryRoadmapStore, item: int, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    model_fake.answer(_reply_without(documentation=" "))

    plan = _plan(store, stage_repo, model=model_fake.checking_replies())

    (failure,) = plan.failed
    assert plan.ready == ()
    assert (failure.number, failure.error) == (item, "StructuredOutputValidationError")
    assert failure.reason == "1 schema violation(s)"
    assert len(model_fake.sent) == 2


@pytest.mark.parametrize("task", ["roadmap_stage_change.md", "roadmap_stage_split.md"])
def test_the_prompts_say_what_a_group_names(task: str) -> None:
    prompt = load_task_prompt(task)

    assert "at least one path" in prompt
    assert "`creates`" in prompt
    assert "Every task has a text" in prompt


@pytest.mark.parametrize("task", ["roadmap_stage_change.md", "roadmap_stage_split.md"])
def test_the_prompts_say_that_the_job_checks_each_path_against_the_staged_commit(task: str) -> None:
    prompt = load_task_prompt(task)

    assert "against the files of the staged commit" in prompt
    assert "`creates`" in prompt


# ── The OpenSpec validation ───────────────────────────────────────────────────


def test_a_proposal_the_rules_refuse_goes_back_to_the_model_once(
    store: InMemoryRoadmapStore,
    item: int,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec: OpenSpecFake,
) -> None:
    model_fake.answer(make_stage_proposal(specs=[]), make_stage_proposal())

    plan = _plan(store, stage_repo)

    first, second = _requests(model_fake)
    assert "problem" not in first
    assert second["problem"] == "skip_specs is false, and the reply gives no spec delta."
    assert second["previous"]["specs"] == []
    assert len(plan.ready) == 1


def _naming(path: str, *, verify: str | None = None) -> StageProposal:
    """The sample proposal, with a second changed file `path` that no group creates."""
    group = make_stage_proposal().groups[0]
    update: dict[str, Any] = {"changes": [*group.changes, path]}
    if verify is not None:
        update["verify"] = verify
    return make_stage_proposal(groups=[group.model_copy(update=update)])


def test_a_path_that_the_commit_lacks_goes_back_with_the_file_of_the_same_name(
    store: InMemoryRoadmapStore,
    item: int,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec: OpenSpecFake,
) -> None:
    stage_repo.track({"tests/security/test_scanner_tool_executor.py": ""})
    model_fake.answer(_naming("tests/test_scanner_tool_executor.py"), make_stage_proposal())

    plan = _plan(store, stage_repo)

    first, second = _requests(model_fake)
    assert "problem" not in first
    assert "`tests/test_scanner_tool_executor.py`" in second["problem"]
    assert "`tests/security/test_scanner_tool_executor.py`" in second["problem"]
    assert len(plan.ready) == 1


def test_a_second_reply_with_a_missing_path_stops_the_item(
    store: InMemoryRoadmapStore,
    item: int,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec: OpenSpecFake,
) -> None:
    stage_repo.track({"tests/security/test_scanner_tool_executor.py": ""})
    model_fake.answer(_naming("tests/test_scanner_tool_executor.py"))

    plan = _plan(store, stage_repo)

    (failure,) = plan.failed
    assert (plan.ready, plan.over_budget) == ((), ())
    assert (failure.number, failure.error) == (item, "RoadmapStageError")
    assert "`tests/security/test_scanner_tool_executor.py`" in failure.reason
    assert model_fake.call_count == 2


def test_a_path_in_a_verify_command_is_checked_and_a_created_path_passes(
    store: InMemoryRoadmapStore,
    item: int,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec: OpenSpecFake,
) -> None:
    model_fake.answer(
        _naming("src/devops_cli/sample.py", verify="uv run pytest tests/old/test_sample.py"),
        make_stage_proposal(),
    )

    plan = _plan(store, stage_repo)

    problem = _requests(model_fake)[1]["problem"]
    assert "`tests/old/test_sample.py`" in problem
    assert "`tests/test_sample.py`" not in problem
    assert len(plan.ready) == 1


@pytest.mark.usefixtures("openspec")
def test_a_split_reply_with_a_missing_path_goes_back_to_the_model_once(
    store: InMemoryRoadmapStore, item: int, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    heavy = heavy_group(stage_repo)
    lost = heavy.model_copy(
        update={"title": "Lost", **NO_FILES, "reads": ["src/devops_cli/old.py"]}
    )
    model_fake.answer(
        make_stage_proposal(groups=[heavy]),
        StageSplit(groups=[lost]),
        make_stage_proposal(),
    )

    plan = _plan(store, stage_repo, step_tokens=6000)

    assert "`src/devops_cli/old.py`" in _requests(model_fake)[2]["problem"]
    assert model_fake.call_count == 3
    assert len(plan.ready) == 1


def test_a_failed_validation_goes_back_to_the_model_once(
    store: InMemoryRoadmapStore,
    item: int,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec: OpenSpecFake,
) -> None:
    openspec.script_sequence(VALIDATE, (1, "ERROR: a requirement has no scenario\n"), VALID)
    model_fake.answer(make_stage_proposal())

    plan = _plan(store, stage_repo)

    assert "a requirement has no scenario" in _requests(model_fake)[1]["problem"]
    assert len(plan.ready) == 1
    assert model_fake.call_count == 2
    assert [call.argv for call in openspec.calls if call.argv[0] == "validate"] == [
        VALIDATE,
        VALIDATE,
    ]


def test_a_second_failed_validation_stops_the_item(
    store: InMemoryRoadmapStore,
    item: int,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec: OpenSpecFake,
) -> None:
    openspec.script_sequence(VALIDATE, (1, "ERROR: first\n"), (1, "ERROR: second\n"))
    model_fake.answer(make_stage_proposal())

    plan = _plan(store, stage_repo)

    (failure,) = plan.failed
    assert plan.ready == ()
    assert model_fake.call_count == 2
    assert "ERROR: second" in failure.reason
    assert "ERROR: first" not in failure.reason


def test_a_note_of_openspec_on_a_valid_change_goes_back_to_the_model_once(
    store: InMemoryRoadmapStore,
    item: int,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec: OpenSpecFake,
) -> None:
    refusal = 'cap-a MODIFIED failed for header "### Requirement: Invented name" - not found'
    openspec.script_sequence(
        VALIDATE,
        (0, validation_report(("INFO", f"Archive would refuse this delta: {refusal}"))),
        VALID,
    )
    model_fake.answer(make_stage_proposal())

    plan = _plan(store, stage_repo)

    assert refusal in _requests(model_fake)[1]["problem"]
    assert len(plan.ready) == 1
    assert model_fake.call_count == 2


def test_a_validation_that_times_out_fails_its_item_and_the_others_are_planned(
    store: InMemoryRoadmapStore,
    item: int,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec: OpenSpecFake,
) -> None:
    second = seed_stageable(store, "fix(roadmap): the job drops a label")
    openspec.hang(VALIDATE)
    openspec.script_sequence(validate_args("2-the-job-drops-a-label"), VALID)
    model_fake.answer(make_stage_proposal())

    plan = _plan(store, stage_repo)

    (failure,) = plan.failed
    assert (failure.number, failure.error) == (item, "ToolExecutionError")
    assert [change.target.item.number for change in plan.ready] == [second]


def test_without_the_openspec_binary_the_plan_says_it_did_not_validate(
    store: InMemoryRoadmapStore,
    item: int,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
) -> None:
    openspec_fake.installed = False
    model_fake.answer(make_stage_proposal())

    plan = _plan(store, stage_repo)

    assert [change.validated for change in plan.ready] == [False]
    assert openspec_fake.calls == []


# ── The held rule and the real tool ───────────────────────────────────────────


def test_the_clone_tells_who_holds_an_issue(stage_repo: StageRepo, tmp_path: Path) -> None:
    stage_repo.push_branch("fix/7-pushed-work")
    run_git(
        stage_repo.clone, "worktree", "add", "-q", "-b", "feat/8-local-work", str(tmp_path / "w")
    )

    heads = read_remote_heads(stage_repo.clone)

    assert (
        issue_holder(stage_repo.clone, 7, heads)
        == "Issue 7 is held by a pushed branch: origin/fix/7-pushed-work."
    )
    assert "feat/8-local-work" in (issue_holder(stage_repo.clone, 8, heads) or "")
    assert issue_holder(stage_repo.clone, 9, heads) is None


@pytest.mark.live("openspec")
def test_the_files_of_a_plan_pass_openspec_validate(tmp_path: Path) -> None:
    files = render_change(
        "1-the-job-drops-a-comment", make_stage_proposal(), [], created=TODAY.date()
    )
    for path, text in files.items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(text, encoding="utf-8")

    with isolated_openspec() as tool:
        run = tool.run(["validate", "1-the-job-drops-a-comment", "--strict"], tmp_path)

    assert (run.returncode, run.stderr) == (0, "")


@pytest.mark.live("openspec")
@pytest.mark.parametrize(
    ("heading", "name", "expected"),
    [
        ("MODIFIED", "Invented name", "Invented name"),
        ("MODIFIED", "Real name", None),
        ("ADDED", "Fresh name", None),
    ],
)
def test_openspec_refuses_a_modified_requirement_that_the_base_spec_lacks(
    tmp_path: Path, heading: str, name: str, expected: str | None
) -> None:
    source = tmp_path / "source"
    base = source / "openspec" / "specs" / "cap-a" / "spec.md"
    base.parent.mkdir(parents=True)
    base.write_text(
        "## Purpose\nThe base spec of a capability, long enough to pass.\n\n## Requirements\n\n"
        "### Requirement: Real name\nThe system SHALL do a thing.\n\n#### Scenario: Thing\n"
        "- **WHEN** a\n- **THEN** b\n",
        encoding="utf-8",
    )
    files = {
        "openspec/config.yaml": "schema: spec-driven\n",
        "openspec/changes/2-x/proposal.md": (
            "## Why\nBecause.\n\n## What Changes\n- A change.\n\n## Capabilities\n\n"
            "### Modified Capabilities\n- `cap-a`: x\n\n## Impact\n- None.\n"
        ),
        "openspec/changes/2-x/specs/cap-a/spec.md": (
            f"## {heading} Requirements\n\n### Requirement: {name}\nThe system SHALL act.\n\n"
            "#### Scenario: Thing\n- **WHEN** a\n- **THEN** b\n"
        ),
    }

    with isolated_openspec() as tool:
        problem = validate_change(tool, source, "2-x", files)

    if expected is None:
        assert problem is None
    else:
        assert problem is not None
        assert expected in problem
