"""The change that the stage job writes (#2654): the reply of the model, the files of the OpenSpec
change it renders, and the measure of each task group against the step budget.

The reply is one `StageProposal`. `check_proposal` finds what the rules of `openspec/config.yaml`
ask and a schema cannot say: a Purpose on a new capability, a MODIFIED requirement only on a
capability that exists, a spec delta only when the change is observable, and a path that is a file
of the staged commit or that a group creates (`stage_paths`). `render_change`
turns the reply into the files of `openspec/changes/<issue>-<slug>/`. `measure_groups` counts the
inputs of one implementation step for each group with tiktoken. It counts the files that the tasks
of the group name, each packed as the step packs it (`step_files`), so a group costs what its step
reads.
"""

from __future__ import annotations

import re
import string
import unicodedata
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from itertools import pairwise
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Annotated, Final, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from devops_cli.ai.context_budget import count_tokens
from devops_cli.config.constants import CONST_ROADMAP_SCOPE_LABEL_PREFIX
from devops_cli.core.paths import safe_resolve_subpath
from devops_cli.exceptions.roadmap import RoadmapStageError
from devops_cli.git.branch_form import is_valid_slug
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.commit_title import commit_scope
from devops_cli.roadmap.pull_form import SUMMARY_MAX_CHARS, is_placeholder, summary_length
from devops_cli.roadmap.refine import sanitize_text
from devops_cli.roadmap.stage_criteria import PENDING_PERSON, StageCriterion, criterion_problems
from devops_cli.roadmap.stage_form import form_problems, search_problems
from devops_cli.roadmap.stage_move import move_prefix_problems, move_verify_problems
from devops_cli.roadmap.stage_paths import StagedTree, change_folder_paths, path_problems
from devops_cli.roadmap.step_files import named_files, packed_file, parse_task_groups
from devops_cli.roadmap.step_rules import rules_sections

if TYPE_CHECKING:
    from devops_cli.roadmap.stage_overlap import Overlap

# A plan is documentation, not a fix or a feature: only the types feat, fix, perf, refactor and
# revert add a line to the changelog, so a pull request that only plans an item has this type.
STAGING_TYPE: Final[str] = "docs(openspec)"
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
# The tokens of one estimated line of a file that a task group creates. The stage adds them to the
# measure of the group, so a large new file counts before the implement Job reads it (#3265).
CREATED_LINE_TOKENS: Final[int] = 32
# The fewest characters of a text of the plan that stands for a sentence: `why`, `existing_tool`, a
# line of `feasibility`, a decision and a task. `No alternative.` has 15, and `x` or `todo` has
# fewer (#3200).
PLAN_FIELD_MIN_CHARS: Final[int] = 10
# The cost that rule 3 of `AGENTS.md` asks of a plan that builds its own code: a number of tokens,
# with an optional `k`, and a number of hours or minutes.
_TOKEN_COST: Final[re.Pattern[str]] = re.compile(r"\d+(?:[.,]\d+)*\s*k?\s*tokens?\b", re.IGNORECASE)
_TIME_COST: Final[re.Pattern[str]] = re.compile(
    r"\d+(?:[.,]\d+)*\s*(?:hours?|minutes?)\b", re.IGNORECASE
)
_REQUIREMENT_WORDS: Final[frozenset[str]] = frozenset({"SHALL", "MUST"})
_WORD_PUNCTUATION: Final[str] = ".,;:()"
# GitHub closes the issue that follows one of these words in the body of a pull request.
_CLOSING_KEYWORDS: Final[frozenset[str]] = frozenset(
    {"close", "closes", "closed", "fix", "fixes", "fixed", "resolve", "resolves", "resolved"}
)
# A change whose every path starts with one of these has no spec delta: tests, workflows, documents
# and plans are not behavior a consumer observes (#3013).
_NO_SPEC_PREFIXES: Final[tuple[str, ...]] = ("tests/", ".github/workflows/", "docs/", "openspec/")
_NO_SPEC_PREFIXES_TEXT: Final[str] = (
    f"{', '.join(_NO_SPEC_PREFIXES[:-1])} or {_NO_SPEC_PREFIXES[-1]}"
)
_TESTS_DIRECTORY: Final[str] = "tests/"
_SOURCE_DIRECTORY: Final[str] = "src/"
_DOCUMENT_SUFFIX: Final[str] = ".md"
_CHANGES_DIRECTORY: Final[str] = "openspec/changes"
# Only `openspec archive` writes a living spec, from the spec delta of the change folder, so no
# task group changes or creates a path under this prefix (#3295).
_LIVING_SPEC_DIRECTORY: Final[str] = "openspec/specs/"
# The catalog of the roadmap messages. A task text that names `MESSAGES.roadmap` needs this file
# in `changes`, so the stage check names it when no group lists it (#3405).
_MESSAGES_FILE: Final[str] = "src/devops_cli/lang/en/messages.py"
_MESSAGE_NAME: Final[re.Pattern[str]] = re.compile(r"\bMESSAGES\.roadmap\b")
_SENTENCE_END: Final[str] = f"{string.whitespace}."
REGENERATE_DOCUMENTS: Final[str] = "uv run devops docs generate --sync-readme"

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
    if not is_valid_slug(name):
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
    str, StringConstraints(strip_whitespace=True, min_length=1), AfterValidator(_one_line)
]
# A command: on one line, with its spaces kept.
Command = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1), AfterValidator(_join_lines)
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
    str, StringConstraints(strip_whitespace=True, min_length=1), AfterValidator(_one_line)
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


