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

import io
import os
import shlex
import subprocess
import tempfile
import time
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from markdown_it import MarkdownIt
from markdown_it.token import Token
from platformdirs import user_cache_dir
from pydantic import BaseModel, ConfigDict
from pydantic_ai import Agent, capture_run_messages
from pydantic_ai.capabilities import AbstractCapability, LocalWorkspace
from pydantic_ai.conversation import Conversation
from pydantic_ai.exceptions import (
    AgentRunError,
    ModelAPIError,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
)
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.usage import UsageLimits
from pydantic_ai_harness.compaction import ClearToolResults, WarnNearLimits
from pydantic_ai_harness.shell import Shell
from pydantic_ai_harness.tool_output_limits import Band, ToolOutputLimits, Truncate

from devops_cli.ai.context_budget import count_tokens, truncate_to_token_limit
from devops_cli.ai.context_packer import ContextPacker, PackingConfig
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
    CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS,
    CONST_ROADMAP_IMPLEMENT_CRITERIA_HEADINGS,
    CONST_ROADMAP_IMPLEMENT_DENIED_OPERATORS,
    CONST_ROADMAP_IMPLEMENT_DIFF_CHARS,
    CONST_ROADMAP_IMPLEMENT_DIFF_READ_CHARS,
    CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS,
    CONST_ROADMAP_IMPLEMENT_FIX_GROUP,
    CONST_ROADMAP_IMPLEMENT_LOG_CHARS,
    CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS,
    CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS,
    CONST_ROADMAP_IMPLEMENT_OUTPUT_TAIL_LINES,
    CONST_ROADMAP_IMPLEMENT_PROBLEM_HEADINGS,
    CONST_ROADMAP_IMPLEMENT_REASON_PATHS,
    CONST_ROADMAP_IMPLEMENT_TOOL_MAX_CHARS,
    CONST_ROADMAP_IMPLEMENT_TOOL_RETRIES,
    CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.process import run_subprocess
from devops_cli.core.process_hardening import end_leftover_processes
from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.lang import MESSAGES
from devops_cli.output import print_muted
from devops_cli.roadmap.agent_run import (
    bounded_text,
    drain_events,
    model_call_error,
    record_run_spend,
)
from devops_cli.roadmap.implement_shell_refusal import shell_refusal_hooks
from devops_cli.roadmap.implement_tool_log import ToolCallLog
from devops_cli.security.sanitizer import mask_secrets

if TYPE_CHECKING:
    from devops_cli.roadmap.store import Item, RoadmapStore

_MARKDOWN = MarkdownIt("commonmark")
_CHECKBOXES = ("[ ]", "[x]", "[X]")
_VERIFICATION = "Verification:"
_CHANGE_DOCUMENTS = ("proposal.md", "design.md", "tasks.md")
_PROMPT = "roadmap_implement_step.md"


@dataclass(frozen=True)
class GroupTask:
    """One task of a group: its text with the checkbox, and whether it is ticked. `line` is the
    zero-based line of the task in its file, or -1 for a task that no file holds. It is no part of
    the comparison: a blank line that moves a task changes no task."""

    text: str
    ticked: bool
    verification: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()
    line: int = field(default=-1, compare=False)


@dataclass(frozen=True)
class TaskGroup:
    """A numbered `##` section of a `tasks.md`: its tasks, and its text from its heading to the
    next `##` heading. `first_line` is the zero-based line of its heading, or -1 for a group that
    no file holds. It is no part of the comparison, like `GroupTask.line`."""

    number: int
    title: str
    tasks: tuple[GroupTask, ...]
    text: str
    first_line: int = field(default=-1, compare=False)

    @property
    def verification_commands(self) -> tuple[str, ...]:
        """The code spans of the `Verification:` lines of the tasks, each once, in file order."""
        return tuple(dict.fromkeys(c for task in self.tasks for c in task.verification))

    @property
    def named_paths(self) -> tuple[str, ...]:
        """The code spans of the text of the tasks, each once: the files the group may name."""
        return tuple(dict.fromkeys(p for task in self.tasks for p in task.paths))


