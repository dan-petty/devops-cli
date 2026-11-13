"""The change that the stage job writes (#2654): the reply of the model, the files of the OpenSpec
change it renders, and the measure of each task group against the step budget.

The reply is one `StageProposal`. `check_proposal` finds what the rules of `openspec/config.yaml`
ask and a schema cannot say: a Purpose on a new capability, a MODIFIED, RENAMED or REMOVED entry
only on a capability that exists and only for a requirement of its base spec (#5340), a spec delta
only when the change is observable, a requirement text no
longer than the limit of OpenSpec (#4524), a base requirement that still names a command that an added requirement removes (#3287), a path that is a file of the
staged commit or that a group creates (`stage_paths`), and a citation of a line or a symbol that
the staged file does not hold (#3422). `render_change` turns the reply into the files of
`openspec/changes/<issue>-<slug>/`. `measure_groups` counts the
inputs of one implementation step for each group with tiktoken. It counts the files that the tasks
of the group name, each packed as the step packs it (`step_files`), so a group costs what its step
reads.
"""

from __future__ import annotations

import logging
import re
import shlex
import string
import unicodedata
from collections.abc import Callable, Collection, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from functools import reduce
from itertools import pairwise
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Annotated, Any, Final, Self, assert_never

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)
from pydantic.json_schema import SkipJsonSchema

from devops_cli.ai.context_budget import count_tokens
from devops_cli.config.constants import (
    CONST_DOCS_CLASS_RECORD,
    CONST_DOCS_CLASS_TOOL_OWNED,
    CONST_ROADMAP_SCOPE_LABEL_PREFIX,
)
from devops_cli.core.paths import safe_resolve_subpath
from devops_cli.core.test_selection import is_test_module
from devops_cli.docs.inventory import explicit_classes
from devops_cli.exceptions.roadmap import RoadmapStageError
from devops_cli.git.branch_form import is_valid_slug
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.agent_run import TraceFacts
from devops_cli.roadmap.commit_title import commit_scope
from devops_cli.roadmap.pull_form import (
    SUMMARY_MAX_CHARS as SUMMARY_MAX_CHARS,
)
from devops_cli.roadmap.pull_form import (
    build_plan_body,
    is_placeholder,
    summary_length,
)
from devops_cli.roadmap.refine.refine import sanitize_text
from devops_cli.roadmap.runner_tools import NOT_IN_RUNNER
from devops_cli.roadmap.stage.stage_commands import command_citation_problems
from devops_cli.roadmap.stage.stage_constants import constant_problems
from devops_cli.roadmap.stage.stage_criteria import (
    PENDING_PERSON,
    StageCriterion,
    criterion_problems,
)
from devops_cli.roadmap.stage.stage_form import form_problems, search_problems
from devops_cli.roadmap.stage.stage_move import (
    move_prefix_problems,
    move_verify_problems,
)
from devops_cli.roadmap.stage.stage_paths import (
    StagedTree,
    change_folder_paths,
    existing_test_problems,
    own_change_problems,
    path_problems,
    same_name_hint,
)
from devops_cli.roadmap.stage.stage_registry import (
    RegistryCount,
    matches,
    missing_test_paths,
    registry_table,
)
from devops_cli.roadmap.step_files import code_spans, named_files, packed_file, parse_task_groups
from devops_cli.roadmap.step_rules import rules_sections
from devops_cli.roadmap.tools import HOLDER_STAGE_EXTENDED, tool_names

if TYPE_CHECKING:
    from devops_cli.roadmap.stage.stage_overlap import Overlap

logger = logging.getLogger(__name__)

# A plan is documentation, not a fix or a feature: only the types feat, fix, perf, refactor and
# revert add a line to the changelog, so a pull request that only plans an item has this type.
STAGING_TYPE: Final[str] = "docs(openspec)"
# The end that GitHub adds to the subject of a squash commit: ` (#<pull>)` (CONTRIBUTING.md).
_SQUASH_SUFFIX: Final[re.Pattern[str]] = re.compile(r" \(#[0-9]+\)$")
_ELLIPSIS: Final[str] = "..."
# A character shows nothing to a reader when its category is a space, a control, a format mark
# (such as U+200B or U+FEFF), a surrogate, a private use or an unassigned mark, or when it is one
# of the blank fillers that have a letter or a symbol category.
_INVISIBLE_CATEGORIES: Final[frozenset[str]] = frozenset(
    {"Cc", "Cf", "Cs", "Co", "Cn", "Zs", "Zl", "Zp"}
)
_BLANK_FILLERS: Final[str] = "\u2800\u115f\u1160\u3164\uffa0"
# The most digits that the number of an issue has. The title of a plan is `docs(openspec): plan
# #<number> <summary>` and its summary has at most `SUMMARY_MAX_CHARS` characters (#2714), so the
# room for the model's summary depends on the digits. The schema cannot know the number, so its
# limit is the room for the longest number, and a shorter number leaves room over (#3249).
ISSUE_NUMBER_DIGITS: Final[int] = 6
STAGE_SUMMARY_MAX_CHARS: Final[int] = SUMMARY_MAX_CHARS - summary_length(
    MESSAGES.roadmap.stage_title_lead.format(number=10**ISSUE_NUMBER_DIGITS - 1)
)
# The most characters of the body of a pull request: it is the message of the squash commit.
BODY_MAX_CHARS: Final[int] = 800
# The fewest characters of the Purpose of a new capability, so archive never writes TBD.
PURPOSE_MIN_CHARS: Final[int] = 50
# The most characters of the text of a requirement: `MAX_REQUIREMENT_TEXT_LENGTH` of OpenSpec
# (`core/validation/constants.js`). `openspec validate --strict` refuses a longer text in a spec,
# and `openspec archive` merges each ADDED and MODIFIED requirement into the spec (#4524).
REQUIREMENT_MAX_CHARS: Final[int] = 500
# The tokens of one estimated line of a file that a task group creates. The stage adds them to the
# measure of the group, so a large new file counts before the implement Job reads it (#3265).
CREATED_LINE_TOKENS: Final[int] = 32
# The fewest characters of a text of the plan that stands for a sentence: `why`, `existing_tool`, a
# line of `feasibility`, a decision and a task. `No alternative.` has 15, and `x` or `todo` has
# fewer (#3200).
PLAN_FIELD_MIN_CHARS: Final[int] = 10
# The cost that rule 3 of `AGENTS.md` asks of a plan that builds its own code: a number of tokens,
# with an optional `k`, and a number of minutes, hours, days or weeks, in digits or in words.
_TOKEN_COST: Final[re.Pattern[str]] = re.compile(r"\d+(?:[.,]\d+)*\s*k?\s*tokens?\b", re.IGNORECASE)
_NUMBER_WORDS: Final[str] = "a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
_TIME_COST: Final[re.Pattern[str]] = re.compile(
    rf"(?:\d+(?:[.,]\d+)*\s*|\b(?:{_NUMBER_WORDS})\s+)(?:minutes?|hours?|days?|weeks?)\b",
    re.IGNORECASE,
)
_REQUIREMENT_WORDS: Final[frozenset[str]] = frozenset({"SHALL", "MUST"})
_WORD_PUNCTUATION: Final[str] = ".,;:()"
# GitHub closes the issue that follows one of these words in the body of a pull request.
_CLOSING_KEYWORDS: Final[frozenset[str]] = frozenset(
    {
        "close",
        "closes",
        "closed",
        "fix",
        "fixes",
        "fixed",
        "resolve",
        "resolves",
        "resolved",
    }
)
# A change whose every path starts with one of these has no spec delta: tests, workflows, documents
# and plans are not behavior a consumer observes (#3013, #3212).
_NO_SPEC_PREFIXES: Final[tuple[str, ...]] = (
    "tests/",
    ".github/workflows/",
    "docs/",
    "openspec/",
    "src/devops_cli/ai/knowledge_base/",
)
_NO_SPEC_PREFIXES_TEXT: Final[str] = (
    f"{', '.join(_NO_SPEC_PREFIXES[:-1])} or {_NO_SPEC_PREFIXES[-1]}"
)
_TESTS_DIRECTORY: Final[str] = "tests/"
_SOURCE_DIRECTORY: Final[str] = "src/"
# A group that changes a path under one of these ends its documents task with the step that
# regenerates the documents (#3226).
_REGENERATE_PREFIXES: Final[tuple[str, ...]] = (
    "src/devops_cli/commands/",
    "src/devops_cli/lang/",
)
# A word names a path when it ends in a dot and letters, as a root document such as SECURITY.md
# does (#3226).
_PATH_SUFFIX: Final[re.Pattern[str]] = re.compile(r"\.[A-Za-z]+$")
_DOCUMENT_SUFFIX: Final[str] = ".md"
_CHANGES_DIRECTORY: Final[str] = "openspec/changes"
# Only `openspec archive` writes a living spec, from the spec delta of the change folder, so no
# task group changes or creates a path under this prefix (#3295).
_LIVING_SPEC_DIRECTORY: Final[str] = "openspec/specs/"
# The catalog of the roadmap messages. A task text that names `MESSAGES.roadmap` needs this file
# in `changes`, so the stage check names it when no group lists it (#3405).
_MESSAGES_FILE: Final[str] = "src/devops_cli/lang/en/messages.py"
_MESSAGE_NAME: Final[re.Pattern[str]] = re.compile(r"\bMESSAGES\.roadmap\b")
# A plan cites a file of the staged commit in its evidence fields: `path:line:text`, or
# `path:def name` and `path:class name`, which stay true when the code moves (#3422). The path
# starts at a word boundary, so the host of a URL is no citation, and the cited text of a line
# ends at the backtick that closes its code span.
_CITED_PATH: Final[str] = r"[A-Za-z0-9_][A-Za-z0-9_./-]*\.[A-Za-z0-9_]+"
_LINE_CITATION: Final[re.Pattern[str]] = re.compile(
    rf"(?<![\w./-])(?P<path>{_CITED_PATH}):(?P<line>\d+):(?P<text>[^`]*)"
)
_SYMBOL_CITATION: Final[re.Pattern[str]] = re.compile(
    rf"(?<![\w./-])(?P<path>{_CITED_PATH}):(?P<kind>def|class)\s+(?P<symbol>[A-Za-z_]\w*)"
)
# The fewest characters of the cited text that the check judges: a shorter text matches almost any
# line, so the check refuses it and asks for a longer one.
_CITATION_MIN_CHARS: Final[int] = 3
# The plan check itself. A plan that adds a rule of it writes the text that the new rule judges,
# so the plan gives a group test that builds its own `StageProposal` and asserts that
# `content_problems` returns no problem for it (#3404).
_PLAN_CHECK_FILE: Final[str] = "src/devops_cli/roadmap/stage/stage_change.py"
_SELF_ACCEPTANCE_MARKS: Final[tuple[str, ...]] = (
    "StageProposal",
    "content_problems",
    "no problem",
)
# A task group that changes a planner prompt must list and verify the prompt-rule test (#3347).
PROMPT_PREFIX: Final[str] = "src/devops_cli/ai/tasks/roadmap_stage_"
PROMPT_SUFFIX: Final[str] = ".md"
PROMPT_RULE_TEST: Final[str] = "tests/roadmap/stage/test_roadmap_stage_prompt_rules.py"
_LEGACY_PROMPT_RULE_TEST: Final[str] = "tests/roadmap/test_roadmap_stage_prompt_rules.py"


class SecurityTriggerPaths(tuple[str, ...]):
    """Paths that require a security section when changed (#3247):
    - SECURITY.md: changes project security policies, disclosure, or requirements.
    - pyproject.toml: adds or updates external dependencies.
    - k8s/: modifies Kubernetes manifests, NetworkPolicies, or RBAC.
    """


SECURITY_TRIGGER_PATHS: Final[SecurityTriggerPaths] = SecurityTriggerPaths(
    (
        "SECURITY.md",
        "pyproject.toml",
        "k8s/",
    )
)
SECURITY_TRIGGER_WORDS: Final[tuple[str, ...]] = (
    "sanitizer",
    "credential",
    "keyring",
    "egress",
    "admission policy",
    "networkpolicy",
    "rbac",
    "new host",
    "loosen",
    "loosened",
    "loosening",
)
# A trigger word matches as a word, not inside a longer word, so `egress` does not match
# `regression` (#4254). A letter next to the match ends it; an underscore, a hyphen or a digit
# does not, so `egress_policy` still matches. An optional plural ending covers `credentials`.
_SECURITY_WORD_PATTERNS: Final[tuple[re.Pattern[str], ...]] = tuple(
    re.compile(rf"(?<![a-z]){re.escape(word)}(?:e?s)?(?![a-z])", re.IGNORECASE)
    for word in SECURITY_TRIGGER_WORDS
)
# An entry of `dependencies` that names an issue which must be delivered first: `#<number>: <reason>`
# (#3224). An overlap or a metric sender keeps its own form, so the reader skips it.
_ISSUE_DEPENDENCY: Final[re.Pattern[str]] = re.compile(r"^#(?P<number>[0-9]+):")
_SENTENCE_END: Final[str] = f"{string.whitespace}."
REGENERATE_DOCUMENTS: Final[str] = "uv run devops docs generate"
# The stage prompt and each module that holds a check of `check_proposal` or of the gates it
# calls. A plan that changes one of these paths must measure the stage job (#3331).
STAGE_EVAL_TRIGGER_PATHS: Final[tuple[str, ...]] = (
    "src/devops_cli/ai/tasks/roadmap_stage_change.md",
    "src/devops_cli/roadmap/stage/stage_change.py",
    "src/devops_cli/roadmap/stage/stage_form.py",
    "src/devops_cli/roadmap/stage/stage_paths.py",
    "src/devops_cli/roadmap/stage/stage_criteria.py",
    "src/devops_cli/roadmap/stage/stage_eval_gates.py",
)
# The command that replays the golden set through the gates of the stage job.
STAGE_EVAL_REPLAY: Final[str] = "uv run devops roadmap eval stage --replay"
# The words that show that the replay task states the score before and after the change.
_STAGE_EVAL_SCORE_WORDS: Final[tuple[str, ...]] = ("score", "before", "after")
# The gate files whose changes must quote the defect the gate refuses (#3386).
GATE_DEFECT_PATHS: Final[tuple[str, ...]] = (
    "src/devops_cli/roadmap/stage/stage_eval_gates.py",
    "src/devops_cli/roadmap/stage/stage_change.py",
)
_FAILS_ON_BASE: Final[str] = "fails on the base"
_SKIP_WORD: Final[re.Pattern[str]] = re.compile(r"\bskips?\b", re.IGNORECASE)
_NON_GOAL: Final[str] = "non-goal"
# The texts of a group that a task holds: the title and each part of the work.
_GROUP_TASK_FIELDS: Final[tuple[str, ...]] = (
    "title",
    "test",
    "implementation",
    "documentation",
    "verify",
)

# ── The reply ─────────────────────────────────────────────────────────────────


def _is_plain(path: str) -> bool:
    """Whether `path` can stand in a code span of one line: no backtick, no control character."""
    return "`" not in path and path.isprintable()


def _repository_path(path: str) -> str:
    """A path inside the repository: relative, with no `..`, and fit for a code span."""
    parts = PurePosixPath(path)
    if not path or parts.is_absolute() or ".." in parts.parts or not _is_plain(path):
        raise ValueError(MESSAGES.roadmap.stage_bad_path.format(path=path))
    return path


def _capability_name(name: str) -> str:
    """`name` when it names a capability: a slug, or slugs that a slash joins for a nested
    capability `<area>/<name>` (#4622)."""
    if not all(is_valid_slug(part) for part in name.split("/")):
        raise ValueError(MESSAGES.roadmap.stage_bad_capability.format(capability=name))
    return name


RepositoryPath = Annotated[str, AfterValidator(_repository_path)]
# The estimated number of lines of a file that a task group creates.
LineCount = Annotated[int, Field(ge=1)]


# U+FEFF is white space for the JavaScript `\\s` that `openspec` reads, and it is none for
# Python. Every other character of that class is white space for Python too.
_JS_SPACE: Final[dict[int, str]] = {0xFEFF: " "}


