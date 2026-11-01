"""`devops roadmap implement` (#2664): one task group of a staged change, run in one bounded
context.

A change is `openspec/changes/<issue>-<slug>/` in a checkout, and its `tasks.md` holds numbered
groups (`## <n>. <title>`). A step reads one group and builds the inputs the model gets: the
item's title, problem and acceptance criteria, the change's `proposal.md`, `design.md` and
`tasks.md`, the group, and the files the group names, packed. It counts their tokens before the
first request and refuses a step that does not fit the window of `ai.tasks.implement`.

The run is one pydantic-ai agent on the harness's `Coder`, tuned where its parts are public: a
shell with an allowlist, a smaller cap on each tool result, and the window of the task. The step
judges the exit, not the model: the tasks of the group change only in their checkboxes, the
verification commands pass, the static checks pass on the changed files, and every task is ticked.
A model that did the work and forgot the ticks gets one more turn of the same conversation, which
may change only `tasks.md` (#2721). Then the step commits the checkout, or it resets it. A step
writes nothing to GitHub.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile
import time
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

from platformdirs import user_cache_dir
from pydantic import BaseModel, ConfigDict
from pydantic_ai import Agent, capture_run_messages
from pydantic_ai.capabilities import AbstractCapability, LocalWorkspace
from pydantic_ai.conversation import Conversation
from pydantic_ai.exceptions import (
    AgentRunError,
    ModelAPIError,
    ModelContextWindowExceededError,
    ModelHTTPError,
    ModelRequestTimeout,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
)
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import RunUsage, UsageLimits
from pydantic_ai_harness.compaction import ClearToolResults, WarnNearLimits
from pydantic_ai_harness.shell import Shell
from pydantic_ai_harness.tool_output_limits import Band, ToolOutputLimits, Truncate

from devops_cli.ai.client.models import AICredentialsError
from devops_cli.ai.context_budget import count_tokens
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.commands import (
    BIN_GIT,
    BIN_MYPY,
    BIN_RUFF,
    BIN_UV,
    IMPLEMENT_ALLOWED_PROGRAMS,
    IMPLEMENT_SHELL_PROGRAMS,
)
from devops_cli.config.constants import (
    CONST_OPENSPEC_CHANGES_DIR,
    CONST_PRE_COMMIT_COMMIT_STAGE,
    CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS,
    CONST_ROADMAP_IMPLEMENT_CRITERIA_HEADINGS,
    CONST_ROADMAP_IMPLEMENT_DENIED_OPERATORS,
    CONST_ROADMAP_IMPLEMENT_DIFF_CHARS,
    CONST_ROADMAP_IMPLEMENT_DIFF_READ_CHARS,
    CONST_ROADMAP_IMPLEMENT_FIX_GROUP,
    CONST_ROADMAP_IMPLEMENT_LOG_CHARS,
    CONST_ROADMAP_IMPLEMENT_MAX_OUTPUT_TOKENS,
    CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS,
    CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS,
    CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS,
    CONST_ROADMAP_IMPLEMENT_OUTPUT_TAIL_LINES,
    CONST_ROADMAP_IMPLEMENT_PROBLEM_HEADINGS,
    CONST_ROADMAP_IMPLEMENT_REASON_CHARS,
    CONST_ROADMAP_IMPLEMENT_REASON_PATHS,
    CONST_ROADMAP_IMPLEMENT_REASON_TESTS,
    CONST_ROADMAP_IMPLEMENT_REQUEST_TIMEOUT_SECONDS,
    CONST_ROADMAP_IMPLEMENT_TOOL_MAX_CHARS,
    CONST_ROADMAP_IMPLEMENT_TOOL_RETRIES,
    CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.process import run_subprocess
from devops_cli.core.process_hardening import end_leftover_processes
from devops_cli.exceptions.ai_pydantic import OutputCapReached
from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.lang import MESSAGES
from devops_cli.output import print_muted
from devops_cli.roadmap.agent_run import (
    body_error_text,
    bounded_text,
    drain_events,
    model_call_error,
    record_run_spend,
)
from devops_cli.roadmap.implement_hooks import commit_stage
from devops_cli.roadmap.implement_output_cap import output_cap_hooks
from devops_cli.roadmap.implement_shell_refusal import shell_refusal_hooks
from devops_cli.roadmap.implement_strays import stray_files
from devops_cli.roadmap.implement_test_names import lost_since
from devops_cli.roadmap.implement_tool_log import ToolCallLog
from devops_cli.roadmap.step_files import (
    CHECKBOXES,
    MARKDOWN,
    GroupTask,
    TaskGroup,
    file_lines,
    named_files,
    packed_file,
    parse_task_groups,
)
from devops_cli.security.sanitizer import mask_secrets

if TYPE_CHECKING:
    from devops_cli.roadmap.store import Item

_CHANGE_DOCUMENTS = ("proposal.md", "design.md", "tasks.md")
_PROMPT = "roadmap_implement_step.md"


class ItemReader(Protocol):
    """What a step reads of the roadmap: the item of an issue number. `RoadmapStore` satisfies it,
    and so does the item of an evaluation fixture (#3030)."""

    def item(self, number: int) -> Item | None:
        """The item numbered `number`, or None when that issue is no item."""


def section_text(body: str, titles: frozenset[str]) -> str:
    """The text of each section of `body` whose heading is one of `titles`, heading included.
    A section ends at the next heading of its level or a higher one."""
    tokens = MARKDOWN.parse(body)
    lines = body.splitlines()
    marks = [
        (token.map[0], int(token.tag[1:]), tokens[index + 1].content)
        for index, token in enumerate(tokens)
        if token.type == "heading_open" and token.map is not None
    ]
    found: list[str] = []
    for position, (first, level, title) in enumerate(marks):
        if title.strip().casefold() not in titles:
            continue
        end = next(
            (start for start, deeper, _ in marks[position + 1 :] if deeper <= level), len(lines)
        )
        found.append("\n".join(lines[first:end]).rstrip())
    return "\n\n".join(found)


def issue_inputs(item: Item) -> str:
    """The title of the item, then its problem and its acceptance criteria. An issue that holds
    neither section gives its whole body."""
    wanted = CONST_ROADMAP_IMPLEMENT_PROBLEM_HEADINGS | CONST_ROADMAP_IMPLEMENT_CRITERIA_HEADINGS
    text = section_text(item.body, wanted) or item.body.strip()
    return f"# Item #{item.number}: {item.title}\n\n{text}"


def find_change(source: Path, item: int, *, archived: bool = False) -> Path:
    """The one folder `openspec/changes/<item>-*/` of the checkout. With `archived`, a change that
    `openspec archive` moved is found too, at `openspec/changes/archive/<date>-<item>-*/`: a fix
    step runs after the archive."""
    pattern = f"{item}-*"
    changes = source / CONST_OPENSPEC_CHANGES_DIR
    found = sorted(path for path in changes.glob(pattern) if path.is_dir())
    if archived and not found:
        dated = f"[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-{pattern}"
        found = sorted(path for path in (changes / "archive").glob(dated) if path.is_dir())
    if not found:
        raise RoadmapImplementError(MESSAGES.roadmap.implement_no_change.format(pattern=pattern))
    if len(found) > 1:
        raise RoadmapImplementError(
            MESSAGES.roadmap.implement_many_changes.format(
                pattern=pattern, names=", ".join(path.name for path in found)
            )
        )
    return found[0]


@dataclass(frozen=True)
class FixRequest:
    """A failed check for a fix step (#2665): its name, and its log. The step reads the last
    `CONST_ROADMAP_IMPLEMENT_LOG_CHARS` characters of the log."""

    check: str
    log: str


def fix_group(fix: FixRequest, groups: Sequence[TaskGroup]) -> TaskGroup:
    """The group of a fix step: one task that names the check, with the verification commands of
    every group of the change, and the number `CONST_ROADMAP_IMPLEMENT_FIX_GROUP`."""
    title = MESSAGES.roadmap.implement_fix_title.format(check=fix.check)
    task = MESSAGES.roadmap.implement_fix_task.format(check=fix.check)
    commands = tuple(dict.fromkeys(c for group in groups for c in group.verification_commands))
    return TaskGroup(
        number=CONST_ROADMAP_IMPLEMENT_FIX_GROUP,
        title=title,
        tasks=(GroupTask(text=task, ticked=False, verification=commands),),
        text=f"## {CONST_ROADMAP_IMPLEMENT_FIX_GROUP}. {title}\n\n- {task}",
    )


@dataclass(frozen=True)
class StepInputs:
    """What one step gives the model: the instructions, the user message, and their tokens.
    `change` is the change folder, and `tasks_md` is the text of its `tasks.md` before the run,
    read with its line ends. The job writes that text back after each turn."""

    group: TaskGroup
    change: Path
    tasks_md: str
    instructions: str
    message: str
    tokens: int
    fix: FixRequest | None = None


def _files_section(source: Path, group: TaskGroup) -> str:
    """The packed files of the group, each under its path."""
    parts = [
        f"## {path.relative_to(source.resolve())}\n\n```\n{packed_file(path)}\n```"
        for path in named_files(source, group)
    ]
    return "# Files the group names (signatures only)\n\n" + "\n\n".join(parts) if parts else ""


def _chosen_group(
    groups: Sequence[TaskGroup], group: int, fix: FixRequest | None, change: Path
) -> TaskGroup:
    """The group the step runs: the synthetic group of a fix, else group `group` of the change."""
    if fix is not None:
        return fix_group(fix, groups)
    chosen = next((candidate for candidate in groups if candidate.number == group), None)
    if chosen is None:
        raise RoadmapImplementError(
            MESSAGES.roadmap.implement_no_group.format(
                change=change.name,
                group=group,
                groups=", ".join(str(candidate.number) for candidate in groups) or "none",
            )
        )
    return chosen


def _log_section(fix: FixRequest | None) -> str:
    """The last characters of the log of a failed check, under their heading."""
    if fix is None:
        return ""
    return f"# The log of the failed check\n\n{fix.log[-CONST_ROADMAP_IMPLEMENT_LOG_CHARS:]}"


def _tasks_file_section(source: Path, change: Path, fix: FixRequest | None) -> str:
    """The path of the `tasks.md` of the change in the checkout, under its heading. A fix step
    ticks no task, so it gets none."""
    if fix is not None:
        return ""
    return f"# The tasks file\n\n`{(change / 'tasks.md').relative_to(source).as_posix()}`"


def build_step_inputs(
    store: ItemReader,
    *,
    item: int,
    group: int,
    source: Path,
    window: int,
    fix: FixRequest | None = None,
) -> StepInputs:
    """The inputs of group `group` of item `item`, read from the checkout `source`. With `fix`,
    the group is the fix of that failed check and `group` is not read.

    Raises `RoadmapImplementError` for an issue that is no Item, a change that is not in the
    checkout, a group the change lacks, and inputs that measure more than `window` minus
    `CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS` tokens.
    """
    held = store.item(item)
    if held is None:
        raise RoadmapImplementError(MESSAGES.roadmap.implement_not_item.format(number=item))
    change = find_change(source, item, archived=fix is not None)
    documents = {name: (change / name).read_text(encoding="utf-8") for name in _CHANGE_DOCUMENTS}
    raw_tasks = (change / "tasks.md").read_text(encoding="utf-8", newline="")
    groups = parse_task_groups(raw_tasks)
    twice = duplicate_group(groups)
    if twice is not None:
        raise RoadmapImplementError(
            MESSAGES.roadmap.implement_duplicate_group.format(change=change.name, group=twice)
        )
    chosen = _chosen_group(groups, group, fix, change)
    sections = [
        issue_inputs(held),
        *(f"# {name} of the change\n\n{text.strip()}" for name, text in documents.items()),
        f"# Your group\n\n{chosen.text}",
        _tasks_file_section(source, change, fix),
        _log_section(fix),
        _files_section(source, chosen),
    ]
    message = "\n\n".join(section for section in sections if section)
    instructions = load_task_prompt(_PROMPT)
    tokens = count_tokens(instructions) + count_tokens(message)
    limit = window - CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS
    if tokens > limit:
        raise RoadmapImplementError(
            MESSAGES.roadmap.implement_over_window.format(
                measured=tokens,
                limit=limit,
                window=window,
                reserve=CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS,
            )
        )
    return StepInputs(
        group=chosen,
        change=change,
        tasks_md=raw_tasks,
        instructions=instructions,
        message=message,
        tokens=tokens,
        fix=fix,
    )


# ── The outcome ───────────────────────────────────────────────────────────────────────────


class StepStatus(StrEnum):
    """How a step ended: its group is committed, or the step stopped and reset the checkout."""

    DONE = "done"
    STOPPED = "stopped"


class StepOutcome(BaseModel):
    """The report of a step. `reason` is why a stopped step stopped: the class and the message of
    the pydantic-ai error that ended the run, with the counts of refused and retried tool calls
    (#2758), or the first exit check that failed. `commit` is the commit of a done step. `diff` is
    the diff of the work that a stopped step discarded, with secrets masked and cut to
    `CONST_ROADMAP_IMPLEMENT_DIFF_CHARS` characters, and `diff_cut` says that it was cut (#2721).
    `tool_calls` counts the tool calls of the replies (#3030). `removed` lists the stray files that
    the step deleted (#3092). `repair_rounds` counts the extra turns that the step used (#3043).
    `planned_requests` are the requests a dry run lists."""

    model_config = ConfigDict(frozen=True)

    item: int
    group: int
    title: str
    status: StepStatus
    reason: str = ""
    last_message: str = ""
    commit: str = ""
    diff: str = ""
    diff_cut: bool = False
    requests: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    removed: tuple[str, ...] = ()
    repair_rounds: int = 0
    dry_run: bool = False
    planned_requests: tuple[str, ...] = ()


# ── The agent ─────────────────────────────────────────────────────────────────────────────


_PASSED_VARIABLES = ("UV_PYTHON", "PYTEST_XDIST_AUTO_NUM_WORKERS")


def shell_environment(home: Path) -> dict[str, str]:
    """The variables a shell command gets on top of the workspace's own: a scratch `home` in place
    of the user's, so that no git configuration, credential helper or key of the user reaches the
    agent, no system git configuration, no prompt for a password, and the cache of `uv` where the
    user keeps it, so that `uv run` finds its packages. The variables in `_PASSED_VARIABLES` go on
    when the process has them. `UV_PYTHON`: the runner image sets it, as it forbids a Python
    download and `uv run` finds no interpreter without it. `PYTEST_XDIST_AUTO_NUM_WORKERS`: the
    pod of the runner sets it to its CPU limit, as `pytest-xdist` counts the CPUs of the node and
    a test run started one worker for each of them (#2806)."""
    env = {
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "UV_CACHE_DIR": os.environ.get("UV_CACHE_DIR") or user_cache_dir("uv"),
    }
    env.update({name: os.environ[name] for name in _PASSED_VARIABLES if os.environ.get(name)})
    return env


def _tune(
    capability: AbstractCapability[None], window: int, home: Path
) -> AbstractCapability[None]:
    """One part of `Coder`, changed for a step: the shell takes the allowlist, the scratch home
    and the refusal of the operators that start a second command, the tool results get the cap of
    a step, and the context controls get the window of the task, in place of the registry's."""
    if isinstance(capability, Shell):
        return replace(
            capability,
            allowed_commands=list(IMPLEMENT_SHELL_PROGRAMS),
            denied_commands=[],
            denied_operators=list(CONST_ROADMAP_IMPLEMENT_DENIED_OPERATORS),
            allow_interactive=False,
            env=shell_environment(home),
        )
    if isinstance(capability, ClearToolResults | WarnNearLimits):
        return replace(capability, context_window=window)
    if isinstance(capability, ToolOutputLimits):
        cap = CONST_ROADMAP_IMPLEMENT_TOOL_MAX_CHARS
        return replace(capability, bands=[Band(over=cap, action=Truncate(max_chars=cap))])
    return capability


def build_agent(
    model: Any, source: Path, instructions: str, window: int, home: Path, log: ToolCallLog
) -> Agent[None, str]:
    """The agent of a step: `Coder` on a local workspace at `source`, whose shell runs with the
    scratch `home`, the hint that a refusal of the shell adds (#2773), and the hooks of `log` for its
    tool calls (#2758). It has no `delegate_task` tool, so the limits of a run cover the whole step,
    and it loads no instruction file of the checkout, so its context is the inputs of the step. Each
    model call has an output cap and a deadline (#2869). The shell is no security boundary: the
    runner of the step is the sandbox."""
    from pydantic_ai_harness.coder import Coder

    coder = Coder[None](instructions=instructions, repo_context=False, sub_agents=False)
    # The visitor replaces leaves and removes none, so the tree is never empty.
    tuned = cast(
        AbstractCapability[None], coder.visit_and_replace(lambda leaf: _tune(leaf, window, home))
    )
    return Agent(
        model,
        output_type=str,
        retries={"tools": CONST_ROADMAP_IMPLEMENT_TOOL_RETRIES},
        model_settings=ModelSettings(
            max_tokens=CONST_ROADMAP_IMPLEMENT_MAX_OUTPUT_TOKENS,
            request_timeout=CONST_ROADMAP_IMPLEMENT_REQUEST_TIMEOUT_SECONDS,
        ),
        capabilities=[
            LocalWorkspace(source),
            tuned,
            shell_refusal_hooks(),
            log.hooks(),
            output_cap_hooks(CONST_ROADMAP_IMPLEMENT_MAX_OUTPUT_TOKENS),
        ],
    )


@dataclass(frozen=True)
class _Run:
    """What a turn left: why it ended early (the class and the message of the pydantic-ai error,
    with the counts of `ToolCallLog`, or empty), the last text of the model, what it spent, and
    the conversation to continue when it ended, and the conversation to resume when a new send of
    the request can fix the error that ended it (#2794)."""

    reason: str
    last_message: str
    requests: int
    input_tokens: int
    output_tokens: int
    tool_calls: int = 0
    conversation: Conversation | None = None
    resend: Conversation | None = None

    def then(self, later: _Run) -> _Run:
        """This turn followed by `later`, which continued its conversation: the end and the last
        text of `later`, and the spend of both."""
        return _Run(
            reason=later.reason,
            last_message=later.last_message or self.last_message,
            requests=self.requests + later.requests,
            input_tokens=self.input_tokens + later.input_tokens,
            output_tokens=self.output_tokens + later.output_tokens,
            tool_calls=self.tool_calls + later.tool_calls,
            conversation=later.conversation,
            resend=later.resend,
        )


def _last_text(messages: Sequence[ModelMessage]) -> str:
    """The last text part of the model's replies."""
    texts = [
        part.content
        for message in messages
        if isinstance(message, ModelResponse)
        for part in message.parts
        if isinstance(part, TextPart)
    ]
    return texts[-1] if texts else ""


def _with_counts(reason: str, log: ToolCallLog) -> str:
    """`reason`, then the counts of refused and retried tool calls when either is not zero, then
    the last reasons of the tool whose retries ended the run (#2866)."""
    if not (log.refused or log.retried):
        return reason
    counts = MESSAGES.roadmap.implement_stop_counts.format(
        refused=log.refused_text(), retried=log.retried
    )
    return "\n".join(line for line in (reason, counts, log.retries_text()) if line)


def _stop_reason(stopped: AgentRunError, log: ToolCallLog) -> str:
    """The reason of a run that a pydantic-ai error ended (#2758): the class and the message of the
    error, then the counts of refused and retried tool calls when either is not zero. It reads
    `message`, not `str()`, which adds the `body`, the text of the model (#2778)."""
    texts = MESSAGES.roadmap
    reason = texts.run_stop_reason.format(
        error=type(stopped).__name__, message=bounded_text(stopped.message)
    )
    return _with_counts(reason, log)


def _model_call_reason(failed: ModelAPIError, log: ToolCallLog) -> str:
    """The reason of a run that a failed model call ended (#2731): the class of the error, the HTTP
    status when the reply has one, and the name of the model, then the error text of the body of
    the reply (#2794), then the line that names a failure of the generation inside a stream
    (#2922), then the counts of `_stop_reason`. The message of the error stays out, and
    so does every value of the body but its error text: the masker finds a secret by its form in
    a sentence, not by its key in the repr of a dict."""
    texts = MESSAGES.roadmap
    detail = texts.implement_model_call_model.format(model=failed.model_name)
    if isinstance(failed, ModelHTTPError):
        detail = texts.implement_model_call_status.format(status=failed.status_code, model=detail)
        if body := body_error_text(failed.body):
            detail = texts.implement_model_call_body.format(detail=detail, body=body)
    if isinstance(failed, ModelRequestTimeout):
        detail = texts.implement_model_call_deadline.format(detail=detail, seconds=failed.timeout)
    reason = texts.run_stop_reason.format(error=type(failed).__name__, message=detail)
    if _generation_failed(failed):
        reason = f"{reason}\n{texts.implement_model_call_generation}"
    return _with_counts(reason, log)


def _generation_failed(failed: ModelAPIError) -> bool:
    """Whether `failed` is an error that the provider reported inside an open stream, with the
    status 400, and that is no context window error (#2794). The request was good, for the
    provider had begun to answer. The model made a reply that the provider could not use, such as
    a tool call that ends early, and the next sample of the model can be whole. A request that
    the provider refuses before it streams, and a prompt that is too long, fail the same way again."""
    return (
        isinstance(failed, ModelHTTPError)
        and failed.in_stream
        and failed.status_code == HTTPStatus.BAD_REQUEST
        and not isinstance(failed, ModelContextWindowExceededError)
    )


def _resend_after(
    failed: ModelAPIError, messages: Sequence[ModelMessage], conversation: Conversation | None
) -> Conversation | None:
    """The conversation that sends the failed request again, or `None` when `failed` is no error
    of the generation or the messages do not end with a request. It holds the same messages as the
    failed request, for the interrupted reply is dropped, and the usage of the replies that came
    before and of the failed request, so the limits of the step count every send."""
    kept = list(messages)
    if kept and isinstance(kept[-1], ModelResponse) and kept[-1].state == "interrupted":
        kept.pop()
    if not _generation_failed(failed) or not kept or isinstance(kept[-1], ModelResponse):
        return None
    replies = _new_replies(kept, conversation)
    spent = (conversation.usage if conversation else RunUsage()) + RunUsage(
        requests=len(replies) + 1, tool_calls=_tool_calls(replies)
    )
    for reply in replies:
        spent.incr(reply.usage)
    return Conversation(messages=kept, usage=spent)


def _run_agent(
    agent: Agent[None, str],
    model: Any,
    log: ToolCallLog,
    message: str,
    conversation: Conversation | None = None,
) -> _Run:
    """One turn of the agent, and each send again of a request that failed inside a stream (#2794).
    A request is sent again at most `CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS` times in a row. A send
    that gets a reply gives the next failed request its own resends. The request limit of the
    step ends the loop. The turn ends with the last send."""
    run = _run_turn(agent, model, log, message, conversation)
    resends = CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS
    while run.resend is not None and resends > 0:
        sent = run.resend
        later = _run_turn(agent, model, log, None, sent)
        stalled = later.resend is not None and len(later.resend.messages) <= len(sent.messages)
        resends = resends - 1 if stalled else CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS
        run = run.then(later)
    return run


def _run_turn(
    agent: Agent[None, str],
    model: Any,
    log: ToolCallLog,
    message: str | None,
    conversation: Conversation | None = None,
) -> _Run:
    """One send of a request to the agent under the limits of a step, and its spend as one record.
    With `conversation`, the turn continues it: its messages and its usage carry over, so the
    limits count both turns. Without `message`, it resumes the request that the conversation ends
    with. A failed model call ends the turn as stopped, with the replies that came before
    it, as a limit does. Raises `AICredentialsError` when the model refuses the key."""
    limits = UsageLimits(
        request_limit=CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS,
        tool_calls_limit=CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS,
    )
    reason = last = ""
    kept = resend = None
    cut: list[ModelResponse] = []
    error: AICredentialsError | None = None
    started = time.monotonic()
    with capture_run_messages() as messages:
        try:
            result = agent.run_sync(
                message,
                conversation=conversation,
                usage_limits=limits,
                event_stream_handler=drain_events,
            )
            last, kept = result.output, result.conversation
        except (UsageLimitExceeded, UnexpectedModelBehavior) as stopped:
            reason, last = _stop_reason(stopped, log), _last_text(messages)
            if isinstance(stopped, OutputCapReached):
                cut.append(stopped.response)
        except ModelAPIError as exc:
            refused = model_call_error(exc, "The step's")
            if isinstance(refused, AICredentialsError):
                # Raised outside this handler, so a logged traceback holds no reply text.
                error = refused
            else:
                reason, last = _model_call_reason(exc, log), _last_text(messages)
                resend = _resend_after(exc, messages, conversation)
        finally:
            replies = [*_new_replies(messages, conversation), *cut]
            record_run_spend(model, replies, time.monotonic() - started, stage="implement")
    if error is not None:
        raise error
    return _Run(
        reason=reason,
        last_message=last,
        requests=len(replies),
        input_tokens=sum(reply.usage.input_tokens for reply in replies),
        output_tokens=sum(reply.usage.output_tokens for reply in replies),
        tool_calls=_tool_calls(replies),
        conversation=kept,
        resend=resend,
    )


def _tool_calls(replies: Sequence[ModelResponse]) -> int:
    """The tool calls that `replies` make."""
    return sum(isinstance(part, ToolCallPart) for reply in replies for part in reply.parts)


def _new_replies(
    messages: Sequence[ModelMessage], conversation: Conversation | None
) -> list[ModelResponse]:
    """The model's replies of this turn: the messages of a run that continues a conversation hold
    its history first, and the replies only ever append."""
    replies = [message for message in messages if isinstance(message, ModelResponse)]
    history = conversation.messages if conversation else []
    return replies[sum(isinstance(message, ModelResponse) for message in history) :]


# ── The exit checks ───────────────────────────────────────────────────────────────────────


def _git(source: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """One git command in the checkout."""
    return run_subprocess(
        [BIN_GIT, *args],
        cwd=source,
        quiet=True,
        timeout=CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS,
    )


def _tail(done: subprocess.CompletedProcess[str]) -> str:
    """The last lines of what a command printed."""
    lines = f"{done.stdout or ''}{done.stderr or ''}".strip().splitlines()
    return "\n".join(lines[-CONST_ROADMAP_IMPLEMENT_OUTPUT_TAIL_LINES:])


def _git_output(source: Path, *args: str) -> str:
    """What a git command printed. Raises `RoadmapImplementError` when it fails."""
    done = _git(source, *args)
    if done.returncode != 0:
        raise RoadmapImplementError(
            MESSAGES.roadmap.implement_git_failed.format(
                command=shlex.join(args), output=_tail(done)
            )
        )
    return done.stdout or ""


def _require_clean(source: Path) -> None:
    """Refuse a checkout with uncommitted changes: a failed step resets it."""
    if _git_output(source, "status", "--porcelain").strip():
        raise RoadmapImplementError(MESSAGES.roadmap.implement_dirty.format(path=source))


def _head(source: Path) -> str:
    """The commit that the checkout is at."""
    return _git_output(source, "rev-parse", "HEAD").strip()


def _reset(source: Path, start: str) -> None:
    """Restore the checkout to the commit `start`, also after the agent made commits."""
    _git_output(source, "reset", "--hard", start)
    _git_output(source, "clean", "-fd")


def duplicate_group(groups: Sequence[TaskGroup]) -> int | None:
    """The first number that two groups hold, or None. A dict keyed by number keeps the last of
    two such groups, so an edit of the first would pass every comparison."""
    twice = [number for number, count in Counter(g.number for g in groups).items() if count > 1]
    return twice[0] if twice else None


def _tasks_after(inputs: StepInputs) -> str | None:
    """The text of the `tasks.md` as the run left it, with its line ends, or None when the file is
    gone or is not UTF-8 text."""
    try:
        return (inputs.change / "tasks.md").read_text(encoding="utf-8", newline="")
    except OSError, UnicodeDecodeError:
        return None


def _own_after(inputs: StepInputs) -> TaskGroup | None:
    """The first group of the `tasks.md` as the run left it that has the number of the own group,
    or None when the file or the group is gone."""
    tasks_md = _tasks_after(inputs)
    if tasks_md is None:
        return None
    return next((g for g in parse_task_groups(tasks_md) if g.number == inputs.group.number), None)


def _unticked(inputs: StepInputs) -> tuple[GroupTask, ...]:
    """The tasks of the group that the run left unticked. A fix step ticks no task."""
    mine = _own_after(inputs)
    if mine is None or inputs.fix is not None:
        return ()
    return tuple(task for task in mine.tasks if not task.ticked)


def _ticked_lines(inputs: StepInputs) -> list[int]:
    """The lines, in the text before the run, of the tasks of the own group that the run ticked.
    A task counts by its position in the group. When the run changed the number of the tasks, the
    position of a tick means nothing, and none counts. A fix step ticks none."""
    mine = _own_after(inputs)
    before = inputs.group.tasks
    if inputs.fix is not None or mine is None or len(mine.tasks) != len(before):
        return []
    return [
        b.line for b, now in zip(before, mine.tasks, strict=True) if now.ticked and not b.ticked
    ]


def _restore_tasks(inputs: StepInputs) -> None:
    """Write the `tasks.md` of the change as it was before the run, with the ticks of the own group
    that the run set. The job owns the file: it reads the verification commands from the text
    before the run, so no edit of the file changes what judges the work. So an edit never stops
    the step, and the line ends, the headings and every other group are those of before the run.
    One line names the change when the file differed. A link or a directory at the path is removed
    first, so the write never goes through a link, and a link never reaches the commit."""
    lines = file_lines(inputs.tasks_md)
    for number in _ticked_lines(inputs):
        lines[number] = lines[number].replace(CHECKBOXES[0], CHECKBOXES[1], 1)
    wanted = "".join(lines)
    path = inputs.change / "tasks.md"
    if not path.is_symlink() and _tasks_after(inputs) == wanted:
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    path.unlink(missing_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(wanted, encoding="utf-8", newline="")
    note = MESSAGES.roadmap.implement_restored_tasks.format(change=inputs.change.name)
    print_muted(note, to_stderr=True)


def _unticked_failure(inputs: StepInputs) -> str | None:
    """Why the step stops when a task of the group is not ticked, else None."""
    unticked = _unticked(inputs)
    if not unticked:
        return None
    return MESSAGES.roadmap.implement_stop_unticked.format(task=unticked[0].text)


def _command_failure(source: Path, argv: Sequence[str], shown: str) -> str | None:
    """Run `argv` in the checkout. None when it exits 0, else why the step stops."""
    try:
        done = run_subprocess(
            list(argv),
            cwd=source,
            quiet=True,
            timeout=CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return MESSAGES.roadmap.implement_stop_command_timeout.format(
            command=shown, seconds=CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS
        )
    if done.returncode == 0:
        return None
    return MESSAGES.roadmap.implement_stop_command_failed.format(
        command=shown, status=done.returncode, output=_tail(done)
    )


def commands_failure(source: Path, commands: Iterable[str]) -> str | None:
    """Run each of `commands` in the checkout, in order: None when all exit 0, else why the first
    that did not stops the run. A command whose program is not on the allowlist does not run. The
    step runs the verification commands of a group, from the tasks as they were before the run."""
    texts = MESSAGES.roadmap
    for command in commands:
        try:
            argv = shlex.split(command)
        except ValueError:
            return texts.implement_stop_command_unparsed.format(command=command)
        if not argv or argv[0] not in IMPLEMENT_ALLOWED_PROGRAMS:
            return texts.implement_stop_command_denied.format(
                command=command,
                program=argv[0] if argv else "",
                allowed=", ".join(IMPLEMENT_ALLOWED_PROGRAMS),
            )
        failure = _command_failure(source, argv, command)
        if failure is not None:
            return failure
    return None


def _python_files(changed: Sequence[str]) -> list[str]:
    """The Python files of the changed paths."""
    return [path for path in changed if path.endswith(".py")]


def _paths_text(
    names: Sequence[str], limit: int = CONST_ROADMAP_IMPLEMENT_REASON_PATHS, separator: str = ", "
) -> str:
    """`names` as one line, cut to `limit` names, with the count of the rest."""
    shown = names[:limit]
    paths = separator.join(shown)
    if len(names) > len(shown):
        paths += MESSAGES.roadmap.implement_paths_more.format(count=len(names) - len(shown))
    return paths


def _tests_failure(source: Path, start: str) -> str | None:
    """Why the step stops when a test file lost a test that it had at `start`, else None. The reason
    names each file with up to `CONST_ROADMAP_IMPLEMENT_REASON_TESTS` of its tests. A file that does
    not parse is skipped: `_static_failure` reports its error."""
    lost = lost_since(lambda *args: _git_output(source, *args), start)
    if not lost:
        return None
    texts = MESSAGES.roadmap
    files = [
        texts.implement_tests_lost_file.format(
            path=path, tests=_paths_text(tests, CONST_ROADMAP_IMPLEMENT_REASON_TESTS)
        )
        for path, tests in lost.items()
    ]
    return texts.implement_stop_tests_lost.format(files=_paths_text(files, separator="\n"))


def _link_failure(source: Path, files: Sequence[str]) -> str | None:
    """Why the step stops when one of `files` is a symbolic link, else None. The formatter writes
    through a link, also to a file outside the checkout, so no tool gets a link."""
    links = [path for path in files if (source / path).is_symlink()]
    if not links:
        return None
    return MESSAGES.roadmap.implement_stop_link.format(paths=_paths_text(links))


def _format_failure(source: Path, changed: Sequence[str]) -> str | None:
    """Run `ruff format` on the changed Python files, outside the shell of the agent, and stage
    the files it changed. Git names them: the index holds the files as they were before the run.
    Prints one line that names them. None when the formatter exits 0, else why the step stops.
    A file name that starts with `-` follows `--`, so the tool reads it as a path."""
    files = _python_files(changed)
    if not files:
        return None
    link = _link_failure(source, files)
    if link is not None:
        return link
    argv = [BIN_UV, "run", BIN_RUFF, "format", "--", *files]
    failure = _command_failure(source, argv, shlex.join(argv))
    if failure is not None:
        return failure
    names = _git_output(source, "diff", "--name-only", "-z", "--", *files)
    formatted = sorted(name for name in names.split("\0") if name)
    if formatted:
        _git_output(source, "add", "--", *formatted)
        print_muted(
            MESSAGES.roadmap.implement_formatted.format(paths=_paths_text(formatted)),
            to_stderr=True,
        )
    return None


def _static_failure(source: Path, changed: Sequence[str]) -> str | None:
    """Run `ruff check` and `mypy --strict` on the changed Python files. `ruff check` fixes
    nothing: a lint rule can point at a defect that the model must see."""
    files = _python_files(changed)
    if not files:
        return None
    for tool in ((BIN_RUFF, "check"), (BIN_MYPY, "--strict")):
        argv = [BIN_UV, "run", *tool, "--", *files]
        failure = _command_failure(source, argv, shlex.join(argv))
        if failure is not None:
            return failure
    return None


def _remove_strays(source: Path, inputs: StepInputs, log: ToolCallLog) -> None:
    """Delete the stray files of the group (#3092) and record their names in `log`: the untracked
    files that git does not ignore (`git ls-files --others --exclude-standard`) and that the group
    does not allow (`stray_files`): a file outside `src/`, `tests/`, `docs/` and `openspec/`, or a
    nested git repository. It runs before the checks stage the checkout, so no stray file
    reaches `ruff`, `mypy` or the commit. The group of a fix step names no file, so a fix step
    keeps its new files."""
    if inputs.fix is not None:
        return
    listed = _git_output(source, "ls-files", "--others", "--exclude-standard", "-z")
    change = inputs.change.relative_to(source).as_posix()
    strays = stray_files([name for name in listed.split("\0") if name], inputs.group, change)
    for name in strays:
        _delete(source / name)
    log.removed_strays(strays)


def _delete(path: Path) -> None:
    """Delete an untracked file, a symbolic link, or a nested git repository that git lists as one
    directory. The path comes from git and is inside the checkout. A symbolic link is unlinked and
    its target stays."""
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _stage(source: Path) -> list[str]:
    """Stage every change of the checkout, and list the paths that the commit would add or
    change."""
    _git_output(source, "add", "-A")
    names = _git_output(source, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    return sorted(name for name in names.split("\0") if name)


@dataclass(frozen=True)
class _Failure:
    """Why the step stops, and, for a failed static check or hook, the paths that the step changed:
    the files that an extra turn for that failure may change (#2795). `repair_paths` is None for
    a failure that gets no such turn. `hook` says that a hook of the project failed (#3043)."""

    reason: str
    repair_paths: frozenset[str] | None = None
    hook: bool = False


def _exit_failure(
    source: Path, inputs: StepInputs, start: str, log: ToolCallLog
) -> _Failure | None:
    """The first exit check that fails, or None when every one passes. The step makes the only
    commit, so a checkout that left `start` fails the first check. The `tasks.md` is written
    back first, whatever the run did to it. The ticks are judged last, by
    `_unticked_failure`, as a step with a task unticked gets a turn for them first. The stray files
    of the agent are deleted before the checkout is staged (#3092)."""
    head = _head(source)
    if head != start:
        return _Failure(MESSAGES.roadmap.implement_stop_head_moved.format(start=start, head=head))
    _restore_tasks(inputs)
    _remove_strays(source, inputs, log)
    changed = _stage(source)
    if not changed:
        return _Failure(MESSAGES.roadmap.implement_stop_no_change)
    lost = _tests_failure(source, start)
    if lost:
        return _Failure(lost)
    early = _format_failure(source, changed) or commands_failure(
        source, inputs.group.verification_commands
    )
    if early:
        return _Failure(early)
    static = _static_failure(source, changed)
    if static:
        return _Failure(static, frozenset(changed))
    return _hooks_failure(source, changed)


def _hooks_failure(source: Path, changed: Sequence[str]) -> _Failure | None:
    """Run the `pre-commit` stage of the hooks over the staged changes (#3043). None when it
    passes. A failed hook (exit 1) is a failure that the agent may repair in the files the step
    changed. Any other exit code is a stop."""
    run = commit_stage(source)
    if run is None:
        return None
    reason = MESSAGES.roadmap.implement_stop_hooks_failed.format(
        stage=CONST_PRE_COMMIT_COMMIT_STAGE, status=run.returncode, output=run.output
    )
    if not run.repairable:
        return _Failure(reason)
    return _Failure(reason, frozenset(changed), hook=True)


def _discarded_diff(source: Path, start: str) -> tuple[str, bool]:
    """The diff from the commit `start` to the checkout, new files included: the work that a
    stopped step is about to discard. Secrets are masked in the first
    `CONST_ROADMAP_IMPLEMENT_DIFF_READ_CHARS` characters, a multiple of the limit, as the masking
    is slower than linear. Then the diff is cut to `CONST_ROADMAP_IMPLEMENT_DIFF_CHARS`
    characters. A cut before the masking could split a secret and let half of it through. No
    external diff program and no text conversion runs: the agent can write the settings that name
    one. The diff, and whether it was cut."""
    _git_output(source, "add", "-A")
    raw = _git_output(
        source, "diff", "--cached", "--no-color", "--no-ext-diff", "--no-textconv", start
    )
    masked = mask_secrets(raw[:CONST_ROADMAP_IMPLEMENT_DIFF_READ_CHARS])
    cut = len(raw) > CONST_ROADMAP_IMPLEMENT_DIFF_READ_CHARS
    return masked[:CONST_ROADMAP_IMPLEMENT_DIFF_CHARS], cut or (
        len(masked) > CONST_ROADMAP_IMPLEMENT_DIFF_CHARS
    )


def _read_discarded_diff(source: Path, start: str, reason: str) -> tuple[str, bool, str]:
    """The discarded diff, whether it was cut, and `reason`. When git refuses to give the diff, the
    diff is empty and the reason holds both why the step stopped and why it has no diff."""
    try:
        diff, cut = _discarded_diff(source, start)
    except RoadmapImplementError as failure:
        return "", False, f"{reason}\n{failure}"
    return diff, cut, reason


def _commit(source: Path, message: str) -> tuple[str, str]:
    """Commit the staged changes. The commit, and why the step stops when git refuses it. The
    hooks of the repository ran as an exit check (`_hooks_failure`), and the job installs no git
    hook, so the commit runs none."""
    done = _git(source, "commit", "-m", message)
    if done.returncode != 0:
        return "", MESSAGES.roadmap.implement_stop_commit_failed.format(output=_tail(done))
    return _git_output(source, "rev-parse", "HEAD").strip(), ""


# ── The step ──────────────────────────────────────────────────────────────────────────────


def _end_agent_processes() -> None:
    """End every process the agent's shell left, in a runner, before the job runs a program that
    gets the session's token. A `git` or `gh` child holds the token in its environment, and a
    process of the same user could read it. Raises `RoadmapImplementError` when one survives."""
    if load_settings().roadmap.implement.in_runner:
        end_leftover_processes()


def _turn(
    agent: Agent[None, str],
    model: Any,
    log: ToolCallLog,
    message: str,
    conversation: Conversation | None = None,
) -> _Run:
    """One turn of the agent. When it ends, so does every process of the agent's shell, before
    the job runs a program that gets the session's token."""
    try:
        return _run_agent(agent, model, log, message, conversation)
    finally:
        _end_agent_processes()


def _tree(source: Path) -> str:
    """The tree of the checkout as it is now, new files included."""
    _stage(source)
    return _git_output(source, "write-tree").strip()


@dataclass(frozen=True)
class _Ask:
    """The one extra turn of a step: its message, the files other than the `tasks.md` of the change
    that it may change, and the reason of the stop when it changes any other."""

    message: str
    may_change: frozenset[str]
    changed_reason: str


def _foreign_change(source: Path, inputs: StepInputs, tree: str, ask: _Ask) -> str | None:
    """Why the step stops when the checkout differs from `tree` in a file that `ask` does not let
    the turn change, else None. The `tasks.md` of the change is always allowed."""
    _git_output(source, "add", "-A")
    names = _git_output(source, "diff", "--cached", "--name-only", "--no-renames", "-z", tree)
    tasks = (inputs.change / "tasks.md").relative_to(source).as_posix()
    allowed = ask.may_change | {tasks}
    others = sorted(name for name in names.split("\0") if name and name not in allowed)
    if not others:
        return None
    return ask.changed_reason.format(paths=_paths_text(others))


def _unticked_fields(source: Path, inputs: StepInputs) -> dict[str, str]:
    """The path of the `tasks.md` of the change and the list of the unticked tasks of the group,
    for the message of an extra turn."""
    tasks_md = (inputs.change / "tasks.md").relative_to(source).as_posix()
    tasks = "\n".join(f"- {task.text}" for task in _unticked(inputs))
    return {"path": tasks_md, "tasks": tasks}


def _extra_ask(
    source: Path, inputs: StepInputs, failure: _Failure | None, log: ToolCallLog
) -> _Ask | None:
    """The extra turn that the result of the exit checks earns, or None. A failed static check or
    hook gets the turn that fixes it, and the message lists the unticked tasks too, so no turn for
    the ticks follows. A step whose checks passed gets the turn for the ticks when a task is
    unticked. No other failure gets a turn. The message names the stray files that the step
    deleted, and why (#3092). The caller counts the turns against `repair_rounds`."""
    texts = MESSAGES.roadmap
    removed = texts.implement_removed_note.format(paths=log.removed_text()) if log.removed else ""
    unticked = bool(_unticked(inputs))
    if failure is None:
        if not unticked:
            return None
        message = texts.implement_tick_turn.format(
            **_unticked_fields(source, inputs), removed=removed
        )
        return _Ask(message, frozenset(), texts.implement_stop_tick_turn_changed)
    if failure.repair_paths is None:
        return None
    ticks = texts.implement_repair_turn_ticks.format(**_unticked_fields(source, inputs))
    template = texts.implement_hook_turn if failure.hook else texts.implement_repair_turn
    message = template.format(
        failure=mask_secrets(failure.reason)[:CONST_ROADMAP_IMPLEMENT_REASON_CHARS],
        ticks=ticks if unticked else "",
        removed=removed,
    )
    return _Ask(message, failure.repair_paths, texts.implement_stop_repair_turn_changed)


def _extra_turn(
    agent: Agent[None, str],
    model: Any,
    log: ToolCallLog,
    source: Path,
    inputs: StepInputs,
    start: str,
    first: _Run,
    ask: _Ask,
) -> tuple[_Run, _Failure | None]:
    """One extra turn of a step (#2721, #2795, #3043): the same conversation and the same limits as
    the first turn, and the message of `ask`. The turns so far and this one together, and the
    first exit check that fails after it, if any. The turn may change only the files that `ask`
    names and the `tasks.md`. Every exit check runs again after it. The stray files of the turn
    are deleted first, so they are no change that `ask` does not allow (#3092). A turn that a
    limit ended, and a change that `ask` does not allow, give a failure that gets no more turns."""
    tree = _tree(source)
    run = first.then(_turn(agent, model, log, ask.message, first.conversation))
    if run.reason:
        return run, _Failure(run.reason)
    _remove_strays(source, inputs, log)
    foreign = _foreign_change(source, inputs, tree, ask)
    if foreign:
        return run, _Failure(foreign)
    return run, _exit_failure(source, inputs, start, log)


def _attempt(
    source: Path, model: Any, window: int, inputs: StepInputs, item: int, start: str
) -> StepOutcome:
    """Run the agent, then judge the exit and commit. A failed check or a missing tick gets an
    extra turn while one of the `roadmap.implement.repair_rounds` rounds is left."""
    budget = load_settings().roadmap.implement.repair_rounds
    rounds = 0
    with tempfile.TemporaryDirectory(prefix="devops-implement-home-") as home:
        log = ToolCallLog(source)
        agent = build_agent(model, source, inputs.instructions, window, Path(home), log)
        run = _turn(agent, model, log, inputs.message)
        failure = _Failure(run.reason) if run.reason else _exit_failure(source, inputs, start, log)
        while rounds < budget and (ask := _extra_ask(source, inputs, failure, log)) is not None:
            run, failure = _extra_turn(agent, model, log, source, inputs, start, run, ask)
            rounds += 1
    reason = failure.reason if failure else ""
    outcome = StepOutcome(
        item=item,
        group=inputs.group.number,
        title=inputs.group.title,
        status=StepStatus.STOPPED,
        last_message=run.last_message,
        requests=run.requests,
        tool_calls=run.tool_calls,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        removed=tuple(log.removed),
        repair_rounds=rounds,
    )
    reason = reason or _unticked_failure(inputs) or ""
    commit = ""
    if not reason:
        commit, reason = _commit(source, f"{inputs.group.title} (#{item})")
    if reason:
        diff, cut, reason = _read_discarded_diff(source, start, reason)
        return outcome.model_copy(update={"reason": reason, "diff": diff, "diff_cut": cut})
    return outcome.model_copy(update={"status": StepStatus.DONE, "commit": commit})


def run_step(
    store: ItemReader,
    *,
    item: int,
    group: int,
    source: Path,
    model: Any,
    window: int,
    fix: FixRequest | None = None,
) -> StepOutcome:
    """Run group `group` of item `item` in the checkout `source`, with the pydantic-ai `model`.

    The step commits the group as `<group title> (#<item>)` when every exit check passes, and
    otherwise resets the checkout to the commit it started at, also when the agent made commits or
    the run raises. It reads the item once and writes nothing to GitHub. A failed model call ends
    the step as stopped, with the diff of the work. Raises `RoadmapImplementError` for a step it
    refuses to start, and `AICredentialsError` when the model refuses the key. With `fix`, the
    step makes the failed check pass and ticks no task (`run_fix_step`).
    """
    inputs = build_step_inputs(store, item=item, group=group, source=source, window=window, fix=fix)
    _require_clean(source)
    start = _head(source)
    done = False
    try:
        outcome = _attempt(source, model, window, inputs, item, start)
        done = outcome.status is StepStatus.DONE
        return outcome
    finally:
        if not done:
            _reset(source, start)


def run_fix_step(
    store: ItemReader, *, item: int, fix: FixRequest, source: Path, model: Any, window: int
) -> StepOutcome:
    """Run the fix of the failed check `fix` for item `item` in the checkout `source`: a step
    whose group is "Make check <name> pass". It commits as `<that title> (#<item>)` when the
    exit checks pass, and `tasks.md` is as it was."""
    return run_step(
        store,
        item=item,
        group=CONST_ROADMAP_IMPLEMENT_FIX_GROUP,
        source=source,
        model=model,
        window=window,
        fix=fix,
    )


# ── The report and the dry run ────────────────────────────────────────────────────────────


def dry_run_step(repo: str, *, item: int, group: int, model: str) -> StepOutcome:
    """The outcome of a dry run: the requests a step makes, and no request made. A step reads the
    item once, and then asks `model` up to `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` times."""
    from devops_cli.dry_run.requests import PlannedRequest
    from devops_cli.roadmap.request_plan import StoreRequests

    texts = MESSAGES.roadmap
    asked = PlannedRequest(
        method=texts.implement_model_request,
        target=texts.implement_model_target.format(model=model, group=group, item=item),
        repeat=texts.implement_model_repeat.format(limit=CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS),
    )
    planned = (*StoreRequests(repo).issue(f"#{item}"), asked)
    return StepOutcome(
        item=item,
        group=group,
        title="",
        status=StepStatus.STOPPED,
        reason=texts.implement_dry_run_reason,
        dry_run=True,
        planned_requests=tuple(request.line() for request in planned),
    )


def render_outcome(outcome: StepOutcome, repo: str, fmt: str) -> None:
    """Print the outcome in the format `fmt`: a table, or the model's fields as JSON or YAML."""
    from devops_cli.config.constants import CONST_OUTPUT_FORMAT_TABLE
    from devops_cli.output import print_key_values, write_stdout
    from devops_cli.output.markup import escape_text
    from devops_cli.output.serialization import emit_serialized

    if fmt != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(outcome.model_dump(mode="json"), fmt)
        return
    texts = MESSAGES.roadmap
    if outcome.dry_run:
        heading = texts.plan_dry_run_title.format(job="implement", repo=repo)
        numbered = (f"{number}. {line}" for number, line in enumerate(outcome.planned_requests, 1))
        write_stdout("\n\n".join([heading, texts.plan_dry_run, "\n".join(numbered)]) + "\n")
        return
    labels = texts.implement_labels
    rows = {
        labels["status"]: outcome.status.value,
        labels["reason"]: escape_text(outcome.reason),
        labels["commit"]: outcome.commit,
        labels["requests"]: str(outcome.requests),
        labels["tool_calls"]: str(outcome.tool_calls),
        labels["input_tokens"]: str(outcome.input_tokens),
        labels["output_tokens"]: str(outcome.output_tokens),
        labels["repair_rounds"]: str(outcome.repair_rounds),
        labels["last_message"]: escape_text(outcome.last_message),
    }
    if outcome.removed:
        rows[labels["removed"]] = escape_text(", ".join(outcome.removed))
    title = texts.implement_title.format(
        item=outcome.item, group=outcome.group, title=outcome.title
    )
    print_key_values(title, rows)
