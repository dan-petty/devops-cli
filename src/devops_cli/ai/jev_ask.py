"""Ask TypeSafe Jev (`typesafe/jev-1.14`) one question and return a typed answer (#4306).

`devops ai ask-jev` and the MCP tool `ai_ask_jev` call `ask_jev`. One request holds one question
of one kind, the kinds of the System One decision model:

- `choice` picks one of the options. The answer is the option and its probability.
- `noul` is a yes/no question. The answer is the probability of yes.
- `score` rates the text against a rubric of ordered levels. The answer is a score from 0 to the
  last level.

A Jev answer is evidence for a person or an agent to check, not a verdict. The module is a
boundary, because an agent chooses its input:

- It refuses an input larger than `CONST_AI_JEV_ASK_MAX_INPUT_CHARS` before any request.
- It refuses an input that holds a secret, because the request leaves the cluster to the hosted
  model (SECURITY.md, item 13). Project text and code may go to Jev; a secret never does.
- An error and an answer hold neither the key of the gateway nor the text of the input.
"""

from __future__ import annotations

import asyncio
import dataclasses
from collections.abc import Sequence
from typing import Any, cast

from pydantic import JsonValue
from pydantic_ai.exceptions import ModelAPIError, UnexpectedModelBehavior, UserError
from pydantic_ai.models.decision import (
    ChoiceAnswer,
    ChoiceQuestion,
    DecisionModelSettings,
    DecisionQuestion,
    DecisionRequest,
    NoulAnswer,
    NoulCriteria,
    NoulQuestion,
    ScoreAnswer,
    ScoreQuestion,
)

from devops_cli.ai.jev import create_jev_model
from devops_cli.ai.jev_ask_models import JevAnswer, JevAskKind
from devops_cli.config.constants import (
    CONST_AI_JEV_ASK_MAX_INPUT_CHARS,
    CONST_AI_JEV_ASK_MAX_LEVELS,
    CONST_AI_JEV_ASK_MAX_OPTIONS,
    CONST_AI_JEV_ASK_MIN_LEVELS,
    CONST_AI_JEV_ASK_MIN_OPTIONS,
    CONST_AI_JEV_ASK_OPTION_SEPARATOR,
    CONST_AI_JEV_DEFAULT_BOOLEAN_THRESHOLD,
    CONST_AI_JEV_MODEL,
)
from devops_cli.config.settings import Settings, load_settings
from devops_cli.exceptions.ai import LLMInferenceError, ModelGatewayUnreachableError
from devops_cli.exceptions.validation import ValidationError
from devops_cli.lang import MESSAGES
from devops_cli.security.sanitizer import mask_secrets

__all__ = ["ask_jev", "build_jev_request", "jev_request_body"]

# The name of the one question in a request.
_QUESTION_NAME = "answer"


def _parse_options(options: Sequence[str]) -> dict[str, JsonValue]:
    """Map the `label=description` options to the criteria of a choice question.

    An option with no separator is its own description.
    """
    criteria: dict[str, JsonValue] = {}
    for option in options:
        label, separator, description = option.partition(CONST_AI_JEV_ASK_OPTION_SEPARATOR)
        label = label.strip()
        if not label:
            raise ValidationError(MESSAGES.ai.ask_jev_empty_label, field="option")
        if label in criteria:
            raise ValidationError(MESSAGES.ai.ask_jev_duplicate_label, field="option")
        criteria[label] = description.strip() if separator and description.strip() else label
    return criteria


def _check_kind_inputs(
    kind: JevAskKind, options: Sequence[str], levels: Sequence[str], yes: str, no: str
) -> None:
    """Refuse an input that does not belong to the kind, or that is out of bounds."""
    stray = {
        "option": bool(options) and kind is not JevAskKind.CHOICE,
        "level": bool(levels) and kind is not JevAskKind.SCORE,
        "yes": bool(yes) and kind is not JevAskKind.NOUL,
        "no": bool(no) and kind is not JevAskKind.NOUL,
    }
    for name, is_stray in stray.items():
        if is_stray:
            raise ValidationError(
                MESSAGES.ai.ask_jev_stray_input.format(name=name, kind=kind.value), field=name
            )
    if kind is JevAskKind.CHOICE and not (
        CONST_AI_JEV_ASK_MIN_OPTIONS <= len(options) <= CONST_AI_JEV_ASK_MAX_OPTIONS
    ):
        raise ValidationError(
            MESSAGES.ai.ask_jev_option_count.format(
                low=CONST_AI_JEV_ASK_MIN_OPTIONS, high=CONST_AI_JEV_ASK_MAX_OPTIONS
            ),
            field="option",
        )
    if kind is JevAskKind.SCORE and not (
        CONST_AI_JEV_ASK_MIN_LEVELS <= len(levels) <= CONST_AI_JEV_ASK_MAX_LEVELS
    ):
        raise ValidationError(
            MESSAGES.ai.ask_jev_level_count.format(
                low=CONST_AI_JEV_ASK_MIN_LEVELS, high=CONST_AI_JEV_ASK_MAX_LEVELS
            ),
            field="level",
        )


