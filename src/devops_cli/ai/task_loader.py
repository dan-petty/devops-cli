"""Shared task prompt loader for markdown prompt files in ai/tasks/.

All modules that need to load markdown task prompts should import from here
instead of defining their own `_load_task_prompt` helper.

A caller that passes a context renders the file as a Jinja2 template, so a prompt can take a
project fact (#4633). A caller that passes no context gets the file text with its markers, so a
prompt that fills its own markers, or a benchmark prompt that holds a GitHub `${{ }}` expression,
keeps its text.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from devops_cli.exceptions.ai import TaskPromptNotFoundError

_TASKS_DIR = Path(__file__).resolve().parent / "tasks"


@lru_cache(maxsize=1)
def prompt_environment() -> SandboxedEnvironment:
    """The shared Jinja2 environment of the task prompts.

    `StrictUndefined` raises on a value that a context does not hold, so a renamed value fails
    instead of rendering empty. No `trim_blocks`, no `lstrip_blocks` and `keep_trailing_newline`
    keep the text of a prompt that renders byte-identical today, and autoescape is off because a
    prompt is Markdown.
    """
    return SandboxedEnvironment(
        undefined=StrictUndefined,
        trim_blocks=False,
        lstrip_blocks=False,
        keep_trailing_newline=True,
        autoescape=False,
    )


def load_task_prompt(filename: str, /, **context: Any) -> str:
    """Load a markdown prompt file from the ai/tasks/ directory.

    With `context`, render the file as a Jinja2 template with `context` as its values, so a prompt
    that holds `{{ name }}` takes the value in place of the marker. With no `context`, return the
    file text with its markers.

    Returns the text stripped of leading and trailing whitespace. Raises `TaskPromptNotFoundError`
    when the name is not a file inside the tasks directory, and `jinja2.UndefinedError` when the
    context does not hold a value that the template names.
    """
    target_path = (_TASKS_DIR / filename).resolve()
    if not target_path.is_relative_to(_TASKS_DIR) or not target_path.is_file():
        raise TaskPromptNotFoundError(filename)
    text = target_path.read_text(encoding="utf-8")
    if not context:
        return text.strip()
    return prompt_environment().from_string(text).render(**context).strip()