class StageSpec(_Reply):
    """The delta of one capability. `purpose` is set for a new capability only."""

    capability: Annotated[str, AfterValidator(_capability_name)]
    purpose: LineStart | None = None
    added: list[StageRequirement] = Field(default_factory=list)
    modified: list[StageRequirement] = Field(default_factory=list)


class StageDecision(_Reply):
    """A design decision and its reason."""

    decision: Line
    reason: Line


class StageRejection(_Reply):
    """An alternative the design rejected, and the evidence that rejected it."""

    alternative: Line
    evidence: Line


class GroupKind(StrEnum):
    """What a task group does. `behavior` adds or changes what the code does: its work starts with
    a failing test. `other` is a document, a manifest, a workflow, a deletion or a refactor that
    keeps behavior, a test-only edit or data: it has no test, and a command or a process proves
    it (#3005)."""

    BEHAVIOR = "behavior"
    OTHER = "other"


class StageGroup(_Reply):
    """One task group of the change: the work of one implementation step. A group changes at
    least one file. `creates` lists the paths of `changes` that the step makes, and `creates_lines`
    gives the estimated number of lines of each of those paths.

    The `kind` sets the tasks. A `behavior` group has a `test` and a `verify` that runs it, and
    changes a path under `src/`. An `other` group has no `test`, and one of `verify` (a command
    that gives the same answer on each run) and `process` (the steps of a manual check).
    `documentation` is None when the group changes no document."""

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
        problems = (
            _behavior_problems(self) if self.kind is GroupKind.BEHAVIOR else _other_problems(self)
        )
        if problems:
            raise ValueError(" ".join(problems))
        return self

    @model_validator(mode="after")
    def _no_change_folder_writes(self) -> Self:
        problems = _change_folder_problems(self)
        if problems:
            raise ValueError(" ".join(problems))
        return self


def _behavior_problems(group: StageGroup) -> list[str]:
    """What breaks the rules of a `behavior` group: no test, no command for it, a process, or no
    path under `src/`."""
    texts = MESSAGES.roadmap
    found = (
        (group.test is None, texts.stage_kind_no_test),
        (group.verify is None, texts.stage_kind_no_verify),
        (group.process is not None, texts.stage_kind_behavior_process),
        (
            not any(path.startswith(_SOURCE_DIRECTORY) for path in group.changes),
            texts.stage_kind_no_source,
        ),
    )
    return [text.format(title=group.title) for broken, text in found if broken]


