"""What the roadmap jobs that run a pydantic-ai agent share (#2398, #2664): the stream handler
that keeps a long reply inside the gateway's tunnel, and the spend record of a run."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import AsyncIterable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit

from pydantic_ai import RunContext
from pydantic_ai.exceptions import (
    AgentRunError,
    ModelAPIError,
    ModelConnectionError,
    ModelHTTPError,
    ModelTimeoutError,
)
from pydantic_ai.messages import (
    AgentStreamEvent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    ToolCallPart,
    ToolReturn,
    ToolReturnPart,
)

from devops_cli.ai.client.models import AIClientError, AICredentialsError
from devops_cli.ai.schema_reflection import ViolationText
from devops_cli.ai.spend import track_request_spend
from devops_cli.config.constants import (
    CONST_AI_GATEWAY_PROVIDER,
    CONST_ROADMAP_RUN_ERROR_CHARS,
    CONST_ROADMAP_RUN_ERROR_READ_CHARS,
    CONST_ROADMAP_RUN_TRACE_ARGUMENT_CHARS,
    CONST_ROADMAP_STAGE_VIOLATIONS_SHOWN,
)
from devops_cli.security.sanitizer import mask_secret_named_values, mask_secrets

# The HTTP statuses of a model reply that refuse the key, which stop the whole run.
_REFUSED_KEY_STATUSES = frozenset({401, 403})


async def drain_events(_ctx: RunContext[None], events: AsyncIterable[AgentStreamEvent]) -> None:
    """Read the run's events. With a handler, pydantic-ai streams each model request, so a long
    reply keeps the gateway's tunnel open past its cut of 125 s, as `LLMClient` streams (#2379)."""
    async for _ in events:
        pass


def model_call_error(exc: ModelAPIError, subject: str) -> AIClientError:
    """The job's class for a failed model call of a run, with no text of the model's reply, and
    with the HTTP status or the timeout of the call (#2562). A failed transport also names its
    phase and the error of the HTTP library, so a report tells a dropped stream from a refused
    connection (#4345). `subject` names the run, such as `The investigation's`."""
    if isinstance(exc, ModelHTTPError) and exc.status_code in _REFUSED_KEY_STATUSES:
        return AICredentialsError(f"The model refused the key (HTTP {exc.status_code}).")
    return AIClientError(
        f"{subject} model call failed ({type(exc).__name__}{_transport_cause(exc)}).",
        status=exc.status_code if isinstance(exc, ModelHTTPError) else None,
        timed_out=isinstance(exc, ModelTimeoutError),
    )


def _transport_cause(exc: ModelAPIError) -> str:
    """The phase of a failed transport and the first error of its chain, masked and cut, after a
    comma, or an empty text. pydantic-ai keeps the error of the SDK as `__cause__`, and the SDK
    keeps the error of the HTTP library as its own, so the first error is the one of the HTTP
    library. A transport error holds no text of a model reply."""
    if not isinstance(exc, ModelConnectionError) or exc.__cause__ is None:
        return ""
    first: BaseException = exc.__cause__
    seen = {id(first)}
    while first.__cause__ is not None and id(first.__cause__) not in seen:
        first = first.__cause__
        seen.add(id(first))
    phase = f", phase {exc.phase}" if exc.phase else ""
    text = bounded_text(str(first))
    return f"{phase}, {type(first).__name__}" + (f": {text}" if text else "")


def bounded_text(text: str) -> str:
    """`text`, masked and cut to `CONST_ROADMAP_RUN_ERROR_CHARS` characters. The text is cut to a
    multiple of that limit before the masking, which is slower than linear, and the masked text is
    cut after, so a cut cannot split a secret."""
    masked = mask_secrets(text[:CONST_ROADMAP_RUN_ERROR_READ_CHARS]).strip()
    return masked[:CONST_ROADMAP_RUN_ERROR_CHARS]


