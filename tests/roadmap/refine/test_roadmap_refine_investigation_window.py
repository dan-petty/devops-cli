"""Tests for the window estimate of an investigation run (#4221): `tokens_of` follows the input
that the last reply reports, and `_limit_reached` keeps the function tools offered while that input
leaves room for a reply.

The messages of a run are built by hand, as a provider returns them, so no test reaches a model.
A streamed `FunctionModel` cannot set the usage of its replies, so a run test cannot report the
real counts of a provider.
"""

from __future__ import annotations

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext
from pydantic_ai.usage import RequestUsage, RunUsage, UsageLimits

from devops_cli.ai.context_budget import count_tokens
from devops_cli.config.constants import (
    CONST_ROADMAP_REFINE_INVESTIGATION_MAX_REQUESTS,
    CONST_ROADMAP_REFINE_INVESTIGATION_MAX_TOOL_CALLS,
)
from devops_cli.roadmap.agent_run import RunLimit
from devops_cli.roadmap.refine.refine_investigation import _limit_reached, tokens_of, tool_stop

# The input that the provider reported for the last reply of the live run of 2026-11-09, which had
# a window of 200000 tokens (#4221).
_REPORTED = 105_412
_WINDOW = 200_000
_INSTRUCTIONS = "Plan the item. Read the files first."
_PROMPT = "The item is to be planned. Read the files that it names."


def _file_text(first: int, lines: int) -> str:
    """The text of a `read_file` answer: numbered lines of code with quotes, backslashes and
    tabs, which the JSON form of a message escapes."""
    return "\n".join(
        f'{n:>5}\t    pattern_{n} = re.compile(r"\\d+\\s*\\"{n}\\"")  # "quoted" step {n}'
        for n in range(first, first + lines)
    )


def _read_call(index: int, *, input_tokens: int, output_tokens: int = 210) -> ModelResponse:
    """A reply that calls `read_file`, with the usage that the provider reported for it."""
    return ModelResponse(
        parts=[ToolCallPart("read_file", {"path": "src/a.py"}, tool_call_id=f"call-{index}")],
        usage=RequestUsage(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def _answer(index: int, text: str) -> ModelRequest:
    return ModelRequest(
        parts=[ToolReturnPart("read_file", text, tool_call_id=f"call-{index}")],
    )


def _run_messages(*, last_input: int, answers: list[str], tail: str) -> list[ModelMessage]:
    """The messages of a run at the hook of its fifth request: the first request, then four replies
    that call `read_file`, each followed by its answer. The last reply reports `last_input`; the
    reply before it reports less by the answers that came between. `tail` is the last answer."""
    reported = [1_700, 48_700, 95_700, last_input]
    messages: list[ModelMessage] = [
        ModelRequest(parts=[UserPromptPart(_PROMPT)], instructions=_INSTRUCTIONS)
    ]
    for index, text in enumerate([*answers, tail]):
        messages.append(_read_call(index, input_tokens=reported[index]))
        messages.append(_answer(index, text))
    return messages


def _big_run(*, last_input: int = _REPORTED, tail: str | None = None) -> list[ModelMessage]:
    """Three big files read, then a short answer. The tiktoken count of the files is above the
    reported input: the tokenizer of a provider counts the same text in fewer tokens, and the JSON
    form of the messages is longer than the text again."""
    answers = [_file_text(1, 2000), _file_text(2001, 2000), _file_text(4001, 500)]
    return _run_messages(last_input=last_input, answers=answers, tail=tail or _file_text(1, 20))


def _context(messages: list[ModelMessage]) -> RunContext[None]:
    """The context of the hook at the fifth request, with the limits of an investigation."""
    return RunContext(
        deps=None,
        model=TestModel(),
        usage=RunUsage(requests=4, tool_calls=4),
        usage_limits=UsageLimits(
            request_limit=CONST_ROADMAP_REFINE_INVESTIGATION_MAX_REQUESTS,
            tool_calls_limit=CONST_ROADMAP_REFINE_INVESTIGATION_MAX_TOOL_CALLS,
        ),
        messages=messages,
    )


def _texts_of(messages: list[ModelMessage]) -> int:
    """The tokens of the text that the model reads in `messages`: the instructions, the user
    prompts, the tool calls and the tool answers."""
    texts: list[str] = []
    for message in messages:
        if isinstance(message, ModelRequest) and message.instructions:
            texts.append(message.instructions)
        for part in message.parts:
            if isinstance(part, UserPromptPart | ToolReturnPart):
                texts.append(str(part.content))
            elif isinstance(part, ToolCallPart):
                texts.append(part.args_as_json_str())
            elif isinstance(part, TextPart):
                texts.append(part.content)
    return int(count_tokens("\n".join(texts)))


def test_the_estimate_follows_the_input_that_the_last_reply_reports() -> None:
    """The estimate is the input of the last reply, its output, and the tokens that were added
    after it. It is within 10 percent of the input of the provider, and no fixed factor is used."""
    estimate = tokens_of(_big_run())

    assert abs(estimate - _REPORTED) <= _REPORTED // 10


def test_the_function_tools_stay_offered_while_the_reported_input_leaves_room() -> None:
    """The reported input is 105,412 tokens and the limit of a window of 200000 is 150,000, so
    the request offers its tools. The live run offered none at this input."""
    assert (_limit_reached(_context(_big_run()), _WINDOW), tool_stop(_WINDOW)) == (None, 150_000)


def test_the_tools_go_when_the_reported_input_has_no_room_for_a_reply() -> None:
    """The last reply reports 149,900 tokens, so its output and the answer after it pass the
    limit of 150,000 tokens."""
    messages = _big_run(last_input=149_900)

    assert _limit_reached(_context(messages), _WINDOW) is RunLimit.WINDOW


def test_the_tokens_added_after_the_last_reply_count_toward_the_limit() -> None:
    """The last reply reports 140,000 tokens, and the answer after it holds more than 10,000."""
    messages = _big_run(last_input=140_000, tail=_file_text(1, 400))

    assert _limit_reached(_context(messages), _WINDOW) is RunLimit.WINDOW


def test_the_first_request_counts_its_text_and_not_its_json() -> None:
    """A run with no reply yet has no reported input. The estimate is the count of the instructions
    and the user prompt, as the model reads them."""
    prompt = _file_text(1, 400)
    request = ModelRequest(parts=[UserPromptPart(prompt)], instructions=_INSTRUCTIONS)
    text = count_tokens(_INSTRUCTIONS) + count_tokens(prompt)

    assert abs(tokens_of([request]) - text) <= text // 50


def test_a_reply_that_reports_no_input_counts_the_text_of_the_messages() -> None:
    """A provider can omit the usage. The estimate is then the count of the text of every message,
    and not of the JSON form."""
    messages = _big_run(last_input=0)
    for index, message in enumerate(messages):
        if isinstance(message, ModelResponse):
            messages[index] = ModelResponse(parts=message.parts, usage=RequestUsage())
    text = _texts_of(messages)

    assert abs(tokens_of(messages) - text) <= text // 50
