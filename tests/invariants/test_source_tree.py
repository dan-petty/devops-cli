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


def test_one_path_validates_a_structured_reply_and_reflects_its_errors(
    parsed_source_trees: ParsedTreeMap,
) -> None:
    """`chat_structured` is the one path that validates a model reply against a schema, sends the
    model the errors and asks again (#1003): no other module builds a schema reflection."""
    assert _schema_reflection_calls_outside(parsed_source_trees, _STRUCTURED_OUTPUT_MODULES) == []
