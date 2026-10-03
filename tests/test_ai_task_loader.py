"""Every prompt the code loads by name exists (#950).

`load_task_prompt` returns an empty string for a missing file, so a misspelt or never-written
prompt reaches a model as nothing at all: the benchmark suite sent empty system and user
prompts from `benchmark_suite_system.md` and `benchmark_suite_user.md`, which never existed.
"""

from __future__ import annotations

import ast
from pathlib import Path

from devops_cli.ai.task_loader import load_task_prompt

_SRC = Path(__file__).resolve().parent.parent / "src" / "devops_cli"


def _named_prompts() -> dict[str, list[str]]:
    """Each literal file name passed to `load_task_prompt` in `src/`, with where it is passed."""
    named: dict[str, list[str]] = {}
    for module in sorted(_SRC.rglob("*.py")):
        source = module.read_text(encoding="utf-8")
        if "load_task_prompt" not in source:
            continue
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            first = node.args[0]
            if name == "load_task_prompt" and isinstance(first, ast.Constant):
                place = f"{module.relative_to(_SRC)}:{node.lineno}"
                named.setdefault(str(first.value), []).append(place)
    return named


def test_every_prompt_loaded_by_name_exists() -> None:
    """Verify each prompt file the code names loads with content."""
    named = _named_prompts()

    missing = {name: places for name, places in named.items() if not load_task_prompt(name)}

    assert (bool(named), missing) == (True, {})
