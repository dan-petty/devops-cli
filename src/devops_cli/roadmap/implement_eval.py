"""The fixtures of `devops roadmap eval implement` (#3030): real items with the properties of a good
result.

A fixture is a folder. `case.json` holds the facts: the issue, the group to run, the commit of this
repository that the run starts from, the paths of the `Changes:` line of the group, the commands
that must pass, and the recorded results of earlier runs. `issue.md` holds the body of the issue,
`plan/` holds the three files of the change that a step reads, and `results/` holds the diff of
each recorded result. A recorded result says which properties it is expected to fail, so a check
of the recorded results proves the checker (`implement_eval_properties`).

The loader reads the folder and refuses a fixture that breaks the schema or contradicts its own
plan. It reads no git: a replay in CI cannot assume the history of the pinned commit.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from devops_cli.config.constants import CONST_OPENSPEC_CHANGES_DIR
from devops_cli.exceptions.roadmap import ImplementEvalError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.step_files import TaskGroup, code_spans, parse_task_groups

CASE_FILE = "case.json"
ISSUE_FILE = "issue.md"
PLAN_DIR = "plan"
RESULTS_DIR = "results"
PLAN_FILES = ("proposal.md", "design.md", "tasks.md")
_LOST_SEPARATOR = "::"


class Property(StrEnum):
    """A property of a good result."""

    TESTS_PASS = "tests_pass"
    TESTS_KEPT = "tests_kept"
    DIFF_SCOPE = "diff_scope"
    VERIFY_PASSES = "verify_passes"
    NO_SCRATCH = "no_scratch"
    TASKS_TICKED = "tasks_ticked"


# The properties that a diff and the plan decide. The others run commands in a tree.
DIFF_PROPERTIES = (
    Property.TESTS_KEPT,
    Property.DIFF_SCOPE,
    Property.NO_SCRATCH,
    Property.TASKS_TICKED,
)
COMMAND_PROPERTIES = (Property.TESTS_PASS, Property.VERIFY_PASSES)
ALL_PROPERTIES = (*DIFF_PROPERTIES, *COMMAND_PROPERTIES)


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RecordedResult(_Strict):
    """The result of an earlier run: where it came from, its diff in `results/`, and the properties
    that the diff is expected to fail. A result that fails none is a good one."""

    name: str = Field(min_length=1)
    source: str = Field(min_length=1)
    diff: str = Field(min_length=1)
    fails: tuple[Property, ...] = ()


class ImplementCase(_Strict):
    """The facts of one fixture. `base` is a full SHA of this repository. `changes` lists the paths
    of the `Changes:` line of the group. `tests_pass` lists the commands that name the tests that
    must pass. `allow_lost_tests` lists the tests, as `path::name`, that the group may remove."""

    name: str = Field(min_length=1)
    source: str = Field(min_length=1)
    issue: int = Field(gt=0)
    title: str = Field(min_length=1)
    group: int = Field(gt=0)
    change: str = Field(min_length=1)
    base: str = Field(pattern=r"^[0-9a-f]{40}$")
    changes: tuple[str, ...] = Field(min_length=1)
    tests_pass: tuple[str, ...] = ()
    allow_lost_tests: tuple[str, ...] = ()
    results: tuple[RecordedResult, ...] = ()

    @field_validator("allow_lost_tests")
    @classmethod
    def _path_and_name(cls, entries: tuple[str, ...]) -> tuple[str, ...]:
        for entry in entries:
            path, separator, name = entry.partition(_LOST_SEPARATOR)
            if not (path and separator and name):
                raise ValueError(MESSAGES.roadmap.eval_implement_lost_form.format(entry=entry))
        return entries

    @model_validator(mode="after")
    def _only_diff_properties_fail(self) -> Self:
        for result in self.results:
            for prop in result.fails:
                if prop in COMMAND_PROPERTIES:
                    raise ValueError(
                        MESSAGES.roadmap.eval_implement_command_property.format(
                            result=result.name, prop=prop.value
                        )
                    )
        return self


@dataclass(frozen=True)
class LoadedCase:
    """A fixture with its files read: the body of the issue, the plan files by name, and the diff of
    each recorded result by the name of the result."""

    case: ImplementCase
    body: str
    plan: Mapping[str, str]
    diffs: Mapping[str, str]

    @property
    def name(self) -> str:
        return self.case.name

    @property
    def tasks_path(self) -> str:
        """The `tasks.md` of the change, from the root of the repository."""
        return f"{CONST_OPENSPEC_CHANGES_DIR}/{self.case.change}/tasks.md"

    @property
    def group(self) -> TaskGroup:
        """The group to run, from the plan. The loader has checked that the plan holds it."""
        return next(
            g for g in parse_task_groups(self.plan["tasks.md"]) if g.number == self.case.group
        )


def _read(name: str, path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ImplementEvalError(
            MESSAGES.roadmap.eval_implement_unreadable.format(name=name, file=path.name, reason=exc)
        ) from exc


def _case(name: str, folder: Path) -> ImplementCase:
    """The case of the folder, validated."""
    try:
        return ImplementCase.model_validate_json(_read(name, folder / CASE_FILE))
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors(include_url=False)
        )
        raise ImplementEvalError(
            MESSAGES.roadmap.eval_implement_invalid.format(name=name, problems=problems)
        ) from exc


def _check_plan(loaded: LoadedCase) -> None:
    """Refuse a case whose group is not in the plan, or whose `changes` the group does not name."""
    texts = MESSAGES.roadmap
    case = loaded.case
    groups = {g.number: g for g in parse_task_groups(loaded.plan["tasks.md"])}
    if case.group not in groups:
        raise ImplementEvalError(
            texts.eval_implement_no_group.format(name=case.name, group=case.group)
        )
    named = set(code_spans(groups[case.group].text))
    for path in case.changes:
        if path not in named:
            raise ImplementEvalError(
                texts.eval_implement_path_unnamed.format(
                    name=case.name, path=path, group=case.group
                )
            )


def load_case(folder: Path) -> LoadedCase:
    """The fixture in `folder`. Raises `ImplementEvalError` for a file that cannot be read, a case
    that breaks the schema, a folder name that is not the name of the case, a group that the plan
    lacks, a `changes` path that the group does not name, and a result with no diff file."""
    name = folder.name
    case = _case(name, folder)
    if case.name != name:
        raise ImplementEvalError(
            MESSAGES.roadmap.eval_implement_name.format(name=name, given=case.name)
        )
    plan = {file: _read(name, folder / PLAN_DIR / file) for file in PLAN_FILES}
    diffs: dict[str, str] = {}
    for result in case.results:
        path = folder / RESULTS_DIR / result.diff
        if not path.is_file():
            raise ImplementEvalError(
                MESSAGES.roadmap.eval_implement_diff_missing.format(
                    name=name, result=result.name, file=result.diff
                )
            )
        diffs[result.name] = _read(name, path)
    loaded = LoadedCase(case=case, body=_read(name, folder / ISSUE_FILE), plan=plan, diffs=diffs)
    _check_plan(loaded)
    return loaded


def load_cases(root: Path) -> list[LoadedCase]:
    """Every fixture under `root`, by folder name. Raises `ImplementEvalError` when `root` is no
    folder, or a fixture is refused."""
    if not root.is_dir():
        raise ImplementEvalError(MESSAGES.roadmap.eval_implement_no_fixtures.format(path=root))
    return [
        load_case(folder) for folder in sorted(root.iterdir()) if (folder / CASE_FILE).is_file()
    ]


def choose_cases(cases: list[LoadedCase], names: tuple[str, ...]) -> list[LoadedCase]:
    """The cases called `names`, in the order of `cases`, or all of them when `names` is empty.
    Raises `ImplementEvalError` for a name that no case has."""
    if not names:
        return cases
    known = [case.name for case in cases]
    unknown = [name for name in names if name not in known]
    if unknown:
        raise ImplementEvalError(
            MESSAGES.roadmap.eval_implement_unknown.format(
                names=", ".join(unknown), known=", ".join(known)
            )
        )
    return [case for case in cases if case.name in names]