# A provider can echo what the model wrote into its error text, as Ollama does in `raw='...'`.
# So the text of a body hides each quoted part and a quote that is not closed, and stops at the
# first `=` or `;`, where the echo of a value begins (#2794).
_BODY_QUOTED = re.compile(r"""(['"`]).*?(?:\1|$)""")
_BODY_DATA = re.compile(r"[;=]")
# The gateway wraps the error text of Ollama in the repr of a dict at the end of its message:
# `Got unexpected response from Ollama: {'error': '<text>'}`. Only that shape is unwrapped, and
# its text then goes through the same guards as any other, so its quoted words stay hidden (#2922).
_BODY_WRAPPED = re.compile(r"""\{'error': (?:'(?P<single>[^']*)'|"(?P<double>[^"]*)")\}$""")


def _body_string(body: object) -> str:
    """The error text in the `body` of a model's error reply: the body when it is a string, else
    its `message`, else its `error`, read the same way. No other value of a body is read, for
    `mask_secrets` finds a secret by its form in a text, and not the value of a key such as
    `api_key` in the repr of a dict."""
    if isinstance(body, str):
        return body
    if isinstance(body, Mapping):
        return next(
            (text for key in ("message", "error") if (text := _body_string(body.get(key)))), ""
        )
    return ""


def body_error_text(body: object) -> str:
    """The error text in the `body` of a model's error reply, safe to show: masked and cut like
    other stop text, then reduced to the part that the provider wrote and not the model: the error
    text of a gateway wrapper when there is one (#2922)."""
    first = (_body_string(body).splitlines() or [""])[0]
    text = bounded_text(first)
    if wrapped := _BODY_WRAPPED.search(text):
        text = wrapped["single"] or wrapped["double"] or ""
    description = _BODY_DATA.split(_BODY_QUOTED.sub("<text>", text), maxsplit=1)[0]
    return "".join(char for char in description if char.isprintable()).strip()


# A part of a message in quotes, such as a tool name, and the characters from which pydantic-ai
# writes data of the reply of the model into a message (#2562).
_QUOTED = re.compile(r"""(['"`]).*?\1""")
_REPLY_DATA = re.compile(r"""[:;='"`]""")


def run_error_message(stopped: AgentRunError) -> str:
    """The fixed description in the `message` of a pydantic-ai error, to log (#2562).

    It is not `str(stopped)`: for `UnexpectedModelBehavior` that adds the `body`, the text of the
    model. The message itself can hold data that the model chose: the id of a tool call, the name
    of a tool, the repr of a part. So it keeps the first line only, hides each quoted part, and
    stops at the first `:`, `;` or `=`. It then drops the characters that cannot print.
    """
    first = (stopped.message.splitlines() or [""])[0]
    hidden = _QUOTED.sub("<text>", bounded_text(first))
    description = _REPLY_DATA.split(hidden, maxsplit=1)[0]
    return "".join(char for char in description if char.isprintable()).strip()


