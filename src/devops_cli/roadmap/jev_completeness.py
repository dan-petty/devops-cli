"""The Jev completeness check of a draft pull request (#4308).

Checks that pass do not say that a draft does what its issue asks. One request to TypeSafe Jev
(`typesafe/jev-1.14`, a System One decision model with no tools and no free text) asks one Noul
question for each acceptance criterion of the issue ("does the draft deliver it?") and one Score
question for the strength of the tests. The diff and the criteria are inline text in the request.

The check can only hold a draft. A criterion with a probability below
`CONST_ROADMAP_JEV_CRITERION_THRESHOLD`, a test score below `CONST_ROADMAP_JEV_MIN_TEST_SCORE`, or
an error of Jev holds the draft, and `completeness_note` lists the doubts for the note that the
caller posts. A pass is no reason to mark a draft ready: the checks and a person still decide. A
diff over `CONST_ROADMAP_JEV_MAX_DIFF_TOKENS`, an issue with no criterion or with more than
`CONST_ROADMAP_JEV_MAX_CRITERIA` criteria skips the check with a logged reason. The check counts
its outcome in `devops_cli_roadmap_jev_completeness_total`.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final, Literal, cast

from pydantic import JsonValue
from pydantic_ai.exceptions import AgentRunError, UserError
from pydantic_ai.models.decision import (
    DecisionModel,
    DecisionQuestion,
    DecisionRequest,
    NoulAnswer,
    NoulQuestion,
    ScoreAnswer,
    ScoreQuestion,
)

from devops_cli.ai.context_budget import count_tokens
from devops_cli.ai.jev import create_jev_model, decide_with_jev
from devops_cli.config.constants import (
    CONST_ROADMAP_JEV_CRITERION_THRESHOLD,
    CONST_ROADMAP_JEV_MAX_CRITERIA,
    CONST_ROADMAP_JEV_MAX_DIFF_TOKENS,
    CONST_ROADMAP_JEV_MIN_TEST_SCORE,
)
from devops_cli.config.settings import Settings
from devops_cli.lang import MESSAGES
from devops_cli.telemetry.instruments import ROADMAP_JEV_COMPLETENESS_TOTAL, emit

logger = logging.getLogger(__name__)

DraftSubject = Literal["plan", "change"]
"""What the diff holds: the files of a plan, or the files of a change to the code."""

_TESTS_KEY: Final[str] = "tests"
_TEST_RUBRIC: Final[list[JsonValue]] = [
    "0: The draft changes behavior and no test asserts it.",
    "1: Tests exist, but they run the code and assert little of the new behavior.",
    "2: Tests assert most of the new behavior.",
    "3: Tests assert each new behavior, including the failure paths.",
]


class CompletenessOutcome(StrEnum):
    """What the check found: every criterion is delivered, a doubt or an error holds the draft,
    or the check did not run."""

    PASSED = "passed"
    HELD = "held"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class Doubt:
    """A criterion that Jev doubts the draft delivers, with the probability that it does."""

    criterion: str
    probability: float


@dataclass(frozen=True)
class Completeness:
    """The result of the check. `probabilities` holds one value for each criterion, in order, and
    `test_score` the score of the tests, both empty when the check did not get an answer.
    `input_tokens` is what Jev counted in the request."""

    outcome: CompletenessOutcome
    doubts: tuple[Doubt, ...] = ()
    probabilities: tuple[float, ...] = ()
    test_score: float | None = None
    reason: str = ""
    input_tokens: int = 0

    @property
    def holds(self) -> bool:
        """Whether the draft stays a draft: a doubt or an error of Jev."""
        return self.outcome in (CompletenessOutcome.HELD, CompletenessOutcome.ERROR)


def _criterion_key(index: int) -> str:
    return f"criterion_{index}"


def build_request(criteria: Sequence[str], diff: str, subject: DraftSubject) -> DecisionRequest:
    """The one request of the check: the diff and the criteria as state, one Noul question for
    each criterion and one Score question for the tests."""
    texts = MESSAGES.roadmap
    question = (
        texts.jev_completeness_question_plan
        if subject == "plan"
        else (texts.jev_completeness_question_change)
    )
    questions: dict[str, DecisionQuestion] = {
        _criterion_key(number): NoulQuestion(instructions=question.format(criterion=criterion))
        for number, criterion in enumerate(criteria, start=1)
    }
    questions[_TESTS_KEY] = ScoreQuestion(
        instructions=(
            texts.jev_completeness_tests_plan
            if subject == "plan"
            else texts.jev_completeness_tests_change
        ),
        criteria=list(_TEST_RUBRIC),
    )
    state: dict[str, JsonValue] = {
        "subject": subject,
        "criteria": {_criterion_key(n): text for n, text in enumerate(criteria, start=1)},
        "diff": diff,
    }
    return DecisionRequest(state=state, questions=questions)


def _skipped(reason: str) -> Completeness:
    logger.info("The Jev completeness check is skipped: %s", reason)
    return Completeness(CompletenessOutcome.SKIPPED, reason=reason)


def _count(outcome: CompletenessOutcome) -> None:
    """Add 1 to the counter of `outcome` and 0 to the others, so the four series exist."""
    for each in CompletenessOutcome:
        emit(ROADMAP_JEV_COMPLETENESS_TOTAL, 1 if each is outcome else 0, {"outcome": each.value})


def assess(
    criteria: Sequence[str],
    diff: str,
    subject: DraftSubject,
    *,
    model: DecisionModel[Any] | None = None,
    settings: Settings | None = None,
) -> Completeness:
    """Ask Jev whether the draft delivers each acceptance criterion, and count nothing. The eval
    uses this; `check_completeness` is the call of a job."""
    texts = MESSAGES.roadmap
    if not criteria:
        return _skipped(texts.jev_completeness_skip_no_criteria)
    if len(criteria) > CONST_ROADMAP_JEV_MAX_CRITERIA:
        return _skipped(
            texts.jev_completeness_skip_criteria.format(
                count=len(criteria), limit=CONST_ROADMAP_JEV_MAX_CRITERIA
            )
        )
    tokens = count_tokens(diff)
    if tokens > CONST_ROADMAP_JEV_MAX_DIFF_TOKENS:
        return _skipped(
            texts.jev_completeness_skip_diff.format(
                tokens=tokens, limit=CONST_ROADMAP_JEV_MAX_DIFF_TOKENS
            )
        )
    request = build_request(criteria, diff, subject)
    try:
        decision_model = model or create_jev_model(settings=settings)
        response = decide_with_jev(request, model=decision_model)
    except (AgentRunError, UserError) as exc:
        logger.warning("The Jev completeness check got no answer: %s", exc)
        return Completeness(CompletenessOutcome.ERROR, reason=str(exc))
    probabilities = tuple(
        cast(NoulAnswer, response.answers[_criterion_key(number)]).noul
        for number in range(1, len(criteria) + 1)
    )
    score = cast(ScoreAnswer, response.answers[_TESTS_KEY]).score
    doubts = tuple(
        Doubt(criterion, probability)
        for criterion, probability in zip(criteria, probabilities, strict=True)
        if probability < CONST_ROADMAP_JEV_CRITERION_THRESHOLD
    )
    weak_tests = score < CONST_ROADMAP_JEV_MIN_TEST_SCORE
    outcome = CompletenessOutcome.HELD if doubts or weak_tests else CompletenessOutcome.PASSED
    tokens = int(response.usage.input_tokens or 0)
    return Completeness(outcome, doubts, probabilities, score, input_tokens=tokens)


def check_completeness(
    criteria: Sequence[str],
    diff: str,
    subject: DraftSubject,
    *,
    model: DecisionModel[Any] | None = None,
    settings: Settings | None = None,
) -> Completeness:
    """Ask Jev whether the draft delivers each acceptance criterion, and count the outcome.

    One request holds all the questions. An error of the request is no exception: it is the
    outcome `error`, which holds the draft, and the log holds the cause.
    """
    result = assess(criteria, diff, subject, model=model, settings=settings)
    _count(result.outcome)
    return result


def completeness_note(result: Completeness, pull: int) -> str:
    """The note on the draft pull request `pull` that lists what Jev doubts, or the error."""
    texts = MESSAGES.roadmap
    if result.outcome is CompletenessOutcome.ERROR:
        return texts.jev_completeness_note_error.format(pull=pull, reason=result.reason)
    lines = [
        texts.jev_completeness_note_doubt.format(
            criterion=doubt.criterion, percent=round(doubt.probability * 100)
        )
        for doubt in result.doubts
    ]
    if result.test_score is not None and result.test_score < CONST_ROADMAP_JEV_MIN_TEST_SCORE:
        lines.append(texts.jev_completeness_note_tests.format(score=f"{result.test_score:.1f}"))
    return texts.jev_completeness_note.format(pull=pull, doubts="\n".join(lines))


__all__ = [
    "Completeness",
    "CompletenessOutcome",
    "Doubt",
    "assess",
    "build_request",
    "check_completeness",
    "completeness_note",
]
