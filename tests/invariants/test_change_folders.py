"""Every active change folder under `openspec/changes/` is a plan: named `<issue>-<slug>`, with a
proposal that states its feasibility and the existing tool considered, a task list, and no field
that lives on GitHub (#1844, ADR 0010, ADR 0001).

`openspec validate --strict` passes a folder of only `.openspec.yaml` and a delta, and the
readiness check in the switch reads the folder by path alone, so without this test an empty plan
would count as a plan.

The step runs every code span of a `Verification:` line as a command. A span that it refuses stops
the plan at its group, so the tree test reads each one with the function that the step calls
(#3595, #3579).

A plan that records a test in `## Weakened checks` names it as the guard of the implement step does
(#3490): `path::Class.test_x` for a test of a class. The guard compares the names exactly, so a name
without its class waives nothing and the plan stops at the group that removes the test.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest
from markdown_it import MarkdownIt
from markdown_it.token import Token

from devops_cli.config.constants import (
    CONST_OPENSPEC_CHANGE_FOLDER_RE,
    CONST_OPENSPEC_CHANGE_NAME_RE,
    CONST_OPENSPEC_CHANGES_DIR,
)
from devops_cli.roadmap.implement.implement_shell_policy import shown, verification_problem
from devops_cli.roadmap.implement.implement_test_names import defined_tests
from devops_cli.roadmap.plan_read import PlanReadError, recorded_tests, weakened_checks
from devops_cli.roadmap.stage.stage_change import GroupKind, render_change
from devops_cli.roadmap.step_files import parse_task_groups
from tests.support.builders import make_stage_proposal
from tests.support.paths import REPO_ROOT

ARCHIVE_DIR_NAME = "archive"
PROPOSAL_HEADINGS = ("Feasibility", "Existing Tool Considered")
# The fields a change folder never carries: they live on GitHub (ADR 0001).
METADATA_FIELD_RE = re.compile(r"\*\*(?:PR|Status|Milestone|Priority)\*\*:")
TASK_GROUP_RE = re.compile(r"\d+\.\s")
TASK_ITEM_RE = re.compile(r"\[[ xX]\]\s")


def _tokens(path: Path) -> list[Token]:
    """The CommonMark tokens of the Markdown file `path`."""
    return MarkdownIt("commonmark").parse(path.read_text(encoding="utf-8"))


def _second_level_headings(tokens: list[Token]) -> list[str]:
    """The text of each `##` heading, code blocks and fences excluded."""
    return [
        tokens[index + 1].content.strip()
        for index, token in enumerate(tokens)
        if token.type == "heading_open" and token.tag == "h2"
    ]


def _task_groups_with_items(tokens: list[Token]) -> list[str]:
    """The `## <n>.` groups that hold at least one task-list item."""
    groups: dict[str, int] = {}
    current = ""
    for index, token in enumerate(tokens):
        if token.type == "heading_open" and token.tag == "h2":
            current = tokens[index + 1].content.strip()
        elif (
            token.type == "inline"
            and tokens[index - 2].type == "list_item_open"
            and TASK_ITEM_RE.match(token.content)
            and TASK_GROUP_RE.match(current)
        ):
            groups[current] = groups.get(current, 0) + 1
    return list(groups)


def _metadata_lines(tokens: list[Token]) -> list[str]:
    """The lines of prose that give a PR, Status, Milestone or Priority."""
    return [
        line
        for token in tokens
        if token.type == "inline"
        for line in token.content.splitlines()
        if METADATA_FIELD_RE.match(line)
    ]


def folder_problems(folder: Path, root: Path = REPO_ROOT) -> list[str]:
    """Why the change folder `folder` is not a plan; empty when it is. `root` is the repository that
    holds the test files which the proposal records."""
    problems = []
    if not re.fullmatch(CONST_OPENSPEC_CHANGE_NAME_RE, folder.name):
        problems.append(f"{folder.name}: not named <issue>-<slug>")
    for path in sorted(folder.rglob("*.md")):
        if _metadata_lines(_tokens(path)):
            problems.append(f"{folder.name}/{path.relative_to(folder).as_posix()}: has a field")
    return [
        *problems,
        *_proposal_problems(folder),
        *_task_problems(folder),
        *_record_problems(folder, root),
    ]


def _proposal_problems(folder: Path) -> list[str]:
    """The headings a proposal lacks, or that it has no proposal."""
    proposal = folder / "proposal.md"
    if not proposal.is_file():
        return [f"{folder.name}: no proposal.md"]
    headings = _second_level_headings(_tokens(proposal))
    return [
        f"{folder.name}/proposal.md: no ## {heading} heading"
        for heading in PROPOSAL_HEADINGS
        if heading not in headings
    ]


def _record_problems(folder: Path, root: Path) -> list[str]:
    """The tests that `## Weakened checks` records under a name that the guard does not read. The
    name `path::test_x` is wrong when `path` defines `Class.test_x` and no `test_x` of its own: the
    guard reads the class. A name that the file no longer defines at all is a removal that the
    pull request has done, and the plan stays until its last commit archives it, so it is no problem.
    A section that the reader refuses is a problem too."""
    proposal = folder / "proposal.md"
    if not proposal.is_file():
        return []
    try:
        recorded = recorded_tests(weakened_checks(proposal.read_text(encoding="utf-8")))
    except PlanReadError as refused:
        return [f"{folder.name}/proposal.md: {refused.reason}"]
    problems = []
    for entry in sorted(recorded):
        path, _, name = entry.partition("::")
        file = root / path
        defined = defined_tests(file.read_text(encoding="utf-8")) if file.is_file() else None
        if not defined or name in defined:
            continue
        near = sorted(
            test for test in defined if test.rsplit(".", 1)[-1] == name.rsplit(".", 1)[-1]
        )
        if near:
            problems.append(
                f"{folder.name}/proposal.md: records {entry}, and the file defines {', '.join(near)}"
            )
    return problems


def _task_problems(folder: Path) -> list[str]:
    """Why `tasks.md` is no task list, or that there is none."""
    tasks = folder / "tasks.md"
    if not tasks.is_file():
        return [f"{folder.name}: no tasks.md"]
    if not _task_groups_with_items(_tokens(tasks)):
        return [f"{folder.name}/tasks.md: no ## <n>. group with a task-list item"]
    return []


def tree_problems(changes_dir: Path, root: Path = REPO_ROOT) -> list[str]:
    """Why the active changes under `changes_dir` are not plans, and any stray entry there. `root`
    is the repository that holds the test files which the proposals record."""
    entries = sorted(changes_dir.iterdir()) if changes_dir.is_dir() else []
    problems = [
        f"{entry.name}: not a change folder or {ARCHIVE_DIR_NAME}/"
        for entry in entries
        if not entry.is_dir() and entry.name != ARCHIVE_DIR_NAME
    ]
    for entry in entries:
        if entry.is_dir() and entry.name != ARCHIVE_DIR_NAME:
            problems.extend(folder_problems(entry, root))
    return problems


def test_every_active_change_folder_is_a_plan() -> None:
    """The repository's own change folders pass, as does a tree with none."""
    assert tree_problems(REPO_ROOT / CONST_OPENSPEC_CHANGES_DIR) == []


