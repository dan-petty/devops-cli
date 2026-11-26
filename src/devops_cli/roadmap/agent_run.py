"""What the roadmap jobs that run a pydantic-ai agent share (#2398, #2664): the stream handler
that keeps a long reply inside the gateway's tunnel, and the spend record of a run."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import AsyncIterable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final
from urllib.parse import urlsplit

from pydantic_ai import RunContext
from pydantic_ai.exceptions import (
    AgentRunError,
    ModelAPIError,
    ModelConnectionError,
    ModelHTTPError,
    ModelQuotaExceededError,
    ModelRequestTimeout,
    ModelTimeoutError,
    UsageLimitExceeded,
)
from pydantic_ai.messages import (
    INVALID_JSON_KEY,
    AgentStreamEvent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryFeedbackPart,
    TextPart,
    ToolCallPart,
    ToolReturn,
    ToolReturnPart,
    is_retry,
)

from devops_cli.ai.client.models import (
    KEY_STOP_STATUSES,
    PAYMENT_REQUIRED,
    AIClientError,
    AICredentialsError,
    provider_error_text,
    spend_limit_error,
    spent_key_error,
)
from devops_cli.ai.schema_reflection import ViolationText
from devops_cli.ai.spend import model_answer_labels, track_request_spend
from devops_cli.config.constants import (
    CONST_AI_GATEWAY_PROVIDER,
    CONST_ROADMAP_RUN_ERROR_CHARS,
    CONST_ROADMAP_RUN_ERROR_READ_CHARS,
    CONST_ROADMAP_RUN_TRACE_ARGUMENT_CHARS,
    CONST_ROADMAP_STAGE_VIOLATIONS_SHOWN,
)
from devops_cli.security.sanitizer import mask_secret_named_values, mask_secrets


async def drain_events(_ctx: RunContext[None], events: AsyncIterable[AgentStreamEvent]) -> None:
    """Read the run's events. With a handler, pydantic-ai streams each model request, so a long
    reply keeps the gateway's tunnel open past its cut of 125 s, as `LLMClient` streams (#2379)."""
    async for _ in events:
        pass