def _other_problems(group: StageGroup) -> list[str]:
    """What breaks the rules of an `other` group: a test, or not exactly one of `verify` and
    `process`."""
    texts = MESSAGES.roadmap
    found = (
        (group.test is not None, texts.stage_kind_other_test),
        (group.verify is None and group.process is None, texts.stage_kind_no_check),
        (group.verify is not None and group.process is not None, texts.stage_kind_two_checks),
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

    @field_validator("summary")
    @classmethod
    def _summary_fits_the_title(cls, summary: str) -> str:
        """The title shows the summary as `safe_text` writes it: on one line, and with a code span
        for a handle or a link. The limit counts that text in the units of the check `Semantic PR
        title` (`summary_length`), so spare whitespace costs nothing, a handle costs its code span
        and an emoji costs two. A summary with no text left is refused too. The reply that breaks
        it goes back to the model with the count and the limit, and `staging_title` cuts no summary
        that the schema accepts."""
        text = safe_text(summary)
        shown = summary_length(text)
        if not any(_shows_something(char) for char in text):
            raise ValueError(MESSAGES.roadmap.stage_summary_blank)
        if text.endswith(_ELLIPSIS):
            raise ValueError(MESSAGES.roadmap.stage_summary_cut)
        if shown > STAGE_SUMMARY_MAX_CHARS:
            raise ValueError(
                MESSAGES.roadmap.stage_summary_long.format(
                    length=shown, limit=STAGE_SUMMARY_MAX_CHARS
                )
            )
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
    if not exists and spec.modified:
        problems.append(texts.stage_problem_modified.format(capability=spec.capability))
    problems.extend(
        texts.stage_problem_keyword.format(requirement=requirement.name)
        for requirement in (*spec.added, *spec.modified)
        if not _says_shall_or_must(requirement.text)
    )
    return problems


def _needs_no_spec(proposal: StageProposal) -> bool:
    """Whether every path of `changes`, in every group, is a test, a workflow, a document or a
    plan: a change that no consumer observes (#3013)."""
    return all(
        path.startswith(_NO_SPEC_PREFIXES) for group in proposal.groups for path in group.changes
    )


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


def _delta_problems(
    proposal: StageProposal, known: Collection[str], requirements: Mapping[str, Collection[str]]
) -> list[str]:
    """What is wrong with the spec delta of `proposal` as a whole and in each capability."""
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
        problems.extend(_duplicate_problems(spec, requirements))
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


def content_problems(proposal: StageProposal, probes: Sequence[str] = ()) -> list[str]:
    """What is wrong with the text of `proposal` that no schema says (#3200): a text that is too
    short or a placeholder word (`is_placeholder` of the pull request form), a `feasibility` that
    quotes no line of `probes` when there are some, a task text that names a `MESSAGES.roadmap`
    entry while no group changes the message file (#3405), and a plan that builds its own code and
    gives no cost of tokens and time in `existing_tool`. The replay (`stage_eval_gates`) and the
    job both call this through `check_proposal`, so one rule set judges both."""
    texts = MESSAGES.roadmap
    problems = [p for field, text in _plan_texts(proposal) for p in _text_problems(field, text)]
    problems.extend(_message_file_problems(proposal))
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


def check_proposal(
    proposal: StageProposal,
    known: Collection[str],
    tree: StagedTree,
    *,
    requirements: Mapping[str, Collection[str]] | None = None,
    issue_body: str = "",
    probes: Sequence[str] = (),
    overlaps: Sequence[Overlap] = (),
    search_evidence: Mapping[str, Sequence[str]] | None = None,
    plan_creates: Mapping[str, int] | None = None,
) -> list[str]:
    """What the rules of `openspec/config.yaml` and the files of the commit find wrong in
    `proposal`, one sentence each. `known` holds the names of the capabilities under
    `openspec/specs/`, `requirements` the requirement names of each base spec by capability, and
    `tree` the files that exist when the change is written. The tree also tells a repository path
    from a word, for the code spans of `what_changes` (#3411). `issue_body` is the whole body of the
    issue: each acceptance criterion in it needs an entry in `criteria` (#3019), and a body with
    none needs no entry. `probes` holds the lines of the premise probe that the model read: when it
    is not empty, `feasibility` quotes one (#3200). `overlaps` lists the open pull requests that
    change a path the item cites: the plan names each in `dependencies` (#3252).
    `search_evidence` maps each negative-search literal to the paths that the staged tree holds:
    the job records it, the replay reads it from its case, and None records no search. `plan_creates`
    maps each path that the plan of an open item creates to that item's number (#3418)."""
    problems = _delta_problems(proposal, known, requirements or {})
    problems.extend(content_problems(proposal, probes))
    problems.extend(form_problems(proposal.groups))
    problems.extend(path_problems(proposal.groups, tree))
    problems.extend(_what_changes_problems(proposal, tree))
    problems.extend(move_prefix_problems(proposal.groups, tree))
    problems.extend(move_verify_problems(proposal.groups, tree))
    problems.extend(search_problems(proposal.groups, search_evidence))
    problems.extend(criterion_problems(proposal.criteria, issue_body, len(proposal.groups)))
    problems.extend(_overlap_problems(proposal.dependencies, overlaps))
    problems.extend(_creates_problems(proposal.groups, plan_creates or {}))
    return problems


def _creates_problems(groups: Sequence[StageGroup], creators: Mapping[str, int]) -> list[str]:
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


def _requirement_lines(requirement: StageRequirement) -> str:
    scenarios = "\n\n".join(
        f"#### Scenario: {s.name.strip()}\n- **WHEN** {s.when.strip()}\n- **THEN** {s.then.strip()}"
        for s in requirement.scenarios
    )
    return f"### Requirement: {requirement.name.strip()}\n{requirement.text.strip()}\n\n{scenarios}"


def _spec_file(spec: StageSpec) -> str:
    parts: list[str] = []
    if spec.purpose:
        parts.append(f"## Purpose\n{spec.purpose.strip()}")
    for heading, requirements in (("ADDED", spec.added), ("MODIFIED", spec.modified)):
        if requirements:
            body = "\n\n".join(_requirement_lines(r) for r in requirements)
            parts.append(f"## {heading} Requirements\n\n{body}")
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

    def listed(chosen: Sequence[StageSpec]) -> str:
        return (
            "\n".join(
                f"- `{s.capability}`: {', '.join(r.name.strip() for r in (*s.added, *s.modified))}"
                for s in chosen
            )
            or texts.stage_none
        )

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
    return (
        f"# Design\n\n## Decisions\n\n{decisions or texts.stage_none}\n\n"
        f"## Rejected alternatives\n\n{rejected or texts.stage_none}\n"
    )


def _paths(paths: Sequence[str], created: Collection[str] = ()) -> str:
    """The paths as code spans, a created path with its mark."""
    mark = MESSAGES.roadmap.stage_group_new
    return ", ".join(f"`{p}`{mark if p in created else ''}" for p in paths)


def _task_texts(group: StageGroup) -> list[str]:
    """The tasks of `group` in order, with no number. A `behavior` group starts with its failing
    test. An `other` group has no test: its work comes first, with the check that proves it. A
    group that changes a document ends with the task that regenerates the documents."""
    texts = MESSAGES.roadmap
    if group.kind is GroupKind.BEHAVIOR:
        tasks = [
            texts.stage_task_test.format(test=group.test, verify=group.verify),
            texts.stage_task_pass.format(work=group.implementation, verify=group.verify),
        ]
    elif group.process is not None:
        tasks = [texts.stage_task_process.format(work=group.implementation, process=group.process)]
    else:
        tasks = [texts.stage_task_pass.format(work=group.implementation, verify=group.verify)]
    if group.documentation is not None:
        tasks.append(
            texts.stage_task_documents.format(
                work=group.documentation, command=REGENERATE_DOCUMENTS
            )
        )
    return tasks


def group_text(index: int, group: StageGroup) -> str:
    """The group as `tasks.md` holds it, numbered `index`: its files, and the tasks of its kind.
    `group` is a validated group: its texts are on one line (`_one_line`), and `verify` holds no
    backtick (`form_problems`). A group built with `model_construct` skips that check, and no
    caller renders one."""
    texts = MESSAGES.roadmap
    files = texts.stage_group_files.format(
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


def _tasks_file(groups: Sequence[StageGroup], criteria: Sequence[StageCriterion] = ()) -> str:
    sections = "\n".join(group_text(i, g) for i, g in enumerate(groups, start=1))
    return f"# Tasks\n\n{sections}\n{_criteria_section(criteria)}## Workflow follow-up\n\n- {MESSAGES.roadmap.stage_pending_review}\n"


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
        files[f"{root}/specs/{spec.capability}/spec.md"] = _spec_file(spec)
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
    shown = safe_text(summary)
    length = summary_length(lead + shown)
    if length > SUMMARY_MAX_CHARS:
        raise RoadmapStageError(
            MESSAGES.roadmap.stage_title_long.format(
                number=number, length=length, limit=SUMMARY_MAX_CHARS
            ),
            failed_items=[number],
        )
    return f"{STAGING_TYPE}: {lead}{shown}"


def delivery_title(issue_title: str, declared: Collection[str]) -> str:
    """The title of the pull request that delivers the code of an item (#2714): the type and the
    scope of the issue's title, and its whole summary. It is never cut, because a cut text ends
    with `...` and hides the summary (#3200): the form check of the pull request judges a long
    one. The staging pull request has the type `docs(openspec)`, which the delivery must not keep.
    A mark of a breaking change is dropped: the project has none before 1.0.0. A scope whose
    `scope/*` label is not in `declared` is dropped too, because the `Semantic PR title` check
    refuses it (#2800)."""
    head, _, summary = issue_title.partition(":")
    head = head.strip().removesuffix("!")
    scope = commit_scope(issue_title)
    if scope and f"{CONST_ROADMAP_SCOPE_LABEL_PREFIX}{scope}" not in declared:
        head = head.partition("(")[0]
    return f"{head}: {safe_text(summary)}"


def pull_request_body(number: int, change: str, proposal: StageProposal) -> str:
    """The body of the draft: `Plans #<issue>`, the what and why, and the change folder."""
    return MESSAGES.roadmap.stage_pull_request_body.format(
        number=number, body=safe_text(proposal.pull_request_body), change=change
    )


def safe_text(text: str) -> str:
    """The model's `text` on one line, with a handle, a link or a reference to another repository
    in a code span, so it pings no one and links nothing in a pull request or a comment."""
    return sanitize_text(" ".join(text.split()), set())


# ── The measure ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MeasuredGroup:
    """A task group and the tokens of the inputs of its step."""

    group: StageGroup
    tokens: int


def _read_tokens(root: Path, text: str) -> int:
    """The tokens of what the step of the group `text` reads under `root`: the files that its
    tasks name, each packed as the step packs it (`step_files`), and the rules of the checkout
    that the step adds (`step_rules`). The step ignores a file that only the `Reads:` line lists,
    and a name that holds no file is a file the step creates."""
    return sum(
        sum(count_tokens(packed_file(path)) for path in named_files(root, group))
        + sum(count_tokens(section) for section in rules_sections(root, group))
        for group in parse_task_groups(text)
    )


def measure_groups(
    root: Path,
    groups: Sequence[StageGroup],
    *,
    shared: Sequence[str],
) -> list[MeasuredGroup]:
    """The measure of each group: the tokens of `shared` (the item and the files of the change
    folder), of the group's own text, of the files and the rules that its step reads under `root`,
    and of the estimated lines of each file that it creates."""
    shared_tokens = sum(count_tokens(text) for text in shared)
    texts = [group_text(index, group) for index, group in enumerate(groups, start=1)]
    return [
        MeasuredGroup(
            group,
            shared_tokens
            + count_tokens(text)
            + _read_tokens(root, text)
            + sum(group.creates_lines.values()) * CREATED_LINE_TOKENS,
        )
        for group, text in zip(groups, texts, strict=True)
    ]


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
