"""The stage job verifies its plan with a model after the gates and before the draft (#3153)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

import pytest

from devops_cli.ai.client.models import StructuredOutputValidationError
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.stage import StagePlan, apply_stage, parse_filters, plan_stage
from devops_cli.roadmap.stage_change import StageProposal
from devops_cli.roadmap.stage_eval_cases import DefectType
from devops_cli.roadmap.stage_verify import Finding, Verification
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import API, github_json
from tests.support.fakes.model import ModelFake
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    seed_stageable,
    validate_args,
)

if TYPE_CHECKING:
    from devops_cli.roadmap.stage import StageClient
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


def _plan(store: InMemoryRoadmapStore, repo: StageRepo, verifier: ModelFake | None) -> StagePlan:
    return plan_stage(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        filters=parse_filters(()),
        verifier=cast("StageClient", verifier.checking_replies()) if verifier else None,
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
    verifier.answer(
        Verification(findings=[_finding(DefectType.FALSE_PREMISE, SAMPLE_QUOTE)]), Verification()
    )

    plan = _plan(store, stage_repo, verifier)

    first, second = _prompts(model_fake)
    assert "problem" not in first
    assert "false_premise" in second["problem"]
    assert SAMPLE_QUOTE in second["problem"]
    assert second["previous"]["summary"] == "Stop the job dropping a comment"
    (change,) = plan.ready
    assert (verifier.call_count, change.proposal.summary, change.findings) == (
        2,
        "Keep the last comment of a thread",
        (),
    )


def test_a_return_that_the_planner_answers_with_premise_failed_returns_the_item(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    model_fake.answer(
        make_stage_proposal(), StageProposal.model_validate({"premise_failed": "The code is gone."})
    )
    verifier.answer(Verification(findings=[_finding(DefectType.FALSE_PREMISE, SAMPLE_QUOTE)]))

    plan = _plan(store, stage_repo, verifier)

    (returned,) = plan.returned
    assert (plan.ready, returned.evidence, verifier.call_count) == ((), "The code is gone.", 1)


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


def test_the_revised_plan_is_not_returned_again(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, verifier: ModelFake
) -> None:
    model_fake.answer(make_stage_proposal(), make_stage_proposal(summary="Keep every comment"))
    again = _finding(DefectType.MISSING_PATH, ISSUE_QUOTE)
    verifier.answer(
        Verification(findings=[_finding(DefectType.FALSE_PREMISE, SAMPLE_QUOTE)]),
        Verification(findings=[again]),
    )

    plan = _plan(store, stage_repo, verifier)

    (change,) = plan.ready
    assert (model_fake.call_count, verifier.call_count, change.findings) == (2, 2, (again,))


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