def _one_line(text: str) -> str:
    """The text on one line, so that a text of the reply adds no line, no task, no group, no
    section and no `Verification:` line to a file of the change. Each run of white space, a line
    break of markdown (`\\n`, `\\r`) and one of `str.splitlines` among them, becomes one space."""
    return " ".join(text.translate(_JS_SPACE).split())


def _join_lines(text: str) -> str:
    """The text on one line, with each line break as one space and every other space kept: a
    command may hold two spaces in a quoted word."""
    return " ".join(text.translate(_JS_SPACE).splitlines()).strip()


# What starts a block in markdown, at the start of a line: a heading, a quote, a list marker or a
# box, a rule, a fence, a comment of HTML.
_BLOCK_START: Final[re.Pattern[str]] = re.compile(
    r"#{1,6}(?:\s|$)|>|[-*+](?:\s|$)|\d{1,9}[.)](?:\s|$)|\[[ xX]\]"
    r"|(?:-{3,}|_{3,}|\*{3,}|={3,}|~{3,}|`{3,})|<[A-Za-z/!?]"
)


def _block_free(text: str) -> str:
    """The text, which starts with no block syntax, as a file of the change writes it at the start
    of a line."""
    if _BLOCK_START.match(text):
        raise ValueError(MESSAGES.roadmap.stage_bad_block_start.format(text=text[:40]))
    return text


# A text of a task group: at least one character once the whitespace around it is stripped, and on
# one line in `tasks.md`.
Text = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
    AfterValidator(_one_line),
]
# A command: on one line, with its spaces kept.
Command = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
    AfterValidator(_join_lines),
]
# A text of a file of the change that is not a task: on one line, and at the start of a line only
# when it starts with no block syntax.
Line = Annotated[str, StringConstraints(strip_whitespace=True), AfterValidator(_one_line)]
LineStart = Annotated[
    str,
    StringConstraints(strip_whitespace=True),
    AfterValidator(_one_line),
    AfterValidator(_block_free),
]


def _sentence(text: str) -> str:
    """The text of a task without the full stops at its end, as the writer joins a comma to it.
    A text that holds only stops and spaces has nothing left, and the schema refuses it."""
    kept = text.rstrip(_SENTENCE_END)
    if not kept:
        raise ValueError(MESSAGES.roadmap.stage_blank_text)
    return kept


# The text of a task that the writer joins to the words after it: it ends in no full stop.
Sentence = Annotated[
    str,
    StringConstraints(strip_whitespace=True),
    AfterValidator(_one_line),
    AfterValidator(_sentence),
]


# The steps of a manual check: at least one character, and on one line in `tasks.md`.
Process = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
    AfterValidator(_one_line),
]


class _Reply(BaseModel):
    # A text that is set after validation is folded too, as the writer of the files trusts it.
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class StageScenario(_Reply):
    """One scenario of a requirement, in the shape of an OpenSpec scenario."""

    name: Line
    when: Line
    then: Line


class StageRequirement(_Reply):
    """One requirement of a spec delta; `text` says SHALL or MUST, in capitals."""

    name: Line
    text: LineStart
    scenarios: list[StageScenario] = Field(min_length=1)


class StageRename(_Reply):
    """One rename of a base requirement (#5340). The archive applies a rename before a MODIFIED
    block, so a `modified` entry of the requirement takes `to_name`."""

    from_name: Text
    to_name: Text


class StageRemoval(_Reply):
    """One removal of a base requirement, with the reason and, when another requirement holds the
    rule now, the migration (#5340)."""

    name: Text
    reason: Text
    migration: Text | None = None


class StageSpec(_Reply):
    """The delta of one capability. `purpose` is set for a new capability only."""

    capability: Annotated[str, AfterValidator(_capability_name)]
    purpose: LineStart | None = None
    added: list[StageRequirement] = Field(default_factory=list)
    modified: list[StageRequirement] = Field(default_factory=list)
    renamed: list[StageRename] = Field(default_factory=list)
    removed: list[StageRemoval] = Field(default_factory=list)

    def base_names(self) -> dict[str, str]:
        """The base name of each requirement of the delta, by its name in the delta: the
        `from_name` of each rename by its `to_name`."""
        return {rename.to_name: rename.from_name for rename in self.renamed}


class StageDecision(_Reply):
    """A design decision and its reason."""

    decision: Line
    reason: Line


class StageRejection(_Reply):
    """An alternative the design rejected, and the evidence that rejected it."""

    alternative: Line
    evidence: Line


class StageReference(_Reply):
    """A reference hit for a moved module (#3373)."""

    path: str
    kind: Line = ""
    unchanged: bool = False
    reason: Line | None = None

    @model_validator(mode="after")
    def _unchanged_has_reason(self) -> Self:
        if self.unchanged and not (self.reason and self.reason.strip()):
            raise ValueError(MESSAGES.roadmap.stage_reference_no_reason.format(path=self.path))
        return self


class GroupKind(StrEnum):
    """What a task group does. `behavior` adds or changes what the code does: its work starts with
    a failing test. `manifest` creates or changes a rule file, a dashboard file or a case file: its
    work starts with a failing case, and a command that runs the case proves it. `other` is a
    document, a workflow, a deletion or a refactor that keeps behavior, a test-only edit or data:
    it has no test, and a command or a process proves it (#3005, #3251)."""

    BEHAVIOR = "behavior"
    MANIFEST = "manifest"
    OTHER = "other"


# The kinds whose work starts with a failing case, which the implement step writes first: a test for
# a behavior and a case for a manifest (#3251).
_CASE_FIRST_KINDS: Final[frozenset[GroupKind]] = frozenset({GroupKind.BEHAVIOR, GroupKind.MANIFEST})


class StageGroup(_Reply):
    """One task group of the change: the work of one implementation step. A group changes at
    least one file. `creates` lists the paths of `changes` that the step makes, and `creates_lines`
    gives the estimated number of lines of each of those paths.

    The `kind` sets the tasks. A `behavior` group has a `test` and a `verify` that runs it, and
    changes a path under `src/`. A `manifest` group has a `test` that names its failing case and a
    `verify` that runs the case, and no `process`. An `other` group has no `test`, and one of
    `verify` (a command that gives the same answer on each run) and `process` (the steps of a
    manual check). `documentation` is None when the group changes no document."""

    title: Text
    kind: GroupKind
    reads: list[RepositoryPath] = Field(default_factory=list)
    changes: list[RepositoryPath] = Field(min_length=1)
    creates: list[RepositoryPath] = Field(default_factory=list)
    creates_lines: dict[RepositoryPath, LineCount] = Field(default_factory=dict)
    test: Sentence | None = None
    implementation: Sentence
    documentation: Sentence | None = None
    verify: Command | None = None
    process: Process | None = None

    @model_validator(mode="after")
    def _creates_are_changes(self) -> Self:
        for path in self.creates:
            if path not in self.changes:
                raise ValueError(MESSAGES.roadmap.stage_bad_creates.format(path=path))
        return self

    @model_validator(mode="after")
    def _creates_have_line_estimates(self) -> Self:
        for path in self.creates:
            if path not in self.creates_lines:
                raise ValueError(MESSAGES.roadmap.stage_creates_no_estimate.format(path=path))
        for path in self.creates_lines:
            if path not in self.creates:
                raise ValueError(MESSAGES.roadmap.stage_estimate_not_creates.format(path=path))
        return self

    @model_validator(mode="after")
    def _no_living_spec(self) -> Self:
        for path in (*self.changes, *self.creates):
            if path.startswith(_LIVING_SPEC_DIRECTORY):
                raise ValueError(MESSAGES.roadmap.stage_bad_living_spec.format(path=path))
        return self

    @model_validator(mode="after")
    def _kind_rules(self) -> Self:
        match self.kind:
            case GroupKind.BEHAVIOR:
                problems = _behavior_problems(self)
            case GroupKind.MANIFEST:
                problems = _manifest_problems(self)
            case GroupKind.OTHER:
                problems = _other_problems(self)
            case _:
                assert_never(self.kind)
        if problems:
            raise ValueError(" ".join(problems))
        return self

    @model_validator(mode="after")
    def _no_change_folder_writes(self) -> Self:
        problems = _change_folder_problems(self)
        if problems:
            raise ValueError(" ".join(problems))
        return self


def changes_source(changes: Sequence[str]) -> bool:
    """Whether a path of `changes` is under `src/`: a `behavior` group changes such a path (#3035),
    and the plan reader tells a `behavior` group from a `manifest` group by it (#5205)."""
    return any(path.startswith(_SOURCE_DIRECTORY) for path in changes)


def _behavior_problems(group: StageGroup) -> list[str]:
    """What breaks the rules of a `behavior` group: no test, no command for it, a process, or no
    path under `src/`."""
    texts = MESSAGES.roadmap
    found = (
        (group.test is None, texts.stage_kind_no_test),
        (group.verify is None, texts.stage_kind_no_verify),
        (group.process is not None, texts.stage_kind_behavior_process),
        (not changes_source(group.changes), texts.stage_kind_no_source),
    )
    return [text.format(title=group.title) for broken, text in found if broken]


def _manifest_problems(group: StageGroup) -> list[str]:
    """What breaks the rules of a `manifest` group: no case, no command for it, or a process."""
    texts = MESSAGES.roadmap
    found = (
        (group.test is None, texts.stage_kind_manifest_no_test),
        (group.verify is None, texts.stage_kind_manifest_no_verify),
        (group.process is not None, texts.stage_kind_manifest_process),
    )
    return [text.format(title=group.title) for broken, text in found if broken]


def _other_problems(group: StageGroup) -> list[str]:
    """What breaks the rules of an `other` group: a test, or not exactly one of `verify` and
    `process`."""
    texts = MESSAGES.roadmap
    found = (
        (group.test is not None, texts.stage_kind_other_test),
        (group.verify is None and group.process is None, texts.stage_kind_no_check),
        (
            group.verify is not None and group.process is not None,
            texts.stage_kind_two_checks,
        ),
    )
    return [text.format(title=group.title) for broken, text in found if broken]


def _change_folder_problems(group: StageGroup) -> list[str]:
    """The `changes` and `creates` paths of `group` that are the change folder or sit under it.
    A group reads the change it implements, and it writes nothing there: the stage job writes the
    change before the groups run (#3285)."""
    return [
        MESSAGES.roadmap.stage_bad_change_path.format(path=path)
        for path in change_folder_paths([*group.changes, *group.creates])
    ]


class WeakenedCheck(_Reply):
    """One guard check that a plan gives up: the check, what it stopped and the safeguard that takes
    its place. AGENTS.md rule 5 lets only the owner lower a threshold, and a person allows the entry
    when that person merges the plan. `check` names a test as `path::name`."""

    check: Text
    stopped: Text
    safeguard: Text


# The prompt that asks the model for a `StageProposal`.
CHANGE_TASK: Final[str] = "roadmap_stage_change.md"


def summary_problem(summary: str) -> str | None:
    """The problem with the text of a `summary`, or None when it fits the title (#3395).

    The title shows the summary as `safe_title` writes it: on one line, and with a code span for a
    handle or a link. The limit counts that text in the units of the check `Semantic PR title`
    (`summary_length`), so spare whitespace costs nothing, a handle costs its code span and an
    emoji costs two. A summary with no text left, a cut summary and a placeholder summary are
    refused."""
    text = safe_title(summary)
    shown = summary_length(text)
    if not any(_shows_something(char) for char in text):
        return MESSAGES.roadmap.stage_summary_blank
    if is_placeholder(text):
        return MESSAGES.roadmap.stage_problem_text_placeholder.format(
            field="summary", text=text.strip()
        )
    if text.endswith(_ELLIPSIS):
        return MESSAGES.roadmap.stage_summary_cut
    if shown > STAGE_SUMMARY_MAX_CHARS:
        return MESSAGES.roadmap.stage_summary_long.format(
            length=shown, limit=STAGE_SUMMARY_MAX_CHARS
        )
    return None


class StageProposal(_Reply):
    """The model's plan of the change. `summary` is the summary of the pull request title, and
    `pull_request_body` the what and why of its body. The scope and the type of the title are not
    the model's: see `staging_title`.

    The reply has no key to report a false premise: an issue that cannot be built as written is
    said in `feasibility` (#3478). Each key of the plan is required."""

    # The limit counts the text as the title shows it (see `_summary_fits_the_title`), so the schema
    # gives it as `maxLength` for the model and checks it in the validator, not with `max_length`.
    summary: str = Field(min_length=1, json_schema_extra={"maxLength": STAGE_SUMMARY_MAX_CHARS})
    pull_request_body: str = Field(min_length=1, max_length=BODY_MAX_CHARS)
    why: LineStart
    what_changes: list[Line] = Field(min_length=1)
    skip_specs: bool
    feasibility: list[Line] = Field(min_length=1)
    existing_tool: LineStart
    # Whether the plan builds its own code and adopts no tool: it then writes its cost (#3200).
    builds_own: bool = False
    decisions: list[StageDecision] = Field(default_factory=list)
    rejected: list[StageRejection] = Field(default_factory=list)
    specs: list[StageSpec] = Field(default_factory=list)
    groups: list[StageGroup] = Field(min_length=1)
    criteria: list[StageCriterion] = Field(default_factory=list)
    dependencies: list[Line] = Field(default_factory=list)
    references: list[StageReference] = Field(default_factory=list)
    security: Line = ""
    # The plan reader fills this list from `## Weakened checks` of `proposal.md` (#3490). The reply
    # schema does not show it: `render_change` writes no such section, so a key in a reply is lost.
    weakened_checks: SkipJsonSchema[list[WeakenedCheck]] = Field(default_factory=list)

    @field_validator("summary")
    @classmethod
    def _summary_fits_the_title(cls, summary: str) -> str:
        """The title shows the summary as `safe_title` writes it: on one line, and with a code span
        for a handle or a link. The limit counts that text in the units of the check `Semantic PR
        title` (`summary_length`), so spare whitespace costs nothing, a handle costs its code span
        and an emoji costs two. A summary with no text left, a cut summary and a placeholder
        summary are refused too. The reply that breaks it goes back to the model with the problem,
        and `staging_title` cuts no summary that the schema accepts."""
        problem = summary_problem(summary)
        if problem is not None:
            raise ValueError(problem)
        return summary


class StageSplit(_Reply):
    """The model's answer to a split: every group of the change, in order, and the `criteria`
    list again, since a split moves the numbers of the groups."""

    groups: list[StageGroup] = Field(min_length=1)
    criteria: list[StageCriterion] = Field(default_factory=list)


def _says_shall_or_must(text: str) -> bool:
    words = {word.strip(_WORD_PUNCTUATION) for word in text.split()}
    return not words.isdisjoint(_REQUIREMENT_WORDS)


def _spec_problems(spec: StageSpec, known: Collection[str]) -> list[str]:
    texts = MESSAGES.roadmap
    problems: list[str] = []
    exists = spec.capability in known
    if not exists and (spec.purpose is None or len(spec.purpose) < PURPOSE_MIN_CHARS):
        problems.append(
            texts.stage_problem_purpose.format(capability=spec.capability, count=PURPOSE_MIN_CHARS)
        )
    if not exists and (spec.modified or spec.renamed or spec.removed):
        problems.append(texts.stage_problem_modified.format(capability=spec.capability))
    problems.extend(
        texts.stage_problem_keyword.format(requirement=requirement.name)
        for requirement in (*spec.added, *spec.modified)
        if not _says_shall_or_must(requirement.text)
    )
    return problems


def _is_no_spec_path(path: str) -> bool:
    """Whether `path` needs no spec delta: a prefix in `_NO_SPEC_PREFIXES` or a document at the
    root outside `src/` (#3013, #3212)."""
    return path.startswith(_NO_SPEC_PREFIXES) or (
        path.endswith(_DOCUMENT_SUFFIX) and not path.startswith(_SOURCE_DIRECTORY)
    )


def _needs_no_spec(proposal: StageProposal) -> bool:
    """Whether every path of `changes`, in every group, is a test, a workflow, a document or a
    plan: a change that no consumer observes (#3013, #3212)."""
    return all(_is_no_spec_path(path) for group in proposal.groups for path in group.changes)


