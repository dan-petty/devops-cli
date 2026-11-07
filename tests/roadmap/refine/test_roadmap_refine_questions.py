"""The questions in the body of an item and in the answer of the model: which ones are open and
which ones a person must answer (#1335).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
import pytest

from devops_cli.roadmap.refine.refine import (
    QuestionAnswer,
    body_questions,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import READY, refine_round, seed_with_body

pytestmark = pytest.mark.usefixtures("keyring_store")


def _first_request(model_fake: ModelFake) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(model_fake.calls[0].prompt)
    return document


_ANSWERED_IN_BODY = (
    "Body\n\n## Key questions\n"
    "- *Which ADR number?* (proposed) The next free one.\n"
    "- *Which files?*\n"
    "  - Decided: each file goes to the package that owns it.\n"
    "- #1336 owns the directory.\n"
)


def test_a_bodys_answered_key_questions_and_its_statements_open_no_question(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A question answered after its question mark or by indented lines, and a bullet with no
    question mark, are not sent and open no question, so one request makes the item Ready."""
    seed_with_body(store, _ANSWERED_IN_BODY)
    model_fake.answer(READY)

    plan = refine_round(store, git_repo)

    assert (
        _first_request(model_fake)["body_questions"],
        plan.refined_items[0].next_step,
        model_fake.call_count,
    ) == ([], "ready", 1)


@pytest.mark.parametrize(
    ("section", "questions"),
    [
        (
            "- How should refine handle a body\n  that wraps across lines?\n",
            ["How should refine handle a body that wraps across lines?"],
        ),
        (
            "- How should refine handle a body\nthat wraps across lines?\n",
            ["How should refine handle a body that wraps across lines?"],
        ),
        (
            "- Which store holds the record?\n\nContext: the Service writes it hourly.\n",
            ["Which store holds the record?"],
        ),
        (
            "### Storage\n- Which backend holds the record?\n### Auth\n- Who owns the key?\n",
            ["Which backend holds the record?", "Who owns the key?"],
        ),
        (
            "- Which command installs the hook?\n\n```sh\n# README today:\nmake hooks\n```\n\n- Does the hook run on push?\n",
            ["Which command installs the hook?", "Does the hook run on push?"],
        ),
        ("- Which format does the export use?\n\n  It is JSON today.\n", []),
        ("- Which store?\n## Next\n- Not this one?\n", ["Which store?"]),
    ],
    ids=[
        "wrapped-indented",
        "wrapped-lazy",
        "paragraph-after",
        "sub-headings",
        "code-fence",
        "indented-answer",
        "next-section",
    ],
)
def test_the_body_questions_follow_markdown(section: str, questions: list[str]) -> None:
    """A wrapped question stays one question, a paragraph or a code block after the list answers
    nothing, a lower heading stays inside the section and a heading of its level ends it, and a
    paragraph indented under the item answers it."""
    assert body_questions(f"Body\n\n## Key questions\n{section}") == questions


def test_a_body_question_that_no_answer_names_is_a_job_failure_not_a_person_wait(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    seed_with_body(store, "Body\n\n## Key questions\n- *Which store holds the record?*\n")
    model_fake.answer(READY)

    plan = refine_round(store, git_repo)

    refined = plan.refined_items[0]
    assert refined.failure is not None
    assert (
        _first_request(model_fake)["body_questions"],
        refined.next_step,
        refined.failure.checks,
        store.comments_on(refined.item.number),
    ) == (
        [{"number": 1, "question": "*Which store holds the record?*"}],
        "retry",
        ("unanswered_question",),
        [],
    )


def test_an_answer_that_names_a_body_question_answers_it(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    seed_with_body(store, "Body\n\n## Key questions\n- *Which store holds the record?*\n")
    answer = QuestionAnswer(
        question="Which store?",
        answer="The job record.",
        kind="decision",
        sources=["src/sample.py"],
        body_question=1,
    )
    model_fake.answer(READY.model_copy(update={"key_questions": [answer]}))

    plan = refine_round(store, git_repo)

    assert (plan.refined_items[0].next_step, model_fake.call_count) == ("ready", 1)
