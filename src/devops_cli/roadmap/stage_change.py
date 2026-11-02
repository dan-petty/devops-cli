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

import string
import textwrap
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from itertools import pairwise
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Final, Self

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
from devops_cli.roadmap.pull_form import SUMMARY_MAX_CHARS
from devops_cli.roadmap.refine import sanitize_text
from devops_cli.roadmap.stage_criteria import PENDING_PERSON, StageCriterion, criterion_problems
from devops_cli.roadmap.stage_form import form_problems
from devops_cli.roadmap.stage_paths import StagedTree, path_problems
from devops_cli.roadmap.step_files import named_files, packed_file, parse_task_groups
from devops_cli.roadmap.step_rules import rules_sections

# A plan is documentation, not a fix or a feature: only the types feat, fix, perf, refactor and
# revert add a line to the changelog, so a pull request that only plans an item has this type.
_STAGING_TYPE: Final[str] = "docs(openspec)"
_ELLIPSIS: Final[str] = "..."
# The most digits that the number of an issue has. The title of a plan is `docs(openspec): plan
# #<number> <summary>` and its summary has at most `SUMMARY_MAX_CHARS` characters (#2714), so the
# room for the model's summary depends on the digits. The schema cannot know the number, so its
# limit is the room for the longest number, and a shorter number leaves room over (#3249).
ISSUE_NUMBER_DIGITS: Final[int] = 6
STAGE_SUMMARY_MAX_CHARS: Final[int] = SUMMARY_MAX_CHARS - len(
    MESSAGES.roadmap.stage_title_lead.format(number=10**ISSUE_NUMBER_DIGITS - 1)
)
# The most characters of the body of a pull request: it is the message of the squash commit.
BODY_MAX_CHARS: Final[int] = 800
# The fewest characters of the Purpose of a new capability, so archive never writes TBD.
PURPOSE_MIN_CHARS: Final[int] = 50
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
_SENTENCE_END: Final[str] = f"{string.whitespace}."
_REGENERATE_DOCUMENTS: Final[str] = "uv run devops docs generate --sync-readme"

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


def _one_line(text: str) -> str:
    """The text on one line, so that a text of the reply adds no line, no task, no group and no
    `Verification:` line to `tasks.md`."""
    return " ".join(text.split())


# A text of a task group: at least one character once the whitespace around it is stripped, and on
# one line in `tasks.md`.
Text = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1), AfterValidator(_one_line)
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
    model_config = ConfigDict(extra="forbid")


class StageScenario(_Reply):
    """One scenario of a requirement, in the shape of an OpenSpec scenario."""

    name: str
    when: str
    then: str


class StageRequirement(_Reply):
    """One requirement of a spec delta; `text` says SHALL or MUST, in capitals."""

    name: str
    text: str
    scenarios: list[StageScenario] = Field(min_length=1)


class StageSpec(_Reply):
    """The delta of one capability. `purpose` is set for a new capability only."""

    capability: Annotated[str, AfterValidator(_capability_name)]
    purpose: str | None = None
    added: list[StageRequirement] = Field(default_factory=list)
    modified: list[StageRequirement] = Field(default_factory=list)


class StageDecision(_Reply):
    """A design decision and its reason."""

    decision: str
    reason: str


class StageRejection(_Reply):
    """An alternative the design rejected, and the evidence that rejected it."""

    alternative: str
    evidence: str


class GroupKind(StrEnum):
    """What a task group does. `behavior` adds or changes what the code does: its work starts with
    a failing test. `other` is a document, a manifest, a workflow, a deletion or a refactor that
    keeps behavior, a test-only edit or data: it has no test, and a command or a process proves
    it (#3005)."""

    BEHAVIOR = "behavior"
    OTHER = "other"