def _duplicate_problems(spec: StageSpec, requirements: Mapping[str, Collection[str]]) -> list[str]:
    """One problem for each ADDED requirement of `spec` whose name the base spec of the capability
    already has."""
    taken = {name.strip() for name in requirements.get(spec.capability, ())}
    return [
        MESSAGES.roadmap.stage_problem_duplicate_requirement.format(
            requirement=requirement.name.strip(), capability=spec.capability
        )
        for requirement in spec.added
        if requirement.name.strip() in taken
    ]


def _base_name_problems(spec: StageSpec, requirements: Mapping[str, Collection[str]]) -> list[str]:
    """One problem for each `from_name` and each removed `name` of `spec` that the base spec of
    the capability does not have, and for each `to_name` that it has (#5340). `openspec validate
    --strict` passes these names: it gives only the first rename that `openspec archive` refuses,
    as an INFO line, and no line for such a removal, which the archive skips with a warning. A
    caller that gives no names for the capability skips the check."""
    if spec.capability not in requirements:
        return []
    texts = MESSAGES.roadmap
    base = {name.strip() for name in requirements[spec.capability]}
    names = {"capability": spec.capability}
    return [
        *(
            texts.stage_problem_rename_unknown.format(requirement=rename.from_name, **names)
            for rename in spec.renamed
            if rename.from_name not in base
        ),
        *(
            texts.stage_problem_rename_taken.format(requirement=rename.to_name, **names)
            for rename in spec.renamed
            if rename.to_name in base
        ),
        *(
            texts.stage_problem_remove_unknown.format(requirement=removal.name, **names)
            for removal in spec.removed
            if removal.name not in base
        ),
    ]


def _js_length(text: str) -> int:
    """The length of `text` as OpenSpec measures it: a JavaScript string counts UTF-16 code units,
    so a character outside the Basic Multilingual Plane counts two."""
    return len(text.encode("utf-16-le")) // 2


def _length_problems(spec: StageSpec) -> list[str]:
    """One problem for each ADDED and MODIFIED requirement of `spec` whose text has more than
    `REQUIREMENT_MAX_CHARS` characters. The validation of a change passes such a text, and the
    strict validation of the spec refuses it after `openspec archive` (#4524)."""
    return [
        MESSAGES.roadmap.stage_problem_requirement_long.format(
            requirement=requirement.name.strip(), length=length, limit=REQUIREMENT_MAX_CHARS
        )
        for requirement in (*spec.added, *spec.modified)
        if (length := _js_length(requirement.text.strip())) > REQUIREMENT_MAX_CHARS
    ]


# An added requirement removes a command or an option when MUST NOT or SHALL NOT governs its name, a
# code span that starts with `devops ` or with `--` (#3287). The name is in the subject of a clause
# whose verb is exist, be available or the passive of a verb that offers a name ("The old `devops
# roadmap intake-eval` command MUST NOT exist", "`devops x` MUST NOT be registered"), or in the
# object of a verb that offers a name ("MUST NOT register the old `devops x` command"). A
# requirement that keeps a command and forbids one act of it ("`devops pr check-readiness` SHALL
# read ... and MUST NOT request the pulls files list") removes nothing (#4954).
_CODE_SPAN: Final[re.Pattern[str]] = re.compile(r"`([^`]+)`")
_REMOVED_NAME_PREFIXES: Final[tuple[str, ...]] = ("devops ", "--")
_REMOVAL_MODAL: Final[str] = r"\b(?:MUST|SHALL)\s+NOT\s+"
_OFFER_VERB: Final[str] = r"(?:register|offer|list|accept|expose|provide|support|have|keep)"
_OFFERED: Final[str] = r"(?:registered|offered|listed|accepted|exposed|provided|supported|kept)"
# The subject is before the verb, or after a colon: "The following commands MUST NOT exist: `a`".
_REMOVED_SUBJECT: Final[re.Pattern[str]] = re.compile(
    rf"{_REMOVAL_MODAL}(?:exist|be\s+(?:available|{_OFFERED}))\b(?P<colon>\s*:)?"
)
# One object can follow a list of verbs: "MUST NOT register or list `devops x`".
_REMOVED_OBJECT: Final[re.Pattern[str]] = re.compile(
    rf"{_REMOVAL_MODAL}{_OFFER_VERB}(?:\s*(?:,|\bor\b|\band\b)\s*{_OFFER_VERB})*\b"
)
# A clause starts at the start of a line, after a sentence mark, or after a parenthesis that does not
# close before the verb. "`devops x` (the old alias) MUST NOT exist" keeps `devops x` in its subject.
_REMOVAL_CLAUSE_MARK: Final[re.Pattern[str]] = re.compile(r"[.;:!?](?=\s)|\(")
# A phrase ends at a sentence mark, a closing parenthesis or the end of a line. A colon starts the
# list of an object, so it ends no object.
_REMOVAL_PHRASE_END: Final[re.Pattern[str]] = re.compile(r"[.;!?](?=\s|\Z)|\)|\n")
_REMOVAL_MODAL_WORD: Final[re.Pattern[str]] = re.compile(r"\b(?:MUST|SHALL|SHOULD|MAY)\b")
_REMOVAL_JOINER: Final[re.Pattern[str]] = re.compile(r",|\b(?:and|or|but)\b")
# A name after one of these words is not the head of its phrase: "The `--old` option of `devops x`"
# and "When `devops x` runs, `--old`" remove `--old` only.
_NOT_HEAD: Final[re.Pattern[str]] = re.compile(
    r"\b(?:of|in|into|for|from|to|by|with|within|without|on|under|over|at|than|as|between"
    r"|among|about|through|via|per|against|that|which|who|whose|when|if|while|unless|until|after"
    r"|before|where|because|since)\b",
    re.IGNORECASE,
)


def _subject_phrase(text: str, verb: int) -> str:
    """The subject of the removal verb at `verb`: the text from the start of its clause. After a
    modal verb of an earlier clause, the subject starts after the first comma, `and`, `or` or `but`,
    as in "The CLI SHALL keep `devops a`, and `devops b` MUST NOT exist"."""
    start = text.rfind("\n", 0, verb) + 1
    for mark in _REMOVAL_CLAUSE_MARK.finditer(text, start, verb):
        if mark[0] != "(" or ")" not in text[mark.end() : verb]:
            start = mark.end()
    phrase = text[start:verb]
    modals = list(_REMOVAL_MODAL_WORD.finditer(phrase))
    if modals:
        joiner = _REMOVAL_JOINER.search(phrase, modals[-1].end())
        phrase = phrase[joiner.end() if joiner else modals[-1].end() :]
    return phrase


def _clause_rest(text: str, start: int) -> str:
    """The object of the removal verb that ends at `start`, or the list of subjects after its colon:
    the text to the end of its clause. A modal verb starts a new clause, whose subject starts at the
    last comma, `and`, `or` or `but` before it, as in "MUST NOT accept `--old`, and `devops x` SHALL
    print an error"."""
    end = _REMOVAL_PHRASE_END.search(text, start)
    phrase = text[start : end.start() if end else len(text)]
    modal = _REMOVAL_MODAL_WORD.search(phrase)
    if modal:
        phrase = phrase[: modal.start()]
        joiners = list(_REMOVAL_JOINER.finditer(phrase))
        phrase = phrase[: joiners[-1].start()] if joiners else phrase
    return phrase


def _head_names(phrase: str) -> Iterator[str]:
    """Each code span of `phrase` that starts with `devops ` or with `--` and that heads the phrase:
    no word such as `of`, `for` or `when` is between the span and the span or the comma before it."""
    previous = 0
    for span in _CODE_SPAN.finditer(phrase):
        lead = phrase[previous : span.start()].rpartition(",")[2]
        previous = span.end()
        name = span[1].strip()
        if name.startswith(_REMOVED_NAME_PREFIXES) and not _NOT_HEAD.search(lead):
            yield name


def _removed_names(text: str) -> tuple[str, ...]:
    """The commands and the options that a requirement removes: each code span that starts with
    `devops ` or with `--` and that MUST NOT or SHALL NOT governs, in the subject of exist, be
    available or the passive of a verb that offers a name, or in the object of a verb that offers a
    name (#3287, #4954)."""
    phrases = [
        (match.start(), _subject_phrase(text, match.start()))
        for match in _REMOVED_SUBJECT.finditer(text)
    ]
    phrases.extend(
        (match.end(), _clause_rest(text, match.end()))
        for match in _REMOVED_SUBJECT.finditer(text)
        if match["colon"]
    )
    phrases.extend(
        (match.end(), _clause_rest(text, match.end())) for match in _REMOVED_OBJECT.finditer(text)
    )
    return tuple(name for _, phrase in sorted(phrases) for name in _head_names(phrase))


def _names(text: str, name: str) -> bool:
    """Whether `text` names `name`. No word character and no hyphen follows the name, so that
    `--old` is no `--older` (#3287)."""
    return re.search(rf"{re.escape(name)}(?![\w-])", text) is not None


def _stale_command_problems(spec: StageSpec, texts: Mapping[str, str]) -> list[str]:
    """One problem for each base requirement of `spec.capability` that names a command or an option
    that an ADDED requirement removes and that no `modified` requirement rewrites and no `removed`
    entry removes, and one for each `modified` requirement whose text keeps the name (#3287). A
    `modified` requirement under the new name of a rename rewrites the base requirement of the old
    name (#5340). `texts` maps the name of each base requirement to its statement, and a caller
    that gives none skips the check."""
    removed = {name for requirement in spec.added for name in _removed_names(requirement.text)}
    if not removed:
        return []
    messages = MESSAGES.roadmap
    base_names = spec.base_names()
    rewritten = {base_names.get(r.name.strip(), r.name.strip()) for r in spec.modified}
    rewritten.update(removal.name for removal in spec.removed)
    problems = [
        messages.stage_problem_stale_command.format(
            requirement=requirement, capability=spec.capability, command=name
        )
        for requirement, statement in texts.items()
        if requirement not in rewritten
        for name in removed
        if _names(statement, name)
    ]
    problems.extend(
        messages.stage_problem_stale_command_text.format(
            requirement=requirement.name.strip(),
            capability=spec.capability,
            command=name,
        )
        for requirement in spec.modified
        for name in removed
        if _names(requirement.text, name)
    )
    return problems


def _delta_problems(
    proposal: StageProposal,
    known: Collection[str],
    requirements: Mapping[str, Collection[str]],
    requirement_texts: Mapping[str, Mapping[str, str]] | None = None,
) -> list[str]:
    """What is wrong with the spec delta of `proposal` as a whole and in each capability.
    `requirement_texts` maps the name of each base requirement to its statement, by capability: a
    caller that gives none skips the check of a base requirement that names a removed command
    (#3287)."""
    texts = MESSAGES.roadmap
    problems: list[str] = []
    if proposal.skip_specs and proposal.specs:
        problems.append(texts.stage_problem_skip_with_specs)
    if not proposal.skip_specs and not proposal.specs:
        problems.append(texts.stage_problem_no_specs)
    if not proposal.skip_specs and proposal.specs and _needs_no_spec(proposal):
        problems.append(
            texts.stage_problem_specs_not_needed.format(prefixes=_NO_SPEC_PREFIXES_TEXT)
        )
    for spec in proposal.specs:
        problems.extend(_spec_problems(spec, known))
        problems.extend(_length_problems(spec))
        problems.extend(_duplicate_problems(spec, requirements))
        problems.extend(_base_name_problems(spec, requirements))
        problems.extend(
            _stale_command_problems(spec, (requirement_texts or {}).get(spec.capability, {}))
        )
    return problems


_SCENARIO_COMMAND_WORDS: Final[frozenset[str]] = frozenset(
    {
        "helm",
        "git",
        "kubectl",
        "uv",
        "devops",
        "tofu",
        "terraform",
        "gh",
        "openspec",
        "pytest",
        "ruff",
        "mypy",
    }
)

_CODE_IDENTIFIER: Final[re.Pattern[str]] = re.compile(
    r"^(?:[A-Za-z_][A-Za-z0-9_]*\.)*[A-Za-z_][A-Za-z0-9_]*$"
)


def _is_scenario_command(span: str) -> bool:
    words = span.split()
    return len(words) > 1 and words[0] in _SCENARIO_COMMAND_WORDS


def _is_code_identifier(span: str) -> bool:
    if span.startswith("devops_cli_") or span.endswith("_") or span.isupper():
        return False
    return bool(_CODE_IDENTIFIER.match(span)) and ("." in span or "_" in span)


def _judged_spans(scenario: StageScenario, tree: StagedTree, touched: Collection[str]) -> list[str]:
    """The code spans of `scenario` that need a behavior test (#4316): the code of the `then`, which
    states the behavior under test, and the code of the `when` that is no path or whose path a
    behavior group changes, creates or reads. A path of the `when` that no group touches is input
    data, such as the file that a fixture holds, and the test builds it with no reason to name it."""
    spans = [
        *(
            span
            for span in code_spans(scenario.when)
            if (path := tree.as_path(span)) is None or path in touched
        ),
        *code_spans(scenario.then),
    ]
    return [span for span in spans if tree.as_path(span) is not None or _is_code_identifier(span)]


def _scenario_problems(
    specs: Sequence[StageSpec],
    groups: Sequence[StageGroup],
    tree: StagedTree,
) -> list[str]:
    """The problems of spec scenarios that name code without a behavior test (#3321)."""
    behavior_groups = [g for g in groups if g.kind == GroupKind.BEHAVIOR]
    behavior_tests = [g.test for g in behavior_groups if g.test]
    behavior_verifies = [g.verify for g in behavior_groups if g.verify]
    touched = {p for g in behavior_groups for p in (*g.reads, *g.changes, *g.creates)}
    problems: list[str] = []

    for spec in specs:
        for req in (*spec.added, *spec.modified):
            for scenario in req.scenarios:
                if any(
                    _is_scenario_command(span)
                    for span in (*code_spans(scenario.when), *code_spans(scenario.then))
                ):
                    continue
                code_spans_in_scenario = _judged_spans(scenario, tree, touched)
                if not code_spans_in_scenario:
                    continue
                satisfied = any(
                    any(code in test for test in behavior_tests)
                    or (
                        tree.as_path(code) is not None
                        and any(code in verify for verify in behavior_verifies)
                    )
                    for code in code_spans_in_scenario
                )
                if not satisfied:
                    problems.append(
                        MESSAGES.roadmap.stage_scenario_untested_code.format(
                            scenario=scenario.name, code=code_spans_in_scenario[0]
                        )
                    )
    return problems


_REFERENCE_HEADER: Final[re.Pattern[str]] = re.compile(
    r"References to\s+['\"].+?['\"]:\s*files\s+\d+,\s*lines\s+\d+", re.IGNORECASE
)
_REFERENCE_FILE_LINE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<path>[\w./-]+):\s*\d+\s*\((?:line|lines)\s+[^)]+\)"
)
_ARCHIVE_PREFIX: Final[str] = "openspec/changes/archive/"


def _extract_reference_paths(texts: Sequence[str]) -> list[str]:
    """The file paths listed in quoted `References to` search blocks."""
    quoted: list[str] = []
    in_block = False
    for text in texts:
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if _REFERENCE_HEADER.search(line):
                in_block = True
                continue
            if not in_block:
                continue
            match = _REFERENCE_FILE_LINE.match(line)
            if match:
                path = match.group("path")
                if not path.startswith(_ARCHIVE_PREFIX):
                    quoted.append(path)
            elif line and not line.startswith("Files left out:"):
                in_block = False
    return quoted


def _reference_problems(proposal: StageProposal) -> list[str]:
    """One problem for each file that a quoted `References to` search lists and no task or
    decision covers (#3321)."""
    texts = (*proposal.feasibility, proposal.why, *proposal.what_changes)
    quoted_paths = _extract_reference_paths(texts)
    if not quoted_paths:
        return []

    covered_paths = {p for g in proposal.groups for p in (*g.changes, *g.creates)}
    decision_texts = [
        f"{d['decision'] if isinstance(d, dict) else d.decision} {d['reason'] if isinstance(d, dict) else d.reason}"
        for d in proposal.decisions
    ] + [
        f"{r['alternative'] if isinstance(r, dict) else r.alternative} {r['evidence'] if isinstance(r, dict) else r.evidence}"
        for r in proposal.rejected
    ]

    problems: list[str] = []
    seen: set[str] = set()
    for path in quoted_paths:
        if path not in seen and path not in covered_paths:
            seen.add(path)
            if not any(path in d_text for d_text in decision_texts):
                problems.append(MESSAGES.roadmap.stage_reference_uncovered_file.format(path=path))

    return problems