def argument_json(call: ToolCallPart) -> str:
    """The argument of a tool call as compact JSON, with each value under a secret-suggesting name
    hidden. A model writes the argument, so a secret in it would reach the trace comment (#3222).
    `bounded_text` masks the rest by form. An argument that is no JSON object is already wrapped
    by pydantic-ai as `{"INVALID_JSON": <text>}`."""
    return json.dumps(
        mask_secret_named_values(call.args_as_dict()),
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


class ToolOutcome(StrEnum):
    """How a tool call ended, as `devops_cli_roadmap_tool_calls_total` labels it (#3240): `ok` for
    an answer with the result that the call asked for, `empty` for a call that ran and found
    nothing, and `error` for a call that could not run or got no answer. A tool of the stage
    planner marks each answer with `ok_answer`, `empty_answer` or `error_answer`. A tool that
    marks none gives `ok`, or `empty` when its text has no non-whitespace character."""

    OK = "ok"
    EMPTY = "empty"
    ERROR = "error"


def ok_answer(text: str) -> ToolReturn:
    """The answer of a tool call that gave the result it was asked for: `text` is what the model
    reads, and the run reads the outcome `ok` (#3240). A tool is annotated with a bare `ToolReturn`
    because pydantic-ai builds the return schema of each tool when it makes the tool, and the
    schema of a union that holds `ToolReturn` takes about 20 ms for each tool."""
    return ToolReturn(text, metadata=ToolOutcome.OK)


def empty_answer(text: str) -> ToolReturn:
    """The answer of a tool call that ran and found nothing, such as a search with no match: `text`
    is what the model reads, and the run reads the outcome `empty` (#3240)."""
    return ToolReturn(text, metadata=ToolOutcome.EMPTY)


def error_answer(text: str) -> ToolReturn:
    """The answer of a tool call that could not run, such as a path outside the repository, a
    missing file or a read that failed: `text` is what the model reads, and the run reads the
    outcome `error`. A tool answers its failure so, and does not raise, so no call of the model
    can stop the run (#3240)."""
    return ToolReturn(text, metadata=ToolOutcome.ERROR)


class RunLimit(StrEnum):
    """The limit that ended the tools of a run, as `devops_cli_roadmap_tool_limit_hits_total`
    labels it (#3240): the calls, the requests or the context window."""

    CALLS = "calls"
    REQUESTS = "requests"
    WINDOW = "window"


@dataclass(frozen=True)
class ToolCallRecord:
    """One tool call of a run: the tool, its argument as JSON, masked and cut, how the call ended,
    the characters of its answer, after the cut of the tool (None for a call with no answer), and
    its timeout in seconds when bounded (#3221)."""

    name: str
    argument: str
    outcome: ToolOutcome = ToolOutcome.OK
    chars: int | None = None
    timeout: float | None = None


@dataclass
class RunTrace:
    """What a run of an agent did (#3037): its tool calls in order, the count of its model
    requests, its input and output tokens, the count of schema violations in the last retry
    prompt of its output tool, the masked text of the first of them (#4269), the names of the function tools that each request offered, in
    order (#3477), and the text of each tool answer, which a quote of the run may come from
    (#3039). A request that offered none holds an empty tuple. `limit` is the limit that ended the
    tools of the run, or None (#3240). `last_input_tokens` is the input of the last request, the one
    that the last reply answered (#4204). `row` is the job row of the run, such as the plan or the
    review of the stage job, and is empty for a run that no job names (#4257). `finish_reason` and
    `answered` are the stop reason and the model name of the last reply, and are empty when the
    provider gave none (#4313)."""

    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    violations: int = 0
    violation_texts: tuple[ViolationText, ...] = ()
    offered: list[tuple[str, ...]] = field(default_factory=list)
    limit: RunLimit | None = None
    tool_answers: list[str] = field(default_factory=list)
    last_input_tokens: int = 0
    finish_reason: str = ""
    answered: str = ""
    row: str = ""

    @classmethod
    def combined(cls, traces: Iterable[RunTrace]) -> RunTrace:
        """One trace for all `traces`, in order: their tool calls and offers joined and their counts
        summed. The violations and the limit are those of the last trace that had any."""
        total = cls()
        for trace in traces:
            total.tool_calls.extend(trace.tool_calls)
            total.offered.extend(trace.offered)
            total.tool_answers.extend(trace.tool_answers)
            total.requests += trace.requests
            total.input_tokens += trace.input_tokens
            total.output_tokens += trace.output_tokens
            total.violations = trace.violations or total.violations
            total.violation_texts = trace.violation_texts or total.violation_texts
            total.last_input_tokens = trace.last_input_tokens or total.last_input_tokens
            total.finish_reason = trace.finish_reason or total.finish_reason
            total.answered = trace.answered or total.answered
            total.limit = trace.limit or total.limit
        return total

    def tool_counts(self) -> dict[str, tuple[int, int]]:
        """The calls and the empty answers of each tool of the trace, as `(calls, empty)`, in the
        alphabetical order of the tool names (#3240)."""
        calls = Counter(record.name for record in self.tool_calls)
        empty = Counter(r.name for r in self.tool_calls if r.outcome is ToolOutcome.EMPTY)
        return {name: (calls[name], empty[name]) for name in sorted(calls)}

    def absorb(
        self,
        messages: Sequence[ModelMessage],
        *,
        tools: Collection[str],
        offered: Iterable[tuple[str, ...]] = (),
        limit: RunLimit | None = None,
    ) -> None:
        """Add the run of `messages` to the trace. `tools` are the names of the function tools of
        the run: a call to any other tool is the output tool's and is no tool call of the trace.
        `offered` holds the tools that each request offered, which the messages do not record.
        `limit` is the limit that ended the tools of the run. The outcome and the answer size of a
        call come from the part that answers it in the request after the reply, by the id of the
        call: a call with no answer is an error (#3240)."""
        self.offered.extend(offered)
        self.limit = limit or self.limit
        for index, message in enumerate(messages):
            if isinstance(message, ModelResponse):
                # The request after a reply holds the answers to its calls.
                self._add_reply(message, tools, _answers(messages[index + 1 : index + 2]))
            elif isinstance(message, ModelRequest):
                self._add_violations(message, tools)
                self.tool_answers.extend(
                    str(part.content)
                    for part in message.parts
                    if isinstance(part, ToolReturnPart) and part.tool_name in tools
                )

    def _add_reply(
        self,
        reply: ModelResponse,
        tools: Collection[str],
        answers: Mapping[str, ToolReturnPart | RetryPromptPart],
    ) -> None:
        self.requests += 1
        self.last_input_tokens = reply.usage.input_tokens
        self.finish_reason = reply.finish_reason or ""
        self.answered = reply.model_name or ""
        self.input_tokens += reply.usage.input_tokens
        self.output_tokens += reply.usage.output_tokens
        for part in reply.parts:
            if isinstance(part, ToolCallPart) and part.tool_name in tools:
                argument = bounded_text(argument_json(part))
                outcome, chars, timeout = _outcome_of(answers.get(part.tool_call_id))
                self.tool_calls.append(
                    ToolCallRecord(
                        part.tool_name,
                        argument[:CONST_ROADMAP_RUN_TRACE_ARGUMENT_CHARS],
                        outcome,
                        chars,
                        timeout=timeout,
                    )
                )

    def _add_violations(self, request: ModelRequest, tools: Collection[str]) -> None:
        for part in request.parts:
            if isinstance(part, RetryPromptPart) and part.tool_name not in tools:
                errors = part.content if isinstance(part.content, list) else []
                self.violations = len(errors)
                self.violation_texts = tuple(
                    _violation_text(error)
                    for error in errors[:CONST_ROADMAP_STAGE_VIOLATIONS_SHOWN]
                )


def _violation_text(error: Mapping[str, Any]) -> ViolationText:
    """The text of one pydantic error of a retry prompt: its location joined by dots (`root` for a
    reply that is no JSON object), its type and its message. The input value of the error is
    dropped."""
    loc = ".".join(str(step) for step in error.get("loc", ())) or "root"
    return ViolationText(
        loc=loc, type=str(error.get("type", "")), message=str(error.get("msg", ""))
    )


def _answers(messages: Sequence[ModelMessage]) -> dict[str, ToolReturnPart | RetryPromptPart]:
    """The part that answers each tool call, by the id of the call, in the requests of `messages`:
    the return of the tool, or the retry prompt of a call that pydantic-ai refused."""
    return {
        part.tool_call_id: part
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart | RetryPromptPart)
    }


