"""The stage job verifies its plan with a model after the gates and before the draft (#3153)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

import pytest

from devops_cli.ai.client.models import StructuredOutputValidationError
from devops_cli.github.client import CreatedPull
from devops_cli.roadmap.stage.stage import (
    StagePlan,
    _label_needs_fix,
    _notes,
    parse_filters,
    plan_stage,
)
from devops_cli.roadmap.stage.stage_eval_cases import DefectType
from devops_cli.roadmap.stage.stage_toolbox import ToolboxModel
from devops_cli.roadmap.stage.stage_verify import (
    PLAN_NEEDS_FIX_LABEL,
    Finding,
    Verification,
)
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import API, github_json
from tests.support.fakes.model import ModelFake, ModelFakeReplies
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import (
    GONE,
    HOLDS,
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    apply_stage,
    later_review,
    seed_stageable,
    validate_args,
)
from tests.support.scripted_model import Script, call

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from devops_cli.roadmap.stage.stage import StageClient
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

CHANGE = "1-the-job-drops-a-comment"
PULLS = f"/repos/{STAGE_REPO}/pulls"
ISSUE_QUOTE = "The job drops the last comment of a thread."
SAMPLE_QUOTE = "return comments[:-1]"


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    seed_stageable(store)
    return store


@pytest.fixture(autouse=True)
def openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    openspec_fake.script_sequence(
        validate_args(CHANGE), (0, VALID_REPORT), (0, VALID_REPORT), (0, VALID_REPORT)
    )
    return openspec_fake


@pytest.fixture
def verifier() -> ModelFake:
    """The model edge of the verification task, apart from the model edge of the planner."""
    return ModelFake()


def _finding(kind: DefectType, quote: str = "", where: str = "group 1") -> Finding:
    return Finding(type=kind, where=where, problem=f"Problem of {kind.value}.", quote=quote)


def _plan(
    store: InMemoryRoadmapStore,
    repo: StageRepo,
    verifier: ModelFake | None,
    *,
    model: ModelFakeReplies | None = None,
) -> StagePlan:
    return plan_stage(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        filters=parse_filters(()),
        model=cast("StageClient | None", model),
        verifier=ToolboxModel(verifier) if verifier else None,
    )


def _prompts(fake: ModelFake) -> list[dict[str, Any]]:
    return [json.loads(call.prompt) for call in fake.calls]


def test_the_verifier_gets_the_issue_the_plan_and_the_cited_files_once_the_gates_pass(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    model_fake.answer(make_stage_proposal())
    verifier.answer(Verification())

    plan = _plan(store, stage_repo, verifier)

    (request,) = _prompts(verifier)
    assert (len(plan.ready), plan.ready[0].findings) == (1, ())
    assert request["body"] == ISSUE_QUOTE
    assert request["plan"]["summary"] == "Stop the job dropping a comment"
    assert SAMPLE_QUOTE in request["files"]["src/devops_cli/sample.py"]
    assert "tests/test_sample.py" not in request["files"]


def test_the_planner_without_a_verifier_makes_no_verification_call(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    model_fake.answer(make_stage_proposal())

    plan = _plan(store, stage_repo, None)

    assert (model_fake.call_count, len(plan.ready)) == (1, 1)


def test_a_plan_that_the_gates_refuse_twice_gets_no_verification(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    group = make_stage_proposal().groups[0]
    bad = make_stage_proposal(
        groups=[group.model_copy(update={"changes": [*group.changes, "tests/test_missing.py"]})]
    )
    model_fake.answer(bad, bad)

    plan = _plan(store, stage_repo, verifier)

    assert (plan.ready, len(plan.failed), verifier.call_count) == ((), 1, 0)


def test_a_finding_with_an_unknown_type_stops_the_item_and_opens_no_draft(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    model_fake.answer(make_stage_proposal())
    verifier.answer('{"findings": [{"type": "style", "where": "x", "problem": "y", "quote": ""}]}')

    plan = _plan(store, stage_repo, verifier)
    applied = apply_stage(store, plan, source=stage_repo.clone)

    (failure,) = plan.failed
    assert (plan.ready, failure.error) == ((), StructuredOutputValidationError.__name__)
    assert (applied.staged, github_api.requested) == ((), [])


def test_a_false_premise_with_a_quote_returns_the_plan_to_the_planner_once(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    revised = make_stage_proposal(summary="Keep the last comment of a thread")
    model_fake.answer(make_stage_proposal(), revised)
    returned = _finding(DefectType.FALSE_PREMISE, SAMPLE_QUOTE)
    verifier.answer(Verification(findings=[returned]), later_review(GONE))

    plan = _plan(store, stage_repo, verifier)

    first, second = _prompts(model_fake)
    assert "problem" not in first
    assert "false_premise" in second["problem"]
    assert SAMPLE_QUOTE in second["problem"]
    assert second["previous"]["summary"] == "Stop the job dropping a comment"
    (change,) = plan.ready
    assert (
        verifier.call_count,
        change.proposal.summary,
        change.findings,
        change.open_findings,
    ) == (
        2,
        "Keep the last comment of a thread",
        (returned,),
        (),
    )


@pytest.mark.parametrize("kind", [DefectType.CRITERION_DROPPED, DefectType.SPEC_DELTA_WRONG])
def test_a_quoted_open_finding_of_any_open_type_returns_the_plan_to_the_planner(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    kind: DefectType,
) -> None:
    """A finding that keeps the plan in draft also goes back to the planner, so the planner can
    fix it before the draft opens (#5059)."""
    model_fake.answer(make_stage_proposal(), make_stage_proposal(summary="Repaired plan"))
    found = _finding(kind, ISSUE_QUOTE)
    verifier.answer(Verification(findings=[found]), later_review(GONE))

    plan = _plan(store, stage_repo, verifier)

    _, second = _prompts(model_fake)
    assert (kind.value in second["problem"], ISSUE_QUOTE in second["problem"]) == (True, True)
    assert second["previous"]["summary"] == "Stop the job dropping a comment"
    (change,) = plan.ready
    assert (verifier.call_count, change.proposal.summary, change.open_findings) == (
        2,
        "Repaired plan",
        (),
    )


def test_a_placeholder_finding_returns_the_plan_to_the_planner(
    stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    store = _placeholder_store()
    model_fake.answer(make_stage_proposal(), make_stage_proposal(summary="Repaired plan"))
    placeholder = _finding(DefectType.OTHER, "placeholder", where="tasks.md")
    verifier.answer(Verification(findings=[placeholder]), later_review(GONE))

    plan = _plan(store, stage_repo, verifier)

    _, second = _prompts(model_fake)
    assert "placeholder" in second["problem"]
    (change,) = plan.ready
    assert (change.proposal.summary, change.open_findings) == ("Repaired plan", ())


def test_a_return_that_the_planner_answers_with_premise_failed_fails_the_item(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    model_fake.answer(make_stage_proposal(), json.dumps({"premise_failed": "The code is gone."}))
    verifier.answer(Verification(findings=[_finding(DefectType.FALSE_PREMISE, SAMPLE_QUOTE)]))

    plan = _plan(store, stage_repo, verifier, model=model_fake.checking_replies())

    (failure,) = plan.failed
    assert (plan.ready, failure.error, verifier.call_count) == (
        (),
        StructuredOutputValidationError.__name__,
        1,
    )


def test_a_return_that_the_gates_refuse_stops_the_item(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    group = make_stage_proposal().groups[0]
    bad = make_stage_proposal(
        groups=[group.model_copy(update={"changes": [*group.changes, "tests/test_missing.py"]})]
    )
    model_fake.answer(make_stage_proposal(), bad)
    verifier.answer(Verification(findings=[_finding(DefectType.MISSING_PATH, ISSUE_QUOTE)]))

    plan = _plan(store, stage_repo, verifier)

    (failure,) = plan.failed
    assert (plan.ready, failure.error, verifier.call_count) == ((), "RoadmapStageError", 1)


def test_a_finding_whose_quote_is_not_in_the_input_goes_to_the_comment_and_returns_nothing(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    model_fake.answer(make_stage_proposal())
    invented = _finding(DefectType.FALSE_PREMISE, "a line that no file holds")
    verifier.answer(Verification(findings=[invented]))

    plan = _plan(store, stage_repo, verifier)

    (change,) = plan.ready
    assert (model_fake.call_count, verifier.call_count) == (1, 1)
    assert change.findings == (invented,)


def test_a_mixed_first_round_lists_every_finding_and_tells_the_planner_the_open_ones(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    model_fake.answer(make_stage_proposal(), make_stage_proposal(summary="Repaired plan"))
    returned = _finding(DefectType.FALSE_PREMISE, SAMPLE_QUOTE)
    spec = _finding(DefectType.SPEC_DELTA_WRONG, SAMPLE_QUOTE)
    advice = _finding(DefectType.CONTRIVED_TEST, SAMPLE_QUOTE)
    verifier.answer(
        Verification(findings=[returned, spec, advice]),
        later_review(GONE, GONE),
    )

    plan = _plan(store, stage_repo, verifier)

    (change,) = plan.ready
    problem = _prompts(model_fake)[1]["problem"]
    assert (change.findings, change.open_findings) == ((returned, spec, advice), ())
    assert ("false_premise" in problem, "spec_delta_wrong" in problem) == (True, True)
    assert "contrived_test" not in problem


def test_an_open_task_order_finding_keeps_the_draft_with_the_label(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    store = _placeholder_store()
    github_api.route(
        "POST",
        PULLS,
        github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201),
    )
    _seed_pull_5(store)
    finding = _finding(DefectType.TASK_ORDER, SAMPLE_QUOTE)
    model_fake.answer(make_stage_proposal())
    verifier.answer(Verification(findings=[finding]), later_review(HOLDS))

    plan = _plan(store, stage_repo, verifier)
    apply_stage(store, plan, source=stage_repo.clone)

    (change,) = plan.ready
    assert (model_fake.call_count, verifier.call_count) == (3, 3)
    assert change.open_findings == (finding,)
    assert store._roadmap.issues[5].labels == (PLAN_NEEDS_FIX_LABEL,)
    assert json.loads(github_api.sent[0].content)["draft"] is True


def test_a_quote_of_a_file_that_the_verifier_read_past_the_cap_returns_the_plan(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    tail = "def existing_helper_that_does_this(): pass"
    sample = stage_repo.clone / "src/devops_cli/sample.py"
    text = sample.read_text(encoding="utf-8") + "# word\n" * 4000 + f"{tail}\n"
    sample.write_text(text, encoding="utf-8")
    stage_repo.git("commit", "-q", "-am", "A long file")
    stage_repo.git("push", "-q", "origin", "main")
    model_fake.answer(make_stage_proposal(), make_stage_proposal(summary="Repaired plan"))
    finding = _finding(DefectType.IGNORES_EXISTING_CODE, tail)
    reads = Script(
        call("read_file", path="src/devops_cli/sample.py", start_line=4000),
        Verification(findings=[finding]),
        later_review(GONE),
    )

    plan = plan_stage(
        store,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        filters=parse_filters(()),
        verifier=ToolboxModel(reads.model()),
    )

    (change,) = plan.ready
    cited = json.loads(reads.prompt())["files"]["src/devops_cli/sample.py"]
    assert tail not in cited
    assert (change.proposal.summary, change.findings, model_fake.call_count) == (
        "Repaired plan",
        (finding,),
        2,
    )


def test_the_review_takes_its_window_from_the_task_verification_and_not_from_stage(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    config: Callable[..., Path],
) -> None:
    window = 12_000
    config(
        ai={
            "tasks": {
                "stage": {"context_window": 262_144},
                "verification": {"context_window": window},
            }
        }
    )
    model_fake.answer(make_stage_proposal())
    filler = " ".join(f"word{number}" for number in range(window))
    reads = Script(call("search_code", text=filler), Verification())

    plan = plan_stage(
        store,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        filters=parse_filters(()),
        verifier=ToolboxModel(reads.model()),
    )

    # The window of 12,000 tokens ends the tools of the review after one call, so the review run
    # fails the item (#3911), and the reason names the window of the task `verification`.
    request = json.loads(reads.prompt())
    (failure,) = plan.failed
    assert (plan.ready, request["files"]) == ((), {})
    assert (bool(reads.tools_offered[0]), reads.tools_offered[1]) == (True, [])
    assert (failure.error, "12000 tokens" in failure.reason) == ("RoadmapStageError", True)
    assert "ai.tasks.verification.context_window" in failure.reason


def test_the_plan_is_returned_twice_then_stays_in_draft(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    model_fake.answer(
        make_stage_proposal(),
        make_stage_proposal(summary="First repair of the plan"),
        make_stage_proposal(summary="Second repair of the plan"),
    )
    first = _finding(DefectType.FALSE_PREMISE, SAMPLE_QUOTE)
    # A later review opens a new finding only in the text that the revision changed (#5409).
    second = _finding(DefectType.TASK_ORDER, "First repair of the plan")
    last = _finding(DefectType.MISSING_PATH, "Second repair of the plan")
    verifier.answer(
        Verification(findings=[first]),
        later_review(GONE, findings=[second]),
        later_review(GONE, findings=[last]),
    )

    plan = _plan(store, stage_repo, verifier)

    (change,) = plan.ready
    assert (model_fake.call_count, verifier.call_count) == (3, 3)
    assert (change.proposal.summary, change.findings, change.open_findings) == (
        "Second repair of the plan",
        (first, second, last),
        (last,),
    )


def test_the_comment_lists_the_findings_of_each_repair_round_and_each_verifier_read(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    github_api.route(
        "POST",
        PULLS,
        github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201),
    )
    model_fake.answer(make_stage_proposal(), make_stage_proposal(summary="Repaired plan"))
    reads = Script(
        call("read_file", path="src/devops_cli/sample.py"),
        Verification(findings=[_finding(DefectType.FALSE_PREMISE, SAMPLE_QUOTE)]),
        later_review(GONE),
    )

    plan = plan_stage(
        store,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        filters=parse_filters(()),
        verifier=ToolboxModel(reads.model()),
    )
    apply_stage(store, plan, source=stage_repo.clone)

    (comment,) = [c.body for c in store.comments_on(1)]
    assert "Problem of false_premise." in comment
    assert "src/devops_cli/sample.py" in comment


def test_a_contrived_test_finding_is_in_the_comment_and_the_draft_opens_and_stays_a_draft(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    github_api.route(
        "POST",
        PULLS,
        github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201),
    )
    model_fake.answer(make_stage_proposal())
    verifier.answer(
        Verification(findings=[_finding(DefectType.CONTRIVED_TEST, SAMPLE_QUOTE, where="group 1")])
    )

    applied = apply_stage(store, _plan(store, stage_repo, verifier), source=stage_repo.clone)

    (comment,) = [c.body for c in store.comments_on(1)]
    assert applied.staged == (1,)
    assert "contrived_test" in comment
    assert "Problem of contrived_test." in comment
    assert github_api.requested == [f"POST {API}{PULLS}"]
    assert json.loads(github_api.sent[0].content)["draft"] is True


def test_a_comment_without_findings_has_no_findings_section(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    github_api.route(
        "POST",
        PULLS,
        github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201),
    )
    model_fake.answer(make_stage_proposal())
    verifier.answer(Verification())

    apply_stage(store, _plan(store, stage_repo, verifier), source=stage_repo.clone)

    (comment,) = [c.body for c in store.comments_on(1)]
    assert "verification" not in comment.lower()


def _seed_pull_5(store: InMemoryRoadmapStore) -> None:
    """Seed the pull request that the fake create returns, as the store knows it (#3264)."""
    for number in range(2, 5):
        store.seed_issue(f"placeholder {number}")
    store.seed_pull("staging PR", head_ref="fix/1-the-job-drops-a-comment", draft=True)
    assert store._roadmap.issues[5].pull_request is True


def _placeholder_store() -> InMemoryRoadmapStore:
    """A store whose issue text holds the word `placeholder`, so a quote of it is in the input."""
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    seed_stageable(store, body="The job drops a placeholder comment of a thread.")
    return store


def test_a_placeholder_finding_keeps_the_draft_and_applies_the_label(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    store = _placeholder_store()
    github_api.route(
        "POST",
        PULLS,
        github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201),
    )
    _seed_pull_5(store)
    placeholder = _finding(DefectType.OTHER, "placeholder", where="tasks.md")
    model_fake.answer(make_stage_proposal())
    verifier.answer(Verification(findings=[placeholder]), later_review(HOLDS))

    plan = _plan(store, stage_repo, verifier)
    applied = apply_stage(store, plan, source=stage_repo.clone)

    (change,) = plan.ready
    (comment,) = [c.body for c in store.comments_on(1)]
    assert applied.staged == (1,)
    assert change.open_findings == (placeholder,)
    assert store._roadmap.issues[5].labels == (PLAN_NEEDS_FIX_LABEL,)
    assert json.loads(github_api.sent[0].content)["draft"] is True
    assert "placeholder" in comment
    assert (
        _notes(change).strip().startswith("A model review of the plan found these open findings.")
    )


def test_a_clean_review_applies_no_needs_fix_label(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    store = _placeholder_store()
    github_api.route(
        "POST",
        PULLS,
        github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201),
    )
    _seed_pull_5(store)
    model_fake.answer(make_stage_proposal())
    verifier.answer(Verification())

    plan = _plan(store, stage_repo, verifier)
    apply_stage(store, plan, source=stage_repo.clone)

    (change,) = plan.ready
    assert change.open_findings == ()
    assert PLAN_NEEDS_FIX_LABEL not in store._roadmap.issues[5].labels


def test_a_clean_round_removes_the_open_finding_label(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
) -> None:
    store = _placeholder_store()
    _seed_pull_5(store)
    store.label_issue(5, PLAN_NEEDS_FIX_LABEL)
    model_fake.answer(make_stage_proposal())
    verifier.answer(Verification())

    (change,) = _plan(store, stage_repo, verifier).ready
    note = _label_needs_fix(
        store,
        CreatedPull(
            number=5, html_url="https://example.com/pull/5", labels=(PLAN_NEEDS_FIX_LABEL,)
        ),
        change,
    )

    assert note == ""
    assert PLAN_NEEDS_FIX_LABEL not in store._roadmap.issues[5].labels


def test_the_verifier_reads_the_repository_with_the_tools_and_its_reads_are_traced(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    model_fake.answer(make_stage_proposal())
    reads = Script(call("read_file", path="src/devops_cli/sample.py"), Verification())

    plan = plan_stage(
        store,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        filters=parse_filters(()),
        verifier=ToolboxModel(reads.model()),
    )

    trace = plan.ready[0].trace
    assert (len(plan.ready), [record.name for record in trace.tool_calls]) == (
        1,
        ["read_file"],
    )
    assert "read_file" in reads.tools_offered[0]