def _is_source_module(path: str) -> bool:
    """Whether `path` is a Python module that is no test module and no `conftest.py`."""
    pure = PurePosixPath(path)
    return not (
        pure.suffix != ".py"
        or pure.name.startswith("test_")
        or pure.name == "conftest.py"
        or path.startswith(("tests/", "test/"))
        or "/tests/" in path
    )


def _moves_to(old: PurePosixPath, created: Collection[str]) -> bool:
    """Whether a created module is the old module in another place: a module of the same name, or
    a module in the subpackage that the name prefix of the old module gives (`stage_probe.py` to
    `stage/probe.py`)."""
    subpackage = old.parent / old.stem.split("_", 1)[0]
    return any(
        PurePosixPath(new).stem == old.stem or PurePosixPath(new).is_relative_to(subpackage)
        for new in created
        if _is_source_module(new)
    )


def moved_modules(groups: Sequence[StageGroup]) -> list[tuple[str, str]]:
    """The old path and the dotted name of each Python module that a group moves (#3373).

    A group moves a module when its `changes` holds the old `.py` path and its `creates` holds the
    same module in another place. A group that creates only a test, a document or a new module of
    another name moves nothing. It skips a test module and `conftest.py`."""
    moved: list[tuple[str, str]] = []
    seen: set[str] = set()
    for group in groups:
        for old in group.changes:
            if (
                old in group.creates
                or old in seen
                or not _is_source_module(old)
                or not _moves_to(PurePosixPath(old), group.creates)
            ):
                continue
            seen.add(old)
            dotted = old.removeprefix("src/").removesuffix(".py").replace("/", ".")
            moved.append((old, dotted))
    return moved


# The documents that no task group of a plan edits: a tool writes them, or they are records. The
# inventory of the documents lists them (#1103), so the move check reads the inventory.
_UNEDITED_CLASSES: Final[frozenset[str]] = frozenset(
    {CONST_DOCS_CLASS_TOOL_OWNED, CONST_DOCS_CLASS_RECORD}
)


def _is_unedited(path: str) -> bool:
    """Whether `path` is a document that a tool writes or that is a record."""
    return bool(_UNEDITED_CLASSES.intersection(explicit_classes(path)))


def _move_reference_problems(proposal: StageProposal, references: Sequence[str]) -> list[str]:
    """One problem for each probed reference of a moved module that no group changes and that the
    reply does not mark unchanged (#3373)."""
    if not references:
        return []
    changed = {path for group in proposal.groups for path in group.changes}
    unchanged = {ref.path for ref in proposal.references if ref.unchanged}
    problems: list[str] = []
    seen: set[str] = set()
    for path in references:
        if path not in seen and path not in changed and path not in unchanged:
            seen.add(path)
            if not _is_unedited(path):
                problems.append(
                    MESSAGES.roadmap.stage_problem_reference_uncovered.format(path=path)
                )
    return problems


def _text_problems(field: str, text: str) -> list[str]:
    """The problems of one text of the plan: too short for a sentence, or a placeholder word."""
    texts = MESSAGES.roadmap
    problems: list[str] = []
    length = len(text.strip())
    if length < PLAN_FIELD_MIN_CHARS:
        problems.append(
            texts.stage_problem_text_short.format(
                field=field, length=length, least=PLAN_FIELD_MIN_CHARS
            )
        )
    if is_placeholder(text):
        problems.append(texts.stage_problem_text_placeholder.format(field=field, text=text.strip()))
    return problems


def _scenario_texts(scenario: Any) -> list[str]:
    if isinstance(scenario, dict):
        return [
            scenario.get("name", ""),
            scenario.get("when", ""),
            scenario.get("then", ""),
        ]
    return [
        getattr(scenario, "name", ""),
        getattr(scenario, "when", ""),
        getattr(scenario, "then", ""),
    ]


def _req_texts(req: Any) -> list[str]:
    if isinstance(req, dict):
        texts = [req.get("name", ""), req.get("text", "")]
        for sc in req.get("scenarios", []):
            texts.extend(_scenario_texts(sc))
        return texts
    texts = [getattr(req, "name", ""), getattr(req, "text", "")]
    for sc in getattr(req, "scenarios", []):
        texts.extend(_scenario_texts(sc))
    return texts


def _spec_texts(spec: Any) -> list[str]:
    if isinstance(spec, dict):
        texts = [spec.get("purpose", "")]
        reqs = (*spec.get("added", []), *spec.get("modified", []))
        changes = (*spec.get("renamed", []), *spec.get("removed", []))
    else:
        texts = [getattr(spec, "purpose", "")]
        reqs = (*getattr(spec, "added", ()), *getattr(spec, "modified", ()))
        changes = (*getattr(spec, "renamed", ()), *getattr(spec, "removed", ()))
    for req in reqs:
        texts.extend(_req_texts(req))
    # The names of a rename, and the name, the reason and the migration of a removal (#5340).
    for change in changes:
        values = change.values() if isinstance(change, dict) else change.model_dump().values()
        texts.extend(value for value in values if isinstance(value, str))
    return texts


def _decision_texts(item: Any, first_key: str, second_key: str) -> list[str]:
    if isinstance(item, dict):
        return [item.get(first_key, ""), item.get(second_key, "")]
    return [getattr(item, first_key, ""), getattr(item, second_key, "")]


def plan_texts(proposal: StageProposal) -> list[str]:
    """The plan fields that render to `proposal.md`, `design.md` and the spec deltas (#3308)."""
    texts: list[str] = [
        proposal.why,
        *proposal.what_changes,
        *proposal.feasibility,
        proposal.existing_tool,
        *proposal.dependencies,
    ]
    for d in proposal.decisions:
        texts.extend(_decision_texts(d, "decision", "reason"))
    for r in proposal.rejected:
        texts.extend(_decision_texts(r, "alternative", "evidence"))
    for s in proposal.specs:
        texts.extend(_spec_texts(s))
    return [t for t in texts if t]


def _plan_texts(proposal: StageProposal) -> list[tuple[str, str]]:
    """The texts of the plan that must read as a sentence, each with the name of its field: `why`,
    `existing_tool`, the lines of `feasibility`, the decisions and the tasks of each group."""
    named = [("why", proposal.why), ("existing_tool", proposal.existing_tool)]
    named.extend(("feasibility", line) for line in proposal.feasibility)
    for decision in proposal.decisions:
        named.append(("decision", decision.decision))
        named.append(("decision reason", decision.reason))
    for number, group in enumerate(proposal.groups, start=1):
        tasks = (("test", group.test), ("implementation", group.implementation))
        for name, text in (*tasks, ("documentation", group.documentation)):
            if text is not None:
                named.append((f"{name} of group {number}", text))
    return named


def _squash(text: str) -> str:
    return " ".join(text.split())


def _message_file_problems(proposal: StageProposal) -> list[str]:
    """What is wrong with a plan that names a `MESSAGES.roadmap` entry in a rendered task text and
    changes no file that defines it (#3405)."""
    named = any(
        _MESSAGE_NAME.search(text) for group in proposal.groups for text in _task_texts(group)
    )
    if not named or any(_MESSAGES_FILE in group.changes for group in proposal.groups):
        return []
    return [MESSAGES.roadmap.stage_problem_message_file.format(path=_MESSAGES_FILE)]


def _adds_plan_rule(group: StageGroup) -> bool:
    """Whether `group` adds or changes a rule of the plan check, which judges the plan that
    proposes it (#3404). An `other` group refactors or documents a rule, so it adds none."""
    return group.kind is GroupKind.BEHAVIOR and _PLAN_CHECK_FILE in group.changes


def _self_acceptance_problems(proposal: StageProposal) -> list[str]:
    """One problem for a plan that adds a rule of the plan check and gives no group test that
    builds the plan's own `StageProposal` and asserts that `content_problems` returns no problem
    (#3404). The rule that the plan adds does not exist when the stage job reads the plan, so no
    check can run it on the plan: the plan gives the test itself, and the implement step runs it."""
    if not any(_adds_plan_rule(group) for group in proposal.groups):
        return []
    tests = [group.test for group in proposal.groups if group.test is not None]
    if any(all(mark in test for mark in _SELF_ACCEPTANCE_MARKS) for test in tests):
        return []
    return [MESSAGES.roadmap.stage_problem_self_acceptance.format(path=_PLAN_CHECK_FILE)]


def _prompt_rule_test_cited(paths: Sequence[str]) -> bool:
    """Whether `paths` cites the prompt-rule test or its historical path."""
    return any(
        p in (PROMPT_RULE_TEST, _LEGACY_PROMPT_RULE_TEST)
        or p.endswith("test_roadmap_stage_prompt_rules.py")
        for p in paths
    )


def _prompt_rule_problems(proposal: StageProposal) -> list[str]:
    """What is wrong with a plan that changes a planner prompt and cites no prompt-rule test
    (#3347). A task group that changes a `roadmap_stage_*.md` prompt must list the prompt-rule
    test in `reads` or `changes`, and its `verify` command must name that test."""
    texts = MESSAGES.roadmap
    problems: list[str] = []
    for group in proposal.groups:
        prompts = [
            p for p in group.changes if p.startswith(PROMPT_PREFIX) and p.endswith(PROMPT_SUFFIX)
        ]
        for prompt in prompts:
            has_test = _prompt_rule_test_cited(group.reads) or _prompt_rule_test_cited(
                group.changes
            )
            verifies_test = bool(
                group.verify and ("test_roadmap_stage_prompt_rules.py" in group.verify)
            )
            if not (has_test and verifies_test):
                problems.append(
                    texts.stage_problem_prompt_rule.format(path=prompt, test=PROMPT_RULE_TEST)
                )
    return problems


def _plan_tasks(proposal: StageProposal) -> list[tuple[int, int, str]]:
    """The number of the group, the number of the task in it and the normalized work text of the
    task, for each task of `proposal`, in the order of `tasks.md`."""
    return [
        (group_number, task_number, _squash(work).casefold())
        for group_number, group in enumerate(proposal.groups, start=1)
        for task_number, work in enumerate(_task_work_texts(group), start=1)
    ]


def _duplicate_task_problems(proposal: StageProposal) -> list[str]:
    """One problem for each pair of tasks of `proposal` whose work text is the same, naming both
    task numbers and the group or groups (#3456). A duplicate task can make the step repeat an
    edit, spend the budget of its group on no change, or stop when the second edit writes no
    file."""
    texts = MESSAGES.roadmap
    tasks = _plan_tasks(proposal)
    problems: list[str] = []
    for index, (first_group, first_task, first) in enumerate(tasks):
        for second_group, second_task, second in tasks[index + 1 :]:
            if first != second:
                continue
            groups = (
                texts.stage_group_one.format(first=first_group)
                if first_group == second_group
                else texts.stage_group_two.format(first=first_group, second=second_group)
            )
            problems.append(
                texts.stage_problem_duplicate_task.format(
                    first=f"{first_group}.{first_task}",
                    second=f"{second_group}.{second_task}",
                    groups=groups,
                )
            )
    return problems


def _lists_path(listed: Collection[str], path: str) -> bool:
    """Whether `listed` holds `path`, a path under it or a folder above it: a group that writes a
    folder covers every file under it, and a What Changes item may name the folder of the files
    that a group writes."""
    return any(
        named == path or named.startswith(f"{path}/") or path.startswith(f"{named}/")
        for named in listed
    )


def _what_changes_problems(proposal: StageProposal, tree: StagedTree) -> list[str]:
    """One problem for each repository path in a code span of a What Changes item that no group
    lists in `changes` or `creates` (#3411). The check reads the tree to tell a path from a word,
    so it makes no git call. A path under the living spec folder is left alone: `openspec archive`
    writes it, and no group may write there."""
    listed = {path for group in proposal.groups for path in (*group.changes, *group.creates)}
    return [
        MESSAGES.roadmap.stage_problem_what_changes_path.format(path=path)
        for item in proposal.what_changes
        for path in tree.code_span_paths(item)
        if not _lists_path(listed, path) and not path.startswith(_LIVING_SPEC_DIRECTORY)
    ]


def _evidence_texts(proposal: StageProposal) -> list[tuple[str, str]]:
    """The texts of the plan that hold evidence, each with the name of its field: `why`, the lines
    of `feasibility` and each line of `what_changes` (#3422)."""
    named = [("why", proposal.why)]
    named.extend(("feasibility", line) for line in proposal.feasibility)
    named.extend(("what_changes", line) for line in proposal.what_changes)
    return named


def _cited_text(text: str) -> str:
    """The cited text as the check compares it: without its backticks and its one trailing full
    stop, and with each run of white space as one space, as a line of the file reads."""
    return _squash(text.replace("`", "").strip().removesuffix("."))


def _anchored_line(content: str, number: int, cited: str) -> int | None:
    """The line of `content`, counting from 1, that a citation of line `number` with the text
    `cited` names: line `number` when it holds the text, else the one line that holds it, because a
    line number copied from another commit points at a line that moved (#4479). None when no line
    holds the text, or more than one other line holds it and no line is sure."""
    lines = [_squash(line) for line in content.splitlines()]
    if 1 <= number <= len(lines) and cited in lines[number - 1]:
        return number
    holding = [index for index, line in enumerate(lines, start=1) if cited in line]
    return holding[0] if len(holding) == 1 else None


def _defines(content: str, kind: str, symbol: str) -> bool:
    """Whether `content` defines `symbol` with `kind` at any line, as `def name` or
    `class name` does."""
    pattern = re.compile(rf"\b{re.escape(kind)}\s+{re.escape(symbol)}\b")
    return any(pattern.search(_squash(line)) for line in content.splitlines())


@dataclass(frozen=True)
class _Citation:
    """The verdict on one citation of a plan: its problem, or None when the staged file holds it,
    whether it cites a line, and whether the gate re-anchored it to the one other line that holds
    its text (#4479)."""

    problem: str | None
    of_line: bool = False
    re_anchored: bool = False


def _line_citation(field: str, path: str, line: str, text: str, content: str | None) -> _Citation:
    """The verdict on one `path:line:text` citation: the staged file holds it when the cited line
    holds the text or, for a stale line number, when exactly one other line holds the text."""
    stale = MESSAGES.roadmap.stage_problem_citation_stale.format(field=field, path=path)
    if content is None:
        return _Citation(stale, of_line=True)
    cited = _cited_text(text)
    if len(cited) < _CITATION_MIN_CHARS:
        return _Citation(
            MESSAGES.roadmap.stage_problem_citation_short.format(
                field=field, path=path, least=_CITATION_MIN_CHARS
            ),
            of_line=True,
        )
    anchored = _anchored_line(content, int(line), cited)
    if anchored is None:
        return _Citation(stale, of_line=True)
    return _Citation(None, of_line=True, re_anchored=anchored != int(line))


def _symbol_citation_problem(
    field: str, path: str, kind: str, symbol: str, content: str | None
) -> str | None:
    """The problem of one `path:def name` or `path:class name` citation, or None when the staged
    file defines the symbol at some line."""
    if content is not None and _defines(content, kind, symbol):
        return None
    return MESSAGES.roadmap.stage_problem_citation_stale.format(field=field, path=path)


# The text of a line citation that follows `path:line:` in a code span of its own, after the
# backtick that closes the span of the citation, if there is one.
_FOLLOWING_QUOTE: Final[re.Pattern[str]] = re.compile(r"`?\s*`(?P<quote>[^`]+)`")


def _quoted_text(text: str, match: re.Match[str]) -> str:
    """The text that a line citation quotes: the text after `path:line:` up to the next backtick,
    else the code span that follows it. The prompt asks for the text of the line in a code span, so
    a plan writes `path:line:` and then the text in a span of its own."""
    quoted = match.group("text")
    if _cited_text(quoted):
        return quoted
    following = _FOLLOWING_QUOTE.match(text, match.end())
    return following["quote"] if following else quoted