def _code_spans(inline: Token) -> tuple[str, ...]:
    """The code spans of an inline token."""
    return tuple(child.content for child in inline.children or () if child.type == "code_inline")


def _list_items(tokens: Sequence[Token]) -> Iterator[Sequence[Token]]:
    """The tokens of each top-level list item of `tokens`."""
    start = 0
    for index, token in enumerate(tokens):
        if token.type == "list_item_open" and token.level == 1:
            start = index
        elif token.type == "list_item_close" and token.level == 1:
            yield tokens[start : index + 1]


def _task_of(item: Sequence[Token]) -> GroupTask | None:
    """The task a list item is, or None when its text starts with no checkbox."""
    lines = [token for token in item if token.type == "inline"]
    if not lines or lines[0].content[:3] not in _CHECKBOXES:
        return None
    verification = tuple(
        command
        for line in lines[1:]
        if line.content.startswith(_VERIFICATION)
        for command in _code_spans(line)
    )
    return GroupTask(
        text=lines[0].content,
        ticked=lines[0].content[:3] != _CHECKBOXES[0],
        verification=verification,
        paths=_code_spans(lines[0]),
        line=lines[0].map[0] if lines[0].map else -1,
    )


def _headings(tokens: Sequence[Token], tag: str) -> list[tuple[int, int, str]]:
    """The index, the first line and the text of each heading of `tag`."""
    return [
        (index, token.map[0], tokens[index + 1].content)
        for index, token in enumerate(tokens)
        if token.type == "heading_open" and token.tag == tag and token.map is not None
    ]


def _file_lines(text: str) -> list[str]:
    """The lines of `text` with their line ends, split as markdown-it splits: at `\\n`, `\\r` and
    `\\r\\n`, and nowhere else. `"".join` of the lines is `text`. The line numbers of the tokens
    index this list."""
    return io.StringIO(text, newline="").readlines()


def parse_task_groups(tasks_md: str) -> list[TaskGroup]:
    """The numbered groups of a `tasks.md`, in file order. A `##` section whose heading is not
    `<n>. <title>`, such as `## Workflow follow-up`, is no group, and ends the one before it."""
    tokens = _MARKDOWN.parse(tasks_md)
    lines = [line.rstrip("\r\n") for line in _file_lines(tasks_md)]
    headings = _headings(tokens, "h2")
    groups: list[TaskGroup] = []
    for position, (index, first_line, heading) in enumerate(headings):
        number, dot, title = heading.partition(". ")
        if not dot or not number.isdigit():
            continue
        last = headings[position + 1] if position + 1 < len(headings) else None
        end_index = last[0] if last else len(tokens)
        end_line = last[1] if last else len(lines)
        tasks = (_task_of(item) for item in _list_items(tokens[index:end_index]))
        groups.append(
            TaskGroup(
                number=int(number),
                title=title,
                tasks=tuple(task for task in tasks if task is not None),
                text="\n".join(lines[first_line:end_line]).rstrip(),
                first_line=first_line,
            )
        )
    return groups


def section_text(body: str, titles: frozenset[str]) -> str:
    """The text of each section of `body` whose heading is one of `titles`, heading included.
    A section ends at the next heading of its level or a higher one."""
    tokens = _MARKDOWN.parse(body)
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


def _packed(path: Path) -> str:
    """A file for the inputs: a Python file as its signatures, any other as its start."""
    if path.suffix == ".py":
        config = PackingConfig(
            max_tokens=CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS, strip_private=False
        )
        return ContextPacker().pack_file(path, config=config).content
    text = path.read_text(encoding="utf-8", errors="replace")
    return truncate_to_token_limit(text, CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS)


