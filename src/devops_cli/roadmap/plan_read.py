"""The plan reader (#3201): the change folder that the stage job wrote, read back as a
`StageProposal`.

`render_change` writes `proposal.md`, `design.md`, `tasks.md`, `.openspec.yaml` and one spec delta
for each capability. `read_change` reverses that writer, so that the gates read a plan pull request
with the same inputs as the reply of the model. The reader refuses a file that it cannot parse with
`PlanReadError`, and the plan check reports that file and goes on.

The writer drops a few facts that no file holds: the kind of a task group, the estimated lines of a
file that a group creates, and whether the plan builds its own code. The reader infers the kind
from the tasks, gives each created path one estimated line, and sets `builds_own` to false.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from pydantic import ValidationError

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement_shell_policy import shown, verification_problem
from devops_cli.roadmap.stage_change import (
    REGENERATE_DOCUMENTS,
    GroupKind,
    StageDecision,
    StageGroup,
    StageProposal,
    StageRejection,
    StageRequirement,
    StageScenario,
    StageSpec,
)
from devops_cli.roadmap.stage_criteria import StageCriterion
from devops_cli.roadmap.step_files import FAILS_ON_BASE, KIND_LINE, TaskGroup, parse_task_groups

_CHANGE_FILE: Final[str] = "/.openspec.yaml"
_PROPOSAL: Final[str] = "proposal.md"
_DESIGN: Final[str] = "design.md"
_TASKS: Final[str] = "tasks.md"
_SPEC: Final[re.Pattern[str]] = re.compile(r"^(?P<root>.*)/specs/(?P<capability>[^/]+)/spec\.md$")
_HEADING: Final[re.Pattern[str]] = re.compile(r"^## (?P<title>.+?)[ \t]*$", re.M)
_REQUIREMENT: Final[re.Pattern[str]] = re.compile(r"^### Requirement: (?P<name>.+?)[ \t]*$", re.M)
_SCENARIO: Final[re.Pattern[str]] = re.compile(r"^#### Scenario: (?P<name>.+?)[ \t]*$", re.M)
_WHEN: Final[re.Pattern[str]] = re.compile(r"^- \*\*WHEN\*\* (?P<text>.+?)[ \t]*$", re.M)
_THEN: Final[re.Pattern[str]] = re.compile(r"^- \*\*THEN\*\* (?P<text>.+?)[ \t]*$", re.M)
_TASK_LINE: Final[re.Pattern[str]] = re.compile(r"^\[[ xX]\] (?P<number>\d+\.\d+) (?P<text>.*)$")
_INLINE_VERIFY: Final[re.Pattern[str]] = re.compile(
    r"(?:,\s*and\s+)?[Vv]erify that `(?P<command>[^`]+)` (?P<suffix>fails on the base|passes)\s*$"
)
_READS: Final[re.Pattern[str]] = re.compile(
    r"Reads: (?P<reads>.*?)\. Changes: (?P<changes>.*)\.$", re.M
)
_CODE_SPAN: Final[re.Pattern[str]] = re.compile(r"`(?P<text>[^`]+)`")
_NEW_MARK: Final[str] = MESSAGES.roadmap.stage_group_new
_PROCESS_MARK: Final[str] = MESSAGES.roadmap.stage_task_process.format(work="", process="").split(
    "{"
)[0]
_DOCUMENTS_MARK: Final[str] = MESSAGES.roadmap.stage_task_regenerate.format(
    command=REGENERATE_DOCUMENTS
)
_CRITERIA_TITLE: Final[str] = MESSAGES.roadmap.stage_criteria_title
_PENDING_PREFIX: Final[str] = "Pending person: "


class PlanReadError(ValueError):
    """A file of a change folder that the plan reader cannot parse."""

    def __init__(self, path: str, reason: str) -> None:
        super().__init__(reason)
        self.path = path
        self.reason = reason


@dataclass(frozen=True)
class _GroupFiles:
    reads: list[str]
    changes: list[str]
    creates: list[str]


def _section(text: str, title: str) -> str:
    """The body of the `## <title>` section, up to the next `##` heading."""
    heading = re.search(rf"^## {re.escape(title)}[ \t]*$", text, re.M)
    if heading is None:
        return ""
    following = _HEADING.search(text, heading.end())
    end = following.start() if following is not None else len(text)
    return text[heading.end() : end].strip()


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _bullets(text: str) -> list[str]:
    return [line[2:].strip() for line in text.splitlines() if line.startswith("- ")]


def _named_bullets(text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for line in _bullets(text):
        if line.startswith("**") and "**: " in line:
            name, _, reason = line.partition("**: ")
            found.append((name.removeprefix("**").strip(), reason.strip()))
        elif ": " in line:
            name, _, reason = line.partition(": ")
            found.append((name.strip(), reason.strip()))
    return found


def _header(files: Mapping[str, str]) -> str:
    roots = {path[: -len(_CHANGE_FILE)] for path in files if path.endswith(_CHANGE_FILE)}
    if len(roots) != 1:
        reason = MESSAGES.roadmap.plan_read_missing_file.format(name=_CHANGE_FILE)
        raise PlanReadError(_CHANGE_FILE, reason)
    root = roots.pop()
    for name in (_PROPOSAL, _DESIGN, _TASKS):
        path = f"{root}/{name}"
        if path not in files:
            reason = MESSAGES.roadmap.plan_read_missing_file.format(name=name)
            raise PlanReadError(path, reason)
    return root


def _skip_specs(text: str) -> bool:
    return any(line.strip() == "skip_specs: true" for line in text.splitlines())


def _requirement_block(path: str, name: str, body: str) -> StageRequirement:
    scenarios: list[StageScenario] = []
    for match in _SCENARIO.finditer(body):
        following = _SCENARIO.search(body, match.end())
        end = following.start() if following is not None else len(body)
        block = body[match.end() : end]
        when = _WHEN.search(block)
        then = _THEN.search(block)
        if when is None or then is None:
            raise PlanReadError(path, MESSAGES.roadmap.plan_read_bad_requirement.format(path=path))
        scenarios.append(
            StageScenario(
                name=match["name"].strip(), when=when["text"].strip(), then=then["text"].strip()
            )
        )
    if not scenarios:
        raise PlanReadError(path, MESSAGES.roadmap.plan_read_bad_requirement.format(path=path))
    statement = _SCENARIO.split(body, maxsplit=1)[0]
    return StageRequirement(name=name, text=_one_line(statement), scenarios=scenarios)


def _requirements(text: str, path: str) -> list[StageRequirement]:
    found: list[StageRequirement] = []
    matches = list(_REQUIREMENT.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        found.append(_requirement_block(path, match["name"].strip(), text[match.end() : end]))
    return found


def _spec(path: str, text: str) -> StageSpec:
    match = _SPEC.match(path)
    if match is None:
        raise PlanReadError(path, MESSAGES.roadmap.plan_read_bad_spec.format(path=path))
    purpose = _section(text, "Purpose")
    return StageSpec(
        capability=match["capability"],
        purpose=_one_line(purpose) or None,
        added=_requirements(_section(text, "ADDED Requirements"), path),
        modified=_requirements(_section(text, "MODIFIED Requirements"), path),
    )


def _proposal(text: str) -> tuple[str, list[str], list[str], str]:
    why = _section(text, "Why")
    if not why:
        raise PlanReadError(_PROPOSAL, MESSAGES.roadmap.plan_read_bad_proposal)
    what_changes = [
        line
        for line in _bullets(_section(text, "What Changes"))
        if line != MESSAGES.roadmap.stage_fits_one_pr
    ]
    feasibility = _bullets(_section(text, "Feasibility"))
    existing_tool = _section(text, "Existing Tool Considered")
    return _one_line(why), what_changes, feasibility, _one_line(existing_tool)


def _design(text: str) -> tuple[list[StageDecision], list[StageRejection]]:
    decisions = [
        StageDecision(decision=name, reason=reason)
        for name, reason in _named_bullets(_section(text, "Decisions"))
    ]
    rejected = [
        StageRejection(alternative=name, evidence=reason)
        for name, reason in _named_bullets(_section(text, "Rejected alternatives"))
    ]
    return decisions, rejected


def _spans(text: str) -> list[tuple[str, str]]:
    return [
        (match["text"], text[match.end() : match.end() + len(_NEW_MARK)])
        for match in _CODE_SPAN.finditer(text)
    ]


def created_paths(tasks_md: str) -> list[str]:
    """The paths that the groups of `tasks_md` mark `(new)`, each once, in file order. It reads the
    marks in the text of each group, so it names the files of a plan whose layout `read_change`
    refuses (#3492)."""
    found = (
        path
        for group in parse_task_groups(tasks_md)
        for path, mark in _spans(group.text)
        if mark.startswith(_NEW_MARK)
    )
    return list(dict.fromkeys(found))


def _group_files(text: str) -> _GroupFiles:
    match = _READS.search(text)
    if match is None:
        raise PlanReadError(_TASKS, MESSAGES.roadmap.plan_read_bad_tasks)
    reads = (
        []
        if match["reads"].strip() == MESSAGES.roadmap.stage_group_no_reads
        else [text for text, mark in _spans(match["reads"]) if not mark.startswith(_NEW_MARK)]
    )
    changes: list[str] = []
    creates: list[str] = []
    for path, mark in _spans(match["changes"]):
        changes.append(path)
        if mark.startswith(_NEW_MARK):
            creates.append(path)
    return _GroupFiles(reads=reads, changes=changes, creates=creates)


def _task_texts(group: TaskGroup) -> list[str]:
    found: list[str] = []
    for task in group.tasks:
        match = _TASK_LINE.match(task.text)
        if match is None:
            raise PlanReadError(_TASKS, MESSAGES.roadmap.plan_read_bad_task.format(text=task.text))
        found.append(match["text"].strip())
    return found


def _verification_suffixes(text: str) -> list[str]:
    return [
        line.split("`", 2)[-1].strip()
        for line in text.splitlines()
        if line.strip().startswith("- Verification:")
    ]


def _split_process(text: str) -> tuple[str, str | None]:
    if _PROCESS_MARK and _PROCESS_MARK in text:
        work, _, process = text.partition(_PROCESS_MARK)
        return work.strip(), process.strip()
    return text.strip(), None


def _split_documents(text: str) -> tuple[str, str | None]:
    if _DOCUMENTS_MARK and _DOCUMENTS_MARK in text:
        work, _, _ = text.partition(_DOCUMENTS_MARK)
        return work.strip(), _DOCUMENTS_MARK
    return text.strip(), None


@dataclass(frozen=True)
class _Task:
    text: str
    verification: str | None
    suffix: str | None


def _task(group: TaskGroup, index: int) -> _Task:
    text = _task_texts(group)[index]
    suffixes = _verification_suffixes(group.text)
    task = group.tasks[index]
    if task.verification:
        return _Task(
            text=text,
            verification=task.verification[0],
            suffix=suffixes[index] if index < len(suffixes) else None,
        )
    match = _INLINE_VERIFY.search(text)
    if match is None:
        return _Task(text=text, verification=None, suffix=None)
    return _Task(
        text=text[: match.start()].strip(),
        verification=match["command"].strip(),
        suffix=match["suffix"].strip(),
    )


def _kind(text: str, first: _Task) -> GroupKind:
    found = KIND_LINE.search(text)
    if found is not None and found["kind"] == GroupKind.BEHAVIOR.value:
        return GroupKind.BEHAVIOR
    return GroupKind.BEHAVIOR if first.suffix == FAILS_ON_BASE else GroupKind.OTHER


def _verification_problems(group: TaskGroup, first: _Task) -> list[str]:
    """The reason for each verification command of `group` that the step cannot run. The step runs
    every code span of every `Verification:` line (`step_files`), so the reader judges all of
    them, and not the one command that the plan record keeps."""
    commands = dict.fromkeys(
        [*group.verification_commands, *([first.verification] if first.verification else [])]
    )
    return [
        MESSAGES.roadmap.plan_read_bad_verification.format(
            group=group.number, command=shown(command), reason=reason
        )
        for command in commands
        if (reason := verification_problem(command)) is not None
    ]


def _group(group: TaskGroup) -> StageGroup:
    files = _group_files(group.text)
    if not group.tasks:
        raise PlanReadError(_TASKS, MESSAGES.roadmap.plan_read_bad_task.format(text=group.title))
    first = _task(group, 0)
    if not first.text:
        raise PlanReadError(_TASKS, MESSAGES.roadmap.plan_read_bad_task.format(text=first.text))
    if problems := _verification_problems(group, first):
        raise PlanReadError(_TASKS, " ".join(problems))
    if _kind(group.text, first) is GroupKind.BEHAVIOR:
        if len(group.tasks) < 2:
            raise PlanReadError(_TASKS, MESSAGES.roadmap.plan_read_bad_task.format(text=first.text))
        second = _task(group, 1)
        implementation, documentation = _split_documents(second.text)
        if len(group.tasks) > 2:
            documentation, _ = _split_documents(_task(group, 2).text)
        return StageGroup(
            title=group.title,
            kind=GroupKind.BEHAVIOR,
            reads=files.reads,
            changes=files.changes,
            creates=files.creates,
            creates_lines={path: 1 for path in files.creates},
            test=first.text,
            implementation=implementation,
            documentation=documentation,
            verify=first.verification,
        )
    implementation, process = _split_process(first.text)
    other_documentation: str | None = None
    if len(group.tasks) > 1:
        other_documentation, _ = _split_documents(_task(group, 1).text)
    return StageGroup(
        title=group.title,
        kind=GroupKind.OTHER,
        reads=files.reads,
        changes=files.changes,
        creates=files.creates,
        creates_lines={path: 1 for path in files.creates},
        implementation=implementation,
        documentation=other_documentation,
        verify=first.verification,
        process=process,
    )


def _criteria(text: str) -> list[StageCriterion]:
    section = _section(text, _CRITERIA_TITLE)
    found: list[StageCriterion] = []
    for line in _bullets(section):
        if line.startswith(_PENDING_PREFIX):
            criterion, _, reason = line.removeprefix(_PENDING_PREFIX).partition(", ")
            if not criterion or not reason:
                raise PlanReadError(
                    _TASKS, MESSAGES.roadmap.plan_read_bad_criterion.format(text=line)
                )
            found.append(
                StageCriterion(
                    criterion=criterion.strip(), group="pending-person", reason=reason.strip()
                )
            )
            continue
        group, separator, criterion = line.partition(": ")
        if (
            not separator
            or not group.startswith("Group ")
            or not group.removeprefix("Group ").isdigit()
        ):
            raise PlanReadError(_TASKS, MESSAGES.roadmap.plan_read_bad_criterion.format(text=line))
        found.append(
            StageCriterion(criterion=criterion.strip(), group=int(group.removeprefix("Group ")))
        )
    return found


def _reasons(exc: ValidationError) -> str:
    """The problems of a pydantic error as one line of text, with no trace and no link."""
    return " ".join(
        ".".join(str(part) for part in error["loc"]) + f": {error['msg']}"
        if error["loc"]
        else str(error["msg"])
        for error in exc.errors(include_url=False)
    )


def _read_group(group: TaskGroup) -> StageGroup:
    """The `StageGroup` of `group`. A group that the model refuses raises `PlanReadError`."""
    try:
        return _group(group)
    except ValidationError as exc:
        reason = MESSAGES.roadmap.plan_read_bad_group.format(
            title=group.title, reason=_reasons(exc)
        )
        raise PlanReadError(_TASKS, reason) from exc


def read_change(files: Mapping[str, str]) -> StageProposal:
    """The `StageProposal` that the change folder in `files` holds, by path from the repository
    root. A file that the reader cannot parse raises `PlanReadError` that names it, and no other
    error leaves the reader for a plan that is wrong in form."""
    root = _header(files)
    why, what_changes, feasibility, existing_tool = _proposal(files[f"{root}/{_PROPOSAL}"])
    decisions, rejected = _design(files[f"{root}/{_DESIGN}"])
    groups = [_read_group(group) for group in parse_task_groups(files[f"{root}/{_TASKS}"])]
    specs = [
        _spec(path, text)
        for path, text in sorted(files.items())
        if _SPEC.match(path) and path.startswith(f"{root}/specs/")
    ]
    criteria = _criteria(files[f"{root}/{_TASKS}"])
    try:
        return StageProposal(
            summary="Read the plan of the change folder",
            pull_request_body=why[:800],
            why=why,
            what_changes=what_changes or [why],
            skip_specs=_skip_specs(files[f"{root}{_CHANGE_FILE}"]),
            feasibility=feasibility or [why],
            existing_tool=existing_tool or why,
            decisions=decisions,
            rejected=rejected,
            specs=specs,
            groups=groups,
            criteria=criteria,
        )
    except ValidationError as exc:
        raise PlanReadError(root, _reasons(exc)) from exc