def model_call_error(exc: ModelAPIError, subject: str) -> AIClientError:
    """The job's class for a failed model call of a run, with no text of the model's reply, and
    with the HTTP status or the timeout of the call (#2562). A failed transport also names its
    phase and the error of the HTTP library, so a report tells a dropped stream from a refused
    connection (#4345). A refused key whose body says that the provider key reached its spend
    limit gives the spend-limit error (#6821). So does an HTTP 402, and a `ModelQuotaExceededError`,
    which pydantic-ai raises when a provider reports that its quota, its credits or its billing is
    exhausted (#7261): a new call fails the same way until a person acts. `subject` names the run,
    such as `The investigation's`."""
    status = exc.status_code if isinstance(exc, ModelHTTPError) else None
    if isinstance(exc, ModelQuotaExceededError):
        return spent_key_error(status or PAYMENT_REQUIRED)
    if isinstance(exc, ModelHTTPError) and exc.status_code in KEY_STOP_STATUSES:
        return spend_limit_error(exc.status_code, exc.body) or AICredentialsError(
            f"The model refused the key (HTTP {exc.status_code})."
        )
    return AIClientError(
        f"{subject} model call failed ({type(exc).__name__}{_transport_cause(exc)}).",
        status=status,
        timed_out=isinstance(exc, (ModelTimeoutError, ModelRequestTimeout)),
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


def body_error_text(body: object) -> str:
    """The error text in the `body` of a model's error reply, safe to show: masked and cut like
    other stop text, then reduced to the part that the provider wrote and not the model: the error
    text of a gateway wrapper when there is one (#2922)."""
    first = (provider_error_text(body).splitlines() or [""])[0]
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


def cut_answer(text: str, cap: str | None) -> ToolReturn:
    """The answer of a tool call that `cap` cut, or `ok_answer(text)` when no cap cut it (#3241).
    The metadata names the cap, so the trace and `devops_cli_roadmap_tool_cuts_total` can count
    the answer."""
    if cap is None:
        return ok_answer(text)
    return ToolReturn(text, metadata={"outcome": ToolOutcome.OK, "cut": cap})


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


class StopReason(StrEnum):
    """Why a run of an agent stopped with no reply (#3717), as the report of a failed case names
    it: the text reply that pydantic-ai refused (`text_reply`), a call to a tool that the run does
    not offer past the tools retry limit (`refused_tool_call`), a call to a tool that the run
    offers with arguments that break the schema of the tool past that limit
    (`tool_retries_exhausted`), a call with arguments that are no JSON text
    (`invalid_arguments`, #4228), a reply that the output token limit cut (`output_limit`,
    #4220), a reply that broke the output schema past its retries (`output_retries_exhausted`),
    a limit of the run (`budget_exhausted`), a window that ended the tools too soon
    (`window_starved`, #3880), or a model call that failed (`model_error`)."""

    TEXT_REPLY = "text_reply"
    REFUSED_TOOL_CALL = "refused_tool_call"
    TOOL_RETRIES_EXHAUSTED = "tool_retries_exhausted"
    INVALID_ARGUMENTS = "invalid_arguments"
    OUTPUT_LIMIT = "output_limit"
    OUTPUT_RETRIES_EXHAUSTED = "output_retries_exhausted"
    BUDGET_EXHAUSTED = "budget_exhausted"
    WINDOW_STARVED = "window_starved"
    MODEL_ERROR = "model_error"


@dataclass(frozen=True)
class StopCause:
    """Why a run stopped with no reply (#3717): its `reason`, the `detail` that a person acts on
    (the name of the tool whose call stopped the run, or of the limit that ended it), the retry
    `limit` that the run used when a retry limit ended it (None otherwise), and `texts`, the text
    of the reply that stopped the run, masked and cut, so a caller can name it."""

    reason: StopReason
    detail: str = ""
    limit: int | None = None
    texts: tuple[str, ...] = ()


# The first line of the message that pydantic-ai raises when the tools retry limit ends a run on a
# call that it refused (#3717).
_TOOL_RETRIES_STOP: Final[re.Pattern[str]] = re.compile(
    r"^Tool .+ exceeded max retries count of \d+"
)
# The name of a limit that a `UsageLimitExceeded` message gives, such as `tool_calls_limit`.
_LIMIT_NAME: Final[re.Pattern[str]] = re.compile(r"\b([a-z_]+_limit)\b")
# The name of each limit that the hook that offers the tools can reach, as `UsageLimits` spells it,
# but the window, which is no limit of pydantic-ai (#3717).
_LIMIT_NAMES: Final[Mapping[RunLimit, str]] = {
    RunLimit.CALLS: "tool_calls_limit",
    RunLimit.REQUESTS: "request_limit",
    RunLimit.WINDOW: "context window",
}


def _last_reply(messages: Sequence[ModelMessage]) -> ModelResponse | None:
    """The last reply of a run, or None for a run that got no reply."""
    return next((m for m in reversed(messages) if isinstance(m, ModelResponse)), None)


def _limit_name(text: str) -> str:
    """The name of the limit that the message of a `UsageLimitExceeded` names, or an empty text."""
    found = _LIMIT_NAME.search(text)
    return found[1] if found else ""


def _retried_name(messages: Sequence[ModelMessage], calls: Sequence[ToolCallPart]) -> str:
    """The name of the tool whose calls spent the tools retry limit: the call of the last reply
    whose name a retried return of the run holds, else the name of its last call. pydantic-ai writes
    the name into the message of the error, which `run_error_message` hides."""
    retried = {
        part.tool_name
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if is_retry(part) and isinstance(part, ToolReturnPart)
    }
    return next(
        (call.tool_name for call in reversed(calls) if call.tool_name in retried),
        calls[-1].tool_name,
    )


def _tool_retries_cause(
    messages: Sequence[ModelMessage],
    calls: Sequence[ToolCallPart],
    *,
    offered: Collection[str],
    tool_retries: int,
    limits_hit: Sequence[RunLimit],
    texts: tuple[str, ...],
) -> StopCause:
    """The cause of a stop by the tools retry limit (#3717). pydantic-ai gives the same message
    for a call to a tool that the run does not offer and for a call to an offered tool whose
    arguments break the schema of the tool, so the names that the run offered tell them apart.
    A limit that ended the tools wins, because the hook that offers the tools takes them away at
    that limit and the next call gets the same stop."""
    if limits_hit:
        return StopCause(StopReason.BUDGET_EXHAUSTED, _LIMIT_NAMES[limits_hit[0]], texts=texts)
    name = _retried_name(messages, calls)
    reason = StopReason.TOOL_RETRIES_EXHAUSTED if name in offered else StopReason.REFUSED_TOOL_CALL
    return StopCause(reason, name, tool_retries, texts)


def stop_cause(
    stopped: AgentRunError,
    messages: Sequence[ModelMessage],
    *,
    offered: Collection[str],
    tool_retries: int,
    output_retries: int,
    limits_hit: Sequence[RunLimit] = (),
) -> StopCause:
    """Why the run of `messages` stopped with `stopped` (#3717), from the messages of the run, the
    names of the tools that it offered and the retry limits that the caller set. `tool_retries`
    and `output_retries` are the retry limits that the run used, so a report names the limit of
    that run and not a constant.

    The output token limit cut the last reply when its finish reason is `length` (#4220). A call
    whose arguments pydantic-ai keeps under `INVALID_JSON_KEY` holds arguments that are no JSON
    text, as when a gateway joins the arguments of several calls into one text (#4228). A reply
    that holds text and no tool call is the text reply that pydantic-ai refused.
    """
    last = _last_reply(messages)
    parts = last.parts if last is not None else []
    texts = tuple(bounded_text(part.content) for part in parts if isinstance(part, TextPart))
    calls = [part for part in parts if isinstance(part, ToolCallPart)]
    invalid = next((call for call in calls if INVALID_JSON_KEY in call.args_as_dict()), None)
    if isinstance(stopped, UsageLimitExceeded):
        return StopCause(StopReason.BUDGET_EXHAUSTED, _limit_name(stopped.message), texts=texts)
    if last is not None and last.finish_reason == "length":
        return StopCause(StopReason.OUTPUT_LIMIT, texts=texts)
    if invalid is not None:
        return StopCause(StopReason.INVALID_ARGUMENTS, invalid.tool_name, texts=texts)
    if texts and not calls:
        return StopCause(StopReason.TEXT_REPLY, texts=texts)
    if calls and _TOOL_RETRIES_STOP.match(stopped.message):
        return _tool_retries_cause(
            messages,
            calls,
            offered=offered,
            tool_retries=tool_retries,
            limits_hit=limits_hit,
            texts=texts,
        )
    return StopCause(StopReason.OUTPUT_RETRIES_EXHAUSTED, limit=output_retries, texts=texts)


@dataclass(frozen=True)
class ToolCallRecord:
    """One tool call of a run: the tool, its argument as JSON, masked and cut, how the call ended,
    the characters of its answer, after the cut of the tool (None for a call with no answer), its
    timeout in seconds when bounded (#3221), the `path:line` of each match line of the answer of a
    search tool (#4495), and the cap that cut its answer, or None (#3241)."""

    name: str
    argument: str
    outcome: ToolOutcome = ToolOutcome.OK
    chars: int | None = None
    timeout: float | None = None
    matches: tuple[str, ...] = ()
    cut: str | None = None


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
    provider gave none (#4313). `stop_reason` and `stop_detail` are the reason and the detail of
    the stop of a run that gave no reply, and are None and empty for a run that gave one
    (#3717)."""

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
    stop_reason: StopReason | None = None
    stop_detail: str = ""

    @classmethod
    def combined(cls, traces: Iterable[RunTrace]) -> RunTrace:
        """One trace for all `traces`, in order: their tool calls and offers joined and their counts
        summed. The violations, the limit and the stop are those of the last trace that had any."""
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
            total.stop_reason = trace.stop_reason or total.stop_reason
            total.stop_detail = trace.stop_detail or total.stop_detail
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
                    if isinstance(part, ToolReturnPart)
                    and part.tool_name in tools
                    and not is_retry(part)
                )

    def _add_reply(
        self,
        reply: ModelResponse,
        tools: Collection[str],
        answers: Mapping[str, ToolReturnPart],
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
                answer = answers.get(part.tool_call_id)
                outcome, chars, timeout, cut = _outcome_of(answer)
                self.tool_calls.append(
                    ToolCallRecord(
                        part.tool_name,
                        argument[:CONST_ROADMAP_RUN_TRACE_ARGUMENT_CHARS],
                        outcome,
                        chars,
                        timeout=timeout,
                        matches=_match_lines(part.tool_name, answer),
                        cut=cut,
                    )
                )

    def _add_violations(self, request: ModelRequest, tools: Collection[str]) -> None:
        for part in request.parts:
            if is_retry(part) and _retried_tool(part) not in tools:
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


def _retried_tool(part: ToolReturnPart | RetryFeedbackPart) -> str | None:
    """The name of the tool whose call a retry answers, or None for a retry that answers no call,
    such as a text reply that breaks the output schema."""
    return part.tool_name if isinstance(part, ToolReturnPart) else None


def _answers(messages: Sequence[ModelMessage]) -> dict[str, ToolReturnPart]:
    """The part that answers each tool call, by the id of the call, in the requests of `messages`:
    the return of the tool, or the retried return of a call that pydantic-ai refused."""
    return {
        part.tool_call_id: part
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    }


# The tools of the stage planner that answer each match as one line, `path:line:content`: the
# lines of the staged commit that a search showed to the run (#4495).
_MATCH_TOOLS: Final[frozenset[str]] = frozenset({"search_code", "callers"})
_MATCH_LINE: Final[re.Pattern[str]] = re.compile(r"^(?P<path>[^\s:]+):(?P<line>\d+):", re.MULTILINE)


def _match_lines(tool: str, answer: ToolReturnPart | None) -> tuple[str, ...]:
    """The `path:line` of each match line of the answer of a search tool, in order and once each.
    The answer of any other tool and a call with no answer give none. `model_response_str()` wraps
    a retried or failed answer in one `{"error": ...}` object, so no line of its text starts with a
    path."""
    if tool not in _MATCH_TOOLS or answer is None:
        return ()
    text = answer.model_response_str()
    return tuple(dict.fromkeys(f"{m['path']}:{m['line']}" for m in _MATCH_LINE.finditer(text)))


def _outcome_of(
    answer: ToolReturnPart | None,
) -> tuple[ToolOutcome, int | None, float | None, str | None]:
    """How a tool call ended, the characters of its answer, its timeout in seconds (None for a call
    with no answer or timeout), and the cap that cut its answer (None with no cut, #3241). The
    answer is the text that the model read, after the cut of the tool. The tool sets its outcome
    with `empty_answer` and `error_answer`, or in a metadata dict. A call with no return of the
    tool is an error."""
    if answer is None or answer.outcome != "success":
        return ToolOutcome.ERROR, None, None, None
    text = answer.model_response_str()
    if isinstance(answer.metadata, ToolOutcome):
        return answer.metadata, len(text), None, None
    if isinstance(answer.metadata, Mapping):
        meta_outcome = answer.metadata.get("outcome")
        outcome = (
            meta_outcome
            if isinstance(meta_outcome, ToolOutcome)
            else (ToolOutcome.OK if text.strip() else ToolOutcome.EMPTY)
        )
        timeout_val = answer.metadata.get("timeout")
        timeout = float(timeout_val) if isinstance(timeout_val, (int, float)) else None
        cut_val = answer.metadata.get("cut")
        cut = cut_val if isinstance(cut_val, str) else None
        return outcome, len(text), timeout, cut
    return (ToolOutcome.OK if text.strip() else ToolOutcome.EMPTY), len(text), None, None


def record_run_spend(
    model: Any, messages: Sequence[ModelMessage], seconds: float, *, stage: str
) -> None:
    """One spend record for the run's model replies, under `stage`; none when the run got no
    reply. A model the bridge sends to a gateway names the gateway's URL in `served_by`, and its
    record names the provider `gateway`, as `LLMClient`'s records do.

    The record keeps the model asked for in `model` and the model of the last reply that names
    one in `served_model`. Each reply that names its model adds one count to
    `devops_cli_ai_model_answers_total`, with the labels asked, answered, fallback and row, so a
    slot that reads one model while a gateway fallback answers with another shows (#4205). The prompt
    tokens that the provider read from its cache cost the cached input rate (#4403), and those that
    it wrote to its cache cost the cache write rate (#3658)."""
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
            model_answer_labels(asked, name),
        )
    served_by = getattr(model, "served_by", None)
    served_model = getattr(model, "served_model", None) or (answered[-1] if answered else None)
    track_request_spend(
        provider=CONST_AI_GATEWAY_PROVIDER if served_by else str(getattr(model, "system", "")),
        model=asked,
        server=urlsplit(served_by).netloc if served_by else "unknown",
        served_model=served_model,
        prompt_tokens=sum(reply.usage.input_tokens for reply in replies),
        completion_tokens=sum(reply.usage.output_tokens for reply in replies),
        cache_read_tokens=sum(reply.usage.cache_read_tokens for reply in replies),
        cache_write_tokens=sum(reply.usage.cache_write_tokens for reply in replies),
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
    """The tools and the paths of a run trace (#3266), and the `path:line` of each line that a
    search match showed to the run (#4495)."""

    tools: frozenset[str] = frozenset()
    paths: frozenset[str] = frozenset()
    lines: frozenset[str] = frozenset()

    @classmethod
    def of(cls, trace: RunTrace) -> TraceFacts:
        """The tool names, the path, directory and paths values of each tool call argument that
        parses as a JSON object, and the match lines of each search answer. A value that is no
        string, and an argument that is no JSON object, adds nothing. The method never raises."""
        tools: set[str] = set()
        paths: set[str] = set()
        lines: set[str] = set()
        for call in trace.tool_calls:
            tools.add(call.name)
            paths.update(_paths_in_argument(call.argument))
            lines.update(call.matches)
        return cls(tools=frozenset(tools), paths=frozenset(paths), lines=frozenset(lines))

    def __or__(self, other: TraceFacts) -> TraceFacts:
        """The facts of both runs: their tools, paths and match lines joined."""
        return TraceFacts(
            tools=self.tools | other.tools,
            paths=self.paths | other.paths,
            lines=self.lines | other.lines,
        )


__all__ = [
    "RunLimit",
    "RunTrace",
    "StopCause",
    "StopReason",
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
    "stop_cause",
]
