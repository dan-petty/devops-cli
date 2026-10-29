"""`devops roadmap implement` (#2664): one task group of a staged change, run in one bounded
context.

A change is `openspec/changes/<issue>-<slug>/` in a checkout, and its `tasks.md` holds numbered
groups (`## <n>. <title>`). A step reads one group and builds the inputs the model gets: the
item's title, problem and acceptance criteria, the change's `proposal.md`, `design.md` and
`tasks.md`, the group, and the files the group names, packed. It counts their tokens before the
first request and refuses a step that does not fit the window of `ai.tasks.implement`.

The run is one pydantic-ai agent on the harness's `Coder`, tuned where its parts are public: a
shell with an allowlist, a smaller cap on each tool result, and the window of the task. The step
judges the exit, not the model: the tasks of the group are ticked, the verification commands pass,
and the static checks pass on the changed files. Then it commits the checkout, or it resets it.
A step writes nothing to GitHub.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from markdown_it import MarkdownIt
from markdown_it.token import Token
from platformdirs import user_cache_dir
from pydantic import BaseModel, ConfigDict
from pydantic_ai import Agent, capture_run_messages
from pydantic_ai.capabilities import AbstractCapability, LocalWorkspace
from pydantic_ai.exceptions import ModelAPIError, UnexpectedModelBehavior, UsageLimitExceeded
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
    CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS,
    CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS,
    CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS,
    CONST_ROADMAP_IMPLEMENT_OUTPUT_TAIL_LINES,
    CONST_ROADMAP_IMPLEMENT_PROBLEM_HEADINGS,
    CONST_ROADMAP_IMPLEMENT_TOOL_MAX_CHARS,
    CONST_ROADMAP_IMPLEMENT_TOOL_RETRIES,
    CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS,
)
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.agent_run import drain_events, model_call_error, record_run_spend

if TYPE_CHECKING:
    from devops_cli.roadmap.store import Item, RoadmapStore

_MARKDOWN = MarkdownIt("commonmark")
_CHECKBOXES = ("[ ]", "[x]", "[X]")
_VERIFICATION = "Verification:"
_CHANGE_DOCUMENTS = ("proposal.md", "design.md", "tasks.md")
_PROMPT = "roadmap_implement_step.md"


@dataclass(frozen=True)
class GroupTask:
    """One task of a group: its text with the checkbox, and whether it is ticked."""

    text: str
    ticked: bool
    verification: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class TaskGroup:
    """A numbered `##` section of a `tasks.md`: its tasks, and its text from its heading to the
    next `##` heading."""

    number: int
    title: str
    tasks: tuple[GroupTask, ...]
    text: str

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
    )


def _headings(tokens: Sequence[Token], tag: str) -> list[tuple[int, int, str]]:
    """The index, the first line and the text of each heading of `tag`."""
    return [
        (index, token.map[0], tokens[index + 1].content)
        for index, token in enumerate(tokens)
        if token.type == "heading_open" and token.tag == tag and token.map is not None
    ]


def parse_task_groups(tasks_md: str) -> list[TaskGroup]:
    """The numbered groups of a `tasks.md`, in file order. A `##` section whose heading is not
    `<n>. <title>`, such as `## Workflow follow-up`, is no group, and ends the one before it."""
    tokens = _MARKDOWN.parse(tasks_md)
    lines = tasks_md.splitlines()
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
            )
        )
    return groups


def _section(body: str, titles: frozenset[str]) -> str:
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
    text = _section(item.body, wanted) or item.body.strip()
    return f"# Item #{item.number}: {item.title}\n\n{text}"


def find_change(source: Path, item: int) -> Path:
    """The one folder `openspec/changes/<item>-*/` of the checkout."""
    pattern = f"{item}-*"
    found = sorted(
        path for path in (source / CONST_OPENSPEC_CHANGES_DIR).glob(pattern) if path.is_dir()
    )
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
class StepInputs:
    """What one step gives the model: the instructions, the user message, and their tokens.
    `change` is the change folder, and `groups` are the groups of its `tasks.md` before the
    run."""

    group: TaskGroup
    change: Path
    groups: tuple[TaskGroup, ...]
    instructions: str
    message: str
    tokens: int


def _files_section(source: Path, group: TaskGroup) -> str:
    """The packed files of the group, each under its path."""
    parts = [
        f"## {path.relative_to(source.resolve())}\n\n```\n{_packed(path)}\n```"
        for path in named_files(source, group)
    ]
    return "# Files the group names (signatures only)\n\n" + "\n\n".join(parts) if parts else ""


def build_step_inputs(
    store: RoadmapStore, *, item: int, group: int, source: Path, window: int
) -> StepInputs:
    """The inputs of group `group` of item `item`, read from the checkout `source`.

    Raises `RoadmapImplementError` for an issue that is no Item, a change that is not in the
    checkout, a group the change lacks, and inputs that measure more than `window` minus
    `CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS` tokens.
    """
    held = store.item(item)
    if held is None:
        raise RoadmapImplementError(MESSAGES.roadmap.implement_not_item.format(number=item))
    change = find_change(source, item)
    documents = {name: (change / name).read_text(encoding="utf-8") for name in _CHANGE_DOCUMENTS}
    groups = parse_task_groups(documents["tasks.md"])
    chosen = next((candidate for candidate in groups if candidate.number == group), None)
    if chosen is None:
        raise RoadmapImplementError(
            MESSAGES.roadmap.implement_no_group.format(
                change=change.name,
                group=group,
                groups=", ".join(str(candidate.number) for candidate in groups) or "none",
            )
        )
    sections = [
        issue_inputs(held),
        *(f"# {name} of the change\n\n{text.strip()}" for name, text in documents.items()),
        f"# Your group\n\n{chosen.text}",
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
    )


# ── The outcome ───────────────────────────────────────────────────────────────────────────


class StepStatus(StrEnum):
    """How a step ended: its group is committed, or the step stopped and reset the checkout."""

    DONE = "done"
    STOPPED = "stopped"


class StepOutcome(BaseModel):
    """The report of a step. `reason` is why a stopped step stopped: the class of the pydantic-ai
    error that ended the run, or the first exit check that failed. `commit` is the commit of a
    done step. `planned_requests` are the requests a dry run lists."""

    model_config = ConfigDict(frozen=True)

    item: int
    group: int
    title: str
    status: StepStatus
    reason: str = ""
    last_message: str = ""
    commit: str = ""
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
    user keeps it, so that `uv run` finds its packages."""
    return {
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "UV_CACHE_DIR": os.environ.get("UV_CACHE_DIR") or user_cache_dir("uv"),
    }


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
    model: Any, source: Path, instructions: str, window: int, home: Path
) -> Agent[None, str]:
    """The agent of a step: `Coder` on a local workspace at `source`, whose shell runs with the
    scratch `home`. It has no `delegate_task` tool, so the limits of a run cover the whole step,
    and it loads no instruction file of the checkout, so its context is the inputs of the step.
    The shell is no security boundary: the runner of the step is the sandbox."""
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
        capabilities=[LocalWorkspace(source), tuned],
    )