_VERIFICATION_LINE = "- Verification:"
_COMMAND_SHOWN_CHARS = 300


def _line_of(lines: list[str], task_line: int, command: str) -> int:
    """The one-based line of the `Verification:` line that holds the code span `command` in the task
    that starts at the zero-based `task_line`. It is the line of the task when none holds it."""
    span = f"`{command}`"
    for number in range(max(task_line, 0), len(lines)):
        stripped = lines[number].lstrip()
        if stripped.startswith(_VERIFICATION_LINE) and span in stripped:
            return number + 1
    return task_line + 1


def _plan_verification_problems(folder: Path) -> list[str]:
    """Each refused code span of a `Verification:` line in the `tasks.md` of `folder`."""
    text = (folder / "tasks.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    refused = [
        (task.line, command, reason)
        for group in parse_task_groups(text)
        for task in group.tasks
        for command in task.verification
        if (reason := verification_problem(command)) is not None
    ]
    return [
        f"{folder.name}/tasks.md:{_line_of(lines, line, command)}: "
        f"`{shown(command, _COMMAND_SHOWN_CHARS)}` is refused: {reason}"
        for line, command, reason in refused
    ]


def verification_problems(changes_dir: Path) -> list[str]:
    """Each code span of a `Verification:` line, in the `tasks.md` of an active change under
    `changes_dir`, that the implement step refuses, with the path, the line and the reason. The spans
    come from `parse_task_groups` and the refusals from `read_verification`, the functions that the
    step calls, so this holds no copy of the grammar. `archive/` is not read."""
    entries = sorted(changes_dir.iterdir()) if changes_dir.is_dir() else []
    return [
        problem
        for folder in entries
        if folder.is_dir() and folder.name != ARCHIVE_DIR_NAME and (folder / "tasks.md").is_file()
        for problem in _plan_verification_problems(folder)
    ]