def _citations(field: str, text: str, read_text: Callable[[str], str | None]) -> list[_Citation]:
    """The verdict on each citation of `text`: the line citations, then the symbol citations."""
    found = [
        _line_citation(
            field,
            match["path"],
            match["line"],
            _quoted_text(text, match),
            read_text(match["path"]),
        )
        for match in _LINE_CITATION.finditer(text)
    ]
    found.extend(
        _Citation(
            _symbol_citation_problem(
                field, match["path"], match["kind"], match["symbol"], read_text(match["path"])
            )
        )
        for match in _SYMBOL_CITATION.finditer(text)
    )
    return found


def _plan_citation_problems(
    proposal: StageProposal, read_text: Callable[[str], str | None] | None
) -> list[str]:
    """One problem for each citation of the evidence fields that the staged file does not hold, a
    citation of the same field and path once. A check with no reader judges no citation: the
    replay of the golden set holds no file text. A check with a reader writes one log line with
    the number of line citations that it re-anchored, so the job log shows the rate (#4479)."""
    if read_text is None:
        return []
    citations = [
        citation
        for field, text in _evidence_texts(proposal)
        for citation in _citations(field, text, read_text)
    ]
    logger.info(
        "The citation gate re-anchored %d of %d line citations.",
        sum(citation.re_anchored for citation in citations),
        sum(citation.of_line for citation in citations),
    )
    return list(
        dict.fromkeys(citation.problem for citation in citations if citation.problem is not None)
    )


def _group_task_texts(group: StageGroup) -> list[str]:
    """The texts of `group` that a task holds: the title and each part of the work."""
    return [text for field in _GROUP_TASK_FIELDS if (text := getattr(group, field)) is not None]


def eval_replay_problems(groups: Sequence[StageGroup]) -> list[str]:
    """One problem when a group changes a path of `STAGE_EVAL_TRIGGER_PATHS` and no group task
    runs the replay with the score before and after the change (#3331). A plan that changes no
    trigger path adds no problem. The check reads the first changed trigger path and the group
    that holds the replay command, so one plan gets one problem."""
    texts = MESSAGES.roadmap
    triggers = [
        (number, path)
        for number, group in enumerate(groups, start=1)
        for path in group.changes
        if path in STAGE_EVAL_TRIGGER_PATHS
    ]
    if not triggers:
        return []
    number, path = triggers[0]
    replays = [
        (number, text)
        for number, group in enumerate(groups, start=1)
        for text in _group_task_texts(group)
        if STAGE_EVAL_REPLAY in text
    ]
    if not replays:
        return [
            texts.stage_problem_eval_replay.format(
                group=number, path=path, command=STAGE_EVAL_REPLAY
            )
        ]
    if any(all(word in text.casefold() for word in _STAGE_EVAL_SCORE_WORDS) for _, text in replays):
        return []
    replay_number = replays[0][0]
    return [
        texts.stage_problem_eval_score.format(
            group=replay_number, path=path, command=STAGE_EVAL_REPLAY
        )
    ]


def _security_search_texts(proposal: StageProposal) -> list[str]:
    """The texts of `proposal` that a security trigger can match (#3247): the plan's Changes,
    group paths and task texts."""
    texts: list[str] = list(proposal.what_changes)
    for group in proposal.groups:
        texts.extend(group.changes)
        texts.extend(group.reads)
        texts.extend(_group_task_texts(group))
        if group.process:
            texts.append(group.process)
    return texts


def _matched_security_trigger(proposal: StageProposal) -> str | None:
    """The first security trigger in list order that `proposal` matches, or None."""
    texts = _security_search_texts(proposal)
    for path in SECURITY_TRIGGER_PATHS:
        path_lower = path.casefold()
        if any(path_lower in t.casefold() for t in texts):
            return path
    for word, pattern in zip(SECURITY_TRIGGER_WORDS, _SECURITY_WORD_PATTERNS, strict=True):
        if any(pattern.search(t) for t in texts):
            return word
    return None


# A test function in a code span: starts with `test_`, with optional parentheses (#3433).
_TEST_FUNCTION: Final[re.Pattern[str]] = re.compile(r"^test_\w*(\(\))?$")


def _is_test_function_span(span: str) -> bool:
    """Whether `span` names a test function: its last segment, after the last `::` when it holds
    one, starts with `test_`, with optional parentheses (#3433)."""
    segment = span.strip().rsplit("::", 1)[-1]
    return bool(_TEST_FUNCTION.match(segment))


def _test_only_group_problems(proposal: StageProposal) -> list[str]:
    """What is wrong with an `other` group that changes only test modules (#3433): its
    implementation must name the test function that it updates in a code span. A group that
    changes a test helper or a fixture is no test-only group (#3462)."""
    problems: list[str] = []
    for group in proposal.groups:
        if (
            group.kind is GroupKind.OTHER
            and group.changes
            and all(p.startswith(_TESTS_DIRECTORY) and is_test_module(p) for p in group.changes)
        ):
            if not any(_is_test_function_span(span) for span in code_spans(group.implementation)):
                problems.append(MESSAGES.roadmap.stage_problem_test_only.format(title=group.title))
    return problems


def _security_problems(proposal: StageProposal) -> list[str]:
    """One problem when `proposal` matches a security trigger and has no security text (#3247)."""
    trigger = _matched_security_trigger(proposal)
    if trigger is not None and not proposal.security.strip():
        return [MESSAGES.roadmap.stage_problem_security.format(trigger=trigger)]
    return []


def _skip_token_modifiers(tokens: list[str]) -> int:
    idx = 0
    while idx < len(tokens) and "=" in tokens[idx] and not tokens[idx].startswith("-"):
        idx += 1
    while idx < len(tokens) and tokens[idx] in {"sudo", "time", "nice", "nohup", "env"}:
        idx += 1
    return idx


def _skip_uv_flags(tokens: list[str], idx: int) -> int:
    while idx < len(tokens) and tokens[idx].startswith("-"):
        if tokens[idx] in {"--with", "--package", "-p", "--python"} and idx + 1 < len(tokens):
            idx += 2
        else:
            idx += 1
    return idx


def _extract_command_programs(cmd_line: str) -> list[str]:
    """Extract program names that are invoked in a command line."""
    programs: list[str] = []
    for part in re.split(r"(?:;|&&|\|\||\|)", cmd_line):
        part = part.strip()
        if not part:
            continue
        try:
            tokens = shlex.split(part)
        except ValueError:
            tokens = part.split()
        if not tokens:
            continue
        idx = _skip_token_modifiers(tokens)
        if idx >= len(tokens):
            continue
        prog = tokens[idx]
        if prog == "uv" and idx + 1 < len(tokens) and tokens[idx + 1] == "run":
            idx = _skip_uv_flags(tokens, idx + 2)
            prog = tokens[idx] if idx < len(tokens) else "uv"
        if prog in {"sh", "bash"} and idx + 2 < len(tokens) and tokens[idx + 1] == "-c":
            programs.extend(_extract_command_programs(tokens[idx + 2]))
            continue
        programs.append(Path(prog).name)
    return programs


def _adds_devops_review_to_job(proposal: StageProposal) -> bool:
    """Whether `proposal` adds `devops review` to the Job (#3258)."""
    texts: list[str] = list(proposal.what_changes)
    texts.append(proposal.why)
    for group in proposal.groups:
        texts.extend(_group_task_texts(group))
    combined = " ".join(texts).casefold()
    if "devops review" not in combined:
        return False
    job_indicators = ("job", "implement", "runner", "cronjob", "ready mark", "mark ready")
    has_job_context = any(ind in combined for ind in job_indicators) or any(
        p.startswith("src/devops_cli/roadmap/implement_") or "cronjob" in p
        for group in proposal.groups
        for p in group.changes
    )
    changes_review_cmd_only = all(
        "commands/review.py" in p or "review/" in p
        for group in proposal.groups
        for p in group.changes
    ) and not any(ind in combined for ind in ("implement", "runner", "cronjob"))
    return has_job_context or not changes_review_cmd_only


def _runner_capability_problems(proposal: StageProposal) -> list[str]:
    """What is wrong with a plan that introduces a command or verify program without stating its
    runner capability in feasibility (#3258)."""
    texts = MESSAGES.roadmap
    problems: list[str] = []
    feasibility_text = " ".join(proposal.feasibility).casefold()

    if _adds_devops_review_to_job(proposal):
        review_caps = ("review tools", "bwrap", "not_in_runner", "runner capability")
        if not any(cap in feasibility_text for cap in review_caps):
            problems.append(
                texts.stage_problem_runner_command.format(
                    command="devops review",
                    capability="review tools",
                )
            )

    seen_programs: set[str] = set()
    for group in proposal.groups:
        if not group.verify:
            continue
        programs = _extract_command_programs(group.verify)
        for prog in programs:
            if prog in NOT_IN_RUNNER and prog not in seen_programs:
                seen_programs.add(prog)
                if (
                    prog.casefold() not in feasibility_text
                    and "not_in_runner" not in feasibility_text
                ):
                    problems.append(
                        texts.stage_problem_runner_verify.format(
                            program=prog,
                            capability=prog,
                        )
                    )
    return problems


def _spec_has_non_goal(spec: StageSpec) -> bool:
    """Whether `spec` mentions non-goal in its purpose, requirements or scenarios (#3386)."""
    if spec.purpose and _NON_GOAL in spec.purpose.casefold():
        return True
    for req in (*spec.added, *spec.modified):
        if _NON_GOAL in req.name.casefold() or _NON_GOAL in req.text.casefold():
            return True
        for sc in req.scenarios:
            if (
                _NON_GOAL in sc.name.casefold()
                or _NON_GOAL in sc.when.casefold()
                or _NON_GOAL in sc.then.casefold()
            ):
                return True
    return False


def _has_non_goal(proposal: StageProposal) -> bool:
    """Whether `proposal` states a non-goal in decisions, rejected alternatives or specs (#3386)."""
    for d in proposal.decisions:
        if _NON_GOAL in d.decision.casefold() or _NON_GOAL in d.reason.casefold():
            return True
    for r in proposal.rejected:
        if _NON_GOAL in r.alternative.casefold() or _NON_GOAL in r.evidence.casefold():
            return True
    return any(_spec_has_non_goal(spec) for spec in proposal.specs)


def _gate_defect_problems(proposal: StageProposal) -> list[str]:
    """What is wrong with a plan that changes a gate file (#3386): feasibility quotes no defective
    text in a code span, no gate test task states that it fails on the base, or a test that skips a
    case states no non-goal."""
    gate_groups = [
        group
        for group in proposal.groups
        if group.kind is GroupKind.BEHAVIOR
        and any(path in GATE_DEFECT_PATHS for path in group.changes)
    ]
    if not gate_groups:
        return []
    gate_path = next(
        path for group in gate_groups for path in group.changes if path in GATE_DEFECT_PATHS
    )
    texts = MESSAGES.roadmap
    problems: list[str] = []
    feasibility_spans = [span for line in proposal.feasibility for span in code_spans(line)]
    if not feasibility_spans:
        problems.append(texts.stage_problem_gate_defect_quote.format(path=gate_path))
    else:
        has_failing_test = any(
            group.test is not None
            and _FAILS_ON_BASE in group.test
            and any(span in group.test for span in feasibility_spans)
            for group in gate_groups
        )
        if not has_failing_test:
            problems.append(texts.stage_problem_gate_defect_test.format(path=gate_path))
    has_skip = any(
        group.test is not None and _SKIP_WORD.search(group.test) for group in gate_groups
    )
    if has_skip and not _has_non_goal(proposal):
        problems.append(texts.stage_problem_gate_non_goal)
    return problems


def content_problems(proposal: StageProposal, probes: Sequence[str] = ()) -> list[str]:
    """What is wrong with the text of `proposal` that no schema says (#3200): a text that is too
    short or a placeholder word (`is_placeholder` of the pull request form), a `feasibility` that
    quotes no line of `probes` when there are some, a task text that names a `MESSAGES.roadmap`
    entry while no group changes the message file (#3405), two tasks that state the same work
    (#3456), a plan that builds its own code and gives no cost of tokens and time in
    `existing_tool`, a plan that adds a rule of the plan check and gives no test that accepts
    its own plan (#3404), a plan that changes a planner prompt and cites no prompt-rule test
    (#3347), a test-only `other` group that names no test function (#3433), a plan that matches
    a security trigger with no security text (#3247), a plan that adds a command to the Job
    or a verify program from NOT_IN_RUNNER with no runner capability in feasibility (#3258),
    and a plan that changes a gate file and quotes no defective text, tests no failure on the
    base, or states no non-goal (#3386). The
    replay (`stage_eval_gates`) and the job both call this through `check_proposal`, so one rule
    set judges both."""
    texts = MESSAGES.roadmap
    problems = [p for field, text in _plan_texts(proposal) for p in _text_problems(field, text)]
    problems.extend(_message_file_problems(proposal))
    problems.extend(_duplicate_task_problems(proposal))
    problems.extend(_self_acceptance_problems(proposal))
    problems.extend(_prompt_rule_problems(proposal))
    problems.extend(_test_only_group_problems(proposal))
    problems.extend(_security_problems(proposal))
    problems.extend(_runner_capability_problems(proposal))
    problems.extend(_gate_defect_problems(proposal))
    lines = [_squash(line) for line in probes if line.strip()]
    if lines:
        feasibility = _squash(" ".join(proposal.feasibility))
        if not any(line in feasibility for line in lines):
            problems.append(texts.stage_problem_no_quote)
    if proposal.builds_own and not (
        _TOKEN_COST.search(proposal.existing_tool) and _TIME_COST.search(proposal.existing_tool)
    ):
        problems.append(texts.stage_problem_no_cost)
    return problems