class StageGroup(_Reply):
    """One task group of the change: the work of one implementation step. A group changes at
    least one file. `creates` lists the paths of `changes` that the step makes.

    The `kind` sets the tasks. A `behavior` group has a `test` and a `verify` that runs it, and
    changes a path under `src/`. An `other` group has no `test`, and one of `verify` (a command
    that gives the same answer on each run) and `process` (the steps of a manual check).
    `documentation` is None when the group changes no document."""

    title: Text
    kind: GroupKind
    reads: list[RepositoryPath] = Field(default_factory=list)
    changes: list[RepositoryPath] = Field(min_length=1)
    creates: list[RepositoryPath] = Field(default_factory=list)
    test: Sentence | None = None
    implementation: Sentence
    documentation: Sentence | None = None
    verify: Text | None = None
    process: Process | None = None

    @model_validator(mode="after")
    def _creates_are_changes(self) -> Self:
        for path in self.creates:
            if path not in self.changes:
                raise ValueError(MESSAGES.roadmap.stage_bad_creates.format(path=path))
        return self

    @model_validator(mode="after")
    def _kind_rules(self) -> Self:
        problems = (
            _behavior_problems(self) if self.kind is GroupKind.BEHAVIOR else _other_problems(self)
        )
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


# The keys of the plan: a reply that does not set `premise_failed` gives each of them.
_PLAN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "summary",
        "pull_request_body",
        "why",
        "what_changes",
        "skip_specs",
        "feasibility",
        "existing_tool",
        "groups",
    }
)


class StageProposal(_Reply):
    """The model's plan of the change. `summary` is the summary of the pull request title, and
    `pull_request_body` the what and why of its body. The scope and the type of the title are not
    the model's: see `staging_title`.

    A reply may instead set `premise_failed`, the evidence that the premise of the issue is false
    (#3011). It then needs no plan, and the job returns the item. A reply with no
    `premise_failed` must give every key of the plan."""

    premise_failed: str | None = None
    # The limit counts the text as the title shows it (see `_summary_fits_the_title`), so the schema
    # gives it as `maxLength` for the model and checks it in the validator, not with `max_length`.
    summary: str = Field("", min_length=1, json_schema_extra={"maxLength": STAGE_SUMMARY_MAX_CHARS})
    pull_request_body: str = Field("", min_length=1, max_length=BODY_MAX_CHARS)
    why: str = ""
    what_changes: list[str] = Field(default_factory=list, min_length=1)
    skip_specs: bool = False
    feasibility: list[str] = Field(default_factory=list, min_length=1)
    existing_tool: str = ""
    decisions: list[StageDecision] = Field(default_factory=list)
    rejected: list[StageRejection] = Field(default_factory=list)
    specs: list[StageSpec] = Field(default_factory=list)
    groups: list[StageGroup] = Field(default_factory=list, min_length=1)
    criteria: list[StageCriterion] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _evidence_alone(cls, data: Any) -> Any:
        """A reply with evidence is only the evidence: the empty keys that a model writes for the
        plan it does not give are dropped."""
        if isinstance(data, dict) and str(data.get("premise_failed") or "").strip():
            return {"premise_failed": data["premise_failed"]}
        return data

    @field_validator("summary")
    @classmethod
    def _summary_fits_the_title(cls, summary: str) -> str:
        """The title shows the summary as `safe_text` writes it: on one line, and with a code span
        for a handle or a link. The limit counts that text, so spare whitespace costs nothing and
        a handle costs its code span. The reply that breaks it goes back to the model with both
        counts, and `staging_title` cuts no summary that the schema accepts."""
        shown = len(safe_text(summary))
        if shown > STAGE_SUMMARY_MAX_CHARS:
            raise ValueError(
                MESSAGES.roadmap.stage_summary_long.format(
                    length=shown, limit=STAGE_SUMMARY_MAX_CHARS
                )
            )
        return summary

    @field_validator("premise_failed")
    @classmethod
    def _blank_is_none(cls, evidence: str | None) -> str | None:
        """A blank text means no failure, as the model writes an empty key for none."""
        return evidence.strip() or None if evidence is not None else None

    @model_validator(mode="after")
    def _plan_unless_premise_failed(self) -> Self:
        if self.premise_failed is None:
            missing = sorted(_PLAN_KEYS - self.model_fields_set)
            if missing:
                raise ValueError(
                    " ".join(
                        MESSAGES.roadmap.stage_premise_plan_missing.format(field=k) for k in missing
                    )
                )
        return self


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


