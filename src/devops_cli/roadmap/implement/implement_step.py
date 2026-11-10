"""`devops roadmap implement` (#2664): one task group of a staged change, run in one bounded
context.

A change is `openspec/changes/<issue>-<slug>/` in a checkout, and its `tasks.md` holds numbered
groups (`## <n>. <title>`). A step reads one group and builds the inputs the model gets: the
`AGENTS.md` of the checkout and the sections of the documents it routes the group to (`step_rules`),
the item's title, problem and acceptance criteria, the change's `proposal.md`, `design.md` and
`tasks.md`, the group, and the files the group names, packed. It counts their tokens before the
first request and refuses a step that does not fit the window of `ai.tasks.implement`.

The run is one pydantic-ai agent on the harness's `Coder`, tuned where its parts are public: a
shell with an allowlist, a smaller cap on each tool result, and the window of the task. The step
judges the exit, not the model: the tasks of the group change only in their checkboxes, the
verification commands pass, the static checks pass on the changed files, and the hooks pass. Then
the job ticks every task of the group (#3488), so a model that did the work and forgot the ticks
does not stop the step. Then the step commits the checkout, or it resets it. While the
agent works, the step keeps the work that is green: a task that the agent ticked and whose
verification passes becomes a `wip:` commit (`implement_wip.py`, #3054), and a reset goes back to the
last of them. A step writes nothing to GitHub; the caller pushes the `wip:` commits.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile
import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from http import HTTPStatus
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Final, Protocol, cast

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
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.settings import ModelSettings
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.usage import RunUsage, UsageLimits
from pydantic_ai_harness.compaction import ClearToolResults, WarnNearLimits
from pydantic_ai_harness.shell import Shell
from pydantic_ai_harness.tool_output_limits import Band, ToolOutputLimits, Truncate

from devops_cli.ai.client.models import AICredentialsError
from devops_cli.ai.context_budget import count_tokens
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.ci.fail_to_pass import is_test_file
from devops_cli.ci.typecheck import typecheck_argv, typecheck_files
from devops_cli.config.commands import (
    BIN_GIT,
    BIN_PYTEST,
    BIN_RUFF,
    BIN_UV,
)
from devops_cli.config.constants import (
    CONST_AI_GATEWAY_PROVIDER,
    CONST_OPENSPEC_CHANGES_DIR,
    CONST_PRE_COMMIT_COMMIT_STAGE,
    CONST_ROADMAP_IMPLEMENT_CRITERIA_HEADINGS,
    CONST_ROADMAP_IMPLEMENT_DIFF_CHARS,
    CONST_ROADMAP_IMPLEMENT_DIFF_READ_CHARS,
    CONST_ROADMAP_IMPLEMENT_FIX_GROUP,
    CONST_ROADMAP_IMPLEMENT_LOG_CHARS,
    CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS,
    CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS,
    CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS,
    CONST_ROADMAP_IMPLEMENT_OUTPUT_TAIL_LINES,
    CONST_ROADMAP_IMPLEMENT_OUTPUT_WINDOW_SHARE,
    CONST_ROADMAP_IMPLEMENT_PROBLEM_HEADINGS,
    CONST_ROADMAP_IMPLEMENT_REASON_CHARS,
    CONST_ROADMAP_IMPLEMENT_REASON_PATHS,
    CONST_ROADMAP_IMPLEMENT_REASON_TESTS,
    CONST_ROADMAP_IMPLEMENT_TOOL_MAX_CHARS,
    CONST_ROADMAP_IMPLEMENT_TOOL_RETRIES,
    CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS,
    CONST_ROADMAP_IMPLEMENT_VERIFY_CHARS,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.process import run_subprocess
from devops_cli.core.process_hardening import end_leftover_processes
from devops_cli.exceptions.ai_pydantic import LimitReached, OutputCapReached
from devops_cli.exceptions.roadmap import OverWindowError, RoadmapImplementError
from devops_cli.lang import MESSAGES
from devops_cli.output import print_muted
from devops_cli.roadmap.agent_run import (
    body_error_text,
    bounded_text,
    drain_events,
    model_call_error,
    record_run_spend,
)
from devops_cli.roadmap.failure import (
    ACTION_BY_CLASS,
    FailureAction,
    FailureClass,
    FailureEvidence,
    classify_failure,
)
from devops_cli.roadmap.fence import code_fence
from devops_cli.roadmap.implement.implement_base_replay import (
    BaseReplay,
    BaseStatus,
    VerifiedCommand,
    replay_group_tests,
)
from devops_cli.roadmap.implement.implement_hooks import commit_stage
from devops_cli.roadmap.implement.implement_limits import ItemSpend, StepBudget, limit_hooks
from devops_cli.roadmap.implement.implement_output_cap import output_cap_hooks
from devops_cli.roadmap.implement.implement_shell_policy import (
    HARNESS_DENIED_OPERATORS,
    IMPLEMENT_SHELL_PROGRAMS,
    fill_prompt,
    read_verification,
    shown,
)
from devops_cli.roadmap.implement.implement_shell_refusal import ShellRefusal
from devops_cli.roadmap.implement.implement_strays import stray_files, unplanned_paths
from devops_cli.roadmap.implement.implement_test_form import (
    TestForm,
    collected_items,
    named_forms,
)
from devops_cli.roadmap.implement.implement_test_names import lost_since, unrecorded_tests
from devops_cli.roadmap.implement.implement_tool_log import ToolCallLog
from devops_cli.roadmap.implement.implement_trace import ImplementTrace
from devops_cli.roadmap.implement.implement_wip import WipCommit, WipKeeper, restore_sources
from devops_cli.roadmap.mcp import ROLE_IMPLEMENTATION, build_roadmap_mcp_toolset
from devops_cli.roadmap.step_commit import step_commit_title
from devops_cli.roadmap.step_files import (
    CHECKBOXES,
    GroupTask,
    TaskGroup,
    file_lines,
    named_files,
    packed_file,
    parse_task_groups,
    section_text,
)
from devops_cli.roadmap.step_rules import rules_sections
from devops_cli.security.sanitizer import mask_secrets

if TYPE_CHECKING:
    from devops_cli.roadmap.stores.store import Item

_CHANGE_DOCUMENTS = ("proposal.md", "design.md", "tasks.md")
_PROMPT = "roadmap_implement_step.md"


class StepClass(StrEnum):
    """The class of a step, which selects its ladder of model tiers (#3060): a group of a change
    is `edit`, and the fix of a failed check is `repair`."""

    EDIT = "edit"
    REPAIR = "repair"


class ItemReader(Protocol):
    """What a step reads of the roadmap: the item of an issue number. `RoadmapStore` satisfies it,
    and so does the item of an evaluation fixture (#3030)."""

    def item(self, number: int) -> Item | None:
        """The item numbered `number`, or None when that issue is no item."""


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


@dataclass(frozen=True)
class EarlierStop:
    """The facts of the stop of the earlier Job (#4071): the end of the log of the check that
    failed, and the files that a rebase left in conflict. The first step of a run gets them."""

    check_log: str = ""
    conflict_files: tuple[str, ...] = ()

    def section(self) -> str:
        """The text under the heading `# The stop of the earlier Job`, or empty when the stop left
        no log and no file."""
        texts = MESSAGES.roadmap
        parts: list[str] = []
        if self.check_log:
            log = self.check_log[-CONST_ROADMAP_IMPLEMENT_LOG_CHARS:]
            parts.append(texts.implement_earlier_stop_log.format(fence=code_fence(log), log=log))
        if self.conflict_files:
            files = "\n".join(f"- {path}" for path in self.conflict_files)
            parts.append(texts.implement_earlier_stop_files.format(files=files))
        if not parts:
            return ""
        return texts.implement_earlier_stop.format(body="\n\n".join(parts))


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
    read with its line ends. The job writes that text back after each turn. `item_title` is the
    title of the item, which gives the type and the scope of the step commit. `hooks` is the
    trusted configuration of the hooks (`trusted_config`), or None when the repository has no hook
    (#3043). `recorded_tests` holds each test, as `path::name`, that the step may lose (#3490)."""

    group: TaskGroup
    change: Path
    tasks_md: str
    item_title: str
    instructions: str
    message: str
    tokens: int
    fix: FixRequest | None = None
    hooks: Path | None = None
    recorded_tests: frozenset[str] = frozenset()


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
    earlier: EarlierStop | None = None,
) -> StepInputs:
    """The inputs of group `group` of item `item`, read from the checkout `source`. With `fix`,
    the group is the fix of that failed check and `group` is not read. With `earlier`, the message
    holds the stop of the earlier Job (#4071).

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
        *rules_sections(source, chosen),
        issue_inputs(held),
        *(f"# {name} of the change\n\n{text.strip()}" for name, text in documents.items()),
        f"# Your group\n\n{chosen.text}",
        _tasks_file_section(source, change, fix),
        earlier.section() if earlier is not None else "",
        _log_section(fix),
        _files_section(source, chosen),
    ]
    message = "\n\n".join(section for section in sections if section)
    instructions = fill_prompt(load_task_prompt(_PROMPT))
    tokens = count_tokens(instructions) + count_tokens(message)
    limit = window - CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS
    if tokens > limit:
        raise OverWindowError(
            MESSAGES.roadmap.implement_over_window.format(
                measured=tokens,
                limit=limit,
                window=window,
                reserve=CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS,
            ),
            measured=tokens,
            limit=limit,
        )
    return StepInputs(
        group=chosen,
        change=change,
        tasks_md=raw_tasks,
        item_title=held.title,
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


class TierSpend(BaseModel):
    """The requests and tokens that one tier of the ladder spent for a step (#3060)."""

    model_config = ConfigDict(frozen=True)

    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def plus(self, run: _Run) -> TierSpend:
        """This spend and the spend of `run`."""
        return TierSpend(
            requests=self.requests + run.requests,
            input_tokens=self.input_tokens + run.input_tokens,
            output_tokens=self.output_tokens + run.output_tokens,
        )


class StepOutcome(BaseModel):
    """The report of a step. `reason` is why a stopped step stopped: the class and the message of
    the pydantic-ai error that ended the run, with the counts of refused and retried tool calls
    (#2758), or the first exit check that failed. `commit` is the commit of a done step. `diff` is
    the diff of the work that a stopped step discarded, with secrets masked and cut to
    `CONST_ROADMAP_IMPLEMENT_DIFF_CHARS` characters, and `diff_cut` says that it was cut (#2721).
    `tool_calls` counts the tool calls of the replies (#3030). `removed` lists the stray files that
    the step deleted (#3092). `repair_rounds` counts the extra turns that the step used (#3043).
    `tier` is the last tier that the step ran on, `tiers` names every tier it attempted, and
    `tier_spend` holds the requests and tokens of each tier (#3060). `failure_class` is the class
    of a stopped step, when the step knows its cause (#3476). `first_request_tokens` is the input
    tokens of the first model request of the step, which is the size of that request (#3499), and
    0 when no request got a reply. `planned_requests` are the requests a dry run lists. `fail_to_pass` is the replay of a behavior group's tests on its base commit,
    and `verified` holds the verify commands of a group of kind `other`, of a done step (#3042)."""

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
    tier: str = ""
    tiers: tuple[str, ...] = ()
    tier_spend: dict[str, TierSpend] = {}
    failure_class: FailureClass | None = None
    first_request_tokens: int = 0
    dry_run: bool = False
    planned_requests: tuple[str, ...] = ()
    fail_to_pass: BaseReplay | None = None
    verified: tuple[VerifiedCommand, ...] = ()


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
    and the refusal of the operators that start a second command (the pipe is read by `ShellRefusal`),
    the tool results get the cap of
    a step, and the context controls get the window of the task, in place of the registry's."""
    if isinstance(capability, Shell):
        return replace(
            capability,
            allowed_commands=list(IMPLEMENT_SHELL_PROGRAMS),
            denied_commands=[],
            denied_operators=list(HARNESS_DENIED_OPERATORS),
            allow_interactive=False,
            env=shell_environment(home),
        )
    if isinstance(capability, ClearToolResults | WarnNearLimits):
        return replace(capability, context_window=window)
    if isinstance(capability, ToolOutputLimits):
        cap = CONST_ROADMAP_IMPLEMENT_TOOL_MAX_CHARS
        return replace(capability, bands=[Band(over=cap, action=Truncate(max_chars=cap))])
    return capability


def output_cap(window: int) -> int:
    """The output cap of one model reply of a step, in tokens: a share of the context `window` of
    the task (`CONST_ROADMAP_IMPLEMENT_OUTPUT_WINDOW_SHARE`)."""
    return window // CONST_ROADMAP_IMPLEMENT_OUTPUT_WINDOW_SHARE


def request_timeout_seconds() -> float:
    """The deadline of one model call of a step, in seconds: the setting
    `roadmap.implement.request_timeout_seconds`."""
    return load_settings().roadmap.implement.request_timeout_seconds


def _ladder_tiers(step_class: StepClass, ladder: Sequence[str] | None = None) -> list[str]:
    """The tiers of `step_class`, weakest first: the `ladder` argument, else the setting
    `roadmap.implement.ladder`. A repeated or empty name counts once or not at all. An empty list
    runs the step on the model it was given, with no tier name (#3060)."""
    names = ladder
    if names is None:
        names = load_settings().roadmap.implement.ladder.get(step_class.value, ())
    return list(dict.fromkeys(name.strip() for name in names if name.strip()))


def _gateway_tier_health(tiers: Sequence[str]) -> dict[str, bool]:
    """Whether the gateway serves each tier now (#3060). A process that sends its steps to no
    gateway has no tier health to read, and every tier is healthy."""
    settings = load_settings()
    names = list(tiers)
    if settings.ai.provider != CONST_AI_GATEWAY_PROVIDER:
        return dict.fromkeys(names, True)
    from devops_cli.ai.gateway import GatewayRouter

    return GatewayRouter(config=settings.ai).tier_health(names)


def _tier_for_attempt(
    tiers: Sequence[str],
    attempt: int,
    tier_health: Callable[[Sequence[str]], Mapping[str, bool]],
) -> tuple[str, int]:
    """The first tier at or after `attempt` that the gateway reports healthy, and its index.
    When no tier from `attempt` is healthy, the tier of `attempt` itself: the call reports the
    failure, and a health endpoint that is down stops no step (#3060)."""
    if not tiers:
        return "", attempt
    health = tier_health(tiers)
    for index in range(min(attempt, len(tiers)), len(tiers)):
        if health.get(tiers[index], True):
            return tiers[index], index
    return tiers[min(attempt, len(tiers) - 1)], min(attempt, len(tiers) - 1)


IMPLEMENT_LOCAL_TOOL_NAMES: Final[frozenset[str]] = frozenset(
    {"read_file", "write_file", "edit_file", "list_files", "grep", "shell"}
)


def build_agent(
    model: Any,
    source: Path,
    instructions: str,
    window: int,
    home: Path,
    log: ToolCallLog,
    budget: StepBudget,
    *,
    mcp_toolset: AbstractToolset[Any] | None = None,
) -> Agent[None, str]:
    """The agent of a step: `Coder` on a local workspace at `source`, whose shell runs with the
    scratch `home`, the hint that a refusal of the shell adds (#2773), and the hooks of `log` for its
    tool calls (#2758). It has no `delegate_task` tool, so the limits of a run cover the whole step,
    and it loads no instruction file of the checkout, so its context is the inputs of the step. Each
    model call has an output cap, a share of `window`, and a deadline (#2869). Before each request the
    agent compares `budget` with its limits (#3053). The shell is no security boundary: the runner
    of the step is the sandbox."""
    from pydantic_ai_harness.coder import Coder

    coder = Coder[None](instructions=instructions, repo_context=False, sub_agents=False)
    # The visitor replaces leaves and removes none, so the tree is never empty.
    tuned = cast(
        AbstractCapability[None], coder.visit_and_replace(lambda leaf: _tune(leaf, window, home))
    )
    toolsets = [mcp_toolset] if mcp_toolset is not None else None
    return Agent(
        model,
        output_type=str,
        toolsets=toolsets,
        retries={"tools": CONST_ROADMAP_IMPLEMENT_TOOL_RETRIES},
        model_settings=ModelSettings(
            max_tokens=output_cap(window),
            request_timeout=request_timeout_seconds(),
        ),
        capabilities=[
            LocalWorkspace(source),
            tuned,
            ShellRefusal(log, source),
            log.hooks(),
            output_cap_hooks(output_cap(window)),
            limit_hooks(budget),
        ],
    )


@dataclass(frozen=True)
class _Run:
    """What a turn left: why it ended early (the class and the message of the pydantic-ai error,
    with the counts of `ToolCallLog`, or empty), the last text of the model, what it spent, and
    the conversation to continue when it ended, and the conversation to resume when a new send of
    the request can fix the error that ended it (#2794). `provider_error` says that a failed model
    call ended it, which moves the step to the next tier (#3060). `failure_class` is the class of
    `reason`: the output cap, or what the classifier reads in the text of the error (#3476). The
    tier decision and the stop of the step read this one class. `first_request_tokens` is the input
    tokens of the first request that got a reply, which is the size of that request (#3499), and 0
    when no request got one."""

    reason: str
    last_message: str
    requests: int
    input_tokens: int
    output_tokens: int
    tool_calls: int = 0
    conversation: Conversation | None = None
    resend: Conversation | None = None
    provider_error: bool = False
    failure_class: FailureClass | None = None
    first_request_tokens: int = 0

    def then(self, later: _Run) -> _Run:
        """This turn followed by `later`, which continued its conversation: the end and the last
        text of `later`, and the spend of both. The first request stays that of this turn, unless
        this turn got no reply."""
        return _Run(
            reason=later.reason,
            last_message=later.last_message or self.last_message,
            requests=self.requests + later.requests,
            input_tokens=self.input_tokens + later.input_tokens,
            output_tokens=self.output_tokens + later.output_tokens,
            first_request_tokens=self.first_request_tokens or later.first_request_tokens,
            tool_calls=self.tool_calls + later.tool_calls,
            conversation=later.conversation,
            resend=later.resend,
            provider_error=self.provider_error or later.provider_error,
            failure_class=later.failure_class,
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


def _ask_smaller_edit(sent: Conversation) -> Conversation:
    """`sent` with one more part at the end of its last request: the text that asks for a smaller
    edit (#3053). A tool call that the provider cannot parse fails again for the same
    conversation, so the request that follows it must differ. The conversation of a resend ends
    with a request, so the last message is one."""
    *earlier, last = sent.messages
    if not isinstance(last, ModelRequest):
        return sent
    ask = UserPromptPart(MESSAGES.roadmap.implement_parser_smaller_edit)
    return Conversation(
        messages=[*earlier, replace(last, parts=[*last.parts, ask])], usage=sent.usage
    )


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
    step ends the loop. The turn ends with the last send.

    A failure of class `parser` is deterministic for one conversation, so its resend carries the
    message that asks for a smaller edit, once on a tier. The next parser failure of the tier ends
    the turn with no resend, and the step stops with class `parser` (#3053). A tier is a new
    conversation, so the tier loop of `run_step` starts the count again."""
    run = _run_turn(agent, model, log, message, conversation)
    resends = CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS
    while run.resend is not None and resends > 0:
        sent = run.resend
        if run.failure_class is FailureClass.PARSER:
            if log.parser_failures:
                break
            log.parser_failures += 1
            sent = _ask_smaller_edit(sent)
        if log.trace is not None:
            log.trace.retry(run.reason)
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
    provider_error = False
    typed: FailureClass | None = None
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
                typed = FailureClass.OUTPUT_CAP
            elif isinstance(stopped, LimitReached):
                typed = FailureClass.LIMIT_REACHED
        except ModelAPIError as exc:
            refused = model_call_error(exc, "The step's")
            if isinstance(refused, AICredentialsError):
                # Raised outside this handler, so a logged traceback holds no reply text.
                error = refused
            else:
                reason, last = _model_call_reason(exc, log), _last_text(messages)
                resend = _resend_after(exc, messages, conversation)
                provider_error = True
        finally:
            replies = [*_new_replies(messages, conversation), *cut]
            record_run_spend(model, replies, time.monotonic() - started, stage="implement")
            if log.trace is not None:
                _trace_replies(log.trace, messages, replies)
    if error is not None:
        raise error
    return _Run(
        reason=reason,
        last_message=last,
        requests=len(replies),
        input_tokens=sum(reply.usage.input_tokens for reply in replies),
        output_tokens=sum(reply.usage.output_tokens for reply in replies),
        first_request_tokens=replies[0].usage.input_tokens if replies else 0,
        tool_calls=_tool_calls(replies),
        conversation=kept,
        resend=resend,
        provider_error=provider_error,
        failure_class=_run_class(reason, typed),
    )


def _run_class(reason: str, typed: FailureClass | None) -> FailureClass | None:
    """The class of the reason that ended a turn, or None when the turn ended well (#3476). The
    output cap and a spent budget are typed by the error that they raised (`typed`). Any other end
    is classified once, here, so the decision to move the tier and the stop of the step read the
    same class."""
    if not reason:
        return None
    if typed is not None:
        return typed
    return classify_failure(FailureEvidence(text=reason))


def _trace_replies(
    trace: ImplementTrace, messages: Sequence[ModelMessage], replies: Sequence[ModelResponse]
) -> None:
    """Add one `model` event for each of `replies` (#3032). The seconds are the time of the reply
    minus the time of the request before it. A reply that is not in `messages`, as one that the
    output cap cut, has no request to measure from, so its seconds are 0."""
    fresh = {id(reply) for reply in replies}
    seen: set[int] = set()
    asked: datetime | None = None
    for message in messages:
        if isinstance(message, ModelRequest):
            asked = message.timestamp
        elif isinstance(message, ModelResponse) and id(message) in fresh:
            seen.add(id(message))
            seconds = (message.timestamp - asked).total_seconds() if asked else 0.0
            _trace_reply(trace, message, max(seconds, 0.0))
    for reply in replies:
        if id(reply) not in seen:
            _trace_reply(trace, reply, 0.0)


def _trace_reply(trace: ImplementTrace, reply: ModelResponse, seconds: float) -> None:
    trace.model_call(
        reply.model_name or "", reply.usage.input_tokens, reply.usage.output_tokens, seconds
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
        timeout=load_settings().roadmap.implement.command_timeout_seconds,
    )


def _tail(done: subprocess.CompletedProcess[str]) -> str:
    """The last lines of what a command printed, each line escaped by `shown` and cut to
    `CONST_ROADMAP_IMPLEMENT_REASON_CHARS` characters, so the output holds no raw control
    character or bidi override when it reaches the comment of a stop."""
    lines = f"{done.stdout or ''}{done.stderr or ''}".strip().splitlines()
    return "\n".join(
        shown(line, CONST_ROADMAP_IMPLEMENT_REASON_CHARS)
        for line in lines[-CONST_ROADMAP_IMPLEMENT_OUTPUT_TAIL_LINES:]
    )


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


def _tick_group(source: Path, inputs: StepInputs) -> str | None:
    """Tick every unticked task of the own group in `tasks.md`, and stage the file (#3488). The job
    calls it when every exit check of the group passed, so the commit holds the ticks of the group,
    also those of a task that the model did not tick. A fix step ticks no task. The own group is
    the one that `_restore_tasks` wrote, so it is in the file and has the tasks of before the run.
    Returns None when the group is ticked or needs no tick, else the reason the job cannot tick it:
    the step stops with that reason, so it never ends done without its ticks."""
    if inputs.fix is not None:
        return None
    mine = _own_after(inputs)
    text = _tasks_after(inputs)
    if mine is None or text is None:
        return MESSAGES.roadmap.implement_stop_tick_unreadable.format(group=inputs.group.number)
    unticked = [task.line for task in mine.tasks if not task.ticked]
    if not unticked:
        return None
    lines = file_lines(text)
    for number in unticked:
        lines[number] = lines[number].replace(CHECKBOXES[0], CHECKBOXES[1], 1)
    path = inputs.change / "tasks.md"
    path.write_text("".join(lines), encoding="utf-8", newline="")
    _git_output(source, "add", "--", path.relative_to(source).as_posix())
    return None


def _command_failure(
    source: Path,
    argv: Sequence[str],
    named: str,
    *,
    negative: bool = False,
    trace: ImplementTrace | None = None,
    verified: list[VerifiedCommand] | None = None,
) -> str | None:
    """Run `argv` in the checkout. None when it exits 0, else why the step stops. A `negative`
    search passes on exit 1 (git found no match), and a match (exit 0) is why it stops. With a
    `trace`, the run is a `check` event: its exit status, or none for a timeout (#3032). With
    `verified`, the run is added to it with its masked, bounded output (#3042)."""
    limit = load_settings().roadmap.implement.command_timeout_seconds
    try:
        done = run_subprocess(list(argv), cwd=source, quiet=True, timeout=limit)
    except subprocess.TimeoutExpired:
        if trace is not None:
            trace.check(named, None)
        return MESSAGES.roadmap.implement_stop_command_timeout.format(command=named, seconds=limit)
    if trace is not None:
        trace.check(named, done.returncode)
    if verified is not None:
        verified.append(
            VerifiedCommand(command=named, status=done.returncode, output=mask_secrets(_tail(done)))
        )
    if done.returncode == (1 if negative else 0):
        return None
    if negative and done.returncode == 0:
        return MESSAGES.roadmap.implement_stop_search_found.format(
            command=named, output=_tail(done)
        )
    return MESSAGES.roadmap.implement_stop_command_failed.format(
        command=named, status=done.returncode, output=_tail(done)
    )


def commands_failure(
    source: Path,
    commands: Iterable[str],
    trace: ImplementTrace | None = None,
    verified: list[VerifiedCommand] | None = None,
) -> str | None:
    """Run each of `commands` in the checkout, in order: None when all exit 0, else why the first
    that did not stops the run. A command whose program is not on the allowlist does not run. A
    command that starts with `!` runs only as the negative search of `read_negative_search`,
    and passes when it finds nothing (#3263). The step runs the verification commands of a group,
    from the tasks as they were before the run."""
    for command in commands:
        named = shown(command, CONST_ROADMAP_IMPLEMENT_VERIFY_CHARS)
        found = read_verification(command)
        if isinstance(found, str):
            return MESSAGES.roadmap.implement_stop_command_refused.format(
                command=named, reason=found
            )
        failure = _command_failure(
            source, found.argv, named, negative=found.negative, trace=trace, verified=verified
        )
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
    listed = names[:limit]
    paths = separator.join(listed)
    if len(names) > len(listed):
        paths += MESSAGES.roadmap.implement_paths_more.format(count=len(names) - len(listed))
    return paths


def _tests_failure(source: Path, start: str, recorded: frozenset[str]) -> str | None:
    """Why the step stops when a test file lost a test that it had at `start`, and `recorded` does
    not name that test, else None. The reason names each file with up to
    `CONST_ROADMAP_IMPLEMENT_REASON_TESTS` of its tests. A file that does not parse is skipped:
    `_static_failure` reports its error."""
    lost = unrecorded_tests(lost_since(lambda *args: _git_output(source, *args), start), recorded)
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


def _format_failure(
    source: Path, changed: Sequence[str], trace: ImplementTrace | None = None
) -> str | None:
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
    failure = _command_failure(source, argv, shlex.join(argv), trace=trace)
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


def _static_failure(
    source: Path, changed: Sequence[str], trace: ImplementTrace | None = None
) -> str | None:
    """Run the static checks of the gate on the changed Python files (#3090). `ruff check` runs on
    every one and fixes nothing: a lint rule can point at a defect that the model must see. `mypy`
    runs, with the options of the gate, on the files that the gate type-checks, and on no other:
    `typecheck_files` names them. A step that changes only test files runs no `mypy`."""
    files = _python_files(changed)
    if not files:
        return None
    commands = [[BIN_UV, "run", BIN_RUFF, "check", "--", *files]]
    typed = typecheck_files(files)
    if typed:
        commands.append(typecheck_argv(["--", *typed]))
    for argv in commands:
        failure = _command_failure(source, argv, shlex.join(argv), trace=trace)
        if failure is not None:
            return failure
    return None


def _index_adds(source: Path) -> tuple[list[str], dict[str, str]]:
    """The paths that the index adds, and the old path of each added path that a rename moved
    (#3488). Git lists a rename once, with both paths, so the new path of a rename is no addition
    of `--diff-filter=A`. The renames are found with `-M`, which is the default of `git diff`."""
    text = _git_output(source, "diff", "--cached", "--name-status", "-z", "-M")
    fields = [field for field in text.split("\0") if field]
    added: list[str] = []
    moved: dict[str, str] = {}
    index = 0
    while index < len(fields):
        status = fields[index]
        if status.startswith("R"):
            old, new = fields[index + 1], fields[index + 2]
            added.append(new)
            moved[new] = old
            index += 3
        else:
            if status == "A":
                added.append(fields[index + 1])
            index += 2
    return added, moved


def _strays(source: Path, inputs: StepInputs) -> list[str]:
    """The stray files of the step (#3092, #3488): see `_remove_strays`. The untracked files and the
    files that the index adds, which the agent staged with `git add` or `git mv`. A fix step's group
    names no file, so its strays are the files outside the project directories."""
    listed = _git_output(source, "ls-files", "--others", "--exclude-standard", "-z")
    added, _ = _index_adds(source)
    names = [name for name in listed.split("\0") if name] + added
    change = inputs.change.relative_to(source).as_posix()
    return stray_files(names, inputs.group, change)


def _remove_strays(source: Path, inputs: StepInputs, log: ToolCallLog) -> None:
    """Unstage and delete the stray files of the step (#3092, #3488) and record their names in
    `log`. A stray file is a file that the group does not allow (`stray_files`): a file outside
    `src/`, `tests/`, `docs/` and `openspec/`, or a nested git repository. It is an untracked file
    that git does not ignore, or a new file that the agent staged. A rename into a stray name also
    puts back the old path of the file, so the commit does not delete it. It runs before the checks
    stage the checkout, so no stray file reaches `ruff`, `mypy` or the commit. A fix step removes its
    strays too, and keeps a new file under `src/`, `tests/`, `docs/` or `openspec/`. The paths go to
    git as literal names, so a name with glob characters matches only its own file."""
    strays = _strays(source, inputs)
    _, moved = _index_adds(source)
    if strays:
        _git_output(
            source,
            "--literal-pathspecs",
            "rm",
            "--cached",
            "--force",
            "--ignore-unmatch",
            "-q",
            "--",
            *strays,
        )
    for name in strays:
        _delete(source / name)
    restore_sources(
        lambda *args: _git_output(source, *args),
        source,
        [moved[name] for name in strays if name in moved],
    )
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
    a failure that gets no such turn. `hook` says that a hook of the project failed (#3043).
    `klass` is the class of the failure, when the check that failed knows its cause (#3476)."""

    reason: str
    repair_paths: frozenset[str] | None = None
    hook: bool = False
    klass: FailureClass | None = None


def _changed_test_files(source: Path, base: str) -> list[str]:
    """The test files that the step changed since `base`: its `wip:` commits and its staged files,
    so a test that a keeper committed on the way is still one of them (#3042)."""
    names = _git_output(source, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z", base)
    return [name for name in names.split("\0") if name and is_test_file(PurePosixPath(name))]


def _named_text(count: int | None) -> str:
    """The case count that a task names, as the step shows it: its number, or that the task states
    no count (#3451)."""
    if count is None:
        return MESSAGES.roadmap.implement_test_form_named_none
    return MESSAGES.roadmap.implement_test_form_named.format(count=count)


def _items_text(count: int) -> str:
    """The number of items that a collection reported, as the step shows it (#3451)."""
    if count == 1:
        return MESSAGES.roadmap.implement_test_form_item
    return MESSAGES.roadmap.implement_test_form_items.format(count=count)


def _form_check(form: TestForm, collected: int | None) -> str:
    """The name of the collection check of `form` in the trace: its path, the case count that the
    task names, and the count that the collection reported, or that it did not end (#3451)."""
    named = _named_text(form.count)
    if collected is None:
        return MESSAGES.roadmap.implement_test_form_check_stopped.format(
            path=form.path, named=named
        )
    return MESSAGES.roadmap.implement_test_form_check.format(
        path=form.path, named=named, collected=_items_text(collected)
    )


def _form_differs(form: TestForm, collected: int) -> bool:
    """Whether a collection of `collected` items does not have the form that the task names
    (#3451). A task that states no count still names a parametrized test, so its file collects more
    than one item: a loop over the cases collects one."""
    if form.count is None:
        return collected <= 1
    return collected != form.count


def _form_failure(
    source: Path, form: TestForm, trace: ImplementTrace | None
) -> _Failure | None:
    """Why the step stops when the test file `form` does not have the form that its task names,
    else None (#3451). The step collects the test file outside the shell of the agent, so a loop
    test and a parametrized test give different counts. A collection that runs out of time is a
    `timeout`. Every other stop is a `test`, and the named test file is the one path that its repair
    round may change."""
    argv = [BIN_UV, "run", BIN_PYTEST, "--collect-only", "-q", "--", form.path]
    limit = load_settings().roadmap.implement.command_timeout_seconds
    try:
        done = run_subprocess(argv, cwd=source, quiet=True, timeout=limit)
    except subprocess.TimeoutExpired:
        if trace is not None:
            trace.check(_form_check(form, None), None)
        return _Failure(
            MESSAGES.roadmap.implement_stop_command_timeout.format(
                command=shlex.join(argv), seconds=limit
            ),
            klass=FailureClass.TIMEOUT,
        )
    collected = collected_items(done.stdout)
    if trace is not None:
        trace.check(_form_check(form, collected), done.returncode)
    if done.returncode != 0:
        return _Failure(
            MESSAGES.roadmap.implement_stop_command_failed.format(
                command=shlex.join(argv), status=done.returncode, output=_tail(done)
            ),
            frozenset({form.path}),
            klass=FailureClass.TEST,
        )
    if not _form_differs(form, collected):
        return None
    return _Failure(
        MESSAGES.roadmap.implement_stop_test_form.format(
            path=form.path, named=_named_text(form.count), collected=_items_text(collected)
        ),
        frozenset({form.path}),
        klass=FailureClass.TEST,
    )


def _test_form_failure(
    source: Path, inputs: StepInputs, trace: ImplementTrace | None
) -> _Failure | None:
    """Why the step stops when a test does not have the form that its task names, else None
    (#3451). A fix step runs no form check: its group is generated from the failed check and names
    no test form of a task. A group whose tasks name no parametrized test gives no form either.
    Each named test file is collected once."""
    if inputs.fix is not None:
        return None
    forms: dict[str, TestForm] = {}
    for task in inputs.group.tasks:
        for form in named_forms(task.text, task.paths):
            forms.setdefault(form.path, form)
    for form in forms.values():
        failure = _form_failure(source, form, trace)
        if failure is not None:
            return failure
    return None


def _fail_to_pass_failure(
    source: Path,
    inputs: StepInputs,
    keeper: WipKeeper,
    log: ToolCallLog,
) -> _Failure | None:
    """Why the step stops when the tests of a behavior group do not fail on the base commit of the
    group, else None (#3042). The step replays the test files that it changed on that commit, and
    keeps the result for the trace and the PR comment. A behavior group that changed no test file
    stops with no repair round. A replay that passes, or that stops with an error, on base gets one
    repair round that may change only the test files."""
    if not inputs.group.is_behavior:
        return None
    files = _changed_test_files(source, keeper.base)
    if not files:
        return _Failure(MESSAGES.roadmap.implement_stop_no_test_file)
    replay = replay_group_tests(source, keeper.base, files)
    log.fail_to_pass = replay
    if log.trace is not None:
        log.trace.check(
            MESSAGES.roadmap.implement_base_check.format(files=", ".join(files)),
            replay.exit_status,
        )
    return _replay_failure(replay)


def _replay_failure(replay: BaseReplay) -> _Failure | None:
    """Why the step stops for a replay of a behavior group on its base commit, else None."""
    texts = MESSAGES.roadmap
    files = ", ".join(replay.files)
    match replay.status:
        case BaseStatus.FAILS:
            return None
        case BaseStatus.PASSES:
            return _Failure(
                texts.implement_stop_base_passes.format(files=files), frozenset(replay.files)
            )
        case BaseStatus.ERRORS:
            return _Failure(
                texts.implement_stop_base_errors.format(files=files), frozenset(replay.files)
            )
        case BaseStatus.NOT_RUN:
            return _Failure(
                texts.implement_stop_base_not_run.format(
                    files=files, status=replay.exit_status, output=replay.output
                )
            )


def _reset_moved_head(source: Path, expected: str) -> _Failure | None:
    """Put a head that the agent moved back to `expected` with `git reset --soft`: the index and
    the checkout keep the work of the agent (#3575). None when the head was at `expected` or the
    reset worked, else the stop with the class `head_moved`."""
    head = _head(source)
    if head == expected:
        return None
    reset = ("reset", "--soft", expected)
    done = _git(source, *reset)
    if done.returncode != 0:
        return _Failure(
            MESSAGES.roadmap.implement_stop_head_moved.format(
                start=expected,
                head=head,
                command=shlex.join([BIN_GIT, *reset]),
                status=done.returncode,
                output=_tail(done),
            ),
            klass=FailureClass.HEAD_MOVED,
        )
    print_muted(
        MESSAGES.roadmap.implement_head_reset.format(start=expected, head=head), to_stderr=True
    )
    return None


def _outside_plan_failure(source: Path, inputs: StepInputs, base: str) -> _Failure | None:
    """Why a fix step stops when it changed, added or deleted a path that the plan does not name,
    else None (#3824). The fix of a failed check whose cause lies in another path is a decision for
    a person: the step writes no compensating code. The failure has no repair paths, so no extra
    turn follows. A group step is not checked."""
    if inputs.fix is None:
        return None
    names = _git_output(source, "diff", "--cached", "--name-only", "--no-renames", "-z", base)
    groups = parse_task_groups(inputs.tasks_md)
    change = inputs.change.relative_to(source).as_posix()
    outside = unplanned_paths([name for name in names.split("\0") if name], groups, change)
    if not outside:
        return None
    paths = _paths_text([f"`{name}`" for name in outside])
    return _Failure(
        MESSAGES.roadmap.implement_stop_outside_plan.format(paths=paths),
        klass=FailureClass.OUTSIDE_PLAN,
    )


def _plan_failure(
    source: Path, inputs: StepInputs, keeper: WipKeeper
) -> _Failure | None:
    """Why the step stops for the plan of the change, else None. A fix step stops when it changed a
    path that the plan does not name (#3824). Any step stops when a test file lost a test that
    existed at the base commit (#3490)."""
    outside = _outside_plan_failure(source, inputs, keeper.base)
    if outside is not None:
        return outside
    lost = _tests_failure(source, keeper.base, inputs.recorded_tests)
    if lost:
        return _Failure(lost, klass=FailureClass.TESTS_LOST)
    return None


def _exit_failure(
    source: Path, inputs: StepInputs, keeper: WipKeeper, log: ToolCallLog
) -> _Failure | None:
    """The first exit check that fails, or None when every one passes. The step makes the only
    commit, besides the `wip:` commits of its keeper (#3054), so a head that the agent moved is put
    back first with `git reset --soft`, which keeps the work in the checkout, and the checks judge
    that work (#3575). Only a reset that fails stops the step. The `tasks.md` is written
    back next, whatever the run did to it. Once every check passes, `_tick_group` ticks the
    tasks of the group (#3488). The stray files of the agent are deleted before the checkout is
    staged (#3092)."""
    log.fail_to_pass = None
    log.verified.clear()
    moved = _reset_moved_head(source, keeper.expected_head)
    if moved is not None:
        return moved
    keeper.fold()
    _restore_tasks(inputs)
    _remove_strays(source, inputs, log)
    changed = _stage(source)
    if not changed:
        # A group step with no change asks for work that the code does not need: the plan is at
        # fault. A fix step with no change leaves the failed check as it was (#3476).
        no_change = (
            FailureClass.NO_CHANGE_IN_FIX if inputs.fix is not None else FailureClass.PLAN_DEFECT
        )
        return _Failure(MESSAGES.roadmap.implement_stop_no_change, klass=no_change)
    outside = _plan_failure(source, inputs, keeper)
    if outside is not None:
        return outside
    early = _format_failure(source, changed, log.trace) or commands_failure(
        source, inputs.group.verification_commands, log.trace, log.verified
    )
    if early:
        return _Failure(early)
    form = _test_form_failure(source, inputs, log.trace)
    if form is not None:
        return form
    proof = _fail_to_pass_failure(source, inputs, keeper, log)
    if proof is not None:
        return proof
    static = _static_failure(source, changed, log.trace)
    if static:
        return _Failure(static, frozenset(changed))
    failure = _hooks_failure(source, inputs.hooks, changed, log.trace)
    if failure is None:
        refused = _tick_group(source, inputs)
        if refused is not None:
            return _Failure(refused)
    return failure


def _hooks_failure(
    source: Path,
    config: Path | None,
    changed: Sequence[str],
    trace: ImplementTrace | None = None,
) -> _Failure | None:
    """Run the `pre-commit` stage of the hooks of `config` over the staged changes (#3043). None
    when it passes. A failed hook (exit 1) is a failure that the agent may repair in the files the
    step changed. Any other exit code, a run that ran out of time too, is a stop. A repository with
    no hook configuration (`config` is None) has no hook to run."""
    if config is None:
        return None
    run = commit_stage(source, config)
    if trace is not None:
        trace.check(
            f"pre-commit {CONST_PRE_COMMIT_COMMIT_STAGE}", 0 if run is None else run.returncode
        )
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


def _extra_ask(failure: _Failure | None, log: ToolCallLog) -> _Ask | None:
    """The extra turn that a failed static check or hook earns, or None. No turn asks for a tick:
    the job ticks the group when its checks pass (#3488). The message names the stray files that
    the step deleted, and why (#3092). A failure with no repair paths, as a group that changed no
    file (`plan_defect`), gets no turn: no attempt can fix it (#3053). The caller counts the turns
    against `repair_rounds`."""
    if failure is None or failure.repair_paths is None:
        return None
    texts = MESSAGES.roadmap
    removed = texts.implement_removed_note.format(paths=log.removed_text()) if log.removed else ""
    template = texts.implement_hook_turn if failure.hook else texts.implement_repair_turn
    message = template.format(
        failure=mask_secrets(failure.reason)[:CONST_ROADMAP_IMPLEMENT_REASON_CHARS],
        removed=removed,
    )
    return _Ask(message, failure.repair_paths, texts.implement_stop_repair_turn_changed)


def _extra_turn(
    agent: Agent[None, str],
    model: Any,
    log: ToolCallLog,
    source: Path,
    inputs: StepInputs,
    keeper: WipKeeper,
    first: _Run,
    ask: _Ask,
) -> tuple[_Run, _Failure | None]:
    """One extra turn of a step (#2721, #2795, #3043): the same conversation and the same limits as
    the first turn, and the message of `ask`. The turns so far and this one together, and the
    first exit check that fails after it, if any. The turn may change only the files that `ask`
    names and the `tasks.md`. Every exit check runs again after it. The stray files of the turn
    are deleted first, so they are no change that `ask` does not allow (#3092). A turn that a
    limit ended, and a change that `ask` does not allow, give a failure that gets no more turns. The
    keeper commits nothing in the turn."""
    tree = _tree(source)
    # The keeper commits the whole checkout. An extra turn may change only some files, so a tick
    # in it is no ground for a `wip:` commit (#3054).
    before_request, log.before_request = log.before_request, None
    try:
        run = first.then(_turn(agent, model, log, ask.message, first.conversation))
    finally:
        log.before_request = before_request
    if run.reason:
        return run, _Failure(run.reason, klass=run.failure_class)
    _remove_strays(source, inputs, log)
    foreign = _foreign_change(source, inputs, tree, ask)
    if foreign:
        return run, _Failure(foreign)
    return run, _exit_failure(source, inputs, keeper, log)


def _moves_tier(run: _Run) -> bool:
    """Whether another tier may serve the step (#3060). A run that ended on a provider error
    moves down the ladder, as does a failure whose class selects `change_tier`, such as a parser
    failure. A failed check keeps its tier and spends a repair round."""
    if run.provider_error:
        return True
    if not run.reason:
        return False
    return run.failure_class is not None and (
        ACTION_BY_CLASS[run.failure_class] is FailureAction.CHANGE_TIER
    )


def _commit_group(
    source: Path, inputs: StepInputs, item: int, keeper: WipKeeper
) -> tuple[str, str]:
    """The commit of a step whose exit checks passed, with the `wip:` commits of the keeper folded
    into it (#3054). The commit, and why the step stops when git refuses it."""
    keeper.fold()
    return _commit(source, step_commit_title(inputs.item_title, inputs.group.title, item))


@dataclass(frozen=True)
class _Rounds:
    """Where the repair rounds of a step stand (#3053): the last turn, its first failing exit
    check, the rounds used, the number of the attempt that the turn made, and the rounds allowed.
    `spent` says that the step wanted another round and had none."""

    run: _Run
    failure: _Failure | None
    used: int
    number: int
    allowed: int
    spent: bool = False


def _repair_rounds(
    agent: Agent[None, str],
    model: Any,
    log: ToolCallLog,
    source: Path,
    inputs: StepInputs,
    keeper: WipKeeper,
    start: _Rounds,
    *,
    tier: str,
    trace: ImplementTrace | None,
) -> _Rounds:
    """Judge the attempt of `start`, and run an extra turn for its failure while a round is left
    and the failure can be repaired. Each attempt is an event of the trace, with whether a round
    follows (#3053). The state after the last attempt."""
    run, failure, used, number = start.run, start.failure, start.used, start.number
    while True:
        ask = _extra_ask(failure, log)
        repair = ask is not None and used < start.allowed
        _trace_attempt(trace, number, tier, failure, repair=repair)
        if ask is None or not repair:
            return _Rounds(run, failure, used, number, start.allowed, spent=ask is not None)
        if trace is not None:
            trace.retry(failure.reason if failure else "")
        run, failure = _extra_turn(agent, model, log, source, inputs, keeper, run, ask)
        used += 1
        number += 1


def _failure_class(failure: _Failure | None) -> FailureClass | None:
    """The class of the failure of an attempt, or None when the attempt passed (#3053). A failure
    that knows its cause carries the class. Any other failure is classified from its text, as the
    stop would classify it."""
    if failure is None:
        return None
    return failure.klass or classify_failure(FailureEvidence(text=failure.reason))


def _trace_attempt(
    trace: ImplementTrace | None,
    number: int,
    tier: str,
    failure: _Failure | None,
    *,
    repair: bool,
) -> None:
    """Add the attempt `number` to the `trace`: its outcome, its class and its evidence, and
    whether a repair round follows (#3053)."""
    if trace is None:
        return
    klass = _failure_class(failure)
    evidence = failure.reason if failure and klass else ""
    trace.attempt(number, tier, klass.value if klass else "", evidence, repair=repair)


def _attempt(
    source: Path,
    model: Any,
    window: int,
    inputs: StepInputs,
    item: int,
    keeper: WipKeeper,
    log: ToolCallLog,
    *,
    tiers: Sequence[str],
    model_for_tier: Callable[[str], Any] | None,
    tier_health: Callable[[Sequence[str]], Mapping[str, bool]],
    limits: StepBudget,
    trace: ImplementTrace | None = None,
    mcp_toolset: AbstractToolset[Any] | None = None,
) -> StepOutcome:
    """Run the agent one tier at a time, then judge the exit and commit. A failed check or a
    hook gets an extra turn while one of the `roadmap.implement.repair_rounds` rounds is
    left. A failure that carries no repair paths gets none. A step that stops with a failure that
    a round could have taken, and no round left, says so in its reason (#3053). A run that ends on a provider error or
    on a class that selects `change_tier` moves to the next healthy tier at once, spends no repair
    round, and discards the checkout of the failed attempt, back to the last `wip:` commit of the
    keeper (#3060, #3054). Each attempt is an event of the `trace`, and the agent stops before a
    request when `limits` is spent."""
    settings = load_settings()
    budget = settings.roadmap.implement.repair_rounds
    if mcp_toolset is None and settings.roadmap.implement.mcp:
        mcp_toolset = build_roadmap_mcp_toolset(
            ROLE_IMPLEMENTATION,
            local_tool_names=IMPLEMENT_LOCAL_TOOL_NAMES,
            settings=settings,
        )
    rounds = 0
    number = 1
    rounds_spent = False
    tool_calls = 0
    first_request = 0
    total = TierSpend()
    spent: dict[str, TierSpend] = {}
    tried: list[str] = []
    attempt = 0
    with tempfile.TemporaryDirectory(prefix="devops-implement-home-") as home:
        while True:
            tier, attempt = _tier_for_attempt(tiers, attempt, tier_health)
            if tier:
                tried.append(tier)
            tier_model = model_for_tier(tier) if model_for_tier is not None and tier else model
            agent = build_agent(
                tier_model,
                source,
                inputs.instructions,
                window,
                Path(home),
                log,
                limits,
                mcp_toolset=mcp_toolset,
            )
            log.fail_to_pass = None
            log.verified.clear()
            log.parser_failures = 0
            run = _turn(agent, tier_model, log, inputs.message)
            first_request = first_request or run.first_request_tokens
            failure = (
                _Failure(run.reason, klass=run.failure_class)
                if run.reason
                else _exit_failure(source, inputs, keeper, log)
            )
            repaired = _repair_rounds(
                agent,
                tier_model,
                log,
                source,
                inputs,
                keeper,
                _Rounds(run, failure, rounds, number, budget),
                tier=tier,
                trace=trace,
            )
            run, failure, rounds, number = (
                repaired.run,
                repaired.failure,
                repaired.used,
                repaired.number,
            )
            rounds_spent = repaired.spent
            total = total.plus(run)
            tool_calls += run.tool_calls
            if tier:
                spent[tier] = spent.get(tier, TierSpend()).plus(run)
            if failure is None or not _moves_tier(run) or attempt + 1 >= len(tiers):
                break
            keeper.discard()
            attempt += 1
            number += 1
    reason = failure.reason if failure else ""
    klass = failure.klass if failure else None
    outcome = StepOutcome(
        item=item,
        group=inputs.group.number,
        title=inputs.group.title,
        status=StepStatus.STOPPED,
        last_message=run.last_message,
        requests=total.requests,
        tool_calls=tool_calls,
        input_tokens=total.input_tokens,
        output_tokens=total.output_tokens,
        first_request_tokens=first_request,
        removed=tuple(log.removed),
        repair_rounds=rounds,
        tier=tried[-1] if tried else "",
        tiers=tuple(tried),
        tier_spend=spent,
        fail_to_pass=log.fail_to_pass,
    )
    if reason and rounds_spent:
        reason = f"{reason}\n{MESSAGES.roadmap.implement_stop_rounds.format(rounds=budget)}"
    commit = ""
    if not reason:
        commit, reason = _commit_group(source, inputs, item, keeper)
    if reason:
        diff, cut, reason = _read_discarded_diff(source, keeper.tip, reason)
        return outcome.model_copy(
            update={"reason": reason, "diff": diff, "diff_cut": cut, "failure_class": klass}
        )
    return outcome.model_copy(
        update={
            "status": StepStatus.DONE,
            "commit": commit,
            "verified": tuple(log.verified),
        }
    )


def _unkeepable(source: Path, base: str, recorded: frozenset[str]) -> str | None:
    """Why the staged work must not become a `wip:` commit (#3054), else None: it loses a test
    that existed at `base` and that `recorded` does not name, or it holds a symbolic link, which
    the step refuses at its exit."""
    lost = _tests_failure(source, base, recorded)
    if lost:
        return lost
    names = _git_output(source, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    return _link_failure(source, [name for name in names.split("\0") if name])


def _keeper(
    source: Path,
    inputs: StepInputs,
    item: int,
    log: ToolCallLog,
    on_wip: Callable[[WipCommit], None] | None,
    *,
    keep: bool,
) -> WipKeeper:
    """The keeper of the step (#3054). A group step lets it commit, before each model request, the
    tasks that the agent ticked and whose verification passes. A fix step ticks no task, so its
    keeper only holds the head."""
    keeper = WipKeeper(
        source=source,
        tasks_file=inputs.change / "tasks.md",
        group=inputs.group,
        before=inputs.tasks_md,
        item=item,
        git=lambda *args: _git_output(source, *args),
        verify=lambda commands: commands_failure(source, commands, log.trace),
        strays=lambda: _strays(source, inputs),
        moved=lambda: _index_adds(source)[1],
        blocked=lambda: _unkeepable(source, keeper.base, inputs.recorded_tests),
        on_commit=on_wip,
    )
    if inputs.fix is None and keep:
        log.before_request = keeper.check
    return keeper


def run_step(
    store: ItemReader,
    *,
    item: int,
    group: int,
    source: Path,
    window: int,
    model: Any = None,
    fix: FixRequest | None = None,
    hooks: Path | None = None,
    step_class: StepClass = StepClass.EDIT,
    ladder: Sequence[str] | None = None,
    model_for_tier: Callable[[str], Any] | None = None,
    tier_health: Callable[[Sequence[str]], Mapping[str, bool]] | None = None,
    trace: ImplementTrace | None = None,
    on_wip: Callable[[WipCommit], None] | None = None,
    keep: bool = True,
    spend: ItemSpend | None = None,
    recorded_tests: frozenset[str] = frozenset(),
    mcp_toolset: AbstractToolset[Any] | None = None,
    earlier: EarlierStop | None = None,
) -> StepOutcome:
    """Run group `group` of item `item` in the checkout `source`, with the pydantic-ai `model`.

    The step commits the group with the type and the scope of the item, the group title and the
    issue reference (`step_commit_title`) when every exit check passes. Otherwise it resets the
    checkout to its last `wip:` commit, or to the commit it started at when it made none, also
    when the agent made commits or the run raises. A `wip:` commit holds the tasks that the agent
    ticked and whose verification passed, and `on_wip` tells the caller of each one (#3054). A step
    that ends done folds its `wip:` commits into its own commit. With `keep` false, the step
    makes none: the evaluation judges the whole attempt. It reads the item once and
    writes nothing to GitHub. A failed model call ends
    the step as stopped, with the diff of the work. Raises `RoadmapImplementError` for a step it
    refuses to start, and `AICredentialsError` when the model refuses the key. With `fix`, the
    step makes the failed check pass and ticks no task (`run_fix_step`). `hooks` is the trusted
    configuration of the hooks of the project (`trusted_config`): the step runs its `pre-commit`
    stage as an exit check, and none when `hooks` is None (#3043). With a `trace`, the step adds
    its model calls, tool calls, exit checks and retries to it (#3032).

    The step runs the ladder of `step_class` (#3060): `ladder` names the tiers, else the setting
    `roadmap.implement.ladder` does. `model_for_tier` builds the model of one tier; without it,
    every tier runs on `model`. `tier_health` reads the gateway's health of each tier before an
    attempt; without it, the gateway is read when `ai.provider` is `gateway`.

    The step stops before a model request when it has spent a budget of `roadmap.implement`
    (#3053): the input tokens or the seconds of the step, or those of the run of the item. `spend`
    is what the run spent before this step; without it the item has spent nothing.

    `recorded_tests` holds each test, as `path::name`, that the step may lose (#3490). The caller
    reads it from a text that the agent cannot edit. With no value, each lost test stops the step.
    `earlier` holds the stop of the earlier Job, which only the first step of a run gets (#4071).
    """
    inputs = replace(
        build_step_inputs(
            store, item=item, group=group, source=source, window=window, fix=fix, earlier=earlier
        ),
        hooks=hooks,
        recorded_tests=recorded_tests,
    )
    if model is None and model_for_tier is None:
        raise RoadmapImplementError(MESSAGES.roadmap.implement_no_model)
    _require_clean(source)
    log = ToolCallLog(source, trace=trace)
    keeper = _keeper(source, inputs, item, log, on_wip, keep=keep)
    done = False
    try:
        outcome = _attempt(
            source,
            model,
            window,
            inputs,
            item,
            keeper,
            log,
            tiers=_ladder_tiers(step_class, ladder),
            model_for_tier=model_for_tier,
            tier_health=tier_health or _gateway_tier_health,
            limits=StepBudget(spend),
            trace=trace,
            mcp_toolset=mcp_toolset,
        )
        done = outcome.status is StepStatus.DONE
        return outcome
    finally:
        if not done:
            keeper.discard()


def run_fix_step(
    store: ItemReader,
    *,
    item: int,
    fix: FixRequest,
    source: Path,
    window: int,
    model: Any = None,
    hooks: Path | None = None,
    ladder: Sequence[str] | None = None,
    model_for_tier: Callable[[str], Any] | None = None,
    tier_health: Callable[[Sequence[str]], Mapping[str, bool]] | None = None,
    trace: ImplementTrace | None = None,
    spend: ItemSpend | None = None,
    recorded_tests: frozenset[str] = frozenset(),
) -> StepOutcome:
    """Run the fix of the failed check `fix` for item `item` in the checkout `source`: a step
    whose group is "Make check <name> pass". It commits with the type and the scope of the item,
    that title and the issue reference (`step_commit_title`) when the exit checks pass, and
    `tasks.md` is as it was. Its ladder is the `repair` ladder (#3060)."""
    return run_step(
        store,
        item=item,
        group=CONST_ROADMAP_IMPLEMENT_FIX_GROUP,
        source=source,
        window=window,
        model=model,
        fix=fix,
        hooks=hooks,
        step_class=StepClass.REPAIR,
        ladder=ladder,
        model_for_tier=model_for_tier,
        tier_health=tier_health,
        trace=trace,
        spend=spend,
        recorded_tests=recorded_tests,
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
    if outcome.tiers:
        rows[labels["tiers"]] = escape_text(", ".join(outcome.tiers))
    if outcome.removed:
        rows[labels["removed"]] = escape_text(", ".join(outcome.removed))
    title = texts.implement_title.format(
        item=outcome.item, group=outcome.group, title=outcome.title
    )
    print_key_values(title, rows)