def test_every_verification_line_of_an_active_plan_is_accepted_by_the_step() -> None:
    """The step runs every code span of a `Verification:` line. A plan with a refused span stops at
    its group, so no active plan holds one."""
    assert verification_problems(REPO_ROOT / CONST_OPENSPEC_CHANGES_DIR) == []


PROPOSAL = (
    "## Why\n\nIssue #1900.\n\n## What Changes\n\nThe export.\n\n"
    "## Feasibility\n\nChecked.\n\n## Existing Tool Considered\n\nNone covers it.\n"
)
TASKS = "## 1. Export\n\n- [x] 1.1 Write the file\n- [ ] 1.2 Document it\n"


def _folder(
    tmp_path: Path,
    name: str = "1900-widget-export",
    *,
    proposal: str = PROPOSAL,
    tasks: str = TASKS,
    extra: dict[str, str] | None = None,
) -> Path:
    """A change folder named `name` holding `proposal` and `tasks`, a file left out when its text
    is empty, and the files of `extra` by path from the folder."""
    folder = tmp_path / "changes" / name
    folder.mkdir(parents=True)
    files = {".openspec.yaml": "schema: spec-driven\n", "proposal.md": proposal, "tasks.md": tasks}
    for path, text in {**files, **(extra or {})}.items():
        if text:
            (folder / path).parent.mkdir(parents=True, exist_ok=True)
            (folder / path).write_text(text, encoding="utf-8")
    return folder


def test_a_folder_with_a_proposal_and_a_task_list_is_a_plan(tmp_path: Path) -> None:
    """A valid folder, with a task ticked and one not, passes."""
    assert folder_problems(_folder(tmp_path)) == []