@dataclass(frozen=True)
class _Run:
    """What a run left: why it ended early (the class of the pydantic-ai error, or empty), the
    last text of the model, and what it spent."""

    reason: str
    last_message: str
    requests: int
    input_tokens: int
    output_tokens: int


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


def _run_agent(agent: Agent[None, str], model: Any, message: str) -> _Run:
    """Run the agent under the limits of a step and record its spend. Raises the client error
    that refine raises when a model call fails."""
    limits = UsageLimits(
        request_limit=CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS,
        tool_calls_limit=CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS,
    )
    reason = last = ""
    error = None
    started = time.monotonic()
    with capture_run_messages() as messages:
        try:
            last = agent.run_sync(
                message, usage_limits=limits, event_stream_handler=drain_events
            ).output
        except (UsageLimitExceeded, UnexpectedModelBehavior) as stopped:
            reason, last = type(stopped).__name__, _last_text(messages)
        except ModelAPIError as exc:
            # Raised outside this handler, so a logged traceback holds no reply text.
            error = model_call_error(exc, "The step's")
        finally:
            record_run_spend(model, messages, time.monotonic() - started, stage="implement")
    if error is not None:
        raise error
    replies = [reply for reply in messages if isinstance(reply, ModelResponse)]
    return _Run(
        reason=reason,
        last_message=last,
        requests=len(replies),
        input_tokens=sum(reply.usage.input_tokens for reply in replies),
        output_tokens=sum(reply.usage.output_tokens for reply in replies),
    )


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