def _check_text(texts: Sequence[str]) -> None:
    """Refuse an input that is larger than the bound or that holds a secret.

    The messages name the rule and never quote the input, which can be a secret.
    """
    size = sum(len(text) for text in texts)
    if size > CONST_AI_JEV_ASK_MAX_INPUT_CHARS:
        raise ValidationError(
            MESSAGES.ai.ask_jev_too_large.format(size=size, limit=CONST_AI_JEV_ASK_MAX_INPUT_CHARS),
            field="question",
        )
    if any(mask_secrets(text) != text for text in texts):
        raise ValidationError(MESSAGES.ai.ask_jev_secret, field="question")


def build_jev_request(
    kind: JevAskKind,
    question: str,
    *,
    context: str = "",
    options: Sequence[str] = (),
    levels: Sequence[str] = (),
    yes: str = "",
    no: str = "",
) -> DecisionRequest:
    """Build the one request, and refuse an input that Jev must not get.

    `context` is the text that Jev decides about; with none, the question is that text. `options`
    are `label=description` strings for `choice`, `levels` are the descriptions of a `score` rubric
    from level 0 up, and `yes` and `no` describe the two outcomes of a `noul` question.
    """
    if not question.strip():
        raise ValidationError(MESSAGES.ai.ask_jev_empty_question, field="question")
    _check_kind_inputs(kind, options, levels, yes, no)
    _check_text([question, context, *options, *levels, yes, no])
    state = context if context.strip() else question
    asked: DecisionQuestion
    if kind is JevAskKind.CHOICE:
        asked = ChoiceQuestion(instructions=question, criteria=_parse_options(options))
    elif kind is JevAskKind.SCORE:
        asked = ScoreQuestion(instructions=question, criteria=list(levels))
    else:
        criteria = NoulCriteria(true=yes or None, false=no or None) if yes or no else None
        asked = NoulQuestion(instructions=question, criteria=criteria)
    return DecisionRequest(state=state, questions={_QUESTION_NAME: asked})


def jev_request_body(request: DecisionRequest) -> dict[str, Any]:
    """The JSON body that the System One endpoint takes for `request`, with unset fields left out."""

    def wire(question: DecisionQuestion) -> dict[str, Any]:
        fields = dataclasses.asdict(question)
        if criteria := fields.get("criteria"):
            if isinstance(criteria, dict):
                fields["criteria"] = {k: v for k, v in criteria.items() if v is not None}
        return {key: value for key, value in fields.items() if value is not None}

    return {
        "state": request.state,
        "model": CONST_AI_JEV_MODEL,
        "questions": {name: wire(question) for name, question in request.questions.items()},
    }


def _typed_answer(
    kind: JevAskKind, raw: Any, model_name: str, input_tokens: int, output_tokens: int
) -> JevAnswer:
    """Read the answer of Jev for one question into the typed result."""
    usage = {"model": model_name, "input_tokens": input_tokens, "output_tokens": output_tokens}
    if kind is JevAskKind.CHOICE:
        choice = cast(ChoiceAnswer, raw)
        return JevAnswer(
            kind=kind,
            answer=choice.choice,
            probability=choice.probabilities.get(choice.choice, 0.0),
            confidence=choice.confidence,
            probabilities=dict(choice.probabilities),
            **usage,
        )
    if kind is JevAskKind.SCORE:
        scored = cast(ScoreAnswer, raw)
        return JevAnswer(
            kind=kind,
            answer=f"{scored.score:g}",
            confidence=scored.confidence,
            score=scored.score,
            probabilities={str(level): p for level, p in sorted(scored.probabilities.items())},
            **usage,
        )
    yes_no = cast(NoulAnswer, raw)
    return JevAnswer(
        kind=kind,
        answer="yes" if yes_no.noul >= CONST_AI_JEV_DEFAULT_BOOLEAN_THRESHOLD else "no",
        probability=yes_no.noul,
        probabilities={"yes": yes_no.noul, "no": round(1.0 - yes_no.noul, 6)},
        **usage,
    )


def ask_jev(
    kind: JevAskKind,
    question: str,
    *,
    context: str = "",
    options: Sequence[str] = (),
    levels: Sequence[str] = (),
    yes: str = "",
    no: str = "",
    settings: Settings | None = None,
) -> JevAnswer:
    """Send one question to Jev and return the typed answer.

    Raises ValidationError before any request when the input is empty, out of bounds or holds a
    secret, and ModelGatewayUnreachableError when the gateway or Jev does not answer.
    """
    request = build_jev_request(
        kind, question, context=context, options=options, levels=levels, yes=yes, no=no
    )
    active = settings or load_settings()
    model = create_jev_model(settings=active)
    model_settings = cast(DecisionModelSettings, dict(getattr(model, "settings", None) or {}))
    try:
        response = asyncio.run(model.decide(request, model_settings))
    except ModelAPIError as exc:
        raise ModelGatewayUnreachableError(
            str(getattr(model, "base_url", CONST_AI_JEV_MODEL)),
            exc,
            consequence=MESSAGES.ai.ask_jev_consequence,
        ) from exc
    except (UnexpectedModelBehavior, UserError) as exc:
        raise LLMInferenceError(
            MESSAGES.ai.ask_jev_unreadable.format(cause=mask_secrets(str(exc))[:200]),
            provider=active.ai.provider,
            model=CONST_AI_JEV_MODEL,
        ) from exc
    usage = response.usage
    return _typed_answer(
        kind,
        response.answers[_QUESTION_NAME],
        response.model_name,
        usage.input_tokens,
        usage.output_tokens,
    )
