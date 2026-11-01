"""Every active change folder under `openspec/changes/` is a plan: named `<issue>-<slug>`, with a
proposal that states its feasibility and the existing tool considered, a task list, and no field
that lives on GitHub (#1844, ADR 0010, ADR 0001).

`openspec validate --strict` passes a folder of only `.openspec.yaml` and a delta, and the
readiness check in the switch reads the folder by path alone, so without this test an empty plan
would count as a plan.
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
from devops_cli.roadmap.stage_change import GroupKind, render_change
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


def folder_problems(folder: Path) -> list[str]:
    """Why the change folder `folder` is not a plan; empty when it is."""
    problems = []
    if not re.fullmatch(CONST_OPENSPEC_CHANGE_NAME_RE, folder.name):
        problems.append(f"{folder.name}: not named <issue>-<slug>")
    for path in sorted(folder.rglob("*.md")):
        if _metadata_lines(_tokens(path)):
            problems.append(f"{folder.name}/{path.relative_to(folder).as_posix()}: has a field")
    return [*problems, *_proposal_problems(folder), *_task_problems(folder)]


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


def _task_problems(folder: Path) -> list[str]:
    """Why `tasks.md` is no task list, or that there is none."""
    tasks = folder / "tasks.md"
    if not tasks.is_file():
        return [f"{folder.name}: no tasks.md"]
    if not _task_groups_with_items(_tokens(tasks)):
        return [f"{folder.name}/tasks.md: no ## <n>. group with a task-list item"]
    return []


def tree_problems(changes_dir: Path) -> list[str]:
    """Why the active changes under `changes_dir` are not plans, and any stray entry there."""
    entries = sorted(changes_dir.iterdir()) if changes_dir.is_dir() else []
    problems = [
        f"{entry.name}: not a change folder or {ARCHIVE_DIR_NAME}/"
        for entry in entries
        if not entry.is_dir() and entry.name != ARCHIVE_DIR_NAME
    ]
    for entry in entries:
        if entry.is_dir() and entry.name != ARCHIVE_DIR_NAME:
            problems.extend(folder_problems(entry))
    return problems


def test_every_active_change_folder_is_a_plan() -> None:
    """The repository's own change folders pass, as does a tree with none."""
    assert tree_problems(REPO_ROOT / CONST_OPENSPEC_CHANGES_DIR) == []


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
        update={"kind": GroupKind.OTHER, "test": None, "documentation": None, "creates": []}
    )
    process = other.model_copy(update={"verify": None, "process": "Read the report."})
    proposal = make_stage_proposal(groups=[behavior, other, process])
    root = "openspec/changes/1900-widget-export"
    files = render_change("1900-widget-export", proposal, [], created=date(2026, 11, 1))

    folder = _folder(tmp_path, tasks=files[f"{root}/tasks.md"])

    assert folder_problems(folder) == []