def _outcome_of(
    answer: ToolReturnPart | RetryPromptPart | None,
) -> tuple[ToolOutcome, int | None, float | None]:
    """How a tool call ended, the characters of its answer, and its timeout in seconds (None for a
    call with no answer or timeout). The answer is the text that the model read, after the cut of
    the tool. The tool sets its outcome with `empty_answer` and `error_answer`, or in a metadata
    dict. A call with no return of the tool is an error."""
    if not isinstance(answer, ToolReturnPart) or answer.outcome != "success":
        return ToolOutcome.ERROR, None, None
    text = answer.model_response_str()
    if isinstance(answer.metadata, ToolOutcome):
        return answer.metadata, len(text), None
    if isinstance(answer.metadata, Mapping):
        meta_outcome = answer.metadata.get("outcome")
        outcome = (
            meta_outcome
            if isinstance(meta_outcome, ToolOutcome)
            else (ToolOutcome.OK if text.strip() else ToolOutcome.EMPTY)
        )
        timeout_val = answer.metadata.get("timeout")
        timeout = float(timeout_val) if isinstance(timeout_val, (int, float)) else None
        return outcome, len(text), timeout
    return (ToolOutcome.OK if text.strip() else ToolOutcome.EMPTY), len(text), None


def _is_fallback(asked: str, answered: str) -> bool:
    """Whether `answered`, the model that a reply names, is another model than `asked`. A
    gateway may name the asked model under a provider prefix (`ollama_chat/<asked>`), which is
    no fallback."""
    return answered != asked and not answered.endswith(f"/{asked}")


