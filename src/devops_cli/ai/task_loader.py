"""Shared task prompt loader for markdown prompt files in ai/tasks/.

All modules that need to load markdown task prompts should import from here
instead of defining their own `_load_task_prompt` helper.
"""

from __future__ import annotations

from pathlib import Path

_TASKS_DIR = Path(__file__).resolve().parent / "tasks"


def load_task_prompt(filename: str) -> str:
    """Load a markdown prompt file from the ai/tasks/ directory.

    Returns the file contents stripped of leading/trailing whitespace,
    or an empty string if the file does not exist or is outside the tasks directory.
    """
    target_path = (_TASKS_DIR / filename).resolve()
    if not target_path.is_relative_to(_TASKS_DIR) or not target_path.is_file():
        return ""
    return target_path.read_text(encoding="utf-8").strip()
