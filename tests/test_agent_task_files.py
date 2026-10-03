"""Task files link their GitHub issue only, and tick a box only for work that is done."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

TASKS_DIR = Path("docs/agent/tasks")
TASK_FILES = sorted(TASKS_DIR.glob("task-*.md"))
STATUSES = ("Backlog", "Ready", "In Progress", "Done")
# A fenced code block, from its opening fence through a closing fence of the same character at
# least as long, or through the end of the file when it is never closed (CommonMark 4.5).
_FENCED_BLOCK_RE = re.compile(
    r"^[ \t]*(?:(?P<ticks>`{3,})[^`\n]*|(?P<tildes>~{3,})[^\n]*)\n"
    r".*?(?:^[ \t]*(?(ticks)(?P=ticks)`*|(?P=tildes)~*)[ \t]*$|\Z)",
    re.MULTILINE | re.DOTALL,
)
# An unchecked task-list item under any list marker, at any indent (GFM task list items).
_UNCHECKED_BOX_RE = re.compile(r"^[ \t]*(?:[-*+]|\d{1,9}[.)])[ \t]+\[ \]")


def _field(text: str, name: str) -> str | None:
    match = re.search(rf"^\*\*{name}\*\*:\s*(.*)$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def unchecked_boxes(text: str) -> list[str]:
    """Return the unchecked task-list lines outside fenced code blocks."""
    prose = _FENCED_BLOCK_RE.sub("", text)
    return [line for line in prose.splitlines() if _UNCHECKED_BOX_RE.match(line)]


@pytest.mark.parametrize("task_file", TASK_FILES, ids=lambda p: p.name)
def test_task_file_links_its_issue_and_ticks_only_done_work(task_file: Path) -> None:
    """Verify a task file links its issue, has no PR field, uses a task status, and has no `- [ ]`.

    The issue links its pull request through the closing keyword, and project cards take
    `In Review` from the open pull request, so neither belongs in the file. Recording a PR
    number took a second commit after the PR existed, which re-ran every check.

    A box is ticked only for work that is done. Work that was not done is a plain bullet naming
    its follow-up issue, and a check only a person can run is a plain bullet starting
    "Pending a person:". Before this rule, 15 files marked Done still held unchecked boxes.
    """
    text = task_file.read_text(encoding="utf-8")
    issue = _field(text, "Issue") or ""

    assert (
        bool(re.search(r"\[#\d+\]\(https://github\.com/[^)]+/(?:issues|pull)/\d+\)", issue)),
        _field(text, "PR"),
        _field(text, "Status") in STATUSES,
        unchecked_boxes(text),
    ) == (True, None, True, [])


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("- [ ] open\n", ["- [ ] open"]),
        ("- [x] done\n  - [ ] nested\n", ["  - [ ] nested"]),
        ("* [ ] starred\n", ["* [ ] starred"]),
        ("```markdown\n- [ ] an example\n```\n- [x] done\n", []),
        ("~~~\n````\n- [ ] still fenced\n~~~\n", []),
        ("- [x] done\n- Pending a person: `uv run devops ci`\n", []),
    ],
    ids=["dash", "indented", "star", "fenced", "tilde-fence", "plain-bullets"],
)
def test_an_unchecked_box_outside_a_fence_fails(text: str, found: list[str]) -> None:
    """Pin the rule on literal text, since every committed task file already satisfies it."""
    assert unchecked_boxes(text) == found


def test_task_files_exist() -> None:
    """Guard the parametrised check against silently running over nothing."""
    assert len(TASK_FILES) > 100