@pytest.mark.parametrize(
    ("name", "files", "problems"),
    [
        ("widget-export", {}, ["widget-export: not named <issue>-<slug>"]),
        ("1900", {}, ["1900: not named <issue>-<slug>"]),
        ("1900-widget-export", {"tasks": ""}, ["1900-widget-export: no tasks.md"]),
        ("1900-widget-export", {"proposal": ""}, ["1900-widget-export: no proposal.md"]),
        (
            "1900-widget-export",
            {"tasks": "## Tasks\n\n- [ ] Write the file\n"},
            ["1900-widget-export/tasks.md: no ## <n>. group with a task-list item"],
        ),
        (
            "1900-widget-export",
            {"tasks": "## 1. Export\n\nWrite the file.\n"},
            ["1900-widget-export/tasks.md: no ## <n>. group with a task-list item"],
        ),
        (
            "1900-widget-export",
            {"tasks": "```markdown\n## 1. Export\n\n- [ ] Write the file\n```\n"},
            ["1900-widget-export/tasks.md: no ## <n>. group with a task-list item"],
        ),
        (
            "1900-widget-export",
            {"proposal": PROPOSAL.replace("## Existing Tool Considered", "### Existing Tool")},
            ["1900-widget-export/proposal.md: no ## Existing Tool Considered heading"],
        ),
        (
            "1900-widget-export",
            {"proposal": PROPOSAL.replace("## Feasibility", "# Feasibility")},
            ["1900-widget-export/proposal.md: no ## Feasibility heading"],
        ),
        (
            "1900-widget-export",
            {"proposal": PROPOSAL + "\n**Status**: In Progress\n"},
            ["1900-widget-export/proposal.md: has a field"],
        ),
        (
            "1900-widget-export",
            {"tasks": TASKS + "\n**Milestone**: 2026-11\n"},
            ["1900-widget-export/tasks.md: has a field"],
        ),
    ],
    ids=[
        "no-issue",
        "no-slug",
        "no-tasks-file",
        "no-proposal",
        "no-numbered-group",
        "group-without-an-item",
        "group-inside-a-fence",
        "existing-tool-heading-is-not-level-2",
        "feasibility-heading-is-not-level-2",
        "status-line",
        "milestone-line",
    ],
)
def test_a_folder_that_is_not_a_plan_is_reported(
    tmp_path: Path, name: str, files: dict[str, str], problems: list[str]
) -> None:
    """Each way a folder can pass `openspec validate --strict` and still be no plan."""
    assert folder_problems(_folder(tmp_path, name, **files)) == problems


def test_a_metadata_line_shown_in_a_code_fence_is_prose_about_it_not_a_field(
    tmp_path: Path,
) -> None:
    """A proposal may show `**Status**: Done` as an example of what a task file once carried."""
    example = PROPOSAL + "\nA task file once had:\n\n```markdown\n**Status**: Done\n```\n"

    assert folder_problems(_folder(tmp_path, proposal=example)) == []


def test_a_stray_file_or_folder_in_the_changes_directory_is_reported(tmp_path: Path) -> None:
    """Only change folders and `archive/` sit in `openspec/changes/`."""
    _folder(tmp_path)
    changes = tmp_path / "changes"
    (changes / "archive").mkdir()
    (changes / "notes.md").write_text("Notes.\n", encoding="utf-8")
    (changes / "scratch").mkdir()

    assert tree_problems(changes) == [
        "notes.md: not a change folder or archive/",
        "scratch: not named <issue>-<slug>",
        "scratch: no proposal.md",
        "scratch: no tasks.md",
    ]


def test_a_file_in_a_change_folder_is_matched_by_the_folder_grammar(tmp_path: Path) -> None:
    """The closed grammar readiness will read the folder with matches every file of a plan,
    however deep, and no file outside a folder named for an issue."""
    folder = _folder(tmp_path, extra={"specs/widget/spec.md": "## ADDED Requirements\n"})
    paths = [
        f"{CONST_OPENSPEC_CHANGES_DIR}/{path.relative_to(folder.parent).as_posix()}"
        for path in folder.rglob("*")
        if path.is_file()
    ]
    assert (
        sorted(path for path in paths if re.fullmatch(CONST_OPENSPEC_CHANGE_FOLDER_RE, path)),
        re.fullmatch(CONST_OPENSPEC_CHANGE_FOLDER_RE, "openspec/changes/archive/2026-10-22-1-a/x"),
        re.fullmatch(CONST_OPENSPEC_CHANGE_FOLDER_RE, "openspec/changes/1900-widget/"),
    ) == (sorted(paths), None, None)