def check_proposal(
    proposal: StageProposal,
    known: Collection[str],
    tree: StagedTree,
    *,
    requirements: Mapping[str, Collection[str]] | None = None,
    issue_body: str = "",
) -> list[str]:
    """What the rules of `openspec/config.yaml` and the files of the commit find wrong in
    `proposal`, one sentence each. `known` holds the names of the capabilities under
    `openspec/specs/`, `requirements` the requirement names of each base spec by capability, and
    `tree` the files that exist when the change is written. `issue_body` is the whole body of the
    issue: each acceptance criterion in it needs an entry in `criteria` (#3019), and a body with
    none needs no entry."""
    problems = _delta_problems(proposal, known, requirements or {})
    problems.extend(form_problems(proposal.groups))
    problems.extend(path_problems(proposal.groups, tree))
    problems.extend(criterion_problems(proposal.criteria, issue_body, len(proposal.groups)))
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
    return (
        f"# Proposal\n\n## Why\n\n{proposal.why.strip()}\n\n"
        f"## What Changes\n\n{_bullets(changes)}\n\n"
        f"## Capabilities\n\n{_capabilities(proposal.specs, known)}\n\n"
        f"## Impact\n\n{impact}\n\n"
        f"## Feasibility\n\n{_bullets(proposal.feasibility)}\n\n"
        f"## Existing Tool Considered\n\n{proposal.existing_tool.strip()}\n"
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
                work=group.documentation, command=_REGENERATE_DOCUMENTS
            )
        )
    return tasks


def group_text(index: int, group: StageGroup) -> str:
    """The group as `tasks.md` holds it, numbered `index`: its files, and the tasks of its kind."""
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


def _criteria_section(criteria: Sequence[StageCriterion]) -> str:
    """The `## Criteria` section of `tasks.md`: one line for each acceptance criterion with the
    group that delivers it, or `pending-person` and the reason. It is no task, so it has no box.
    A plan with no criterion has no section."""
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


def staging_title(number: int, summary: str) -> str:
    """The title of the draft pull request of item `number`: `docs(openspec): plan #<number>
    <summary>`. It is on one line, with a handle or a link in a code span, so it pings no one. The
    part after the colon has at most `SUMMARY_MAX_CHARS` characters (#2714). A summary that the
    schema accepts (`STAGE_SUMMARY_MAX_CHARS`) always fits, for a number of `ISSUE_NUMBER_DIGITS`
    digits or fewer. The title is never cut, because a cut text ends with `...` and the form check
    refuses it (#3249): a summary that does not fit stops the item with `RoadmapStageError`."""
    lead = MESSAGES.roadmap.stage_title_lead.format(number=number)
    shown = safe_text(summary)
    if len(lead) + len(shown) > SUMMARY_MAX_CHARS:
        raise RoadmapStageError(
            MESSAGES.roadmap.stage_title_long.format(
                number=number, length=len(lead) + len(shown), limit=SUMMARY_MAX_CHARS
            ),
            failed_items=[number],
        )
    return f"{_STAGING_TYPE}: {lead}{shown}"


def delivery_title(issue_title: str, declared: Collection[str]) -> str:
    """The title of the pull request that delivers the code of an item (#2714): the type and the
    scope of the issue's title, and its summary cut at a word to `SUMMARY_MAX_CHARS`. The staging
    pull request has the type `docs(openspec)`, which the delivery must not keep. A mark of a
    breaking change is dropped: the project has none before 1.0.0. A scope whose `scope/*` label is
    not in `declared` is dropped too, because the `Semantic PR title` check refuses it (#2800)."""
    head, _, summary = issue_title.partition(":")
    head = head.strip().removesuffix("!")
    scope = commit_scope(issue_title)
    if scope and f"{CONST_ROADMAP_SCOPE_LABEL_PREFIX}{scope}" not in declared:
        head = head.partition("(")[0]
    shortened = textwrap.shorten(safe_text(summary), SUMMARY_MAX_CHARS, placeholder=_ELLIPSIS)
    return f"{head}: {shortened}"


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
    folder), of the group's own text, and of the files and the rules that its step reads under
    `root`."""
    shared_tokens = sum(count_tokens(text) for text in shared)
    texts = [group_text(index, group) for index, group in enumerate(groups, start=1)]
    return [
        MeasuredGroup(group, shared_tokens + count_tokens(text) + _read_tokens(root, text))
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