def named_files(source: Path, group: TaskGroup) -> list[Path]:
    """The files of the checkout that the group names: each code span of its tasks that is an
    existing file inside the checkout. A span that names a file that does not exist yet is
    left out."""
    root = source.resolve()
    resolved = (Path(os.path.normpath(root / span)) for span in group.named_paths)
    return [path for path in resolved if path.is_relative_to(root) and os.path.isfile(path)]


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
    `change` is the change folder, and `groups` are the groups of its `tasks.md` before the
    run. `region` holds the raw lines of the own group in that file, with their line ends: from
    its heading to the heading of the next numbered group, or to the end of the file. A fix step
    has none."""

    group: TaskGroup
    change: Path
    groups: tuple[TaskGroup, ...]
    instructions: str
    message: str
    tokens: int
    fix: FixRequest | None = None
    region: tuple[str, ...] = ()


def _region_bounds(groups: Sequence[TaskGroup], number: int, size: int) -> tuple[int, int]:
    """The first line of group `number` and the line where its region ends: the heading of the
    next numbered group in file order, or `size`, the number of lines of the file. The region holds
    the unnumbered sections between two groups too, so a text that the model puts there is part of
    the region that the step restores."""
    index = next(i for i, group in enumerate(groups) if group.number == number)
    following = groups[index + 1].first_line if index + 1 < len(groups) else size
    return groups[index].first_line, following


def _files_section(source: Path, group: TaskGroup) -> str:
    """The packed files of the group, each under its path."""
    parts = [
        f"## {path.relative_to(source.resolve())}\n\n```\n{_packed(path)}\n```"
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


def _own_region(
    tasks_md: str, groups: Sequence[TaskGroup], chosen: TaskGroup, fix: FixRequest | None
) -> tuple[str, ...]:
    """The raw lines of the own group in `tasks_md`, as `StepInputs.region` holds them. `tasks_md`
    is the text of the file read with its line ends."""
    if fix is not None:
        return ()
    lines = _file_lines(tasks_md)
    first, end = _region_bounds(groups, chosen.number, len(lines))
    return tuple(lines[first:end])


def build_step_inputs(
    store: RoadmapStore,
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
        groups=tuple(groups),
        instructions=instructions,
        message=message,
        tokens=tokens,
        fix=fix,
        region=_own_region(raw_tasks, groups, chosen, fix),
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
    input_tokens: int = 0
    output_tokens: int = 0
    dry_run: bool = False
    planned_requests: tuple[str, ...] = ()


# ── The agent ─────────────────────────────────────────────────────────────────────────────


def shell_environment(home: Path) -> dict[str, str]:
    """The variables a shell command gets on top of the workspace's own: a scratch `home` in place
    of the user's, so that no git configuration, credential helper or key of the user reaches the
    agent, no system git configuration, no prompt for a password, and the cache of `uv` where the
    user keeps it, so that `uv run` finds its packages. `UV_PYTHON` goes on when the process has
    it: the runner image sets it, as it forbids a Python download and `uv run` finds no
    interpreter without it."""
    env = {
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "UV_CACHE_DIR": os.environ.get("UV_CACHE_DIR") or user_cache_dir("uv"),
    }
    if interpreter := os.environ.get("UV_PYTHON"):
        env["UV_PYTHON"] = interpreter
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
    and it loads no instruction file of the checkout, so its context is the inputs of the step. The
    shell is no security boundary: the runner of the step is the sandbox."""
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
        capabilities=[LocalWorkspace(source), tuned, shell_refusal_hooks(), log.hooks()],
    )


