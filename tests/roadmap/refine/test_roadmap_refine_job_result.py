"""The `refine` row logs one result line for each item of its round, and the review of the
proposal for an item that a bot opened logs one line for each model call (#4845)."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.ai.client.models import AIClientError
from devops_cli.exceptions import RoadmapRefineError
from devops_cli.roadmap.refine.refine import QuestionAnswer, RefinementProposal
from devops_cli.roadmap.run import MODEL_LANE_ROWS
from devops_cli.roadmap.stage.stage_eval_cases import DefectType, Severity
from devops_cli.roadmap.stage.stage_verify import Finding, Locator, PlanPart, Verification
from devops_cli.roadmap.stores.store import ItemField, RefineRecordKey
from tests.support.roadmap_job_result import result_fields
from tests.support.roadmap_refine import READY, REPO, seed_item, seed_new_items
from tests.support.roadmap_stage import STAGE_NAME

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

pytestmark = pytest.mark.usefixtures("keyring_store", "app_slug")

REFINE_ROW = next(row for row in MODEL_LANE_ROWS if row.name == "refine")
FALSE_PREMISE = Finding(
    type=DefectType.FALSE_PREMISE,
    severity=Severity.MAJOR,
    where=Locator(part=PlanPart.PROPOSAL, section="problem_statement"),
    problem="The issue does not say that the item needs a design.",
    quote=READY.problem_statement,
)


def _document(prompt: str) -> dict[str, Any]:
    """The request document of a prompt, or an empty one for a prompt that is no JSON object."""
    try:
        document = json.loads(prompt)
    except ValueError:
        return {}
    return document if isinstance(document, dict) else {}


def _about(number: int) -> Callable[[str], bool]:
    """The prompts of the requests about item `number`."""
    return lambda prompt: _document(prompt).get("number") == number


def _is_review(prompt: str) -> bool:
    """A request of the review holds the key `plan`, and a request of refine never does."""
    return "plan" in _document(prompt)


def _seed_of_a_bot(store: InMemoryRoadmapStore) -> int:
    store.seed_visibility(is_private=True)
    return store.seed_issue(
        "feat(roadmap): a report",
        body="Make a report.",
        fields={ItemField.STATUS: "New", ItemField.PRIORITY: "P1-High"},
        author_login=STAGE_NAME,
        author_association="CONTRIBUTOR",
    )


def _form_check_failure(*, open_question: bool = False) -> RefinementProposal:
    """A proposal whose first criterion has an empty `then`, and, with `open_question`, a fact
    that no source answers, so its job failure holds a form check beside an open question
    (#6327)."""
    (criterion,) = READY.acceptance_criteria
    proposal = READY.model_copy(
        update={"acceptance_criteria": [criterion.model_copy(update={"then": ""})]}
    )
    if not open_question:
        return proposal
    question = QuestionAnswer(question="Where is the sample function?", answer="?", kind="fact")
    return proposal.model_copy(update={"key_questions": [question]})


def test_a_form_check_failure_writes_its_class_and_its_parts_on_the_result_line(
    store: InMemoryRoadmapStore,
    git_repo: Path,
    model_fake: ModelFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A refine attempt whose job failure holds a form check writes the class `form_check` and
    each failed part of the criterion as a name of its result line (#6327)."""
    seed_item(store, "New", "P1-High")
    model_fake.answer(_form_check_failure())

    with caplog.at_level(logging.INFO):
        REFINE_ROW.runner(store=store, repo=REPO, clone_path=git_repo)

    (line,) = result_fields(caplog)
    assert (line["result"], line["class"], line["failed_1"]) == (
        "retry",
        "form_check",
        "acceptance_criteria.0.then",
    )


def test_a_form_check_beside_an_open_question_writes_the_class_form_check(
    store: InMemoryRoadmapStore,
    git_repo: Path,
    model_fake: ModelFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failure that holds a form check beside an open question is still a form check failure,
    so its line writes no `class=none` (#6327)."""
    number = seed_item(store, "New", "P1-High")
    model_fake.answer(_form_check_failure(open_question=True))

    with caplog.at_level(logging.INFO):
        REFINE_ROW.runner(store=store, repo=REPO, clone_path=git_repo)

    (line,) = result_fields(caplog)
    item = store.item(number)
    assert item is not None
    assert item.job_record.get(RefineRecordKey.FAILED_CHECK) == (
        "acceptance_criteria,missing_source"
    )
    assert (line["result"], line["class"], line["failed_1"]) == (
        "retry",
        "form_check",
        "acceptance_criteria.0.then",
    )


def test_a_round_logs_the_next_step_of_each_item_and_the_class_of_a_failed_model_call(
    store: InMemoryRoadmapStore,
    git_repo: Path,
    model_fake: ModelFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    first, second = seed_new_items(store, ("P1-High", "P2-Medium"))
    model_fake.route_error(_about(second), AIClientError("The provider is down."))
    model_fake.answer(READY)

    with caplog.at_level(logging.INFO), pytest.raises(RoadmapRefineError) as raised:
        REFINE_ROW.runner(store=store, repo=REPO, clone_path=git_repo)

    assert list(raised.value.failed_items) == [second]
    assert result_fields(caplog) == [
        {
            "job": "refine",
            "repo": REPO,
            "item": f"#{number}",
            "result": result,
            "success": success,
            "class": failure,
            "infra": infra,
            "first_pass": first_pass,
            "tries": "1",
            **extra,
        }
        for number, result, success, failure, infra, first_pass, extra in (
            (
                first,
                "ready",
                "true",
                "none",
                "false",
                "true",
                {"context_before": "30", "context_after": "30"},
            ),
            (second, "error", "false", "provider", "true", "false", {}),
        )
    ]


def test_a_ready_proposal_that_waits_on_the_alternatives_verdict_logs_a_success(
    store: InMemoryRoadmapStore,
    git_repo: Path,
    model_fake: ModelFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A ready proposal of a public item with no verdict of the alternatives row waits on that
    verdict (#2951). The wait is the intended result of refine, so the line is a success (#6037)."""
    number = seed_item(store, "New", "P1-High")
    model_fake.answer(READY)

    with caplog.at_level(logging.INFO):
        REFINE_ROW.runner(store=store, repo=REPO, clone_path=git_repo)

    assert [
        (line["item"], line["result"], line["success"], line["first_pass"])
        for line in result_fields(caplog)
    ] == [(f"#{number}", "alternatives", "true", "true")]


@pytest.mark.parametrize(
    ("findings", "verdict", "step", "success"),
    [([], "approved", "ready", "true"), ([FALSE_PREMISE], "refused", "retry", "false")],
)
def test_each_review_of_an_item_of_a_bot_logs_its_verdict_and_its_open_findings(
    store: InMemoryRoadmapStore,
    git_repo: Path,
    model_fake: ModelFake,
    caplog: pytest.LogCaptureFixture,
    findings: list[Finding],
    verdict: str,
    step: str,
    success: str,
) -> None:
    number = _seed_of_a_bot(store)
    model_fake.route(_is_review, Verification(findings=findings))
    model_fake.answer(READY)

    with caplog.at_level(logging.INFO):
        REFINE_ROW.runner(store=store, repo=REPO, clone_path=git_repo)

    assert [
        (line["job"], line["result"], line.get("findings")) for line in result_fields(caplog)
    ] == [
        ("refine_judge", verdict, str(len(findings))),
        ("refine", step, None),
    ]
    assert [line["success"] for line in result_fields(caplog)] == [success, success]
    assert {line["item"] for line in result_fields(caplog)} == {f"#{number}"}