_NEGATION: Final[re.Pattern[str]] = re.compile(
    r"\b(?:not|never|no|without|neither|nor)\b", re.IGNORECASE
)
# A read word is a form of `read` or `ran`, or the tool `read_file`. A `read` before a hyphen is a
# part of another word, such as `read-only` (#4495).
_READ_WORD: Final[re.Pattern[str]] = re.compile(
    r"\b(?:read|reads|reading|ran|read_file)\b(?!-)", re.IGNORECASE
)
# The subject of a read word is the words after the last mark or word that starts its clause
# (#4495). A relative pronoun, `and` or `or` with no word after it, as in "the code that reads" or
# "it fetches the head and reads", shares the subject of the words before it. A comma does so for a
# verb, as in "this plan cites `x`, reads `y`", but not for `reading`, which is its own subject.
_CLAUSE_START: Final[re.Pattern[str]] = re.compile(
    r"[,;:()]|\b(?:and|or|but|so|because|since|while|whereas|when|once|if|then|after|before|by"
    r"|that|which|who)\b",
    re.IGNORECASE,
)
_SHARED_SUBJECT: Final[frozenset[str]] = frozenset({"that", "which", "who", "and", "or"})
# The words of a subject that name no reader: an article, a determiner, an auxiliary verb or an
# adverb. A subject of these words only names no reader, as a noun read ("the same read") or a
# passive ("`x.py` was read") does, and the read is the run's (#4495).
_NO_READER: Final[frozenset[str]] = frozenset(
    {
        *("a", "an", "the", "this", "these", "those", "each", "every", "same", "one", "its"),
        *("first", "second", "third", "last", "another", "earlier", "previous", "full", "direct"),
        *("is", "are", "was", "were", "be", "been", "being", "has", "have", "had"),
        *("do", "does", "did", "can", "could", "will", "would", "should", "must", "may"),
        *("also", "then", "only", "already", "now", "again", "still", "just", "fully", "directly"),
    }
)
# The words of a subject that name the run or its author: a read with such a subject, or with no
# subject, is a claim of the run (#4495).
_RUN_READERS: Final[frozenset[str]] = frozenset(
    {"i", "we", "me", "us", "my", "our", "run", "runs", "planner", "agent"}
)
# The auxiliary verbs of a passive read, as in "`x.py` was read": the run read the subject.
_PASSIVE: Final[frozenset[str]] = frozenset({"is", "are", "was", "were", "be", "been", "being"})
# The end of the object of a read word: a `;`, or a comma before a word that starts a new clause, as
# in "`read_file` of the prompt shows the rule, and `search_code` returned `x.py`" (#4495).
_OBJECT_END: Final[re.Pattern[str]] = re.compile(
    r";|,\s*(?:and|or|but|so|because|since|while|whereas|then|which|where)\b", re.IGNORECASE
)
# A verb that starts the result of a read, as in "`read_file` on it showed the text `x.py`" or
# "`x.py`, read with `read_file`, shows `y.py`". A path in the result is a part of what the read
# took, not the file that it read (#4495).
_RESULT_VERB: Final[re.Pattern[str]] = re.compile(
    r"\b(?:shows|showed|shown|gives|gave|returns|returned|finds|found|lists|listed|prints|printed"
    r"|says|said|answers|answered|reports|reported|confirms|confirmed|holds|held|contains"
    r"|contained)\b",
    re.IGNORECASE,
)
# The start of a list of verbs: a `;`, `:` or parenthesis, or a word that starts a new clause. A
# comma, `and`, `or` and a preposition such as `after` or `by` are a part of the list, as in "I
# listed `src/`, added `x` after `y`, and read `z.py`", so its subject is before all of them (#4495).
_LIST_START: Final[re.Pattern[str]] = re.compile(
    r"[;:()]|\b(?:but|so|because|since|while|whereas|when|once|if|that|which|who)\b", re.IGNORECASE
)
# The marks with no word between them and a read word that make the read word a verb of a list.
_LIST_MARKS: Final[frozenset[str]] = frozenset({",", "and", "or"})
# The word after a noun read: `of`, as in "a quick read of `x.py`", or a verb of its result, as in
# "the first read shows". A noun read has no subject, so it is a read of the run (#4495).
_NOUN_READ_NEXT: Final[re.Pattern[str]] = re.compile(
    rf"\s+(?:of\b|{_RESULT_VERB.pattern})", re.IGNORECASE
)
# A preposition after a participle `read` that follows a comma or a code span, as in "`x.py`, read
# at the base, shows" or "`x.py` read from GitHub". The participle is a passive of the path before
# it (#4495).
_PARTICIPLE_NEXT: Final[re.Pattern[str]] = re.compile(
    r"\s+(?:at|with|in|on|from|by|through|via|into|over|under|for|during|after|before)\b",
    re.IGNORECASE,
)
# A pronoun at the start of the object of a read, after the closing backtick of `read_file` and one
# preposition: `it`, `them`, or `that`, `this`, `these`, `those` or `the same` before a noun, as in
# "`read_file` on it revealed `x.py`". The read takes the path before it, not the path after the
# pronoun (#4495).
_PRONOUN_OBJECT: Final[re.Pattern[str]] = re.compile(
    r"`?\s*(?:(?:on|of|in|at|from|with)\s+)?"
    r"(?:(?:it|them)\b|(?:that|this|these|those|the\s+same)\s+(?!(?:the|an?)\b)[a-z])",
    re.IGNORECASE,
)
# The present tense of `read` with a code span, `it` or `which` before it says what code does, such
# as "it reads `.github/labels.yml`". It is no claim that the run read the file (#4314).
_CODE_READS: Final[re.Pattern[str]] = re.compile(
    r"(?:`[^`\n]+`|\b(?:it|which))\s*(?:,|\bis\b|\bare\b)?\s*$", re.IGNORECASE
)
_PATH_EXTENSIONS: Final[tuple[str, ...]] = (
    ".py",
    ".md",
    ".yaml",
    ".yml",
    ".json",
    ".txt",
    ".toml",
    ".sh",
    ".rst",
)


# A citation span starts with its path: `path:line:text`, `path:line`, `path:start-end` or
# `path:def name`. The trace gate judges the path, because a run reads the file, not the citation.
_CITATION_PATH: Final[re.Pattern[str]] = re.compile(
    rf"^(?P<path>{_CITED_PATH}):(?:\d+(?:-\d+)?(?::|$)|(?:def|class)\s)"
)


def _is_path_span(span: str) -> bool:
    """Whether `span` looks like a file or directory path in the repository."""
    return "/" in span or any(span.endswith(ext) for ext in _PATH_EXTENSIONS)


# A citation of one line, `path:line` or `path:line:text`, as a search match shows it (#4495).
_CITED_LINE: Final[re.Pattern[str]] = re.compile(rf"^(?P<path>{_CITED_PATH}):(?P<line>\d+)(?::|$)")


# A call of a toolbox tool with a quoted path as its first argument, `read_file("path", 60, 80)`.
_TOOL_CALL: Final[re.Pattern[str]] = re.compile(
    r"""^(?P<tool>\w+)\(\s*(?:"(?P<double>[^"]+)"|'(?P<single>[^']+)')"""
)


def _citation(span: str, stage_tools: Collection[str]) -> str:
    """The citation of a code span: the span without a toolbox tool name before it, as in
    `read_file path`, the first string argument of a toolbox tool call, as in
    `read_file("path", 60, 80)`, and without a leading `./` (#4463)."""
    call = _TOOL_CALL.match(span)
    if call and call["tool"] in stage_tools:
        return (call["double"] or call["single"]).removeprefix("./")
    tool, _, rest = span.partition(" ")
    if tool in stage_tools and rest.strip():
        span = rest.strip()
    return span.removeprefix("./")


def _claimed_path(span: str, stage_tools: Collection[str]) -> str:
    """The path that a code span claims: the path of a `path:line:text`, `path:line`,
    `path:start-end` or `path:def name` citation, else the span. A toolbox tool name before the
    path, as in `read_file path`, a leading `./` and a trailing `/` are no part of it (#4463)."""
    span = _citation(span, stage_tools)
    cited = _CITATION_PATH.match(span)
    return (cited["path"] if cited else span).rstrip("/")


def _same_path(seen: str, claimed: str) -> bool:
    """Whether a path that the run saw is the claimed path: it equals it, or ends with it after a
    `/`, so a claim that names a file or the end of its path is true."""
    return seen == claimed or seen.endswith(f"/{claimed}")


def _was_read(path: str, trace: TraceFacts) -> bool:
    """Whether the run read `path`. A trailing `/` of a directory that the run listed is no part of
    the path (#4463)."""
    return any(_same_path(read.rstrip("/"), path) for read in trace.paths)


def _was_seen(span: str, stage_tools: Collection[str], trace: TraceFacts, *, by_line: bool) -> bool:
    """Whether the run saw what the code span cites: it read the path, or, when `by_line`, the span
    cites one line, `path:line` or `path:line:text`, that a search match of the run showed (#4495).
    A match shows one line, so it supports no claim of the whole file or of a line range."""
    if _was_read(_claimed_path(span, stage_tools), trace):
        return True
    if not by_line:
        return False
    cited = _CITED_LINE.match(_citation(span, stage_tools))
    line = f"{cited['path']}:{cited['line']}" if cited else None
    return line is not None and any(_same_path(match, line) for match in trace.lines)


def _claim_words(sentence: str, stage_tools: set[str]) -> str:
    """The sentence with each code span blanked, except the name of a tool of the toolbox at the
    start of a span, as in `read_file` or `read_file path` (#4495). A word inside a quoted line of
    code is no claim of the plan."""

    def blank(span: re.Match[str]) -> str:
        tool = span.group(1).strip().partition(" ")[0]
        if tool not in stage_tools:
            return " " * len(span.group(0))
        start = span.group(0).index(tool) + len(tool)
        return span.group(0)[:start] + " " * (len(span.group(0)) - start)

    return _CODE_SPAN.sub(blank, sentence)


def _is_code_reading(sentence: str, read: re.Match[str]) -> bool:
    """Whether `read` is `reads` or `reading` with code as its subject: a code span, `it` or
    `which` before it (#4314). The sentence holds the code spans that the claim blanks."""
    return read.group().lower() in ("reads", "reading") and bool(
        _CODE_READS.search(sentence[: read.start()])
    )


def _reader_words(text: str) -> list[str]:
    """The words of `text` that can name a reader: each word that is not in `_NO_READER`."""
    return [w for w in re.findall(r"[a-z0-9_]+", text.lower()) if w not in _NO_READER]


def _subject(claim: str, read: re.Match[str]) -> tuple[int, list[str]]:
    """The start of the clause of `read` in `claim`, and the words of its subject that can name a
    reader. A relative pronoun with no word after it takes the subject of the words before it, as
    in "the code that reads". A comma, `and` or `or` with no word after it makes `read` a verb of a
    list, and the subject is in the words back to the start of the list, as in "I listed `src/`,
    opened the test and read `x.py`" (#4495)."""
    shared = _SHARED_SUBJECT if read.group().lower() == "reading" else {*_SHARED_SUBJECT, ","}
    text = claim[: read.start()]
    while True:
        marks = list(_CLAUSE_START.finditer(text))
        mark = marks[-1] if marks else None
        start = mark.end() if mark else 0
        words = _reader_words(text[start:])
        if words or mark is None or mark.group().lower() not in shared:
            return start, words
        text = text[: mark.start()]
        if mark.group().lower() in _LIST_MARKS:
            starts = list(_LIST_START.finditer(text))
            start = starts[-1].end() if starts else 0
            return start, _reader_words(text[start:])


def _is_passive(claim: str, read: re.Match[str], clause: int) -> bool:
    """Whether `read` is the participle of a passive, as in "`x.py` was read" or "is also read". A
    verb of a list after a passive, as in "`x.py` was copied and read", is a passive too (#4495)."""
    if read.group().lower() != "read":
        return False
    words = re.findall(r"[a-z]+", claim[: read.start()].lower())
    while words and words[-1] in _NO_READER and words[-1] not in _PASSIVE:
        words.pop()
    if words and words[-1] in _LIST_MARKS:
        return not _PASSIVE.isdisjoint(re.findall(r"[a-z]+", claim[clause : read.start()].lower()))
    return bool(words) and words[-1] in _PASSIVE


def _is_participle(sentence: str, read: re.Match[str]) -> bool:
    """Whether `read` is a participle after a comma or a code span, as in "`x.py`, read at the
    base, shows" or "`x.py` read from GitHub": a passive of the path before it (#4495)."""
    return (
        read.group().lower() == "read"
        and sentence[: read.start()].rstrip().endswith((",", "`"))
        and bool(_PARTICIPLE_NEXT.match(sentence, read.end()))
    )


def _is_noun_read(sentence: str, read: re.Match[str]) -> bool:
    """Whether `read` is a noun, as in "a quick read of `x.py`" or "the first read shows" (#4495)."""
    return read.group().lower() in ("read", "reads") and bool(
        _NOUN_READ_NEXT.match(sentence, read.end())
    )


def _object_span(
    claim: str,
    read: re.Match[str],
    spans: Sequence[tuple[int, str]],
    stage_tools: set[str],
    clause: int,
    *,
    passive: bool,
    participle: bool,
) -> tuple[str, bool] | None:
    """The code span of the path that `read` reads, and whether the read names that span itself
    (#4495). The tool name of a span `read_file path` reads that span. A participle reads the last
    path before it, and a passive the first path of its subject. Else the read takes the first
    path of its object, which ends at a verb of its result. A read with no path in its object, or
    with a pronoun before the path, as in "`read_file` on it showed", reads the last path before
    it, and a read with no such path, as in "the same read shows `x.py:3`", reads the first path
    of its result. Those reads do not name the span. None when the sentence cites no such path."""
    ends = _OBJECT_END.search(claim, read.end())
    end = ends.start() if ends else len(claim)
    result = _RESULT_VERB.search(claim, read.end(), end)
    stop = result.start() if result else end
    paths = [
        (pos, span)
        for pos, span in spans
        if span not in stage_tools and _is_path_span(_claimed_path(span, stage_tools))
    ]
    inside = [span for pos, span in paths if pos == read.start() - 1]
    if inside:
        return inside[0], True
    earlier = [span for pos, span in paths if pos < read.start()]
    if participle and earlier:
        return earlier[-1], True
    subject = [span for pos, span in paths if clause <= pos < read.start()]
    if passive and subject:
        return subject[0], True
    obj = [(pos, span) for pos, span in paths if read.end() <= pos < stop]
    if obj and not (earlier and _PRONOUN_OBJECT.match(claim, read.end(), obj[0][0])):
        return obj[0][1], True
    if earlier:
        return earlier[-1], False
    after = [span for pos, span in paths if read.end() <= pos < end]
    return (after[0], False) if after else None


def _is_run_read(
    sentence: str, read: re.Match[str], subject: Sequence[str], *, passive: bool
) -> bool:
    """Whether `read` claims a read of the run: it is the tool `read_file`, a `passive` or a
    participle, a noun, or a read whose `subject` is empty or names the run or its author, such as
    `I` or `the run`. A read whose subject is other words, such as `this plan`, `the group` or `the
    probe`, says what code or the plan does (#4495)."""
    if read.group().lower() == "read_file" or passive or _is_noun_read(sentence, read):
        return True
    return not subject or not _RUN_READERS.isdisjoint(subject)


def _uncalled_path(
    sentence: str, spans: Sequence[tuple[int, str]], stage_tools: set[str], trace: TraceFacts
) -> str | None:
    """The first path that a read claim of the run in `sentence` names and that the run did not
    see, or None. A negated read, a read of code (#4314) and a read whose subject is no reader of
    the run are no claim, and a claim judges only the path of its object (#4495). A search match
    line supports only a read that names that line: not `read_file`, and not a read that takes
    the line through a pronoun or from its result, because those claim the whole file."""
    claim = _claim_words(sentence, stage_tools)
    for read in _READ_WORD.finditer(claim):
        if _NEGATION.search(claim[: read.end()]) or _is_code_reading(sentence, read):
            continue
        clause, subject = _subject(claim, read)
        passive = _is_passive(claim, read, clause)
        participle = _is_participle(sentence, read)
        if not _is_run_read(sentence, read, subject, passive=passive or participle):
            continue
        found = _object_span(
            claim, read, spans, stage_tools, clause, passive=passive, participle=participle
        )
        if found is None:
            continue
        span, named = found
        by_line = named and read.group().lower() != "read_file"
        if not _was_seen(span, stage_tools, trace, by_line=by_line):
            return _claimed_path(span, stage_tools)
    return None


def _uncalled_tool(
    sentence: str, spans: Sequence[tuple[int, str]], stage_tools: set[str], trace: TraceFacts
) -> str | None:
    """The first uncalled tool cited in `sentence`, or None when negated or called."""
    for start_pos, span in spans:
        if span in stage_tools:
            if not _NEGATION.search(sentence[:start_pos]) and span not in trace.tools:
                return span
    return None


def _sentence_trace_problem(sentence: str, stage_tools: set[str], trace: TraceFacts) -> str | None:
    """A trace problem in `sentence`, or None when the sentence makes no uncalled claim."""
    spans = [
        (m.start(), m.group(1).strip()) for m in _CODE_SPAN.finditer(sentence) if m.group(1).strip()
    ]
    if path := _uncalled_path(sentence, spans, stage_tools, trace):
        return MESSAGES.roadmap.stage_problem_trace_path.format(path=path)
    if tool := _uncalled_tool(sentence, spans, stage_tools, trace):
        return MESSAGES.roadmap.stage_problem_trace_tool.format(tool=tool)
    return None


def _sentences(text: str) -> list[str]:
    """The sentences of `text`, with each run of white space as one space."""
    return [s for s in re.split(r"(?<=[.!?])\s+", _squash(text)) if s]


def _trace_problems(
    proposal: StageProposal, trace: TraceFacts | None, probes: Sequence[str] = ()
) -> list[str]:
    """What is wrong with the claims of `proposal.feasibility` compared to `trace` (#3266). A
    sentence of `probes` that the plan quotes is the text of the probe and no claim of the plan,
    so the gate removes it before it reads the claim (#4463)."""
    if trace is None:
        return []
    stage_tools = set(tool_names(HOLDER_STAGE_EXTENDED))
    quoted = [s.rstrip(".!?") for line in probes for s in _sentences(line) if s.rstrip(".!?")]
    problems: list[str] = []
    for line in proposal.feasibility:
        for sentence in _sentences(line):
            claim = reduce(lambda text, probe: text.replace(probe, ""), quoted, sentence)
            if problem := _sentence_trace_problem(claim, stage_tools, trace):
                problems.append(problem)
    return problems


