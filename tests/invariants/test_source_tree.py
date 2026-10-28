"""Source-tree invariants: rules that hold over every module under `src/`."""

from __future__ import annotations

import ast
from pathlib import Path

from tests.support.paths import REPO_ROOT
from tests.support.trees import ParsedTreeMap

# The one structured-output path, and the module that defines the reflection it sends (#1003).
_STRUCTURED_OUTPUT_MODULES = frozenset(
    {"devops_cli/ai/client/structured.py", "devops_cli/ai/schema_reflection.py"}
)
_SCHEMA_REFLECTION_CALLS = frozenset(
    {"extract_schema_reflection", "build_schema_reflection_message"}
)


def _called_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _schema_reflection_calls_outside(trees: ParsedTreeMap, allowed: frozenset[str]) -> list[str]:
    src = (REPO_ROOT / "src").resolve()
    calls: list[str] = []
    for path, tree in trees.items():
        rel = Path(path).resolve().relative_to(src).as_posix()
        if rel in allowed:
            continue
        calls.extend(
            f"{rel}:{node.lineno}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and _called_name(node) in _SCHEMA_REFLECTION_CALLS
        )
    return sorted(calls)


def _reports_of_a_devops_error(node: ast.AST) -> list[tuple[int, str]]:
    """The lines at which `node` reports a `DevOpsCLIError` itself, each with what it uses."""
    if isinstance(node, ast.keyword) and node.arg == "exit_on":
        return [(node.value.lineno, "exit_on=")]
    if isinstance(node, ast.Name) and node.id == "exit_on_error":
        return [(node.lineno, "exit_on_error")]
    if not isinstance(node, ast.ExceptHandler) or node.name is None:
        return []
    exit_status = f"{node.name}.exit_code"
    return [
        (raised.lineno, f"typer.Exit({exit_status})")
        for raised in ast.walk(node)
        if isinstance(raised, ast.Raise)
        and raised.exc is not None
        and exit_status in ast.unparse(raised.exc)
    ]


def _reports_of_devops_errors_in_commands(trees: ParsedTreeMap) -> list[str]:
    src = (REPO_ROOT / "src").resolve()
    found: list[str] = []
    for path, tree in trees.items():
        rel = Path(path).resolve().relative_to(src).as_posix()
        if rel.startswith("devops_cli/commands/"):
            found.extend(
                f"{rel}:{line} {used}"
                for node in ast.walk(tree)
                for line, used in _reports_of_a_devops_error(node)
            )
    return sorted(found)


def test_commands_leave_the_report_of_a_devops_error_to_the_exit_seam(
    parsed_source_trees: ParsedTreeMap,
) -> None:
    """The wrapper of `new_typer()` reports every `DevOpsCLIError` that a command raises (#2487),
    so no command module reports one itself: no `exit_on=`, no `exit_on_error` and no
    `raise typer.Exit(exc.exit_code)` in an `except`."""
    assert _reports_of_devops_errors_in_commands(parsed_source_trees) == []


def test_one_path_validates_a_structured_reply_and_reflects_its_errors(
    parsed_source_trees: ParsedTreeMap,
) -> None:
    """`chat_structured` is the one path that validates a model reply against a schema, sends the
    model the errors and asks again (#1003): no other module builds a schema reflection."""
    assert _schema_reflection_calls_outside(parsed_source_trees, _STRUCTURED_OUTPUT_MODULES) == []