def test_the_tasks_of_a_stage_group_of_each_kind_make_a_plan(tmp_path: Path) -> None:
    """The stage job writes a `tasks.md` that passes, also for groups with no test task (#3005)."""
    behavior = make_stage_proposal().groups[0]
    other = behavior.model_copy(
        update={
            "kind": GroupKind.OTHER,
            "test": None,
            "documentation": None,
            "creates": [],
            "creates_lines": {},
        }
    )
    process = other.model_copy(update={"verify": None, "process": "Read the report."})
    proposal = make_stage_proposal(groups=[behavior, other, process])
    root = "openspec/changes/1900-widget-export"
    files = render_change("1900-widget-export", proposal, [], created=date(2026, 11, 1))

    folder = _folder(tmp_path, tasks=files[f"{root}/tasks.md"])

    assert folder_problems(folder) == []


SECTION = (
    "\n## Weakened checks\n\n- **`{entry}`**: Stopped: an old form. Safeguard: `test_b` holds it.\n"
)
CLASS_TESTS = "class TestSample:\n    def test_a(self) -> None: ...\n"


def _repo_with_tests(tmp_path: Path, text: str) -> Path:
    """A repository root with the test file `tests/test_sample.py` that holds `text`."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_sample.py").write_text(text, encoding="utf-8")
    return tmp_path


def _records(tmp_path: Path, entry: str) -> Path:
    return _folder(tmp_path, proposal=PROPOSAL + SECTION.format(entry=entry))


def test_a_test_of_a_class_that_a_plan_records_by_its_qualified_name_passes(
    tmp_path: Path,
) -> None:
    root = _repo_with_tests(tmp_path, CLASS_TESTS)
    folder = _records(tmp_path, "tests/test_sample.py::TestSample.test_a")

    assert folder_problems(folder, root) == []


def test_a_test_of_a_class_that_a_plan_records_with_no_class_is_reported(tmp_path: Path) -> None:
    """The guard reads `TestSample.test_a`, so the entry `test_a` would waive nothing."""
    root = _repo_with_tests(tmp_path, CLASS_TESTS)
    folder = _records(tmp_path, "tests/test_sample.py::test_a")

    assert folder_problems(folder, root) == [
        "1900-widget-export/proposal.md: records tests/test_sample.py::test_a, "
        "and the file defines TestSample.test_a"
    ]


def test_a_test_that_a_plan_records_under_another_class_is_reported(tmp_path: Path) -> None:
    root = _repo_with_tests(tmp_path, CLASS_TESTS)
    folder = _records(tmp_path, "tests/test_sample.py::TestOther.test_a")

    assert folder_problems(folder, root) == [
        "1900-widget-export/proposal.md: records tests/test_sample.py::TestOther.test_a, "
        "and the file defines TestSample.test_a"
    ]


def test_a_module_level_test_that_a_plan_records_passes(tmp_path: Path) -> None:
    root = _repo_with_tests(tmp_path, "def test_a() -> None: ...\n")
    folder = _records(tmp_path, "tests/test_sample.py::test_a")

    assert folder_problems(folder, root) == []


@pytest.mark.parametrize(
    "text",
    [None, "def test_b() -> None: ...\n", "def test_a(:\n"],
    ids=["no-file", "gone", "syntax"],
)
def test_a_record_of_a_test_that_the_file_no_longer_defines_is_no_problem(
    tmp_path: Path, text: str | None
) -> None:
    """The pull request that removes the test leaves the plan in place until it archives it."""
    root = tmp_path if text is None else _repo_with_tests(tmp_path, text)
    folder = _records(tmp_path, "tests/test_sample.py::TestSample.test_a")

    assert folder_problems(folder, root) == []


def test_a_section_that_the_reader_refuses_is_reported(tmp_path: Path) -> None:
    folder = _folder(tmp_path, proposal=PROPOSAL + "\n## Weakened checks\n\nThe test goes.\n")

    assert folder_problems(folder, tmp_path) == [
        "1900-widget-export/proposal.md: `proposal.md` holds a line in `## Weakened checks` that "
        "is no entry: The test goes.. The form is "
        "`- **<check>**: Stopped: <stopped> Safeguard: <safeguard>`."
    ]


def _plan(tmp_path: Path, name: str, verification: str) -> Path:
    """The plan `name` under `tmp_path/changes`, whose one task has the `Verification:` line
    `verification`. It returns the changes directory."""
    tasks = f"## 1. Export\n\n- [ ] 1.1 Write the file\n  - Verification: {verification}\n"
    return _folder(tmp_path, name, tasks=tasks).parent


def test_a_verification_command_that_the_step_accepts_is_no_problem(tmp_path: Path) -> None:
    changes = _plan(
        tmp_path, "1900-widget-export", "`uv run devops ci test tests/test_widget.py` passes"
    )

    assert verification_problems(changes) == []


def test_a_negative_search_with_word_boundaries_is_reported_with_path_line_and_command(
    tmp_path: Path,
) -> None:
    """The grammar of the negative search has no `-E`, so the step refuses the line."""
    changes = _plan(tmp_path, "1900-widget-export", r"`! git grep -n -E '\bfoo\b' src/`")

    [problem] = verification_problems(changes)

    assert problem.startswith("1900-widget-export/tasks.md:4: `! git grep -n -E '")
    assert "bfoo" in problem
    assert "is refused: the option `-E` is not allowed" in problem


def test_a_prose_code_span_in_a_verification_line_is_reported(tmp_path: Path) -> None:
    changes = _plan(tmp_path, "1900-widget-export", "`the log is empty`")

    [problem] = verification_problems(changes)

    assert problem.startswith("1900-widget-export/tasks.md:4: `the log is empty` is refused: ")


def test_each_span_of_a_verification_line_is_read_not_only_the_first(tmp_path: Path) -> None:
    changes = _plan(
        tmp_path,
        "1900-widget-export",
        "`uv run devops ci test tests/test_widget.py` passes, and `test -z x` holds",
    )

    [problem] = verification_problems(changes)

    assert problem.startswith("1900-widget-export/tasks.md:4: `test -z x` is refused: ")


def test_the_line_of_a_problem_is_the_verification_line_of_its_own_task(tmp_path: Path) -> None:
    tasks = (
        "## 1. Export\n\n"
        "- [ ] 1.1 Write the file\n  - Verification: `uv run devops ci docs` passes\n"
        "- [ ] 1.2 Document it\n  - Verification: `docker buildx` passes\n"
    )
    changes = _folder(tmp_path, tasks=tasks).parent

    [problem] = verification_problems(changes)

    assert problem.startswith("1900-widget-export/tasks.md:6: `docker buildx` is refused: ")


def test_a_plan_under_the_archive_directory_is_not_read(tmp_path: Path) -> None:
    changes = _plan(tmp_path, "1900-widget-export", "`uv run devops ci docs` passes")
    archived = changes / ARCHIVE_DIR_NAME / "2026-11-01-1901-old-plan"
    archived.mkdir(parents=True)
    (archived / "tasks.md").write_text(
        "## 1. Old\n\n- [x] 1.1 Done\n  - Verification: `docker buildx` passes\n", encoding="utf-8"
    )

    assert verification_problems(changes) == []


def test_every_active_plan_is_read(tmp_path: Path) -> None:
    _plan(tmp_path, "1900-widget-export", "`docker buildx` passes")
    changes = _plan(tmp_path, "1901-widget-import", "`test -d src` passes")

    assert [problem.split(":")[0] for problem in verification_problems(changes)] == [
        "1900-widget-export/tasks.md",
        "1901-widget-import/tasks.md",
    ]


def test_a_changes_directory_that_does_not_exist_has_no_problem(tmp_path: Path) -> None:
    assert verification_problems(tmp_path / "missing") == []