class ProposalGate(StrEnum):
    """The name of each gate of `check_proposal` (#3498). A gate finds one type of problem in a
    plan, and the name tells a person which rule refused a plan. `devops roadmap plan-recheck`
    prints it with each refusal. The replay of `devops roadmap eval stage` runs all of them as its
    one gate `paths`, so these names are finer than its gate names. A new gate adds a member here
    and a line to `check_gates`."""

    SPEC_DELTA = "spec-delta"
    CONTENT = "content"
    CITATION = "citation"
    FORM = "form"
    EVAL_REPLAY = "eval-replay"
    PATHS = "paths"
    WHAT_CHANGES = "what-changes"
    MOVE_PREFIX = "move-prefix"
    MOVE_VERIFY = "move-verify"
    SEARCH = "search"
    CRITERIA = "criteria"
    DEPENDENCIES = "dependencies"
    CREATES = "creates"
    REGISTRY = "registry"
    CONSTANTS = "constants"
    TRACE = "trace"


def _proposal_all_texts(proposal: StageProposal) -> list[str]:
    """All texts of `proposal` that describe plan changes and design (#3344)."""
    texts = plan_texts(proposal)
    for group in proposal.groups:
        texts.extend(
            filter(
                None,
                (group.title, group.test, group.implementation, group.documentation, group.verify),
            )
        )
    return texts


def _attribute_references(text: str) -> Iterator[tuple[str, str]]:
    """Each `Class.attribute` pair found in `text` (#3344)."""
    for match in re.finditer(r"\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)\b", text):
        yield match.group(1), match.group(2)


def _missing_attribute_problem(
    cls_name: str,
    attr_name: str,
    models: Mapping[str, tuple[str, Sequence[str]]],
    all_changes: Collection[str],
) -> str | None:
    """A problem when `cls_name.attr_name` is absent and its file is not in changes (#3344)."""
    entry = models.get(cls_name)
    if entry is None:
        return None
    path, fields = entry
    if attr_name in fields or path in all_changes:
        return None
    ref = f"{cls_name}.{attr_name}"
    return MESSAGES.roadmap.stage_problem_model_attribute.format(reference=ref, path=path)


def model_problems(
    proposal: StageProposal,
    models: Mapping[str, tuple[str, Sequence[str]]] | None,
) -> list[str]:
    """What the plan reads from a model that does not define the field (#3344)."""
    if not models:
        return []
    all_changes = {p for g in proposal.groups for p in g.changes}
    problems: list[str] = []
    seen: set[str] = set()
    for text in _proposal_all_texts(proposal):
        for cls_name, attr_name in _attribute_references(text):
            problem = _missing_attribute_problem(cls_name, attr_name, models, all_changes)
            if problem and problem not in seen:
                seen.add(problem)
                problems.append(problem)
    return problems


def check_gates(
    proposal: StageProposal,
    known: Collection[str],
    tree: StagedTree,
    *,
    change: str = "",
    requirements: Mapping[str, Collection[str]] | None = None,
    requirement_texts: Mapping[str, Mapping[str, str]] | None = None,
    issue_body: str = "",
    probes: Sequence[str] = (),
    overlaps: Sequence[Overlap] = (),
    search_evidence: Mapping[str, Sequence[str]] | None = None,
    plan_creates: Mapping[str, int] | None = None,
    read_text: Callable[[str], str | None] | None = None,
    registry: Sequence[RegistryCount] | None = None,
    constants: Mapping[str, int] | None = None,
    references: Sequence[str] = (),
    models: Mapping[str, tuple[str, Sequence[str]]] | None = None,
    manifest_references: Mapping[str, Sequence[str]] | None = None,
    module_tests: Mapping[str, Sequence[str]] | None = None,
    trace: TraceFacts | None = None,
) -> dict[ProposalGate, list[str]]:
    """What each gate of `check_proposal` finds wrong in `proposal`, one sentence each, under the
    name of the gate. Every gate has a key, and a gate that finds nothing has an empty list. The
    keys follow the order of `ProposalGate`. The arguments are those of `check_proposal`."""
    return {
        ProposalGate.SPEC_DELTA: [
            *_delta_problems(proposal, known, requirements or {}, requirement_texts),
            *_scenario_problems(proposal.specs, proposal.groups, tree),
        ],
        ProposalGate.CONTENT: content_problems(proposal, probes),
        ProposalGate.CITATION: [
            *_plan_citation_problems(proposal, read_text),
            *command_citation_problems(proposal),
        ],
        ProposalGate.FORM: form_problems(proposal.groups),
        ProposalGate.EVAL_REPLAY: eval_replay_problems(proposal.groups),
        ProposalGate.PATHS: [
            *path_problems(proposal.groups, tree, manifest_references, change=change),
            *existing_test_problems(proposal.groups, tree, module_tests or {}),
            *own_change_problems(proposal.groups, change),
            *_reference_problems(proposal),
            *_move_reference_problems(proposal, references),
            *_stale_test_path_problems(proposal, tree),
            *model_problems(proposal, models),
        ],
        ProposalGate.WHAT_CHANGES: _what_changes_problems(proposal, tree),
        ProposalGate.MOVE_PREFIX: move_prefix_problems(proposal.groups, tree),
        ProposalGate.MOVE_VERIFY: move_verify_problems(proposal.groups, tree),
        ProposalGate.SEARCH: search_problems(proposal.groups, search_evidence),
        ProposalGate.CRITERIA: criterion_problems(
            proposal.criteria, issue_body, len(proposal.groups)
        ),
        ProposalGate.DEPENDENCIES: _overlap_problems(proposal.dependencies, overlaps),
        ProposalGate.CREATES: creates_problems(proposal.groups, plan_creates or {}),
        ProposalGate.REGISTRY: registry_problems(
            proposal,
            registry if registry is not None else registry_table(Path.cwd()),
        ),
        ProposalGate.CONSTANTS: constant_problems(plan_texts(proposal), constants or {}),
        ProposalGate.TRACE: _trace_problems(proposal, trace, probes),
    }


def check_proposal(
    proposal: StageProposal,
    known: Collection[str],
    tree: StagedTree,
    *,
    change: str = "",
    requirements: Mapping[str, Collection[str]] | None = None,
    requirement_texts: Mapping[str, Mapping[str, str]] | None = None,
    issue_body: str = "",
    probes: Sequence[str] = (),
    overlaps: Sequence[Overlap] = (),
    search_evidence: Mapping[str, Sequence[str]] | None = None,
    plan_creates: Mapping[str, int] | None = None,
    read_text: Callable[[str], str | None] | None = None,
    registry: Sequence[RegistryCount] | None = None,
    constants: Mapping[str, int] | None = None,
    references: Sequence[str] = (),
    models: Mapping[str, tuple[str, Sequence[str]]] | None = None,
    manifest_references: Mapping[str, Sequence[str]] | None = None,
    module_tests: Mapping[str, Sequence[str]] | None = None,
    trace: TraceFacts | None = None,
) -> list[str]:
    """What the rules of `openspec/config.yaml` and the files of the commit find wrong in
    `proposal`, one sentence each. `known` holds the names of the capabilities under
    `openspec/specs/`, `requirements` the requirement names of each base spec by capability, and
    `tree` the files that exist when the change is written. `requirement_texts` holds the statement
    of each base requirement by capability and requirement name: an added requirement that removes a
    command or an option needs a `modified` requirement for each base requirement that names it, and
    a caller that gives no texts skips that check (#3287). The tree also tells a repository path
    from a word, for the code spans of `what_changes` (#3411). `issue_body` is the whole body of the
    issue: each acceptance criterion in it needs an entry in `criteria` (#3019), and a body with
    none needs no entry. `probes` holds the lines of the premise probe that the model read: when it
    is not empty, `feasibility` quotes one (#3200). `overlaps` lists the open pull requests that
    change a path the item cites: the plan names each in `dependencies` (#3252).
    `search_evidence` maps each negative-search literal to the paths that the staged tree holds:
    the job records it, the replay reads it from its case, and None records no search. `plan_creates`
    maps each path that the plan of an open item creates to that item's number (#3418). `read_text`
    returns the text of a cited file at the staged commit, or None when the commit holds no such
    file: the stage job passes the reader of its checkout and commit, and a check with none judges
    no citation (#3422). `manifest_references` maps each changed YAML manifest of `k8s/` to the
    tests that reference it: the job records it from its checkout, the replay reads it from its
    case, and a caller that gives none judges no test of a manifest (#3972). `module_tests` maps
    each Python module under `src/` that a behavior group changes to the existing tests of that
    module: the job records it from its checkout, the recheck reads it from the tree it holds, and
    a caller that gives none judges no test of a module (#3414). The problems are those of
    `check_gates`, joined in the order of the gates."""
    found = check_gates(
        proposal,
        known,
        tree,
        change=change,
        requirements=requirements,
        requirement_texts=requirement_texts,
        issue_body=issue_body,
        probes=probes,
        overlaps=overlaps,
        search_evidence=search_evidence,
        plan_creates=plan_creates,
        read_text=read_text,
        registry=registry,
        constants=constants,
        references=references,
        models=models,
        manifest_references=manifest_references,
        module_tests=module_tests,
        trace=trace,
    )
    return joined_problems(found)


def joined_problems(found: Mapping[ProposalGate, Sequence[str]]) -> list[str]:
    """The problems of `check_gates` in one list, in the order of the gates."""
    return [problem for problems in found.values() for problem in problems]


def registry_problems(
    proposal: StageProposal,
    registry: Sequence[RegistryCount],
) -> list[str]:
    """One sentence for each declared registry or ratchet place that the plan misses (#3254)."""
    task_texts = [
        text
        for group in proposal.groups
        for text in (group.test, group.implementation, group.documentation)
        if text
    ]
    changed_paths = [path for group in proposal.groups for path in group.changes]
    matched = matches(registry, task_texts, changed_paths)
    problems: list[str] = []
    seen: set[str] = set()
    for entry in matched:
        if not any(entry.path in text for text in task_texts):
            location = f"{entry.declaring_path}:{entry.line}"
            key = f"{entry.path}:{location}"
            if key not in seen:
                seen.add(key)
                problems.append(
                    MESSAGES.roadmap.stage_problem_registry.format(
                        token=entry.token,
                        path=entry.path,
                        location=location,
                    )
                )
    return problems


def _stale_test_path_problems(proposal: StageProposal, tree: StagedTree) -> list[str]:
    """One sentence for each test path in a spec of the plan that names no file of the commit.
    The base text of a changed file is not read: the plan cannot change it (#4791)."""
    return [
        MESSAGES.roadmap.stage_problem_missing_test_file.format(
            path=path, hint=same_name_hint(tree, path)
        )
        for path in missing_test_paths(tree, [spec_file(spec) for spec in proposal.specs])
    ]


def creates_problems(groups: Sequence[StageGroup], creators: Mapping[str, int]) -> list[str]:
    """One sentence for each path that a group creates and the plan of an open item creates too
    (#3418). A path that two groups create gets one sentence."""
    texts = MESSAGES.roadmap
    shared = dict.fromkeys(path for group in groups for path in group.creates if path in creators)
    return [texts.stage_problem_creates.format(number=creators[path], path=path) for path in shared]


def _overlap_problems(dependencies: Sequence[str], overlaps: Sequence[Overlap]) -> list[str]:
    """One sentence for each overlap that no `dependencies` entry names by its number and a
    shared path."""
    texts = MESSAGES.roadmap
    problems: list[str] = []
    for overlap in overlaps:
        path = overlap.paths[0]
        if any(f"#{overlap.number}" in entry and path in entry for entry in dependencies):
            continue
        problems.append(texts.stage_problem_dependencies.format(pull=overlap.number, path=path))
    return problems


def issue_dependencies(dependencies: Sequence[str]) -> list[int]:
    """The number of each `dependencies` entry that names an issue, in the order of the entries
    (#3224). An entry of another form, such as an overlap or a metric sender, gives no number."""
    return [
        int(found.group("number"))
        for entry in dependencies
        if (found := _ISSUE_DEPENDENCY.match(entry.strip())) is not None
    ]


def closing_keyword_in(text: str) -> str | None:
    """The closing keyword that `text` puts before an issue reference, or None.

    GitHub closes the issue when the body of a pull request holds one of its closing keywords,
    with an optional colon, and then a reference to an issue (`#12`, `owner/repo#12` or the URL
    of the issue). A pull request that only plans an item closes none (#2654).
    """
    words = text.split()
    for word, following in pairwise(words):
        keyword = word.strip(_WORD_PUNCTUATION).lower()
        if keyword in _CLOSING_KEYWORDS and ("#" in following or "/issues/" in following):
            return keyword
    return None


# ── The files ─────────────────────────────────────────────────────────────────


def _bullets(lines: Sequence[str]) -> str:
    return "\n".join(f"- {line.strip()}" for line in lines)


# The scenarios of a base requirement that a MODIFIED block omits: the name of each and its raw text,
# by the name of the requirement (#4310).
OmittedScenarios = Mapping[str, Sequence[tuple[str, str]]]


def omitted_scenarios(
    requirement: StageRequirement, base: Sequence[tuple[str, str]]
) -> list[tuple[str, str]]:
    """The scenarios of `base`, as pairs of name and raw text, that `requirement` does not name.
    OpenSpec compares the names of the scenarios, without the white space at their ends (#4310)."""
    named = {scenario.name.strip() for scenario in requirement.scenarios}
    return [(name, raw) for name, raw in base if name.strip() not in named]


# The header of a requirement. A rename holds it in a code span, as the OpenSpec documents write it:
# the span keeps a name that ends with a code span whole, as OpenSpec strips one closing backtick of
# the line (#5340).
_REQUIREMENT_HEADER: Final[str] = "### Requirement: "


def _requirement_lines(
    requirement: StageRequirement, omitted: Sequence[tuple[str, str]] = ()
) -> str:
    scenarios = "\n\n".join(
        [
            f"#### Scenario: {s.name.strip()}\n- **WHEN** {s.when.strip()}\n- **THEN** {s.then.strip()}"
            for s in requirement.scenarios
        ]
        + [f"#### Scenario: {name.strip()}\n{raw.strip()}" for name, raw in omitted]
    )
    return f"{_REQUIREMENT_HEADER}{requirement.name.strip()}\n{requirement.text.strip()}\n\n{scenarios}"


def _removal_lines(removal: StageRemoval) -> str:
    """The block of one removal: the header, the reason and the migration, in the form of the
    OpenSpec documents (#5340)."""
    lines = [f"{_REQUIREMENT_HEADER}{removal.name}", f"**Reason**: {removal.reason}"]
    if removal.migration:
        lines.append(f"**Migration**: {removal.migration}")
    return "\n".join(lines)


def _rename_lines(rename: StageRename) -> str:
    """The FROM line and the TO line of one rename, each header in a code span (#5340)."""
    return (
        f"- FROM: `{_REQUIREMENT_HEADER}{rename.from_name}`\n"
        f"- TO: `{_REQUIREMENT_HEADER}{rename.to_name}`"
    )


def spec_file_path(change: str, capability: str) -> str:
    """The path of the spec delta of `capability` in the change `change`."""
    return f"{_CHANGES_DIRECTORY}/{change}/specs/{capability}/spec.md"


def spec_file(spec: StageSpec, omitted: OmittedScenarios | None = None) -> str:
    """The text of the spec delta of `spec`. `omitted` gives, by the name of a MODIFIED
    requirement, the base scenarios that its block adds after the scenarios of the reply (#4310).
    The REMOVED and RENAMED sections follow the ADDED and MODIFIED sections, as in the template of
    OpenSpec, and a delta with neither writes the same text as before (#5340)."""
    parts: list[str] = []
    if spec.purpose:
        parts.append(f"## Purpose\n{spec.purpose.strip()}")
    if spec.added:
        body = "\n\n".join(_requirement_lines(r) for r in spec.added)
        parts.append(f"## ADDED Requirements\n\n{body}")
    if spec.modified:
        body = "\n\n".join(
            _requirement_lines(r, (omitted or {}).get(r.name.strip(), ())) for r in spec.modified
        )
        parts.append(f"## MODIFIED Requirements\n\n{body}")
    if spec.removed:
        body = "\n\n".join(_removal_lines(r) for r in spec.removed)
        parts.append(f"## REMOVED Requirements\n\n{body}")
    if spec.renamed:
        body = "\n\n".join(_rename_lines(r) for r in spec.renamed)
        parts.append(f"## RENAMED Requirements\n\n{body}")
    return "\n\n".join(parts) + "\n"


