"""The failure taxonomy of the implement job (#3065): which class a failure is in, and the one
action that the class takes by default.

A stop of the implement job holds one reason and the last error. Before this module a person chose
the recovery each time. `classify_failure` is a pure function: it reads the exit status, the error
text, the refusal of a tool, the name of the check and the log of the check, and returns one
`FailureClass`. It reads no file, makes no request and changes no state. It never reads the last
message of the agent, which is a claim that no check verified (#3476). `ACTION_BY_CLASS` is the one
table of defaults: each class has exactly one `FailureAction`.

**Typed classes.** A stop site that knows its cause passes the class itself: `no_change_in_fix`,
`tests_lost`, `head_moved`, `output_cap`, `limit_reached` and `outside_plan` come from the step, and
`git_config` from the check of the git settings of the implement job; no rule below makes them.
The rules are the fallback for a stop whose cause has no class of its own.

**Order of the rules.** The first rule that matches wins, and the order goes from the cause that is
most sure to the one that is least sure:

1. An exit status that a signal gives: 137 is `oom`, and 124 and 143 are `timeout`.
2. A refusal of a tool is `refused_tool`.
3. The text, for the causes outside the code of the item: `oom`, `timeout`, `read_only_path`,
   `conflict`, `parser` (before `provider`, as a provider that cannot parse the call answers with
   an HTTP error too), `provider`, `refused_tool`.
4. The text, then the log of the check, for the checks of the item: `types`, `lint`, `test`.
5. `premise_false` and `plan_defect`, from the text.
6. The name of the check, for a check whose log shows no sign of its class.
7. Anything else is `ci_infra`, whose default action is one retry. A failure that matches no rule
   must not stop the item for good, and the class list is fixed.

**What the job does with a class.** The default action is the action that remains for the item. The
job takes no action by itself yet, except the fix rounds that it has always run
(`roadmap.implement.repair_rounds`): a stop for a class whose default action is `repair`, after
those rounds, has taken `repair`. `left_action` gives the action that remains after that.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Final, NamedTuple

from devops_cli.ai.client.models import AIClientError, StructuredOutputValidationError
from devops_cli.exceptions import (
    DevOpsCLIError,
    GitHubOperationError,
    GitOperationError,
    RoadmapItemChangedError,
    RoadmapStageError,
    ToolExecutionError,
)
from devops_cli.lang import MESSAGES


class FailureClass(StrEnum):
    """The class of a failure. The value is the label of the metric and the word in the comment."""

    PROVIDER = "provider"
    PARSER = "parser"
    TEST = "test"
    LINT = "lint"
    TYPES = "types"
    PLAN_DEFECT = "plan_defect"
    PREMISE_FALSE = "premise_false"
    OOM = "oom"
    TIMEOUT = "timeout"
    REFUSED_TOOL = "refused_tool"
    CONFLICT = "conflict"
    CI_INFRA = "ci_infra"
    NO_CHANGE_IN_FIX = "no_change_in_fix"
    TESTS_LOST = "tests_lost"
    HEAD_MOVED = "head_moved"
    OUTPUT_CAP = "output_cap"
    READ_ONLY_PATH = "read_only_path"
    LIMIT_REACHED = "limit_reached"
    OUTSIDE_PLAN = "outside_plan"
    GIT_CONFIG = "git_config"


class StepName(StrEnum):
    """The step of a job that failed. The stage job records `plan` and `apply` with the class of
    the failure (#4056), refine records `investigate` (the model call that reads the item), and
    intake records `place` (the write of a candidate to the roadmap) (#4061), and consolidate
    records `judge` (the proposal and the refutation of one shortlist) (#3740). `select`, `gate` and
    `review` are labels of the step seconds of the stage job (#4066): a failed gate or review is
    still recorded with the step `plan`. `checks`, `publish` and `watch` are labels of the step
    seconds of the implement job (#4067). A job that records or times a step adds a member here."""

    PLAN = "plan"
    APPLY = "apply"
    INVESTIGATE = "investigate"
    PLACE = "place"
    SELECT = "select"
    GATE = "gate"
    REVIEW = "review"
    CHECKS = "checks"
    PUBLISH = "publish"
    WATCH = "watch"
    JUDGE = "judge"


class FailureAction(StrEnum):
    """What can be done with a failure: retry the run, change the model tier, repair the code with
    a fix step, amend the plan, return the item, raise a limit, or wait for a person."""

    RETRY = "retry"
    CHANGE_TIER = "change_tier"
    REPAIR = "repair"
    AMEND = "amend"
    RETURN = "return"
    RAISE_LIMIT = "raise_limit"
    WAIT = "wait"


# The one table of defaults: one action for each class. A test holds that no class is missing.
ACTION_BY_CLASS: Final[Mapping[FailureClass, FailureAction]] = MappingProxyType(
    {
        FailureClass.PROVIDER: FailureAction.RETRY,
        FailureClass.PARSER: FailureAction.CHANGE_TIER,
        FailureClass.TEST: FailureAction.REPAIR,
        FailureClass.LINT: FailureAction.REPAIR,
        FailureClass.TYPES: FailureAction.REPAIR,
        FailureClass.PLAN_DEFECT: FailureAction.AMEND,
        FailureClass.PREMISE_FALSE: FailureAction.RETURN,
        FailureClass.OOM: FailureAction.RAISE_LIMIT,
        FailureClass.TIMEOUT: FailureAction.RETRY,
        FailureClass.REFUSED_TOOL: FailureAction.WAIT,
        FailureClass.CONFLICT: FailureAction.WAIT,
        FailureClass.CI_INFRA: FailureAction.RETRY,
        FailureClass.NO_CHANGE_IN_FIX: FailureAction.WAIT,
        FailureClass.TESTS_LOST: FailureAction.WAIT,
        FailureClass.HEAD_MOVED: FailureAction.RETRY,
        FailureClass.OUTPUT_CAP: FailureAction.RAISE_LIMIT,
        FailureClass.READ_ONLY_PATH: FailureAction.WAIT,
        FailureClass.LIMIT_REACHED: FailureAction.RAISE_LIMIT,
        FailureClass.OUTSIDE_PLAN: FailureAction.WAIT,
        FailureClass.GIT_CONFIG: FailureAction.WAIT,
    }
)


# The class of an exception, read by `isinstance` from the first entry that matches (#4056). The
# order is the order of the match: a type comes before each parent that it is a subclass of, and
# `DevOpsCLIError` is last, so every error of the project has a class. An item that changed while
# the job worked is `head_moved`: the next round reads it again and no person must act.
CLASS_BY_EXCEPTION: Final[tuple[tuple[type[DevOpsCLIError], FailureClass], ...]] = (
    (RoadmapItemChangedError, FailureClass.HEAD_MOVED),
    (StructuredOutputValidationError, FailureClass.PARSER),
    (AIClientError, FailureClass.PROVIDER),
    (RoadmapStageError, FailureClass.PLAN_DEFECT),
    (GitHubOperationError, FailureClass.CI_INFRA),
    (GitOperationError, FailureClass.CI_INFRA),
    (ToolExecutionError, FailureClass.CI_INFRA),
    (DevOpsCLIError, FailureClass.CI_INFRA),
)


# The wait of a failed stage item before the stage job takes it again, for each class that
# `CLASS_BY_EXCEPTION` gives (#4060). A provider or an infrastructure error is often short, so it
# waits 1 hour. A refused plan waits 1 hour too (#4802): the stage row runs every 37 minutes, so
# the item skips one round, and the return to New after `roadmap.stage.plan_defect_limit`
# refused plans limits its attempts. A parser error waits 6 hours, as one fixed wait did before.
# An item that changed while the job worked waits for no time: the next round reads it again.
RETRY_AFTER: Final[Mapping[FailureClass, timedelta]] = MappingProxyType(
    {
        FailureClass.PROVIDER: timedelta(hours=1),
        FailureClass.PARSER: timedelta(hours=6),
        FailureClass.PLAN_DEFECT: timedelta(hours=1),
        FailureClass.CI_INFRA: timedelta(hours=1),
        FailureClass.HEAD_MOVED: timedelta(0),
    }
)


def retry_after(recorded: str | None) -> timedelta:
    """The wait for the class `recorded`, a value as the stage record holds it. A record with no
    class (written before #4056), or with a value that is no class that has a wait, waits as
    `ci_infra`, so a stale record never stops an item for good and never raises."""
    try:
        return RETRY_AFTER[FailureClass(recorded or "")]
    except KeyError, ValueError:
        return RETRY_AFTER[FailureClass.CI_INFRA]


def failure_class_of(exc: DevOpsCLIError) -> FailureClass:
    """The class of `exc`, from the first entry of `CLASS_BY_EXCEPTION` that it is an instance of.
    Pure: it reads the type, never the text."""
    return next(
        klass for exception_type, klass in CLASS_BY_EXCEPTION if isinstance(exc, exception_type)
    )


class FailureEvidence(NamedTuple):
    """What the classifier reads: the error text, the exit status of the command that failed, the
    text of the refusal of a tool, the name of the check that failed, and the log of that check.
    Each field is empty or None when the failure has none. The last message of the agent is no
    evidence: it is a claim that no check verified (#3476)."""

    text: str = ""
    exit_status: int | None = None
    refusal: str = ""
    check: str = ""
    log: str = ""


# The signals of the kernel and of the Job controller: SIGKILL of a pod that went over its memory
# limit, `timeout(1)`, and SIGTERM of a Job that went over its active deadline.
_EXIT_STATUS: Final[Mapping[int, FailureClass]] = MappingProxyType(
    {137: FailureClass.OOM, 124: FailureClass.TIMEOUT, 143: FailureClass.TIMEOUT}
)

_FLAGS = re.IGNORECASE | re.MULTILINE


def _text_around(template: str, *fields: str) -> str:
    """A pattern for the text of `template`, with `.*` for each of `fields` and the text between
    the fields kept as it is. The rule then follows the message and cannot drift from it."""
    pattern = re.escape(template)
    for name in fields:
        pattern = pattern.replace(re.escape(f"{{{name}}}"), ".*", 1)
    return pattern


# A verification command that the step refuses: its message names the command and then the reason.
# The command can hold the words of any other rule (`timed out`, `rate limit`), and the reason can
# list `mypy` and `ruff`, so this rule is read first, and only at the start of the text (#3263).
_REFUSED_COMMAND: Final[str] = _text_around(
    MESSAGES.roadmap.implement_stop_command_refused, "command", "reason"
)


_REFUSED_AT_START: Final[re.Pattern[str]] = re.compile(rf"\A{_REFUSED_COMMAND}", _FLAGS)


def _rule(klass: FailureClass, pattern: str) -> tuple[FailureClass, re.Pattern[str]]:
    return klass, re.compile(pattern, _FLAGS)


# Rules for the causes outside the code of the item. The parser comes before the provider: an
# Ollama that cannot parse a tool call answers `ModelHTTPError`, an HTTP 400 (#2747).
_CAUSE_RULES: Final[tuple[tuple[FailureClass, re.Pattern[str]], ...]] = (
    _rule(
        FailureClass.OOM,
        r"OOMKilled|out of memory|MemoryError|Cannot allocate memory|memory cgroup|Killed process"
        r"|exited with status 137",
    ),
    _rule(
        FailureClass.TIMEOUT,
        r"ran out of time|timed out|TimeoutExpired|did not finish in \d+|no complete reply in"
        r"|deadline ?exceeded",
    ),
    # A command wrote to a path that the Job mounts read-only (`EROFS`, errno 30). A new attempt
    # or a new image writes to the same path, so only a person can change the cause (#3484).
    _rule(FailureClass.READ_ONLY_PATH, r"Read-only file system|\bEROFS\b"),
    _rule(
        FailureClass.CONFLICT,
        r"merge conflict|CONFLICT \(|rebase onto origin/\S+ stopped|non-fast-forward",
    ),
    _rule(
        FailureClass.PARSER,
        r"Ollama_chatException|unexpected response from Ollama|tool call pars|failed to parse"
        r"|could not parse|JSONDecodeError|invalid (tool call|JSON)|output validation",
    ),
    _rule(
        FailureClass.PROVIDER,
        r"ModelHTTPError|HTTP (429|5\d\d)|rate.?limit|ConnectionError|Connection (refused|reset"
        r"|aborted)|APIConnectionError|ServiceUnavailable|overloaded|Bad Gateway"
        r"|temporarily unavailable|AIClientError|ModelAPIError",
    ),
    # A tool that came back as a retry more often than the bound, or a shell that refused a
    # command (#2735). "Refused commands: 0" is a count of none.
    _rule(
        FailureClass.REFUSED_TOOL,
        r"exceeded max retries|Refused commands: (?!0\b)|refused by (the )?policy",
    ),
)

# Rules for the checks of the item. The log of a check names its tool.
_CHECK_RULES: Final[tuple[tuple[FailureClass, re.Pattern[str]], ...]] = (
    _rule(
        FailureClass.TYPES,
        r"\bmypy\b|\bpyright\b|^\S+:\d+(:\d+)?: error: .*\[[a-z][a-z-]*\]\s*$",
    ),
    _rule(
        FailureClass.LINT,
        r"\bruff\b|\bbandit\b|ast-grep|\bpre-commit\b|would reformat|\bflake8\b|\bactionlint\b"
        r"|\bzizmor\b|hooks of the stage|^\S+:\d+:\d+: [A-Z]+\d+ ",
    ),
    _rule(
        FailureClass.TEST,
        r"\bpytest\b|^FAILED\b|AssertionError|\d+ failed\b|tests? failed|devops ci test",
    ),
)

_PREMISE = re.compile(
    r"premise (is|was) false|premise does not hold|cannot be built as written"
    r"|already (deleted|removed|fixed|implemented)|does not exist in the current codebase",
    _FLAGS,
)
# The plan cannot be run as written: a task of an archived change is not ticked, or the inputs of
# the step do not fit the window. An open finding of the stage keeps the plan in draft for the same
# class (#3264). The stops of a step that changed no file are typed by the
# step (#3476).
_PLAN = re.compile(
    r"has a task that is not ticked"
    r"|inputs of the step measure|not a file on the default branch|open finding|plan/needs-fix",
    _FLAGS,
)

# The name of a check, when its log shows no sign of its class. The infra names come first:
# "Test Job Duration" is not a test.
_CHECK_NAMES: Final[tuple[tuple[FailureClass, re.Pattern[str]], ...]] = (
    _rule(FailureClass.CI_INFRA, r"image|duration|devcontainer|build|setup|install"),
    _rule(FailureClass.TYPES, r"type|mypy"),
    _rule(FailureClass.TEST, r"test|coverage|pytest"),
    _rule(
        FailureClass.LINT,
        r"lint|ruff|format|static|bandit|security|pre-push|pre-commit|actionlint|openspec|docs",
    ),
)


def _first(
    rules: tuple[tuple[FailureClass, re.Pattern[str]], ...], text: str
) -> FailureClass | None:
    return next((klass for klass, pattern in rules if pattern.search(text)), None)


def classify_failure(evidence: FailureEvidence) -> FailureClass:
    """The class of the failure that `evidence` shows. Pure: the same evidence gives the same
    class, and nothing is read or written. A failure that matches no rule is `ci_infra`."""
    by_signal = _EXIT_STATUS.get(evidence.exit_status) if evidence.exit_status else None
    if by_signal is not None:
        return by_signal
    if evidence.refusal.strip() or _REFUSED_AT_START.search(evidence.text):
        return FailureClass.REFUSED_TOOL
    found = (
        _first(_CAUSE_RULES, evidence.text)
        or _first(_CHECK_RULES, evidence.text)
        or _first(_CHECK_RULES, evidence.log)
    )
    if found is not None:
        return found
    if _PREMISE.search(evidence.text):
        return FailureClass.PREMISE_FALSE
    if _PLAN.search(evidence.text):
        return FailureClass.PLAN_DEFECT
    return _first(_CHECK_NAMES, evidence.check) or FailureClass.CI_INFRA


def action_for(klass: FailureClass) -> FailureAction:
    """The default action of `klass`."""
    return ACTION_BY_CLASS[klass]


def left_action(klass: FailureClass, taken: FailureAction | None) -> FailureAction:
    """The action that remains for an item that stopped with a failure of `klass`: the default
    action of the class, or `wait` when the job took that action already and the failure stayed."""
    default = ACTION_BY_CLASS[klass]
    return FailureAction.WAIT if taken is default else default


def failure_lines(
    klass: FailureClass,
    *,
    repair_rounds: int = 0,
    taken: FailureAction | None = None,
    left: FailureAction | None = None,
    tier_changes: int = 0,
) -> str:
    """The three lines of a stop comment: the class, the action taken and the action left. The job
    has taken `change_tier` when it moved the step to another tier before it stopped, `repair` when
    it ran `repair_rounds` fix rounds and no tier move, `amend` when it applied an amendment, and
    no action else."""
    texts = MESSAGES.roadmap
    if taken is None and tier_changes > 0:
        taken = FailureAction.CHANGE_TIER
    if taken is None and repair_rounds > 0:
        taken = FailureAction.REPAIR
    if left is None:
        left = left_action(klass, taken)
    if taken is FailureAction.CHANGE_TIER:
        taken_text = texts.implement_failure_taken_change_tier.format(moves=max(tier_changes, 1))
    elif taken is FailureAction.REPAIR:
        taken_text = texts.implement_failure_taken_repair.format(rounds=repair_rounds)
    elif taken is FailureAction.AMEND:
        taken_text = texts.implement_failure_taken_amend
    elif taken is not None:
        taken_text = f"`{taken.value}`"
    else:
        taken_text = texts.implement_failure_taken_none
    return texts.implement_failure_lines.format(
        failure_class=klass.value,
        taken=taken_text,
        left=texts.implement_failure_action_text[left.value],
    )


__all__ = [
    "ACTION_BY_CLASS",
    "CLASS_BY_EXCEPTION",
    "FailureAction",
    "FailureClass",
    "FailureEvidence",
    "StepName",
    "action_for",
    "classify_failure",
    "failure_class_of",
    "failure_lines",
    "left_action",
]