def _tasks_failure(inputs: StepInputs) -> str | None:
    """The first rule of the tasks that the run broke: the group changed beyond its checkboxes,
    a task of the group is not ticked, or another group changed."""
    texts = MESSAGES.roadmap
    number = inputs.group.number
    try:
        tasks_md = (inputs.change / "tasks.md").read_text(encoding="utf-8")
    except OSError, UnicodeDecodeError:
        return texts.implement_stop_tasks_edited.format(group=number)
    after = {g.number: g for g in parse_task_groups(tasks_md)}
    mine = after.get(number)
    if mine is None or _shape(mine) != _shape(inputs.group):
        return texts.implement_stop_tasks_edited.format(group=number)
    unticked = next((task for task in mine.tasks if not task.ticked), None)
    if unticked is not None:
        return texts.implement_stop_unticked.format(task=unticked.text)
    before = {g.number: g for g in inputs.groups}
    changed = sorted(
        other
        for other in (before.keys() | after.keys()) - {number}
        if _whole(before.get(other)) != _whole(after.get(other))
    )
    return texts.implement_stop_group_changed.format(group=changed[0]) if changed else None


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
    commit, so a checkout that left `start` fails the first check."""
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


def _commit(source: Path, message: str) -> tuple[str, str]:
    """Commit the staged changes, with the hooks of the repository. The commit, and why the
    step stops when git refuses it."""
    done = _git(source, "commit", "-m", message)
    if done.returncode != 0:
        return "", MESSAGES.roadmap.implement_stop_commit_failed.format(output=_tail(done))
    return _git_output(source, "rev-parse", "HEAD").strip(), ""


# ── The step ──────────────────────────────────────────────────────────────────────────────


def _attempt(
    source: Path, model: Any, window: int, inputs: StepInputs, item: int, start: str
) -> StepOutcome:
    """Run the agent, then judge the exit and commit."""
    with tempfile.TemporaryDirectory(prefix="devops-implement-home-") as home:
        agent = build_agent(model, source, inputs.instructions, window, Path(home))
        run = _run_agent(agent, model, inputs.message)
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
    reason = run.reason or _exit_failure(source, inputs, start)
    commit = ""
    if not reason:
        commit, reason = _commit(source, f"{inputs.group.title} (#{item})")
    if reason:
        return outcome.model_copy(update={"reason": reason})
    return outcome.model_copy(update={"status": StepStatus.DONE, "commit": commit})


def run_step(
    store: RoadmapStore, *, item: int, group: int, source: Path, model: Any, window: int
) -> StepOutcome:
    """Run group `group` of item `item` in the checkout `source`, with the pydantic-ai `model`.

    The step commits the group as `<group title> (#<item>)` when every exit check passes, and
    otherwise resets the checkout to the commit it started at, also when the agent made commits or the run raises. It reads the
    item once and writes nothing to GitHub. Raises `RoadmapImplementError` for a step it
    refuses to start, and the client error of a failed model call.
    """
    inputs = build_step_inputs(store, item=item, group=group, source=source, window=window)
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
        labels["reason"]: outcome.reason,
        labels["commit"]: outcome.commit,
        labels["requests"]: str(outcome.requests),
        labels["input_tokens"]: str(outcome.input_tokens),
        labels["output_tokens"]: str(outcome.output_tokens),
        labels["last_message"]: outcome.last_message,
    }
    title = texts.implement_title.format(
        item=outcome.item, group=outcome.group, title=outcome.title
    )
    print_key_values(title, rows)
