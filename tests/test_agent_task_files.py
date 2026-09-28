"""Task files link their GitHub issue only; pull request and review state stay on GitHub."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

TASKS_DIR = Path("docs/agent/tasks")
TASK_FILES = sorted(TASKS_DIR.glob("task-*.md"))
STATUSES = ("Backlog", "Ready", "In Progress", "Done")


def _field(text: str, name: str) -> str | None:
    match = re.search(rf"^\*\*{name}\*\*:\s*(.*)$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


@pytest.mark.parametrize("task_file", TASK_FILES, ids=lambda p: p.name)
def test_task_file_links_its_issue_and_keeps_review_state_on_github(task_file: Path) -> None:
    """Verify a task file links its issue, has no PR field, and uses a task status.

    The issue links its pull request through the closing keyword, and project cards take
    `In Review` from the open pull request, so neither belongs in the file. Recording a PR
    number took a second commit after the PR existed, which re-ran every check.
    """
    text = task_file.read_text(encoding="utf-8")
    issue = _field(text, "Issue") or ""

    assert (
        bool(re.search(r"\[#\d+\]\(https://github\.com/[^)]+/(?:issues|pull)/\d+\)", issue)),
        _field(text, "PR"),
        _field(text, "Status") in STATUSES,
    ) == (True, None, True)


def test_task_files_exist() -> None:
    """Guard the parametrised check against silently running over nothing."""
    assert len(TASK_FILES) > 100
