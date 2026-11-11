"""The task prompts of `ai/tasks/`: each name the code loads exists, and each file has a reader (#950, #4630).

`review_prompt_digest` hashes every file of the folder, so a file that no code reads still moves
the review benchmark arm when someone edits it.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import NamedTuple

from tests.support.paths import REPO_ROOT

_SRC = REPO_ROOT / "src"
_TASKS = _SRC / "devops_cli" / "ai" / "tasks"
_LOADER = "load_task_prompt"
# A chain of imports longer than this is a cycle, and the name stays unresolved.
_MAX_IMPORT_HOPS = 8


class _Bindings(NamedTuple):
    """The top-level string constants of a module, and the names it imports with their source."""

    strings: dict[str, str]
    imports: dict[str, tuple[str, str]]


def _module_name(path: Path, src: Path) -> str:
    """The dotted name of a module under `src`."""
    parts = path.relative_to(src).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _string_binding(node: ast.stmt) -> tuple[str, str] | None:
    """The name and the string of `NAME = "..."` or `NAME: T = "..."`, else None."""
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target, value = node.targets[0], node.value
    elif isinstance(node, ast.AnnAssign):
        target, value = node.target, node.value
    else:
        return None
    if isinstance(target, ast.Name) and isinstance(value, ast.Constant):
        return (target.id, value.value) if isinstance(value.value, str) else None
    return None


def _bindings(tree: ast.Module) -> _Bindings:
    """The bindings of a module that can hold a prompt name."""
    strings: dict[str, str] = {}
    imports: dict[str, tuple[str, str]] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for alias in node.names:
                imports[alias.asname or alias.name] = (node.module, alias.name)
        elif (bound := _string_binding(node)) is not None:
            strings[bound[0]] = bound[1]
    return _Bindings(strings, imports)


def _constant(modules: Mapping[str, _Bindings], module: str, name: str) -> str | None:
    """The string that `name` holds in `module`, through `from` imports, or None for a name that
    is not a constant, such as a parameter or a local variable."""
    for _ in range(_MAX_IMPORT_HOPS):
        strings, imports = modules.get(module, _Bindings({}, {}))
        if name in strings:
            return strings[name]
        if name not in imports:
            return None
        module, name = imports[name]
    return None


def _loaded_names(trees: Mapping[Path, ast.Module], src: Path) -> Iterator[tuple[str, str]]:
    """Each prompt name given to `load_task_prompt` as a literal or a constant, with its place."""
    modules = {_module_name(path, src): _bindings(tree) for path, tree in trees.items()}
    for path, tree in trees.items():
        module = _module_name(path, src)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and node.args):
                continue
            func = node.func
            called = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            first = node.args[0]
            if called != _LOADER:
                continue
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                yield first.value, f"{path.relative_to(src)}:{node.lineno}"
            elif isinstance(first, ast.Name) and (value := _constant(modules, module, first.id)):
                yield value, f"{path.relative_to(src)}:{node.lineno}"


def missing_prompts(
    trees: Mapping[Path, ast.Module], src: Path = _SRC, tasks: Path = _TASKS
) -> dict[str, list[str]]:
    """Each prompt name the code loads that is not a file of `tasks`, with the places that load
    it. The key `<none>` holds no place when the code loads no prompt by a name it states."""
    loaded = list(_loaded_names(trees, src))
    missing: dict[str, list[str]] = {} if loaded else {"<none>": []}
    for name, place in loaded:
        if not (tasks / name).is_file():
            missing.setdefault(name, []).append(place)
    return missing


def unread_prompts(trees: Mapping[Path, ast.Module], tasks: Path = _TASKS) -> list[str]:
    """Each file of `tasks` whose name no string literal of the modules holds."""
    named = {
        node.value
        for tree in trees.values()
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    return sorted(path.name for path in tasks.glob("*.md") if path.name not in named)


def check_every_prompt_the_code_loads_exists(parsed_source_trees: dict[Path, ast.Module]) -> None:
    """Each literal or constant name given to `load_task_prompt` names a file of `ai/tasks/`."""
    assert missing_prompts(parsed_source_trees) == {}


def check_every_task_prompt_has_a_reader(parsed_source_trees: dict[Path, ast.Module]) -> None:
    """Each file of `ai/tasks/` is named by a string literal of `src/`, so no file is an orphan."""
    assert unread_prompts(parsed_source_trees) == []