def _impact(groups: Sequence[StageGroup]) -> str:
    changed = list(dict.fromkeys(path for group in groups for path in group.changes))
    tests = [p for p in changed if p.startswith(_TESTS_DIRECTORY)]
    documents = [p for p in changed if p.endswith(_DOCUMENT_SUFFIX) and p not in tests]
    code = [p for p in changed if p not in tests and p not in documents]
    texts = MESSAGES.roadmap
    lines = [
        texts.stage_impact_line.format(kind=kind, paths=", ".join(f"`{p}`" for p in paths))
        for kind, paths in (
            (texts.stage_impact_code, code),
            (texts.stage_impact_documents, documents),
            (texts.stage_impact_tests, tests),
        )
        if paths
    ]
    return "\n".join(f"- {line}" for line in lines)


def _capabilities(specs: Sequence[StageSpec], known: Collection[str]) -> str:
    texts = MESSAGES.roadmap

    def names(spec: StageSpec) -> str:
        changed = [r.name.strip() for r in (*spec.added, *spec.modified)]
        changed.extend(r.to_name for r in spec.renamed)
        changed.extend(r.name for r in spec.removed)
        return ", ".join(dict.fromkeys(changed))

    def listed(chosen: Sequence[StageSpec]) -> str:
        return "\n".join(f"- `{s.capability}`: {names(s)}" for s in chosen) or texts.stage_none

    return (
        f"### New Capabilities\n\n{listed([s for s in specs if s.capability not in known])}\n\n"
        f"### Modified Capabilities\n\n{listed([s for s in specs if s.capability in known])}"
    )


def _proposal_file(proposal: StageProposal, known: Collection[str]) -> str:
    texts = MESSAGES.roadmap
    changes = [*proposal.what_changes, texts.stage_fits_one_pr]
    impact = _impact(proposal.groups) or texts.stage_none
    dependencies = _bullets(proposal.dependencies) or texts.stage_none
    return (
        f"# Proposal\n\n## Why\n\n{proposal.why.strip()}\n\n"
        f"## What Changes\n\n{_bullets(changes)}\n\n"
        f"## Capabilities\n\n{_capabilities(proposal.specs, known)}\n\n"
        f"## Impact\n\n{impact}\n\n"
        f"## Feasibility\n\n{_bullets(proposal.feasibility)}\n\n"
        f"## Existing Tool Considered\n\n{proposal.existing_tool.strip()}\n\n"
        f"## Dependencies\n\n{dependencies}\n"
    )


def _design_file(proposal: StageProposal) -> str:
    texts = MESSAGES.roadmap
    decisions = _bullets(
        [f"**{d.decision.strip()}**: {d.reason.strip()}" for d in proposal.decisions]
    )
    rejected = _bullets(
        [f"**{r.alternative.strip()}**: {r.evidence.strip()}" for r in proposal.rejected]
    )
    content = (
        f"# Design\n\n## Decisions\n\n{decisions or texts.stage_none}\n\n"
        f"## Rejected alternatives\n\n{rejected or texts.stage_none}\n"
    )
    unchanged = [ref for ref in proposal.references if ref.unchanged]
    if unchanged:
        references = _bullets(
            [f"`{ref.path}` ({ref.kind}): {(ref.reason or '').strip()}" for ref in unchanged]
        )
        content += f"\n## Unchanged references\n\n{references}\n"
    if proposal.security.strip():
        content += f"\n## Security\n\n{proposal.security.strip()}\n"
    return content


def _paths(paths: Sequence[str], created: Collection[str] = ()) -> str:
    """The paths as code spans, a created path with its mark."""
    mark = MESSAGES.roadmap.stage_group_new
    return ", ".join(f"`{p}`{mark if p in created else ''}" for p in paths)


def _task_texts(group: StageGroup) -> list[str]:
    """The tasks of `group` in order, with no number. A `behavior` group starts with its failing
    test, and a `manifest` group with its failing case. An `other` group has no test: its work
    comes first, with the check that proves it. A group that changes a document ends with its
    documents task."""
    texts = MESSAGES.roadmap
    if group.kind in _CASE_FIRST_KINDS:
        tasks = [
            texts.stage_task_test.format(test=group.test, verify=group.verify),
            texts.stage_task_pass.format(work=group.implementation, verify=group.verify),
        ]
    elif group.process is not None:
        tasks = [texts.stage_task_process.format(work=group.implementation, process=group.process)]
    else:
        tasks = [texts.stage_task_pass.format(work=group.implementation, verify=group.verify)]
    if group.documentation is not None:
        tasks.append(_documents_task(group.documentation, group.changes))
    return tasks


def _task_work_texts(group: StageGroup) -> list[str]:
    """The work text of each task of `group`, in the order of `_task_texts`: the test task of a
    `behavior` group or the case task of a `manifest` group, its implementation task, and its
    documents task. The `Verification:` line, the `process` check and the fixed documents command
    are no work of a task, so two tasks may share one and stay two tasks (#3456)."""
    works = [group.test] if group.kind in _CASE_FIRST_KINDS else []
    works.extend((group.implementation, group.documentation))
    return [work for work in works if work is not None]


def _is_document_path(word: str) -> bool:
    """Whether `word` names a path: it holds a slash, or it ends in a dot and letters, as the
    name of a root document does. A version such as `v1.2` is no path."""
    return "/" in word or _PATH_SUFFIX.search(word) is not None


def document_work(documentation: str) -> str:
    """The work of a documents task. A text that starts with a path gets the verb `Edit` and the
    path in a code span, so the task starts with a verb (#3226). Any other text is kept as it is,
    so a text that starts with a verb has no second verb."""
    word, space, rest = documentation.partition(" ")
    path = word.rstrip(".,;:")
    name = path.strip("`")
    if not _is_document_path(name):
        return documentation
    return MESSAGES.roadmap.stage_document_path.format(
        path=name, rest=f"{word[len(path) :]}{space}{rest}"
    )


def _documents_task(documentation: str, changes: Sequence[str]) -> str:
    """The documents task of a group. It ends with the step that regenerates the documents only
    when the group changes a command, an option or a message, because only those change the
    generated text (#3226)."""
    texts = MESSAGES.roadmap
    work = document_work(documentation)
    if any(path.startswith(_REGENERATE_PREFIXES) for path in changes):
        work += texts.stage_task_regenerate.format(command=REGENERATE_DOCUMENTS)
    return texts.stage_task_documents.format(work=work)


def group_text(index: int, group: StageGroup) -> str:
    """The group as `tasks.md` holds it, numbered `index`: its kind and its files on one line, and
    the tasks of its kind. The plan reader reads the kind from that line, because a `manifest`
    group has the tasks of a `behavior` group (#5205). `group` is a validated group: its texts are
    on one line (`_one_line`), and `verify` holds no backtick (`form_problems`). A group built with
    `model_construct` skips that check, and no caller renders one."""
    texts = MESSAGES.roadmap
    files = texts.stage_group_files.format(
        kind=group.kind,
        reads=_paths(group.reads) or texts.stage_group_no_reads,
        changes=_paths(group.changes, group.creates),
    )
    tasks = "".join(
        f"- [ ] {index}.{number} {task}\n"
        for number, task in enumerate(_task_texts(group), start=1)
    )
    return f"## {index}. {group.title}\n\n{files}\n\n{tasks}"


def criteria_section(criteria: Sequence[StageCriterion]) -> str:
    """The `## Criteria` section of `tasks.md`: one line for each acceptance criterion with the
    group that delivers it, or `pending-person` and the reason. It is no task, so it has no box.
    A line starts with a fixed word and holds the folded text of the criterion, which comes from
    the issue: a criterion `## 2. X` is no heading of the file. A plan with no criterion has no
    section."""
    texts = MESSAGES.roadmap
    lines = [
        texts.stage_criteria_pending.format(
            criterion=_one_line(c.criterion), reason=_one_line(c.reason or "")
        )
        if c.group == PENDING_PERSON
        else texts.stage_criteria_line.format(criterion=_one_line(c.criterion), group=c.group)
        for c in criteria
    ]
    return f"## {texts.stage_criteria_title}\n\n{_bullets(lines)}\n\n" if lines else ""


_criteria_section = criteria_section


def _follow_up_section(groups: Sequence[StageGroup]) -> str:
    """The `## Workflow follow-up` section with the tuicr bullet, for a plan that changes a path
    under `src/`, the only plan that has code for tuicr to review. A plan with no such path has no
    section."""
    if not any(changes_source(g.changes) for g in groups):
        return ""
    return f"## Workflow follow-up\n\n- {MESSAGES.roadmap.stage_pending_review}\n"


def _tasks_file(groups: Sequence[StageGroup], criteria: Sequence[StageCriterion] = ()) -> str:
    sections = "\n".join(group_text(i, g) for i, g in enumerate(groups, start=1))
    body = f"# Tasks\n\n{sections}\n{_criteria_section(criteria)}{_follow_up_section(groups)}"
    return body.rstrip("\n") + "\n"


def render_change(
    change: str,
    proposal: StageProposal,
    known: Collection[str],
    *,
    created: date,
) -> dict[str, str]:
    """The files of the change `change`, by path from the repository root."""
    root = f"{_CHANGES_DIRECTORY}/{change}"
    skip = "skip_specs: true\n" if proposal.skip_specs else ""
    files = {
        f"{root}/.openspec.yaml": f"schema: spec-driven\ncreated: {created.isoformat()}\n{skip}",
        f"{root}/proposal.md": _proposal_file(proposal, known),
        f"{root}/design.md": _design_file(proposal),
        f"{root}/tasks.md": _tasks_file(proposal.groups, proposal.criteria),
    }
    for spec in proposal.specs:
        files[spec_file_path(change, spec.capability)] = spec_file(spec)
    return files


def _shows_something(char: str) -> bool:
    """Whether `char` shows something to a reader."""
    return char not in _BLANK_FILLERS and unicodedata.category(char) not in _INVISIBLE_CATEGORIES


def staging_title(number: int, summary: str) -> str:
    """The title of the draft pull request of item `number`: `docs(openspec): plan #<number>
    <summary>`. It is on one line, with a handle or a link in a code span, so it pings no one. The
    part after the colon has at most `SUMMARY_MAX_CHARS` characters (#2714). A summary that the
    schema accepts (`STAGE_SUMMARY_MAX_CHARS`) always fits, for a number of `ISSUE_NUMBER_DIGITS`
    digits or fewer. The title is never cut, because a cut text ends with `...` and the form check
    refuses it (#3249): a summary that does not fit stops the item with `RoadmapStageError`."""
    lead = MESSAGES.roadmap.stage_title_lead.format(number=number)
    shown = safe_title(summary)
    length = summary_length(lead + shown)
    if length > SUMMARY_MAX_CHARS:
        raise RoadmapStageError(
            MESSAGES.roadmap.stage_title_long.format(
                number=number, length=length, limit=SUMMARY_MAX_CHARS
            ),
            failed_items=[number],
        )
    return f"{STAGING_TYPE}: {lead}{shown}"


def plan_summary(subject: str, number: int) -> str | None:
    """The summary of the plan of item `number` in `subject`, the subject of the commit that adds
    its change folder (#5341). The stage job writes that subject as `staging_title` does, and the
    squash merge of the plan pull request writes its title and adds ` (#<pull>)`. None when
    `subject` is no plan title of the item, or holds no summary."""
    lead = f"{STAGING_TYPE}: {MESSAGES.roadmap.stage_title_lead.format(number=number)}"
    title = _SQUASH_SUFFIX.sub("", subject.strip())
    if not title.startswith(lead):
        return None
    return title.removeprefix(lead).strip() or None


def delivery_title(issue_title: str, declared: Collection[str], summary: str | None = None) -> str:
    """The title of the pull request that delivers the code of an item (#2714): the type and the
    scope of the issue's title, and `summary`, the summary of the plan (#5341). The issue states a
    goal, and the plan states the change that the branch makes. With no `summary`, the title keeps
    the whole summary of the issue's title. It is never cut, because a cut text ends with `...`
    and hides the summary (#3200): the form check of the pull request judges a long one. The
    staging pull request has the type `docs(openspec)`, which the delivery must not keep. A mark
    of a breaking change is dropped: the project has none before 1.0.0. A scope whose `scope/*`
    label is not in `declared` is dropped too, because the `Semantic PR title` check refuses it
    (#2800)."""
    head, _, issue_summary = issue_title.partition(":")
    head = head.strip().removesuffix("!")
    scope = commit_scope(issue_title)
    if scope and f"{CONST_ROADMAP_SCOPE_LABEL_PREFIX}{scope}" not in declared:
        head = head.partition("(")[0]
    return f"{head}: {safe_title(issue_summary if summary is None else summary)}"


def pull_request_body(number: int, change: str, proposal: StageProposal) -> str:
    """The body of the draft: `Plans #<issue>`, the what and why, and the change folder. It is
    built and checked by `build_plan_body`, which raises `ValidationError` for a body that breaks
    the plan form."""
    return build_plan_body(
        why=safe_text(proposal.pull_request_body),
        issue=number,
        change=f"openspec/changes/{change}",
    )


def safe_text(text: str) -> str:
    """The model's `text` on one line, with a handle, a link or a reference to another repository
    in a code span, so it pings no one and links nothing in a pull request or a comment, and with
    the `<` of each tag outside code as an entity, so it shows as text and acts as no tag."""
    return sanitize_text(" ".join(text.split()), set())


def safe_title(text: str) -> str:
    """The model's `text` as `safe_text` writes it, but with each tag as it is. A title is plain
    text: GitHub shows `<section>` as text and counts its characters, and the squash commit takes
    the title as it is, so an entity would show as the text `&lt;` (#3504). The `<` of a comment
    opener is still an entity, since the job puts a title in a comment too."""
    return sanitize_text(" ".join(text.split()), set(), escape_tags=False)


# ── The measure ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MeasuredGroup:
    """A task group, the tokens of the inputs of its step, and the number of files that the step
    packs for it (#3499)."""

    group: StageGroup
    tokens: int
    files: int


def _reads(root: Path, text: str) -> tuple[int, int]:
    """The tokens and the count of what the step of the group `text` reads under `root`: the files
    that its tasks name, each packed as the step packs it (`step_files`), and the rules of the
    checkout that the step adds (`step_rules`). The count is the count of files, and the tokens
    include the rules. The step ignores a file that only the `Reads:` line lists, and a name that
    holds no file is a file the step creates."""
    tokens = files = 0
    for group in parse_task_groups(text):
        paths = named_files(root, group)
        files += len(paths)
        tokens += sum(count_tokens(packed_file(path)) for path in paths)
        tokens += sum(count_tokens(section) for section in rules_sections(root, group))
    return tokens, files


def shared_texts(title: str, body: str, files: Mapping[str, str]) -> list[str]:
    """The text that all groups of a change share in their measure: the item, and the files of the
    change folder by path. The stage job and `plan-check` both build it here, so their figures for
    one plan stay equal (#3499)."""
    return [f"{title}\n{body}", *files.values()]


def measure_groups(
    root: Path,
    groups: Sequence[StageGroup],
    *,
    shared: Sequence[str],
) -> list[MeasuredGroup]:
    """The measure of each group: the tokens of `shared` (the item and the files of the change
    folder), of the group's own text, of the files and the rules that its step reads under `root`,
    and of the estimated lines of each file that it creates. It also counts the files that the
    step packs."""
    shared_tokens = sum(count_tokens(text) for text in shared)
    measured: list[MeasuredGroup] = []
    for index, group in enumerate(groups, start=1):
        text = group_text(index, group)
        read_tokens, files = _reads(root, text)
        tokens = (
            shared_tokens
            + count_tokens(text)
            + read_tokens
            + sum(group.creates_lines.values()) * CREATED_LINE_TOKENS
        )
        measured.append(MeasuredGroup(group, tokens, files))
    return measured


def write_change_files(root: Path, files: Mapping[str, str]) -> None:
    """Write `files`, by path from the repository root, under `root`. A path that leaves `root`
    raises `SecurityError`."""
    for path, text in files.items():
        target = safe_resolve_subpath(root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def comment_groups(measured: Sequence[MeasuredGroup]) -> Mapping[str, int]:
    """The title of each group with its tokens, as the record keeps them."""
    return {m.group.title: m.tokens for m in measured}