@dataclass(frozen=True)
class _Run:
    """What a turn left: why it ended early (the class and the message of the pydantic-ai error,
    with the counts of `ToolCallLog`, or empty), the last text of the model, what it spent, and
    the conversation to continue when it ended."""

    reason: str
    last_message: str
    requests: int
    input_tokens: int
    output_tokens: int
    conversation: Conversation | None = None

    def then(self, later: _Run) -> _Run:
        """This turn followed by `later`, which continued its conversation: the end and the last
        text of `later`, and the spend of both."""
        return _Run(
            reason=later.reason,
            last_message=later.last_message or self.last_message,
            requests=self.requests + later.requests,
            input_tokens=self.input_tokens + later.input_tokens,
            output_tokens=self.output_tokens + later.output_tokens,
            conversation=later.conversation,
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


def _stop_reason(stopped: AgentRunError, log: ToolCallLog) -> str:
    """The reason of a run that a pydantic-ai error ended (#2758): the class and the message of the
    error, then the counts of refused and retried tool calls when either is not zero. It reads
    `message`, not `str()`, which adds the `body`, the text of the model (#2778)."""
    texts = MESSAGES.roadmap
    reason = texts.run_stop_reason.format(
        error=type(stopped).__name__, message=bounded_text(stopped.message)
    )
    if not (log.refused or log.retried):
        return reason
    counts = texts.implement_stop_counts.format(refused=log.refused_text(), retried=log.retried)
    return f"{reason}\n{counts}"


def _run_agent(
    agent: Agent[None, str],
    model: Any,
    log: ToolCallLog,
    message: str,
    conversation: Conversation | None = None,
) -> _Run:
    """One turn of the agent under the limits of a step, and its spend as one record. With
    `conversation`, the turn continues it: its messages and its usage carry over, so the limits
    count both turns. Raises the client error that refine raises when a model call fails."""
    limits = UsageLimits(
        request_limit=CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS,
        tool_calls_limit=CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS,
    )
    reason = last = ""
    kept = None
    error = None
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
        except ModelAPIError as exc:
            # Raised outside this handler, so a logged traceback holds no reply text.
            error = model_call_error(exc, "The step's")
        finally:
            replies = _new_replies(messages, conversation)
            record_run_spend(model, replies, time.monotonic() - started, stage="implement")
    if error is not None:
        raise error
    return _Run(
        reason=reason,
        last_message=last,
        requests=len(replies),
        input_tokens=sum(reply.usage.input_tokens for reply in replies),
        output_tokens=sum(reply.usage.output_tokens for reply in replies),
        conversation=kept,
    )


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


def _shape(group: TaskGroup | None) -> tuple[str, tuple[tuple[str, tuple[str, ...]], ...]] | None:
    """What a step may not change in its own group: the title, and the text and the commands of
    each task, but not the checkboxes."""
    if group is None:
        return None
    return group.title, tuple((task.text[3:], task.verification) for task in group.tasks)


def _whole(group: TaskGroup | None) -> tuple[str, tuple[GroupTask, ...]] | None:
    """What a step may not change in another group: the title and the tasks, checkboxes too."""
    return None if group is None else (group.title, group.tasks)


def _fix_tasks_failure(inputs: StepInputs, after: dict[int, TaskGroup]) -> str | None:
    """The rule of the tasks that a fix step broke: any change to any task, checkboxes too."""
    before = {g.number: g for g in inputs.groups}
    if any(_whole(before.get(n)) != _whole(after.get(n)) for n in before.keys() | after.keys()):
        return MESSAGES.roadmap.implement_stop_fix_tasks_changed
    return None


def duplicate_group(groups: Sequence[TaskGroup]) -> int | None:
    """The first number that two groups hold, or None. A dict keyed by number keeps the last of
    two such groups, so an edit of the first would pass every comparison."""
    twice = [number for number, count in Counter(g.number for g in groups).items() if count > 1]
    return twice[0] if twice else None


def _list_after(inputs: StepInputs) -> list[TaskGroup] | None:
    """The groups of the `tasks.md` as the run left it, in file order, or None when the file is
    gone or is not UTF-8 text."""
    try:
        tasks_md = (inputs.change / "tasks.md").read_text(encoding="utf-8")
    except OSError, UnicodeDecodeError:
        return None
    return parse_task_groups(tasks_md)


def _groups_after(inputs: StepInputs) -> dict[int, TaskGroup] | None:
    """The groups of the `tasks.md` as the run left it by number, or None when the file is gone or
    is not UTF-8 text. `_tasks_failure` has refused a number that two groups hold."""
    groups = _list_after(inputs)
    return None if groups is None else {g.number: g for g in groups}


def _unticked(inputs: StepInputs) -> tuple[GroupTask, ...]:
    """The tasks of the group that the run left unticked. A fix step ticks no task, and a file
    that the run broke has none: `_tasks_failure` reports it."""
    after = _groups_after(inputs)
    mine = after.get(inputs.group.number) if after is not None else None
    if mine is None or inputs.fix is not None:
        return ()
    return tuple(task for task in mine.tasks if not task.ticked)


def _write_boxes(
    inputs: StepInputs,
    wanted: dict[int, TaskGroup],
    current: dict[int, TaskGroup],
    numbers: list[int],
) -> None:
    """Write the checkbox of each task of groups `numbers` in `wanted` over the checkbox of the
    task at the same place in `current`, in the `tasks.md` that `current` was parsed from. The
    line ends are kept."""
    path = inputs.change / "tasks.md"
    lines = _file_lines(path.read_text(encoding="utf-8", newline=""))
    for number in numbers:
        for base, now in zip(wanted[number].tasks, current[number].tasks, strict=True):
            if base.text[:3] != now.text[:3]:
                lines[now.line] = lines[now.line].replace(now.text[:3], base.text[:3], 1)
    path.write_text("".join(lines), encoding="utf-8", newline="")


def _restore_ticks(
    inputs: StepInputs,
    before: dict[int, TaskGroup],
    after: dict[int, TaskGroup],
    numbers: list[int],
) -> str | None:
    """Write the checkboxes of groups `numbers` back to their state before the run, in the
    `tasks.md` as the run left it, and print one line that names the groups. The line ends are
    kept. The file is parsed again after the write: a group whose text still differs from its text
    before the run stops the step, so a wrong line or an edit beyond the checkboxes can never reach
    the commit. Why the step stops, or None."""
    _write_boxes(inputs, before, after, numbers)
    again = _groups_after(inputs) or {}
    for number in numbers:
        if again.get(number) != before[number]:
            return MESSAGES.roadmap.implement_stop_group_changed.format(group=number)
    groups = ", ".join(str(number) for number in numbers)
    print_muted(MESSAGES.roadmap.implement_restored_ticks.format(groups=groups), to_stderr=True)
    return None


def _other_groups_failure(inputs: StepInputs, after: dict[int, TaskGroup]) -> str | None:
    """The rule of the groups other than the own one: a change beyond their checkboxes stops the
    step with the first such group named. A change of their checkboxes only is restored, and the
    restored text must equal the text before the run."""
    before = {g.number: g for g in inputs.groups}
    others = sorted((before.keys() | after.keys()) - {inputs.group.number})
    edited = [n for n in others if _shape(before.get(n)) != _shape(after.get(n))]
    if edited:
        return MESSAGES.roadmap.implement_stop_group_changed.format(group=edited[0])
    changed = [n for n in others if before[n].text != after[n].text]
    return _restore_ticks(inputs, before, after, changed) if changed else None


def _same_tasks(mine: TaskGroup, base: TaskGroup) -> bool:
    """Whether `mine` holds the heading and the number of tasks of `base`, and the texts of its
    tasks in the order of `base` or in no order that `base` holds. A rewritten text is no
    difference. The same texts in another order are one."""
    kept = [task.text[3:] for task in mine.tasks]
    wanted = [task.text[3:] for task in base.tasks]
    reordered = kept != wanted and sorted(kept) == sorted(wanted)
    return mine.title == base.title and len(kept) == len(wanted) and not reordered


def _restored_wrong(inputs: StepInputs, mine: TaskGroup) -> bool:
    """Whether the file, after `_write_boxes` wrote the checkboxes of `mine`, holds the own group
    in another shape than before the run or with other checkboxes than `mine`."""
    base = inputs.group
    again = (_groups_after(inputs) or {}).get(base.number)
    return (
        again is None
        or _shape(again) != _shape(base)
        or [task.text[:3] for task in again.tasks] != [task.text[:3] for task in mine.tasks]
    )


def _restore_own_text(inputs: StepInputs, groups: Sequence[TaskGroup]) -> str | None:
    """Write the region of the own group from before the run over its region in the `tasks.md` as
    the run left it, keep the checkboxes that the run set, and print one line that names the group
    when the file changed. The region runs to the heading of the next numbered group, so a section
    that the run put inside or after the group goes too, and the bytes of the region are those of
    before the run. The file is parsed again after each write: the group must equal its text
    before the run, then keep its shape and the checkboxes of the run, so a wrong line can never
    reach the commit. Why the step stops, or None."""
    base = inputs.group
    mine = next(group for group in groups if group.number == base.number)
    path = inputs.change / "tasks.md"
    original = path.read_text(encoding="utf-8", newline="")
    lines = _file_lines(original)
    first, end = _region_bounds(groups, base.number, len(lines))
    lines[first:end] = inputs.region
    path.write_text("".join(lines), encoding="utf-8", newline="")
    current = _groups_after(inputs) or {}
    if current.get(base.number) != base:
        return MESSAGES.roadmap.implement_stop_tasks_edited.format(group=base.number)
    _write_boxes(inputs, {base.number: mine}, current, [base.number])
    if _restored_wrong(inputs, mine):
        return MESSAGES.roadmap.implement_stop_tasks_edited.format(group=base.number)
    if path.read_text(encoding="utf-8", newline="") != original:
        note = MESSAGES.roadmap.implement_restored_text.format(group=base.number)
        print_muted(note, to_stderr=True)
    return None


def _own_group_failure(inputs: StepInputs, groups: Sequence[TaskGroup]) -> str | None:
    """The rule of the own group: it keeps the heading and the number and the order of its tasks,
    else the step stops. Any other difference in its region is written back, with the checkboxes
    of the run. Why the step stops, or None."""
    mine = next((group for group in groups if group.number == inputs.group.number), None)
    if mine is None or not _same_tasks(mine, inputs.group):
        return MESSAGES.roadmap.implement_stop_tasks_edited.format(group=inputs.group.number)
    return _restore_own_text(inputs, groups)


def _tasks_failure(inputs: StepInputs) -> str | None:
    """The first rule of the tasks that the run broke: the own group changed the number, the order
    or the heading of its tasks (#2774), or another group changed beyond its checkboxes (#2767).
    The text of the own group, and the checkboxes of another group, are written back to their state
    before the run, so the commit holds the restored file. A fix step may change no task. The
    ticks of the group are no rule of this check: `_unticked_failure` judges them last."""
    texts = MESSAGES.roadmap
    number = inputs.group.number
    groups = _list_after(inputs)
    if groups is None:
        return (
            texts.implement_stop_fix_tasks_changed
            if inputs.fix
            else texts.implement_stop_tasks_edited.format(group=number)
        )
    twice = duplicate_group(groups)
    after = {g.number: g for g in groups}
    if twice is not None:
        return (
            texts.implement_stop_fix_tasks_changed
            if inputs.fix
            else texts.implement_stop_group_changed.format(group=twice)
        )
    if inputs.fix is not None:
        return _fix_tasks_failure(inputs, after)
    failure = _own_group_failure(inputs, groups)
    if failure is not None:
        return failure
    return _other_groups_failure(inputs, _groups_after(inputs) or after)


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


def _verification_failure(source: Path, group: TaskGroup) -> str | None:
    """Run each verification command of the group, from the tasks as they were before the run.
    A command whose program is not on the allowlist does not run."""
    texts = MESSAGES.roadmap
    for command in group.verification_commands:
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


def _static_failure(source: Path, changed: Sequence[str]) -> str | None:
    """Run `ruff check`, `ruff format --check` and `mypy --strict` on the changed Python files."""
    files = [path for path in changed if path.endswith(".py")]
    if not files:
        return None
    for tool in ((BIN_RUFF, "check"), (BIN_RUFF, "format", "--check"), (BIN_MYPY, "--strict")):
        argv = [BIN_UV, "run", *tool, *files]
        failure = _command_failure(source, argv, shlex.join(argv))
        if failure is not None:
            return failure
    return None


def _stage(source: Path) -> list[str]:
    """Stage every change of the checkout, and list the paths that the commit would add or
    change."""
    _git_output(source, "add", "-A")
    names = _git_output(source, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    return sorted(name for name in names.split("\0") if name)


def _exit_failure(source: Path, inputs: StepInputs, start: str) -> str | None:
    """The first exit check that fails, or None when every one passes. The step makes the only
    commit, so a checkout that left `start` fails the first check. The ticks are judged last, by
    `_unticked_failure`, as a step with a task unticked gets a turn for them first."""
    head = _head(source)
    if head != start:
        return MESSAGES.roadmap.implement_stop_head_moved.format(start=start, head=head)
    failure = _tasks_failure(inputs)
    if failure is not None:
        return failure
    changed = _stage(source)
    if not changed:
        return MESSAGES.roadmap.implement_stop_no_change
    return _verification_failure(source, inputs.group) or _static_failure(source, changed)


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


def _commit(source: Path, message: str) -> tuple[str, str]:
    """Commit the staged changes, with the hooks of the repository. The commit, and why the
    step stops when git refuses it."""
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


def _foreign_change(source: Path, inputs: StepInputs, tree: str) -> str | None:
    """Why the step stops when the checkout differs from `tree` in a file other than the
    `tasks.md` of the change, else None."""
    _git_output(source, "add", "-A")
    names = _git_output(source, "diff", "--cached", "--name-only", "--no-renames", "-z", tree)
    tasks = (inputs.change / "tasks.md").relative_to(source).as_posix()
    others = sorted(name for name in names.split("\0") if name and name != tasks)
    if not others:
        return None
    shown = others[:CONST_ROADMAP_IMPLEMENT_REASON_PATHS]
    paths = ", ".join(shown)
    if len(others) > len(shown):
        paths += MESSAGES.roadmap.implement_paths_more.format(count=len(others) - len(shown))
    return MESSAGES.roadmap.implement_stop_tick_turn_changed.format(paths=paths)


def _tick_turn(
    agent: Agent[None, str],
    model: Any,
    log: ToolCallLog,
    source: Path,
    inputs: StepInputs,
    start: str,
    first: _Run,
) -> tuple[_Run, str]:
    """The one extra turn of a step whose checks passed and whose agent left tasks unticked: the
    same conversation and the same limits, a message that asks only for the ticks. The turn and
    the first together, and why the step stops, if it does. The turn may change only `tasks.md`.
    Every exit check runs again after it."""
    tasks_md = (inputs.change / "tasks.md").relative_to(source).as_posix()
    tasks = "\n".join(f"- {task.text}" for task in _unticked(inputs))
    message = MESSAGES.roadmap.implement_tick_turn.format(path=tasks_md, tasks=tasks)
    tree = _tree(source)
    run = first.then(_turn(agent, model, log, message, first.conversation))
    reason = (
        run.reason or _foreign_change(source, inputs, tree) or _exit_failure(source, inputs, start)
    )
    return run, reason or ""


def _attempt(
    source: Path, model: Any, window: int, inputs: StepInputs, item: int, start: str
) -> StepOutcome:
    """Run the agent, then judge the exit and commit."""
    with tempfile.TemporaryDirectory(prefix="devops-implement-home-") as home:
        log = ToolCallLog()
        agent = build_agent(model, source, inputs.instructions, window, Path(home), log)
        run = _turn(agent, model, log, inputs.message)
        reason = run.reason or _exit_failure(source, inputs, start) or ""
        if not reason and _unticked(inputs):
            run, reason = _tick_turn(agent, model, log, source, inputs, start, run)
    outcome = StepOutcome(
        item=item,
        group=inputs.group.number,
        title=inputs.group.title,
        status=StepStatus.STOPPED,
        last_message=run.last_message,
        requests=run.requests,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
    )
    reason = reason or _unticked_failure(inputs) or ""
    commit = ""
    if not reason:
        commit, reason = _commit(source, f"{inputs.group.title} (#{item})")
    if reason:
        diff, cut = _discarded_diff(source, start)
        return outcome.model_copy(update={"reason": reason, "diff": diff, "diff_cut": cut})
    return outcome.model_copy(update={"status": StepStatus.DONE, "commit": commit})


def run_step(
    store: RoadmapStore,
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
    otherwise resets the checkout to the commit it started at, also when the agent made commits or the run raises. It reads the
    item once and writes nothing to GitHub. Raises `RoadmapImplementError` for a step it
    refuses to start, and the client error of a failed model call. With `fix`, the step makes the
    failed check pass and ticks no task (`run_fix_step`).
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
    store: RoadmapStore, *, item: int, fix: FixRequest, source: Path, model: Any, window: int
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
        labels["input_tokens"]: str(outcome.input_tokens),
        labels["output_tokens"]: str(outcome.output_tokens),
        labels["last_message"]: escape_text(outcome.last_message),
    }
    title = texts.implement_title.format(
        item=outcome.item, group=outcome.group, title=outcome.title
    )
    print_key_values(title, rows)