def record_run_spend(
    model: Any, messages: Sequence[ModelMessage], seconds: float, *, stage: str
) -> None:
    """One spend record for the run's model replies, under `stage`; none when the run got no
    reply. A model the bridge sends to a gateway names the gateway's URL in `served_by`, and its
    record names the provider `gateway`, as `LLMClient`'s records do.

    The record keeps the model asked for in `model` and the model of the last reply that names
    one in `served_model`. Each reply that names its model adds one count to
    `devops_cli_ai_model_answers_total`, with the labels asked, answered and fallback, so a slot
    that reads one model while a gateway fallback answers with another shows (#4205)."""
    from devops_cli.telemetry.instruments import AI_MODEL_ANSWERS_TOTAL, emit

    replies = [message for message in messages if isinstance(message, ModelResponse)]
    if not replies:
        return
    asked = str(getattr(model, "model_name", "unknown"))
    answered = [reply.model_name for reply in replies if reply.model_name]
    for name in answered:
        emit(
            AI_MODEL_ANSWERS_TOTAL,
            1,
            {"asked": asked, "answered": name, "fallback": str(_is_fallback(asked, name)).lower()},
        )
    served_by = getattr(model, "served_by", None)
    track_request_spend(
        provider=CONST_AI_GATEWAY_PROVIDER if served_by else str(getattr(model, "system", "")),
        model=asked,
        server=urlsplit(served_by).netloc if served_by else "unknown",
        served_model=answered[-1] if answered else None,
        prompt_tokens=sum(reply.usage.input_tokens for reply in replies),
        completion_tokens=sum(reply.usage.output_tokens for reply in replies),
        request_type="agent_run",
        duration_seconds=seconds,
        stage=stage,
    )


def _paths_in_argument(argument: str) -> set[str]:
    """The path, directory and paths string values of `argument` when JSON."""
    try:
        data = json.loads(argument)
    except json.JSONDecodeError, TypeError:
        return set()
    if not isinstance(data, dict):
        return set()
    found: set[str] = set()
    for key in ("path", "directory", "paths"):
        val = data.get(key)
        if isinstance(val, str):
            found.add(val)
        elif isinstance(val, (list, tuple)):
            found.update(item for item in val if isinstance(item, str))
    return found


@dataclass(frozen=True)
class TraceFacts:
    """The tools and the paths of a run trace (#3266)."""

    tools: frozenset[str] = frozenset()
    paths: frozenset[str] = frozenset()

    @classmethod
    def of(cls, trace: RunTrace) -> TraceFacts:
        """The tool names and the path, directory and paths values of each tool call argument that
        parses as a JSON object. A value that is no string, and an argument that is no JSON object,
        adds nothing. The method never raises."""
        tools: set[str] = set()
        paths: set[str] = set()
        for call in trace.tool_calls:
            tools.add(call.name)
            paths.update(_paths_in_argument(call.argument))
        return cls(tools=frozenset(tools), paths=frozenset(paths))


__all__ = [
    "RunLimit",
    "RunTrace",
    "ToolCallRecord",
    "ToolOutcome",
    "TraceFacts",
    "argument_json",
    "body_error_text",
    "bounded_text",
    "drain_events",
    "empty_answer",
    "error_answer",
    "model_call_error",
    "ok_answer",
    "record_run_spend",
    "run_error_message",
]
